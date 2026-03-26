import pytest
from fastapi.testclient import TestClient

from backend.routers.users import router


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client(router)


@pytest.fixture
def authenticated_client(make_authenticated_client) -> TestClient:
    return make_authenticated_client(router)


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
