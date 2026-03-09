import re
from typing import Any

from fastapi import HTTPException, status
from sqlmodel import select
from sqlalchemy.exc import IntegrityError
from psycopg2.errors import UniqueViolation

from .session import SessionDep
from ..models import User


def _parse_postgres_duplicate_key(
    error: IntegrityError,
) -> tuple[str | None, str | None]:
    """
    Helper function that extracts constraint and details from PostgreSQL's UniqueViolation error.
    """
    if not isinstance(error.orig, UniqueViolation):
        return None, None

    constraint = getattr(error.orig.diag, "constraint_name", None)
    detail = getattr(error.orig.diag, "message_detail", "")

    duplicate_value = "unknown"
    if detail:
        match = re.search(r"\((.*?)\)=\((.*?)\)", detail)
        if match:
            # duplicate_field = match.group(1)
            duplicate_value = match.group(2)

    return constraint, duplicate_value


def _create_message_for_duplicate_key_violation(
    error: IntegrityError, default_error_message: str
) -> str:
    """
    Helper function that creates a response message to diffrentiate between situations where project with
    specified name already exists or document with specified name already exists.
    Returns message personalized message during IntegrityError.
    """
    constraint, duplicate_value = _parse_postgres_duplicate_key(error)

    print(f"\n\n\n{constraint=}\n{duplicate_value=}\n\n\n")

    if constraint == "project_name_key":
        return f"Project with name '{duplicate_value}' already exists."

    if constraint == "document_name_key":
        return f"Document with name '{duplicate_value}' already exists."

    return default_error_message


def commit_or_409(
    session: SessionDep, error_message: str, extract_details: bool = False
):
    try:
        session.commit()
    except IntegrityError as e:
        session.rollback()

        if hasattr(e, "orig") and isinstance(e.orig, UniqueViolation):
            if extract_details:
                error_message = _create_message_for_duplicate_key_violation(
                    e, error_message
                )

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=error_message
            )
        raise e


def get_or_404(session: SessionDep, model: Any, pk: Any, error_message: str):
    obj = session.get(model, pk)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_message)

    return obj


def get_user_by_username(session: SessionDep, username: str) -> User:
    statement = select(User).where(User.username == username)
    user = session.exec(statement).one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No user with that username."
        )
    return user
