from agents import Agent, Runner, FileSearchTool, output_guardrail, GuardrailFunctionOutput, OutputGuardrailTripwireTriggered, RunContextWrapper, output_guardrail
from openai import vector_stores
from pydantic import BaseModel
from pydantic import BaseModel, Field

class IndividualQuest(BaseModel):
    Description: str
    # Grade: str = Field(description="Grade provided by the grader")
    # Feedback: str = Field(description="Feedback provided by the grader")
    Skills: str = Field(description="Skills the student will practice through this quest")
    Week: int = Field(description="Week the student will work on this quest")
    # created_at: str

class baseQuest(BaseModel):
    name: str
    topics: list[str] = Field(description="List of course topics covered in the quest")

class schedule(BaseModel):
    list_of_quests: list[IndividualQuest] = Field(description="List of quests for the student")



class SchedulesAgent:
    def __init__(self, student, period):
        self.student = student
        self.period = period
        self.vector_store = period.vector_store_id
        self.input = f"""I'm {self.student.first_name} {self.student.last_name}. My strengths are {self.student.strength}, my weaknesses are {self.student.weakness}, my interests are {self.student.interest}, and my learning style is {self.student.learning_style}. My long-term goal is {self.student.long_term_goal}. I am in grade {self.student.grade}."""

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
        async def guardrail(ctx: RunContextWrapper, agent: Agent, output: schedule) -> GuardrailFunctionOutput:
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





class HWAgent:
    def __init__(self, student, period, schedule):
        self.student = student
        self.period = period
        self.vector_store = period.vector_store_id
        self.schedule = schedule
        self.input = f"""I'm {self.student.first_name} {self.student.last_name}. My strengths are {self.student.strenth}, my weaknesses are {self.student.weakness}, my interests are {self.student.interest}, and my learning style is {self.student.learning_style}. My long-term goal is {self.student.long_term_goal}. I am in grade {self.student.grade}."""

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
                    vector_store_ids=[]
                )
            ],
            handoffs = [self.schedules_agent, self.rubric_agent, self.instruction_agent]
        )
