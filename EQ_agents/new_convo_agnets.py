from pyexpat import model
import openai
from openai import OpenAI
import time
import os
import json
from dotenv import load_dotenv
from openai.types.shared_params.response_format_json_schema import ResponseFormatJSONSchema
from openai.types.shared import Reasoning
# from models.student import Student
import decimal
import asyncio
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
from types import SimpleNamespace
from guardrails.runtime import load_config_bundle, instantiate_guardrails, run_guardrails
# New agents framework imports
from agents import (
    Agent,
    Runner,
    input_guardrail,
    output_guardrail,
    GuardrailFunctionOutput,
    RunContextWrapper,
    InputGuardrailTripwireTriggered,
    OutputGuardrailTripwireTriggered,
    MessageOutputItem,
    TResponseInputItem,
    SQLiteSession,
    ModelSettings,
    FileSearchTool,
    trace
)
load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Guardrails setup for student input checking
guardrails_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
guardrails_ctx = SimpleNamespace(guardrail_llm=guardrails_client)

# Guardrails configuration (matching agent builder code.py)
student_input_guardrails_config = {
  "guardrails": [
    { "name": "Moderation", "config": { "categories": ["sexual", "sexual/minors", "hate", "hate/threatening", "harassment", "harassment/threatening", "self-harm", "self-harm/intent", "self-harm/instructions", "violence", "violence/graphic", "illicit", "illicit/violent"] } },
    { "name": "Jailbreak", "config": { "model": "gpt-4.1-mini", "confidence_threshold": 0.7 } },
    { "name": "Prompt Injection Detection", "config": { "model": "gpt-4.1-mini", "confidence_threshold": 0.7 } },
    { "name": "Custom Prompt Check", "config": { "system_prompt_details": "Raise the guardrail if user expresses any experience of abuse.", "model": "gpt-4.1-mini", "confidence_threshold": 0.7 } }
  ]
}

def student_guardrails_has_tripwire(results):
    return any((hasattr(r, "tripwire_triggered") and (r.tripwire_triggered is True)) for r in (results or []))

async def check_student_input_with_guardrails(input_text: str) -> dict:
    """Run input guardrails on student text and return results"""
    results = await run_guardrails(
        guardrails_ctx, 
        input_text, 
        "text/plain", 
        instantiate_guardrails(load_config_bundle(student_input_guardrails_config)), 
        suppress_tripwire=True, 
        raise_guardrail_errors=True
    )
    has_tripwire = student_guardrails_has_tripwire(results)
    return {"results": results, "has_tripwire": has_tripwire}

# Pydantic models for structured outputs
class StudentProfile(BaseModel):
    strengths: List[str]
    weaknesses: List[str]
    interests: List[str]
    learning_styles: List[str]

class InitialConversationResponse(BaseModel):
    response: str = Field(description="Assistant's response to the student")
    # profile_complete: bool = Field(description="Whether the student profile is complete")
    profile: Optional[StudentProfile] = Field(description="Extracted student traits throughout the conversation")

class SafetyCheck(BaseModel):
    is_safe: bool = Field(description="Whether the content is safe for students")
    reason: str = Field(description="Reason if content is not safe")

# Guardrail functions for student safety
@input_guardrail
async def check_student_input_safety(
    ctx: RunContextWrapper[None],
    agent: Agent,
    input_str: str | list[TResponseInputItem]
) -> GuardrailFunctionOutput:
    """Check if student input contains inappropriate content using LLM"""

    safety_agent = Agent(
        name="Input Safety Checker",
        instructions="""You are a content safety moderator for educational platforms.
        Analyze the student message and determine if it's appropriate for educational settings.
        Check for inappropriate language, violence, hate speech, sexual content, bullying,
        self-harm references, or illegal activities.

        Return is_safe as true if appropriate, false if inappropriate.
        If not safe, provide a brief reason.""",
        model="omni-moderation-latest",
        output_type=SafetyCheck
    )

    result = await Runner.run(
        safety_agent,
        input_str,
        context=ctx.context
    )
    if result.final_output.is_safe:
        return GuardrailFunctionOutput(
            output_info=result.final_output, 
            tripwire_triggered=False,
        )
    else:
        return GuardrailFunctionOutput(
            output_info=result.final_output, 
            tripwire_triggered=True,
        )

@output_guardrail
async def check_student_output_safety(
    ctx: RunContextWrapper,
    agent: Agent,
    output: MessageOutputItem
) -> GuardrailFunctionOutput:
    """Ensure output content is safe and appropriate for students using LLM"""
    safety_agent = Agent(
        name="Output Safety Checker",
        instructions="""You are a content safety moderator for educational platforms.
        Analyze the AI response to ensure it's appropriate for students.
        Check for age-appropriate language, educational content, no harmful/inappropriate content,
        and supportive tone.

        Return is_safe as true if appropriate, false if needs modification.
        If not safe, provide a brief reason.""",
        model="omni-moderation-latest",
        output_type=SafetyCheck
    )

    result = await Runner.run(
        safety_agent,
        output.response,
        context=ctx.context
    )

    if result.final_output.is_safe:
        return GuardrailFunctionOutput(
            output_info=result.final_output, 
            tripwire_triggered=False,
        )
    else:
        return GuardrailFunctionOutput(
            output_info=result.final_output, 
            tripwire_triggered=True,
        ), result.final_output.reason


class ini_conv:
    def __init__(self, student, session_id):
        self.student = student
        self.session = SQLiteSession(session_id)
        self.agent = Agent(
            name="Initial Conversation Agent",
            instructions="""You are an advisor who helps students identify their strengths, weaknesses, interests, and learning styles. Your role is to understand these personal attributes to better support students in their educational journey. 

                Here's how you will interact with users and gain information about the student:
                - Greet the student. Begin by introducing yourself as EduQuest, their education companion, and you are trying to gather information about them to create a personalized profile for them so EduQuest can personalize their school work, while also encouraging them to talk about their interests in a supportive and engaging manner.
                - Ask about details of their interests to gain more insights into the student. Use this conversation to explore and learn about their strengths, weaknesses, and learning styles through discussion. Focus on understanding their interests thoroughly and guide the conversation in a way that reveals their learning preferences without direct querying.

                # Examples
                - **Example of Student Profile**:
                - **Strengths**: "Analytical thinking, problem-solving"
                - **Weaknesses**: "Time management, public speaking"
                - **Interests**: "Robotics, astronomy"
                - **Learning Styles**: "Visual, hands-on"

                # Notes
                - Keep asking details until you receive enough information to generate the student profile.
                - Limit the response to under 3 sentences or 100 words.
                - Only assist with identifying strengths, weaknesses, interests, and learning styles. If asked to do something outside of this responsibility, respectfully decline the request.""",
            model="gpt-5",
            model_settings=ModelSettings(reasoning=Reasoning(effort="low"), verbosity="medium"),
            output_type=InitialConversationResponse,
            output_guardrails=[check_student_output_safety]
        )

    async def initiate(self):
        initial_message = f"Hello, I'm in {self.student.grade}th grade."
        
        # Check input with guardrails
        guardrail_result = await check_student_input_with_guardrails(initial_message)
        if guardrail_result["has_tripwire"]:
            return "I'm sorry, but I cannot process this request due to safety concerns."
        
        result = await Runner.run(
            self.agent,
            initial_message,
            session=self.session
        )
        
        response = result.final_output
        # Session management simplified for demo
        
        return response.response

    async def cont_conv(self, user_input):
        print(f"User input: {user_input}")
        
        # Check input with guardrails
        guardrail_result = await check_student_input_with_guardrails(user_input)
        if guardrail_result["has_tripwire"]:
            return "I'm sorry, but I cannot process this request due to safety concerns.", False, None
        
        while True:
            try:
                result = await Runner.run(
                    self.agent,
                    user_input,
                    session=self.session
                )
                
                response = result.final_output

                if response.profile:
                    profile = {
                        "strength": response.profile.strengths,
                        "weakness": response.profile.weaknesses,
                        "interest": response.profile.interests,
                        "learning_style": response.profile.learning_styles,
                    }
                    return response.response, True, profile
                else:
                    return response.response, False, None
            except OutputGuardrailTripwireTriggered:
                await self.session.pop_item()
                continue
##########################################################



class LTGResponse(BaseModel):
    message: str = Field(description="Assistant's message to the student")
    goal_1: str = Field(description="The first long-term goal")
    goal_2: str = Field(description="The second long-term goal")
    goal_3: str = Field(description="The third long-term goal")
    chosen_goal: Optional[str] = Field(description="The goal chosen by the student, if any")

class GradingResult(BaseModel):
    numerical_grade: int = Field(description="Total points from rubric")
    feedback: str = Field(description="Student-facing feedback")
    skill_mastery: Dict[str, float] = Field(description="Skill to mastery level mapping")
    homework_changes_recommended: bool = Field(description="Whether homework changes are recommended")
    recommended_changes: Optional[List[str]] = Field(description="Specific change suggestions")

class ltg:
    def __init__(self, student, vector_store_id, session_id=None):
        self.student = student
        self.vector_store_id = vector_store_id
        self.session_id = session_id
        self.agent = Agent(
            name="Long-Term Goal Assistant",
            instructions="""You are a Long-Term Goal (LTG) Assistant for EduQuest. Your job is to help students choose a meaningful long-term goal that aligns with their course materials, strengths, weaknesses, interests, and learning style.

            **INITIAL RESPONSE (when student first asks for goals):**
            1. Search the course materials using file_search to understand what the student will learn
            2. Suggest exactly 3 long-term goals that:
               - Incorporate ALL the course materials from the file search
               - Align with the student's strengths, weaknesses, interests, and learning style
               - Can be achieved in 18 weeks
               - Help the student practice what they learn in class in a way that interests them

            **WHEN STUDENT CHOOSES A GOAL:**
            If the student indicates they want to choose a goal (e.g., "I choose goal 1", "I pick the first one", "I want to do goal 2"), respond with:
            - message: "Excellent choice! I've selected [chosen goal] as your long-term goal. This will help you [brief explanation of how it aligns with their interests and course materials]."
            - chosen_goal: "[full text of the chosen goal]"

            **IMPORTANT RULES:**
            - Always search course materials first using file_search
            - Make goals specific and actionable
            - Ensure goals incorporate course content meaningfully
            - Keep responses encouraging and supportive
            - Only set chosen_goal when student explicitly chooses one""",
            model="gpt-5",
            model_settings=ModelSettings(reasoning=Reasoning(effort="medium"), verbosity="medium"),
            output_type=LTGResponse,
            tools=[
                # FileSearchTool will be added when we have vector store integration
            ],
            output_guardrails=[check_student_output_safety]
        )

    async def initiate(self):
        first_name = self.student["first_name"]
        last_name = self.student["last_name"]
        grade = self.student["grade"]
        strengths = ", ".join(self.student.get("strength", [])) if isinstance(self.student.get("strength"), list) else str(self.student.get("strength", ""))
        weaknesses = ", ".join(self.student.get("weakness", [])) if isinstance(self.student.get("weakness"), list) else str(self.student.get("weakness", ""))
        interests = ", ".join(self.student.get("interest", [])) if isinstance(self.student.get("interest"), list) else str(self.student.get("interest", ""))
        learning_style = ", ".join(self.student.get("learning_style", [])) if isinstance(self.student.get("learning_style"), list) else str(self.student.get("learning_style", ""))
        
        initial_message = f"Hello, I'm {first_name} {last_name}, in {grade}th grade. My strengths are {strengths}, my weaknesses are {weaknesses}, my interests are {interests}, and my learning style is {learning_style}. Please search the course materials and recommend 3 long-term goals for me that incorporate what I'll learn in this class."
        
        # Check input with guardrails
        guardrail_result = await check_student_input_with_guardrails(initial_message)
        if guardrail_result["has_tripwire"]:
            return {
                "message": "I'm sorry, but I cannot process this request due to safety concerns.",
                "chosen_goal": None,
                "session_id": self.session_id
            }
        
        result = await Runner.run(
            self.agent,
            initial_message,
            session_id=self.session_id
        )
        
        response = result.final_output
        # Session management simplified for demo
        
        return {
            "message": response.message,
            "chosen_goal": response.chosen_goal,
            "session_id": self.session_id
        }

    async def cont_conv(self, user_input):
        # Check input with guardrails
        guardrail_result = await check_student_input_with_guardrails(user_input)
        if guardrail_result["has_tripwire"]:
            return "I'm sorry, but I cannot process this request due to safety concerns.", False
        
        result = await Runner.run(
            self.agent,
            user_input
        )
        
        response = result.final_output
        
        # Check if a goal was chosen
        if response.chosen_goal and response.chosen_goal.lower() != "null":
            return response.chosen_goal, True
        else:
            return response.message, False

# class 

class SemesterSchedule(BaseModel):
    weeks: dict[int, list[str]] = Field(
        description="Map week number → topics/skills"
    )


class SemesterScheduleConversation(BaseModel):
    schedule: SemesterSchedule = Field(description="The schedule for the semester")
    changes_requested: bool = Field(description="Whether changes to the schedule are requested")
    changes_suggested: Optional[List[str]] = Field(description="Suggested changes to the schedule")

class Semester:
    def __init__(self, vector_store_id, session_id=None, weeks=18):
        self.vector_store_id = vector_store_id
        self.weeks = weeks
        self.session_id = session_id
        self.session = SQLiteSession(session_id)
        # Define semester_schedule_agent FIRST (before triage_agent references it)
        self.semester_schedule_agent = Agent(
            name="Semester Schedule Outliner",
            handoff_description="Specialist agent for outlining the schedule for a semester.",
            instructions="""
            You are a teaching assistant that helps teachers outline the schedule for a semester. 
            You will use the course materials in the vector store to outline the schedule for the semester. 
            For each week, you will outline the topics/skills that the student will learn in that week.
            """,
            model="gpt-5",
            model_settings=ModelSettings(reasoning=Reasoning(effort="medium"), verbosity="medium"),
            tools=[
                FileSearchTool(
                    vector_store_ids=[self.vector_store_id]
                )
            ],
            output_type=SemesterSchedule
        )
        
        # Now define triage_agent that references semester_schedule_agent in handoffs
        self.triage_agent = Agent(
            name="Triage Agent",
            instructions="""
            You are a teaching assistant that helps teachers outline the schedule for a semester. 
            Here's your procedure:
            1. Use the scheduler tool to outline the schedule for the semester.
            2. Wait for the Semester Schedule Outliner agent to return the schedule.
            3. Return the schedule to the teacher and ask if there are any changes to the schedule.
            4. If there are changes, handoff to the Semester Schedule Outliner agent to outline the schedule for the semester.
            5. Repeat steps 2-4 until the teacher is satisfied with the schedule.
            6. Return the final schedule to the teacher.
            """,
            model="gpt-5",
            model_settings=ModelSettings(reasoning=Reasoning(effort="medium"), verbosity="medium"),
            output_type=SemesterScheduleConversation,
            tools=[
                self.semester_schedule_agent.as_tool(
                    tool_name="scheduler",
                    tool_description="Specialist agent for outlining the schedule for a semester.",
                ),
                FileSearchTool(
                    vector_store_ids=[self.vector_store_id]
                )
            ]
        )

    async def initiate(self):
        initial_message = f"Please outline the schedule for the semester according to the course materials in the vector store."
        result = await Runner.run(
            self.triage_agent,
            initial_message,
            session=self.session
        )
        return result.final_output

    async def cont_conv(self, user_input):
        result = await Runner.run(
            self.triage_agent,
            user_input,
            session_id=self.session_id
        )
        return result.final_output
    
    async def initiate_with_approval(self):
        """
        Initiates the semester scheduling workflow for approval loop.
        Generates the initial schedule and returns it for review.
        
        Returns:
            dict: Contains schedule, session_id, and iteration count
        """
        self.iteration_count = 1
        initial_message = "Please outline the schedule for the semester according to the course materials in the vector store."
        
        result = await Runner.run(
            self.triage_agent,
            initial_message,
            session=self.session
        )
        
        response = result.final_output
        
        return response
    
    # async def handle_approval_response(self, approved: bool, feedback: Optional[str] = None, max_iterations: int = 5):
    #     """
    #     Handles the approval decision from the frontend.
        
    #     Args:
    #         approved (bool): True if user approves, False if they want changes
    #         feedback (str, optional): Teacher's feedback for requested changes
    #         max_iterations (int): Maximum number of regeneration attempts (default: 5)
            
    #     Returns:
    #         dict: Contains schedule, approval status, iteration count, and message
    #     """
    #     # Check if approved
    #     if approved:
    #         # Fetch the current schedule from session
    #         result = await Runner.run(
    #             self.triage_agent,
    #             "I approve this schedule.",
    #             session_id=self.session_id
    #         )
    #         response = result.final_output
            
    #         return {
    #             "schedule": response.schedule.model_dump(),
    #             "approved": True,
    #             "iteration": self.iteration_count,
    #             "message": "Schedule approved successfully!"
    #         }
        
    #     # Not approved - check if we can regenerate
    #     if self.iteration_count >= max_iterations:
    #         return {
    #             "schedule": None,
    #             "approved": False,
    #             "iteration": self.iteration_count,
    #             "message": f"Maximum iterations ({max_iterations}) reached without approval. Please try again with clearer requirements.",
    #             "error": "max_iterations_reached"
    #         }
        
    #     # Regenerate with feedback
    #     self.iteration_count += 1
        
    #     if feedback:
    #         user_message = f"Please revise the schedule. Here are the requested changes: {feedback}"
    #     else:
    #         user_message = "Please revise the schedule based on my feedback."
        
    #     result = await Runner.run(
    #         self.triage_agent,
    #         user_message,
    #         session=self.session
    #     )
        
    #     response = result.final_output
        
    #     return {
    #         "schedule": response.schedule.model_dump(),
    #         "approved": False,
    #         "iteration": self.iteration_count,
    #         "message": f"Schedule regenerated (iteration {self.iteration_count}). Please review the changes."
    #     }
# Multi-Agent Grading System
class GradingInput(BaseModel):
    submission: str = Field(description="The student's submission")
    rubric: Dict[str, Any] = Field(description="The grading rubric")
    skills: List[str] = Field(description="Skills being assessed")
    instructions: str = Field(description="Assignment instructions")

class NumericalGrade(BaseModel):
    criteria_scores: Dict[str, int] = Field(description="Score for each rubric criterion")
    total_score: int = Field(description="Total numerical score")
    max_possible: int = Field(description="Maximum possible points")

class StudentFeedback(BaseModel):
    feedback: str = Field(description="Constructive feedback for the student")

class SkillMastery(BaseModel):
    skill_mastery: Dict[str, float] = Field(description="Skill mastery levels (0.0-1.0)")

class HomeworkRecommendation(BaseModel):
    changes_recommended: bool = Field(description="Whether changes are recommended")
    recommended_changes: Optional[List[str]] = Field(description="Specific change recommendations")

class GradingOrchestrator:
    def __init__(self):
        # Sub-agents for different grading tasks
        self.numerical_agent = Agent(
            name="Numerical Grading Agent",
            instructions="""You are a numerical grading specialist. Analyze the student submission against the provided rubric.
            
            For each criterion in the rubric:
            1. Evaluate the submission's performance on that criterion
            2. Assign a numerical score based on the rubric scale
            3. Be fair but rigorous in your assessment
            
            Calculate the total score and maximum possible points.""",
            model="gpt-5",
            output_type=NumericalGrade
        )
        
        self.feedback_agent = Agent(
            name="Feedback Generation Agent", 
            instructions="""You are a feedback specialist focused on student growth. Based on the numerical scores and submission:
            
            1. Provide constructive, encouraging feedback
            2. Highlight specific strengths in the work
            3. Identify areas for improvement with actionable suggestions
            4. Maintain a supportive, educational tone
            5. Reference specific parts of the submission
            
            Your feedback should help the student understand their performance and how to improve.""",
            model="gpt-5",
            output_type=StudentFeedback
        )
        
        self.mastery_agent = Agent(
            name="Skill Mastery Assessment Agent",
            instructions="""You are a skill assessment specialist. Analyze the student's demonstration of target skills.
            
            For each skill:
            1. Evaluate evidence of mastery in the submission (0.0 = no evidence, 1.0 = full mastery)
            2. Consider the quality and depth of skill demonstration
            3. Be objective and evidence-based in your assessment
            
            Focus on what the student has actually demonstrated, not potential or effort.""",
            model="gpt-5", 
            output_type=SkillMastery
        )
        
        self.adaptation_agent = Agent(
            name="Homework Adaptation Agent",
            instructions="""You are a curriculum adaptation specialist. Based on skill gaps and performance patterns:
            
            1. Determine if homework changes are needed (threshold: skill mastery < 0.7 or total score < 70%)
            2. If changes needed, recommend specific adaptations:
               - Difficulty adjustments (easier/harder)
               - Additional practice areas
               - Different learning approaches
               - Prerequisite skill reinforcement
            
            Only recommend changes when there's clear evidence of need.""",
            model="gpt-5",
            output_type=HomeworkRecommendation
        )

    async def grade_submission(self, grading_input: GradingInput) -> GradingResult:
        """Orchestrate the full grading process using multiple specialized agents"""
        
        # Step 1: Numerical grading
        numerical_result = await Runner.run(
            self.numerical_agent,
            f"""Grade this submission:
            
            Instructions: {grading_input.instructions}
            Rubric: {json.dumps(grading_input.rubric, indent=2)}
            Submission: {grading_input.submission}"""
        )
        numerical_grade = numerical_result.final_output
        
        # Step 2: Generate feedback based on numerical results
        feedback_result = await Runner.run(
            self.feedback_agent,
            f"""Generate feedback for this submission:
            
            Submission: {grading_input.submission}
            Scores: {numerical_grade.criteria_scores}
            Total Score: {numerical_grade.total_score}/{numerical_grade.max_possible}
            Rubric: {json.dumps(grading_input.rubric, indent=2)}"""
        )
        student_feedback = feedback_result.final_output
        
        # Step 3: Assess skill mastery
        mastery_result = await Runner.run(
            self.mastery_agent,
            f"""Assess skill mastery for:
            
            Target Skills: {grading_input.skills}
            Submission: {grading_input.submission}
            Performance Score: {numerical_grade.total_score}/{numerical_grade.max_possible}"""
        )
        skill_mastery = mastery_result.final_output
        
        # Step 4: Determine homework adaptations (handoff to adaptation agent)
        adaptation_result = await Runner.run(
            self.adaptation_agent,
            f"""Analyze need for homework changes:
            
            Skill Mastery: {skill_mastery.skill_mastery}
            Total Score: {numerical_grade.total_score}/{numerical_grade.max_possible}
            Performance: {numerical_grade.criteria_scores}"""
        )
        homework_rec = adaptation_result.final_output
        
        # Combine results into final grading result
        return GradingResult(
            numerical_grade=numerical_grade.total_score,
            feedback=student_feedback.feedback,
            skill_mastery=skill_mastery.skill_mastery,
            homework_changes_recommended=homework_rec.changes_recommended,
            recommended_changes=homework_rec.recommended_changes
        )

class TeacherFeedbackResponse(BaseModel):
    response: str = Field(description="Response to the teacher")
    suggested_change: Optional[str] = Field(description="Suggested change to student profile or quests")

class TeacherFeedbackAgent:
    """Simplified agent for handling teacher feedback conversations only"""
    
    def __init__(self, student, quests, session_id=None):
        self.student = student
        self.quests = quests
        self.session_id = session_id
        self.agent = Agent(
            name="Teacher Feedback Agent",
            instructions="""You are an educational assistant that helps teachers provide feedback about students.
            
            Your role:
            1. Ask the teacher what they've noticed about the student
            2. Discuss what changes they'd like to make to the student's profile or future quests
            3. Help update student profiles based on teacher observations
            4. Suggest quest modifications based on teacher feedback
            
            When you have enough information to suggest a specific change, include it in the suggested_change field.
            Otherwise, leave suggested_change as null and continue the conversation.
            
            Keep conversations collaborative and focused on student improvement.
            Ask specific questions to gather actionable insights.""",
            model="gpt-5",
            output_type=TeacherFeedbackResponse
        )

    async def initiate(self):
        student_name = f"{self.student.get('first_name', '')} {self.student.get('last_name', '')}"
        initial_message = f"You are talking to a teacher about {student_name}. The student's current profile and quest information has been provided. Ask the teacher what they've noticed about this student."
        
        result = await Runner.run(
            self.agent,
            initial_message,
            session_id=self.session_id
        )
        
        response = result.final_output
        # Session management simplified for demo
        
        return {
            "response": response.response,
            "suggested_change": response.suggested_change,
            "session_id": self.session_id
        }

    async def cont_conv(self, user_input):
        result = await Runner.run(
            self.agent,
            user_input
        )
        
        response = result.final_output
        
        return {
            "response": response.response,
            "suggested_change": response.suggested_change
        }

    def approve_change(self, suggested_change: str) -> str:
        """Hard-coded function for teacher to approve a suggested change"""
        # In a real implementation, this would apply the change to the student profile/quests
        return f"Change approved and applied: {suggested_change}"

    def continue_conversation(self) -> str:
        """Hard-coded function for teacher to continue refining the change"""
        return "Please provide more details or adjustments to the suggested change."


