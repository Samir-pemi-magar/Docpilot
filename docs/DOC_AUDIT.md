# Documentation audit

Two review passes are recorded here. **Pass 2 (this revision)** is first; pass 1 is kept below for history. This is a one-time review aid; delete it once you have read it.

Method (both passes): static reading of the repository. No tests or services were run, and the Gmail integration was not exercised against Google. Mermaid syntax of every `.mmd` file and the README diagram was checked with the Mermaid parser.

---

## Pass 2: Gmail integration, PDF export, sessions

### A. In-repo documentation that no longer matched the code

Some documentation in the repository had been edited for an earlier, partial Gmail state. Those edits are superseded.

| # | Claim in the repo | Current reality | Evidence |
|---|---|---|---|
| 1 | Alembic head is `2c985d8c78fb` (DOC_AUDIT, diagram 05); earlier docs said `c4f91a2d7e60` | Head is **`a7c19d4e2b61`** (four Gmail migrations on top of `c4f91a2d7e60`) | `alembic/versions/*` |
| 2 | Two Gmail tables (diagram 05); "15 model files; verify" (diagram 03); 13 tables (older docs) | **17 tables**: also `gmail_imports` and `gmail_import_attachments`; models and migrations agree | `models/gmail_*.py`, `a7c19d4e2b61`, `13e2a56a8a32` |
| 3 | Gmail "exposes message metadata and snippets; does not provide full message bodies and attachments" (README) | Full import exists: email text becomes a document, and supported attachments become documents (10 per email, 10 MiB each, 25 MiB total) | `routes/gmail.py` `import_gmail_message`, `_import_gmail_attachments` |
| 4 | README endpoint list omitted the import endpoint | `POST /organizations/{id}/gmail/messages/{message_id}/import` (owner or admin) | `routes/gmail.py` |
| 5 | Diagram 01 said "Gmail OAuth is implemented for read-only access" with no Google node | Google (OAuth + Gmail API) added as an optional external system | diagram 01 |
| 6 | "Single access token, no refresh" (notes 3.4) | `POST /auth/refresh`; login returns an access and a refresh token; SPA refreshes silently | `auth/routes.py`, `auth/security.py`, `lib/api.js` |
| 7 | Evaluation runs "started" with no concurrency rule (diagram 10, README) | Global advisory lock + 409 if any run is pending/running in any organization | `routes/evaluations.py` |
| 8 | Conversation and evaluation endpoints without export | PDF downloads for a chat answer and for an evaluation run (ReportLab) | `routes/conversations.py`, `routes/evaluations.py`, `services/*_pdf_export.py` |
| 9 | SPA had three pages | Four pages (Gmail added); Download PDF buttons; OAuth return handled in `App.jsx` | `App.jsx`, `Sidebar.jsx`, `GmailPage.jsx` |
| 10 | "about 290 test functions" / 288 (README, notes) | 372 test functions | `tests/` |
| 11 | `main.py` "includes 9 routers" | 11 router instances (gmail registers two) | `main.py` |
| 12 | `.env.example` "only lists app name ... database URL" | Now also lists the Gmail variables, but still no `JWT_SECRET_KEY` or `FRONTEND_URL` | `.env.example` |

### B. New or changed documentation

- Diagrams **15** (Gmail OAuth connect sequence) and **16** (Gmail message and attachment import) are new.
- Updated: 01, 02, 03, 04, 05, 06, 09, 10, 11, 12, 14. Unchanged: 07, 08, 13.
- README: Gmail section rewritten (what it does, what to know, setup), sessions, PDF export, one-active-evaluation rule, new environment variables, known limitations.
- ARCHITECTURE_NOTES: sections 1.1 to 1.8, 2, 3 and 4 updated; new inconsistencies 15 to 22.

### C. New findings (recorded as known issues; no code was changed)

1. **`reportlab` is declared only as a dev dependency**, but production modules import it when the API starts. Fine for `make install`; likely to break an install without dev dependencies.
2. **`FRONTEND_URL` defaults to port 8443** while `make dev` uses 5173, so the post-OAuth redirect lands on the wrong port unless the variable is set. It is missing from `.env.example`.
3. **One active evaluation across all organizations**; a crash-stuck run would likely block everyone.
4. **Refresh tokens are stateless and non-revocable**; both tokens are in `localStorage`.
5. **Imported Gmail content is visible to the whole organization.**
6. **Gmail lifecycle gaps:** no disconnect, no cleanup of OAuth state rows, no CHECK constraints on status columns, failed imports not retryable.
7. **Gmail page does not gate by role**, so plain members see a 403 per import.

### D. Checked and unchanged since pass 1

Chat routing and the general-knowledge issue (pass-1 finding 11 still applies), retrieval (three lists), LLM client, ingestion pipeline and parsers, evaluation metrics and import, storage layout, Docker Compose, Makefile. `chat.py`, `retrieval.py`, `llm.py` and all parsers are byte-identical to the pass-1 snapshot.

### E. Not read line by line this pass

`gmail_google_client.py` (623 lines) was skimmed for endpoints, limits, timeouts and returned fields rather than read in full. The two PDF export modules were checked for imports, entry points and headers, not for layout. `GmailPage.jsx` was checked for API calls, props and role handling, not for UI details.

---

## Pass 1 (kept for history)

The claims below were corrected in the first review; they are listed so you can see how the docs drifted from the original version.

### Pass 1, A. Claims that were wrong or missing

| # | Previous claim (where) | Current reality | Evidence |
|---|---|---|---|
| 1 | LLM is Qwen3-1.7B, downloaded via `-hf`, ctx 4096, alias `docpilot-qwen3-1.7b` (README, notes 1.7, diagrams 01/02/12) | Qwen3-**8B** Q4_K_M loaded from a **local file** `./data/local_models/Qwen3-8B-Q4_K_M.gguf`, ctx 8192, `--parallel 1`, alias `docpilot-qwen3-4b`. Not auto-downloaded | `compose.yaml` |
| 2 | README `LLM_MODEL` default `docpilot-qwen3-1.7b` | Default is `docpilot-qwen3-4b` | `core/config.py` |
| 3 | LLM temperature 0.2, `enable_thinking: false` always (notes 1.6) | Fast mode: temp 0.0, 700 tokens. Thinking mode (temp 0.6, top-p 0.95, top-k 20, 3000 tokens) for numeric/date/eligibility questions in `auto` mode, with fast-mode fallback; five new settings | `services/llm.py`, `core/config.py`, `tests/test_llm.py` |
| 4 | Retrieval has two branches (vector + keyword) (README, notes 1.4, diagrams 07/08) | Three lists: vector 1.0, strict keyword 1.0, **OR-keyword 0.10** (10 candidates) | `services/retrieval.py`, `bench_retrieval.py` |
| 5 | DOCX: paragraphs only, tables counted but not extracted (notes 1.4, diagram 04) | DOCX tables **are extracted** (cells joined with a pipe character, title from `Table N` or last heading) | `parsers/docx.py`, `normalization/docx.py` |
| 6 | XLSX: "openpyxl worksheets" (diagram 04) | Reads formulas **and** saved results; saved value is indexed; empty formula results skipped | `parsers/xlsx.py` |
| 7 | Evaluation runs execute synchronously inside the request (notes 1.2/3.4, diagram 10) | Run is created `pending`, returned with 201, executed by `run_evaluation_background` in a `BackgroundTasks` job; SPA polls every 800 ms | `routes/evaluations.py`, `services/evaluation_runner.py`, `db/session.py`, `EvalDashboard.jsx` |
| 8 | Context builder treats any chunk with 2+ pipe-containing lines as a table (diagram 07) | Requires pipe lines to be at least half of non-empty lines | `routes/chat.py` (`_build_retrieved_context`) |
| 9 | "The first run downloads the Qwen GGUF model" (README) | Only BGE-M3 is downloaded; the GGUF must be placed manually or the LLM container cannot start | `compose.yaml` |
| 10 | Backend start-up not described as CPU-only for embeddings | `make dev` launches uvicorn with `CUDA_VISIBLE_DEVICES=`, so BGE-M3 runs on CPU | `Makefile` |
| 11 | "An evidence guard stops the system answering from nothing" and trace includes "evidence guard" (README) | Two distinct things: a fixed no-results fallback (no LLM call) and an `evidence_guard` trace step that fires only for the admissions-deadline guard | `routes/chat.py` |
| 12 | README chat flow: "Recent history is added to the retrieval query" | History is used only in an LLM rewrite of follow-ups matching a regex; the rewritten question replaces the query | `routes/chat.py` |
| 13 | SPA pages: Chat, Files, Eval (diagram 02) | Also a conversation sidebar (list/open/new/delete) and a label→document mapping UI for eval import | `App.jsx`, `Sidebar.jsx`, `EvalDashboard.jsx` |
| 14 | "Answer quality is bounded by the small default model (1.7B)" | Default is now 8B (4-bit) | `compose.yaml` |
| 15 | README project layout omitted root scripts, `docs/`, `data/` | Added `bench_*.py`, `probe_retrieval.py`, `retrieval_cases*.json`, `apply_*.py`, `backend/bge_m3_*.py` | repo root |
| 16 | Notes said "see the table in README.md" for diagrams | README had no such table. Added `docs/diagrams/README.md` index and a README link | n/a |
| 17 | Notes `.env.example` item mentioned only the missing key and password | Still true; README now tells readers what to add | `.env.example` |
| 18 | Notes said "chat.py (963 lines)" | 967 lines | `wc -l` |

### Pass 1, B. Newly documented

- Diagram 13: LLM adaptive thinking decision flow.
- Diagram 14: tests, benchmarks and dev tooling (including the 60-case JSONL and 20-question chat set).
- Notes 3.1 items 11-14 (new findings, below).
- README: how to use the evaluation dashboard, opt-in test flags, benchmark commands.
