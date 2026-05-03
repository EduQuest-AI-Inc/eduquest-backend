from pydantic import BaseModel, Field


class InstructionStep(BaseModel):
    step: int = Field(description="Step number, starting from 1")
    text: str = Field(description="Clear, actionable instruction text for this step. Plain prose only — no markdown, no escape sequences like \\n, no asterisks, no carets.")


class Instructions(BaseModel):
    steps: list[InstructionStep] = Field(description="Ordered list of steps to complete the quest")
