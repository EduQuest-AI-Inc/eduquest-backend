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

class IndividualQuest(BaseModel):
    Name: str = Field(description="Name of the quest")
    Skills: str = Field(description="Skills the student will practice through this quest")
    Week: int = Field(description="Week the student will work on this quest")
    instructions: str = Field(description="Detailed instructions for completing the quest")
    rubric: dict = Field(description="Grading criteria and expectations for the quest")

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
    def __init__(self, student, period, schedule):
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
   - A 'Criteria' dictionary with at least 4 keys: 'Criterion A', 'Criterion B', etc.

IMPORTANT: You must generate detailed homework for ALL 18 quests in the schedule. Do not skip any quests.

Your response must follow this format exactly:

{{
  "list_of_quests": [
    {{
      "Name": "Quest Name",
      "Skills": "Skill A, Skill B, Skill C",
      "Week": 1,
      "instructions": "Step-by-step instructions...",
      "rubric": {{
        "Grade_Scale": "Letter grades based on mastery",
        "Criteria": {{
          "Criterion A": "...",
          "Criterion B": "...",
          "Criterion C": "...",
          "Criterion D": "..."
        }}
      }}
    }},
    ...
  ]
}}

Only return valid **JSON**, no markdown, no commentary, and no code blocks.
"""

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
            ]
        )

        self.homework_agent = Agent(
            name="Homework Agent",
            instructions="""
            You will generate detailed homework assignments including rubrics and detailed instructions for a student.
            
            CRITICAL: You must generate detailed homework for ALL 18 quests in the schedule provided. Do not skip any quests.
            
            For each quest in the schedule, you must create:
            - A detailed name that reflects the quest content
            - A comprehensive skills list as a comma-separated string
            - Detailed step-by-step instructions
            - A complete rubric with grade scale and 4 criteria
            
            You must return a valid JSON object with the following structure:
            {
                "list_of_quests": [
                    {
                        "Name": "Quest Name",
                        "Skills": "Skill A, Skill B, Skill C",
                        "Week": 1,
                        "instructions": "Detailed step-by-step instructions...",
                        "rubric": {
                            "Grade_Scale": "A to F based on rubric",
                            "Criteria": {
                                "Criterion A": "Description of criterion A",
                                "Criterion B": "Description of criterion B",
                                "Criterion C": "Description of criterion C",
                                "Criterion D": "Description of criterion D"
                            }
                        }
                    }
                ]
            }
            
            IMPORTANT: Ensure you generate exactly 18 quests, one for each week in the schedule.
            Make sure to return only valid JSON, no markdown formatting or code blocks.
            """,
            model="gpt-4.1-mini",
            tools=[
                FileSearchTool(
                    vector_store_ids=[self.vector_store]
                )
            ],
            handoffs=[self.rubric_agent, self.instruction_agent]
        )

    @output_guardrail()
    async def guardrail(self, ctx: RunContextWrapper, agent: Agent, output: detailed_schedule) -> GuardrailFunctionOutput:
        try:
            result = await Runner.run(
                self.guardrial_agent,
                output.model_dump_json(),
                context=ctx.context
            )

            if "approved" in result.response.lower():
                return GuardrailFunctionOutput(output=output)

            new_homework = await Runner.run(
                self.homework_agent,
                self.input,
                context=ctx.context
            )

            if isinstance(new_homework.output, detailed_schedule):
                return GuardrailFunctionOutput(output=new_homework.output)

            raise OutputGuardrailTripwireTriggered(
                message="Failed to regenerate aligned homework",
                original_output=output
            )

        except Exception as e:
            raise OutputGuardrailTripwireTriggered(
                message=f"Error in guardrail check: {str(e)}",
                original_output=output
            )

    async def _run_async(self) -> detailed_schedule:
        with trace("homework_generation") as span:
            with guardrail_span("homework_guardrail"):
                print("Starting HWAgent._run_async()")
                result = await Runner.run(
                    self.homework_agent,
                    self.input
                )
                print(f"Raw result type: {type(result)}")
                print(f"Raw result: {result}")
                print(f"Result.final_output type: {type(result.final_output)}")
                print(f"Result.final_output: {result.final_output}")

        if isinstance(result.final_output, dict):
            for quest in result.final_output.get("list_of_quests", []):
                if isinstance(quest.get("Skills"), list):
                    quest["Skills"] = ", ".join(quest["Skills"])
            return detailed_schedule(**result.final_output)
        elif isinstance(result.final_output, str):
            print("Agent returned a string instead of structured data")
            print(f"String content: {result.final_output}")
            try:
                parsed = json.loads(result.final_output)
                if isinstance(parsed, dict):
                    for quest in parsed.get("list_of_quests", []):
                        if isinstance(quest.get("Skills"), list):
                            quest["Skills"] = ", ".join(quest["Skills"])
                    return detailed_schedule(**parsed)
            except json.JSONDecodeError:
                print("Failed to parse string as JSON")
                raise Exception("Agent returned invalid format")

        return result.final_output

    def run(self) -> detailed_schedule:
        try:
            print("Starting HWAgent.run()")
            result = asyncio.run(self._run_async())
            print(f"HWAgent result type: {type(result)}")
            print(f"HWAgent result: {result}")
            return result
        except Exception as e:
            print(f"Error in HWAgent.run(): {str(e)}")
            import traceback
            traceback.print_exc()
            raise

# Add response format schema for homework agent
homework_response_format = {
    "type": "object",
    "properties": {
        "list_of_quests": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "Name": {"type": "string"},
                    "Skills": {"type": "string"},
                    "Week": {"type": "integer"},
                    "instructions": {"type": "string"},
                    "rubric": {
                        "type": "object",
                        "properties": {
                            "Grade_Scale": {"type": "string"},
                            "Criteria": {"type": "object"}
                        },
                        "required": ["Grade_Scale", "Criteria"]
                    }
                },
                "required": ["Name", "Skills", "Week", "instructions", "rubric"]
            }
        }
    },
    "required": ["list_of_quests"]
}

# def run_agent(student, period_id):
#     period = Period.get_period(period_id)
#     schedule = SchedulesAgent(student, period).run()
#     homework = HWAgent(student, period, schedule).run()
#     return homework

"""
1. call schedules agent -> get 
"""