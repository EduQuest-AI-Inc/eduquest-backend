from typing import Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class PptxAgentProtocol(Protocol):
    async def run(self, lesson: dict[str, Any], period_context: dict[str, Any]) -> dict[str, Any]: ...


@runtime_checkable
class BotProviderProtocol(Protocol):
    is_mock: bool

    def create_hw_agent(
        self,
        student,
        period,
        schedule,
        conversation_id=None,
        previous_response_id=None,
    ) -> Any: ...

    def create_grading_orchestrator(self) -> Any: ...

    def create_curriculum_agent(
        self,
        vector_store_ids: list,
        course_name: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        course_description: Optional[str] = None,
        grade_level: Optional[str] = None,
        research_context: Optional[str] = None,
    ) -> Any: ...

    def create_ltg_agent(self, vector_store_id: str, curriculum: dict) -> Any: ...

    def create_schedule_agent(
        self,
        student,
        period,
        schedule,
        goal_text,
        previous_response_id=None,
    ) -> Any: ...

    def create_profile_agent(self) -> Any: ...

    def create_teacher_feedback_agent(self) -> Any: ...

    def create_curriculum_only_quest_agent(self, period: dict, schedule: list) -> Any: ...

    def create_coverage_evaluator(self) -> Any: ...

    def create_demo_ltg_agent(self, grade: str, interests: list[str], subject: str) -> Any: ...

    def create_pptx_agent(self) -> "PptxAgentProtocol": ...

    def make_conversations_session(self, conversation_id=None) -> Any: ...

    async def run_conversation(
        self,
        agent,
        message: str,
        *,
        trace_workflow_name: Optional[str] = None,
        trace_group_id: Optional[str] = None,
        trace_metadata: Optional[dict[str, Any]] = None,
        **kwargs,
    ) -> Any: ...

    async def grade_submission(self, quest_data: dict, submission_text: str) -> dict: ...

    def create_vector_store(self, name: str) -> str: ...

    def ingest_files_to_vector_store(self, vector_store_id: str, file_paths: list) -> list: ...
