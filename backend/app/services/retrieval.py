from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, literal_column, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import Chunk
from app.models.chunk_embedding import ChunkEmbedding
from app.models.document import Document
from app.models.document_version import DocumentVersion


@dataclass(frozen=True)
class RetrievedChunk:
    """A chunk returned by vector or keyword retrieval."""

    chunk: Chunk
    distance: float | None
    model: str | None
    document_id: uuid.UUID | None = None
    document_name: str = "Document"


def _validate_top_k(top_k: int) -> None:
    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    if top_k > 100:
        raise ValueError("top_k must not exceed 100.")


async def retrieve_chunks(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    query_vector: list[float],
    model: str,
    top_k: int = 5,
) -> list[RetrievedChunk]:
    """Retrieve the most similar chunks belonging to an organization."""

    if not query_vector:
        raise ValueError("Query vector must not be empty.")

    if len(query_vector) != 1024:
        raise ValueError("Query vector must contain exactly 1024 dimensions.")

    if not model.strip():
        raise ValueError("Embedding model must not be empty.")

    _validate_top_k(top_k)

    distance = ChunkEmbedding.embedding.cosine_distance(query_vector)

    statement = (
        select(
            Chunk,
            distance.label("distance"),
            ChunkEmbedding.model,
            Document.id,
            Document.name,
        )
        .join(
            ChunkEmbedding,
            ChunkEmbedding.chunk_id == Chunk.id,
        )
        .join(
            DocumentVersion,
            DocumentVersion.id == Chunk.document_version_id,
        )
        .join(
            Document,
            Document.id == DocumentVersion.document_id,
        )
        .where(
            Document.organization_id == organization_id,
            ChunkEmbedding.model == model,
        )
        .order_by(distance)
        .limit(top_k)
    )

    result = await db.execute(statement)

    return [
        RetrievedChunk(
            chunk=chunk,
            distance=float(distance_value),
            model=embedding_model,
            document_id=document_id,
            document_name=document_name,
        )
        for chunk, distance_value, embedding_model, document_id, document_name
        in result.all()
    ]


async def retrieve_keyword_chunks(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    query: str,
    top_k: int = 5,
) -> list[RetrievedChunk]:
    """Retrieve organization-scoped chunks using text and literal matching.

    Full-text search handles ordinary words and phrases. Literal substring
    matching supplements it for identifiers such as phone extensions and
    email addresses, which can be tokenized unexpectedly by full-text search.

    Keyword-only results have no embedding distance or model.
    """

    query = query.strip()
    if not query:
        raise ValueError("Query must not be empty.")

    _validate_top_k(top_k)

    # Treat user-provided %, _ and backslashes as literal characters.
    escaped_query = (
        query.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
    literal_match = Chunk.text.ilike(
        f"%{escaped_query}%",
        escape="\\",
    )

    document_vector = func.to_tsvector(literal_column("'simple'::regconfig"), Chunk.text)
    parsed_query = func.websearch_to_tsquery(literal_column("'simple'::regconfig"), query)
    text_rank = func.ts_rank_cd(document_vector, parsed_query)
    text_match = document_vector.op("@@")(parsed_query)

    statement = (
        select(
            Chunk,
            Document.id,
            Document.name,
            text_rank.label("text_rank"),
            literal_match.label("literal_match"),
        )
        .join(
            DocumentVersion,
            DocumentVersion.id == Chunk.document_version_id,
        )
        .join(
            Document,
            Document.id == DocumentVersion.document_id,
        )
        .where(
            Document.organization_id == organization_id,
            or_(text_match, literal_match),
        )
        .order_by(
            literal_match.desc(),
            text_rank.desc(),
            Chunk.id,
        )
        .limit(top_k)
    )

    result = await db.execute(statement)

    return [
        RetrievedChunk(
            chunk=chunk,
            distance=None,
            model=None,
            document_id=document_id,
            document_name=document_name,
        )
        for chunk, document_id, document_name, _rank, _literal
        in result.all()
    ]


async def retrieve_hybrid_chunks(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    query: str,
    query_vector: list[float],
    model: str,
    top_k: int = 5,
) -> list[RetrievedChunk]:
    """Combine vector and keyword rankings using reciprocal-rank fusion."""

    query = query.strip()
    if not query:
        raise ValueError("Query must not be empty.")

    _validate_top_k(top_k)

    # Retrieve a larger candidate pool before merging the rankings.
    candidate_k = min(max(top_k * 4, 20), 100)

    vector_results = await retrieve_chunks(
        db,
        organization_id=organization_id,
        query_vector=query_vector,
        model=model,
        top_k=candidate_k,
    )
    keyword_results = await retrieve_keyword_chunks(
        db,
        organization_id=organization_id,
        query=query,
        top_k=candidate_k,
    )

    # Reciprocal-rank fusion combines ranks, not incomparable raw scores.
    # Rank positions start at 1; 60 is a conventional smoothing constant.
    rrf_constant = 60
    fused_scores: dict[uuid.UUID, float] = {}
    candidates: dict[uuid.UUID, RetrievedChunk] = {}

    for results in (vector_results, keyword_results):
        for rank, item in enumerate(results, start=1):
            chunk_id = item.chunk.id
            fused_scores[chunk_id] = (
                fused_scores.get(chunk_id, 0.0)
                + 1.0 / (rrf_constant + rank)
            )

            existing = candidates.get(chunk_id)
            if existing is None:
                candidates[chunk_id] = item
            elif existing.distance is None and item.distance is not None:
                # Preserve the actual vector distance whenever available.
                candidates[chunk_id] = item

    ranked_ids = sorted(
        fused_scores,
        key=lambda chunk_id: (-fused_scores[chunk_id], chunk_id.hex),
    )

    return [candidates[chunk_id] for chunk_id in ranked_ids[:top_k]]
