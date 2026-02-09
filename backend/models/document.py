from typing import TYPE_CHECKING
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, Relationship


if TYPE_CHECKING:
    from .project import Project


class Document(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    storage_key: str # TODO
    size: int

    project_id: UUID = Field(foreign_key="project.id") # If a project is deleted than documents are deleted as well so there is no point in setting `ondelete` here
    project: Project = Relationship(back_populates="documents")
