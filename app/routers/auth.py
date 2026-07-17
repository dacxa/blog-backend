from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.security import create_access_token, verify_password
from app.db.models import User
from app.db.session import get_db
from app.schemas.auth import (
    CurrentUserResponse,
    EmailVerificationRequest,
    Token,
    UserLogin,
    UserRegister,
)
from app.services import verification_service


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register/request-code")
def request_code(payload: EmailVerificationRequest):
    verification_service.request_code(payload.email)
    return {"msg": "Verification code sent."}


@router.post("/register/verify-code")
def verify_and_register(payload: UserRegister):
    verification_service.verify_and_create_user(
        email=payload.email,
        code=payload.code,
        username=payload.username,
        password=payload.password,
    )
    return {"msg": "Registration completed."}


@router.post("/login", response_model=Token)
def login(payload: UserLogin, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        (User.username == payload.username) | (User.email == payload.username)
    ).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account is inactive.",
        )

    access_token = create_access_token(
        data={"sub": str(user.id), "ver": user.token_version},
        expires_delta=timedelta(seconds=settings.JWT_ACCESS_EXPIRE_SECONDS),
    )
    current_user = CurrentUserResponse.model_validate(user)
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=settings.JWT_ACCESS_EXPIRE_SECONDS,
        path="/",
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=True,
        samesite="lax",
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        role=current_user.role,
        user=current_user,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    db.query(User).filter(User.id == current_user.id).update(
        {User.token_version: User.token_version + 1},
        synchronize_session=False,
    )
    db.commit()

    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(
        key="access_token",
        path="/",
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/me", response_model=CurrentUserResponse)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user
