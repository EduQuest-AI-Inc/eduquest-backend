from typing import Any

from data_access.base_dao import SupabaseBaseDAO
from models.skill import Skill


class SkillDAO(SupabaseBaseDAO):
    def __init__(self, jwt: str | None = None) -> None:
        super().__init__('skill', jwt=jwt)

    def insert_skill(self, skill: Skill) -> None:
        self._insert(skill.to_item())

    def get_skills_by_period(self, period_id: str) -> list[dict[str, Any]]:
        return self._select_eq('period_id', period_id)

    def update_skill(self, period_id: str, skill_name: str, fields: dict[str, Any]) -> None:
        self._update({'period_id': period_id, 'skill_name': skill_name}, fields)

    def delete_all_for_period(self, period_id: str) -> None:
        self._delete({'period_id': period_id})
