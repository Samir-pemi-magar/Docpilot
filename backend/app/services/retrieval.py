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


def _requests_historical_policy(query: str) -> bool:
    """Return whether the query explicitly asks about past policy information."""
    normalized = query.casefold()

    historical_phrases = (
        "historical",
        "history of",
        "previous policy",
        "previous version",
        "prior policy",
        "prior version",
        "old policy",
        "old version",
        "superseded",
        "earlier version",
        "what was",
        "used to be",
        "previously",
        "formerly",
        "last year's",
        "last year's policy",
    )

    return any(phrase in normalized for phrase in historical_phrases)


def _is_historical_chunk(chunk: Chunk) -> bool:
    """Identify chunks explicitly marked as historical in their metadata."""
    metadata = chunk.metadata_ or {}
    title = str(metadata.get("table_title", "")).casefold()

    historical_markers = (
        "historical",
        "superseded",
        "for reference only",
    )

    return any(marker in title for marker in historical_markers)


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

    # Prefer explicitly current/ordinary evidence for normal policy questions.
    # Historical evidence remains searchable and receives no penalty when the
    # user explicitly asks about past policies or versions.
    historical_query = _requests_historical_policy(query)

    def normalize_term(term: str) -> str:
        term = term.casefold().strip(".,?!:;()[]{}")
        if len(term) > 4 and term.endswith("ies"):
            return term[:-3] + "y"
        if len(term) > 4 and term.endswith("s") and not term.endswith("ss"):
            return term[:-1]
        return term

    query_terms = {
        normalize_term(term)
        for term in query.split()
    }
    query_terms.discard("")

    # Map common ways of expressing an intent to the policy domain.
    # This is lexical expansion, not a claim about policy contents.
    normalized_query = " ".join(query.casefold().split())
    policy_intents = {
        "refund": (
            "refund", "money back", "get my money back",
            "give my money back", "receive my money back",
            "get a reimbursement", "tuition returned",
        ),
    }

    matched_policy_intents: set[str] = set()
    for intent, phrases in policy_intents.items():
        if any(phrase in normalized_query for phrase in phrases):
            matched_policy_intents.add(intent)
            query_terms.add(intent)

    def adjusted_score(chunk_id: uuid.UUID) -> float:
        score = fused_scores[chunk_id]
        item = candidates[chunk_id]
        chunk = item.chunk

        # Prefer tables whose titles match the subject of the question.
        # This is deliberately limited to table chunks.
        metadata = chunk.metadata_ or {}
        table_title = str(metadata.get("table_title", ""))
        if str(chunk.element_type).casefold() == "table" and table_title:
            title_terms = {
                normalize_term(term)
                for term in table_title.split()
            }
            title_terms.discard("")
            overlap = query_terms & title_terms

            if overlap:
                # A matching policy-domain title is stronger evidence than
                # generic word overlap (e.g. "money back" -> "Refund Policy").
                if overlap & matched_policy_intents:
                    score *= 3.0
                elif overlap & {
                    "deadline", "price", "cost", "rate", "value", "amount",
                }:
                    score *= 1.5
                else:
                    score *= 1.2

        # Keep the existing historical-policy behavior.
        if _is_historical_chunk(chunk):
            if historical_query:
                score *= 2.0
            else:
                score *= 0.5

        return score

    ranked_ids = sorted(
        fused_scores,
        key=lambda chunk_id: (
            -adjusted_score(chunk_id),
            chunk_id.hex,
        ),
    )

    return [candidates[chunk_id] for chunk_id in ranked_ids[:top_k]]
