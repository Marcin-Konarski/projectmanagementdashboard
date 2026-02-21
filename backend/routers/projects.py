from uuid import UUID
from typing import Annotated
from fastapi import APIRouter, Depends, Query, Body, Path, status
from sqlmodel import select

from ..dependencies import SessionDep
from ..db.utility import commit_or_409, get_or_404, get_user_by_username
from ..schemas.project import DocumentBase, DocumentResponse, DocumentListResponse, ProjectBase, ProjectInfoResponse, ProjectInfoWithUsersResponse, ProjectsListResponse, ProjectWIthDocuments, ProjectWithDocumentsResponse, UserResponse
from ..models import Project, ProjectUser, Document, Role, User
from ..core.security import get_user_and_session

router = APIRouter()

#! Ensure user permissions! So that only valid users can create projects!


# Create new project
@router.post("/projects", response_model=ProjectWithDocumentsResponse, status_code=status.HTTP_201_CREATED, tags=["projects"])
def create_project(project: Annotated[ProjectWIthDocuments, Body()], session_and_user: tuple[User, SessionDep] = Depends(get_user_and_session)) -> Project:
    current_user, session = session_and_user

    project_db = Project(name=project.name, description=project.description, owner_id=current_user.id)
    project_user_db = ProjectUser(user_id=current_user.id, project_id=project_db.id, role=Role.OWNER)

    if project.documents:
        documents_db = [Document(name=doc.name, size=doc.size, storage_key=doc.storage_key) for doc in project.documents]
        project_db.documents = documents_db

    session.add(project_db)
    session.add(project_user_db)

    commit_or_409(session, "Project with that name already exists.", extract_details=True)

    session.refresh(project_db)
    return project_db

# List all projects that a user has access to
@router.get("/projects", response_model=ProjectsListResponse, status_code=status.HTTP_200_OK, tags=["projects"]) # TODO: right now there is an error when user id is not valid. Fix that
def list_all_projects(session_and_user: tuple[User, SessionDep] = Depends(get_user_and_session)):
    current_user, session = session_and_user

    statement = select(Project).join(ProjectUser).where(ProjectUser.user_id == current_user.id) # Select all projects that user's id corresponds to user's id from projectuser table 
    projects_list = session.exec(statement).all()

    return ProjectsListResponse(projects=projects_list)

# Return project’s details
@router.get("/project/{project_id}/info", response_model=ProjectInfoWithUsersResponse, status_code=status.HTTP_200_OK, tags=["projects"])
def get_project_details(project_id: Annotated[UUID, Path()], session_and_user: tuple[User, SessionDep] = Depends(get_user_and_session)) -> ProjectInfoWithUsersResponse:
    current_user, session = session_and_user
    project = get_or_404(session, Project, project_id, "Project not found.") # TODO: actually verify the permissions!

    users_list = [UserResponse(username=pu.user.username, id=pu.user.id) for pu in project.users]

    return ProjectInfoWithUsersResponse(id=project.id, name=project.name, description=project.description, owner_id=project.owner_id, users=users_list)

# Update projects details
@router.put("/project/{project_id}/info", response_model=ProjectInfoResponse, status_code=status.HTTP_201_CREATED, tags=["projects"])
def update_project_details(project_id: Annotated[UUID, Path()], project: Annotated[ProjectBase, Body()], session_and_user: tuple[User, SessionDep] = Depends(get_user_and_session)):
    current_user, session = session_and_user

    project_db = get_or_404(session, Project, project_id, "Project not found.")

    project_data = project.model_dump(exclude_unset=True)
    project_db.sqlmodel_update(project_data)
    # project_db.name = project.name
    # project_db.description = project.description

    session.add(project_db)
    commit_or_409(session, "Project with that name already exists.")
    session.refresh(project_db)

    return project_db

# Return all of the project's documents
@router.get("/project/{project_id}/documents", response_model=DocumentListResponse, status_code=status.HTTP_200_OK, tags=["projects"])
def get_project_documents(project_id: Annotated[UUID, Path()], session_and_user: tuple[User, SessionDep] = Depends(get_user_and_session)):
    current_user, session = session_and_user
    project = get_or_404(session, Project, project_id, "Project not found.") # Ensure the project exists before returning empty list

    # statement = select(Document).where(Document.project_id == project_id)
    # documents = session.exec(statement).all()

    return DocumentListResponse(documents=project.documents, count=len(project.documents))

# Upload document/documents for a specific project
@router.post("/project/{project_id}/documents", response_model=DocumentListResponse, status_code=status.HTTP_201_CREATED, tags=["projects"])
def upload_documents(project_id: Annotated[UUID, Path()], documents: Annotated[list[DocumentBase], Body()], session_and_user: tuple[User, SessionDep] = Depends(get_user_and_session)):
    current_user, session = session_and_user
    project = get_or_404(session, Project, project_id, "Project not found.")

    documents_db = [Document(name=doc.name, size=doc.size, storage_key=doc.storage_key, project_id=project.id) for doc in documents]

    session.add_all(documents_db)
    commit_or_409(session, "Document with that name already exists.", extract_details=True)
    session.refresh(project)

    return DocumentListResponse(documents=project.documents, count=len(project.documents))

# Download document, if the user has access to the corresponding project
@router.get("/document/{document_id}", status_code=status.HTTP_200_OK, tags=["projects"])
def get_project(document_id: Annotated[UUID, Path()]):
    raise NotImplementedError
    # return

# Update document
@router.put("/document/{document_id}", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED, tags=["projects"])
def update_document(document_id: Annotated[UUID, Path()], document: Annotated[DocumentBase, Body()], session_and_user: tuple[User, SessionDep] = Depends(get_user_and_session)):
    current_user, session = session_and_user
    document_db = get_or_404(session, Document, document_id, "Document not found.")

    document_data = document.model_dump(exclude_unset=True)
    document_db.sqlmodel_update(document_data)
    # document_db.name = document.name
    # document_db.storage_key = document.storage_key
    # document_db.size = document.size

    session.add(document_db)
    commit_or_409(session, "Document with that name already exists.")
    session.refresh(document_db)

    return document_db

# Delete document and remove it from the corresponding project
@router.delete("/document/{document_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["projects"])
def delete_document(document_id: Annotated[UUID, Path()], session_and_user: tuple[User, SessionDep] = Depends(get_user_and_session)):
    current_user, session = session_and_user
    document_db = get_or_404(session, Document, document_id, "Document not found.")

    session.delete(document_db)
    session.commit()

    return # HTTP_204_NO_CONTENT

# Grant access to the project for a specific user
@router.post("/project/{project_id}/invite", status_code=status.HTTP_204_NO_CONTENT, tags=["projects"])
def add_user_to_project(project_id: Annotated[UUID, Path()], user: Annotated[str, Query()], session_and_user: tuple[User, SessionDep] = Depends(get_user_and_session)):
    current_user, session = session_and_user

    clean_username = user.strip().strip('/')
    query_user = get_user_by_username(session, clean_username)

    project_user_db = ProjectUser(user_id=query_user.id, project_id=project_id, role=Role.USER)

    session.add(project_user_db)
    commit_or_409(session, f"User {query_user.username} has already access to this project.")

    return # HTTP_204_NO_CONTENT




#! TODO: Add return types so that FastAPI can validate returned data
#! TODO: in the return body for some responses also add the list of users that have access to the project
# https://fastapi.tiangolo.com/tutorial/response-model/