from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from responses.marketplace import (
    ForkResponse,
    MarketplaceListingDetailOut,
    MarketplaceListingOut,
    MessageResponse,
)

from routers.deps import AuthPayload, get_auth, require_active_membership
from services.marketplace.marketplace_service import MarketplaceService

router = APIRouter()


class PublishRequest(BaseModel):
    period_id: str
    tags: List[str] = []


@router.get("", response_model=list[MarketplaceListingOut])
def list_marketplace(
    grade_level: Optional[str] = None,
    tags: Optional[str] = None,  # comma-separated
    limit: int = 20,
    offset: int = 0,
    auth: AuthPayload = Depends(get_auth),
):
    svc = MarketplaceService(jwt=auth.token)
    parsed_tags = [t.strip() for t in tags.split(",")] if tags else None
    return svc.list_marketplace(
        grade_level=grade_level, tags=parsed_tags, limit=limit, offset=offset
    )


@router.get("/{listing_id}", response_model=MarketplaceListingDetailOut)
def get_listing(
    listing_id: str,
    auth: AuthPayload = Depends(get_auth),
):
    svc = MarketplaceService(jwt=auth.token)
    return svc.get_listing(listing_id)


@router.post("", response_model=MarketplaceListingOut)
def publish_class(
    body: PublishRequest,
    auth: AuthPayload = Depends(require_active_membership),
):
    svc = MarketplaceService(jwt=auth.token)
    return svc.publish(body.period_id, auth.sub, body.tags)


@router.delete("/{listing_id}", response_model=MessageResponse)
def unpublish_class(
    listing_id: str,
    auth: AuthPayload = Depends(require_active_membership),
):
    svc = MarketplaceService(jwt=auth.token)
    svc.unpublish(listing_id, auth.sub)
    return {"message": "Listing unpublished"}


@router.post("/{listing_id}/fork", response_model=ForkResponse)
def fork_class(
    listing_id: str,
    auth: AuthPayload = Depends(require_active_membership),
):
    svc = MarketplaceService(jwt=auth.token)
    forked_period = svc.fork(listing_id, auth.sub)
    return {"message": "Class forked successfully", "period": forked_period}
