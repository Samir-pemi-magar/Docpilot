from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.auth.authorization import MembershipRole


class MembershipCreate(BaseModel):
    email: EmailStr
    role: MembershipRole = MembershipRole.MEMBER


class MembershipUpdate(BaseModel):
    role: MembershipRole


class MembershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    organization_id: uuid.UUID
    role: MembershipRole
    created_at: datetime


class OrganizationMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    membership_id: uuid.UUID
    user_id: uuid.UUID
    email: EmailStr
    full_name: str
    role: MembershipRole
    joined_at: datetime
