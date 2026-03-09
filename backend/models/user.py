from typing import TYPE_CHECKING
from uuid import UUID, uuid4
from sqlmodel import SQLModel, VARCHAR, Column, Field, Relationship


# TYPE_CHECKING helps avoids circular imports
if TYPE_CHECKING:
    from .project_user import ProjectUser


class User(SQLModel, table=True):
    __tablename__ = "user"  # Explicit name is required for alembic to create this table as user is reserved keywork in postgres and it generates conflicts with this table
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    username: str = Field(sa_column=Column("username", VARCHAR, unique=True))
    password: str

    # projects: list[Project] = Relationship(back_populates="users", link_model=ProjectUser)
    projects: list["ProjectUser"] = Relationship(back_populates="user")
