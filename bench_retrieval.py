"""Retrieval benchmark for DocPilot: how often does the text that answers a question actually reach the model?

No LLM is involved, so it is fast and repeatable. For each question it retrieves chunks with the app's real hybrid search,
builds the prompt context exactly like the chat does, and checks that each required piece of source text is (a) in the
retrieved chunks and (b) still in the context sent to the model.

It compares settings of the extra "any content word" keyword list (see backend/app/services/retrieval.py):
  A_original  list switched off (the code before the keyword patch)
  B_equal     list as strong as the vector list (1.0) and long (32)   <- what the first keyword patch effectively did
  D_w50       weight 0.5, 10 candidates
  E_w25       weight 0.25, 10 candidates
  F_w10       weight 0.10, 10 candidates

Run from the project root with the GPU hidden:
    CUDA_VISIBLE_DEVICES= uv run python bench_retrieval.py --cases retrieval_cases.json retrieval_cases_chat.json --verbose
"""
import argparse
import asyncio
import json
import sys
import uuid
from types import SimpleNamespace

sys.path.insert(0, "backend")

MODES = {  # name: (KEYWORD_OR_WEIGHT, KEYWORD_OR_CANDIDATES)
    "A_original": (0.0, 10),
    "B_equal": (1.0, 32),
    "D_w50": (0.5, 10),
    "E_w25": (0.25, 10),
    "F_w10": (0.10, 10),
}


def contains(text: str, needle: str) -> bool:
    return needle.lower() in " ".join(text.split()).lower()


async def count_chunks(db, org_id) -> int:
    from sqlalchemy import text

    rows = await db.execute(
        text(
            "SELECT count(*) FROM chunks c JOIN document_versions v ON v.id = c.document_version_id "
            "JOIN documents d ON d.id = v.document_id WHERE d.organization_id = :org"
        ),
        {"org": org_id},
    )
    return rows.scalar_one()


async def evaluate(db, org_id, provider, cases, *, top_k=8):
    import app.services.retrieval as R
    from app.api.routes.chat import _build_retrieved_context

    saved = (R.KEYWORD_OR_WEIGHT, R.KEYWORD_OR_CANDIDATES)
    results = {m: [] for m in MODES}
    try:
        for case in cases:
            emb = provider.embed_query(case["question"])
            for mode, (weight, candidates) in MODES.items():
                R.KEYWORD_OR_WEIGHT, R.KEYWORD_OR_CANDIDATES = weight, candidates
                hits = await R.retrieve_hybrid_chunks(
                    db, organization_id=org_id, query=case["question"],
                    query_vector=emb.vector, model=emb.model, top_k=top_k,
                )
                joined = " ".join(h.chunk.text for h in hits)
                context = _build_retrieved_context([SimpleNamespace(text=h.chunk.text) for h in hits], max_chars=12_000)
                results[mode].append((
                    case["case_id"], case["question"],
                    [contains(joined, n) for n in case["needles"]],
                    [contains(context, n) for n in case["needles"]],
                ))
    finally:
        R.KEYWORD_OR_WEIGHT, R.KEYWORD_OR_CANDIDATES = saved
    return results, await count_chunks(db, org_id)


def summarize(results):
    out = {}
    for mode, rows in results.items():
        needles = sum(len(r[2]) for r in rows)
        out[mode] = {
            "cases": len(rows),
            "needle_in_top_k": sum(sum(r[2]) for r in rows) / needles,
            "needle_in_prompt": sum(sum(r[3]) for r in rows) / needles,
            "cases_fully_in_prompt": sum(all(r[3]) for r in rows),
        }
    return out


def print_report(results, n_chunks, verbose=False):
    summary = summarize(results)
    print(f"\n{n_chunks} chunks in the workspace\n")
    print(f"{'variant':<12} {'needles in top-k':>17} {'needles in prompt':>18} {'cases fully in prompt':>23}")
    for mode, s in summary.items():
        print(f"{mode:<12} {s['needle_in_top_k']*100:>16.1f}% {s['needle_in_prompt']*100:>17.1f}% {s['cases_fully_in_prompt']:>16} of {s['cases']}")
    base = {r[0]: all(r[3]) for r in results["A_original"]}
    for mode in list(MODES)[1:]:
        gained = [r for r in results[mode] if all(r[3]) and not base[r[0]]]
        lost = [r for r in results[mode] if not all(r[3]) and base[r[0]]]
        print(f"\n{mode} vs A_original: gained {len(gained)}, lost {len(lost)}  (net {len(gained) - len(lost):+d})")
        for tag, group in (("  + gained", gained), ("  - lost  ", lost)):
            for r in group:
                print(f"{tag} {r[0]:<6} {r[1][:76]}")
    if verbose:
        best = max(summary, key=lambda m: (summary[m]["cases_fully_in_prompt"], summary[m]["needle_in_prompt"]))
        print(f"\nBest variant by cases fully in the prompt: {best}. Cases it still misses:")
        for r in results[best]:
            if not all(r[3]):
                print(f"  {r[0]:<6} {r[1][:76]}")


async def main() -> None:
    from app.db.session import AsyncSessionLocal
    from app.embeddings.dependencies import get_default_embedding_provider

    ap = argparse.ArgumentParser()
    ap.add_argument("--org", default="d209210b-3c5c-4181-ba4f-f9cfe4ff0df3")
    ap.add_argument("--cases", nargs="+", default=["retrieval_cases.json", "retrieval_cases_chat.json"])
    ap.add_argument("--top-k", type=int, default=8)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    cases, seen = [], set()
    for path in args.cases:
        for case in json.load(open(path)):
            if case["case_id"] not in seen:
                seen.add(case["case_id"])
                cases.append(case)
    provider = get_default_embedding_provider()
    async with AsyncSessionLocal() as db:
        results, n_chunks = await evaluate(db, uuid.UUID(args.org), provider, cases, top_k=args.top_k)
    print_report(results, n_chunks, verbose=args.verbose)


if __name__ == "__main__":
    asyncio.run(main())
