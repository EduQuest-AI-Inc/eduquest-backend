"""
Homework (HW) Agent for generating quest instructions and rubrics.

Note: SchedulesAgent has been removed - quest weeks now come from the centralized
period_schedule table (teacher-selected quest weeks). The HWAgent is called directly
with the list of enabled quest weeks.
"""
import sys
import os

# Add the parent directory to Python path so we can import from eduquest-backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents import (
    Agent,
    Runner,
    FileSearchTool,
    OpenAIConversationsSession,
    trace,
)
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import asyncio
from models.rubric import Rubric, Scale


class IndividualQuest(BaseModel):
    """Schema for a quest with full details including instructions and rubric."""
    Name: str = Field(description="Name of the quest")
    Skills: str = Field(description="Skills the student will practice through this quest")
    Week: int = Field(description="Week the student will work on this quest")
    instructions: str = Field(description="Detailed instructions for completing the quest")
    rubric: Dict[str, Any] = Field(description="Grading criteria and expectations for the quest")


class detailed_schedule(BaseModel):
    """Schema for a list of fully detailed quests."""
    list_of_quests: list[IndividualQuest] = Field(description="List of quests for the student")


class HWAgent:
    """
    Homework agent that generates quest instructions and rubrics.
    
    Uses OpenAIConversationsSession to maintain memory of student's LTG conversation,
    so generated homework can reference what the student discussed during goal selection.
    """
    
    def __init__(self, student, period, schedule, conversation_id: Optional[str] = None):
        """
        Initialize the HWAgent.
        
        Args:
            student: Student data dict.
            period: Period data dict (must contain vector_store_id).
            schedule: List of quest dicts with Name, Skills, Week.
            conversation_id: Optional OpenAI conversation_id to use for memory.
                             If provided, all Runner.run calls will share this session.
        """
        self.student = student
        self.period = period
        self.schedule = schedule
        self.vector_store = period["vector_store_id"]
        self.conversation_id = conversation_id
        
        # Create a session for conversation memory if conversation_id is provided
        if conversation_id:
            self.session = OpenAIConversationsSession(conversation_id=conversation_id)
            print(f"HWAgent using conversation memory: {conversation_id}")
        else:
            self.session = None
            print("HWAgent running without conversation memory (stateless)")
        
    async def generate_instructions(self, quest) -> str:
        """Generate detailed instructions for a quest"""
        with trace("generate_instructions"):
            # Handle both dict and object formats
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
                
                Create instructions that:
                1. Are clear and numbered (1, 2, 3, etc.)
                2. Align with the quest skills: {quest_skills}
                3. Consider the student's profile above
                4. Are practical and actionable
                5. Connect to the student's interests where possible
                
                Return ONLY the instructions as a numbered list. No headers or extra text.
                """,
                model="gpt-4o"
            )
            
            # Pass session for conversation memory if available
            run_kwargs = {"session": self.session} if self.session else {}
            result = await Runner.run(
                instruction_agent,
                f"Create detailed instructions for this quest: {quest_name} - Skills: {quest_skills}",
                **run_kwargs
            )
            
            return result.final_output
    
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
                model="gpt-4o",
                output_type=Rubric
            )
            
            # Pass session for conversation memory if available
            run_kwargs = {"session": self.session} if self.session else {}
            result = await Runner.run(
                rubric_agent,
                f"Create a rubric for: {quest_name}",
                **run_kwargs
            )
            
            return result.final_output
    
    async def process_quest(self, quest) -> IndividualQuest:
        """Process a single quest to generate instructions and rubric"""
        with trace("process_quest"):
            # Handle both dict and object formats
            quest_name = quest.get("Name") if isinstance(quest, dict) else getattr(quest, "name", "")
            quest_skills = quest.get("Skills") if isinstance(quest, dict) else getattr(quest, "skills", "")
            quest_week = quest.get("Week") if isinstance(quest, dict) else getattr(quest, "week", 1)
            
            print(f"Processing quest: {quest_name}")
            
            # When using a shared session, run sequentially to avoid concurrent writes
            # Otherwise, run in parallel for speed
            if self.session:
                # Sequential execution for session safety
                instructions = await self.generate_instructions(quest)
                rubric = await self.generate_rubric(quest)
            else:
                # Parallel execution when stateless
                instructions, rubric = await asyncio.gather(
                    self.generate_instructions(quest),
                    self.generate_rubric(quest)
                )
            
            # Convert rubric to dict format
            rubric_dict = rubric.to_dict_format()
            
            # Create the IndividualQuest object
            individual_quest = IndividualQuest(
                Name=quest_name,
                Skills=quest_skills,
                Week=quest_week,
                instructions=instructions,
                rubric=rubric_dict
            )
            
            return individual_quest
    
    async def _run_async(self) -> list[IndividualQuest]:
        """Process all quests in the schedule asynchronously"""
        with trace("homework_generation"):
            total_quests = len(self.schedule)
            successful_quests = []
            
            if self.session:
                # Sequential processing when using shared conversation session
                # This avoids concurrent writes to the same conversation
                print(f"Starting HWAgent - Processing {total_quests} quests sequentially (using conversation memory)")
                
                for i, quest in enumerate(self.schedule, 1):
                    try:
                        result = await self.process_quest(quest)
                        successful_quests.append(result)
                        print(f"✓ Completed quest {i}/{total_quests}")
                    except Exception as e:
                        print(f"✗ Error processing quest {i}: {str(e)}")
            else:
                # Parallel processing when stateless (no session)
                print(f"Starting HWAgent - Processing {total_quests} quests in parallel (stateless)")
                
                tasks = [self.process_quest(quest) for quest in self.schedule]
                detailed_quests = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Filter out exceptions and log errors
                for i, result in enumerate(detailed_quests, 1):
                    if isinstance(result, Exception):
                        print(f"✗ Error processing quest {i}: {str(result)}")
                    else:
                        successful_quests.append(result)
                        print(f"✓ Completed quest {i}")
            
            print(f"\nHWAgent completed - Processed {len(successful_quests)}/{total_quests} quests successfully")
            return successful_quests

    def run(self) -> list[IndividualQuest]:
        return asyncio.run(self._run_async())
