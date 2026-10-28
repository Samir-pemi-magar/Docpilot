# DocPilot

**A self-hosted, multi-tenant document intelligence and retrieval-augmented generation (RAG) platform.**

Upload PDFs, Word, Excel, Markdown and text files into an organization, then ask questions in chat. DocPilot retrieves the most relevant passages, answers only from that evidence, cites its sources, and shows a step-by-step trace of how the answer was produced. Everything runs on your own hardware: no third-party AI APIs.

> **Status:** under development. It runs locally via Docker Compose and has not been deployed to a server or cloud.

---

## Features

- **Multi-tenant by design.** Every document, chunk, conversation and evaluation set belongs to an organization. Members have `owner`, `admin` or `member` roles, and every route is checked against the caller's membership. Conversations are private to the member who started them.
- **Multi-format ingestion.** PDF (PyMuPDF), DOCX, XLSX, Markdown and TXT go through a parse, normalize, chunk and embed pipeline that runs in the background after upload. Tables are extracted from PDF **and** DOCX files; spreadsheets are read as their saved (calculated) values, with dense cell regions detected as tables or key-value blocks.
- **Versioned documents.** Re-uploading creates a new version. Each version tracks its own ingestion status (`pending`, `processing`, `completed`, `failed`), and old versions can be downloaded.
- **Structure-aware chunking.** Prose is split by token budget with overlap (target 500, max 800, overlap 75). Tables and spreadsheet content use a separate structured chunker: rows are never cut, the header row is repeated in every chunk, and a worksheet / table / page prefix is added so each chunk is self-describing.
- **Hybrid retrieval.** Three candidate lists are fused with reciprocal-rank fusion: dense vector search (BGE-M3, 1024 dimensions, pgvector cosine distance), strict Postgres full-text search, and a deliberately low-weight "any content word" full-text list that adds recall for natural-language questions. Table-title matches get a boost, and superseded or historical policy chunks are down-weighted unless the user asks about the past.
- **Grounded answers.** The LLM is told to treat retrieved text as untrusted data, not instructions, and to say so when the excerpts are insufficient. When nothing is retrieved, a fixed fallback is returned and the model is not called.
- **Adaptive reasoning.** For questions that involve numbers, dates, amounts or eligibility wording, the LLM client switches the model into its thinking mode (bounded by tokens and time) and falls back to a fast answer if thinking fails or runs out. Plain look-ups stay fast.
- **Explainable responses.** Each reply carries source citations and an agent trace with measured step timings (routing, retrieval, context preparation, LLM call, persistence).
- **Conversation history.** The sidebar lists, reopens and deletes past conversations. Follow-up questions such as "And for health insurance?" are rewritten into standalone questions before retrieval.
- **Built-in evaluation.** Create datasets of question and expected-answer cases (JSONL bulk import with label-to-document mapping), run them against the live retrieval pipeline in the background, and inspect per-case results and score history in a dashboard.
- **Local inference.** Qwen3-8B (Q4_K_M) runs in a `llama.cpp` server container behind an OpenAI-compatible API, so any OpenAI-compatible endpoint can be swapped in via config.

## Architecture

```mermaid
flowchart LR
    UI[React + Vite frontend] -->|/api proxy| API[FastAPI backend]
    API --> AUTH[JWT auth + org RBAC]
    API -->|upload: BackgroundTasks| ING[Ingestion pipeline]
    ING --> PARSE[Parsers<br/>PDF / DOCX / XLSX / MD / TXT]
    PARSE --> NORM[Normalizers]
    NORM --> CHUNK[Chunkers<br/>prose + structured]
    CHUNK --> EMB[BGE-M3 embeddings]
    EMB --> PG[(PostgreSQL 17<br/>+ pgvector)]
    API --> RET[Hybrid retrieval<br/>vector + keyword + OR-keyword + RRF]
    RET --> PG
    API -->|eval run: BackgroundTasks| EVAL[Evaluation runner]
    EVAL --> RET
    API --> LLM[llama.cpp server<br/>Qwen3-8B<br/>fast + thinking modes]
    EVAL --> LLM
    API --> STORE[(File storage)]
```

More diagrams (ER diagram, retrieval, chat sequence, evaluation, deployment, and others) are indexed in [docs/diagrams/](docs/diagrams/README.md). Findings, decisions and open issues are in [ARCHITECTURE_NOTES.md](ARCHITECTURE_NOTES.md).

**Chat request flow**

1. The question is routed by rule-based checks: name introductions, small talk, general-knowledge questions and "which document said that?" follow-ups are handled without document retrieval; everything else is a document question.
2. If a document question looks like a follow-up ("and …", "what about …"), the model rewrites it into one standalone question using recent history. History is used for this rewrite only.
3. The query is embedded and hybrid retrieval returns the top chunks (default 5) for that organization only. If nothing is found, a fixed "couldn't find relevant information" answer is returned.
4. A bounded context (12,000 characters, whole chunks, complete table rows) is built from the chunks.
5. The LLM answers from the excerpts, using fast or thinking mode depending on the question. The answer, sources and trace are saved to the conversation in one commit; if the LLM fails, nothing is saved and the API returns 503.

## Tech stack

| Layer | Technology |
|---|---|
| API | Python 3.12, FastAPI, Pydantic v2, Uvicorn |
| Data | PostgreSQL 17, pgvector, SQLAlchemy 2 (async), asyncpg, Alembic |
| Auth | JWT (PyJWT), Argon2 password hashing (pwdlib) |
| Embeddings | `BAAI/bge-m3` via FlagEmbedding (local, 1024-d, dense only) |
| LLM | Qwen3-8B (GGUF, Q4_K_M) on `llama.cpp` server (CUDA image), OpenAI-compatible |
| Parsing | PyMuPDF, python-docx, openpyxl |
| Frontend | React 19, Vite, Tailwind CSS 4, Recharts, react-markdown |
| Tooling | uv, pytest + pytest-asyncio, Docker Compose, Makefile |

## Getting started

### Prerequisites

- Docker with Compose. The default LLM container reserves an NVIDIA GPU, so you also need the NVIDIA Container Toolkit. With no GPU, point `LLM_BASE_URL` at any OpenAI-compatible server instead.
- [uv](https://docs.astral.sh/uv/) and Python 3.12
- Node.js and npm
- **The LLM model file.** Compose does not download it. Put `Qwen3-8B-Q4_K_M.gguf` in `data/local_models/` (the folder is git-ignored), for example:

  ```bash
  mkdir -p data/local_models
  huggingface-cli download Qwen/Qwen3-8B-GGUF Qwen3-8B-Q4_K_M.gguf --local-dir data/local_models
  ```

  Without this file the `llama-server` container cannot start.

### Setup

```bash
git clone https://github.com/Samir-pemi-magar/Docpilot.git
cd Docpilot

# Backend + frontend dependencies
make install

# Configuration
cp .env.example .env     # then edit it: see below
```

`.env.example` includes application, database, and optional Gmail OAuth settings. Add the required JWT secret and ensure the database URL matches your Compose configuration. Configure Gmail OAuth only if you intend to use that integration. Minimum `.env`:

```env
DATABASE_URL=postgresql+asyncpg://docpilot:docpilot_dev@127.0.0.1:5433/docpilot
JWT_SECRET_KEY=change-me-to-a-long-random-string

# Optional. Defaults shown.
LLM_BASE_URL=http://127.0.0.1:3000/v1
LLM_MODEL=docpilot-qwen3-4b        # must match --alias in compose.yaml (the served model is Qwen3-8B)
LLM_TIMEOUT_SECONDS=60
LLM_MAX_TOKENS=700

# Thinking mode (see "Adaptive reasoning")
LLM_THINKING_MODE=auto             # auto | always | never
LLM_THINKING_TIMEOUT_SECONDS=75    # effectively capped by LLM_TIMEOUT_SECONDS
LLM_THINKING_MAX_TOKENS=3000
LLM_THINKING_TEMPERATURE=0.6

# Optional: Gmail read-only integration
GMAIL_TOKEN_ENCRYPTION_KEY=
GMAIL_CLIENT_ID=
GMAIL_CLIENT_SECRET=
GMAIL_REDIRECT_URI=http://127.0.0.1:8000/gmail/oauth/callback
```

### Run

```bash
make up        # start Postgres (and the LLM container)
make migrate   # create the database schema (Postgres must be up)
make dev       # starts Postgres, the LLM server, the API and the frontend
```

- Frontend: http://127.0.0.1:5173
- API: http://127.0.0.1:8000, with interactive docs at `/docs`

`make dev` starts the API with `CUDA_VISIBLE_DEVICES` empty on purpose: the GPU is left to the LLM container, so **BGE-M3 embeddings run on the CPU**. The BGE-M3 model is downloaded on first ingestion or query, so expect a slow first request. Ingestion and evaluation runs execute inside the API process.

Run `make help` to list all commands (`up`, `down`, `status`, `logs`, `api-logs`, `frontend-logs`, `migration MSG="..."`, `db-shell`, `llm-up`, `llm-down`, and more).

## Using the evaluation dashboard

1. Upload your documents in **File Manager**.
2. In **Eval**, create a dataset and import a `.jsonl` file (one case per line, max 2,000). Each line needs `question`, plus optionally `reference_answer` (or `expected_answer`), `relevant_document_ids` and metadata such as `essential_facts` and `answerable`.
3. If `relevant_document_ids` holds labels such as `DOC-01` rather than UUIDs, the dashboard asks you to map each label to an uploaded document.
4. Start a run. It is queued, executed in the background (the page polls until it finishes), and each case's retrieved sources, answer and metrics are stored.

Metrics: `hit_rate_at_k`, `recall_at_k` and `reciprocal_rank` (document level, need `relevant_document_ids`); `essential_fact_coverage` and `answerability_compliance` (lexical, need `essential_facts` / `answerable`). Evaluation runs retrieval plus a simplified answer prompt; it does not go through chat routing.

## Gmail integration (optional)

DocPilot can connect a user's Gmail account to an organization through Google OAuth. The integration requests the `gmail.readonly` scope and exposes message metadata and snippets; it does not send email or provide full message bodies and attachments through the documented integration.

### Google OAuth setup

1. In Google Cloud Console, configure the OAuth consent screen and create an OAuth client ID for a web application.
2. Register this authorized redirect URI on the OAuth client:

   `http://127.0.0.1:8000/gmail/oauth/callback`

3. Set the following variables in your local `.env`:

   - `GMAIL_CLIENT_ID`: Google OAuth client ID.
   - `GMAIL_CLIENT_SECRET`: Google OAuth client secret.
   - `GMAIL_REDIRECT_URI`: must match the registered redirect URI.
   - `GMAIL_TOKEN_ENCRYPTION_KEY`: Fernet key used to encrypt stored refresh tokens.

   Generate a Fernet key with:

   ```bash
   uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

4. Restart the API after configuring the values. Keep `.env` and the encryption key private. Back up the key securely; losing it may make stored encrypted tokens unreadable.
5. Start OAuth for the intended organization and authenticated user, complete Google's consent flow, then check the connection and retrieve message metadata.

The organization-scoped endpoints are:

- `POST /organizations/{organization_id}/gmail/oauth/start` — begin OAuth.
- `GET /organizations/{organization_id}/gmail/status` — inspect connection status.
- `GET /organizations/{organization_id}/gmail/messages` — retrieve message metadata and snippets.
- `GET /gmail/oauth/callback` — handle Google's OAuth redirect.

The callback URI must exactly match `GMAIL_REDIRECT_URI` and the URI registered in Google Cloud Console.

Gmail access is optional. The application also supports ordinary application authentication; Gmail OAuth is not general-purpose SSO.

## API overview

All organization data lives under `/organizations/{organization_id}/...`.

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `DELETE /auth/me` |
| Organizations | create, list, get, update, delete; manage members and roles |
| Documents | upload, list, get, delete; add versions; download a version |
| Search | `POST /organizations/{id}/search` (hybrid retrieval, no LLM) |
| Chat | `POST /organizations/{id}/chat` (answer, sources, trace) |
| Conversations | list, get, delete; export an answer as PDF |
| Evaluations | datasets, cases (incl. bulk import), runs (`POST` returns `pending`; poll the run), per-case results; export a run report as PDF |
| Gmail | OAuth connection, connection status, and read-only message metadata/snippets |
| Ops | `GET /health`, `GET /version` |

## Project layout

```
backend/app/
  api/          FastAPI routers and dependencies
  auth/         JWT, password hashing, org-role authorization
  parsers/      Format-specific parsers (pdf, docx, xlsx, markdown, txt)
  normalization/  Cleans parsed content into a common model
  chunking/     Prose, structured (table) and hybrid chunkers
  embeddings/   Provider interface + local BGE-M3 implementation
  processing/   Parse -> normalize -> chunk pipeline
  services/     Ingestion, retrieval, LLM client, evaluation runner
  models/       SQLAlchemy models
  storage/      Storage interface + local filesystem backend
backend/bge_m3_*.py   Embedding smoke / similarity scripts
alembic/        Database migrations
frontend/       React + Vite app (chat, conversation sidebar, trace, sources, eval dashboard, files)
tests/          pytest suite with sample PDF/DOCX/XLSX/TXT fixtures
docs/diagrams/  Mermaid diagrams (see docs/diagrams/README.md)
ARCHITECTURE_NOTES.md   Verified findings, decisions, known issues
bench_retrieval.py, bench_answers.py, probe_retrieval.py, retrieval_cases*.json
                Retrieval / answer benchmarks and probes (see Testing)
compose.yaml    Postgres + llama.cpp server
data/           Git-ignored: uploaded files, model files (data/local_models)
```

## Testing

```bash
make test       # full suite
make check      # syntax check + tests
make test-fast  # chat tests only
```

The suite (about 290 test functions) covers auth, organization authorization and database isolation, every parser, normalization, chunking, embeddings, ingestion, retrieval, search, chat, the LLM client (including thinking-mode fallback) and evaluations. Tests that touch the database need the Compose Postgres running (`make up`) and use a separate `docpilot_test` database on `localhost:5433`.

Tests that load real models are skipped unless you opt in: `RUN_REAL_BGE_TEST=1`, `RUN_REAL_RAG_CHAT=1`, `RUN_REAL_UPLOAD_RAG=1`, `RUN_REAL_WORKER_TEST=1`.

**Benchmarks and probes** (run from the project root against a populated workspace; pass your own workspace id, because the scripts default to an id from the author's database):

```bash
CUDA_VISIBLE_DEVICES= uv run python probe_retrieval.py <ORG_ID>              # is the answer chunk retrieved?
CUDA_VISIBLE_DEVICES= uv run python bench_retrieval.py --org <ORG_ID> --verbose   # no LLM; tunes keyword weight
CUDA_VISIBLE_DEVICES= uv run python bench_answers.py --org <ORG_ID> --variant A --app  # through the app's LLM client
```

`apply_chat_fix.py` and `apply_config.py` are one-off patch scripts that have already been applied.

## Design notes

- **RRF over score blending.** Cosine distance and full-text rank are not comparable numbers, so they are fused by rank position. The loosest keyword list is given a weight of 0.10 so it adds recall without outvoting the vector and strict keyword lists.
- **Storage is an interface.** Local disk is the only backend today, but `StorageService` makes S3-style backends a drop-in change.
- **Embeddings sit behind a provider interface.** BGE-M3 is the default, and tests use fakes so they do not need the model.
- **Retrieved text is data, not instructions.** The system prompt says so explicitly, which limits prompt injection through uploaded documents.
- **Thinking is a budgeted tool, not a default.** It is used only where questions look numeric or eligibility-related, and every failure path ends in a normal fast answer.
- **Same job model for ingestion and evaluation.** Both return immediately with a `pending` record and finish in a background task with their own database session.

## Known limitations

- Single-node: ingestion and evaluation runs execute as in-process background tasks (no queue, no retries, no recovery after a crash), files live on local disk, and embeddings are computed in the API process (on CPU under `make dev`).
- Chat responses are returned whole rather than streamed. A thinking-mode answer can take up to about a minute, and in the worst case two (thinking attempt, then fast retry).
- Answer quality is bounded by the local model (8B parameters at 4-bit). Use a larger OpenAI-compatible model for better results.
- **Chat routing was tuned on a school-admissions corpus.** Its general-knowledge detector treats many `Who is …?` and `How does … work?` questions as general knowledge unless they contain school-related words, so on other corpora such questions (for example "Who is the Chief Claims Officer?") may be answered without searching your documents. Evaluation runs do not use chat routing and will not show this.
- Other retrieval and chat heuristics (a "refund" intent boost, historical-document handling, the year-specific admissions-deadline guard) were also tuned against specific test corpora and may need generalizing for other domains.
- OCR is not implemented, so scanned PDFs yield no text. The token counter is whitespace-based, and the vector search is an exact scan (no ANN index).
- Older document versions remain searchable alongside the newest version.
- The UI does not show ingestion status, so a failed ingestion is not visible there.
- Not production-hardened: default dev credentials, no rate limiting, no CORS/TLS, no deployment manifests, no CI.

## License

MIT. See [LICENSE.txt](LICENSE.txt).
