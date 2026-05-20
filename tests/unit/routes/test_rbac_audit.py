"""
Audit: every route must declare an auth dependency or be explicitly listed as public.
Fails loudly when a new route is added without auth.
"""
import pytest
from fastapi.routing import APIRoute
from main import app
from routers.deps import get_auth

# Routes that are intentionally public — no auth required.
# Add to this set when a new public endpoint is introduced; document the reason.
EXPLICITLY_PUBLIC_ROUTES = {
    "/auth/signup",
    "/auth/login",
    "/auth/password-reset/request",
    "/auth/password-reset/confirm",
    "/helloworld",
    "/billing/webhook",  # verified by Stripe signature, not JWT
    "/demo/quest",  # public demo endpoint — no account required
}


def _has_get_auth(dependant) -> bool:
    """Recursively check whether get_auth appears anywhere in the dependency tree."""
    for dep in dependant.dependencies:
        if dep.call is get_auth:
            return True
        if _has_get_auth(dep):
            return True
    return False


@pytest.mark.unit
def test_all_routes_have_auth_dependency():
    unguarded = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if route.path in EXPLICITLY_PUBLIC_ROUTES:
            continue
        if not _has_get_auth(route.dependant):
            methods = ",".join(sorted(route.methods or []))
            unguarded.append(f"{methods} {route.path}")

    assert unguarded == [], (
        "Routes missing auth dependency (add Depends(get_auth / require_roles / "
        "require_student_viewer) or add to EXPLICITLY_PUBLIC_ROUTES):\n"
        + "\n".join(unguarded)
    )
