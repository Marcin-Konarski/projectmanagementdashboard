from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

from backend.routers.projects import router
from backend.models import Project, ProjectUser, Document, Role


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client(router)


@pytest.fixture
def authenticated_client(make_authenticated_client) -> TestClient:
    return make_authenticated_client(router)


@pytest.fixture
def fake_project(fake_user) -> Project:
    return Project(
        id=uuid4(),
        name=f"test_project_{id}",  # Ensure each project has diffrent name
        description="Test Description",
        owner_id=fake_user.id,
    )


@pytest.fixture
def fake_project_user(fake_project, fake_user) -> ProjectUser:
    return ProjectUser(
        user_id=fake_user.id, project_id=fake_project.id, role=Role.OWNER
    )


@pytest.fixture
def fake_document(fake_project) -> Document:
    return Document(
        id=uuid4(),
        name=f"test_document_{id}",  # Ensure each document has diffrent name
        storage_key="key",
        size=5,
        project_id=fake_project.id,
    )


@pytest.fixture
def fake_project_payload():
    return {
        "name": "Test Project",
        "description": "Test Description",
    }


@pytest.fixture
def fake_document_1_payload():
    return {"name": "doc1", "storage_key": "key", "size": 5}


@pytest.fixture
def fake_document_2_payload():
    return {"name": "doc2", "storage_key": "key", "size": 5}


@pytest.fixture
def fake_project_with_documents_payload(
    fake_project_payload, fake_document_1_payload, fake_document_2_payload
):
    return {
        **fake_project_payload,
        "documents": [fake_document_1_payload, fake_document_2_payload],
    }
