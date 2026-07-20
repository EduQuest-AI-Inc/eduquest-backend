"""
MisconceptionSeeder — converts raw misconception strings to structured records
via a single structured-output LLM call. No Agent overhead; no DB access.
The service layer is responsible for writing the returned dicts to MisconceptionDAO.
"""
from __future__ import annotations

import logging

import openai
from pydantic import BaseModel

from bots.model_config import RESOLVER_JUDGE_MODEL

logger = logging.getLogger(__name__)


class _MisconceptionRecord(BaseModel):
    signature: str
    remediation_strategy: str


class _SeedResult(BaseModel):
    misconceptions: list[_MisconceptionRecord]


class MisconceptionSeeder:
    """
    Single structured OpenAI call (no Agent overhead).
    Takes a list of raw misconception strings and returns structured dicts
    suitable for inserting into the misconception table.
    """

    def __init__(self) -> None:
        self._oai = openai.OpenAI()

    def seed(self, misconceptions: list[str], context: str = "") -> list[dict]:
        """
        Returns list of {signature, remediation_strategy} dicts.
        Returns [] if input is empty or the LLM call fails.
        """
        if not misconceptions:
            return []
        try:
            resp = self._oai.beta.chat.completions.parse(
                model=RESOLVER_JUDGE_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Convert each educational misconception into a structured record. "
                            "signature: a concise, searchable description of the wrong belief "
                            "(keep it ≤ 20 words). "
                            "remediation_strategy: a 1-2 sentence teaching approach to address it."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Skill context: {context}\n"
                            f"Misconceptions to structure: {misconceptions}"
                        ),
                    },
                ],
                response_format=_SeedResult,
            )
            result = resp.choices[0].message.parsed
            return [
                {"signature": r.signature, "remediation_strategy": r.remediation_strategy}
                for r in result.misconceptions
            ]
        except Exception:
            logger.warning("MisconceptionSeeder.seed failed for context=%r", context)
            return []
