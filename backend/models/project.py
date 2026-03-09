from typing import TYPE_CHECKING
from uuid import UUID, uuid4
from datetime import datetime, timezone
from sqlmodel import SQLModel, VARCHAR, Column, Field, Relationship


if TYPE_CHECKING:
    from .project_user import ProjectUser
    from .document import Document


class Project(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(sa_column=Column("name", VARCHAR, unique=True))
    description: str | None = None
    owner_id: UUID | None = Field(foreign_key="user.id", ondelete="SET NULL")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # users: list[User] = Relationship(back_populates="projects", link_model="ProjectUser")
    users: list["ProjectUser"] = Relationship(
        back_populates="project", cascade_delete=True
    )
    documents: list["Document"] = Relationship(
        back_populates="project", cascade_delete=True
    )
