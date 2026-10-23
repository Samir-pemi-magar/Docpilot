"""Show which chunks DocPilot retrieves for a question, and whether the chunk holding the answer is among them.

Run from the project root, with the GPU hidden (same as the backend):
    CUDA_VISIBLE_DEVICES= uv run python probe_retrieval.py
Optional: pass your workspace id as the first argument.
"""
import asyncio
import sys
import uuid

sys.path.insert(0, "backend")

from app.db.session import AsyncSessionLocal  # noqa: E402
from app.embeddings.dependencies import get_default_embedding_provider  # noqa: E402
from app.services.retrieval import retrieve_hybrid_chunks  # noqa: E402
from app.api.routes.chat import _build_retrieved_context  # noqa: E402
from types import SimpleNamespace  # noqa: E402

ORG_ID = sys.argv[1] if len(sys.argv) > 1 else "d209210b-3c5c-4181-ba4f-f9cfe4ff0df3"
TOP_K = 8

# (question, [text that must reach the model for it to be able to answer])
CASES = [
    ("What does Comprehensive Plus give me that Comprehensive doesn't?", ["courtesy car for up to 14 days"]),
    ("I'm 23 and have Comprehensive motor insurance. What deductible do I pay on a claim?", ["additional deductible of $200"]),
    ("Can my 82-year-old father buy travel insurance?", ["age 80 at purchase"]),
    ("I missed my monthly payment due on 1 March 2027. When does my cover stop and can I get it back?", ["15 calendar days", "within 60 days"]),
    ("I paid $800 for my motor policy and cancelled after 146 days with no claims. What's my refund?", ["unused days and divided by 365"]),
    ("I sent all documents for my home claim on 6 December 2027. When must ESI decide?", ["15 Business Days", "2027-12-27"]),
    ("Who can approve a $30,000 claim, and who holds that role?", ["up to $50,000", "Michael Reyes"]),
    ("Can a Branch Manager approve a $1,500 goodwill payment?", ["up to $500", "up to $2,000"]),
    ("Since the Comprehensive deductible is $600, how much would I get on a $2,000 claim?", ["$500"]),
]


async def main() -> None:
    provider = get_default_embedding_provider()
    org = uuid.UUID(ORG_ID)
    async with AsyncSessionLocal() as db:
        for question, needles in CASES:
            emb = provider.embed_query(question)
            hits = await retrieve_hybrid_chunks(
                db, organization_id=org, query=question,
                query_vector=emb.vector, model=emb.model, top_k=TOP_K,
            )
            print("\n" + "=" * 100)
            print("Q:", question)
            srcs = [SimpleNamespace(text=h.chunk.text) for h in hits]
            ctx = {cap: _build_retrieved_context(srcs, max_chars=cap).lower() for cap in (12_000, 18_000)}
            total = sum(len(h.chunk.text) for h in hits)
            print(f"   retrieved text: {total:,} characters in {len(hits)} chunks")
            for needle in needles:
                rank = next((i for i, h in enumerate(hits, 1) if needle.lower() in h.chunk.text.lower()), None)
                found = f"FOUND at rank {rank}" if rank else f"MISSING from the top {TOP_K}"
                in12 = "yes" if needle.lower() in ctx[12_000] else "NO"
                in18 = "yes" if needle.lower() in ctx[18_000] else "NO"
                print(f"   needs {needle!r}: {found} | reaches the model at 12k cap: {in12} | at 18k cap: {in18}")
            for i, h in enumerate(hits, 1):
                et = getattr(h.chunk, "element_type", "")
                first = " ".join(h.chunk.text.split())[:80]
                print(f"   {i}. {h.document_name[:34]:34} [{et}] {len(h.chunk.text):5,} chars  {first[:60]}")


asyncio.run(main())
