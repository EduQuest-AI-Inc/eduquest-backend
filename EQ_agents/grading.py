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
        self.grading_agent = Agent(
            name="Grading Agent",
            instructions="You are a grading agent that grades a student's quest submission.",
            model="gpt-4.1",
            tools=[
                FileSearchTool(
                    vector_store_ids=[self.vector_store])])

    async def grade_quest(self, quest):
        pass