from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.models import User
from app.db.session import get_db


bearer_scheme = HTTPBearer(auto_error=False)
VALID_ROLES = {"user", "admin"}


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication is required.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    if credentials is not None and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
    else:
        token = access_token

    if not token:
        raise unauthorized()

    payload = decode_token(token)
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.isdigit():
        raise unauthorized()

    token_version = payload.get("ver")
    if isinstance(token_version, bool) or not isinstance(token_version, int):
        raise unauthorized()

    user = db.get(User, int(subject))
    if user is None or not user.is_active or user.role not in VALID_ROLES:
        raise unauthorized()
    if user.token_version != token_version:
        raise unauthorized()

    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access is required.",
        )

    return current_user
