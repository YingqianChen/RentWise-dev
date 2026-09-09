"""Security utilities for authentication."""

from dataclasses import dataclass
import hashlib
import json

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import settings

# Use PBKDF2-SHA256 to avoid bcrypt backend issues and the 72-byte password limit.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a stored hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password for storage."""
    return pwd_context.hash(password)


def create_access_token(subject: str | Any, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    if expires_delta is not None:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject), "jti": str(uuid4())}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt


@dataclass(frozen=True)
class AccessTokenIdentity:
    user_id: str
    revocation_key: str
    expires_at: datetime


def decode_token_identity(token: str) -> Optional[AccessTokenIdentity]:
    """Verify first, then identify a session from authenticated claims.

    Never key revocation by raw JWT bytes: alternate signature encodings can
    represent the same valid token. Legacy tokens had only sub and exp.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"], options={"require_exp": True, "require_sub": True})
        user_id = str(UUID(payload["sub"]))
        expires = payload["exp"]
        if type(expires) is not int:
            return None
        expires_at = datetime.fromtimestamp(expires, timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            return None
        jti = payload.get("jti")
        if jti is not None and (not isinstance(jti, str) or not jti or len(jti) > 128):
            return None
        identity = ["jti", user_id, jti] if jti is not None else ["legacy", user_id, expires]
        key = hashlib.sha256(json.dumps(identity, separators=(",", ":")).encode()).hexdigest()
        return AccessTokenIdentity(user_id=user_id, revocation_key=key, expires_at=expires_at)
    except (JWTError, ValueError, TypeError, AttributeError, OverflowError, OSError):
        return None


def decode_access_token(token: str) -> Optional[str]:
    """Compatibility helper for callers that only need the verified subject."""
    identity = decode_token_identity(token)
    return identity.user_id if identity else None
