from uuid import UUID
from pydantic import BaseModel

from ..custom_types import Name



class DocumentBase(BaseModel):
    name: Name
    storage_key: str
    size: int


class DocumentResponse(DocumentBase):
    id: UUID
    project_id: UUID

    model_config = {
        "from_attributes": True
    }

class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    count: int