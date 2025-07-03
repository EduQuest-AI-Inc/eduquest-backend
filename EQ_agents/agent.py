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
import json
from openai import vector_stores
from pydantic import BaseModel, Field
import asyncio
from models.period import Period
from models.rubric import Rubric, Scale
from pydantic import BaseModel, Field

class IndividualQuest(BaseModel):
    Name: str = Field(description="Name of the quest")
    Skills: str = Field(description="Skills the student will practice through this quest")
    Week: int = Field(description="Week the student will work on this quest")
    instructions: str = Field(description="Detailed instructions for completing the quest")
    rubric: Rubric = Field(description="Grading criteria and expectations for the quest")

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
    def __init__(self, student, period, schedule, timeout_seconds=300):
        self.student = student
        self.period = period
        self.vector_store = period["vector_store_id"]
        self.schedule = schedule
        schedule_json = json.dumps(schedule, indent=2)

        self.input = f"""I'm {self.student["first_name"]} {self.student["last_name"]}. My strengths are {self.student["strength"]}, my weaknesses are {self.student["weakness"]}, my interests are {self.student["interest"]}, and my learning style is {self.student["learning_style"]}. My long-term goal is {self.student["long_term_goal"]}. I am in grade {self.student["grade"]}.

The following is a course schedule consisting of 18 quests:

{schedule_json}

For each of the 18 quests in the schedule above, please generate:
1. A **string** for the 'Skills' field (not a list) that summarizes the key skills practiced, separated by commas
2. A **detailed 'instructions'** field in paragraph form
3. A **'rubric'** object that includes:
   - A 'Grade_Scale' field (e.g., 'A to F based on rubric')
   - A 'Criteria' dictionary with at least 4 keys

IMPORTANT: You must generate detailed homework for ALL 18 quests in the schedule. Do not skip any quests.
"""
        self.timeout_seconds = timeout_seconds

        self.guardrial_agent = Agent(
            name="Guardrial Agent",
            handoff_description="You check if the weekly quests align with the materials taught in class accurately and timely. If not, you will handoff to the Schedules Agent.",
            instructions="You check if the weekly quests align with the materials taught in class for that corresponding week accurately and timely. If not, you will handoff to the Schedules Agent.",
            model="gpt-o3",
            tools=[
                FileSearchTool(
                    vector_store_ids=[self.vector_store]
                )
            ]
        )

        self.instruction_agent = Agent(
            name="Instruction Agent",
            handoff_description="""You specialize in providing detailed instructions for weekly quests""",
            instructions="""
            You will provide detailed instructions for the weekly quests. Make sure to address the materials taught in class for the corresponding week. 
            """,
            model="gpt-4.1-mini",
            tools=[
                FileSearchTool(
                    vector_store_ids=[self.vector_store]
                )
            ]
        )

        self.rubric_agent = Agent(
            name="Rubric Agent",
            handoff_description="""You specialize in creating rubrics for weekly quests""",
            instructions="""
            You will create a detailed rubric for the weekly quests. Make sure to address the materials taught in class for the corresponding week.
            """,
            model="gpt-4.1-mini",
            tools=[
                FileSearchTool(
                    vector_store_ids=[self.vector_store]
                )
            ],
            output_type=Rubric
        )

        self.homework_agent = Agent(
            name="Homework Agent",
            instructions="""
            You will generate detailed homework assignments including rubrics and detailed instructions for EXISTING quests.
            
            IMPORTANT: Do NOT create new quests or modify the schedule. Only add detailed instructions and rubrics to the existing quest.
            
            For the given quest, you must create:
            - Detailed step-by-step instructions that align with the quest's skills and objectives
            - A complete rubric with grade scales for each criterion

            Make sure to return only valid JSON, no markdown formatting or code blocks.
            """,
            model="gpt-4.1-mini",
            tools=[
                FileSearchTool(
                    vector_store_ids=[self.vector_store]
                )
            ],
            handoffs=[self.rubric_agent, self.instruction_agent],
            output_type=IndividualQuest
        )

    async def _generate_quest_details(self, quest, week_number):
        """Generate detailed instructions and rubric for a single quest"""
        student_info = f"""I'm {self.student["first_name"]} {self.student["last_name"]}. My strengths are {self.student["strength"]}, my weaknesses are {self.student["weakness"]}, my interests are {self.student["interest"]}, and my learning style is {self.student["learning_style"]}. My long_term_goal is {self.student["long_term_goal"]}. I am in grade {self.student["grade"]}."""

        quest_input = f"""{student_info}

Please generate detailed homework for this existing quest:

Week {week_number}: {quest.get('Name', 'Quest')}
Skills: {quest.get('Skills', '')}

Generate ONLY the detailed instructions and rubric for this specific quest. Do NOT create a new schedule or modify the quest name/skills.
"""

        print(f"Generating details for Week {week_number}: {quest.get('Name', 'Quest')}")
        
        result = await Runner.run(
            self.homework_agent,
            quest_input
        )
        
        return result.final_output

    async def _run_async(self) -> detailed_schedule:
        with trace("homework_generation") as span:
            with guardrail_span("homework_guardrail"):
                print("Starting HWAgent._run_async() - Processing quests sequentially")
                
                quests = self.schedule.get("list_of_quests", [])
                detailed_quests = []
                
                total_quests = len(quests)
                print(f"Processing {total_quests} quests...")
                
                for i, quest in enumerate(quests, 1):
                    week_number = quest.get("Week", i)
                    print(f"Progress: {i}/{total_quests} - Week {week_number}")
                    
                    detailed_quest = await self._generate_quest_details(quest, week_number)
                    detailed_quests.append(detailed_quest)
                    
                    # Small delay to avoid rate limiting
                    await asyncio.sleep(1)
                
                print(f"Completed processing all {total_quests} quests")
                
                return detailed_schedule(list_of_quests=detailed_quests)

    def run(self) -> detailed_schedule:
        print("Starting HWAgent.run()")
        result = asyncio.run(self._run_async())
        print(f"HWAgent completed successfully")
        return result

# def run_agent(student, period_id):
#     period = Period.get_period(period_id)
#     schedule = SchedulesAgent(student, period).run()
#     homework = HWAgent(student, period, schedule).run()
#     return homework

"""
1. call schedules agent -> get 
"""