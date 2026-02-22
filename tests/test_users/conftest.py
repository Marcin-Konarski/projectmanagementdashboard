import sys, os
from unittest.mock import MagicMock
from uuid import uuid4
import pytest
from pytest_mock import MockerFixture
from sqlmodel import Session
from fastapi.testclient import TestClient
from fastapi import FastAPI

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.routers.users import router
from backend.dependencies import get_session
from backend.core.security import get_user_and_session
from backend.models.user import User




@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(router)
    return application


@pytest.fixture
def mock_session(mocker: MockerFixture) -> MagicMock:
    session = mocker.MagicMock(spec=Session)
    return session


@pytest.fixture
def app_with_session(app, mock_session):
    def override_session(): # This simulates DI
        yield mock_session
    app.dependency_overrides[get_session] = override_session # Instead of a real DB session endpoints get mock_session
    return app


@pytest.fixture
def fake_user():
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.username = "testuser"
    return user


@pytest.fixture
def client(app_with_session):
    return TestClient(app_with_session)


@pytest.fixture
def authenticated_client(app, fake_user):
    def override_get_user_and_session():
        return fake_user, MagicMock()
    app.dependency_overrides[get_user_and_session] = override_get_user_and_session # This simulates DI
    return TestClient(app)






@pytest.fixture
def user_register_payload():
    return {
        "username": "testuser",
        "password": "aaaaaaaa",
        "repeat_password": "aaaaaaaa",
    }


@pytest.fixture
def user_register_not_matching_passwords_payload():
    return {
        "username": "testuser",
        "password": "aaaaaaaa",
        "repeat_password": "bbbbbbbb",
    }


@pytest.fixture
def login_payload():
    return {
        "username": "testuser",
        "password": "aaaaaaaa",
    }


@pytest.fixture
def login_invalid_password_payload():
    return {
        "username": "testuser",
        "password": "wrongpassword",
    }


@pytest.fixture
def login_invalid_username_payload():
    return {
        "username": "unknownuser",
        "password": "aaaaaaaa",
    }