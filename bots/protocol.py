from typing import Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class PptxAgentProtocol(Protocol):
    async def run(
        self,
        lesson: dict[str, Any],
        concepts: list[dict[str, Any]],
        skills: list[dict[str, Any]],
    ) -> bytes: ...


@runtime_checkable
class BotProviderProtocol(Protocol):
    def create_hw_agent(
        self,
        student,
        period,
        schedule,
        conversation_id=None,
        previous_response_id=None,
    ): ...

    def create_grading_orchestrator(self): ...

    def create_curriculum_agent(
        self,
        vector_store_ids: list,
        course_name: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        course_description: Optional[str] = None,
        grade_level: Optional[str] = None,
        research_context: Optional[str] = None,
    ): ...

    def create_ltg_agent(self, vector_store_id: str, curriculum: dict): ...

    def create_schedule_agent(
        self,
        student,
        period,
        schedule,
        goal_text,
        previous_response_id=None,
    ): ...

    def create_profile_agent(self): ...

    def create_teacher_feedback_agent(self): ...

    def create_pptx_agent(self) -> "PptxAgentProtocol": ...

    def make_conversations_session(self, conversation_id=None): ...

    async def run_conversation(self, agent, message: str, **kwargs): ...

    async def grade_submission(self, quest_data: dict, submission_text: str) -> dict: ...
