from typing import TYPE_CHECKING
from uuid import UUID, uuid4
from datetime import datetime, timezone
from sqlmodel import SQLModel, VARCHAR, Column, Field, Relationship


if TYPE_CHECKING:
    from .project import Project


class Document(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(sa_column=Column("name", VARCHAR, unique=True))
    storage_key: str  # TODO
    size: int  # TODO: validate size and storage key inputs!!
    content_type: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    project_id: UUID = Field(
        foreign_key="project.id"
    )  # If a project is deleted than documents are deleted as well so there is no point in setting `ondelete` here
    project: "Project" = Relationship(back_populates="documents")
