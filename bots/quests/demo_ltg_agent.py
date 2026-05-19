"""
Demo LTG + Quest agent — single-call, no auth, no tools.

Takes a child's grade and interests and returns one long-term goal plus
four weekly quests. Used by POST /demo/quest on the public landing page.
"""
from pydantic import BaseModel, Field
from agents import Agent

from bots.model_config import DEMO_LTG_MODEL


class DemoQuestItem(BaseModel):
    week: int = Field(description="Week number (1–4)")
    title: str = Field(description="Short, active quest title")
    description: str = Field(description="1–2 sentence description of the concrete deliverable")


class DemoLTGOutput(BaseModel):
    ltg: str = Field(description="One ambitious but achievable 12-week long-term goal that references the child's interests")
    quests: list[DemoQuestItem] = Field(description="Exactly 4 weekly quests (W1–W4) that build toward the goal")


_INSTRUCTIONS = """You are a homeschool learning coach helping parents see what their child could accomplish.

Given a child's grade level, subject, and interests, produce:
1. ONE long-term goal (ltg): a 1–2 sentence statement of what the child will create, investigate, or master over 12 weeks. It must be grounded in the subject, ambitious but realistic for the grade, and must weave in the child's interests directly.
2. FOUR weekly quests (W1–W4): each with an active title and a 1–2 sentence description of the concrete deliverable the child produces that week. Every quest must involve real subject-matter work, not general research. Each quest should build on the previous one toward the goal.

Rules:
- The goal and quests must be unmistakably about the subject — not generic projects with a subject name bolted on.
- Make the goal specific and personally meaningful — avoid generic phrases like "learn about X".
- Quest descriptions must describe a real output (a solved problem set, a proof, an experiment write-up, a coded model, a map, a presentation, etc.).
- Calibrate complexity to the grade level: simpler for K–3, more sophisticated for 9–12.
- Keep the writing warm, encouraging, and parent-readable."""


def create_demo_ltg_agent(grade: str, interests: list[str], subject: str) -> Agent:
    interests_str = ", ".join(interests) if interests else "general learning"
    user_context = f"Grade level: {grade}\nSubject: {subject}\nChild's interests: {interests_str}"

    return Agent(
        name="DemoLTGAgent",
        instructions=f"{_INSTRUCTIONS}\n\n{user_context}",
        model=DEMO_LTG_MODEL,
        output_type=DemoLTGOutput,
    )
