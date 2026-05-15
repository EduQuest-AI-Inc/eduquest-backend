"""
Shared student safety guardrails for EQ agents.

Provides input and output guardrails for student-facing agents to check
for inappropriate content, jailbreak attempts, and prompt injection.
"""
import os
from types import SimpleNamespace
from openai import OpenAI
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from agents import (
    Agent,
    Runner,
    custom_span,
    input_guardrail,
    output_guardrail,
    GuardrailFunctionOutput,
    RunContextWrapper,
    MessageOutputItem,
    TResponseInputItem,
)
from bots.model_config import STUDENT_SAFETY_MODEL
from bots.tracing import build_trace_run_config
try:
    from guardrails.runtime import load_config_bundle, instantiate_guardrails, run_guardrails
    _HAS_GUARDRAILS_RUNTIME = True
except ImportError:
    _HAS_GUARDRAILS_RUNTIME = False

load_dotenv()

# Guardrails OpenAI client
guardrails_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
guardrails_ctx = SimpleNamespace(guardrail_llm=guardrails_client)

# Guardrails configuration for student input checking
student_input_guardrails_config = {
    "guardrails": [
        {
            "name": "Moderation",
            "config": {
                "categories": [
                    "sexual", "sexual/minors", "hate", "hate/threatening",
                    "harassment", "harassment/threatening",
                    "self-harm", "self-harm/intent", "self-harm/instructions",
                    "violence", "violence/graphic", "illicit", "illicit/violent",
                ]
            },
        },
        {
            "name": "Jailbreak",
            "config": {"model": STUDENT_SAFETY_MODEL, "confidence_threshold": 0.7},
        },
        {
            "name": "Prompt Injection Detection",
            "config": {"model": STUDENT_SAFETY_MODEL, "confidence_threshold": 0.7},
        },
        {
            "name": "Custom Prompt Check",
            "config": {
                "system_prompt_details": "Raise the guardrail if user expresses any experience of abuse.",
                "model": STUDENT_SAFETY_MODEL,
                "confidence_threshold": 0.7,
            },
        },
    ]
}


def student_guardrails_has_tripwire(results):
    """Check if any guardrail result triggered a tripwire."""
    return any(
        (hasattr(r, "tripwire_triggered") and (r.tripwire_triggered is True))
        for r in (results or [])
    )


async def check_student_input_with_guardrails(input_text: str) -> dict:
    """Run input guardrails on student text and return results.

    If the guardrails.runtime package is not installed, returns safe by default.
    Install the guardrails package to enable full input checking.
    """
    if not _HAS_GUARDRAILS_RUNTIME:
        return {"results": [], "has_tripwire": False}

    results = await run_guardrails(
        guardrails_ctx,
        input_text,
        "text/plain",
        instantiate_guardrails(load_config_bundle(student_input_guardrails_config)),
        suppress_tripwire=True,
        raise_guardrail_errors=True,
    )
    has_tripwire = student_guardrails_has_tripwire(results)
    return {"results": results, "has_tripwire": has_tripwire}


# --- Pydantic model for safety check results ---

class SafetyCheck(BaseModel):
    is_safe: bool = Field(description="Whether the content is safe for students")
    reason: str = Field(description="Reason if content is not safe")


# --- Input guardrail for student messages ---

@input_guardrail
async def check_student_input_safety(
    ctx: RunContextWrapper[None],
    agent: Agent,
    input_str: str | list[TResponseInputItem],
) -> GuardrailFunctionOutput:
    """Check if student input contains inappropriate content using LLM."""
    safety_agent = Agent(
        name="Input Safety Checker",
        instructions="""You are a content safety moderator for educational platforms.
        Analyze the student message and determine if it's appropriate for educational settings.
        Check for inappropriate language, violence, hate speech, sexual content, bullying,
        self-harm references, or illegal activities.

        Return is_safe as true if appropriate, false if inappropriate.
        If not safe, provide a brief reason.""",
        model=STUDENT_SAFETY_MODEL,
        output_type=SafetyCheck,
    )
    with custom_span("student_input_safety_check", data={"input_type": type(input_str).__name__}):
        result = await Runner.run(
            safety_agent,
            input_str,
            context=ctx.context,
            run_config=build_trace_run_config(
                workflow_name="student_input_safety_check",
                metadata={"guardrail_type": "input"},
            ),
        )
    return GuardrailFunctionOutput(
        output_info=result.final_output,
        tripwire_triggered=not result.final_output.is_safe,
    )


# --- Output guardrail for agent responses ---

@output_guardrail
async def check_student_output_safety(
    ctx: RunContextWrapper,
    agent: Agent,
    output: MessageOutputItem,
) -> GuardrailFunctionOutput:
    """Ensure output content is safe and appropriate for students using LLM."""
    safety_agent = Agent(
        name="Output Safety Checker",
        instructions="""You are a content safety moderator for educational platforms.
        Analyze the AI response to ensure it's appropriate for students.
        Check for age-appropriate language, educational content, no harmful/inappropriate content,
        and supportive tone.

        Return is_safe as true if appropriate, false if needs modification.
        If not safe, provide a brief reason.""",
        model=STUDENT_SAFETY_MODEL,
        output_type=SafetyCheck,
    )
    content = output.response if hasattr(output, "response") else str(output)
    with custom_span("student_output_safety_check", data={"output_type": type(output).__name__}):
        result = await Runner.run(
            safety_agent,
            content,
            context=ctx.context,
            run_config=build_trace_run_config(
                workflow_name="student_output_safety_check",
                metadata={"guardrail_type": "output"},
            ),
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
