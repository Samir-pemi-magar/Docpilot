# DocPilot

**A self-hosted, multi-tenant document intelligence and retrieval-augmented generation (RAG) platform.**

Upload PDFs, Word, Excel, Markdown and text files into an organization, then ask questions in chat. DocPilot retrieves the most relevant passages, answers only from that evidence, cites its sources, and shows a step-by-step trace of how the answer was produced. Everything runs on your own hardware: no third-party AI APIs.

> **Status:** under development. It runs locally via Docker Compose and has not been deployed to a server or cloud.

---

## Features

- **Multi-tenant by design.** Every document, chunk, conversation and evaluation set belongs to an organization. Members have `owner`, `admin` or `member` roles, and every route is checked against the caller's membership.
- **Multi-format ingestion.** PDF (PyMuPDF), DOCX, XLSX, Markdown and TXT go through a parse, normalize, chunk and embed pipeline that runs in the background after upload.
- **Versioned documents.** Re-uploading creates a new version. Each version tracks its own ingestion status (`processing`, `failed`, and so on), and old versions can be downloaded.
- **Structure-aware chunking.** Prose is split by token budget with overlap (target 500, max 800, overlap 75). Tables and spreadsheet content use a separate structured chunker so rows are not cut mid-table.
- **Hybrid retrieval.** Dense vector search (BGE-M3, 1024 dimensions, pgvector cosine distance) and Postgres full-text search are fused with reciprocal-rank fusion. Table-title matches get a boost, and superseded or historical policy chunks are down-weighted unless the user asks about the past.
- **Grounded answers.** The LLM is told to treat retrieved text as untrusted data, not instructions, and to say so when the excerpts are insufficient. An evidence guard stops the system answering from nothing.
- **Explainable responses.** Each reply carries source citations and an agent trace (routing, retrieval, context preparation, evidence guard, LLM call).
- **Built-in evaluation.** Create datasets of question and expected-answer cases (bulk import supported), run them against the live pipeline, and inspect per-case results and score history in a dashboard.
- **Local inference.** Qwen3-1.7B runs in a `llama.cpp` server container behind an OpenAI-compatible API, so any OpenAI-compatible endpoint can be swapped in via config.

## Architecture

```mermaid
flowchart LR
    UI[React + Vite frontend] -->|/api proxy| API[FastAPI backend]
    API --> AUTH[JWT auth + org RBAC]
    API --> ING[Ingestion pipeline]
    ING --> PARSE[Parsers<br/>PDF / DOCX / XLSX / MD / TXT]
    PARSE --> NORM[Normalizers]
    NORM --> CHUNK[Chunkers<br/>prose + structured]
    CHUNK --> EMB[BGE-M3 embeddings]
    EMB --> PG[(PostgreSQL 17<br/>+ pgvector)]
    API --> RET[Hybrid retrieval<br/>vector + full-text + RRF]
    RET --> PG
    API --> LLM[llama.cpp server<br/>Qwen3-1.7B]
    API --> STORE[(File storage)]
```

**Chat request flow**

1. The question is routed: small talk, general-knowledge questions and follow-ups are handled differently from document questions.
2. Recent conversation history is added to the retrieval query when the question depends on it.
3. The query is embedded and hybrid retrieval returns the top chunks for that organization only.
4. A bounded context window is built from the chunks, and the evidence guard checks there is something to answer from.
5. The LLM answers from the excerpts. The response, sources and trace are saved to the conversation.

## Tech stack

| Layer | Technology |
|---|---|
| API | Python 3.12, FastAPI, Pydantic v2, Uvicorn |
| Data | PostgreSQL 17, pgvector, SQLAlchemy 2 (async), asyncpg, Alembic |
| Auth | JWT (PyJWT), Argon2 password hashing (pwdlib) |
| Embeddings | `BAAI/bge-m3` via FlagEmbedding (local, 1024-d) |
| LLM | Qwen3-1.7B (GGUF, Q4_K_M) on `llama.cpp` server, OpenAI-compatible |
| Parsing | PyMuPDF, python-docx, openpyxl |
| Frontend | React 19, Vite, Tailwind CSS 4, Recharts, react-markdown |
| Tooling | uv, pytest + pytest-asyncio, Docker Compose, Makefile |

## Getting started

### Prerequisites

- Docker with Compose. The default LLM container reserves an NVIDIA GPU, so you also need the NVIDIA Container Toolkit. With no GPU, point `LLM_BASE_URL` at any OpenAI-compatible server instead.
- [uv](https://docs.astral.sh/uv/) and Python 3.12
- Node.js and npm

### Setup

```bash
git clone https://github.com/Samir-pemi-magar/Docpilot.git
cd Docpilot

# Backend + frontend dependencies
make install

# Configuration
cp .env.example .env     # then edit the values below
```

Minimum `.env` (matches the Compose defaults):

```env
DATABASE_URL=postgresql+asyncpg://docpilot:docpilot_dev@127.0.0.1:5433/docpilot
JWT_SECRET_KEY=change-me-to-a-long-random-string

# Optional. Defaults shown.
LLM_BASE_URL=http://127.0.0.1:3000/v1
LLM_MODEL=docpilot-qwen3-1.7b
```

### Run

```bash
make migrate   # create the database schema (Postgres must be up: `make up`)
make dev       # starts Postgres, the LLM server, the API and the frontend
```

- Frontend: http://127.0.0.1:5173
- API: http://127.0.0.1:8000, with interactive docs at `/docs`

The first run downloads the Qwen GGUF model and, on first ingestion or query, the BGE-M3 embedding model. Expect a few GB and a slow first request.

Run `make help` to list all commands (`up`, `down`, `status`, `logs`, `migration MSG="..."`, `db-shell`, `llm-up`, `llm-down`, and more).

## API overview

All organization data lives under `/organizations/{organization_id}/...`.

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `DELETE /auth/me` |
| Organizations | create, list, get, update, delete; manage members and roles |
| Documents | upload, list, get, delete; add versions; download a version |
| Search | `POST /organizations/{id}/search` (hybrid retrieval, no LLM) |
| Chat | `POST /organizations/{id}/chat` (answer, sources, trace) |
| Conversations | list, get, delete |
| Evaluations | datasets, cases (incl. bulk import), runs, per-case results |
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
alembic/        Database migrations
frontend/       React + Vite app (chat, sources, trace, eval dashboard, files)
tests/          pytest suite with sample PDF/DOCX/XLSX/TXT fixtures
```

## Testing

```bash
make test       # full suite
make check      # syntax check + tests
```

The suite covers auth, organization authorization and database isolation, every parser, normalization, chunking, embeddings, ingestion, retrieval, search, chat, LLM client and evaluations. Some tests need the Postgres container running (`make up`).

## Design notes

- **RRF over score blending.** Cosine distance and full-text rank are not comparable numbers, so they are fused by rank position.
- **Storage is an interface.** Local disk is the only backend today, but `StorageService` makes S3-style backends a drop-in change.
- **Embeddings sit behind a provider interface.** BGE-M3 is the default, and tests use fakes so they do not need the model.
- **Retrieved text is data, not instructions.** The system prompt says so explicitly, which limits prompt injection through uploaded documents.

## Known limitations

- Single-node: ingestion runs as an in-process background task, files live on local disk, and embeddings are computed in the API process.
- Chat responses are returned whole rather than streamed.
- Answer quality is bounded by the small default model (1.7B parameters). Use a larger OpenAI-compatible model for better results.
- Some retrieval and chat heuristics (policy intents, historical-document handling) were tuned against a specific test corpus and may need generalizing for other domains.
- Not production-hardened: default dev credentials, no rate limiting, no deployment manifests.

## License

MIT. See [LICENSE.txt](LICENSE.txt).
