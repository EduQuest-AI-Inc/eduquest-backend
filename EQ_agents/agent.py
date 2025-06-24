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
from models.rubric import Rubric

class HomeworkSchedule(BaseModel):
    Name: str = Field(description="Name of the quest")
    Skills: str = Field(description="Skills the student will practice through this quest")
    Week: int = Field(description="Week the student will work on this quest")
    instructions: str = Field(description="Detailed instructions for completing the quest")
    rubric: Rubric = Field(description="Grading criteria and expectations for the quest")

#both of these classes were named IndividualQuest. not sure which one is supposed to be the HomeworkSchedule. 
class IndividualQuest(BaseModel):
    Name: str = Field(description="Name of the quest")
    Skills: str = Field(description="Skills the student will practice through this quest")
    Week: int = Field(description="Week the student will work on this quest")

class schedule(BaseModel):
    list_of_quests: list[IndividualQuest] = Field(description="List of quests for the student")

class SchedulesAgent:
    def __init__(self, student, period):
        self.student = student
        self.period = period
        self.vector_store = period["vector_store_id"] #this was period.vector_store_id, changed because route expects a dict
        # self.input = f"""I'm {self.student.first_name} {self.student.last_name}. My strengths are {self.student.strength}, my weaknesses are {self.student.weakness}, my interests are {self.student.interest}, and my learning style is {self.student.learning_style}. My long-term goal is {self.student.long_term_goal}. I am in grade {self.student.grade}."""
        self.input = f"""I'm {self.student["first_name"]} {self.student["last_name"]}. My strengths are {self.student["strength"]}, my weaknesses are {self.student["weakness"]}, my interests are {self.student["interest"]}, and my learning style is {self.student["learning_style"]}. My long-term goal is {self.student["long_term_goal"]}. I am in grade {self.student["grade"]}."""


        self.schedules_agent = Agent(
            name="Schedules Agent",
            # handoff_description="""You specialize in breaking down the long-term goal into weekly quest. into manageable weekly quests to replace homework. You link the weekly skills students need to learn in the class (found in the course schedule) to their interests while accommodating their capabilities and learning preferences. """,
            instructions="""
                    You specialize in breaking down the long-term goal into manageable weekly quests to replace homework. You link the weekly skills students need to learn in the class (found in the course schedule) to their interests while accommodating their capabilities and learning preferences. 
                    First, you will determine and/or decide what the students are required to learn in the class each week based on the course modules items from file search. There are 18 weeks in total.
                    Baseed on that, you will create a weekly quest for the student that aligns with their long-term goal, interests, strengths, weaknesses, and learning style.
                    Each quest should be a thorough practice of the skills and knowledge learned in class that week and help the student to master these skills and knowledge.
                    You will return the homework schedule for the duration of the course, including the weekly quests and their due dates.
                    By the 18th week, the student will have accomplished their lone term goal.
                    """,
            model="gpt-4.1",
            tools=[
                FileSearchTool(
                    vector_store_ids=[self.vector_store]
                )
            ],
            # output_guardrail()
            output_type = schedule
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
        """
        Guardrail function to ensure weekly quests align with course materials.
        Checks if each quest's skills and topics match what's being taught in class.
        If misaligned, triggers regeneration of the schedule.
        """
        try:
            # Run the guardrail agent to verify alignment
            result = await Runner.run(
                self.guardrial_agent,
                output.model_dump_json(),
                context=ctx.context
            )
            
            # If the guardrail agent approves, return the original output
            if "approved" in result.response.lower():
                return GuardrailFunctionOutput(output=output)
            
            # If not approved, regenerate the schedule
            new_schedule = await Runner.run(
                self.schedules_agent,
                self.input,
                context=ctx.context
            )
            
            # Check if the new schedule is valid
            if isinstance(new_schedule.output, schedule):
                return GuardrailFunctionOutput(output=new_schedule.output)
            
            # If regeneration failed, trigger the tripwire
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
        """
        Internal async method to run the SchedulesAgent with guardrail validation.
        Returns the generated schedule.
        """
        with trace("schedule_generation") as span:
            with guardrail_span("schedule_guardrail"):
                result = await Runner.run(
                    self.schedules_agent,
                    self.input
                )
        return result.final_output

    def run(self) -> schedule:
        """
        Run the SchedulesAgent to generate a schedule with guardrail validation.
        Handles async execution internally and returns the final schedule.
        """
        return asyncio.run(self._run_async())





class HWAgent:
    def __init__(self, student, period, schedule):
        self.student = student
        self.period = period
        self.vector_store = period.vector_store_id
        self.schedule = schedule
        self.input = f"""I'm {self.student.first_name} {self.student.last_name}. My strengths are {self.student.strength}, my weaknesses are {self.student.weakness}, my interests are {self.student.interest}, and my learning style is {self.student.learning_style}. My long-term goal is {self.student.long_term_goal}. I am in grade {self.student.grade}.

For each quest in the schedule, I need detailed instructions and a grading rubric that:
1. Aligns with the skills and topics being taught that week
2. Accommodates my learning style and interests
3. Provides clear expectations and evaluation criteria
4. Helps me practice and master the required skills"""

        self.guardrial_agent = Agent(
            name = "Guardrial Agent",
            handoff_description = "You check if the weekly quests align with the materials taught in class accurately and timely. If not, you will handoff to the Schedules Agent.",
            instructions = "You check if the weekly quests align with the materials taught in class for that corresponding week accurately and timely. If not, you will handoff to the Schedules Agent.",
            model = "gpt-o3",
            tools = [
                FileSearchTool(
                    vector_store_ids=[self.vector_store]
                )
            ]
        )

        self.instruction_agent = Agent(
            name = "Instruction Agent",
            handoff_description = """You specialize in providing detailed instructions for weekly quests""",
            instructions = """
            You will provide detailed instructions for the weekly quests. Make sure to address the materials taught in class for the corresponding week. 
            """,
            model = "gpt-4.1-mini",
            tools = [
                FileSearchTool(
                    vector_store_ids=[self.vector_store]
                )
            ]
        )

        self.rubric_agent = Agent(
            name = "Rubric Agent",
            handoff_description = """You specialize in creating rubrics for weekly quests""",
            instructions = """
            You will create a detailed rubric for the weekly quests. Make sure to address the materials taught in class for the corresponding week.
            """,
            model = "gpt-4.1-mini",
            tools = [
                FileSearchTool(
                    vector_store_ids=[self.vector_store]
                )
            ]
        )

        self.homework_agent = Agent(
            name = "Homework Agent",
            instructions = """
            You will generate a detailed homework assignment including a rubric and detailed instructions for a student. 
            """,
            model = "gpt-4.1-mini",
            tools = [
                FileSearchTool(
                    vector_store_ids=[self.vector_store]
                )
            ],
            output_type = HomeworkSchedule,
            handoffs = [self.rubric_agent, self.instruction_agent]
        )

    @output_guardrail()
    async def guardrail(self, ctx: RunContextWrapper, agent: Agent, output: HomeworkSchedule) -> GuardrailFunctionOutput:
        """
        Guardrail function to ensure homework assignments align with course materials and student needs.
        Checks if each assignment's instructions and rubric match the quest requirements.
        If misaligned, triggers regeneration of the homework.
        """
        try:
            # Run the guardrail agent to verify alignment
            result = await Runner.run(
                self.guardrial_agent,
                output.model_dump_json(),
                context=ctx.context
            )
            
            # If the guardrail agent approves, return the original output
            if "approved" in result.response.lower():
                return GuardrailFunctionOutput(output=output)
            
            # If not approved, regenerate the homework
            new_homework = await Runner.run(
                self.homework_agent,
                self.input,
                context=ctx.context
            )
            
            # Check if the new homework is valid
            if isinstance(new_homework.output, HomeworkSchedule):
                return GuardrailFunctionOutput(output=new_homework.output)
            
            # If regeneration failed, trigger the tripwire
            raise OutputGuardrailTripwireTriggered(
                message="Failed to regenerate aligned homework",
                original_output=output
            )
            
        except Exception as e:
            raise OutputGuardrailTripwireTriggered(
                message=f"Error in guardrail check: {str(e)}",
                original_output=output
            )

    async def _run_async(self) -> HomeworkSchedule:
        """
        Internal async method to run the HWAgent with guardrail validation.
        Returns the generated homework schedule with instructions and rubrics.
        """
        with trace("homework_generation") as span:
            with guardrail_span("homework_guardrail"):
                result = await Runner.run(
                    self.homework_agent,
                    self.input
                )
        return result.final_output

    def run(self) -> HomeworkSchedule:
        """
        Run the HWAgent to generate homework assignments with guardrail validation.
        Handles async execution internally and returns the final homework schedule.
        """
        return asyncio.run(self._run_async())


# def run_agent(student, period_id):
#     period = Period.get_period(period_id)
#     schedule = SchedulesAgent(student, period).run()
#     homework = HWAgent(student, period, schedule).run()
#     return homework