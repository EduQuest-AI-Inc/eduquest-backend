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
    guardrail_span, 
    SQLiteSession
)
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX
import json
from openai import vector_stores
from pydantic import BaseModel, Field
from typing import Dict, Any
import asyncio
from models.period import Period
from models.rubric import Rubric, Scale
from agent import *

functions = [
    {   
        "type": "function",
        "function":{
            "name": "list_buckets",
            "description": "List all available S3 buckets",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function":{
            "name": "list_objects",
            "description": "List the objects or files inside a given S3 bucket",
            "parameters": {
                "type": "object",
                "properties": {
                    "bucket": {"type": "string", "description": "The name of the S3 bucket"},
                    "prefix": {"type": "string", "description": "The folder path in the S3 bucket"},
                },
                "required": ["bucket"],
            },
        }
    },
    {   
        "type": "function",
        "function":{
            "name": "download_file",
            "description": "Download a specific file from an S3 bucket to a local distribution folder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bucket": {"type": "string", "description": "The name of the S3 bucket"},
                    "key": {"type": "string", "description": "The path to the file inside the bucket"},
                    "directory": {"type": "string", "description": "The local destination directory to download the file, should be specificed by the user."},
                },
                "required": ["bucket", "key", "directory"],
            }
        }
    },
    {
        "type": "function",
        "function":{
            "name": "upload_file",
            "description": "Upload a file to an S3 bucket",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "The local source path or remote URL"},
                    "bucket": {"type": "string", "description": "The name of the S3 bucket"},
                    "key": {"type": "string", "description": "The path to the file inside the bucket"},
                    "is_remote_url": {"type": "boolean", "description": "Is the provided source a URL (True) or local path (False)"},
                },
                "required": ["source", "bucket", "key", "is_remote_url"],
            }
        }
    },
    {
        "type": "function",
        "function":{
            "name": "search_s3_objects",
            "description": "Search for a specific file name inside an S3 bucket",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_name": {"type": "string", "description": "The name of the file you want to search for"},
                    "bucket": {"type": "string", "description": "The name of the S3 bucket"},
                    "prefix": {"type": "string", "description": "The folder path in the S3 bucket"},
                    "exact_match": {"type": "boolean", "description": "Set exact_match to True if the search should match the exact file name. Set exact_match to False to compare part of the file name string (the file contains)"}
                },
                "required": ["search_name"],
            },
        }
    }
]

# def 

class GradingAgent:
    def __init__(self, student, period, quest, submission, timeout_seconds=300):
        self.student = student
        self.period = period
        self.quest = quest
        self.submission = submission
        self.timeout_seconds = timeout_seconds
        self.vector_store = period["vector_store_id"]
        self.triage = Agent(
            name="Triage GradingAgent",
            instructions="You are a triage agent that handles the ",
            model="gpt-5",
            tools=[
                FileSearchTool(
                    vector_store_ids=[self.vector_store])],
            handoffs=[self.feedback_agent, self.grading_agent, self.update_agent])
        self.feedback_agent = Agent(
            name="Feedback Agent",
            instructions="You are a feedback agent that provides feedback on a student's quest submission.",
            model="gpt-5",
            tools=[
                FileSearchTool(
                    vector_store_ids=[self.vector_store])])
        self.grading_agent = Agent(
            name="Grading Agent",
            instructions="You are a rubric grading agent that grades a student's quest submission based on a rubric.",
            model="gpt-5",
            tools=[
                FileSearchTool(
                    vector_store_ids=[self.vector_store])])
        self.update_agent = Agent(
            name="Update Agent",
            instructions="""
            You specialize in identifying the student's weaknesses in the skills they are practicing through the quest.
            You will then provide recommendations for changes to future quests""",
            model="gpt-5",
            tools=[
                FileSearchTool(
                    vector_store_ids=[self.vector_store])])
        
        

    async def grade_quest(self, quest):
        pass
