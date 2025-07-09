import sys
import os

# Add the parent directory to Python path so we can import from eduquest-backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents import (
    Agent,
    Runner,
    FileSearchTool,
    output_guardrail,
    GuardrailFunctionOutput,
    OutputGuardrailTripwireTriggered,
    RunContextWrapper,
    trace,
    guardrail_span

)
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX
import json
from openai import vector_stores
from pydantic import BaseModel, Field
from typing import Dict, Any
import asyncio
from models.period import Period
from models.rubric import Rubric, Scale

class IndividualQuest(BaseModel):
    Name: str = Field(description="Name of the quest")
    Skills: str = Field(description="Skills the student will practice through this quest")
    Week: int = Field(description="Week the student will work on this quest")
    instructions: str = Field(description="Detailed instructions for completing the quest")
    rubric: Dict[str, Any] = Field(description="Grading criteria and expectations for the quest")

class BaseQuest(BaseModel):
    Name: str = Field(description="Name of the quest")
    Skills: str = Field(description="Skills the student will practice through this quest")
    Week: int = Field(description="Week the student will work on this quest")

class schedule(BaseModel):
    list_of_quests: list[BaseQuest] = Field(description="List of quests for the student")

class detailed_schedule(BaseModel):
    list_of_quests: list[IndividualQuest] = Field(description="List of quests for the student")

class SchedulesAgent:
    def __init__(self, student, period):
        self.student = student
        self.period = period
        self.vector_store = period["vector_store_id"]
        self.input = f"""I'm {self.student["first_name"]} {self.student["last_name"]}. My strengths are {self.student["strength"]}, my weaknesses are {self.student["weakness"]}, my interests are {self.student["interest"]}, and my learning style is {self.student["learning_style"]}. My long-term goal is {self.student["long_term_goal"]}. I am in grade {self.student["grade"]}."""

        self.schedules_agent = Agent(
            name="Schedules Agent",
            instructions="""
                You specialize in breaking down the long-term goal into manageable weekly quests to replace homework. You link the weekly skills students need to learn in the class (found in the course schedule) to their interests while accommodating their capabilities and learning preferences. 
                First, you will determine and/or decide what the students are required to learn in the class each week based on the course modules items from file search. There are 18 weeks in total.
                Based on that, you will create a weekly quest for the student that aligns with their long-term goal, interests, strengths, weaknesses, and learning style.
                Each quest should be a thorough practice of the skills and knowledge learned in class that week and help the student to master these skills and knowledge.
                You will return the homework schedule for the duration of the course, including the weekly quests and their due dates.
                By the 18th week, the student will have accomplished their long term goal.
            """,
            model="gpt-4.1",
            tools=[
                FileSearchTool(
                    vector_store_ids=[self.vector_store]
                )
            ],
            output_type=schedule
        )

        self.guardrial_agent = Agent(
            name="Guardrial Agent",
            handoff_description="You check if the weekly quests align with the materials taught in class accurately and timely. If not, you will handoff to the Schedules Agent.",
            instructions="You check if the weekly quests align with the materials taught in class for that corresponding week accurately and timely. If not, you will handoff to the Schedules Agent.",
            model="gpt-4.1",
            tools=[
                FileSearchTool(
                    vector_store_ids=[self.vector_store]
                )
            ]
        )

    @output_guardrail()
    async def guardrail(self, ctx: RunContextWrapper, agent: Agent, output: schedule) -> GuardrailFunctionOutput:
        try:
            result = await Runner.run(
                self.guardrial_agent,
                output.model_dump_json(),
                context=ctx.context
            )
            if "approved" in result.response.lower():
                return GuardrailFunctionOutput(output=output)

            new_schedule = await Runner.run(
                self.schedules_agent,
                self.input,
                context=ctx.context
            )
            if isinstance(new_schedule.output, schedule):
                return GuardrailFunctionOutput(output=new_schedule.output)

            raise OutputGuardrailTripwireTriggered(
                message="Failed to regenerate aligned schedule",
                original_output=output
            )
        except Exception as e:
            raise OutputGuardrailTripwireTriggered(
                message=f"Error in guardrail check: {str(e)}",
                original_output=output
            )

    async def _run_async(self) -> schedule:
        with trace("schedule_generation") as span:
            with guardrail_span("schedule_guardrail"):
                result = await Runner.run(
                    self.schedules_agent,
                    self.input
                )
        return result.final_output

    def run(self) -> schedule:
        return asyncio.run(self._run_async())

class HWAgent:
    """A simpler homework agent that generates instructions and rubrics directly"""
    
    def __init__(self, student, period, schedule, timeout_seconds=300):
        self.student = student
        self.period = period
        self.schedule = schedule
        self.vector_store = period["vector_store_id"]
        self.timeout_seconds = timeout_seconds
        
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
            
            result = await Runner.run(
                instruction_agent,
                f"Create detailed instructions for this quest: {quest_name} - Skills: {quest_skills}"
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
            
            result = await Runner.run(
                rubric_agent,
                f"Create a rubric for: {quest_name}"
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
            
            # Generate instructions and rubric in parallel
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
            detailed_quests = []
            total_quests = len(self.schedule)
            
            print(f"Starting HWAgent - Processing {total_quests} quests")
            
            for i, quest in enumerate(self.schedule, 1):
                print(f"\nProgress: {i}/{total_quests}")
                try:
                    detailed_quest = await self.process_quest(quest)
                    detailed_quests.append(detailed_quest)
                    print(f"✓ Completed quest {i}")
                    
                    # For testing, just process the first quest
                    # if i == 1:
                    #     break
                        
                except Exception as e:
                    print(f"✗ Error processing quest {i}: {str(e)}")
                    continue
            
            print(f"\nHWAgent completed - Processed {len(detailed_quests)} quests successfully")
            return detailed_quests

    def run(self) -> list[IndividualQuest]:
        """Process all quests in the schedule"""
        return asyncio.run(self._run_async())

# def run_agent(student, period_id):
#     period = Period.get_period(period_id)
#     schedule = SchedulesAgent(student, period).run()
#     homework = HWAgent(student, period, schedule).run()
#     return homework

"""
1. call schedules agent -> get 
"""