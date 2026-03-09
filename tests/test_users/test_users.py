from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import status
from psycopg2.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError
from datetime import timedelta
import sys
import os
import jwt

from backend.models import User
from backend.routers.users import get_password_hash
from backend.core.security import create_access_token
from backend.core.config import SECRET_KEY, ALGORITHM

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..")
)  # TODO: replace this with pyproject.toml or pytest.ini


class TestUserAuth:
    def test_user_created_returns_201(
        self, client: TestClient, mock_session: MagicMock, user_register_payload
    ):
        with patch(
            "backend.routers.users.get_password_hash", return_value="hashed_password"
        ):
            response = client.post("/auth", json=user_register_payload)

        assert response.status_code == status.HTTP_201_CREATED
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

    def test_user_created_returns_400_when_passwords_dont_match(
        self,
        client: TestClient,
        mock_session: MagicMock,
        user_register_not_matching_passwords_payload,
    ):
        response = client.post(
            "/auth", json=user_register_not_matching_passwords_payload
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "Passwords do not match."
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_user_created_returns_409_when_username_exists(
        self, client: TestClient, mock_session: MagicMock, user_register_payload
    ):
        fake_unique_violation = MagicMock(spec=UniqueViolation)
        fake_unique_violation.diag.constraint_name = "username_key"
        fake_unique_violation.diag.message_detail = "(username)=(testuser)"  # Simulate real UniqueViolation error with username duplicate field

        mock_session.commit.side_effect = IntegrityError(
            "duplicate", {}, fake_unique_violation
        )

        with patch(
            "backend.routers.users.get_password_hash", return_value="hashed_password"
        ):
            response = client.post("/auth", json=user_register_payload)

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["detail"] == "Username already exists."
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_called_once()


class TestUserLogin:
    def test_login_returns_200_with_token(
        self, client: TestClient, mock_session: MagicMock, login_payload
    ):
        mock_session.exec.return_value.one_or_none.return_value = User(
            username="testuser", password=get_password_hash("aaaaaaaa")
        )

        response = client.post("/login/", json=login_payload)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["token_type"] == "bearer"
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 0
        decoded = jwt.decode(
            data["access_token"], SECRET_KEY, algorithms=[ALGORITHM]
        )  # This will actually verify if it's a real JWT
        assert decoded["sub"] == "testuser"

    def test_login_returns_401_for_wrong_credentials(
        self,
        client: TestClient,
        mock_session: MagicMock,
        login_invalid_password_payload,
    ):
        mock_session.exec.return_value.one_or_none.return_value = User(
            username="testuser", password=get_password_hash("aaaaaaaa")
        )

        response = client.post("/login/", json=login_invalid_password_payload)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["detail"] == "Could not validate credentials."

    def test_login_returns_404_for_unknown_user(
        self,
        client: TestClient,
        mock_session: MagicMock,
        login_invalid_username_payload,
    ):
        mock_session.exec.return_value.one_or_none.return_value = None

        response = client.post("/login/", json=login_invalid_username_payload)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "No user with that username."


class TestGetMe:
    def test_get_me_returns_200_with_user_info(
        self, client: TestClient, mock_session: MagicMock
    ):
        fake_user = User(username="testuser", password=get_password_hash("aaaaaaaa"))
        mock_session.exec.return_value.one_or_none.return_value = fake_user

        real_token = create_access_token(data={"sub": "testuser"})

        response = client.get("/me/", headers={"Authorization": f"Bearer {real_token}"})

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["username"] == "testuser"
        assert response.json()["id"] == str(fake_user.id)

    def test_get_me_returns_401_with_invalid_token(
        self, client: TestClient, mock_session: MagicMock
    ):
        response = client.get(
            "/me/", headers={"Authorization": "Bearer fake_invalid_token"}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["detail"] == "Could not validate credentials."
        mock_session.exec.assert_not_called()  # Should fail before hitting DB

    def test_get_me_returns_401_with_expired_token(
        self, client: TestClient, mock_session: MagicMock
    ):
        expired_token = create_access_token(
            data={"sub": "testuser"}, expires_delta=timedelta(seconds=-1)
        )

        response = client.get(
            "/me/", headers={"Authorization": f"Bearer {expired_token}"}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["detail"] == "Could not validate credentials."
        mock_session.exec.assert_not_called()
