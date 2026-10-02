from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

class Organization(Base):
    __tablename__="organizations"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid = True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    
    slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique =True,
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone = True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    
    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    
    documents: Mapped[list["Document"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    