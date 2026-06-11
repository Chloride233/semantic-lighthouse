from datetime import UTC, datetime, timedelta
from hashlib import sha256
import secrets
from uuid import uuid4

import bcrypt
import jwt
from jwt import InvalidTokenError

from semantic_lighthouse.config import Settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def hash_secret(secret: str) -> str:
    return sha256(secret.encode("utf-8")).hexdigest()


def generate_refresh_secret() -> str:
    return secrets.token_urlsafe(64)


def create_access_token(user_id: str, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "jti": str(uuid4()),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_expire_minutes)).timestamp()),
        "token_type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except InvalidTokenError as exc:
        raise ValueError("Invalid access token") from exc
    if payload.get("token_type") != "access":
        raise ValueError("Invalid token type")
    return payload

