from datetime import datetime, timedelta, timezone
from typing import Annotated, Tuple

import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pwdlib import PasswordHash

from .config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from ..db.session import SessionDep
from ..db.utility import get_user_by_username
from ..schemas.user import TokenData
from ..models import User


password_hash = PasswordHash.recommended()

bearer_scheme = HTTPBearer()


def verify_password(plain_password, hashed_password) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password) -> str:
    return password_hash.hash(password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=5)
    to_encode.update({"exp": int(expire.timestamp())})

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def authenticate_user(session: SessionDep, username: str, password: str) -> str:
    user = get_user_by_username(session, username)
    if not verify_password(password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return access_token


# def get_user_and_session(token: Annotated[str, Depends(oauth2_scheme)], session: SessionDep) -> Tuple[User, SessionDep]:
#     credentials_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="Could not validate credentials.",
#         headers={"WWW-Authenticate": "Bearer"},
#     )


def get_user_and_session(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    session: SessionDep,
) -> Tuple[User, SessionDep]:
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except InvalidTokenError:  # Invalid Token
        raise credentials_exception
    except ExpiredSignatureError:  # Expired token
        raise credentials_exception

    user = get_user_by_username(session, token_data.username)
    if user is None:
        raise credentials_exception
    return (
        user,
        session,
    )  # Returning also session so that it can be reused in the endpoint itself (1 db connection instead of 2 + one DI less)
