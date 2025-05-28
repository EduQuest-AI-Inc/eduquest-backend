from EQ_agents.agent import *
from models.period import Period
from models.student_profile import student_profile
import asyncio
from agents import Agent, Runner, guardrail_span
import os
from dotenv import load_dotenv
import openai
from openai import OpenAI

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

golden = student_profile(
    first_name="Golden",
    last_name="Huang",
    age=16,
    gender="Male",
    grade=10,
    strength="math, computer science",
    weakness="history, physical education",
    interest="golfing and statistics",
    learning_style="visual",
    long_term_goal="Create a visual data analysis project focused on golf statistics using key topics from your pre-calculus course such as functions, graphs, sequences & series, probability, and matrices. For example, collect or simulate golf performance data (e.g., scores, shot distances, angles) and apply function transformations and graphing to model player performance trends. Use sequences and series to analyze scoring patterns, probability concepts to evaluate shot success rates, and matrix operations to manage multivariate data. Present your findings with clear visualizations leveraging your visual learning style.")

pre_calc = Period(
    period_id="period_1",
    initial_conversation_assistant_id="assistant_1",
    update_assistant_id="assistant_2",
    teacher_id="teacher_1",
    vector_store_id="vs_682cfbf6f3a88191bfde8d520e939fd6",
    course="course_1")

schedule_agent = SchedulesAgent(golden, pre_calc)


# async


# --- Main Function ---
async def main():
    result = await Runner.run(schedule_agent.schedules_agent, schedule_agent.input)
    return(result.final_output)


if __name__ == "__main__":
    print(asyncio.run(main()))