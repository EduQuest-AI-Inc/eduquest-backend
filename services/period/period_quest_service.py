from datetime import date, timedelta
from typing import Dict, Any, Optional
from data_access.period_dao import PeriodDAO
from data_access.student_dao import StudentDAO
from data_access.enrollment_dao import EnrollmentDAO
from data_access.period_schedule_dao import PeriodScheduleDAO
from data_access.ltg_conversation_dao import LtgConversationDAO

from bots.provider import get_bot_provider
from services.quest.quest_service import QuestService


def _friday_of_week(start: date, week_num: int) -> date:
    """Return the Friday of the calendar week that starts `(week_num-1)` weeks after `start`."""
    days_until_friday = (4 - start.weekday()) % 7
    first_friday = start + timedelta(days=days_until_friday)
    return first_friday + timedelta(weeks=week_num - 1)


class PeriodQuestService:

    def __init__(self) -> None:
        self.period_dao = PeriodDAO()
        self.student_dao = StudentDAO()
        self.enrollment_dao = EnrollmentDAO()
        self.period_schedule_dao = PeriodScheduleDAO()
        self.ltg_conversation_dao = LtgConversationDAO()
        self.quest_service = QuestService()

    def _assert_enrolled(self, caller_id: str, period_id: str) -> None:
        enrollments = self.enrollment_dao.get_enrollments_by_period(period_id)
        if not any(e['user_id'] == caller_id for e in enrollments):
            raise Exception(f"Student {caller_id} is not enrolled in period {period_id}")

    def start_homework_agent(self, caller_id: str, period_id: str) -> Dict[str, Any]:
        self._assert_enrolled(caller_id, period_id)

        student = self.student_dao.get_student_by_id(caller_id)
        if not student:
            raise Exception("Student not found")

        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise Exception("Period not found")

        period_schedule = self.period_schedule_dao.get_by_period_id(period_id)
        if not period_schedule:
            raise Exception("No period schedule found. Teacher must generate a schedule first.")

        quest_enabled_weeks = period_schedule.quest_enabled_weeks or []
        if not quest_enabled_weeks:
            raise Exception("No quest weeks enabled by teacher. Teacher must select which weeks have quests.")

        schedule_json = period_schedule.schedule_json or {}
        schedule_weeks = schedule_json.get("weeks", [])
        if not schedule_weeks:
            raise Exception("Period schedule has no weeks data. Teacher must generate a schedule.")

        period_start_date: Optional[date] = None
        raw_start = period.get("start_date")
        if raw_start:
            try:
                period_start_date = date.fromisoformat(raw_start)
            except ValueError:
                pass

        schedule_quests = []
        for week_data in schedule_weeks:
            week_num = week_data.get("week_number")
            if week_num in quest_enabled_weeks:
                lessons = week_data.get("lessons", [])
                skills = week_data.get("skills", [])
                quest_name = f"Week {week_num}: " + "; ".join(lessons[:3]) if lessons else f"Week {week_num} Quest"
                quest_skills = "; ".join(skills) if skills else "Practice skills from this week"
                quest_entry: Dict[str, Any] = {"Name": quest_name, "Skills": quest_skills, "Week": week_num}
                if period_start_date is not None:
                    quest_entry["DueDate"] = _friday_of_week(period_start_date, week_num).isoformat()
                schedule_quests.append(quest_entry)

        if not schedule_quests:
            raise Exception("No quests could be built from enabled weeks. Check period schedule data.")

        ltg_conv_id = self.ltg_conversation_dao.get_conversation_id(caller_id, period_id)
        if not ltg_conv_id:
            raise Exception(
                "No LTG conversation found for this period. "
                "Student must complete the Long-Term Goal conversation before generating quests."
            )

        ltg_response_id = self.ltg_conversation_dao.get_last_response_id(caller_id, period_id)

        homework_agent = get_bot_provider().create_hw_agent(student, period, schedule_quests, previous_response_id=ltg_response_id)
        homework = homework_agent.run()

        homework_dict = self._normalize_homework(homework)
        schedule_dict = {"list_of_quests": schedule_quests}

        save_result = self.quest_service.update_quests_preserving_completed_data(
            schedule_dict, homework_dict, caller_id, period_id
        )

        return {
            "homework": homework_dict,
            "message": f"Homework generated successfully for {len(schedule_quests)} quest weeks",
            "saved_quests": save_result,
            "quest_weeks": quest_enabled_weeks,
        }

    def update_quests_with_recommended_change(
        self, caller_id: str, caller_role: str, period_id: str, recommended_change: str
    ) -> Dict[str, Any]:
        self._assert_enrolled(caller_id, period_id)

        student = self.student_dao.get_student_by_id(caller_id)
        if not student:
            raise Exception(f"Student not found: {caller_id}")

        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise Exception("Period not found")

        existing_quests = self.quest_service.get_quests_for_student_and_period(caller_id, period_id)
        if not existing_quests:
            raise Exception("No existing quests found. Cannot update without existing quest structure.")

        incomplete_quests = [
            {"Name": q.get('description', ''), "Skills": q.get('skills', ''), "Week": q.get('week', 1)}
            for q in existing_quests
            if q.get('grade') is None and q.get('status') != 'completed'
        ]

        if not incomplete_quests:
            return {
                "message": "No incomplete quests to update - all quests are completed or graded",
                "recommended_change": recommended_change,
                "affected_quests": 0,
                "preserved_quests": len(existing_quests),
                "updated_quests": 0,
                "total_quests": len(existing_quests),
            }

        ltg_response_id = self.ltg_conversation_dao.get_last_response_id(caller_id, period_id)
        student_with_context = {**student, 'recommended_change': recommended_change}

        homework_agent = get_bot_provider().create_hw_agent(student_with_context, period, incomplete_quests, previous_response_id=ltg_response_id)
        homework = homework_agent.run()
        homework_dict = self._normalize_homework(homework)

        update_result = self.quest_service.update_quests_preserving_completed_data(
            {"list_of_quests": incomplete_quests}, homework_dict, caller_id, period_id
        )

        affected_weeks = [q.get("Week") for q in incomplete_quests]
        return {
            "message": f"Successfully updated {len(incomplete_quests)} incomplete quests based on recommended changes",
            "recommended_change": recommended_change,
            "affected_weeks": affected_weeks,
            "quest_update_details": update_result,
            "affected_quests": len(incomplete_quests),
            "preserved_quests": len(existing_quests) - len(incomplete_quests),
            "updated_quests": len(incomplete_quests),
            "total_quests": len(existing_quests),
        }

    @staticmethod
    def _normalize_homework(homework) -> Dict[str, Any]:
        if isinstance(homework, list):
            quests = []
            for q in homework:
                if hasattr(q, 'model_dump'):
                    quests.append(q.model_dump())
                elif isinstance(q, dict):
                    quests.append(q)
                else:
                    quests.append({
                        "Name": getattr(q, 'Name', ''),
                        "Skills": getattr(q, 'Skills', ''),
                        "Week": getattr(q, 'Week', 1),
                        "instructions": getattr(q, 'instructions', ''),
                        "rubric": getattr(q, 'rubric', {}),
                    })
            return {"list_of_quests": quests}
        if hasattr(homework, 'model_dump'):
            return homework.model_dump()
        return homework if isinstance(homework, dict) else {}
