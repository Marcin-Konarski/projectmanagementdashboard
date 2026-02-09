from typing import TYPE_CHECKING
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, Relationship


if TYPE_CHECKING:
    from .project_user import ProjectUser
    from .document import Document


class Project(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    description: str | None = None
    owner_id: UUID | None = Field(foreign_key="user.id", ondelete="SET NULL")

    # users: list[User] = Relationship(back_populates="projects", link_model="ProjectUser")
    users: list[ProjectUser] = Relationship(back_populates="project")
    documents: list[Document] = Relationship(back_populates="project", cascade_delete=True)

