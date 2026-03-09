from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Annotated

from ..custom_types import Name


class DocumentBase(BaseModel):
    name: Name
    storage_key: Annotated[
        str, Field(min_length=1)
    ]  # TODO: Adjust this value to actual AWS key
    size: Annotated[int, Field(gt=0)]

    model_config = {"from_attributes": True}


class DocumentRequest(BaseModel):
    name: Name | None = None
    size: Annotated[int, Field(gt=0)] | None = None
    storage_key: Annotated[str, Field(min_length=1)] | None = None
    content_type: Annotated[str, Field(min_length=1)] | None = None


class DocumentResponse(DocumentBase):
    id: UUID
    content_type: str | None = None
    created_at: datetime


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    count: int
