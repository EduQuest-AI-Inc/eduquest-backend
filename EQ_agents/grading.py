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

class GradingAgent:
    def __init__(self, student, period, quest, submission, timeout_seconds=300):
        self.student = student
        self.period = period
        self.quest = quest
        self.submission = submission
        self.timeout_seconds = timeout_seconds
        self.vector_store = period["vector_store_id"]
        self.grading_agent = Agent(
            name="Grading Agent",
            instructions="You are a grading agent that grades a student's quest submission.",
            model="gpt-5",
            tools=[
                FileSearchTool(
                    vector_store_ids=[self.vector_store])],
            handoffs=[self.feedback_agent])
        self.feedback_agent = Agent(
            name="Feedback Agent",
            instructions="You are a feedback agent that provides feedback on a student's quest submission.",
            model="gpt-5",
            tools=[
                FileSearchTool(
                    vector_store_ids=[self.vector_store])])


    async def grade_quest(self, quest):
        pass
