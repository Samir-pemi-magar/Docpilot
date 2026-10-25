# DocPilot Architecture Notes

Findings from inspecting the repository (backend, Alembic migrations, tests, frontend, `compose.yaml`, `Makefile`, root-level scripts). Diagrams are in [docs/diagrams/](docs/diagrams/README.md). What changed relative to the previous version of these notes is itemised in [docs/DOC_AUDIT.md](docs/DOC_AUDIT.md).

**Conventions.** *Verified* = read directly in code, migrations or tests. *Interpretation* = a reasoned reading of the code, not proven by it. *Uncertain* = could not be established from the repository. This is a static review: the test suite and the application were **not executed**. The one exception is noted in section 3.1, item 11, where a single pure function was extracted and run in isolation.

---

## 1. Verified facts

### 1.1 Components and responsibilities

| Component | Location | Responsibility |
|-----------|----------|----------------|
| App entry | `backend/app/main.py` | Creates the FastAPI app, includes 9 routers (health, version, documents, organizations, search, chat, conversations, auth, evaluations). No CORS middleware. |
| Settings | `core/config.py` | pydantic-settings from `<root>/.env`. `database_url` and `jwt_secret_key` are required. LLM settings: base URL, API key, model alias, timeout, and five thinking-mode settings (section 1.5). |
| Routes | `api/routes/*`, `auth/routes.py` | HTTP boundary. `chat.py` (967 lines) contains routing, query rewrite, context building, guard and persistence inline; there is no chat service. `conversations.py` queries models directly. |
| Auth | `auth/*` | JWT issue/verify (HS256, 30 min default), Argon2 hashing, `get_current_user`, `get_organization_access`, `require_organization_roles`, role-management rules. |
| Services | `services/*` | Document/version CRUD + storage, organization and membership logic, retrieval, ingestion, evaluation CRUD/import, evaluation runner, LLM client. |
| Processing | `parsers/`, `normalization/`, `chunking/`, `processing/` | Registry-based parse → normalize → chunk, assembled by `processing/factory.py`. |
| Embeddings | `embeddings/` | `EmbeddingProvider` interface; one implementation, `LocalBGEEmbeddingProvider` (BAAI/bge-m3, dense only, 1024-d, `max_length` 1024, batches of up to 8). |
| Storage | `storage/` | `StorageService` interface; one implementation, `LocalStorage` with path-traversal protection. |
| Models | `models/` | 13 tables (diagram 05). |
| Frontend | `frontend/src` | React 19 SPA: login/register, organization picker, and three pages (Chat, Eval, File Manager). A sidebar lists, opens, starts and deletes conversations. `lib/api.js` wraps the REST API. |
| Tooling | repo root, `backend/bge_m3_*.py` | Retrieval and answer benchmarks, probe script, embedding smoke tests (diagram 14). |

### 1.2 Main request and data flows

- **Upload → index.** The request saves the file, creates the version with status `pending`, and returns 201. A FastAPI `BackgroundTasks` job in the same process then sets `processing`, runs parse/normalize/chunk and BGE-M3 embedding in a threadpool, locks the version row, replaces its chunks and embeddings in one transaction and sets `completed`; any exception sets `failed`. (Diagram 04.)
- **Chat.** Auth → membership → optional conversation ownership check → regex routing → (optional LLM rewrite) → embed → hybrid retrieval → context (12,000 chars) → one LLM call → deadline guard → persist both messages in one commit → respond with answer, sources, trace. LLM failure returns 503 and persists nothing. The SPA sends `top_k = 5` and then refreshes the conversation list. (Diagrams 08, 09, 13.)
- **Evaluation.** `POST .../runs` inserts a run with status `pending`, returns 201, and schedules `run_evaluation_background` as a `BackgroundTasks` job with its own DB session. The job sets `running`, then embeds, retrieves, answers and scores each case sequentially, committing each result individually; run metrics are means of per-case values. The SPA polls the run every 800 ms until it is `completed` or `failed`. (Diagram 10.)

### 1.3 Database and multi-tenancy

- Linear Alembic chain, head `c4f91a2d7e60`: `ead90c65e5e9` → `194464cb75ed` → `758729bc7295` → `a690a96a1c58` → `59951fb83652` → `92b58f83987a` → `a3ed5f65c7ce` → `618942c83d29` → `b2e7a91c4d60` → `c4f91a2d7e60`. Models and migrations agree on tables, columns and FKs for the checked entities. No schema change since the previous notes.
- Tenant key is `organizations.id`. It is a direct column on `documents`, `conversations`, `evaluation_datasets`; `chunks`, `chunk_embeddings`, cases, runs and results are tenant-scoped only through joins (`chunks → document_versions → documents`, `runs → datasets`).
- Isolation is application-level: the path `organization_id` is checked against `memberships` for the JWT user, and all queries filter by that organization. No row-level security exists in models or migrations.
- Conversations are additionally private to their creator; mismatches return 404 (not 403).
- Roles (`owner`/`admin`/`member`) are a CHECK-constrained string. Only the owner can delete an organization; the owner role cannot be assigned through any endpoint, so each organization has the creating user as its sole owner.
- FK delete behaviour: most tenant children cascade; `documents.created_by_user_id` and `document_versions.uploaded_by_user_id` have no DB-level `ondelete`, and account deletion nulls them in application code (made nullable by migration `c4f91a2d7e60`); evaluation datasets/runs use `SET NULL` for user references; `evaluation_results.case_id` is `SET NULL`.
- `evaluation_cases.relevant_document_ids` is JSONB, not a foreign key. Referential integrity is checked only at import/create time.

### 1.4 Ingestion and retrieval behaviour

- Supported extensions: `.pdf .docx .xlsx .txt .md .markdown`. Upload does not validate type.
- Chunking defaults: target 500, max 800, overlap 75 "tokens", counted by whitespace splitting (`SimpleTokenCounter`, documented in code as "for testing and development" but used by the production factory).
- **PDF:** PyMuPDF per page. Pages with detected tables emit table elements (rows joined with ` | `, title from a leading `Table N` header cell or a short nearby heading) plus prose blocks that do not overlap a table. No OCR code exists.
- **DOCX:** the body is walked in order, so headings, paragraphs **and tables** are all extracted. Tables use the same shape as PDF tables (`" | "`-joined rows, `content={"rows": ...}`), with the title taken from a `Table N` first cell or the last heading, so the structured chunker handles them. `table_count` is also kept in metadata.
- **XLSX:** the workbook is opened twice (formulas and saved results). A formula cell is indexed by its saved value; if a sheet has saved results and a formula has none (an empty result), that cell is skipped instead of indexed as raw formula text. The normalizer finds dense rectangular cell regions and classifies them as `table` or `key_value`.
- **Structured chunker:** rows are never split; the header row is repeated in every chunk of a table, and a context prefix (`Worksheet:`, `Table:`, `Page:`) is prepended to the embedded text.
- One embedding row per (chunk, model); dimension fixed to 1024 by a CHECK constraint and `Vector(1024)`.
- **Retrieval** (`retrieve_hybrid_chunks`), three candidate lists fused with reciprocal-rank fusion (constant 60) over a pool of `min(max(4·top_k, 20), 100)`:
  1. vector: exact cosine-distance ordering, filtered by organization and embedding model name, weight 1.0;
  2. strict keyword: `to_tsvector('simple')` with `websearch_to_tsquery` (every word must match) OR escaped `ILIKE`, backed by a GIN index, weight 1.0;
  3. **OR keyword** (`retrieve_keyword_or_chunks`): stopwords removed, remaining words OR-ed, ranked by `ts_rank_cd`, 10 candidates, weight `KEYWORD_OR_WEIGHT = 0.10`. Setting the weight to 0 disables it.

  Heuristic multipliers then apply (table-title overlap ×3.0 / ×1.5 / ×1.2; historical or superseded table title ×0.5, or ×2.0 when the query asks about the past) before the top `top_k` are returned.
- No `hnsw`/`ivfflat` index exists anywhere in the code or migrations.
- Retrieval does not filter on `ingestion_status` or on "latest version"; chunks exist only for versions whose ingestion transaction committed, and all such versions stay searchable.
- **Context builder** (`_build_retrieved_context`, chat only): a chunk is treated as a table only when it has at least two lines containing `|` **and** those lines are at least half of its non-empty lines. Otherwise it is kept whole as prose. (This is the already-applied fix from `apply_chat_fix.py`.)

### 1.5 Chat, LLM and evaluation implementation

- Chat is a single JSON response; there is no SSE/WebSocket endpoint. `ChatResponse.trace` carries measured step timings. `streamingText` in the SPA hook is a constant empty string.
- Rule-based paths bypass retrieval and/or the LLM: name introduction/recall, small talk (LLM, no documents), general-knowledge questions (LLM, no documents), "which document" questions (saved sources, no LLM), no retrieved chunks (fixed fallback, no LLM).
- History (last 10 messages, ≤1,200 chars) is used only for the standalone-question rewrite, never in the answer prompt. The rewrite runs only when the question matches a follow-up pattern (`and …`, `what about …`, `how about …`, `tell me more`, and similar). Prior sources are reused only from the immediately preceding assistant message.
- **LLM client** (`services/llm.py`, diagram 13). One `generate()` entry point with two modes. *Fast:* `enable_thinking=false`, temperature 0.0, `max_tokens` 700. *Thinking:* `enable_thinking=true`, temperature 0.6, top-p 0.95, top-k 20, `max_tokens` 3000. In `auto` mode (default) thinking is used only for answer prompts (those shaped `Question:\n…\n\nRetrieved document excerpts:`) whose question contains a digit or reasoning wording (how much, refund, deadline, am I covered, can I, …). If thinking raises an error, times out, or is cut off before the answer (`<think>` left open), the client silently retries once in fast mode. `<think>…</think>` blocks are stripped from every response. Settings: `LLM_THINKING_MODE` (`auto|always|never`), `LLM_THINKING_TIMEOUT_SECONDS` (75), `LLM_THINKING_MAX_TOKENS` (3000), `LLM_THINKING_TEMPERATURE` (0.6), `LLM_MAX_TOKENS` (700). Covered by unit tests in `tests/test_llm.py` using a mock transport.
- `_guard_year_specific_admissions_deadline` post-processes answers about year-specific admissions deadlines. Retrieval boosts include a hard-coded "refund" intent and historical-policy handling. These are domain-specific.
- Evaluation implements: `hit_rate_at_k`, `recall_at_k`, `reciprocal_rank` (document level, unique documents), `essential_fact_coverage` (normalized substring match of `metadata.essential_facts`), `answerability_compliance` (`metadata.answerable` vs. fixed abstention phrases). The stored `reference_answer` is not used by any metric.
- Evaluation uses its own system prompt and truncates context to 3,000 characters; it does not run chat's routing, rewrite or guard. It does use the same LLM client, so thinking mode can apply to evaluation answers.
- JSONL import: ≤2,000 lines, all-or-nothing, duplicate `case_id` rejection, optional label→UUID mapping (the dashboard lets the user map each label to an uploaded document), full record retained in case metadata.

### 1.6 Storage and model-integration boundaries

- Storage boundary: `StorageService` (`save/open/delete/exists`). Keys: `organizations/{org}/documents/{doc}/versions/{n}/original{.ext}`. DB commit precedes file deletion on document/org deletion; failures there are logged, not raised (orphaned files are possible).
- LLM boundary: `OpenAICompatibleLLMClient` posts to `{LLM_BASE_URL}/chat/completions` with `chat_template_kwargs.enable_thinking` on every call, which is llama.cpp/Qwen3-specific. The base URL, model name and API key are configurable, so another OpenAI-compatible endpoint can be used.
- Embedding boundary: in-process library call, not a network service.
- Frontend boundary: `VITE_API_BASE_URL` (default `/api`); Vite proxies `/api` to `DOC_PILOT_API_TARGET` (default `http://127.0.0.1:8000`) and strips the prefix. The backend has no CORS middleware.

### 1.7 Deployment

`compose.yaml` defines exactly two services:

- `postgres`: `pgvector/pgvector:pg17`, host port 5433, named volume.
- `llama-server`: `ghcr.io/ggml-org/llama.cpp:server-cuda`, host port 3000, one NVIDIA GPU reserved. It loads **`/models/Qwen3-8B-Q4_K_M.gguf`** from the bind mount `./data/local_models`, with context 8192, `-ngl 99`, `--parallel 1` and alias `docpilot-qwen3-4b`. The model is **not downloaded automatically**; the file must be placed there by hand (`data/` is git-ignored).

Backend and frontend run on the host through `make dev`: uvicorn `--reload` on 127.0.0.1:8000 started with `CUDA_VISIBLE_DEVICES=` (empty, so BGE-M3 runs on the CPU and the GPU stays free for the LLM), and Vite on 127.0.0.1:5173. Migrations are a manual step (`make migrate`). No Dockerfile, CI configuration, production config or secret management exists in the archive.

### 1.8 Tests and tooling

- 288 test functions across `tests/` cover auth, authorization, database isolation, every parser, normalization, chunking, embeddings (fakes), ingestion, retrieval, search, chat, LLM client, evaluations and documents. `tests/conftest.py` forces `DATABASE_URL` to `…@localhost:5433/docpilot_test`, so API/DB tests need the Compose Postgres.
- Four real-model tests are skipped unless opted in: `RUN_REAL_BGE_TEST`, `RUN_REAL_RAG_CHAT`, `RUN_REAL_UPLOAD_RAG`, `RUN_REAL_WORKER_TEST`.
- Root-level scripts (diagram 14): `probe_retrieval.py`, `bench_retrieval.py` (no LLM; compares OR-keyword weights using `retrieval_cases*.json`), `bench_answers.py` (prompt variants, optional run through the app's own LLM client), `backend/bge_m3_smoke.py`, `backend/bge_m3_similarity.py`. `apply_chat_fix.py` and `apply_config.py` are one-off patch scripts whose changes are already present in `chat.py` and `config.py`.

---

## 2. Architectural decisions evident in the code

- **Postgres as the only data store**, including vectors (pgvector) and keyword search (GIN full-text); simple to operate, and tenant filtering stays in one SQL layer.
- **Pluggable seams with one implementation each**: `EmbeddingProvider`, `StorageService`, parser/normalizer registries, `Chunker` protocol. Dependency overrides make tests independent of real models and disk.
- **Process → embed outside the DB lock, persist inside a short locked transaction**, replacing prior chunks atomically (`ingestion.py`).
- **Evidence-first answering**: the answer call receives only the standalone question and retrieved excerpts, with "untrusted reference data" instructions; saved attribution is answered without the LLM.
- **Measured retrieval tuning**: the OR-keyword branch exists as a deliberately weak third list (weight 0.10) chosen by comparing settings in `bench_retrieval.py`, rather than as an equal partner.
- **Selective, bounded reasoning**: thinking mode is spent only where the question looks numeric or eligibility-related, is capped by tokens and time, and always has a fast-mode fallback.
- **Org-scoped everything through the URL** (`/organizations/{id}/...`), with a single dependency enforcing membership.
- **Snapshots for history**: message `sources` and evaluation result question/answer/sources/metadata are stored by value so history survives later edits or deletions.
- **Chat turn atomicity**: nothing is persisted until the answer exists.
- **Same background-task model for ingestion and evaluation**: respond immediately with `pending`, work in the same process with an independent DB session.

---

## 3. Inconsistencies, uncertainties and limitations

### 3.1 Verified inconsistencies

1. `.env.example` omits the required `JWT_SECRET_KEY` and uses DB password `change-me`, while `compose.yaml` and `tests/conftest.py` use `docpilot_dev`.
2. `core/lifespan.py` sets `app.state.storage`, but `get_storage()` returns a separate module-level `LocalStorage`; the app-state object is unused.
3. `ingestion_task` calls `get_default_embedding_provider()` directly, so an embedding provider placed on `app.state` (which the request-time dependency honors) does not affect background ingestion.
4. The delete-account dialog tells users to "transfer or delete" owned organizations, but no ownership-transfer endpoint exists and the owner role cannot be assigned.
5. `api.js` has no member-management or search calls, so those backend features have no UI. The SPA also never shows `ingestion_status`, so a failed ingestion is invisible in the UI.
6. `frontend/src/hooks/useMockChat.js` is named "mock" but calls the real API; its streaming state is inert. `frontend/src/data/mock*.js` are not imported anywhere (dead code). `components/eval/EvalHistoryChart.jsx.bak` is a stray backup file.
7. `models/__init__.py` lists the evaluation models in `__all__` before importing them (works at runtime; ordering only).
8. Migration `758729bc7295` backfills a hard-coded Argon2 hash for any pre-existing users; this only matters for databases that had users before that revision.
9. `vite.config.ts` defaults to port 8443 while `make dev` forces 5173.
10. The frontend `package.json` name (`figma-make-app`) and `.figma/` directory indicate generated scaffolding that was not renamed. `frontend/CLAUDE.md` and `AGENTS.md` describe a Figma Make environment and point to `src/App.tsx`, but the entry component is `src/App.jsx`.
11. **General-knowledge routing is too broad for non-school corpora.** `_is_general_knowledge_question` exempts only a school/organization vocabulary (`admission`, `tuition`, `policy`, `fee`, …) from its `who is …`, `what is …`, `why is …`, `how does … work` patterns. The function was extracted and run in isolation on insurance-style questions: *"Who is the Chief Claims Officer?"*, *"Who is Sandra Whitlow?"*, *"Who is the Customer Relations Manager?"* and *"How does the grace period work?"* all return `True`, which skips retrieval and sends the question to the model with no documents. *"What is the claims hotline number?"* and *"What is Comprehensive Plus?"* return `False`. Only the classifier was executed, not the endpoint, but the route code shows that a `True` result bypasses retrieval. Because evaluation runs bypass chat routing (section 1.5), the evaluation dashboard cannot reveal this.
12. **The thinking timeout cannot exceed `LLM_TIMEOUT_SECONDS`.** The thinking attempt uses `min(LLM_TIMEOUT_SECONDS, LLM_THINKING_TIMEOUT_SECONDS)`, which is 60 s with defaults even though the thinking setting is 75. Worst case for one answer is about 120 s (60 s thinking + 60 s fast).
13. **Model naming drift.** The container serves a Qwen3-**8B** file under the alias `docpilot-qwen3-4b`, which is also the `LLM_MODEL` default. It works (the server serves one model) but the name is misleading.
14. **Hard-coded organization id.** `probe_retrieval.py`, `bench_retrieval.py` and `bench_answers.py` default to `d209210b-3c5c-4181-ba4f-f9cfe4ff0df3`, an id from one developer's database.

### 3.2 Observations that depend on interpretation

- **Fresh clone and the LLM container.** Because the GGUF file is not downloaded and `restart: unless-stopped` is set, a missing file would most likely leave `llama-server` in a restart loop while `make dev` carries on with a warning. Not tested.
- **Message ordering within a turn.** Both messages of a turn are inserted in one transaction, so their `created_at` (`now()`) is likely identical. The conversation-detail endpoint breaks ties explicitly (`role desc`), but the history query used for rewrites orders by `created_at desc, id desc` with random UUIDs, so the user/assistant order inside one turn may be arbitrary in the rewrite history. Not confirmed at runtime.
- **Login email casing.** Registration lowercases the email; login and `add_member` compare the submitted string as given. Whether `EmailStr` normalization masks this was not tested.
- **Scanned PDFs.** With no OCR, an image-only PDF would probably yield zero chunks and may be marked `completed` with nothing indexed (empty embedding batch is handled). Not tested.
- **Crash recovery.** No code resets a version left in `processing`, or an evaluation run left in `pending`/`running`, after a process crash; none was found in `lifespan.py`.
- **Heuristic tuning.** Two corpora have shaped the code: a school-administration benchmark (admissions-deadline guard, general-knowledge and name-recall regexes, a "refund" boost) and the insurance corpus (OR-keyword branch, table-detection fix, thinking-mode triggers). How general the result is cannot be judged from the repository.
- **Evaluation vs. chat.** Because evaluation bypasses chat routing and uses a smaller context (3,000 vs 12,000 characters), evaluation scores describe retrieval plus a simplified answer path, not the full chat behavior.

### 3.3 Uncertain / unresolved from the repository

- Whether BGE-M3 weights are fetched from Hugging Face at runtime. This is implied by `FlagEmbedding` but not demonstrated; cache locations are not configured by the repo.
- How the `docpilot_test` database is created and migrated for tests (not scripted).
- Real-model behavior (answer quality, retrieval quality, latency); the real-model tests are opt-in and were not run.
- Any production deployment plan; none is present.
- Whether `.github` workflows ever existed; `.dockerignore` mentions `.git`/`.github`, but no such directory is in the archive.

### 3.4 Limitations (current state, not recommendations)

Single-process ingestion and evaluation runs without retries or crash recovery; exact (non-indexed) vector scan; older versions remain searchable; whitespace tokenization; no OCR; non-streaming chat; application-level (not DB-level) tenant isolation; evaluation open to all members; no CORS/TLS/production packaging; single access token with no refresh or revocation; GPU-dependent LLM container; no CI.

---

## 4. Diagram-to-source map

| Diagram | Main sources |
|---------|--------------|
| 01, 02, 12 | `compose.yaml`, `Makefile`, `core/config.py`, `vite.config.ts`, `llm.py` |
| 03 | imports across `backend/app` |
| 04 | `routes/documents.py`, `services/document.py`, `ingestion.py`, `ingestion_task.py`, `processing/*`, `parsers/*` (incl. `docx.py`, `xlsx.py`), `normalization/*`, `chunking/*` |
| 05 | `models/*.py`, `alembic/versions/*` |
| 06 | `auth/*`, `routes/organizations.py`, `services/membership.py`, tests `test_authorization.py`, `test_organizations.py`, `test_documents.py` |
| 07 | `services/retrieval.py`, `routes/chat.py` (`_build_retrieved_context`), tests `test_retrieval.py`, `bench_retrieval.py` |
| 08, 09 | `routes/chat.py`, `routes/conversations.py`, tests `test_chat.py` |
| 10 | `routes/evaluations.py`, `services/evaluation_runner.py`, `db/session.py`, `EvalDashboard.jsx`, tests `test_evaluations.py` |
| 11 | all routers, `api/dependencies.py`, `db/session.py`, `frontend/src/lib/api.js` |
| 13 | `services/llm.py`, `core/config.py`, tests `test_llm.py` |
| 14 | `tests/`, `bench_*.py`, `probe_retrieval.py`, `retrieval_cases*.json`, `apply_*.py`, `backend/bge_m3_*.py` |
