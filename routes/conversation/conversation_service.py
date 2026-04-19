"""
Conversation service — orchestrates profile gathering, grading, and
teacher-feedback flows by delegating to specialised agent services.
"""
import logging
import uuid
import os
import json
import tempfile

logger = logging.getLogger(__name__)

from dotenv import load_dotenv

if os.getenv('USE_SUPABASE', 'false').lower() == 'true':
    from data_access.supabase.session_dao import SessionDAO
    from data_access.supabase.period_dao import PeriodDAO
    from data_access.supabase.student_dao import StudentDAO
    from data_access.supabase.conversation_dao import ConversationDAO
    from data_access.supabase.teacher_dao import TeacherDAO
else:
    from data_access.session_dao import SessionDAO
    from data_access.period_dao import PeriodDAO
    from data_access.student_dao import StudentDAO
    from data_access.conversation_dao import ConversationDAO
    from data_access.teacher_dao import TeacherDAO
from models.conversation import Conversation
from services.s3_service import upload_file_to_s3

from routes.conversation.profile_service import (
    initiate_profile_conversation,
    continue_profile_conversation,
)
from routes.conversation.grading_service import grade_student_submission
from routes.auth_utils import require_auth
from routes.conversation.teacher_feedback_service import (
    initiate_teacher_feedback,
    continue_teacher_feedback,
)

load_dotenv()


class ConversationService:
    def __init__(self):
        self.session_dao = SessionDAO()
        self.student_dao = StudentDAO()
        self.conversation_dao = ConversationDAO()
        self.teacher_dao = TeacherDAO()
        self.period_dao = PeriodDAO()

    # ------------------------------------------------------------------
    # Profile assistant
    # ------------------------------------------------------------------

    def start_profile_assistant(self, auth_token: str):
        user_id = require_auth(self.session_dao, auth_token, ["student"])

        student = self.student_dao.get_student_by_id(user_id)
        if not student:
            raise Exception("Student not found")

        result = initiate_profile_conversation(student)

        response_id = result.get("response_id")
        if not response_id:
            raise Exception("Failed to obtain response_id from profile agent")

        conversation_id = str(uuid.uuid4())
        self.conversation_dao.add_conversation(Conversation(
            conversation_id=conversation_id,
            user_id=user_id,
            role="student",
            conversation_type="profile",
            last_response_id=response_id,
        ))

        return {
            "conversation_id": conversation_id,
            "response": result.get("response"),
        }

    def continue_profile_assistant(self, auth_token, conversation_type, conversation_id, message):
        user_id = require_auth(self.session_dao, auth_token, ["student"])

        conversation = self.conversation_dao.get_conversation_by_id_user_type(
            conversation_id, user_id, conversation_type
        )
        if not conversation:
            raise Exception("Conversation not found")

        last_response_id = conversation.get("last_response_id")
        result = continue_profile_conversation(last_response_id, message)

        new_response_id = result.get("response_id")
        if new_response_id:
            self.conversation_dao.update_conversation(
                conversation_id, {"last_response_id": new_response_id}
            )

        if result.get("profile_complete") and result.get("profile"):
            self.student_dao.update_student(user_id, result["profile"])

        return {
            "response": result["response"],
            "profile_complete": result.get("profile_complete", False),
        }

    # ------------------------------------------------------------------
    # Update assistant — student grading + teacher feedback
    # ------------------------------------------------------------------

    def start_update_assistant(
        self,
        auth_token: str,
        quests_file: str,
        is_instructor: bool,
        week: int = None,
        submission_file: str = None,
        student_id: str = None,
        period_id: str = None,
        individual_quest_id: str = None,
    ):
        sessions = self.session_dao.get_sessions_by_auth_token(auth_token)
        if not sessions:
            raise Exception("Invalid auth token")

        session = sessions[0]
        user_id = session.get("user_id")
        role = session.get("role")
        if not user_id or not role:
            raise Exception("Session missing user_id or role")

        user = (
            self.teacher_dao.get_teacher_by_id(user_id)
            if role == "teacher"
            else self.student_dao.get_student_by_id(user_id)
        )
        if not user:
            raise Exception(f"{role.capitalize()} not found")

        # Resolve period_id
        if is_instructor:
            if not period_id:
                raise Exception("period_id is required for instructors")
        else:
            if not quests_file:
                raise Exception("quests_file is required for students")
            try:
                quests_data = json.loads(quests_file)
                if not quests_data or not isinstance(quests_data, list):
                    raise Exception("Invalid quests data format")
                period_id = quests_data[0].get("period_id")
                if not period_id:
                    raise Exception("No period_id found in quest data")
            except json.JSONDecodeError as e:
                raise Exception(f"Failed to parse quests JSON: {e}")

        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise Exception(f"Period with id {period_id} not found")

        # ----- Teacher path: multi-turn feedback via TeacherFeedbackAgent -----
        if is_instructor:
            if not student_id:
                raise Exception("Instructor must provide a student_id to fetch quests")
            from routes.quest.quest_service import QuestService
            quests_data = QuestService().get_individual_quests_for_student(student_id)

            target_student = self.student_dao.get_student_by_id(student_id)
            if not target_student:
                raise Exception("Target student not found")

            quests_summary = json.dumps(quests_data, indent=2, default=str)
            result = initiate_teacher_feedback(
                student=target_student,
                quests_summary=quests_summary,
            )

            conversation_id = result.get("conversation_id")
            if conversation_id:
                self.conversation_dao.add_conversation(Conversation(
                    conversation_id=conversation_id,
                    user_id=student_id,
                    role=role,
                    conversation_type="update",
                    period_id=period_id,
                ))

            raw_response = result.get("response", "")
            suggested_change = result.get("suggested_change")
            if suggested_change and period_id:
                self._apply_quest_change(auth_token, student_id, period_id, suggested_change)

            return {
                "conversation_id": conversation_id,
                "response": raw_response,
            }

        # ----- Student path: one-shot grading via GradingOrchestrator -----
        quests_data = json.loads(quests_file)
        quest_data = quests_data[0] if quests_data else {}

        # Upload submission to S3
        s3_key = None
        if submission_file and period_id and student_id and individual_quest_id:
            import time
            timestamp = int(time.time())
            filename = f"{timestamp}_{os.path.basename(submission_file)}"
            folder = f"periods/{period_id}/students/{student_id}/{individual_quest_id}"
            s3_key = upload_file_to_s3(submission_file, filename=filename, folder=folder)

        grading_result = grade_student_submission(
            quest_data=quest_data,
            submission_path=submission_file,
        )

        grade = grading_result.get("grade")
        overall_score = grading_result.get("overall_score")
        feedback = grading_result.get("feedback")
        change = grading_result.get("change")
        recommended_change = grading_result.get("recommended_change")
        raw_response = grading_result.get("response", "")

        # PRIORITY 1: persist grade + feedback
        if week and student_id:
            self._save_grade(
                student_id, week, period_id, individual_quest_id,
                grade, overall_score, feedback,
            )

        # PRIORITY 2: apply recommended quest changes
        if change and recommended_change and period_id:
            self._apply_quest_change(auth_token, student_id or user_id, period_id, recommended_change)

        # Save a conversation record for auditing
        conversation_id = str(uuid.uuid4())
        self.conversation_dao.add_conversation(Conversation(
            conversation_id=conversation_id,
            user_id=student_id or user_id,
            role=role,
            conversation_type="update",
            period_id=period_id,
        ))

        return {
            "conversation_id": conversation_id,
            "response": raw_response,
            **({"s3_key": s3_key} if s3_key else {}),
        }

    def continue_update_assistant(
        self,
        auth_token: str,
        conversation_id: str,
        message: str,
        student_id: str = None,
    ):
        sessions = self.session_dao.get_sessions_by_auth_token(auth_token)
        if not sessions:
            raise Exception("Invalid auth token")
        user_id = sessions[0]["user_id"]
        role = sessions[0].get("role", "student")

        target_user_id = student_id if (role == "teacher" and student_id) else user_id

        conversation = self.conversation_dao.get_conversation_by_id_user_type(
            conversation_id, target_user_id, "update"
        )
        if not conversation:
            raise Exception("Conversation not found")

        period_id = conversation.get("period_id")

        result = continue_teacher_feedback(conversation_id, message)

        suggested_change = result.get("suggested_change")
        if suggested_change and period_id:
            self._apply_quest_change(auth_token, target_user_id, period_id, suggested_change)

        return {"response": result.get("response", "")}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _save_grade(
        self, student_id, week, period_id, individual_quest_id,
        grade, overall_score, feedback,
    ):
        """Persist grading results to the individual quest record."""
        try:
            grade_data = {
                "detailed_grade": grade,
                "overall_score": overall_score,
            }
            import os as _os
            if _os.getenv('USE_SUPABASE', 'false').lower() == 'true':
                from data_access.supabase.individual_quest_dao import IndividualQuestDAO
            else:
                from data_access.individual_quest_dao import IndividualQuestDAO
            quest_dao = IndividualQuestDAO()

            if individual_quest_id:
                quest_dao.update_quest_grade_and_feedback(
                    individual_quest_id, json.dumps(grade_data), feedback
                )
                logger.info("Saved grade %s for quest %s", overall_score, individual_quest_id)
                return

            from routes.quest.quest_service import QuestService
            individual_quests = QuestService().get_individual_quests_for_student(student_id)
            target_quest = None
            for quest in individual_quests:
                if period_id and quest.get("week") == week and quest.get("period_id") == period_id:
                    target_quest = quest
                    break
            if not target_quest:
                for quest in individual_quests:
                    if quest.get("week") == week:
                        target_quest = quest
                        break
            if target_quest:
                quest_dao.update_quest_grade_and_feedback(
                    target_quest["individual_quest_id"],
                    json.dumps(grade_data),
                    feedback,
                )
                logger.info("Saved grade %s for quest %s", overall_score, target_quest['individual_quest_id'])
            else:
                logger.warning("Could not find quest for student %s, week %s", student_id, week)
        except Exception as e:
            logger.error("Error saving grade: %s", e, exc_info=True)

    def _apply_quest_change(self, auth_token, student_id, period_id, recommended_change):
        """Delegate recommended changes to PeriodService."""
        try:
            from routes.period.period_service import PeriodService
            period_service = PeriodService()
            quest_update_result = period_service.update_quests_with_recommended_change(
                auth_token, student_id, period_id, recommended_change,
            )
            logger.info("Quest update: %s", quest_update_result.get('message', ''))
        except Exception as e:
            logger.error("Error applying quest change: %s", e, exc_info=True)
