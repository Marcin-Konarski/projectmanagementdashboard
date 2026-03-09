from uuid import UUID
from datetime import datetime
from typing import Annotated
from pydantic import BaseModel, Field

from ..custom_types import Name
from .document import DocumentResponse
from .user import MemberResponse


class ProjectBase(BaseModel):
    name: Name
    description: Annotated[str, Field(max_length=200)] | None = None


class ProjectUpdateRequest(BaseModel):
    name: Name | None = None
    description: Annotated[str, Field(max_length=200)] | None = None


class ProjectInfoResponse(BaseModel):
    id: UUID
    name: Name
    description: Annotated[str, Field(max_length=200)] | None
    owner_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectListItemResponse(BaseModel):
    id: UUID
    name: Name
    description: Annotated[str, Field(max_length=200)] | None

    model_config = {"from_attributes": True}


class ProjectDetailResponse(ProjectInfoResponse):
    members: list[MemberResponse]
    documents: list[DocumentResponse]


class MembersAddRequest(BaseModel):
    usernames: list[str]
