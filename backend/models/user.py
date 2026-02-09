from typing import TYPE_CHECKING
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, Relationship


# TYPE_CHECKING helps avoids circular imports
if TYPE_CHECKING:
    from .project_user import ProjectUser


class User(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    username: str
    password: str

    # projects: list[Project] = Relationship(back_populates="users", link_model=ProjectUser)
    projects: list[ProjectUser] = Relationship(back_populates="user")
