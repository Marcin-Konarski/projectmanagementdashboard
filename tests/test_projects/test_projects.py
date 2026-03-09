from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from fastapi import status
from psycopg2.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError
from uuid import uuid4

from backend.models import Project, ProjectUser, Document, Role, User


class TestCreateProjects:
    def test_create_project_returns_201(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_user: MagicMock,
        fake_project_payload,
    ):
        response = authenticated_client.post("/projects/", json=fake_project_payload)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["name"] == fake_project_payload.get("name")
        assert response.json()["description"] == fake_project_payload.get("description")

        # Verify fake db calls
        assert mock_session.add.call_count == 2
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

        # Verify what fake objects where attemted to be saved in fake db
        first_call_arg = mock_session.add.call_args_list[0].args[0]  # Project
        second_call_arg = mock_session.add.call_args_list[1].args[0]  # ProjectUser

        # Verify Project was created correctly
        assert isinstance(first_call_arg, Project)
        assert first_call_arg.name == fake_project_payload["name"]
        assert first_call_arg.description == fake_project_payload["description"]
        assert first_call_arg.owner_id == fake_user.id

        # verify ProjectUser was created correctly
        assert isinstance(second_call_arg, ProjectUser)
        assert second_call_arg.user_id == fake_user.id
        assert second_call_arg.project_id == first_call_arg.id  # IDs must match
        assert second_call_arg.role == Role.OWNER

    def test_create_project_with_document_returns_201(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_user: MagicMock,
        fake_project_with_documents_payload,
    ):
        response = authenticated_client.post(
            "/projects/", json=fake_project_with_documents_payload
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["name"] == fake_project_with_documents_payload.get(
            "name"
        )
        assert response.json()[
            "description"
        ] == fake_project_with_documents_payload.get("description")

        # Verify fake db calls
        assert mock_session.add.call_count == 2
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

        # Verify what fake objects where attemted to be saved in fake db
        first_call_arg = mock_session.add.call_args_list[0].args[0]  # Project
        second_call_arg = mock_session.add.call_args_list[1].args[0]  # ProjectUser

        # Verify Project was created correctly
        assert isinstance(first_call_arg, Project)
        assert first_call_arg.name == fake_project_with_documents_payload["name"]
        assert (
            first_call_arg.description
            == fake_project_with_documents_payload["description"]
        )
        assert first_call_arg.owner_id == fake_user.id

        print(f"{first_call_arg.model_dump()=}")

        # Verify documents
        assert isinstance(first_call_arg.documents, list)  # Verify that it's a list
        assert len(first_call_arg.documents) == len(
            fake_project_with_documents_payload["documents"]
        )  # Verify that i has correct number of elements
        assert all(
            isinstance(doc, Document) for doc in first_call_arg.documents
        )  # Verify that all documents are of correct type

        # verify ProjectUser was created correctly
        assert isinstance(second_call_arg, ProjectUser)
        assert second_call_arg.user_id == fake_user.id
        assert second_call_arg.project_id == first_call_arg.id  # IDs must match
        assert second_call_arg.role == Role.OWNER

        for doc, expected in zip(
            first_call_arg.documents, fake_project_with_documents_payload["documents"]
        ):
            assert (
                doc.project_id == first_call_arg.id
            )  # IDs must match (That is the place where I found first actual bug :>)
            assert doc.name == expected["name"]
            assert doc.storage_key == expected["storage_key"]
            assert doc.size == expected["size"]

    def test_create_project_but_user_not_auth_returns_401(
        self, client: TestClient, mock_session: MagicMock, fake_project_payload
    ):
        response = client.post("/projects/", json=fake_project_payload)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_create_project_but_project_name_already_exists_returns_409_(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project_payload,
    ):
        fake_unique_violation = MagicMock(spec=UniqueViolation)
        fake_unique_violation.diag.constraint_name = "project_name_key"
        fake_unique_violation.diag.message_detail = "(name)=(Test Project)"

        # Configure session.commit() to raise IntegrityError with origin of UniqueViolation from PostgreSQL
        mock_session.commit.side_effect = IntegrityError(
            "duplicate", {}, fake_unique_violation
        )

        response = authenticated_client.post("/projects/", json=fake_project_payload)

        assert response.status_code == status.HTTP_409_CONFLICT
        assert (
            response.json()["detail"]
            == f"Project with name '{fake_project_payload.get("name")}' already exists."
        )
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_called_once()
        mock_session.refresh.assert_not_called()

    def test_create_project_but_document_name_already_exists_returns_409(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project_with_documents_payload,
    ):
        document_name = fake_project_with_documents_payload["documents"][0].get(
            "name"
        )  # Get the name of the document
        fake_unique_violation = MagicMock(spec=UniqueViolation)
        fake_unique_violation.diag.constraint_name = "document_name_key"
        fake_unique_violation.diag.message_detail = f"(name)=({document_name})"  # Use the project's name as UniqueViolation message detail

        # Configure session.commit() to raise IntegrityError with origin of UniqueViolation from PostgreSQL
        mock_session.commit.side_effect = IntegrityError(
            "duplicate", {}, fake_unique_violation
        )

        response = authenticated_client.post(
            "/projects/", json=fake_project_with_documents_payload
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert (
            response.json()["detail"]
            == f"Document with name '{fake_project_with_documents_payload['documents'][0].get("name")}' already exists."
        )
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_called_once()
        mock_session.refresh.assert_not_called()


class TestListAllProjects:
    def test_list_all_projects_returns_200(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_user,
        fake_project_payload,
    ):
        project_object = Project(
            name=fake_project_payload.get("name"),
            description=fake_project_payload.get("description"),
            owner_id=fake_user.id,
        )
        mock_session.exec.return_value.all.return_value = [project_object]

        response = authenticated_client.get("/projects/")

        project_data = response.json()["projects"][0]
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["projects"]) == 1
        assert project_data["id"] == str(project_object.id)
        assert project_data["name"] == fake_project_payload.get("name")
        assert project_data["description"] == fake_project_payload.get("description")
        assert project_data["owner_id"] == str(fake_user.id)
        mock_session.exec.assert_called_once()

    def test_list_all_projects_returns_200_with_empty_list(
        self, authenticated_client: TestClient, mock_session: MagicMock
    ):
        mock_session.exec.return_value.all.return_value = []

        response = authenticated_client.get("/projects/")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["projects"] == []
        mock_session.exec.assert_called_once()

    def test_list_all_projects_returns_401_when_not_authenticated(
        self, client: TestClient, mock_session: MagicMock
    ):
        response = client.get("/projects/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        mock_session.exec.assert_not_called()


class TestGetProjectDetails:
    def test_get_project_details_returns_200(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_user: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
    ):
        fake_user_1 = (
            MagicMock()
        )  # Create first fake user that has access to the project
        fake_user_1.user.username = "testuser"
        fake_user_1.user.id = fake_user.id

        fake_user_2 = (
            MagicMock()
        )  # Create second fake user that has access to the project
        fake_user_2.user.username = "otheruser"
        fake_user_2.user.id = uuid4()

        fake_project.users = [
            fake_user_1,
            fake_user_2,
        ]  # Assign access to this project for those users
        mock_session.get.return_value = fake_project

        mock_session.exec.return_value.one_or_none.return_value = (
            fake_project,
            fake_project_user,
        )

        response = authenticated_client.get(f"/project/{fake_project.id}/info")

        project_data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert project_data["id"] == str(fake_project.id)
        assert project_data["name"] == fake_project.name
        assert project_data["description"] == fake_project.description
        assert project_data["owner_id"] == str(fake_project.owner_id)
        assert len(project_data["users"]) == 2
        assert project_data["users"][0]["username"] == "testuser"
        assert project_data["users"][0]["id"] == str(fake_user.id)
        assert project_data["users"][1]["username"] == "otheruser"
        assert project_data["users"][1]["id"] == str(fake_user_2.user.id)

        mock_session.exec.assert_called_once()

    def test_get_project_details_returns_404_when_project_not_found(
        self, authenticated_client: TestClient, mock_session: MagicMock
    ):
        mock_session.exec.return_value.one_or_none.return_value = None

        response = authenticated_client.get(f"/project/{uuid4()}/info")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Project not found."

        mock_session.exec.assert_called_once()

    def test_get_project_details_returns_401_when_not_authenticated(
        self, client: TestClient, mock_session: MagicMock
    ):
        response = client.get(f"/project/{uuid4()}/info")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        mock_session.get.assert_not_called()

    def test_get_project_details_returns_404_when_user_has_no_access(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
    ):
        mock_session.exec.return_value.one_or_none.return_value = (
            None  # If there is no project_user object user has no access to it
        )

        response = authenticated_client.get(f"/project/{fake_project.id}/info")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Project not found."

        mock_session.exec.assert_called_once()


class TestUpdateProjectDetails:
    def test_update_project_details_returns_200(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
    ):
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_project,
            fake_project_user,
        )  # Create fake object
        update_body = {"name": "Updated Name", "description": "Updated Description"}

        response = authenticated_client.put(
            f"/project/{fake_project.id}/info", json=update_body
        )

        # Verify response
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == update_body["name"]
        assert response.json()["description"] == update_body["description"]
        assert response.json()["id"] == str(fake_project.id)
        assert response.json()["owner_id"] == str(fake_project.owner_id)

        # Verify if fake DB operations are correct
        mock_session.exec.assert_called_once()
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

        # Verify the actual object passed to session.add() was the updated project
        updated_project = mock_session.add.call_args_list[0].args[0]
        assert isinstance(updated_project, Project)
        assert updated_project.name == update_body["name"]
        assert updated_project.description == update_body["description"]
        assert (
            updated_project.id == fake_project.id
        )  # Id have to match cuz it's the same project

    def test_update_project_name_only_returns_200(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
    ):
        original_description = (
            fake_project.description
        )  # Remember original description to check if it didn't change
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_project,
            fake_project_user,
        )
        update_body = {"name": "Updated Name Only"}  # No description here

        response = authenticated_client.put(
            f"/project/{fake_project.id}/info", json=update_body
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == update_body["name"]
        assert (
            response.json()["description"] == original_description
        )  # Description must be unchanged

        updated_project = mock_session.add.call_args_list[0].args[0]
        assert updated_project.description == original_description

    def test_update_project_details_returns_404_when_project_not_found(
        self, authenticated_client: TestClient, mock_session: MagicMock
    ):
        mock_session.exec.return_value.one_or_none.return_value = (
            None  # No project found
        )
        update_body = {"name": "Updated Name", "description": "Updated Description"}

        response = authenticated_client.put(
            f"/project/{uuid4()}/info", json=update_body
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Project not found."
        mock_session.exec.assert_called_once()
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_update_project_details_returns_409_when_name_already_exists(
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
        fake_unique_violation.diag.message_detail = f"(name)=({fake_project.name})"
        mock_session.commit.side_effect = IntegrityError(
            "duplicate", {}, fake_unique_violation
        )

        update_body = {
            "name": f"{fake_project.name}",
            "description": "Test Description",
        }
        response = authenticated_client.put(
            f"/project/{fake_project.id}/info", json=update_body
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert (
            response.json()["detail"]
            == f"Project with name '{fake_project.name}' already exists."
        )
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_called_once()
        mock_session.refresh.assert_not_called()  # Must not refresh after failed commit

    def test_update_project_details_returns_401_when_not_authenticated(
        self, client: TestClient, mock_session: MagicMock, fake_project: Project
    ):
        update_body = {
            "name": "Random Name",
            "description": "Random Description",
        }  # Here body doesn't matter. It only has to pass pydantic validation

        response = client.put(f"/project/{fake_project.id}/info", json=update_body)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        mock_session.exec.assert_not_called()
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_update_project_details_returns_404_when_user_has_no_access(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
    ):
        mock_session.exec.return_value.one_or_none.return_value = (
            None  # User has no access (no ProjectUser record)
        )

        update_body = {"name": "Updated Name", "description": "Updated Description"}

        response = authenticated_client.put(
            f"/project/{fake_project.id}/info", json=update_body
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Project not found."
        mock_session.exec.assert_called_once()  # Permission check should be called
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_update_project_details_returns_422_when_name_is_too_long(
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
        update_body = {
            "name": "a" * 1000,
            "description": "Some Description",
        }  # Name way too long

        response = authenticated_client.put(
            f"/project/{fake_project.id}/info", json=update_body
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        mock_session.exec.assert_called_once()  # This exec is called in _get_project_user function which is DI. Dependencies should run before pydantic validation
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()


class TestDeleteProject:
    def test_delete_project_returns_204_when_user_is_owner(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
    ):
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_project,
            fake_project_user,
        )  # Simulate owner permissions

        response = authenticated_client.delete(f"/project/{fake_project.id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        mock_session.exec.assert_called_once()
        mock_session.delete.assert_called_once()
        mock_session.commit.assert_called_once()

        # Verify the correct project object was deleted
        deleted_project = mock_session.delete.call_args_list[0].args[0]
        assert deleted_project == fake_project

    def test_delete_project_returns_403_when_user_is_not_owner(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
    ):
        non_owner_project_user = ProjectUser(
            user_id=fake_project_user.user_id,
            project_id=fake_project.id,
            role=Role.USER,
        )
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_project,
            non_owner_project_user,
        )  # Simulate user (not owner but project participant) tries to delete project

        response = authenticated_client.delete(f"/project/{fake_project.id}")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["detail"] == "Not enough permissions."
        mock_session.exec.assert_called_once()
        mock_session.delete.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_delete_project_returns_404_when_project_not_found_or_no_access(
        self, authenticated_client: TestClient, mock_session: MagicMock
    ):
        mock_session.exec.return_value.one_or_none.return_value = (
            None  # Simulate project not found
        )

        response = authenticated_client.delete(f"/project/{uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Project not found."
        mock_session.exec.assert_called_once()
        mock_session.delete.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_delete_project_returns_401_when_not_authenticated(
        self, client: TestClient, mock_session: MagicMock
    ):
        response = client.delete(f"/project/{uuid4()}")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        mock_session.exec.assert_not_called()
        mock_session.delete.assert_not_called()
        mock_session.commit.assert_not_called()


class TestGetAllProjectDocuments:
    def test_get_project_documents_returns_200(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_document: Document,
        fake_project_user: ProjectUser,
    ):
        fake_project.documents = [fake_document]
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_project,
            fake_project_user,
        )  # Create fake project with a document to be returned and mock project_user to simulate permissions

        response = authenticated_client.get(f"/project/{fake_project.id}/documents/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["documents"]) == response.json()["count"] == 1

        doc_data = response.json()["documents"][0]
        assert doc_data.get("id") == str(fake_document.id)
        assert doc_data.get("name") == fake_document.name
        assert doc_data.get("storage_key") == fake_document.storage_key
        assert doc_data.get("size") == fake_document.size
        assert isinstance(doc_data.get("size"), int)

        mock_session.exec.assert_called_once()

    def test_get_project_documents_returns_200_with_empty_list(
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

        response = authenticated_client.get(f"/project/{fake_project.id}/documents/")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["documents"] == []
        assert response.json()["count"] == 0
        mock_session.exec.assert_called_once()

    def test_get_project_documents_returns_404_when_project_not_found(
        self, authenticated_client: TestClient, mock_session: MagicMock
    ):
        mock_session.exec.return_value.one_or_none.return_value = None

        response = authenticated_client.get(f"/project/{uuid4()}/documents/")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Project not found."
        mock_session.exec.assert_called_once()

    def test_get_project_documents_returns_404_when_user_has_no_access(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
    ):
        mock_session.exec.return_value.one_or_none.return_value = None

        response = authenticated_client.get(f"/project/{fake_project.id}/documents/")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Project not found."
        mock_session.exec.assert_called_once()

    def test_get_project_documents_returns_401_when_not_authenticated(
        self, client: TestClient, mock_session: MagicMock
    ):
        response = client.get(f"/project/{uuid4()}/documents/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        mock_session.exec.assert_not_called()


class TestUploadDocuments:
    def test_upload_documents_returns_201(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
    ):
        fake_doc_1 = Document(
            id=uuid4(),
            name="doc1",
            storage_key="key1",
            size=5,
            project_id=fake_project.id,
        )
        fake_doc_2 = Document(
            id=uuid4(),
            name="doc2",
            storage_key="key2",
            size=10,
            project_id=fake_project.id,
        )
        fake_doc_3 = Document(
            id=uuid4(),
            name="doc3",
            storage_key="key3",
            size=15,
            project_id=fake_project.id,
        )
        fake_project.documents = [
            fake_doc_1,
            fake_doc_2,
            fake_doc_3,
        ]  # Create fake project with 3 fake documents
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_project,
            fake_project_user,
        )

        body = [
            {"name": "doc1", "storage_key": "key1", "size": 5},
            {"name": "doc2", "storage_key": "key2", "size": 10},
            {"name": "doc3", "storage_key": "key3", "size": 15},
        ]
        response = authenticated_client.post(
            f"/project/{fake_project.id}/documents", json=body
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["count"] == 3
        assert len(response.json()["documents"]) == 3

        # Verify all 3 documents were passed to add_all in one call
        added_documents = mock_session.add_all.call_args_list[0].args[0]
        assert len(added_documents) == 3
        assert all(isinstance(doc, Document) for doc in added_documents)
        assert all(
            doc.project_id == fake_project.id for doc in added_documents
        )  # Verify that all are linked to correct project

        # Verify the data of those projects
        for doc, expected in zip(added_documents, body):
            assert doc.name == expected["name"]
            assert doc.storage_key == expected["storage_key"]
            assert doc.size == expected["size"]

    def test_upload_document_returns_404_when_project_not_found(
        self, authenticated_client: TestClient, mock_session: MagicMock
    ):
        mock_session.exec.return_value.one_or_none.return_value = None

        body = [{"name": "doc1", "storage_key": "key", "size": 5}]
        response = authenticated_client.post(f"/project/{uuid4()}/documents", json=body)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Project not found."
        mock_session.exec.assert_called_once()
        mock_session.add_all.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_upload_document_returns_409_when_document_name_already_exists(
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
        fake_unique_violation.diag.constraint_name = "document_name_key"
        fake_unique_violation.diag.message_detail = "(name)=(doc1)"
        mock_session.commit.side_effect = IntegrityError(
            "duplicate", {}, fake_unique_violation
        )  # Set up session.commit() to return IntegrityError with origin of UniqueViolation from PostgreSQL

        body = [{"name": "doc1", "storage_key": "key", "size": 5}]
        response = authenticated_client.post(
            f"/project/{fake_project.id}/documents", json=body
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert (
            response.json()["detail"]
            == f"Document with name '{body[0].get("name")}' already exists."
        )
        mock_session.add_all.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_called_once()
        mock_session.refresh.assert_not_called()  # Refresh not called cuz it did not reach this

    def test_upload_document_returns_401_when_not_authenticated(
        self, client: TestClient, mock_session: MagicMock
    ):
        body = [
            {"name": "doc1", "storage_key": "key", "size": 5}
        ]  # Again body doesn't really matter but must pass pydantic validation
        response = client.post(f"/project/{uuid4()}/documents", json=body)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        mock_session.exec.assert_not_called()
        mock_session.add_all.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_upload_document_returns_404_when_user_has_no_access(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
    ):
        mock_session.exec.return_value.one_or_none.return_value = (
            None  # Simulate situation when user has no access
        )

        body = [{"name": "doc1", "storage_key": "key", "size": 5}]
        response = authenticated_client.post(
            f"/project/{fake_project.id}/documents", json=body
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Project not found."
        mock_session.exec.assert_called_once()
        mock_session.add_all.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_upload_document_returns_422_when_body_is_empty_list(
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

        body = []
        response = authenticated_client.post(
            f"/project/{fake_project.id}/documents", json=body
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        mock_session.exec.assert_called_once()  # Exec triggers as dependecies (so permission validation -> object is fetched from db) are handled before pydantic validation
        mock_session.add_all.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_upload_document_returns_422_when_size_is_negative(
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

        body = [
            {"name": "doc1", "storage_key": "key", "size": -1}
        ]  # Validate negative file size
        response = authenticated_client.post(
            f"/project/{fake_project.id}/documents", json=body
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        mock_session.exec.assert_called_once()  # Exec triggers as dependecies (so permission validation -> object is fetched from db) are handled before pydantic validation
        mock_session.add_all.assert_not_called()

    def test_upload_document_returns_422_when_size_is_string(
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

        # NOTE: following body: body = [{"name": "doc1", "storage_key": "key", "size": "10"}] - with "size": "10" will pass
        # Pydantic validation as Pydantic by default does coerce compatible types so "10" -> 10
        body = [
            {"name": "doc1", "storage_key": "key", "size": "bb"}
        ]  # Validate file size is string
        response = authenticated_client.post(
            f"/project/{fake_project.id}/documents", json=body
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        mock_session.exec.assert_called_once()  # Exec triggers as dependecies (so permission validation -> object is fetched from db) are handled before pydantic validation
        mock_session.add_all.assert_not_called()


class TestDownloadDocument:
    pass


class TestUpdateDocument:
    def test_update_document_returns_200(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_document: Document,
        fake_project_user: ProjectUser,
        fake_document_1_payload,
    ):
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_document,
            fake_project_user,
        )

        response = authenticated_client.put(
            f"/document/{fake_document.id}/", json=fake_document_1_payload
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == fake_document_1_payload.get("name")
        assert response.json()["storage_key"] == fake_document_1_payload.get(
            "storage_key"
        )
        assert response.json()["size"] == fake_document_1_payload.get("size")

        mock_session.exec.assert_called_once()
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

        # Verify actual updated object passed to session.add()
        updated_doc = mock_session.add.call_args_list[0].args[0]
        assert isinstance(updated_doc, Document)
        assert updated_doc.name == fake_document_1_payload["name"]
        assert updated_doc.storage_key == fake_document_1_payload["storage_key"]
        assert updated_doc.size == fake_document_1_payload["size"]
        assert updated_doc.id == fake_document.id
        assert (
            updated_doc.project_id == fake_document.project_id
        )  # Project_id should not be changed

    def test_update_document_returns_404_when_document_not_found(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_document_1_payload,
    ):
        mock_session.exec.return_value.one_or_none.return_value = None

        response = authenticated_client.put(
            f"/document/{uuid4()}/", json=fake_document_1_payload
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Document not found."
        mock_session.exec.assert_called_once()
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_update_document_returns_404_when_user_has_no_access(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_document: Document,
        fake_document_1_payload,
    ):
        mock_session.exec.return_value.one_or_none.return_value = (
            None  # Mock permission check to return None (user has no access)
        )

        response = authenticated_client.put(
            f"/document/{fake_document.id}/", json=fake_document_1_payload
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Document not found."
        mock_session.exec.assert_called_once()
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_update_document_returns_409_when_name_already_exists(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_document: Document,
        fake_project_user: ProjectUser,
        fake_document_1_payload,
    ):
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_document,
            fake_project_user,
        )

        fake_unique_violation = MagicMock(spec=UniqueViolation)
        fake_unique_violation.diag.constraint_name = "document_name_key"
        fake_unique_violation.diag.message_detail = (
            f"(name)=({fake_document_1_payload['name']})"
        )
        mock_session.commit.side_effect = IntegrityError(
            "duplicate", {}, fake_unique_violation
        )

        response = authenticated_client.put(
            f"/document/{fake_document.id}/", json=fake_document_1_payload
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["detail"] == "Document with that name already exists."
        mock_session.exec.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_called_once()
        mock_session.refresh.assert_not_called()

    def test_update_document_returns_401_when_user_not_authenticated(
        self,
        client: TestClient,
        mock_session: MagicMock,
        fake_document: Document,
        fake_document_1_payload,
    ):
        response = client.put(
            f"/document/{fake_document.id}/", json=fake_document_1_payload
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        mock_session.exec.assert_not_called()
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_update_document_returns_422_when_body_is_empty(
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

        body = {}
        response = authenticated_client.put(f"/document/{uuid4()}/", json=body)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        mock_session.exec.assert_called_once()
        mock_session.add_all.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_update_document_returns_422_when_size_is_negative(
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

        body = {
            "name": "doc1",
            "storage_key": "key",
            "size": -1,
        }  # Validate negative file size
        response = authenticated_client.put(f"/document/{uuid4()}/", json=body)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        mock_session.exec.assert_called_once()
        mock_session.add_all.assert_not_called()

    def test_update_document_returns_422_when_size_is_string(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_document: Document,
        fake_project_user: ProjectUser,
    ):
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_document,
            fake_project_user,
        )

        # NOTE: following body: body = [{"name": "doc1", "storage_key": "key", "size": "10"}] - with "size": "10" will pass
        # Pydantic validation as Pydantic by default does coerce compatible types so "10" -> 10
        body = {
            "name": "doc1",
            "storage_key": "key",
            "size": "bb",
        }  # Validate file size is string
        response = authenticated_client.put(f"/document/{fake_project.id}/", json=body)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        mock_session.exec.assert_called_once()
        mock_session.add_all.assert_not_called()


class TestDeleteDocument:
    def test_delete_document_returns_200(
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

        response = authenticated_client.delete(f"/document/{fake_document.id}/")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        mock_session.exec.assert_called_once()
        mock_session.delete.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_not_called()

        # Verify the correct document was deleted
        deleted_doc = mock_session.delete.call_args_list[0].args[0]
        assert deleted_doc == fake_document

    def test_delete_document_returns_404_when_document_not_found(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_document: Document,
    ):
        mock_session.exec.return_value.one_or_none.return_value = None

        response = authenticated_client.delete(f"/document/{fake_document.id}/")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Document not found."
        mock_session.exec.assert_called_once()
        mock_session.delete.assert_not_called()
        mock_session.commit.assert_not_called()
        mock_session.refresh.assert_not_called()

    def test_delete_document_returns_401_when_user_not_authenticated(
        self, client: TestClient, mock_session: MagicMock, fake_document: Document
    ):
        response = client.delete(f"/document/{fake_document.id}/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        mock_session.exec.assert_not_called()
        mock_session.delete.assert_not_called()
        mock_session.commit.assert_not_called()
        mock_session.refresh.assert_not_called()


class TestAddUserToProject:
    def test_add_user_to_project_returns_204(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
    ):
        invited_user = User(id=uuid4(), username="inviteduser", password="aaaaaaaa")
        mock_session.exec.return_value.one_or_none.side_effect = [
            (fake_project, fake_project_user),
            invited_user,
        ]

        response = authenticated_client.post(
            f"/project/{fake_project.id}/invite?user={invited_user.username}"
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

        # Verify correct ProjectUser object was created correctly
        added_project_user = mock_session.add.call_args_list[0].args[0]
        assert isinstance(added_project_user, ProjectUser)  # Validate instance
        assert added_project_user.user_id == invited_user.id  # Validate if new user id
        assert added_project_user.project_id == fake_project.id  # Validate project id
        assert added_project_user.role == Role.USER  # Validate role permission

    def test_add_user_to_project_returns_404_when_project_not_found(
        self, authenticated_client: TestClient, mock_session: MagicMock, fake_user: User
    ):
        mock_session.exec.return_value.one_or_none.return_value = (
            None  # Project not found or no access
        )

        response = authenticated_client.post(
            f"/project/{uuid4()}/invite?user={fake_user.username}"
        )  # Randon project

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Project not found."
        mock_session.exec.assert_called_once()
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_add_user_to_project_returns_404_when_user_not_found(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
    ):
        mock_session.exec.return_value.one_or_none.side_effect = [
            (fake_project, fake_project_user),
            None,
        ]  # User not found

        response = authenticated_client.post(
            f"/project/{fake_project.id}/invite?user=nonexistent"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "No user with that username."
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_add_user_to_project_returns_403_when_user_is_not_owner(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
    ):
        non_owner_project_user = ProjectUser(
            user_id=fake_project_user.user_id,
            project_id=fake_project.id,
            role=Role.USER,
        )  # Permission check with non-owner role
        mock_session.exec.return_value.one_or_none.return_value = (
            fake_project,
            non_owner_project_user,
        )

        response = authenticated_client.post(
            f"/project/{fake_project.id}/invite?user=someuser"
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["detail"] == "Not enough permissions."
        mock_session.exec.assert_called_once()
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_add_user_to_project_returns_409_when_user_already_has_access(
        self,
        authenticated_client: TestClient,
        mock_session: MagicMock,
        fake_project: Project,
        fake_project_user: ProjectUser,
    ):
        invited_user = User(id=uuid4(), username="inviteduser", password="aaaaaaaa")
        mock_session.exec.return_value.one_or_none.side_effect = [
            (fake_project, fake_project_user),
            invited_user,
        ]

        # Simulate duplicate constraint violation
        fake_unique_violation = MagicMock(spec=UniqueViolation)
        mock_session.commit.side_effect = IntegrityError(
            "duplicate", {}, fake_unique_violation
        )

        response = authenticated_client.post(
            f"/project/{fake_project.id}/invite?user={invited_user.username}"
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert (
            response.json()["detail"]
            == f"User {invited_user.username} has already access to this project."
        )
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_called_once()

    def test_add_user_to_project_returns_401_when_not_authenticated(
        self, client: TestClient, mock_session: MagicMock, fake_project: Project
    ):
        response = client.post(f"/project/{fake_project.id}/invite?user=someone")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        mock_session.exec.assert_not_called()
        mock_session.get.assert_not_called()
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()
