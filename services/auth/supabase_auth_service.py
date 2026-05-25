import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from data_access.user_dao import UserDAO
    from supabase import Client

logger = logging.getLogger(__name__)


class SupabaseAuthService:
    """
    Thin wrapper around Supabase Auth Admin API.
    Creates Supabase Auth entries and stores the returned UUID in the EduQuest
    user table. Must never raise — failures are logged and retried on next login.
    """

    def __init__(self, supabase_client: "Client | None" = None, user_dao: "UserDAO | None" = None) -> None:
        self._client = supabase_client
        self._user_dao = user_dao

    def _get_client(self) -> "Client":
        if self._client is None:
            from data_access.config import get_admin_supabase_client
            self._client = get_admin_supabase_client()
        return self._client

    def _get_user_dao(self) -> "UserDAO":
        if self._user_dao is None:
            from data_access.user_dao import UserDAO
            self._user_dao = UserDAO()
        return self._user_dao

    def provision_user(self, user_id: str, email: str, password: str, role: str) -> "str | None":
        """
        Create a Supabase Auth entry for this EduQuest user and store the UUID.
        Returns the UUID on success, None on any failure.
        Idempotent — returns existing supabase_auth_id without a second create_user call.

        Sets app_metadata: {"username": user_id, "role": role}
          username — EduQuest user_id; read by Phase 4 deps.py to populate AuthPayload.sub
          role     — EduQuest role; read by Phase 4 middleware for route gating
        """
        try:
            existing = self._get_user_dao().get_by_id(user_id)
            if existing and existing.get("supabase_auth_id"):
                return existing["supabase_auth_id"]

            response = self._get_client().auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True,
                "app_metadata": {"username": user_id, "role": role},
            })
            auth_uuid: str = response.user.id
            self._get_user_dao().update(user_id, {"supabase_auth_id": auth_uuid})
            return auth_uuid
        except Exception:
            logger.warning(
                "Supabase Auth provisioning failed for user_id=%s email=%s",
                user_id,
                email,
                exc_info=True,
            )
            return None

    def store_oauth_auth_id(self, user_id: str, supabase_auth_uuid: str, role: str) -> None:
        """
        For OAuth users: the Supabase Auth entry already exists; store the UUID and
        set app_metadata.username + app_metadata.role via admin API so Phase 4 deps.py
        can read these claims from the Supabase JWT.
        """
        try:
            self._get_user_dao().update(user_id, {"supabase_auth_id": supabase_auth_uuid})
        except Exception:
            logger.warning(
                "Failed to store supabase_auth_id for OAuth user user_id=%s uuid=%s",
                user_id,
                supabase_auth_uuid,
                exc_info=True,
            )
        # Do NOT swallow this exception — if app_metadata is not set, every
        # subsequent request for this user will 401 ("User not provisioned in Supabase Auth")
        self._get_client().auth.admin.update_user_by_id(
            supabase_auth_uuid,
            {"app_metadata": {"username": user_id, "role": role}},
        )

    def sign_in_with_password(self, email: str, password: str):
        """
        Sign in via Supabase Auth and return the AuthResponse.
        Raises on failure — callers are responsible for handling exceptions.

        Uses a fresh, throw-away client (anon key) so the shared admin client's
        internal session is never overwritten by the returned user JWT. Without
        this isolation, supabase-py would replace the admin client's
        Authorization header with the user JWT on every login, causing all
        subsequent DAO queries to run under that user's RLS context.
        """
        import os
        import httpx
        from supabase import create_client
        from supabase.lib.client_options import SyncClientOptions
        url = os.environ["SUPABASE_URL"]
        anon_key = os.environ["SUPABASE_PUBLISHABLE_KEY"]
        fresh_client = create_client(
            url, anon_key,
            options=SyncClientOptions(httpx_client=httpx.Client()),
        )
        return fresh_client.auth.sign_in_with_password({"email": email, "password": password})

    def delete_user(self, supabase_auth_uuid: str) -> None:
        """Delete a Supabase Auth user by UUID. Raises on failure."""
        self._get_client().auth.admin.delete_user(supabase_auth_uuid)

    def sync_password(self, supabase_auth_uuid: str, new_plaintext_password: str) -> None:
        """
        Sync a changed password to Supabase Auth.
        Called from the password reset confirm flow so Phase 4's sign_in_with_password
        never diverges from the bcrypt hash.
        No-op if supabase_auth_uuid is falsy (user not yet provisioned).
        """
        if not supabase_auth_uuid:
            return
        try:
            self._get_client().auth.admin.update_user_by_id(
                supabase_auth_uuid,
                {"password": new_plaintext_password},
            )
        except Exception:
            logger.warning(
                "Failed to sync password to Supabase Auth for uuid=%s",
                supabase_auth_uuid,
                exc_info=True,
            )
