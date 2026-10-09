from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import(
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

class DocumentVersion(Base):
    __tablename__="document_versions"
    __table_args__=(
        CheckConstraint(
            "ingestion_status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_document_versions_ingestion_status",
        ),

        UniqueConstraint(
            "document_id",
            "version_number",
            name="uq_document_version_document_version",
        ),
        CheckConstraint(
            "version_number >0",
            name="ck_document_versions_version_number_positive",
        ),
        CheckConstraint(
            "size_bytes >=0",
            name="ck_document_versions_size_bytes_nonnegative",
        )
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    original_filename: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )

    content_type: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    storage_object_key: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        unique=True,
    )

    sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    ingestion_status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        server_default="pending",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    document: Mapped["Document"] = relationship(
        back_populates="versions",
    )

    uploaded_by: Mapped["User"] = relationship(
        back_populates="uploaded_document_versions",
        foreign_keys=[uploaded_by_user_id],
    )

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document_version",
        cascade="all, delete-orphan",
        order_by="Chunk.chunk_index",
    )
