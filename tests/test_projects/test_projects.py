from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from psycopg2.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError

from backend.core.config import config
from backend.models import Document, DocumentStatus, Project, ProjectUser, Role


PROJECT_ID = str(uuid4())
DOCUMENT_ID = str(uuid4())
USER_ID = str(uuid4())


def _member(username: str, role: Role = Role.USER, user_id=None):
    member = MagicMock()
    member.user.id = user_id or uuid4()
    member.user.username = username
    member.user_id = member.user.id
    member.role = role
    return member


class TestAuthRequired:
    @pytest.mark.parametrize(
        ("method", "path", "payload"),
        [
            ("post", "/projects", {"name": "Auth Project", "description": "x"}),
            ("get", "/projects", None),
            ("get", f"/projects/{PROJECT_ID}", None),
            ("patch", f"/projects/{PROJECT_ID}", {"name": "Updated"}),
            ("delete", f"/projects/{PROJECT_ID}", None),
            ("get", f"/projects/{PROJECT_ID}/members", None),
            ("post", f"/projects/{PROJECT_ID}/members", {"usernames": ["john"]}),
            ("delete", f"/projects/{PROJECT_ID}/members/{USER_ID}", None),
            ("get", f"/projects/{PROJECT_ID}/documents", None),
            ("post", f"/projects/{PROJECT_ID}/documents", {"name": "docx"}),
            ("get", f"/projects/{PROJECT_ID}/documents/{DOCUMENT_ID}", None),
            ("get", f"/projects/{PROJECT_ID}/documents/{DOCUMENT_ID}/content", None),
            (
                "patch",
                f"/projects/{PROJECT_ID}/documents/{DOCUMENT_ID}",
                {"name": "docu"},
            ),
            ("put", f"/projects/{PROJECT_ID}/documents/{DOCUMENT_ID}/content", None),
            ("delete", f"/projects/{PROJECT_ID}/documents/{DOCUMENT_ID}", None),
        ],
    )
    def test_all_endpoints_require_auth(
        self,
        client: TestClient,
        mock_session: MagicMock,
        method: str,
        path: str,
        payload: dict | None,
    ):
        response = (
            getattr(client, method)(path, json=payload)
            if payload
            else getattr(client, method)(path)
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["detail"] in {
            "Not authenticated",
            "Could not validate credentials.",
        }
        mock_session.commit.assert_not_called()
        mock_session.rollback.assert_not_called()


class TestProjectCreate:
    def test_create_project_happy_path(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_user: MagicMock,
        fake_project_payload,
    ):
        mock_session.exec.return_value.all.return_value = []

        response = authenticated_client.post("/projects", json=fake_project_payload)

        assert response.status_code == status.HTTP_201_CREATED
        assert mock_session.commit.call_count == 1
        assert mock_session.rollback.call_count == 0
        assert mock_session.add.call_count == 2

        project_obj = mock_session.add.call_args_list[0].args[0]
        project_user_obj = mock_session.add.call_args_list[1].args[0]
        mock_session.refresh.assert_called_once_with(project_obj)
        assert response.json()["id"] == str(project_obj.id)
        assert response.json()["name"] == fake_project_payload["name"]
        assert response.json()["description"] == fake_project_payload["description"]
        assert response.json()["owner_id"] == str(fake_user.id)
        assert response.json()["created_at"]
        assert isinstance(project_obj, Project)
        assert project_obj.name == fake_project_payload["name"]
        assert project_obj.description == fake_project_payload["description"]
        assert project_obj.owner_id == fake_user.id
        assert isinstance(project_user_obj, ProjectUser)
        assert project_user_obj.user_id == fake_user.id
        assert project_user_obj.project_id == project_obj.id
        assert project_user_obj.role == Role.OWNER

    def test_create_project_409_project_limit(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project_payload,
    ):
        mock_session.exec.return_value.all.return_value = [
            object()
        ] * config.max_projects

        response = authenticated_client.post("/projects", json=fake_project_payload)

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "Project limit reached" in response.json()["detail"]
        mock_session.commit.assert_not_called()
        mock_session.rollback.assert_not_called()
        mock_session.add.assert_not_called()

    def test_create_project_409_duplicate_name_rolls_back(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project_payload,
    ):
        mock_session.exec.return_value.all.return_value = []

        fake_unique_violation = MagicMock(spec=UniqueViolation)
        fake_unique_violation.diag.constraint_name = "project_name_key"
        fake_unique_violation.diag.message_detail = "(name)=(Test Project)"
        mock_session.commit.side_effect = IntegrityError(
            "duplicate", {}, fake_unique_violation
        )

        response = authenticated_client.post("/projects", json=fake_project_payload)

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already exists" in response.json()["detail"]
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_called_once()
        mock_session.refresh.assert_not_called()

    def test_create_project_422_invalid_name(self, authenticated_client: TestClient):
        response = authenticated_client.post(
            "/projects", json={"name": "ab", "description": "too short name"}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert any("name" in err["loc"] for err in response.json()["detail"])


class TestProjectList:
    def test_list_projects_happy_path(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_user: MagicMock,
    ):
        mock_session.exec.return_value.all.return_value = [
            Project(name="ProjA", description="d1", owner_id=fake_user.id),
            Project(name="ProjB", description="d2", owner_id=fake_user.id),
        ]

        response = authenticated_client.get("/projects")

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert len(payload) == 2
        assert payload[0]["id"]
        assert payload[0]["name"] == "ProjA"
        assert payload[0]["description"] == "d1"
        assert "owner_id" not in payload[0]
        assert payload[1]["name"] == "ProjB"
        assert payload[1]["description"] == "d2"
        mock_session.exec.assert_called_once()


class TestProjectDetails:
    def test_get_project_details_happy_path(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
        fake_user: MagicMock,
        fake_document: Document,
    ):
        fake_project.users = [
            _member("testuser", Role.OWNER, fake_user.id),
            _member("member2", Role.USER),
        ]
        fake_project.documents = [fake_document]
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_project,
            fake_project_user,
        )

        response = authenticated_client.get(f"/projects/{fake_project.id}")

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert payload["id"] == str(fake_project.id)
        assert payload["name"] == fake_project.name
        assert payload["description"] == fake_project.description
        assert payload["owner_id"] == str(fake_project.owner_id)
        assert payload["created_at"]
        assert len(payload["members"]) == 2
        assert payload["members"][0]["id"] == str(fake_user.id)
        assert payload["members"][0]["username"] == "testuser"
        assert payload["members"][0]["role"] == "Owner"
        assert len(payload["documents"]) == 1
        assert payload["documents"][0]["id"] == str(fake_document.id)
        assert payload["documents"][0]["name"] == fake_document.name
        assert payload["documents"][0]["status"] == fake_document.status.value

    def test_get_project_details_404_without_access(
        self, authenticated_client: TestClient, mock_session: MagicMock
    ):
        mock_session.exec.return_value.one_or_none.return_value = None

        response = authenticated_client.get(f"/projects/{uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Project not found."
        mock_session.exec.assert_called_once()


class TestProjectUpdate:
    def test_update_project_happy_path(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
    ):
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_project,
            fake_project_user,
        )

        response = authenticated_client.patch(
            f"/projects/{fake_project.id}",
            json={"name": "UpdatedName", "description": "Updated desc"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == str(fake_project.id)
        assert response.json()["name"] == "UpdatedName"
        assert response.json()["description"] == "Updated desc"
        assert response.json()["owner_id"] == str(fake_project.owner_id)
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()
        mock_session.add.assert_called_once_with(fake_project)
        mock_session.refresh.assert_called_once_with(fake_project)

    def test_update_project_404_without_access(
        self, authenticated_client: TestClient, mock_session: MagicMock
    ):
        mock_session.exec.return_value.one_or_none.return_value = None

        response = authenticated_client.patch(
            f"/projects/{uuid4()}", json={"name": "UpdatedName"}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Project not found."
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_update_project_409_duplicate_rolls_back(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
    ):
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_project,
            fake_project_user,
        )

        fake_unique_violation = MagicMock(spec=UniqueViolation)
        fake_unique_violation.diag.constraint_name = "project_name_key"
        fake_unique_violation.diag.message_detail = "(name)=(UpdatedName)"
        mock_session.commit.side_effect = IntegrityError(
            "duplicate", {}, fake_unique_violation
        )

        response = authenticated_client.patch(
            f"/projects/{fake_project.id}", json={"name": "UpdatedName"}
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "UpdatedName" in response.json()["detail"]
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_called_once()
        mock_session.refresh.assert_not_called()

    def test_update_project_422_invalid_name(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
    ):
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_project,
            fake_project_user,
        )

        response = authenticated_client.patch(
            f"/projects/{fake_project.id}", json={"name": "xy"}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert any("name" in err["loc"] for err in response.json()["detail"])


class TestProjectDelete:
    def test_delete_project_happy_path(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
    ):
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_project,
            fake_project_user,
        )

        with patch(
            "backend.routers.projects.delete_objects_by_prefix"
        ) as delete_prefix:
            response = authenticated_client.delete(f"/projects/{fake_project.id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        delete_prefix.assert_called_once_with(
            config.s3_bucket_name, f"{fake_project.id}/"
        )
        mock_session.delete.assert_called_once_with(fake_project)
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()

    def test_delete_project_403_non_owner(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
    ):
        fake_project_user.role = Role.USER
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_project,
            fake_project_user,
        )

        response = authenticated_client.delete(f"/projects/{fake_project.id}")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["detail"] == "Not enough permissions."
        mock_session.delete.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_delete_project_404_without_access(
        self, authenticated_client: TestClient, mock_session: MagicMock
    ):
        mock_session.exec.return_value.one_or_none.return_value = None

        response = authenticated_client.delete(f"/projects/{uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Project not found."
        mock_session.delete.assert_not_called()
        mock_session.commit.assert_not_called()


class TestProjectMembers:
    def test_get_members_happy_path(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
        fake_user: MagicMock,
    ):
        fake_project.users = [
            _member("testuser", Role.OWNER, fake_user.id),
            _member("member2", Role.USER),
        ]
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_project,
            fake_project_user,
        )

        response = authenticated_client.get(f"/projects/{fake_project.id}/members")

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert len(payload) == 2
        assert payload[0]["username"] == "testuser"
        assert payload[0]["role"] == "Owner"
        assert payload[1]["username"] == "member2"
        assert payload[1]["role"] == "User"

    def test_get_members_404_without_access(
        self, authenticated_client: TestClient, mock_session: MagicMock
    ):
        mock_session.exec.return_value.one_or_none.return_value = None

        response = authenticated_client.get(f"/projects/{uuid4()}/members")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Project not found."

    def test_add_members_happy_path_and_strip_skip_logic(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
        fake_user: MagicMock,
    ):
        fake_project.users = [_member("testuser", Role.OWNER, fake_user.id)]
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_project,
            fake_project_user,
        )

        existing_user = MagicMock()
        existing_user.id = fake_user.id
        new_user = MagicMock()
        new_user.id = uuid4()

        with patch(
            "backend.routers.projects.get_user_by_username",
            side_effect=[existing_user, new_user],
        ) as get_user_by_username:
            response = authenticated_client.post(
                f"/projects/{fake_project.id}/members",
                json={"usernames": ["  testuser/", "newuser"]},
            )

        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.json()) == 1
        assert response.json()[0]["username"] == "testuser"
        assert mock_session.add.call_count == 1
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()
        get_user_by_username.assert_any_call(mock_session, "testuser")
        get_user_by_username.assert_any_call(mock_session, "newuser")

    def test_add_members_403_non_owner(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
    ):
        fake_project_user.role = Role.USER
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_project,
            fake_project_user,
        )

        response = authenticated_client.post(
            f"/projects/{fake_project.id}/members", json={"usernames": ["newuser"]}
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["detail"] == "Not enough permissions."
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_add_members_404_without_access(
        self, authenticated_client: TestClient, mock_session: MagicMock
    ):
        mock_session.exec.return_value.one_or_none.return_value = None

        response = authenticated_client.post(
            f"/projects/{uuid4()}/members", json={"usernames": ["newuser"]}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Project not found."
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_add_members_409_duplicate_rolls_back(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
    ):
        fake_project.users = [_member("owner", Role.OWNER)]
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_project,
            fake_project_user,
        )

        fake_unique_violation = MagicMock(spec=UniqueViolation)
        fake_unique_violation.diag.constraint_name = "project_user_pkey"
        fake_unique_violation.diag.message_detail = "(user_id,project_id)=(x,y)"
        mock_session.commit.side_effect = IntegrityError(
            "duplicate", {}, fake_unique_violation
        )

        with patch("backend.routers.projects.get_user_by_username") as get_user:
            user = MagicMock()
            user.id = uuid4()
            get_user.return_value = user
            response = authenticated_client.post(
                f"/projects/{fake_project.id}/members", json={"usernames": ["u1"]}
            )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert (
            response.json()["detail"]
            == "One or more users already have access to this project."
        )
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_called_once()

    def test_add_members_422_invalid_body(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
    ):
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_project,
            fake_project_user,
        )

        response = authenticated_client.post(
            f"/projects/{fake_project.id}/members", json={"usernames": "not-a-list"}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert any("usernames" in err["loc"] for err in response.json()["detail"])

    def test_remove_member_happy_path(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
    ):
        removable = ProjectUser(
            user_id=uuid4(), project_id=fake_project.id, role=Role.USER
        )
        mock_session.exec.return_value.one_or_none.side_effect = [
            (fake_project, fake_project_user),
            removable,
        ]

        response = authenticated_client.delete(
            f"/projects/{fake_project.id}/members/{removable.user_id}"
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        mock_session.delete.assert_called_once_with(removable)
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()

    def test_remove_member_404_not_member(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
    ):
        mock_session.exec.return_value.one_or_none.side_effect = [
            (fake_project, fake_project_user),
            None,
        ]

        response = authenticated_client.delete(
            f"/projects/{fake_project.id}/members/{uuid4()}"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "User is not a member of this project."
        mock_session.delete.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_remove_member_400_owner_cannot_be_removed(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
    ):
        owner_target = ProjectUser(
            user_id=uuid4(), project_id=fake_project.id, role=Role.OWNER
        )
        mock_session.exec.return_value.one_or_none.side_effect = [
            (fake_project, fake_project_user),
            owner_target,
        ]

        response = authenticated_client.delete(
            f"/projects/{fake_project.id}/members/{owner_target.user_id}"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "Cannot remove the project owner."
        mock_session.delete.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_remove_member_403_non_owner(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
    ):
        fake_project_user.role = Role.USER
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_project,
            fake_project_user,
        )

        response = authenticated_client.delete(
            f"/projects/{fake_project.id}/members/{uuid4()}"
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["detail"] == "Not enough permissions."
        mock_session.delete.assert_not_called()
        mock_session.commit.assert_not_called()


class TestProjectDocuments:
    def test_list_documents_happy_path(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
        fake_document: Document,
    ):
        fake_project.documents = [fake_document]
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_project,
            fake_project_user,
        )

        response = authenticated_client.get(f"/projects/{fake_project.id}/documents")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["count"] == 1
        assert len(response.json()["documents"]) == 1
        assert response.json()["documents"][0]["id"] == str(fake_document.id)
        assert response.json()["documents"][0]["name"] == fake_document.name
        assert response.json()["documents"][0]["status"] == fake_document.status.value

    def test_list_documents_404_without_access(
        self, authenticated_client: TestClient, mock_session: MagicMock
    ):
        mock_session.exec.return_value.one_or_none.return_value = None

        response = authenticated_client.get(f"/projects/{uuid4()}/documents")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Project not found."

    def test_upload_document_happy_path(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
    ):
        fake_project.documents = []
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_project,
            fake_project_user,
        )

        with patch(
            "backend.routers.projects.create_presigned_url_post_operation",
            return_value={"url": "https://upload", "fields": {}},
        ) as create_url:
            response = authenticated_client.post(
                f"/projects/{fake_project.id}/documents", json={"name": "doc123"}
            )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["id"]
        assert response.json()["name"] == "doc123"
        assert response.json()["status"] == DocumentStatus.PENDING.value
        assert response.json()["presigned_url"]["url"] == "https://upload"
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()
        create_url.assert_called_once()
        created_document = mock_session.add.call_args.args[0]
        assert isinstance(created_document, Document)
        assert created_document.name == "doc123"
        assert created_document.project_id == fake_project.id

    def test_upload_document_409_limit(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
    ):
        fake_project.documents = [
            Document(name=f"doc-{i}", project_id=fake_project.id)
            for i in range(config.max_docs)
        ]
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_project,
            fake_project_user,
        )

        response = authenticated_client.post(
            f"/projects/{fake_project.id}/documents", json={"name": "doc-limit"}
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "Document limit reached" in response.json()["detail"]
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_upload_document_409_duplicate_rolls_back(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
    ):
        fake_project.documents = []
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_project,
            fake_project_user,
        )

        fake_unique_violation = MagicMock(spec=UniqueViolation)
        fake_unique_violation.diag.constraint_name = "document_name_key"
        fake_unique_violation.diag.message_detail = "(name)=(doc123)"
        mock_session.commit.side_effect = IntegrityError(
            "duplicate", {}, fake_unique_violation
        )

        response = authenticated_client.post(
            f"/projects/{fake_project.id}/documents", json={"name": "doc123"}
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "doc123" in response.json()["detail"]
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_called_once()
        mock_session.refresh.assert_not_called()

    def test_upload_document_404_without_access(
        self, authenticated_client: TestClient, mock_session: MagicMock
    ):
        mock_session.exec.return_value.one_or_none.return_value = None

        response = authenticated_client.post(
            f"/projects/{uuid4()}/documents", json={"name": "doc123"}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Project not found."
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_upload_document_422_invalid_name(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
    ):
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_project,
            fake_project_user,
        )

        response = authenticated_client.post(
            f"/projects/{fake_project.id}/documents", json={"name": "ab"}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert any("name" in err["loc"] for err in response.json()["detail"])

    def test_get_document_happy_path(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_document: Document,
        fake_project_user: ProjectUser,
    ):
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_document,
            fake_project_user,
        )

        response = authenticated_client.get(
            f"/projects/{fake_document.project_id}/documents/{fake_document.id}"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == str(fake_document.id)
        assert response.json()["name"] == fake_document.name
        assert response.json()["status"] == fake_document.status.value

    def test_get_document_404_without_access(
        self,
        authenticated_client: TestClient,
        fake_document: Document,
        mock_session: MagicMock,
    ):
        mock_session.exec.return_value.one_or_none.return_value = None

        response = authenticated_client.get(
            f"/projects/{fake_document.project_id}/documents/{fake_document.id}"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Document not found."

    def test_get_document_content_happy_path(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_document: Document,
        fake_project_user: ProjectUser,
    ):
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_document,
            fake_project_user,
        )

        with patch(
            "backend.routers.projects.create_presigned_url_get_operation",
            return_value="https://download",
        ) as create_get_url:
            response = authenticated_client.get(
                f"/projects/{fake_document.project_id}/documents/{fake_document.id}/content"
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["url"] == "https://download"
        create_get_url.assert_called_once_with(
            bucket_name=config.s3_bucket_name,
            object_name=f"{fake_document.project_id}/{fake_document.id}",
        )

    def test_get_document_content_404_without_access(
        self,
        authenticated_client: TestClient,
        fake_document: Document,
        mock_session: MagicMock,
    ):
        mock_session.exec.return_value.one_or_none.return_value = None

        response = authenticated_client.get(
            f"/projects/{fake_document.project_id}/documents/{fake_document.id}/content"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Document not found."

    def test_update_document_happy_path(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_document: Document,
        fake_project_user: ProjectUser,
    ):
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_document,
            fake_project_user,
        )

        response = authenticated_client.patch(
            f"/projects/{fake_document.project_id}/documents/{fake_document.id}",
            json={"name": "updated-doc"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == str(fake_document.id)
        assert response.json()["name"] == "updated-doc"
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()
        mock_session.add.assert_called_once_with(fake_document)
        mock_session.refresh.assert_called_once_with(fake_document)

    def test_update_document_409_duplicate_rolls_back(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_document: Document,
        fake_project_user: ProjectUser,
    ):
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_document,
            fake_project_user,
        )

        fake_unique_violation = MagicMock(spec=UniqueViolation)
        fake_unique_violation.diag.constraint_name = "document_name_key"
        fake_unique_violation.diag.message_detail = "(name)=(updated-doc)"
        mock_session.commit.side_effect = IntegrityError(
            "duplicate", {}, fake_unique_violation
        )

        response = authenticated_client.patch(
            f"/projects/{fake_document.project_id}/documents/{fake_document.id}",
            json={"name": "updated-doc"},
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "updated-doc" in response.json()["detail"]
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_called_once()
        mock_session.refresh.assert_not_called()

    def test_update_document_404_without_access(
        self,
        authenticated_client: TestClient,
        fake_document: Document,
        mock_session: MagicMock,
    ):
        mock_session.exec.return_value.one_or_none.return_value = None

        response = authenticated_client.patch(
            f"/projects/{fake_document.project_id}/documents/{fake_document.id}",
            json={"name": "updated-doc"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Document not found."
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_update_document_422_invalid_name(
        self,
        authenticated_client: TestClient,
        fake_document: Document,
        mock_session: MagicMock,
        fake_project_user: ProjectUser,
    ):
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_document,
            fake_project_user,
        )

        response = authenticated_client.patch(
            f"/projects/{fake_document.project_id}/documents/{fake_document.id}",
            json={"name": "ab"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert any("name" in err["loc"] for err in response.json()["detail"])

    def test_update_document_content_happy_path(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_document: Document,
        fake_project_user: ProjectUser,
    ):
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_document,
            fake_project_user,
        )

        with patch(
            "backend.routers.projects.create_presigned_url_put_operation",
            return_value="https://replace",
        ) as create_put_url:
            response = authenticated_client.put(
                f"/projects/{fake_document.project_id}/documents/{fake_document.id}/content"
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["url"] == "https://replace"
        create_put_url.assert_called_once_with(
            bucket_name=config.s3_bucket_name,
            object_name=f"{fake_document.project_id}/{fake_document.id}",
            filename=fake_document.name,
        )

    def test_update_document_content_404_without_access(
        self,
        authenticated_client: TestClient,
        fake_document: Document,
        mock_session: MagicMock,
    ):
        mock_session.exec.return_value.one_or_none.return_value = None

        response = authenticated_client.put(
            f"/projects/{fake_document.project_id}/documents/{fake_document.id}/content"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Document not found."

    def test_delete_document_happy_path(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_document: Document,
        fake_project_user: ProjectUser,
    ):
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_document,
            fake_project_user,
        )

        with patch("backend.routers.projects.delete_object") as delete_object:
            response = authenticated_client.delete(
                f"/projects/{fake_document.project_id}/documents/{fake_document.id}"
            )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        delete_object.assert_called_once_with(
            config.s3_bucket_name, f"{fake_document.project_id}/{fake_document.id}"
        )
        mock_session.delete.assert_called_once_with(fake_document)
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()

    def test_delete_document_404_without_access(
        self,
        authenticated_client: TestClient,
        fake_document: Document,
        mock_session: MagicMock,
    ):
        mock_session.exec.return_value.one_or_none.return_value = None

        response = authenticated_client.delete(
            f"/projects/{fake_document.project_id}/documents/{fake_document.id}"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Document not found."
        mock_session.delete.assert_not_called()
        mock_session.commit.assert_not_called()


class TestValidationByPath:
    @pytest.mark.parametrize(
        ("method", "path", "payload"),
        [
            ("get", "/projects/not-a-uuid", None),
            ("patch", "/projects/not-a-uuid", {"name": "UpdatedName"}),
            ("delete", "/projects/not-a-uuid", None),
            ("get", "/projects/not-a-uuid/members", None),
            ("delete", "/projects/not-a-uuid/members/not-a-uuid", None),
            ("get", "/projects/not-a-uuid/documents/not-a-uuid", None),
            (
                "patch",
                "/projects/not-a-uuid/documents/not-a-uuid",
                {"name": "valid-name"},
            ),
        ],
    )
    def test_invalid_uuid_returns_422(
        self,
        authenticated_client: TestClient,
        method: str,
        path: str,
        payload: dict | None,
    ):
        response = (
            getattr(authenticated_client, method)(path, json=payload)
            if payload
            else getattr(authenticated_client, method)(path)
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json()["detail"]
