#!/usr/bin/env python3
"""
Manual integration test for the schedule generation pipeline:
  CoverageEvaluator → PerplexityService (deep-research) → PeriodScheduleAgent

This is a standalone script — NOT collected by pytest (conftest mocks would
break the real OpenAI/Perplexity calls). Run directly:

    cd eduquest-backend
    source venv/bin/activate
    python tests/scripts/test_schedule_pipeline.py

    # To skip the live OpenAI schedule agent call (steps 1 & 2 still run live):
    MOCK_AI=true python tests/scripts/test_schedule_pipeline.py

    # Tweak these constants below to test different courses / descriptions.

Requirements:
    OPENAI_API_KEY     — for CoverageEvaluator (gpt-4o-mini)
    PERPLEXITY_API_KEY — for PerplexityService (deep-research preset)
"""
import asyncio
import os
import sys
from pathlib import Path

# Load .env before any imports that read env vars
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env", override=False)

# Ensure eduquest-backend is on the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# ── Configure your test here ─────────────────────────────────────────────────
COURSE_NAME = "AP US History"
COURSE_DESCRIPTION = "This is a history class."   # thin → triggers research
GRADE_LEVEL = "11th grade"
START_DATE = "2025-09-01"
END_DATE = "2026-01-15"
MAX_RESEARCH_QUERIES = 2   # limit for speed; real usage can use all queries
MAX_PERPLEXITY_STEPS = 5   # 1-10; lower = faster, less thorough
# ─────────────────────────────────────────────────────────────────────────────


def _check(condition: bool, label: str) -> None:
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        sys.exit(1)


async def main() -> None:
    from bots.coverage_evaluator import CoverageEvaluator
    from integrations.perplexity_service import PerplexityService
    from bots.schedule_agent import PeriodScheduleAgent, PeriodScheduleSchema

    # ── Step 1: Coverage evaluation ───────────────────────────────────────────
    print("\n=== Step 1: Coverage Evaluation ===")
    ev = CoverageEvaluator()
    cov = ev.evaluate(
        course_name=COURSE_NAME,
        course_description=COURSE_DESCRIPTION,
        has_files=False,
        grade_level=GRADE_LEVEL,
    )
    print(f"  sufficient     : {cov.sufficient}")
    print(f"  gaps           : {cov.gaps}")
    print(f"  research_queries ({len(cov.research_queries)}): {cov.research_queries}")
    _check(isinstance(cov.sufficient, bool), "sufficient is bool")
    _check(isinstance(cov.gaps, list), "gaps is list")
    _check(isinstance(cov.research_queries, list), "research_queries is list")

    # ── Step 2: Perplexity deep research (only when coverage insufficient) ────
    research_context: str | None = None
    if not cov.sufficient and cov.research_queries:
        print(f"\n=== Step 2: Perplexity Deep Research ({MAX_RESEARCH_QUERIES} queries, {MAX_PERPLEXITY_STEPS} steps each) ===")
        svc = PerplexityService()
        queries = cov.research_queries[:MAX_RESEARCH_QUERIES]
        print(f"  Queries: {queries}")
        research_context = await svc.research(queries, max_steps=MAX_PERPLEXITY_STEPS)
        print(f"  Research context: {len(research_context)} chars")
        print(f"  Preview: {research_context[:300]}...")
        _check(len(research_context) > 100, "research context is non-empty")
    else:
        print("\n=== Step 2: Perplexity Deep Research — SKIPPED (coverage sufficient) ===")

    # ── Step 3: Schedule agent ────────────────────────────────────────────────
    mock = os.environ.get("MOCK_AI", "").lower() in ("true", "1", "yes")
    print(f"\n=== Step 3: Schedule Agent ({'MOCK' if mock else 'LIVE — calls OpenAI'}) ===")

    if mock:
        from bots.provider import get_bot_provider, set_bot_provider
        set_bot_provider(None)
        os.environ["MOCK_AI"] = "true"
        agent = get_bot_provider().create_schedule_agent(
            course_name=COURSE_NAME,
            course_description=COURSE_DESCRIPTION,
            start_date=START_DATE,
            end_date=END_DATE,
            research_context=research_context,
        )
    else:
        agent = PeriodScheduleAgent(
            vector_store_ids=[],
            course_name=COURSE_NAME,
            course_description=COURSE_DESCRIPTION,
            start_date=START_DATE,
            end_date=END_DATE,
            research_context=research_context,
        )

    if hasattr(agent, "run_and_get_json_async"):
        data = await agent.run_and_get_json_async()
    else:
        data = agent.run_and_get_json()
    parsed = PeriodScheduleSchema.model_validate(data)

    print(f"  Weeks: {len(parsed.weeks)}")
    for w in parsed.weeks[:3]:
        print(f"  Week {w.week_number} ({w.start_date} → {w.end_date}): {len(w.lessons)} lessons")
        for lesson in w.lessons:
            total_skills = sum(len(c.skills) for c in lesson.concepts)
            print(f"    {lesson.lesson_name} — {len(lesson.concepts)} concepts, {total_skills} skills")
            for concept in lesson.concepts:
                for skill in concept.skills:
                    print(f"      [{skill.bloom_level}/{skill.difficulty}] {skill.skill_name}")

    _check(len(parsed.weeks) > 0, "schedule has weeks")
    _check(all(len(w.lessons) > 0 for w in parsed.weeks), "every week has lessons")
    _check(
        all(len(c.skills) > 0 for w in parsed.weeks for lesson in w.lessons for c in lesson.concepts),
        "every concept has skills",
    )
    _check(
        all(
            s.bloom_level in ("Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create")
            for w in parsed.weeks for lesson in w.lessons for c in lesson.concepts for s in c.skills
        ),
        "all bloom_levels are valid",
    )
    _check(
        all(
            s.difficulty in ("beginner", "intermediate", "advanced")
            for w in parsed.weeks for lesson in w.lessons for c in lesson.concepts for s in c.skills
        ),
        "all difficulties are valid",
    )

    print("\n=== ALL CHECKS PASSED ===\n")


if __name__ == "__main__":
    asyncio.run(main())
