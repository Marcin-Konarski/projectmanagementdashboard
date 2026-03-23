from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Annotated

from ..custom_types import Name


class DocumentBase(BaseModel):
    name: Name

    model_config = {"from_attributes": True}


class DocumentResponse(DocumentBase):
    id: UUID
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}

class DocumentResponseWithURLs(DocumentResponse):
    presigned_url: dict


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    count: int


class PresignedUrlResponse(BaseModel):
    url: str
