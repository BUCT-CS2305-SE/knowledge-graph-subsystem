"""JWT authentication helpers for the API."""

from __future__ import annotations

from typing import Iterable, Optional

import jwt
from fastapi import HTTPException

from .config import app_config


def resolve_token(authorization: Optional[str], x_token: Optional[str]) -> Optional[str]:
    if authorization and authorization.startswith("Bearer "):
        return authorization[len("Bearer "):].strip()
    if x_token:
        return x_token.strip()
    return None


def verify_token(
    authorization: Optional[str],
    x_token: Optional[str],
    allowed_user_types: Optional[Iterable[str]] = None,
) -> dict:
    if not app_config.admin_auth_enabled:
        return {}

    token = resolve_token(authorization, x_token)
    if not token:
        raise HTTPException(status_code=401, detail={
            "code": 401, "message": "Unauthorized"})
    try:
        payload = jwt.decode(
            token,
            app_config.jwt_secret,
            algorithms=["HS256"],
            issuer=app_config.jwt_issuer,
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail={
            "code": 401, "message": "Token expired"})
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail={
            "code": 401, "message": "Unauthorized"})

    if allowed_user_types is not None:
        user_type = payload.get("userType")
        if user_type is None or str(user_type) not in set(allowed_user_types):
            raise HTTPException(status_code=403, detail={
                "code": 403, "message": "Forbidden"})

    return payload
