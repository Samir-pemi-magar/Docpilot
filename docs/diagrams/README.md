# DocPilot diagrams

All diagrams are [Mermaid](https://mermaid.js.org/) source files. GitHub renders `.mmd` files directly; locally you can paste them into the Mermaid Live Editor or use `mmdc` (Mermaid CLI). Each file starts with `%%` comments saying what it shows and what changed in the latest review.

| # | File | Shows |
|---|------|-------|
| 01 | [01-system-context.mmd](01-system-context.mmd) | Users, system boundary, external services |
| 02 | [02-high-level-architecture.mmd](02-high-level-architecture.mmd) | Logical layers inside the API process, background tasks, LLM client, Gmail, PDF export |
| 03 | [03-backend-components.mmd](03-backend-components.mmd) | Modules in `backend/app` and their real dependencies |
| 04 | [04-document-ingestion.mmd](04-document-ingestion.mmd) | Upload through parse, normalize, chunk, embed, persist |
| 05 | [05-database-erd.mmd](05-database-erd.mmd) | 17-table ER diagram (includes the Gmail tables) |
| 06 | [06-multitenancy-authorization.mmd](06-multitenancy-authorization.mmd) | Auth chain, roles, tenant scoping |
| 07 | [07-retrieval-architecture.mmd](07-retrieval-architecture.mmd) | Three-list hybrid retrieval, RRF, boosts, context building |
| 08 | [08-chat-rag-sequence.mmd](08-chat-rag-sequence.mmd) | End-to-end chat request sequence |
| 09 | [09-conversation-lifecycle.mmd](09-conversation-lifecycle.mmd) | Conversation creation, ownership, follow-ups |
| 10 | [10-evaluation-architecture.mmd](10-evaluation-architecture.mmd) | Datasets, background runs, metrics |
| 11 | [11-api-request-flow.mmd](11-api-request-flow.mmd) | Endpoint groups by access level, dependency chain |
| 12 | [12-deployment-infrastructure.mmd](12-deployment-infrastructure.mmd) | Compose services, host processes, configuration |
| 13 | [13-llm-answer-generation.mmd](13-llm-answer-generation.mmd) | Fast vs thinking mode and fallback (new) |
| 14 | [14-dev-quality-tooling.mmd](14-dev-quality-tooling.mmd) | Tests, benchmarks, probes, test corpus (new) |
| 15 | [15-gmail-oauth-connect.mmd](15-gmail-oauth-connect.mmd) | Gmail OAuth connect sequence (new) |
| 16 | [16-gmail-import-flow.mmd](16-gmail-import-flow.mmd) | Gmail message and attachment import (new) |

Source files behind each diagram are listed in [../../ARCHITECTURE_NOTES.md](../../ARCHITECTURE_NOTES.md#4-diagram-to-source-map).

Syntax check (optional): `npm i mermaid jsdom` and call `mermaid.parse()` on each file, or open them in the Live Editor.
