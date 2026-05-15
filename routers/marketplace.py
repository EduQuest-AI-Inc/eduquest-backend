from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from routers.deps import AuthPayload, get_auth, require_active_membership
from services.marketplace.marketplace_service import MarketplaceService

router = APIRouter()
_marketplace_service = MarketplaceService()


class PublishRequest(BaseModel):
    period_id: str
    tags: List[str] = []


@router.get("")
def list_marketplace(
    grade_level: Optional[str] = None,
    tags: Optional[str] = None,  # comma-separated
    limit: int = 20,
    offset: int = 0,
    auth: AuthPayload = Depends(get_auth),
):
    parsed_tags = [t.strip() for t in tags.split(",")] if tags else None
    return _marketplace_service.list_marketplace(
        grade_level=grade_level, tags=parsed_tags, limit=limit, offset=offset
    )


@router.get("/{listing_id}")
def get_listing(
    listing_id: str,
    auth: AuthPayload = Depends(get_auth),
):
    return _marketplace_service.get_listing(listing_id)


@router.post("")
def publish_class(
    body: PublishRequest,
    auth: AuthPayload = Depends(require_active_membership),
):
    return _marketplace_service.publish(body.period_id, auth.sub, body.tags)


@router.delete("/{listing_id}")
def unpublish_class(
    listing_id: str,
    auth: AuthPayload = Depends(require_active_membership),
):
    _marketplace_service.unpublish(listing_id, auth.sub)
    return {"message": "Listing unpublished"}


@router.post("/{listing_id}/fork")
def fork_class(
    listing_id: str,
    auth: AuthPayload = Depends(require_active_membership),
):
    forked_period = _marketplace_service.fork(listing_id, auth.sub)
    return {"message": "Class forked successfully", "period": forked_period}
