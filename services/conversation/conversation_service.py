"""
Conversation service — orchestrates profile gathering, grading, and
teacher-feedback flows by delegating to specialised agent services.
"""
import asyncio
import json
import logging
import os
import time
import uuid
from typing import Optional

from dotenv import load_dotenv

from data_access.conversation_dao import ConversationDAO
from data_access.period_dao import PeriodDAO
from data_access.quest_dao import QuestDAO
from data_access.student_dao import StudentDAO
from data_access.teacher_dao import TeacherDAO
from exceptions.not_found_error import NotFoundError
from exceptions.validation_error import ValidationError
from integrations.s3_service import upload_file_to_s3
from bots.protocol import BotProviderProtocol
from models.conversation import Conversation
from services.conversation.grading_service import grade_student_submission
from services.conversation.profile_service import ProfileConversationService
from services.tracking import Events, track_event
from services.conversation.teacher_feedback_service import (
    continue_teacher_feedback,
    initiate_teacher_feedback,
)
from services.period.period_service import PeriodService
from services.quest.quest_retrieval_service import QuestRetrievalService

load_dotenv()

logger = logging.getLogger(__name__)


class ConversationService:
    def __init__(
        self,
        *,
        bot_provider: BotProviderProtocol,
        jwt: str | None = None,
        period_service=None,
        conversation_dao=None,
        student_dao=None,
        teacher_dao=None,
        period_dao=None,
        admin_quest_retrieval_svc=None,
        quest_dao=None,
    ) -> None:
        self._bot_provider = bot_provider
        self._jwt = jwt
        self.student_dao = student_dao or StudentDAO(jwt=jwt)
        self.conversation_dao = conversation_dao or ConversationDAO()  # RLS: INSERT/UPDATE/DELETE is FastAPI-only; must use admin client
        self.teacher_dao = teacher_dao or TeacherDAO(jwt=jwt)
        self.period_dao = period_dao or PeriodDAO(jwt=jwt)
        self._admin_quest_retrieval_svc = admin_quest_retrieval_svc or QuestRetrievalService()  # admin client — teacher paths read student quests
        self._quest_dao = quest_dao or QuestDAO()
        self._period_service = period_service or PeriodService(bot_provider=bot_provider)

    # ------------------------------------------------------------------
    # Profile assistant
    # ------------------------------------------------------------------

    async def start_profile_assistant(self, user_id: str):
        student = await asyncio.to_thread(self.student_dao.get_student_by_id, user_id)
        if not student:
            raise NotFoundError("Student not found")

        service = ProfileConversationService(bot_provider=self._bot_provider)
        result = await service.initiate(student)

        response_id = result.get("response_id")
        if not response_id:
            raise ValidationError("Profile agent did not return a response_id")

        conversation_id = str(uuid.uuid4())
        await asyncio.to_thread(
            self.conversation_dao.add_conversation,
            Conversation(
                conversation_id=conversation_id,
                user_id=user_id,
                conversation_type="profile",
                last_response_id=response_id,
            ),
        )

        return {
            "conversation_id": conversation_id,
            "response": result.get("response"),
        }

    async def continue_profile_assistant(self, user_id: str, conversation_type, conversation_id, message):
        conversation = await asyncio.to_thread(
            self.conversation_dao.get_conversation_by_id_user_type,
            conversation_id, user_id, conversation_type,
        )
        if not conversation:
            raise NotFoundError("Conversation not found")

        last_response_id = conversation.get("last_response_id")
        if not isinstance(last_response_id, str):
            raise NotFoundError("Conversation has no response ID")

        service = ProfileConversationService(previous_response_id=last_response_id, bot_provider=self._bot_provider)
        result = await service.continue_conversation(message)

        new_response_id = result.get("response_id")
        if new_response_id:
            await asyncio.to_thread(
                self.conversation_dao.update_conversation,
                conversation_id, {"last_response_id": new_response_id},
            )

        if result.get("profile_complete") and result.get("profile"):
            await asyncio.to_thread(self.student_dao.update_student, user_id, result["profile"])

        return {
            "response": result["response"],
            "profile_complete": result.get("profile_complete", False),
        }

    # ------------------------------------------------------------------
    # Update assistant — student grading + teacher feedback
    # ------------------------------------------------------------------

    def start_update_assistant(
        self,
        quests_file: str,
        is_instructor: bool,
        caller_user_id: str,
        caller_role: str,
        week: Optional[int] = None,
        submission_file: Optional[str] = None,
        user_id: Optional[str] = None,
        period_id: Optional[str] = None,
        individual_quest_id: Optional[str] = None,
    ):
        user_id = caller_user_id

        user = (
            self.teacher_dao.get_teacher_by_id(user_id)
            if is_instructor
            else self.student_dao.get_student_by_id(user_id)
        )
        if not user:
            raise NotFoundError(f"{'Instructor' if is_instructor else 'Student'} not found")

        # Resolve period_id
        if is_instructor:
            if not period_id:
                raise ValidationError("period_id is required for instructors")
        else:
            if not quests_file:
                raise ValidationError("quests_file is required for students")
            try:
                quests_data = json.loads(quests_file)
                if not quests_data or not isinstance(quests_data, list):
                    raise ValidationError("Invalid quests data format")
                period_id = quests_data[0].get("period_id")
                if not period_id:
                    raise ValidationError("No period_id found in quest data")
            except json.JSONDecodeError as e:
                raise ValidationError(f"Failed to parse quests JSON: {e}")

        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise NotFoundError(f"Period with id {period_id} not found")

        # ----- Teacher path: multi-turn feedback via TeacherFeedbackAgent -----
        if is_instructor:
            if not user_id:
                raise ValidationError("Instructor must provide a user_id to fetch quests")
            quests_data = self._admin_quest_retrieval_svc.get_quests_for_student(user_id)

            target_student = self.student_dao.get_student_by_id(user_id)
            if not target_student:
                raise NotFoundError("Target student not found")

            quests_summary = json.dumps(quests_data, indent=2, default=str)
            result = initiate_teacher_feedback(
                student=target_student,
                quests_summary=quests_summary,
                bot_provider=self._bot_provider,
            )

            conversation_id = result.get("conversation_id")
            if conversation_id:
                self.conversation_dao.add_conversation(Conversation(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    conversation_type="update",
                    period_id=period_id,
                ))

            raw_response = result.get("response", "")
            suggested_change = result.get("suggested_change")
            if suggested_change and period_id:
                self._apply_quest_change(caller_user_id, caller_role, period_id, suggested_change)

            return {
                "conversation_id": conversation_id,
                "response": raw_response,
            }

        # ----- Student path: one-shot grading via GradingOrchestrator -----
        quests_data = json.loads(quests_file)
        quest_data = quests_data[0] if quests_data else {}

        # Upload submission to S3 — non-critical audit trail; grading proceeds on failure
        s3_key = None
        if submission_file and period_id and user_id and individual_quest_id:
            timestamp = int(time.time())
            filename = f"{timestamp}_{os.path.basename(submission_file)}"
            folder = f"periods/{period_id}/students/{user_id}/{individual_quest_id}"
            try:
                s3_key = upload_file_to_s3(submission_file, filename=filename, folder=folder)
            except Exception as exc:
                logger.warning(
                    "S3 upload failed for quest submission user=%s quest=%s, continuing without upload: %s",
                    user_id, individual_quest_id, exc, exc_info=True,
                )

        grading_result = grade_student_submission(
            quest_data=quest_data,
            submission_path=submission_file,
            bot_provider=self._bot_provider,
        )

        grade = grading_result.get("grade")
        overall_score = grading_result.get("overall_score")
        feedback = grading_result.get("feedback")
        change = grading_result.get("change")
        recommended_change = grading_result.get("recommended_change")
        raw_response = grading_result.get("response", "")

        # PRIORITY 1: persist grade + feedback
        if week and user_id:
            self._save_grade(
                user_id, week, period_id, individual_quest_id,
                grade, overall_score, feedback,
            )

        # PRIORITY 2: apply recommended quest changes
        if change and recommended_change and period_id:
            self._apply_quest_change(caller_user_id, caller_role, period_id, recommended_change)

        # Save a conversation record for auditing
        conversation_id = str(uuid.uuid4())
        self.conversation_dao.add_conversation(Conversation(
            conversation_id=conversation_id,
            user_id=user_id or "",
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
        user_id: str,
        caller_role: str,
        conversation_id: str,
        message: str,
    ):
        conversation = self.conversation_dao.get_conversation_by_id_user_type(
            conversation_id, user_id, "update"
        )
        if not conversation:
            raise NotFoundError("Conversation not found")

        period_id = conversation.get("period_id")

        result = continue_teacher_feedback(conversation_id, message, bot_provider=self._bot_provider)

        suggested_change = result.get("suggested_change")
        if suggested_change and period_id:
            self._apply_quest_change(user_id, caller_role, period_id, suggested_change)

        return {"response": result.get("response", "")}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _save_grade(
        self, user_id, week, period_id, individual_quest_id,
        grade, overall_score, feedback,
    ) -> None:
        """Persist grading results to the individual quest record."""
        try:
            grade_data = {
                "detailed_grade": grade,
                "overall_score": overall_score,
            }

            if individual_quest_id:
                self._quest_dao.update_quest_grade_and_feedback(individual_quest_id, grade_data, feedback)
                logger.info("Saved grade %s for quest %s", overall_score, individual_quest_id)
                return

            quests = self._admin_quest_retrieval_svc.get_quests_for_student(user_id)
            target_quest = None
            for quest in quests:
                if period_id and quest.get("week") == week and quest.get("period_id") == period_id:
                    target_quest = quest
                    break
            if not target_quest:
                for quest in quests:
                    if quest.get("week") == week:
                        target_quest = quest
                        break
            if target_quest:
                self._quest_dao.update_quest_grade_and_feedback(
                    target_quest["quest_id"],
                    grade_data,
                    feedback,
                )
                logger.info("Saved grade %s for quest %s", overall_score, target_quest['quest_id'])
            else:
                logger.warning("Could not find quest for student %s, week %s", user_id, week)
        except Exception as e:
            logger.error("Error saving grade: %s", e, exc_info=True)
            track_event(
                user_id=user_id,
                event=Events.GRADE_PERSISTENCE_FAILED,
                properties={
                    "period_id": period_id,
                    "week": week,
                    "error_type": type(e).__name__,
                    "no_ad_targeting": True,
                    "student_data": True,
                },
            )

    def _apply_quest_change(self, caller_id: str, caller_role: str, period_id: str, recommended_change: str) -> None:
        """Delegate recommended changes to PeriodService."""
        try:
            quest_update_result = self._period_service.update_quests_with_recommended_change(
                caller_id, caller_role, period_id, recommended_change,
            )
            logger.info("Quest update: %s", quest_update_result.get('message', ''))
        except Exception as e:
            logger.error("Error applying quest change: %s", e, exc_info=True)
            track_event(
                user_id=caller_id,
                event=Events.QUEST_UPDATE_FAILED,
                properties={"period_id": period_id, "error_type": type(e).__name__},
            )
