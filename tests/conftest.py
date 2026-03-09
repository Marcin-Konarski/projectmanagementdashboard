import pytest
from pytest_mock import MockerFixture
from unittest.mock import MagicMock
from sqlmodel import Session
from fastapi import FastAPI, APIRouter
from fastapi.testclient import TestClient
from uuid import uuid4
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.dependencies import get_session
from backend.core.security import get_user_and_session
from backend.models.user import User


# @pytest.fixture
# def app():
#     application = FastAPI()
#     application.include_router(router)
#     return application


@pytest.fixture
def mock_session(mocker: MockerFixture) -> MagicMock:
    """Fixture that creates fake session"""
    session = mocker.MagicMock(spec=Session)
    return session


# @pytest.fixture
# def app_with_session(app, mock_session):
#     def override_session(): # This simulates DI
#         yield mock_session
#     app.dependency_overrides[get_session] = override_session # Instead of a real DB session endpoints get mock_session
#     return app


@pytest.fixture
def fake_user() -> MagicMock:
    """Fixture that creates a fake user"""
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.username = "testuser"
    return user


# @pytest.fixture
# def client(app_with_session) -> TestClient:
#     return TestClient(app_with_session)


# @pytest.fixture
# def authenticated_client(app, fake_user):
#     def override_get_user_and_session() -> TestClient:
#         return fake_user, MagicMock()
#     app.dependency_overrides[get_user_and_session] = override_get_user_and_session # This simulates DI
#     return TestClient(app)


# Factory methods in order to reuse the code with different routers


@pytest.fixture
def make_client(mock_session):
    """Factory fixture — call it with a router to get a plain client"""

    def _make(router: APIRouter) -> TestClient:
        app = FastAPI()
        app.include_router(router)

        def override_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_session
        return TestClient(app)

    return _make


@pytest.fixture
def make_authenticated_client(mock_session, fake_user):
    """Factory fixture — call it with a router to get an authenticated client"""

    def _make(router: APIRouter) -> TestClient:
        app = FastAPI()
        app.include_router(router)

        def override_session():
            yield mock_session

        def override_get_user_and_session():
            yield fake_user, mock_session

        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[get_user_and_session] = override_get_user_and_session
        return TestClient(app)

    return _make
