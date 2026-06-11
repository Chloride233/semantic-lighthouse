from datetime import timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from semantic_lighthouse.config import Settings, get_settings
from semantic_lighthouse.database import get_db
from semantic_lighthouse.dependencies import get_current_user
from semantic_lighthouse.models import GroupMembership, RefreshToken, User, as_utc, utc_now
from semantic_lighthouse.schemas import AccessTokenResponse, LoginRequest, MeResponse, RegisterRequest, UserResponse
from semantic_lighthouse.security import (
    create_access_token,
    generate_refresh_secret,
    hash_password,
    hash_secret,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _set_refresh_cookie(response: Response, raw_token: str, settings: Settings) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=raw_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/auth",
    )


def _clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(key=settings.refresh_cookie_name, path="/auth")


def _client_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    return request.client.host


def _create_refresh_token(
    db: Session,
    user_id: str,
    settings: Settings,
    request: Request,
    family_id: str | None = None,
) -> tuple[str, RefreshToken]:
    raw_token = generate_refresh_secret()
    refresh_token = RefreshToken(
        user_id=user_id,
        token_hash=hash_secret(raw_token),
        family_id=family_id or str(uuid4()),
        jti=str(uuid4()),
        expires_at=utc_now() + timedelta(days=settings.refresh_token_expire_days),
        user_agent=request.headers.get("user-agent"),
        ip_address=_client_ip(request),
    )
    db.add(refresh_token)
    db.flush()
    return raw_token, refresh_token


def _revoke_refresh_family(db: Session, family_id: str) -> None:
    now = utc_now()
    tokens = db.scalars(select(RefreshToken).where(RefreshToken.family_id == family_id)).all()
    for token in tokens:
        if token.revoked_at is None:
            token.revoked_at = now


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> User:
    email = _normalize_email(payload.email)
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=email, password_hash=hash_password(payload.password), display_name=payload.display_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=AccessTokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AccessTokenResponse:
    email = _normalize_email(payload.email)
    user = db.scalar(select(User).where(User.email == email))
    if user is None or user.disabled_at is not None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    raw_refresh, _ = _create_refresh_token(db, user.id, settings, request)
    db.commit()
    _set_refresh_cookie(response, raw_refresh, settings)
    return AccessTokenResponse(access_token=create_access_token(user.id, settings))


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AccessTokenResponse:
    raw_token = request.cookies.get(settings.refresh_cookie_name)
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")

    token_hash = hash_secret(raw_token)
    refresh_token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if refresh_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    now = utc_now()
    if refresh_token.revoked_at is not None:
        _revoke_refresh_family(db, refresh_token.family_id)
        db.commit()
        _clear_refresh_cookie(response, settings)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token replay detected")
    if as_utc(refresh_token.expires_at) <= now:
        refresh_token.revoked_at = now
        db.commit()
        _clear_refresh_cookie(response, settings)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    user = db.get(User, refresh_token.user_id)
    if user is None or user.disabled_at is not None:
        refresh_token.revoked_at = now
        db.commit()
        _clear_refresh_cookie(response, settings)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is not active")

    raw_new_refresh, new_refresh = _create_refresh_token(
        db,
        user.id,
        settings,
        request,
        family_id=refresh_token.family_id,
    )
    refresh_token.revoked_at = now
    refresh_token.replaced_by_token_id = new_refresh.id
    db.commit()
    _set_refresh_cookie(response, raw_new_refresh, settings)
    return AccessTokenResponse(access_token=create_access_token(user.id, settings))


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    raw_token = request.cookies.get(settings.refresh_cookie_name)
    if raw_token:
        refresh_token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_secret(raw_token)))
        if refresh_token is not None and refresh_token.revoked_at is None:
            refresh_token.revoked_at = utc_now()
            db.commit()
    _clear_refresh_cookie(response, settings)
    return {"message": "Logged out"}


@router.get("/me", response_model=MeResponse)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MeResponse:
    memberships = db.scalars(select(GroupMembership).where(GroupMembership.user_id == current_user.id)).all()
    return MeResponse(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
        created_at=current_user.created_at,
        groups=[
            {"group_id": membership.group_id, "user_id": membership.user_id, "role": membership.role}
            for membership in memberships
        ],
    )
