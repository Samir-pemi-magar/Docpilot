from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import(
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column,relationship

from app.db.base import Base

class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_memberships_organization_user",
        ),
        CheckConstraint(
            "role IN ('owner', 'admin', 'member')",
            name="ck_memberships_role"
        )
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
     
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="member",
    )
     
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
     
    organization: Mapped["Organization"] = relationship(
        back_populates="memberships",
    )
    
    user: Mapped["User"] = relationship(
        back_populates="memberships",
    )