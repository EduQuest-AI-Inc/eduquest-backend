from typing import Any, Optional

from data_access.base_dao import SupabaseBaseDAO
from data_access.config import get_admin_supabase_client
from models.marketplace_listing import MarketplaceListing


class MarketplaceListingDAO(SupabaseBaseDAO):
    def __init__(self, jwt: str | None = None) -> None:
        super().__init__('marketplace_listing', jwt=jwt)
        self._admin_client = get_admin_supabase_client()

    def insert_listing(self, listing: MarketplaceListing) -> dict[str, Any]:
        return self._insert(listing.to_item())

    def get_by_id(self, listing_id: str) -> Optional[dict[str, Any]]:
        return self._select_by_id('listing_id', listing_id)

    def get_by_period_id(self, period_id: str) -> Optional[dict[str, Any]]:
        rows = self._select_eq('period_id', period_id)
        return rows[0] if rows else None

    def get_published_by_period_id(self, period_id: str) -> Optional[dict[str, Any]]:
        response = self._execute(
            self._admin_client.table('marketplace_listing')
            .select('*')
            .eq('period_id', period_id)
            .eq('is_published', True)
            .maybe_single()
        )
        if response is None or response.data is None:
            return None
        return response.data

    def get_published(
        self,
        grade_level: Optional[str] = None,
        tags: Optional[list[str]] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        query = (
            self._admin_client.table('marketplace_listing')
            .select('*, period(name, grade_level, course_description)')
            .eq('is_published', True)
            .order('created_at', desc=True)
            .range(offset, offset + limit - 1)
        )
        if grade_level:
            # filter via the joined period table
            query = query.eq('period.grade_level', grade_level)
        if tags:
            query = query.contains('tags', tags)
        response = self._execute(query)
        rows = response.data if response.data else []
        # Flatten the nested period join into the listing dict
        result = []
        for row in rows:
            flat = dict(row)
            period_data = flat.pop('period', None) or {}
            flat['period_name'] = period_data.get('name')
            flat['period_grade_level'] = period_data.get('grade_level')
            flat['period_description'] = period_data.get('course_description')
            result.append(flat)
        return result

    def upsert_published(self, listing: MarketplaceListing) -> dict[str, Any]:
        existing = self.get_by_period_id(listing.period_id)
        if existing:
            rows = self._update(
                {'listing_id': existing['listing_id']},
                {'is_published': True, 'tags': listing.tags},
            )
            return rows[0] if rows else existing
        return self.insert_listing(listing)

    def update_listing(self, listing_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        rows = self._update({'listing_id': listing_id}, updates)
        return rows[0] if rows else {}

    def fork(self, listing_id: str, new_owner_id: str, new_period_id: str) -> None:
        """Call the atomic fork_marketplace_listing Postgres RPC."""
        self._rpc('fork_marketplace_listing', {
            'p_listing_id': listing_id,
            'p_new_owner_id': new_owner_id,
            'p_new_period_id': new_period_id,
        })
