import os
from typing import Optional

import jwt
from fastapi import Cookie, Header, HTTPException

JWT_SECRET = os.getenv("JWT_SECRET_KEY", "fallback-secret")
JWT_ALGORITHM = "HS256"


class AuthPayload:
    def __init__(self, sub: str, role: str, token: str) -> None:
        self.sub = sub        # decoded user id / teacher id
        self.role = role      # decoded role claim
        self.token = token    # raw JWT string — forwarded to SessionDAO-backed services


def get_auth(
    authorization: Optional[str] = Header(default=None),
    auth_token: Optional[str] = Cookie(default=None),
) -> AuthPayload:
    token: Optional[str] = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    elif auth_token:
        token = auth_token

    if not token:
        raise HTTPException(status_code=401, detail="Missing auth token")

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return AuthPayload(
            sub=payload["sub"],
            role=payload.get("role", "student"),
            token=token,
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
