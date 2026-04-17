from typing import Protocol, List, Dict, Any, Optional


class SessionDAOProtocol(Protocol):
    def get_sessions_by_auth_token(self, auth_token: str) -> List[Dict[str, Any]]: ...


def require_auth(session_dao: SessionDAOProtocol, auth_token: str, allowed_roles: List[str]) -> Optional[str]:
    """
    Validate auth_token and enforce role access.

    Returns the user's student_id if their role is 'student', or None for
    teachers and parents. Raises on invalid token or disallowed role.
    """
    sessions = session_dao.get_sessions_by_auth_token(auth_token)
    if not sessions:
        raise Exception("Invalid auth token")

    session = sessions[0]
    role = session.get("role", "student")

    if role not in allowed_roles:
        raise Exception(f"Unauthorized: role '{role}' is not permitted")

    return session["user_id"] if role == "student" else None
