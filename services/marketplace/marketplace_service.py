import logging
from typing import Any, Optional

from data_access.marketplace_listing_dao import MarketplaceListingDAO
from data_access.period_dao import PeriodDAO
from exceptions.not_found_error import NotFoundError
from exceptions.permission_error import PermissionError
from exceptions.validation_error import ValidationError
from models.marketplace_listing import MarketplaceListing
from services.period.period_management_service import PeriodManagementService

logger = logging.getLogger(__name__)

_SAFE_PERIOD_FIELDS = {
    'period_id', 'name', 'grade_level', 'course_description',
    'start_date', 'end_date', 'status', 'is_summer_quest', 'created_at',
    'forked_from_period_id',
    # intentionally excluded: vector_store_id, file_urls, file_vector_store_ids, owner_id
}


class MarketplaceService:
    def __init__(
        self,
        listing_dao: Optional[MarketplaceListingDAO] = None,
        period_dao: Optional[PeriodDAO] = None,
        period_management_service: Optional[PeriodManagementService] = None,
        jwt: str | None = None,
    ) -> None:
        self.listing_dao = listing_dao or MarketplaceListingDAO(jwt=jwt)
        self.period_dao = period_dao or PeriodDAO(jwt=jwt)
        self._admin_period_dao = PeriodDAO()  # for cross-user period reads in get_listing / fork
        self.period_management_service = period_management_service or PeriodManagementService(jwt=jwt)

    # ── publish ────────────────────────────────────────────────────────────────

    def publish(self, period_id: str, user_id: str, tags: list[str]) -> dict[str, Any]:
        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise NotFoundError("Period not found")
        if period.get('owner_id') != user_id:
            raise PermissionError("Only the class owner can publish to the marketplace")
        if period.get('forked_from_period_id'):
            raise ValidationError("Forked classes cannot be published to the marketplace")
        if period.get('status') not in ('draft', 'approved'):
            raise ValidationError(
                "Only classes with an approved or draft curriculum can be published"
            )
        listing = MarketplaceListing(
            period_id=period_id,
            published_by=user_id,
            tags=tags,
        )
        return self.listing_dao.upsert_published(listing)

    # ── unpublish ──────────────────────────────────────────────────────────────

    def unpublish(self, listing_id: str, user_id: str) -> None:
        listing = self.listing_dao.get_by_id(listing_id)
        if not listing:
            raise NotFoundError("Listing not found")
        if listing.get('published_by') != user_id:
            raise PermissionError("Only the listing owner can unpublish")
        self.listing_dao.update_listing(listing_id, {'is_published': False})

    # ── list ───────────────────────────────────────────────────────────────────

    def list_marketplace(
        self,
        grade_level: Optional[str] = None,
        tags: Optional[list[str]] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return self.listing_dao.get_published(
            grade_level=grade_level, tags=tags, limit=limit, offset=offset
        )

    # ── get single listing ─────────────────────────────────────────────────────

    def get_listing(self, listing_id: str) -> dict[str, Any]:
        listing = self.listing_dao.get_by_id(listing_id)
        if not listing or not listing.get('is_published'):
            raise NotFoundError("Listing not found")
        period = self._admin_period_dao.get_period_by_id(listing['period_id'])
        if not period:
            raise NotFoundError("Associated period not found")
        safe_period = {k: v for k, v in period.items() if k in _SAFE_PERIOD_FIELDS}
        return {**listing, 'period': safe_period}

    # ── fork ───────────────────────────────────────────────────────────────────

    def fork(self, listing_id: str, user_id: str) -> dict[str, Any]:
        listing = self.listing_dao.get_by_id(listing_id)
        if not listing or not listing.get('is_published'):
            raise NotFoundError("Listing not found")

        orig_period_id = listing['period_id']

        # Prevent double-forking the same listing by the same user
        existing_forks = self._admin_period_dao.get_forks_by_period(orig_period_id)
        already_forked = any(f.get('owner_id') == user_id for f in existing_forks)
        if already_forked:
            raise ValidationError("You have already forked this class")

        orig_period = self._admin_period_dao.get_period_by_id(orig_period_id)
        if not orig_period:
            raise NotFoundError("Original class not found")

        new_period_id = self.period_management_service.generate_period_id(
            orig_period.get('name', 'FORK')
        )
        # Ensure uniqueness
        for _ in range(5):
            if not self.period_dao.get_period_by_id(new_period_id):
                break
            new_period_id = self.period_management_service.generate_period_id(
                orig_period.get('name', 'FORK')
            )
        else:
            raise ValidationError("Unable to generate unique period ID for fork")

        logger.info(
            "Forking listing %s for user %s → new period %s",
            listing_id, user_id, new_period_id,
        )
        try:
            self.listing_dao.fork(listing_id, user_id, new_period_id)
        except ValidationError as exc:
            logger.error("Fork RPC failed for listing %s: %s", listing_id, exc, exc_info=True)
            raise ValidationError("Fork failed — please try again") from exc

        forked = self.period_dao.get_period_by_id(new_period_id)
        if not forked:
            raise ValidationError("Fork completed but period could not be retrieved")
        return forked
