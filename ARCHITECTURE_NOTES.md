# DocPilot Architecture Notes

Findings from inspecting the repository (backend, Alembic migrations, tests, frontend, `compose.yaml`, `Makefile`). Diagrams are in [docs/diagrams/](docs/diagrams/); see the table in [README.md](README.md).

**Conventions.** *Verified* = read directly in code, migrations or tests. *Interpretation* = a reasoned reading of the code, not proven by it. *Uncertain* = could not be established from the repository. The test suite and the application were **not executed**; nothing below is based on runtime observation.

---

## 1. Verified facts

### 1.1 Components and responsibilities

| Component | Location | Responsibility |
|-----------|----------|----------------|
| App entry | `backend/app/main.py` | Creates FastAPI app, includes 9 routers (health, version, documents, organizations, search, chat, conversations, auth, evaluations). |
| Settings | `core/config.py` | pydantic-settings from `<root>/.env`. `database_url` and `jwt_secret_key` are required. |
| Routes | `api/routes/*`, `auth/routes.py` | HTTP boundary. `chat.py` (963 lines) contains routing, query rewrite, context building, guard and persistence inline; there is no chat service. `conversations.py` queries models directly. |
| Auth | `auth/*` | JWT issue/verify, Argon2 hashing, `get_current_user`, `get_organization_access`, `require_organization_roles`, role-management rules. |
| Services | `services/*` | Document/version CRUD + storage, organization and membership logic, retrieval, ingestion, evaluation CRUD/runner, LLM client. |
| Processing | `parsers/`, `normalization/`, `chunking/`, `processing/` | Registry-based parse → normalize → chunk, assembled by `processing/factory.py`. |
| Embeddings | `embeddings/` | `EmbeddingProvider` interface; one implementation, `LocalBGEEmbeddingProvider` (BAAI/bge-m3, dense only, 1024-d). |
| Storage | `storage/` | `StorageService` interface; one implementation, `LocalStorage` with path-traversal protection. |
| Models | `models/` | 13 tables (see diagram 05). |
| Frontend | `frontend/src` | React SPA with login, org picker, Chat, Files, Eval pages; `lib/api.js` wraps the REST API. |

### 1.2 Main request and data flows

- **Upload → index.** The request saves the file, creates the version with status `pending`, and returns 201. A FastAPI `BackgroundTasks` job in the same process then sets `processing`, runs parse/normalize/chunk and BGE-M3 embedding in a threadpool, locks the version row, replaces its chunks and embeddings in one transaction and sets `completed`; any exception sets `failed`. (Diagram 04.)
- **Chat.** Auth → membership → optional conversation ownership check → regex routing → (optional LLM rewrite) → embed → hybrid retrieval → context (12,000 chars) → one LLM call → deadline guard → persist both messages in one commit → respond with answer, sources, trace. LLM failure returns 503 and persists nothing. (Diagrams 08, 09.)
- **Evaluation.** A run is created, then each case is embedded, retrieved, answered and scored sequentially inside the request; each result is committed individually; run metrics are means of per-case values. (Diagram 10.)

### 1.3 Database and multi-tenancy

- Linear Alembic chain, head `c4f91a2d7e60`: `ead90c65e5e9` → `194464cb75ed` → `758729bc7295` → `a690a96a1c58` → `59951fb83652` → `92b58f83987a` → `a3ed5f65c7ce` → `618942c83d29` → `b2e7a91c4d60` → `c4f91a2d7e60`. Models and migrations agree on tables, columns and FKs for the checked entities.
- Tenant key is `organizations.id`. It is a direct column on `documents`, `conversations`, `evaluation_datasets`; `chunks`, `chunk_embeddings`, cases, runs and results are tenant-scoped only through joins (`chunks → document_versions → documents`, `runs → datasets`).
- Isolation is application-level: the path `organization_id` is checked against `memberships` for the JWT user, and all queries filter by that organization. No row-level security exists in models or migrations.
- Conversations are additionally private to their creator; mismatches return 404 (not 403).
- Roles (`owner`/`admin`/`member`) are a CHECK-constrained string. Only the owner can delete an organization; the owner role cannot be assigned through any endpoint, so each organization has the creating user as its sole owner.
- FK delete behaviour: most tenant children cascade; `documents.created_by_user_id` and `document_versions.uploaded_by_user_id` have no DB-level `ondelete`, and account deletion nulls them in application code (made nullable by migration `c4f91a2d7e60`); evaluation datasets/runs use `SET NULL` for user references; `evaluation_results.case_id` is `SET NULL`.
- `evaluation_cases.relevant_document_ids` is JSONB, not a foreign key. Referential integrity is checked only at import/create time.

### 1.4 Ingestion and retrieval behaviour

- Supported extensions: `.pdf .docx .xlsx .txt .md .markdown`. Upload does not validate type.
- Chunking defaults: target 500, max 800, overlap 75 "tokens", counted by whitespace splitting (`SimpleTokenCounter`, documented in code as "for testing and development" but used by the production factory).
- DOCX: paragraphs only; `table_count` is recorded in metadata, table content is not extracted. PDF: PyMuPDF text plus detected tables; no OCR code exists.
- One embedding row per (chunk, model); dimension fixed to 1024 by a CHECK constraint and `Vector(1024)`.
- Retrieval: vector branch (exact cosine-distance ordering, filtered by organization and embedding model name) + keyword branch (`to_tsvector('simple')` with `websearch_to_tsquery`, OR escaped `ILIKE`, backed by a GIN index) → RRF with constant 60 over a candidate pool of `min(max(4·top_k, 20), 100)` → heuristic multipliers → top_k.
- No `hnsw`/`ivfflat` index exists anywhere in the code or migrations.
- Retrieval does not filter on `ingestion_status` or on "latest version"; chunks exist only for versions whose ingestion transaction committed, and all such versions stay searchable.

### 1.5 Chat and evaluation implementation

- Chat is a single JSON response; there is no SSE/WebSocket endpoint. `ChatResponse.trace` carries measured step timings.
- Rule-based paths bypass retrieval and/or the LLM: name introduction/recall, small talk (LLM, no documents), general-knowledge questions (LLM, no documents), "which document" questions (saved sources, no LLM), no retrieved chunks (fixed fallback, no LLM).
- History (last 10 messages, ≤1,200 chars) is used only for the standalone-question rewrite, never in the answer prompt. Prior sources are reused only from the immediately preceding assistant message.
- `_guard_year_specific_admissions_deadline` post-processes answers about year-specific admissions deadlines. Retrieval boosts include a hard-coded "refund" intent and historical-policy handling. These are domain-specific.
- Evaluation implements: `hit_rate_at_k`, `recall_at_k`, `reciprocal_rank` (document level, unique documents), `essential_fact_coverage` (normalized substring match of `metadata.essential_facts`), `answerability_compliance` (`metadata.answerable` vs. fixed abstention phrases). The stored `reference_answer` is not used by any metric.
- Evaluation uses its own system prompt and truncates context to 3,000 characters; it does not run chat's routing, rewrite or guard.
- JSONL import: ≤2,000 lines, all-or-nothing, duplicate `case_id` rejection, optional label→UUID mapping, full record retained in case metadata.

### 1.6 Storage and model-integration boundaries

- Storage boundary: `StorageService` (`save/open/delete/exists`). Keys: `organizations/{org}/documents/{doc}/versions/{n}/original{.ext}`. DB commit precedes file deletion on document/org deletion; failures there are logged, not raised (orphaned files are possible).
- LLM boundary: `OpenAICompatibleLLMClient` posts to `{LLM_BASE_URL}/chat/completions` (temperature 0.2, `enable_thinking: false` in `chat_template_kwargs`, which is llama.cpp/Qwen3-specific). The base URL, model name and API key are configurable, so another OpenAI-compatible endpoint can be used.
- Embedding boundary: in-process library call, not a network service.
- Frontend boundary: `VITE_API_BASE_URL` (default `/api`); Vite proxies `/api` to `DOC_PILOT_API_TARGET` (default `http://127.0.0.1:8000`) and strips the prefix. The backend has no CORS middleware.

### 1.7 Deployment

`compose.yaml` defines exactly two services: `postgres` (pgvector pg17, host port 5433, named volume) and `llama-server` (llama.cpp CUDA image, host port 3000, GPU reservation, Qwen3-1.7B Q4_K_M via `-hf`). Backend and frontend run on the host through `make dev` (uvicorn `--reload` on 127.0.0.1:8000, Vite on 127.0.0.1:5173). Migrations are a manual step (`make migrate`). No Dockerfile, CI configuration, production config or secret management exists in the archive.

---

## 2. Architectural decisions evident in the code

- **Postgres as the only data store**, including vectors (pgvector) and keyword search (GIN full-text); simple to operate, and tenant filtering stays in one SQL layer.
- **Pluggable seams with one implementation each**: `EmbeddingProvider`, `StorageService`, parser/normalizer registries, `Chunker` protocol. Dependency overrides make tests independent of real models and disk.
- **Process → embed outside the DB lock, persist inside a short locked transaction**, replacing prior chunks atomically (`ingestion.py`).
- **Evidence-first answering**: the answer call receives only the standalone question and retrieved excerpts, with "untrusted reference data" instructions; saved attribution is answered without the LLM.
- **Org-scoped everything through the URL** (`/organizations/{id}/...`), with a single dependency enforcing membership.
- **Snapshots for history**: message `sources` and evaluation result question/answer/sources/metadata are stored by value so history survives later edits or deletions.
- **Chat turn atomicity**: nothing is persisted until the answer exists.

---

## 3. Inconsistencies, uncertainties and limitations

### 3.1 Verified inconsistencies

1. `.env.example` omits the required `JWT_SECRET_KEY` and uses DB password `change-me`, while `compose.yaml` uses `docpilot_dev`.
2. `core/lifespan.py` sets `app.state.storage`, but `get_storage()` returns a separate module-level `LocalStorage`; the app-state object is unused.
3. `ingestion_task` calls `get_default_embedding_provider()` directly, so an embedding provider placed on `app.state` (which the request-time dependency honors) does not affect background ingestion.
4. The delete-account dialog tells users to "transfer or delete" owned organizations, but no ownership-transfer endpoint exists and the owner role cannot be assigned.
5. `api.js` has no member-management or search calls, so those backend features have no UI.
6. `frontend/src/hooks/useMockChat.js` is named "mock" but calls the real API; it also holds an inert streaming state. `frontend/src/data/mock*.js` are not imported anywhere (dead code).
7. `models/__init__.py` lists the evaluation models in `__all__` before importing them (works at runtime; ordering only).
8. Migration `758729bc7295` backfills a hard-coded Argon2 hash for any pre-existing users; this only matters for databases that had users before that revision.
9. `vite.config.ts` defaults to port 8443 while `make dev` forces 5173.
10. The frontend `package.json` name (`figma-make-app`) and `.figma/` directory indicate generated scaffolding that was not renamed.

### 3.2 Observations that depend on interpretation

- **Message ordering within a turn.** Both messages of a turn are inserted in one transaction, so their `created_at` (`now()`) is likely identical. The conversation-detail endpoint breaks ties explicitly (`role desc`), but the history query used for rewrites orders by `created_at desc, id desc` with random UUIDs, so the user/assistant order inside one turn may be arbitrary in the rewrite history. Not confirmed at runtime.
- **Login email casing.** Registration lowercases the email; login and `add_member` compare the submitted string as given. Whether `EmailStr` normalization masks this was not tested.
- **Scanned PDFs.** With no OCR, an image-only PDF would probably yield zero chunks and may be marked `completed` with nothing indexed (empty embedding batch is handled). Not tested.
- **Crash recovery.** No code resets a version left in `processing` after a process crash; none was found in `lifespan.py`.
- **Heuristic tuning.** Admissions-deadline and refund rules suggest the retrieval/chat logic was tuned against a specific school-administration benchmark; how general it is cannot be judged from the repository.
- **Evaluation vs. chat.** Because evaluation bypasses chat routing and uses a smaller context, evaluation scores describe retrieval plus a simplified answer path, not the full chat behavior.

### 3.3 Uncertain / unresolved from the repository

- Whether BGE-M3 and Qwen weights are fetched from Hugging Face at runtime. This is implied by `FlagEmbedding` and the `-hf` flag but not demonstrated; cache locations for BGE-M3 are not configured by the repo.
- How the `docpilot_test` database is created and migrated for tests (not scripted).
- Real-model behavior (answer quality, retrieval quality, latency); the real-model tests are opt-in and were not run.
- Any production deployment plan; none is present.
- Whether `.github` workflows ever existed; `.dockerignore` mentions `.git`/`.github`, but no such directory is in the archive.

### 3.4 Limitations (current state, not recommendations)

Single-process ingestion without retries; exact (non-indexed) vector scan; older versions remain searchable; whitespace tokenization; no OCR; DOCX tables skipped; non-streaming chat; application-level (not DB-level) tenant isolation; evaluation open to all members and run synchronously; no CORS/TLS/production packaging; single access token with no refresh or revocation.

---

## 4. Diagram-to-source map

| Diagram | Main sources |
|---------|--------------|
| 01, 02, 12 | `compose.yaml`, `Makefile`, `core/config.py`, `vite.config.ts`, `llm.py` |
| 03 | imports across `backend/app` |
| 04 | `routes/documents.py`, `services/document.py`, `ingestion.py`, `ingestion_task.py`, `processing/*`, parsers, normalization, chunking |
| 05 | `models/*.py`, `alembic/versions/*` |
| 06 | `auth/*`, `routes/organizations.py`, `services/membership.py`, tests `test_authorization.py`, `test_organizations.py`, `test_documents.py` |
| 07 | `services/retrieval.py`, `routes/chat.py` (`_build_retrieved_context`), tests `test_retrieval.py` |
| 08, 09 | `routes/chat.py`, `routes/conversations.py`, tests `test_chat.py` |
| 10 | `routes/evaluations.py`, `services/evaluation_runner.py`, tests `test_evaluations.py` |
| 11 | all routers, `api/dependencies.py`, `frontend/src/lib/api.js` |
