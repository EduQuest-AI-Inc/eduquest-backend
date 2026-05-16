"""
Homework (HW) Agent for generating quest instructions and rubrics.

Quest weeks are derived from the curriculum (all weeks in an approved curriculum
generate quests). The HWAgent receives the assembled quest list from PeriodQuestService.
"""
import logging
import sys
import os

# Add the parent directory to Python path so we can import from eduquest-backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

logger = logging.getLogger(__name__)

from agents import (
    Agent,
    Runner,
    trace,
)
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import asyncio
from bots.schemas.rubric import Rubric
from bots.schemas.instructions import Instructions
from bots.model_config import QUEST_INSTRUCTION_MODEL, QUEST_RUBRIC_MODEL
import re


def _clean_step_text(text: str) -> str:
    """Strip common AI text artifacts from a step's text."""
    text = text.replace('\\n', ' ').replace('\\r', ' ')
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'^[\-\*\^#>\s]+', '', text)
    return text.strip()


class IndividualQuest(BaseModel):
    """Schema for a quest with full details including instructions and rubric."""
    Name: str = Field(description="Name of the quest")
    Skills: str = Field(description="Skills the student will practice through this quest")
    Week: int = Field(description="Week the student will work on this quest")
    instructions: list[Dict[str, Any]] = Field(description="Ordered list of step dicts [{step, text}]")
    rubric: Dict[str, Any] = Field(description="Grading criteria and expectations for the quest")


class detailed_schedule(BaseModel):
    """Schema for a list of fully detailed quests."""
    list_of_quests: list[IndividualQuest] = Field(description="List of quests for the student")


class HWAgent:
    """
    Homework agent that generates quest instructions and rubrics.

    Accepts an optional previous_response_id (the last response ID from the
    student's LTG conversation) so instruction and rubric generation get LTG context.
    """

    def __init__(self, student, period, schedule, conversation_id: Optional[str] = None, previous_response_id: Optional[str] = None) -> None:
        """
        Initialize the HWAgent.

        Args:
            student: Student data dict.
            period: Period data dict (must contain vector_store_id).
            schedule: List of quest dicts with Name, Skills, Week.
            conversation_id: Ignored (kept for backwards-compat call sites).
            previous_response_id: Optional last_response_id from the LTG conversation
                                   for passing context to instruction and rubric generation.
        """
        self.student = student
        self.period = period
        self.schedule = schedule
        self.vector_store = period["vector_store_id"]
        self.previous_response_id = previous_response_id
        self.session = None  # No longer using OpenAIConversationsSession

        if previous_response_id:
            logger.debug("HWAgent using LTG previous_response_id for context: %s", previous_response_id)
        else:
            logger.debug("HWAgent running without LTG conversation context (stateless)")
        
    async def generate_instructions(self, quest) -> list[dict]:
        """Generate detailed step-by-step instructions for a quest as structured data."""
        with trace("generate_instructions"):
            quest_name = quest.get("Name") if isinstance(quest, dict) else getattr(quest, "name", "")
            quest_skills = quest.get("Skills") if isinstance(quest, dict) else getattr(quest, "skills", "")

            instruction_agent = Agent(
                name="Instruction Generator",
                instructions=f"""
                You create detailed step-by-step instructions for a quest.

                Student Information:
                - Name: {self.student["first_name"]} {self.student["last_name"]}
                - Strengths: {self.student["strength"]}
                - Weaknesses: {self.student["weakness"]}
                - Interests: {self.student["interest"]}
                - Learning Style: {self.student["learning_style"]}
                - Grade: {self.student["grade"]}

                Create 4-7 steps that:
                - Are clear and actionable
                - Align with the quest skills: {quest_skills}
                - Consider the student's profile above
                - Connect to the student's interests where possible

                IMPORTANT formatting rules for each step's text:
                - Write plain prose sentences only
                - No markdown (no *, **, #, -, ^, >)
                - No escape sequences (no \\n, \\r, \\t)
                - No numbered prefixes in the text (the step number is stored separately)
                """,
                model=QUEST_INSTRUCTION_MODEL,
                output_type=Instructions,
            )

            run_kwargs = {}
            if self.previous_response_id:
                run_kwargs["previous_response_id"] = self.previous_response_id
            result = await Runner.run(
                instruction_agent,
                f"Create detailed instructions for this quest: {quest_name} - Skills: {quest_skills}",
                **run_kwargs  # type: ignore[arg-type]
            )

            steps = result.final_output.steps
            return [{"step": s.step, "text": _clean_step_text(s.text)} for s in steps]
    
    async def generate_rubric(self, quest) -> Rubric:
        """Generate a rubric for a quest"""
        with trace("generate_rubric"):
            # Handle both dict and object formats
            quest_name = quest.get("Name") if isinstance(quest, dict) else getattr(quest, "name", "")
            quest_skills = quest.get("Skills") if isinstance(quest, dict) else getattr(quest, "skills", "")
            
            rubric_agent = Agent(
                name="Rubric Generator",
                instructions=f"""
                You create grading rubrics for quests with multiple criteria.
                
                For the quest "{quest_name}" focusing on skills: {quest_skills}
                
                Create a rubric with 3-4 specific assessment criteria, each with their own Score_0 through Score_5 descriptions.
                
                IMPORTANT: Create a list of criteria_list where each item has:
                - name: The name of the criterion (e.g., "Accuracy", "Understanding", "Presentation")
                - scale: An object with Score_0, Score_1, Score_2, Score_3, Score_4, Score_5 fields
                
                For each criterion, provide specific descriptions for what constitutes each score level (0-5) for THAT particular aspect.
                
                Example criteria might be:
                - Accuracy/Correctness
                - Explanation/Understanding  
                - Presentation/Organization
                - Application/Analysis
                
                Make each criterion's scoring descriptions specific to what you're evaluating in that area.
                Each score level should clearly describe what performance looks like for that criterion at that level.
                """,
                model=QUEST_RUBRIC_MODEL,
                output_type=Rubric
            )
            
            run_kwargs = {}
            if self.previous_response_id:
                run_kwargs["previous_response_id"] = self.previous_response_id
            result = await Runner.run(
                rubric_agent,
                f"Create a rubric for: {quest_name}",
                **run_kwargs  # type: ignore[arg-type]
            )

            return result.final_output
    
    async def process_quest(self, quest) -> IndividualQuest:
        """Process a single quest to generate instructions and rubric."""
        with trace("process_quest"):
            teacher_plan = quest.get("Name") if isinstance(quest, dict) else getattr(quest, "name", "")
            quest_skills = quest.get("Skills") if isinstance(quest, dict) else getattr(quest, "skills", "")
            quest_week = quest.get("Week") if isinstance(quest, dict) else getattr(quest, "week", 1)

            logger.debug("Processing quest: %s", teacher_plan)

            instructions, rubric = await asyncio.gather(
                self.generate_instructions(quest),
                self.generate_rubric(quest),
            )

            return IndividualQuest(
                Name=teacher_plan,
                Skills=quest_skills,  # type: ignore[arg-type]
                Week=quest_week,  # type: ignore[arg-type]
                instructions=instructions,
                rubric=rubric.to_dict_format(),
            )
    
    async def _run_async(self) -> list[IndividualQuest]:
        """Process all quests in the schedule asynchronously"""
        with trace("homework_generation"):
            total_quests = len(self.schedule)
            successful_quests = []
            
            logger.info("Starting HWAgent - Processing %d quests in parallel", total_quests)

            tasks = [self.process_quest(quest) for quest in self.schedule]
            detailed_quests = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(detailed_quests, 1):
                if isinstance(result, Exception):
                    logger.error("Error processing quest %d: %s", i, result)
                else:
                    successful_quests.append(result)
                    logger.debug("Completed quest %d", i)

            logger.info("HWAgent completed - Processed %d/%d quests successfully", len(successful_quests), total_quests)
            return successful_quests  # type: ignore[return-value]

    def run(self) -> list[IndividualQuest]:
        return asyncio.run(self._run_async())
