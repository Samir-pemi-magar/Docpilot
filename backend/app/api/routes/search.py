from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.auth.authorization import (
    OrganizationAccess,
    get_organization_access,
)
from app.db.session import get_db_session
from app.embeddings.base import EmbeddingProvider
from app.embeddings.dependencies import get_embedding_provider
from app.schemas.retrieval import (
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)
from app.services.retrieval import retrieve_chunks

router = APIRouter(
    prefix="/organizations/{organization_id}/search",
    tags=["search"],
)


@router.post("", response_model=SearchResponse)
async def search_organization_documents(
    organization_id: uuid.UUID,
    payload: SearchRequest,
    access: OrganizationAccess = Depends(get_organization_access),
    db: AsyncSession = Depends(get_db_session),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> SearchResponse:
    """Search indexed document chunks within an organization."""

    # Generate the query embedding without blocking the async event loop.
    try:
        query_embedding = await run_in_threadpool(
            embedding_provider.embed_query,
            payload.query,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if query_embedding.dimension != 1024:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The embedding provider returned an incompatible dimension.",
        )

    retrieved_chunks = await retrieve_chunks(
        db,
        organization_id=organization_id,
        query_vector=query_embedding.vector,
        model=query_embedding.model,
        top_k=payload.top_k,
    )

    return SearchResponse(
        query=payload.query,
        results=[
            SearchResultItem(
                chunk_id=item.chunk.id,
                document_version_id=item.chunk.document_version_id,
                chunk_index=item.chunk.chunk_index,
                text=item.chunk.text,
                distance=item.distance,
                model=item.model,
            )
            for item in retrieved_chunks
        ],
    )
