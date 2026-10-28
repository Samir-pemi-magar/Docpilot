# Documentation audit: what was out of date

This file records every claim in the previous README, `ARCHITECTURE_NOTES.md` and diagrams that no longer matched the code, what is true now, and where it was verified. It is a one-time review aid; delete it once you have read it.

Method: static reading of the repository (no tests or services were run). Mermaid syntax of every `.mmd` file and of the README diagram was checked with the Mermaid parser.

## A. Claims that were wrong or missing

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

## B. Newly documented

- Diagram 13: LLM adaptive thinking decision flow.
- Diagram 14: tests, benchmarks and dev tooling (including the 60-case JSONL and 20-question chat set).
- Notes 3.1 items 11-14 (new findings, below).
- README: how to use the evaluation dashboard, opt-in test flags, benchmark commands.

## C. New findings recorded as known issues (not fixed; code was not changed)

1. **General-knowledge routing hijacks insurance questions.** Running `_is_general_knowledge_question` in isolation returned `True` for "Who is the Chief Claims Officer?", "Who is the Senior Adjuster?", "Who is Sandra Whitlow?", "Who is the Customer Relations Manager?" and "How does the grace period work?". Those skip retrieval. Evaluation runs bypass chat routing, so the dashboard cannot show it. Your 20 chat questions avoid this by wording (e.g. "Who can approve a $30,000 claim…").
2. **Thinking timeout cap.** `min(LLM_TIMEOUT_SECONDS, LLM_THINKING_TIMEOUT_SECONDS)` makes the effective thinking timeout 60 s, not 75 s.
3. **Alias/model mismatch.** Alias `docpilot-qwen3-4b` serves an 8B model.
4. **Hard-coded org id** in three scripts.
5. **Leftovers:** `apply_chat_fix.py`, `apply_config.py` (already applied), `EvalHistoryChart.jsx.bak`, `frontend/CLAUDE.md` and `AGENTS.md` (Figma Make boilerplate pointing at a non-existent `src/App.tsx`).

## D. Checked and unchanged

Historical findings from the earlier audit included a 13-table schema at Alembic head `c4f91a2d7e60`. That schema count and migration reference are stale: the October 2026 review reports current head `2c985d8c78fb`, and Gmail models have since been added. Re-verify the current schema and diagrams before relying on the earlier audit's claims. Other historical topics reviewed included authentication, role rules, multi-tenancy, ingestion, JSONL import, evaluation metrics, storage, streaming, CORS, OCR and ANN indexing.

## E. Not re-read line by line this pass

Carried forward from the previous notes after spot checks (route inventory, role checks, import limit, account-deletion 409, conversation ordering, model/migration alignment): `auth/routes.py`, `organizations.py`, `membership.py`, `conversations.py`, the import validation in `evaluations.py`, and `schemas/*`. If you changed behavior there recently, re-check diagrams 06, 09 and 11.
