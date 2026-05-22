import logging

logger = logging.getLogger(__name__)


class AccountDeletionService:
    def __init__(
        self,
        user_dao=None,
        membership_dao=None,
        student_dao=None,
        parent_dao=None,
        supabase_auth_service=None,
        stripe_service=None,
    ) -> None:
        self._user_dao = user_dao
        self._membership_dao = membership_dao
        self._student_dao = student_dao
        self._parent_dao = parent_dao
        self._supabase_auth_service = supabase_auth_service
        self._stripe_service = stripe_service

    # ── lazy getters ──────────────────────────────────────────────────────────

    def _get_user_dao(self):
        if self._user_dao is None:
            from data_access.user_dao import UserDAO
            self._user_dao = UserDAO()
        return self._user_dao

    def _get_membership_dao(self):
        if self._membership_dao is None:
            from data_access.membership_dao import MembershipDAO
            self._membership_dao = MembershipDAO()
        return self._membership_dao

    def _get_student_dao(self):
        if self._student_dao is None:
            from data_access.student_dao import StudentDAO
            self._student_dao = StudentDAO()
        return self._student_dao

    def _get_parent_dao(self):
        if self._parent_dao is None:
            from data_access.parent_dao import ParentDAO
            self._parent_dao = ParentDAO()
        return self._parent_dao

    def _get_supabase_auth_service(self):
        if self._supabase_auth_service is None:
            from services.auth.supabase_auth_service import SupabaseAuthService
            self._supabase_auth_service = SupabaseAuthService()
        return self._supabase_auth_service

    # ── main ──────────────────────────────────────────────────────────────────

    def delete_account(self, user_id: str, role: str) -> None:
        """
        Delete a user account. Steps that must happen before the DB row is removed:
        1. Cancel Stripe subscription (teacher/parent with active subscription).
        2. Delete membership row explicitly (not cascaded — we own the Stripe lifecycle).
        3. If parent: null out created_by_parent_id on child student rows.
        4. If parent: remove self from linked_student_ids on other parent rows.
        5. Delete Supabase Auth user (soft-delete; wrap in try/except).
        6. Delete user row — DB cascades handle all owned data.
        """
        user = self._get_user_dao().get_by_id(user_id)
        if not user:
            from exceptions.not_found_error import NotFoundError
            raise NotFoundError(f"User {user_id} not found")

        # Step 1 & 2 — billing cleanup for teacher/parent
        if role in ("teacher", "parent"):
            membership = self._get_membership_dao().get_by_user_id(user_id)
            if membership and membership.get("stripe_subscription_id"):
                try:
                    from integrations.stripe_service import cancel_subscription_immediately
                    cancel_subscription_immediately(membership["stripe_subscription_id"])
                except Exception:
                    logger.warning(
                        "Stripe subscription cancellation failed for user_id=%s; continuing deletion",
                        user_id,
                        exc_info=True,
                    )
            self._get_membership_dao().delete(user_id)

        # Step 3 & 4 — parent link cleanup
        if role == "parent":
            self._get_student_dao().nullify_created_by_parent(user_id)
            self._get_parent_dao().remove_student_link(user_id)

        # Step 5 — remove from Supabase Auth
        supabase_auth_id = user.get("supabase_auth_id")
        if supabase_auth_id:
            try:
                self._get_supabase_auth_service().delete_user(supabase_auth_id)
            except Exception:
                logger.warning(
                    "Supabase Auth deletion failed for user_id=%s uuid=%s; continuing deletion",
                    user_id,
                    supabase_auth_id,
                    exc_info=True,
                )

        # Step 6 — delete user row; DB cascades remove all owned data
        self._get_user_dao().delete(user_id)
