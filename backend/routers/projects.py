from uuid import UUID
from typing import Annotated
from fastapi import APIRouter, Depends, Body, Path, status, HTTPException
from sqlmodel import select

from ..db.session import SessionDep
from ..db.utility import commit_or_409, get_user_by_username
from ..schemas.project import (
    ProjectBase,
    ProjectUpdateRequest,
    ProjectInfoResponse,
    ProjectDetailResponse,
    ProjectListItemResponse,
    MembersAddRequest,
)
from ..schemas.document import (
    DocumentBase,
    DocumentResponse,
    DocumentResponseWithURLs,
    DocumentListResponse,
    PresignedUrlResponse,
)
from ..schemas.user import MemberResponse
from ..models import Project, ProjectUser, Document, Role, User, DocumentStatus
from ..core.security import get_user_and_session
from ..dependencies import (
    get_project_for_user_permissions,
    get_project_for_owner_permissions,
    get_document_for_user_permissions,
)
from ..core.config import config
from ..aws_utility.s3_buckets import (
    create_presigned_url_post_operation,
    create_presigned_url_get_operation,
    create_presigned_url_put_operation,
    delete_object,
    delete_objects_by_prefix,
)


router = APIRouter(tags=["projects"])


# Create new project
@router.post(
    "/projects", response_model=ProjectInfoResponse, status_code=status.HTTP_201_CREATED
)
def create_project(
    project: Annotated[ProjectBase, Body()],
    session_and_user: tuple[User, SessionDep] = Depends(get_user_and_session),
) -> Project:
    current_user, session = session_and_user

    owned_count = session.exec(
        select(Project).where(Project.owner_id == current_user.id)
    ).all()
    if len(owned_count) >= config.max_projects:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project limit reached. Maximum allowed: {config.max_projects}.",
        )

    project_db = Project(
        name=project.name, description=project.description, owner_id=current_user.id
    )
    project_user_db = ProjectUser(
        user_id=current_user.id, project_id=project_db.id, role=Role.OWNER
    )

    session.add(project_db)
    session.add(project_user_db)

    commit_or_409(
        session, "Project with that name already exists.", extract_details=True
    )

    session.refresh(project_db)
    return project_db


# List all projects that a user has access to
@router.get(
    "/projects",
    response_model=list[ProjectListItemResponse],
    status_code=status.HTTP_200_OK,
)
def list_all_projects(
    session_and_user: tuple[User, SessionDep] = Depends(get_user_and_session),
) -> list[ProjectListItemResponse]:
    current_user, session = session_and_user

    statement = (
        select(Project).join(ProjectUser).where(ProjectUser.user_id == current_user.id)
    )  # Select all projects that user's id corresponds to user's id from projectuser table
    projects_list = session.exec(statement).all()

    return projects_list


# Return project's full details (members + documents)
@router.get(
    "/projects/{project_id}",
    response_model=ProjectDetailResponse,
    status_code=status.HTTP_200_OK,
)
def get_project_details(
    project_and_session: tuple[Project, SessionDep] = Depends(
        get_project_for_user_permissions
    ),
) -> ProjectDetailResponse:
    project, session = (
        project_and_session  # At this point user is authenticated and authorized
    )

    members = [
        MemberResponse(username=pu.user.username, id=pu.user.id, role=pu.role)
        for pu in project.users
    ]

    return ProjectDetailResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        owner_id=project.owner_id,
        created_at=project.created_at,
        members=members,
        documents=project.documents,
    )


# Update project details (partial update)
@router.patch(
    "/projects/{project_id}",
    response_model=ProjectInfoResponse,
    status_code=status.HTTP_200_OK,
)
def update_project_details(
    project: Annotated[ProjectUpdateRequest, Body()],
    project_and_session: tuple[Project, SessionDep] = Depends(
        get_project_for_user_permissions
    ),
):
    project_db, session = project_and_session

    project_data = project.model_dump(exclude_unset=True)
    project_db.sqlmodel_update(project_data)

    session.add(project_db)
    commit_or_409(
        session, "Project with that name already exists.", extract_details=True
    )
    session.refresh(project_db)

    return project_db


# Delete project (owner only)
@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_and_session: tuple[Project, SessionDep] = Depends(
        get_project_for_owner_permissions
    ),
):
    project, session = project_and_session

    delete_objects_by_prefix(config.s3_bucket_name, f"{project.id}/")

    session.delete(project)
    session.commit()

    return  # HTTP_204_NO_CONTENT


# List project members
@router.get(
    "/projects/{project_id}/members",
    response_model=list[MemberResponse],
    status_code=status.HTTP_200_OK,
)
def get_project_members(
    project_and_session: tuple[Project, SessionDep] = Depends(
        get_project_for_user_permissions
    ),
) -> list[MemberResponse]:
    project, session = project_and_session

    return [
        MemberResponse(id=pu.user.id, username=pu.user.username, role=pu.role)
        for pu in project.users
    ]


# Add members to project (owner only)
@router.post(
    "/projects/{project_id}/members",
    response_model=list[MemberResponse],
    status_code=status.HTTP_201_CREATED,
)
def add_members_to_project(
    members: Annotated[MembersAddRequest, Body()],
    project_and_session: tuple[Project, SessionDep] = Depends(
        get_project_for_owner_permissions
    ),
):
    project, session = project_and_session

    # Disable autoflush to prevent premature INSERT before all usernames are resolved
    with session.no_autoflush:
        # Get existing member user_ids for this project
        existing_member_ids = {pu.user_id for pu in project.users}

        for username in members.usernames:
            clean_username = username.strip().strip("/")
            query_user = get_user_by_username(session, clean_username)

            # Skip users that are already members of this project
            if query_user.id in existing_member_ids:
                continue

            project_user_db = ProjectUser(
                user_id=query_user.id, project_id=project.id, role=Role.USER
            )
            session.add(project_user_db)

    commit_or_409(session, "One or more users already have access to this project.")
    session.refresh(project)

    return [
        MemberResponse(id=pu.user.id, username=pu.user.username, role=pu.role)
        for pu in project.users
    ]


# Remove a member from project (owner only)
@router.delete(
    "/projects/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_member_from_project(
    user_id: Annotated[UUID, Path()],
    project_and_session: tuple[Project, SessionDep] = Depends(
        get_project_for_owner_permissions
    ),
):
    project, session = project_and_session

    statement = select(ProjectUser).where(
        ProjectUser.project_id == project.id, ProjectUser.user_id == user_id
    )
    project_user = session.exec(statement).one_or_none()

    # Here validate if target user is already a member of an project
    if not project_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of this project.",
        )

    # Here validate if target user is project owner so that owner doesn't remove themself from project
    if project_user.role == Role.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the project owner.",
        )

    session.delete(project_user)
    session.commit()

    return


# List all documents for a project
@router.get(
    "/projects/{project_id}/documents",
    response_model=DocumentListResponse,
    status_code=status.HTTP_200_OK,
)
def get_project_documents(
    project_and_session: tuple[Project, SessionDep] = Depends(
        get_project_for_user_permissions
    ),
):
    project, session = project_and_session

    return DocumentListResponse(
        documents=project.documents, count=len(project.documents)
    )


# Upload a document for a specific project
@router.post(
    "/projects/{project_id}/documents",
    response_model=DocumentResponseWithURLs,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    document: Annotated[DocumentBase, Body()],
    project_and_session: tuple[Project, SessionDep] = Depends(
        get_project_for_user_permissions
    ),
):
    project, session = project_and_session

    if len(project.documents) >= config.max_docs:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document limit reached. Maximum allowed per project: {config.max_docs}.",
        )

    document_db = Document(
        name=document.name, project_id=project.id, status=DocumentStatus.PENDING
    )

    session.add(document_db)
    commit_or_409(
        session, "Document with that name already exists.", extract_details=True
    )
    session.refresh(document_db)

    object_key = f"{project.id}/{document_db.id}"
    url = create_presigned_url_post_operation(
        bucket_name=config.s3_bucket_name,
        object_name=object_key,
        filename=document_db.name,
    )

    return DocumentResponseWithURLs(
        id=document_db.id,
        name=document_db.name,
        status=document_db.status,
        created_at=document_db.created_at,
        presigned_url=url,
    )


# Get/download a specific document
@router.get(
    "/projects/{project_id}/documents/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
)
def get_document(
    document_and_session: tuple[Document, SessionDep] = Depends(
        get_document_for_user_permissions
    ),
):
    document, session = document_and_session

    return document


# Get/download a specific document content
@router.get(
    "/projects/{project_id}/documents/{document_id}/content",
    response_model=PresignedUrlResponse,
    status_code=status.HTTP_200_OK,
)
def get_document_content(
    document_and_session: tuple[Document, SessionDep] = Depends(
        get_document_for_user_permissions
    ),
):
    document, session = document_and_session

    object_key = f"{document.project_id}/{document.id}"
    url = create_presigned_url_get_operation(
        bucket_name=config.s3_bucket_name,
        object_name=object_key,
    )

    return PresignedUrlResponse(url=url)


# Update document metadata (partial update)
@router.patch(
    "/projects/{project_id}/documents/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
)
def update_document(
    document_update: Annotated[DocumentBase, Body()],
    document_and_session: tuple[Document, SessionDep] = Depends(
        get_document_for_user_permissions
    ),
):
    document_db, session = document_and_session

    document_data = document_update.model_dump(exclude_unset=True)
    document_db.sqlmodel_update(document_data)

    session.add(document_db)
    commit_or_409(
        session, "Document with that name already exists.", extract_details=True
    )
    session.refresh(document_db)

    return document_db


# Generate presigned URL to replace document content
@router.put(
    "/projects/{project_id}/documents/{document_id}/content",
    response_model=PresignedUrlResponse,
    status_code=status.HTTP_200_OK,
)
def update_document_content(
    document_and_session: tuple[Document, SessionDep] = Depends(
        get_document_for_user_permissions
    ),
):
    document, session = document_and_session

    object_key = f"{document.project_id}/{document.id}"
    url = create_presigned_url_put_operation(
        bucket_name=config.s3_bucket_name,
        object_name=object_key,
        filename=document.name,
    )

    return PresignedUrlResponse(url=url)


# Delete a document
@router.delete(
    "/projects/{project_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_document(
    document_and_session: tuple[Document, SessionDep] = Depends(
        get_document_for_user_permissions
    ),
):
    document, session = document_and_session

    object_key = f"{document.project_id}/{document.id}"
    delete_object(config.s3_bucket_name, object_key)

    session.delete(document)
    session.commit()

    return  # HTTP_204_NO_CONTENT
