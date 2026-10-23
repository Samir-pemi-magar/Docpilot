"""Retrieval benchmark for DocPilot: how often does the text that answers a question actually reach the model?

No LLM is involved, so it is fast and repeatable. For each question in retrieval_cases.json it retrieves chunks with the
app's real hybrid search, builds the prompt context exactly like the chat does, and checks whether each required piece of
source text is (a) among the retrieved chunks and (b) still present in the context sent to the model.

It compares keyword-search variants side by side:
  A_original  keyword search as it was before (every word of the question must match)
  B_or_all    match any content word (the patch from docpilot_fixes2_patch.zip)
  C_or_rare   match any content word, but ignore words that appear in many chunks (home, claim, days, ...)

Run from the project root with the GPU hidden:
    CUDA_VISIBLE_DEVICES= uv run python bench_retrieval.py
Options: --org <workspace id>  --top-k 8  --rare 0.15  --cases retrieval_cases.json  --verbose
"""
import argparse
import asyncio
import json
import re
import sys
import uuid
from types import SimpleNamespace

sys.path.insert(0, "backend")

TOKEN = re.compile(r"[^\W_]+")


def tokens(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


def build_document_frequency(texts: list[str]) -> tuple[dict[str, int], int]:
    df: dict[str, int] = {}
    for text in texts:
        for token in set(tokens(text)):
            df[token] = df.get(token, 0) + 1
    return df, len(texts)


def make_rare_filter(original, df: dict[str, int], n_chunks: int, max_fraction: float):
    """Wrap the app's OR-query builder so words found in more than max_fraction of all chunks are dropped."""

    def rare_only(query: str):
        built = original(query)
        if not built:
            return None
        kept = [t for t in built.split(" | ") if df.get(t, 0) / max(n_chunks, 1) <= max_fraction]
        return " | ".join(kept) if kept else None

    return rare_only


def contains(text: str, needle: str) -> bool:
    return needle.lower() in " ".join(text.split()).lower()


async def load_texts(db, org_id) -> list[str]:
    from sqlalchemy import text

    rows = await db.execute(
        text(
            "SELECT c.text FROM chunks c JOIN document_versions v ON v.id = c.document_version_id "
            "JOIN documents d ON d.id = v.document_id WHERE d.organization_id = :org"
        ),
        {"org": org_id},
    )
    return [r[0] for r in rows]


async def evaluate(db, org_id, provider, cases, *, top_k=8, rare=0.15, verbose=False):
    import app.services.retrieval as R
    from app.api.routes.chat import _build_retrieved_context

    original = R._keyword_or_query
    texts = await load_texts(db, org_id)
    df, n_chunks = build_document_frequency(texts)
    modes = {
        "A_original": lambda q: None,
        "B_or_all": original,
        "C_or_rare": make_rare_filter(original, df, n_chunks, rare),
    }
    results = {m: [] for m in modes}
    try:
        for case in cases:
            emb = provider.embed_query(case["question"])
            for mode, fn in modes.items():
                R._keyword_or_query = fn
                hits = await R.retrieve_hybrid_chunks(
                    db, organization_id=org_id, query=case["question"],
                    query_vector=emb.vector, model=emb.model, top_k=top_k,
                )
                joined = " ".join(h.chunk.text for h in hits)
                context = _build_retrieved_context([SimpleNamespace(text=h.chunk.text) for h in hits], max_chars=12_000)
                in_top = [contains(joined, n) for n in case["needles"]]
                in_ctx = [contains(context, n) for n in case["needles"]]
                results[mode].append((case["case_id"], case["question"], in_top, in_ctx))
    finally:
        R._keyword_or_query = original
    return results, n_chunks


def summarize(results) -> dict[str, dict[str, float]]:
    summary = {}
    for mode, rows in results.items():
        needles = sum(len(r[2]) for r in rows)
        summary[mode] = {
            "cases": len(rows),
            "needle_in_top_k": sum(sum(r[2]) for r in rows) / needles,
            "needle_in_prompt": sum(sum(r[3]) for r in rows) / needles,
            "cases_fully_in_prompt": sum(all(r[3]) for r in rows),
        }
    return summary


def print_report(results, n_chunks, verbose=False):
    summary = summarize(results)
    print(f"\n{n_chunks} chunks in the workspace\n")
    print(f"{'variant':<12} {'needles in top-k':>17} {'needles in prompt':>18} {'cases fully in prompt':>23}")
    for mode, s in summary.items():
        print(f"{mode:<12} {s['needle_in_top_k']*100:>16.1f}% {s['needle_in_prompt']*100:>17.1f}% {s['cases_fully_in_prompt']:>16} of {s['cases']}")
    base = {r[0]: all(r[3]) for r in results["A_original"]}
    for mode in ("B_or_all", "C_or_rare"):
        gained = [r for r in results[mode] if all(r[3]) and not base[r[0]]]
        lost = [r for r in results[mode] if not all(r[3]) and base[r[0]]]
        print(f"\n{mode} vs A_original:  gained {len(gained)} cases, lost {len(lost)} cases")
        for tag, group in (("  + gained", gained), ("  - lost  ", lost)):
            for r in group:
                print(f"{tag} {r[0]:<6} {r[1][:78]}")
    if verbose:
        print("\nCases still not fully in the prompt (variant C):")
        for r in results["C_or_rare"]:
            if not all(r[3]):
                print(f"  {r[0]:<6} {r[1][:78]}")


async def main() -> None:
    from app.db.session import AsyncSessionLocal
    from app.embeddings.dependencies import get_default_embedding_provider

    ap = argparse.ArgumentParser()
    ap.add_argument("--org", default="d209210b-3c5c-4181-ba4f-f9cfe4ff0df3")
    ap.add_argument("--cases", default="retrieval_cases.json")
    ap.add_argument("--top-k", type=int, default=8)
    ap.add_argument("--rare", type=float, default=0.15)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    cases = json.load(open(args.cases))
    provider = get_default_embedding_provider()
    async with AsyncSessionLocal() as db:
        results, n_chunks = await evaluate(db, uuid.UUID(args.org), provider, cases, top_k=args.top_k, rare=args.rare)
    print_report(results, n_chunks, verbose=args.verbose)


if __name__ == "__main__":
    asyncio.run(main())
