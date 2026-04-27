import os
from fastapi import Response
from exceptions.auth_error import AuthError

_IS_DEVELOPMENT = os.getenv('APP_ENV', 'production') == 'development'
_COOKIE_DOMAIN = 'eduquestai.org'


def extract_auth_token(request) -> str | None:
    """Extract auth token from Authorization header with cookie fallback."""
    auth_header = request.headers.get('Authorization', '')
    if auth_header and auth_header.lower().startswith('bearer '):
        return auth_header.split(' ', 1)[1].strip()

    raw_cookie = request.headers.get('Cookie', '')
    if 'auth_token=' in raw_cookie:
        parts = [p.strip() for p in raw_cookie.split(';')]
        tokens = [p.split('=', 1)[1] for p in parts if p.startswith('auth_token=')]
        if tokens:
            return tokens[-1]

    return None


def get_user_id_from_token(auth_token, session_dao) -> str:
    """Validate auth_token and return user_id, or raise AuthError."""
    if not auth_token:
        raise AuthError("Missing auth token")
    sessions = session_dao.get_sessions_by_auth_token(auth_token)
    if not sessions:
        raise AuthError("Invalid auth token")
    return sessions[0]['user_id']


def set_auth_cookie(response: Response, token: str) -> None:
    """Set the auth_token cookie with environment-appropriate flags."""
    if _IS_DEVELOPMENT:
        response.set_cookie('auth_token', token, httponly=True, samesite='lax')
    else:
        response.set_cookie(
            'auth_token', token,
            httponly=True, secure=True,
            samesite='none', domain=_COOKIE_DOMAIN,
        )
