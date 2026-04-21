import os
from typing import Dict, Any
from routes.auth_utils import require_auth

if os.getenv('USE_SUPABASE', 'false').lower() == 'true':
    from data_access.supabase.period_dao import PeriodDAO
    from data_access.supabase.session_dao import SessionDAO
    from data_access.supabase.student_dao import StudentDAO
    from data_access.supabase.enrollment_dao import EnrollmentDAO
    from data_access.supabase.period_schedule_dao import PeriodScheduleDAO
    from data_access.supabase.ltg_conversation_dao import LtgConversationDAO
else:
    from data_access.period_dao import PeriodDAO
    from data_access.session_dao import SessionDAO
    from data_access.student_dao import StudentDAO
    from data_access.enrollment_dao import EnrollmentDAO
    from data_access.period_schedule_dao import PeriodScheduleDAO

from bots.agent import HWAgent
from routes.quest.quest_service import QuestService


class PeriodQuestService:

    def __init__(self):
        self.period_dao = PeriodDAO()
        self.session_dao = SessionDAO()
        self.student_dao = StudentDAO()
        self.enrollment_dao = EnrollmentDAO()
        self.period_schedule_dao = PeriodScheduleDAO()
        self.ltg_conversation_dao = LtgConversationDAO()
        self.quest_service = QuestService()

    def _assert_enrolled(self, user_id: str, period_id: str) -> None:
        enrollments = self.enrollment_dao.get_enrollments_by_period(period_id)
        if not any(e['user_id'] == user_id for e in enrollments):
            raise Exception(f"Student {user_id} is not enrolled in period {period_id}")

    def start_homework_agent(self, auth_token: str, user_id: str, period_id: str) -> Dict[str, Any]:
        sessions = self.session_dao.get_sessions_by_auth_token(auth_token)
        if not sessions:
            raise Exception("Invalid auth token")
        caller_id = sessions[0]["user_id"]
        caller_role = sessions[0].get("role", "student")

        if caller_role not in ("teacher", "parent") and caller_id != user_id:
            raise Exception("Unauthorized: caller must be the target student, a teacher, or a parent")

        self._assert_enrolled(user_id, period_id)

        student = self.student_dao.get_student_by_id(user_id)
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

        schedule_quests = []
        for week_data in schedule_weeks:
            week_num = week_data.get("week_number")
            if week_num in quest_enabled_weeks:
                lessons = week_data.get("lessons", [])
                skills = week_data.get("skills", [])
                quest_name = f"Week {week_num}: " + "; ".join(lessons[:3]) if lessons else f"Week {week_num} Quest"
                quest_skills = "; ".join(skills) if skills else "Practice skills from this week"
                schedule_quests.append({"Name": quest_name, "Skills": quest_skills, "Week": week_num})

        if not schedule_quests:
            raise Exception("No quests could be built from enabled weeks. Check period schedule data.")

        ltg_conv_id = self.ltg_conversation_dao.get_conversation_id(user_id, period_id)
        if not ltg_conv_id:
            raise Exception(
                "No LTG conversation found for this period. "
                "Student must complete the Long-Term Goal conversation before generating quests."
            )

        ltg_response_id = self.ltg_conversation_dao.get_last_response_id(user_id, period_id)

        existing_weekly_quest = self.quest_service.get_weekly_quests_for_student(user_id, period_id)
        if not existing_weekly_quest:
            schedule_dict = {"list_of_quests": schedule_quests}
            self.quest_service.save_schedule_to_weekly_quests(schedule_dict, user_id, period_id)

        homework_agent = HWAgent(student, period, schedule_quests, previous_response_id=ltg_response_id)
        homework = homework_agent.run()

        homework_dict = self._normalize_homework(homework)

        save_result = self.quest_service.update_weekly_quest_with_homework(homework_dict, user_id, period_id)

        individual_quests = self.quest_service.get_individual_quests_for_student_and_period(user_id, period_id)
        if not individual_quests:
            self.quest_service.create_individual_quests_from_homework(homework_dict, user_id, period_id)

        return {
            "homework": homework_dict,
            "message": f"Homework generated successfully for {len(schedule_quests)} quest weeks",
            "saved_quests": save_result,
            "quest_weeks": quest_enabled_weeks,
        }

    def update_quests_with_recommended_change(
        self, auth_token: str, user_id: str, period_id: str, recommended_change: str
    ) -> Dict[str, Any]:
        sessions = self.session_dao.get_sessions_by_auth_token(auth_token)
        if not sessions:
            raise Exception("Invalid auth token")
        caller_id = sessions[0]["user_id"]
        caller_role = sessions[0].get("role", "student")

        if caller_role not in ("teacher", "parent") and caller_id != user_id:
            raise Exception("Unauthorized: caller must be the target student, a teacher, or a parent")

        self._assert_enrolled(user_id, period_id)

        student = self.student_dao.get_student_by_id(user_id)
        if not student:
            raise Exception(f"Student not found: {user_id}")

        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise Exception("Period not found")

        existing_quests = self.quest_service.get_individual_quests_for_student_and_period(user_id, period_id)
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

        ltg_response_id = self.ltg_conversation_dao.get_last_response_id(user_id, period_id)
        student_with_context = {**student, 'recommended_change': recommended_change}

        homework_agent = HWAgent(student_with_context, period, incomplete_quests, previous_response_id=ltg_response_id)
        homework = homework_agent.run()
        homework_dict = self._normalize_homework(homework)

        update_result = self.quest_service.update_weekly_quest_with_homework(homework_dict, user_id, period_id)

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
