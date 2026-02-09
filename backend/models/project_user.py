from typing import TYPE_CHECKING
from uuid import UUID
from enum import Enum
from sqlmodel import SQLModel, Field, Relationship


if TYPE_CHECKING:
    from .user import User
    from .project import Project


class Role(Enum):
    OWNER = "Owner"
    USER = "User"


class ProjectUser(SQLModel, table=True):
    user_id: UUID | None = Field(default=None, foreign_key="user.id", primary_key=True, ondelete="CASCADE")
    project_id: UUID | None = Field(default=None, foreign_key="project.id", primary_key=True, ondelete="CASCADE")
    role: Role

    user: User = Relationship(back_populates="projects")
    project: Project = Relationship(back_populates="users")
