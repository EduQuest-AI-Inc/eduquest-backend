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

    is_mock: bool = False

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

    def create_curriculum_only_quest_agent(self, period: dict, schedule: list):
        from bots.quests.curriculum_only_quest_agent import CurriculumOnlyQuestAgent
        return CurriculumOnlyQuestAgent(period=period, schedule=schedule)

    def create_coverage_evaluator(self):
        from bots.curriculum.coverage_evaluator import CoverageEvaluator
        return CoverageEvaluator()

    def create_demo_ltg_agent(self, grade: str, interests: list[str], subject: str):
        from bots.quests.demo_ltg_agent import create_demo_ltg_agent
        return create_demo_ltg_agent(grade, interests, subject)

    def create_pptx_agent(self):
        from bots.slideshow.pptx_agent import PptxAgent
        return PptxAgent()

    async def grade_submission(self, quest_data: dict, submission_text: str) -> dict:
        grading_input = self._build_grading_input(quest_data, submission_text)
        orchestrator = self.create_grading_orchestrator()
        result = await orchestrator.grade_submission(
            grading_input,
            trace_group_id=quest_data.get("individual_quest_id") or quest_data.get("quest_id"),
            trace_metadata=self._build_grading_trace_metadata(quest_data, grading_input),
        )
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

    @staticmethod
    def _build_grading_trace_metadata(quest_data: dict, grading_input) -> dict:
        rubric = grading_input.rubric
        return {
            "skill_count": len(grading_input.skills),
            "rubric_type": type(rubric).__name__,
            "rubric_key_count": len(rubric) if isinstance(rubric, dict) else 0,
            "submission_text_len": len(grading_input.submission),
            "has_quest_id": bool(quest_data.get("quest_id")),
            "has_individual_quest_id": bool(quest_data.get("individual_quest_id")),
        }

    async def run_conversation(
        self,
        agent,
        message: str,
        *,
        trace_workflow_name: Optional[str] = None,
        trace_group_id: Optional[str] = None,
        trace_metadata: Optional[dict] = None,
        **kwargs,
    ):
        from agents import Runner
        from bots.tracing import build_trace_run_config

        if trace_workflow_name or trace_group_id or trace_metadata:
            kwargs["run_config"] = build_trace_run_config(
                kwargs.get("run_config"),
                workflow_name=trace_workflow_name,
                group_id=trace_group_id,
                metadata=trace_metadata,
            )
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

    def create_vector_store(self, name: str) -> str:
        from integrations import openai_vector_store
        return openai_vector_store.create_empty(name)

    def ingest_files_to_vector_store(self, vector_store_id: str, file_paths: list) -> list:
        from services.period.period_file_service import PeriodFileService
        return PeriodFileService().ingest_to_openai(vector_store_id, file_paths)


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
        from bots.profile_agent import ProfileResponse
        from bots._mocks import _MockAgent
        return _MockAgent(ProfileResponse)

    def create_ltg_agent(self, vector_store_id: str, curriculum: dict):
        from bots.ltg_agent import LTGResponse
        from bots._mocks import _MockAgent
        return _MockAgent(LTGResponse)

    def create_schedule_agent(self, student, period, schedule, goal_text, previous_response_id=None):
        from bots._mocks import MockLTGScheduleAgent
        return MockLTGScheduleAgent(student=student, schedule=schedule, goal_text=goal_text)

    def create_teacher_feedback_agent(self):
        from bots.teacher_feedback_agent import create_teacher_feedback_agent
        return create_teacher_feedback_agent()

    def create_curriculum_only_quest_agent(self, period: dict, schedule: list):
        from bots._mocks import MockCurriculumOnlyQuestAgent
        return MockCurriculumOnlyQuestAgent(period=period, schedule=schedule)

    def create_coverage_evaluator(self):
        from bots._mocks import MockCoverageEvaluator
        return MockCoverageEvaluator()

    def create_demo_ltg_agent(self, grade: str, interests: list[str], subject: str):
        from bots._mocks import MockDemoLTGAgent
        return MockDemoLTGAgent()

    def create_pptx_agent(self):
        from bots._mocks import MockPptxAgent
        return MockPptxAgent()

    async def run_conversation(
        self,
        agent,
        message: str,
        *,
        trace_workflow_name: Optional[str] = None,
        trace_group_id: Optional[str] = None,
        trace_metadata: Optional[dict] = None,
        **kwargs,
    ):
        from bots._mocks import MockRunner
        return await MockRunner.run(agent, message, **kwargs)

    def make_conversations_session(self, conversation_id=None):
        from bots._mocks import MockConversationsSession
        return MockConversationsSession(conversation_id=conversation_id)

    @property
    def runner(self):
        from bots._mocks import MockRunner
        return MockRunner

    def create_vector_store(self, name: str) -> str:
        return "mock-vs-id"

    def ingest_files_to_vector_store(self, vector_store_id: str, file_paths: list) -> list:
        return []
