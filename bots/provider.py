"""
Bot provider — factory for real and mock bot instances.

Receive BotProviderProtocol via constructor injection or via
routers.deps.get_bot_provider (FastAPI Depends). The canonical provider is
selected once at startup in main.py lifespan and stored in app.state.bot_provider.
"""
from typing import Optional

from bots.protocol import BotProviderProtocol  # noqa: F401 — re-exported for callers


class BotProvider:
    """Returns real bot instances. All imports are lazy to avoid loading the
    OpenAI SDK at module import time when it isn't needed."""

    def create_hw_agent(self, student, period, schedule, conversation_id=None, previous_response_id=None):
        from bots.quests.quest_agent import HWAgent
        return HWAgent(
            student, period, schedule,
            conversation_id=conversation_id,
            previous_response_id=previous_response_id,
        )

    def create_grading_orchestrator(self):
        from bots.grading_agent import GradingOrchestrator
        return GradingOrchestrator()

    def create_curriculum_agent(
        self,
        vector_store_ids: list,
        course_name: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        course_description: Optional[str] = None,
        grade_level: Optional[str] = None,
        research_context: Optional[str] = None,
    ):
        from bots.curriculum.curriculum_agent import CurriculumAgent
        return CurriculumAgent(
            vector_store_ids=vector_store_ids,
            course_name=course_name,
            start_date=start_date,
            end_date=end_date,
            course_description=course_description,
            grade_level=grade_level,
            research_context=research_context,
        )

    def create_profile_agent(self):
        from bots.profile_agent import create_profile_agent
        return create_profile_agent()

    def create_ltg_agent(self, vector_store_id: str, curriculum: dict):
        from bots.ltg_agent import create_ltg_agent
        return create_ltg_agent(vector_store_id, curriculum)

    def create_schedule_agent(self, student, period, schedule, goal_text, previous_response_id=None):
        from bots.quests.ltg_schedule_agent import LTGScheduleAgent
        return LTGScheduleAgent(
            student=student,
            period=period,
            schedule=schedule,
            goal_text=goal_text,
            previous_response_id=previous_response_id,
        )

    def create_teacher_feedback_agent(self):
        from bots.teacher_feedback_agent import create_teacher_feedback_agent
        return create_teacher_feedback_agent()

    def create_pptx_agent(self):
        from bots.slideshow.pptx_agent import PptxAgent
        return PptxAgent()

    async def grade_submission(self, quest_data: dict, submission_text: str) -> dict:
        grading_input = self._build_grading_input(quest_data, submission_text)
        orchestrator = self.create_grading_orchestrator()
        result = await orchestrator.grade_submission(grading_input)
        return self._format_grading_result(result)

    @staticmethod
    def _build_grading_input(quest_data: dict, submission_text: str):
        import json
        from bots.grading_agent import GradingInput
        rubric = quest_data.get("rubric", {})
        if isinstance(rubric, str):
            try:
                rubric = json.loads(rubric)
            except json.JSONDecodeError:
                rubric = {"raw": rubric}
        skills_raw = quest_data.get("skills", "")
        if isinstance(skills_raw, str):
            skills = [s.strip() for s in skills_raw.split(";") if s.strip()]
        elif isinstance(skills_raw, list):
            skills = skills_raw
        else:
            skills = []
        instructions = quest_data.get("instructions", quest_data.get("description", ""))
        if isinstance(instructions, list):
            instructions = "\n".join(
                f"Step {s['step']}: {s['text']}" for s in instructions if isinstance(s, dict)
            )
        return GradingInput(
            submission=submission_text,
            rubric=rubric,
            skills=skills,
            instructions=instructions,
        )

    @staticmethod
    def _format_grading_result(result) -> dict:
        from typing import Optional
        recommended_change_text: Optional[str] = None
        if result.recommended_changes:
            recommended_change_text = "; ".join(result.recommended_changes)
        return {
            "grade": result.skill_mastery,
            "overall_score": result.numerical_grade,
            "feedback": result.feedback,
            "change": result.homework_changes_recommended,
            "recommended_change": recommended_change_text,
            "response": (
                f"Grade: {result.numerical_grade}\n"
                f"Feedback: {result.feedback}\n"
                f"Changes recommended: {result.homework_changes_recommended}"
            ),
        }

    async def run_conversation(self, agent, message: str, **kwargs):
        from agents import Runner
        return await Runner.run(agent, message, **kwargs)

    def make_conversations_session(self, conversation_id=None):
        from agents import OpenAIConversationsSession
        if conversation_id:
            return OpenAIConversationsSession(conversation_id=conversation_id)
        return OpenAIConversationsSession()

    @property
    def runner(self):
        from agents import Runner
        return Runner


class MockBotProvider(BotProvider):
    """Returns fast mock implementations. Real Agent objects are still created
    for conversation bots (they're cheap — no network calls) so MockRunner can
    read agent.output_type to dispatch the right response type."""

    def create_hw_agent(self, student, period, schedule, conversation_id=None, previous_response_id=None):
        from bots._mocks import MockHWAgent
        return MockHWAgent(
            student, period, schedule,
            conversation_id=conversation_id,
            previous_response_id=previous_response_id,
        )

    def create_grading_orchestrator(self):
        from bots._mocks import MockGradingOrchestrator
        return MockGradingOrchestrator()

    def create_curriculum_agent(
        self,
        vector_store_ids: list,
        course_name: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        course_description: Optional[str] = None,
        grade_level: Optional[str] = None,
        research_context: Optional[str] = None,
    ):
        from bots._mocks import MockCurriculumAgent
        return MockCurriculumAgent(
            vector_store_ids=vector_store_ids,
            course_name=course_name,
            start_date=start_date,
            end_date=end_date,
            course_description=course_description,
            grade_level=grade_level,
            research_context=research_context,
        )

    def create_profile_agent(self):
        from bots.profile_agent import create_profile_agent
        return create_profile_agent()

    def create_ltg_agent(self, vector_store_id: str, curriculum: dict):
        from bots.ltg_agent import create_ltg_agent
        return create_ltg_agent(vector_store_id, curriculum)

    def create_schedule_agent(self, student, period, schedule, goal_text, previous_response_id=None):
        from bots._mocks import MockLTGScheduleAgent
        return MockLTGScheduleAgent(student=student, schedule=schedule, goal_text=goal_text)

    def create_teacher_feedback_agent(self):
        from bots.teacher_feedback_agent import create_teacher_feedback_agent
        return create_teacher_feedback_agent()

    def create_pptx_agent(self):
        from bots._mocks import MockPptxAgent
        return MockPptxAgent()

    async def run_conversation(self, agent, message: str, **kwargs):
        from bots._mocks import MockRunner
        return await MockRunner.run(agent, message, **kwargs)

    def make_conversations_session(self, conversation_id=None):
        from bots._mocks import MockConversationsSession
        return MockConversationsSession(conversation_id=conversation_id)

    @property
    def runner(self):
        from bots._mocks import MockRunner
        return MockRunner
