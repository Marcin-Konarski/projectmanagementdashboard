from typing import Annotated, Any
from fastapi import APIRouter, HTTPException, Depends, Body, status
from fastapi.security import OAuth2PasswordRequestForm

from ..dependencies import SessionDep
from ..db.utility import commit_or_409
from ..core.security import get_password_hash, authenticate_user, get_user_and_session
from ..schemas.user import UserRequest, UserAuthRequest, UserResponse, Token, TokenData
from ..models.user import User


router = APIRouter()

# TODO: Unify endpoints reqest data!!
# TODO: /auth/ takes params in body and /login/ takes params from OAuth2. Decide which one to use and stick to one


# Create user
@router.post("/auth", response_model=UserResponse, status_code=status.HTTP_201_CREATED, tags=["users"])
def auth_user(user: Annotated[UserAuthRequest, Body()], session: SessionDep) -> Any:
    if user.password.get_secret_value() != user.repeat_password.get_secret_value():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match.")

    hashed_password = get_password_hash(user.password.get_secret_value())
    user_db = User(username=user.username, password=hashed_password)
    session.add(user_db)

    commit_or_409(session=session, error_message="Username already exists.")

    session.refresh(user_db)
    return user_db

# TODO: CONSIDER SENDING THIS JWT TOKEN IN HEADER OR EVEN IN COOKIE!!!
# TODO: CONSIDER SENDING THIS JWT TOKEN IN HEADER OR EVEN IN COOKIE!!!

# Login into service, validate credentials and return JWT access token
# @router.post("/login", status_code=status.HTTP_200_OK, tags=["users"])
# def login_user(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep) -> Any:
#     access_token = authenticate_user(session, form_data.username, form_data.password)
#     return Token(access_token=access_token, token_type="bearer")

@router.post("/login/", status_code=status.HTTP_200_OK, tags=["users"])
def login_user(user: Annotated[UserRequest, Body()], session: SessionDep) -> Any:
    access_token = authenticate_user(session, user.username, user.password.get_secret_value())
    return Token(access_token=access_token, token_type="bearer")

# Get informations about currently logged in user
@router.get("/me/", response_model=UserResponse, status_code=status.HTTP_200_OK, tags=["users"])
def get_user_info(session_and_user: tuple[User, SessionDep] = Depends(get_user_and_session)) -> Any:
    current_user, session = session_and_user
    return current_user





# # Logout from service
# @router.post("/logout/", status_code=status.HTTP_200_OK, tags=["users"])
# def logout_user():
#     raise NotImplementedError
#     # return















#! TODO: Add return types so that FastAPI can validate returned data