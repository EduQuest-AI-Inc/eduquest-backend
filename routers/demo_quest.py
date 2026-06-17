"""
Public demo endpoint — no auth required.

POST /demo/quest is intentionally disabled during the privacy-safe redesign.
The landing page renders a fictional static preview instead.
"""
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.post("/quest", response_model=dict[str, Any])
async def generate_demo_quest():
    raise HTTPException(
        status_code=410,
        detail="The interactive demo is unavailable while its privacy-safe redesign is completed.",
    )
