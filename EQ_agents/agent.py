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
    def __init__(self, student, period, schedule, timeout_seconds=300):
        self.student = student
        self.period = period
        self.vector_store = period["vector_store_id"]
        self.schedule = schedule
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
            ]
        )

        self.homework_agent = Agent(
            name="Homework Agent",
            instructions="""
            You will generate detailed homework assignments including rubrics and detailed instructions for a student.
            
            For each quest in the schedule, you must create:
            - A detailed name that reflects the quest content
            - A comprehensive skills list as a comma-separated string
            - Detailed step-by-step instructions
            - A complete rubric with grade scale and 4 criteria
            
            You must return a valid JSON object with the following structure:
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

    async def _generate_quest_details(self, quest, week_number):
        """Generate detailed instructions and rubric for a single quest"""
        try:
            student_info = f"""I'm {self.student["first_name"]} {self.student["last_name"]}. My strengths are {self.student["strength"]}, my weaknesses are {self.student["weakness"]}, my interests are {self.student["interest"]}, and my learning style is {self.student["learning_style"]}. My long-term goal is {self.student["long_term_goal"]}. I am in grade {self.student["grade"]}."""

            quest_input = f"""{student_info}

Please generate detailed homework for this quest:

Week {week_number}: {quest.get('Name', 'Quest')}
Skills: {quest.get('Skills', '')}

Generate:
1. Detailed step-by-step instructions
2. A complete rubric with grade scale and 4 criteria

Return as JSON:
{{
    "Name": "{quest.get('Name', 'Quest')}",
    "Skills": "{quest.get('Skills', '')}",
    "Week": {week_number},
    "instructions": "Detailed instructions...",
    "rubric": {{
        "Grade_Scale": "A to F based on rubric",
        "Criteria": {{
            "Criterion A": "...",
            "Criterion B": "...",
            "Criterion C": "...",
            "Criterion D": "..."
        }}
    }}
}}"""

            print(f"Generating details for Week {week_number}: {quest.get('Name', 'Quest')}")
            
            result = await Runner.run(
                self.homework_agent,
                quest_input
            )
            
            if isinstance(result.final_output, dict):
                return result.final_output
            elif isinstance(result.final_output, str):
                try:
                    return json.loads(result.final_output)
                except json.JSONDecodeError:
                    print(f"Failed to parse JSON for Week {week_number}")
                    # Return fallback data
                    return {
                        "Name": quest.get('Name', f'Week {week_number} Quest'),
                        "Skills": quest.get('Skills', ''),
                        "Week": week_number,
                        "instructions": f"Complete the assigned tasks for Week {week_number}. Follow the course materials and apply the skills learned in class.",
                        "rubric": {
                            "Grade_Scale": "A to F based on rubric",
                            "Criteria": {
                                "Criterion A": "Understanding of concepts",
                                "Criterion B": "Application of skills",
                                "Criterion C": "Quality of work",
                                "Criterion D": "Completion of requirements"
                            }
                        }
                    }
            
        except Exception as e:
            print(f"Error generating details for Week {week_number}: {str(e)}")
            # Return fallback data
            return {
                "Name": quest.get('Name', f'Week {week_number} Quest'),
                "Skills": quest.get('Skills', ''),
                "Week": week_number,
                "instructions": f"Complete the assigned tasks for Week {week_number}. Follow the course materials and apply the skills learned in class.",
                "rubric": {
                    "Grade_Scale": "A to F based on rubric",
                    "Criteria": {
                        "Criterion A": "Understanding of concepts",
                        "Criterion B": "Application of skills",
                        "Criterion C": "Quality of work",
                        "Criterion D": "Completion of requirements"
                    }
                }
            }

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
                    
                    # Validate that the quest has proper rubric and instructions
                    if not detailed_quest.get("instructions") or len(detailed_quest.get("instructions", "").strip()) < 10:
                        print(f"Warning: Week {week_number} has insufficient instructions, regenerating...")
                        detailed_quest = await self._generate_quest_details(quest, week_number)
                    
                    if not detailed_quest.get("rubric") or not detailed_quest.get("rubric", {}).get("Criteria"):
                        print(f"Warning: Week {week_number} has insufficient rubric, regenerating...")
                        detailed_quest = await self._generate_quest_details(quest, week_number)
                    
                    detailed_quests.append(detailed_quest)
                    
                    # Small delay to avoid rate limiting
                    await asyncio.sleep(1)
                
                print(f"Completed processing all {total_quests} quests")
                
                # Final validation
                for i, quest in enumerate(detailed_quests):
                    if not quest.get("instructions") or not quest.get("rubric"):
                        print(f"Error: Quest {i+1} is missing required fields")
                        # Use fallback data
                        detailed_quests[i] = {
                            "Name": quest.get("Name", f'Week {i+1} Quest'),
                            "Skills": quest.get("Skills", ''),
                            "Week": quest.get("Week", i+1),
                            "instructions": f"Complete the assigned tasks for Week {i+1}. Follow the course materials and apply the skills learned in class.",
                            "rubric": {
                                "Grade_Scale": "A to F based on rubric",
                                "Criteria": {
                                    "Criterion A": "Understanding of concepts",
                                    "Criterion B": "Application of skills",
                                    "Criterion C": "Quality of work",
                                    "Criterion D": "Completion of requirements"
                                }
                            }
                        }
                
                return detailed_schedule(list_of_quests=detailed_quests)

    def run(self) -> detailed_schedule:
        try:
            print("Starting HWAgent.run()")
            result = asyncio.run(self._run_async())
            print(f"HWAgent completed successfully")
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