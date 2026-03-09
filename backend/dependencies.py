from typing import Annotated, Tuple
from uuid import UUID
from sqlmodel import select
from fastapi import Depends, Path, status, HTTPException

from .db.session import SessionDep
from .core.security import get_user_and_session
from .models import Project, ProjectUser, Document, Role, User


def _get_project_user_for_project(
    session: SessionDep, user_id: UUID, project_id: UUID
) -> Tuple[Project, ProjectUser]:
    # Get project and project_user record to validate user's permissions to this project
    statement = (
        select(Project, ProjectUser)
        .join(ProjectUser, ProjectUser.project_id == Project.id)
        .where(ProjectUser.project_id == project_id, ProjectUser.user_id == user_id)
    )

    result = session.exec(statement).one_or_none()
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found."
        )

    project, project_user = result
    return project, project_user


def _get_project_user_for_document(
    session: SessionDep, user_id: UUID, project_id: UUID, document_id: UUID
) -> Tuple[Document, ProjectUser]:
    # Get document with that document_id, verify it belongs to the specified project, and get project_user record to validate user's permissions
    statement = (
        select(Document, ProjectUser)
        .where(Document.id == document_id)
        .where(Document.project_id == project_id)
        .join(Project, Project.id == Document.project_id)
        .join(ProjectUser, ProjectUser.project_id == Document.project_id)
        .where(ProjectUser.user_id == user_id)
    )
    result = session.exec(statement).one_or_none()

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
        )

    document, project_user = result
    return document, project_user


def validate_permissions_for_project(
    session: SessionDep, user_id: UUID, project_id: UUID
) -> Tuple[Project, Role]:
    project, project_user = _get_project_user_for_project(session, user_id, project_id)

    if not project_user or project_user.role == Role.NONE:
        # * Here I return 404 instead of 403 in order to not give informations about the project. As "security through obscurity" principle
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found."
        )

    return project, project_user.role


def validate_permissions_for_document(
    session: SessionDep, user_id: UUID, project_id: UUID, document_id: UUID
) -> Tuple[Document, Role]:
    document, project_user = _get_project_user_for_document(
        session, user_id, project_id, document_id
    )

    if not project_user or project_user.role == Role.NONE:
        # * Here I return 404 instead of 403 in order to not give informations about the project. As "security through obscurity" principle
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
        )

    return document, project_user.role


def get_project_for_user_permissions(
    project_id: Annotated[UUID, Path()],
    session_and_user: Tuple[User, SessionDep] = Depends(get_user_and_session),
) -> Tuple[Project, SessionDep]:
    current_user, session = (
        session_and_user  # Validate user's credentials in dependency get_user_and_session()
    )
    project, _role = validate_permissions_for_project(
        session, current_user.id, project_id
    )  # Validate permissions

    return project, session  # Return project and session for reuse


def get_project_for_owner_permissions(
    project_id: Annotated[UUID, Path()],
    session_and_user: Tuple[User, SessionDep] = Depends(get_user_and_session),
) -> Tuple[Project, SessionDep]:
    current_user, session = (
        session_and_user  # Validate user's credentials in get_user_and_session()
    )

    project, role = validate_permissions_for_project(
        session, current_user.id, project_id
    )  # Validate permissions
    # Only project owner can perform actions
    if role != Role.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions."
        )

    return project, session


def get_document_for_user_permissions(
    project_id: Annotated[UUID, Path()],
    document_id: Annotated[UUID, Path()],
    session_and_user: Tuple[User, SessionDep] = Depends(get_user_and_session),
) -> Tuple[Document, SessionDep]:
    current_user, session = (
        session_and_user  # Validate user's credentials in get_user_and_session()
    )
    document, _role = validate_permissions_for_document(
        session, current_user.id, project_id, document_id
    )  # Validate permissions

    return document, session


def get_document_for_owner_permissions(
    project_id: Annotated[UUID, Path()],
    document_id: Annotated[UUID, Path()],
    session_and_user: Tuple[User, SessionDep] = Depends(get_user_and_session),
) -> Tuple[Document, SessionDep]:
    current_user, session = (
        session_and_user  # Validate user's credentials in get_user_and_session()
    )

    document, role = validate_permissions_for_document(
        session, current_user.id, project_id, document_id
    )  # Validate permissions
    # Only project owner can perform actions
    if role != Role.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions."
        )

    return document, session
