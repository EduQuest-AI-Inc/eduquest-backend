from datetime import datetime, timezone
from typing import Optional

from data_access.base_dao import SupabaseBaseDAO
from models.student_skill_mastery import MASTERY_CUTOFF, StudentSkillMastery


class StudentSkillMasteryDAO(SupabaseBaseDAO):
    def __init__(self, jwt: str | None = None) -> None:
        super().__init__('student_skill_mastery', jwt=jwt)

    def get_for_student(self, student_id: str, period_id: str) -> list[StudentSkillMastery]:
        response = self._execute(
            self._table()
            .select('*')
            .eq('student_id', student_id)
            .eq('period_id', period_id)
        )
        rows = self._rows(response.data)
        return [StudentSkillMastery.from_item(r) for r in rows]

    def get_one(
        self, student_id: str, period_id: str, skill_name: str
    ) -> Optional[StudentSkillMastery]:
        response = self._execute(
            self._table()
            .select('*')
            .eq('student_id', student_id)
            .eq('period_id', period_id)
            .eq('skill_name', skill_name)
            .maybe_single()
        )
        row = self._row(response)
        return StudentSkillMastery.from_item(row) if row else None

    def bulk_upsert(self, rows: list[StudentSkillMastery]) -> None:
        if not rows:
            return
        self._execute(self._table().upsert([r.to_item() for r in rows]))

    def upsert_score(
        self,
        student_id: str,
        period_id: str,
        skill_name: str,
        score: float,
        threshold: float = MASTERY_CUTOFF,
    ) -> StudentSkillMastery:
        row = StudentSkillMastery(
            student_id=student_id,
            period_id=period_id,
            skill_name=skill_name,
            score=score,
            mastered=score >= threshold,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._upsert(row.to_item())
        return row

    def delete_for_student_period(self, student_id: str, period_id: str) -> None:
        self._delete({'student_id': student_id, 'period_id': period_id})
