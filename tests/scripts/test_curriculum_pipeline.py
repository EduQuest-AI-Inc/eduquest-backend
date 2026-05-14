#!/usr/bin/env python3
"""
Manual integration test for the full curriculum creation pipeline:

  Stage 1: CoverageEvaluator    — is the course description sufficient?
  Stage 2: PerplexityService    — deep-research to fill curriculum gaps
  Stage 3: PeriodScheduleAgent  — generate Week→Lesson→Concept→Skill schedule
  Stage 4: Quest entry building — simulate teacher selecting quest-enabled weeks
  Stage 5: HWAgent              — generate per-student quests (instructions + rubric)

This is a standalone script — NOT collected by pytest (conftest mocks would
break the real OpenAI/Perplexity calls). Run directly:

    cd eduquest-backend
    source venv/bin/activate
    python tests/scripts/test_curriculum_pipeline.py

    # Fast mode — mocks OpenAI schedule + HW agent; Perplexity still runs live:
    MOCK_AI=true python tests/scripts/test_curriculum_pipeline.py

Requirements:
    OPENAI_API_KEY     — for CoverageEvaluator (gpt-4o-mini) and HWAgent
    PERPLEXITY_API_KEY — for PerplexityService (deep-research preset)
"""
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env", override=False)

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# ── Configure your test here ─────────────────────────────────────────────────
COURSE_NAME = "AP US History"
COURSE_DESCRIPTION = "This is a history class."   # thin → triggers Perplexity research
GRADE_LEVEL = "11th grade"
START_DATE = "2025-09-01"
END_DATE = "2026-01-15"
QUEST_ENABLED_WEEKS = [1, 2]    # which weeks the teacher enables for quests
MAX_RESEARCH_QUERIES = 2        # limit for speed; increase to use all returned queries
MAX_PERPLEXITY_STEPS = 5        # 1–10; higher = more thorough but slower
# ─────────────────────────────────────────────────────────────────────────────

MOCK_MODE = os.environ.get("MOCK_AI", "").lower() in ("true", "1", "yes")

# Mock student and period used for HWAgent (no DB needed)
MOCK_STUDENT = {
    "user_id": "test-student-001",
    "name": "Test Student",
    "grade_level": GRADE_LEVEL,
}
MOCK_PERIOD = {
    "period_id": "test-period-001",
    "name": COURSE_NAME,
    "vector_store_id": "vs-mock-000",  # HWAgent reads this but MockHWAgent ignores it
    "owner_id": "test-teacher-001",
}


def _check(condition: bool, label: str) -> None:
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        sys.exit(1)


def _build_quest_entries(schedule: dict, enabled_weeks: list) -> list:
    """
    Build quest entry dicts from the new Week→Lesson→Concept→Skill schema.
    Simulates what PeriodQuestService.start_homework_agent() will do once
    updated to handle the new schema format.
    """
    entries = []
    for week in schedule.get("weeks", []):
        week_num = week["week_number"]
        if week_num not in enabled_weeks:
            continue
        lessons = week.get("lessons", [])
        lesson_names = [lesson["lesson_name"] for lesson in lessons]
        skills = [
            s["skill_name"]
            for lesson in lessons
            for c in lesson.get("concepts", [])
            for s in c.get("skills", [])
        ]
        entries.append({
            "Name": f"Week {week_num}: " + "; ".join(lesson_names[:3]),
            "Skills": "; ".join(skills) if skills else "Practice skills from this week",
            "Week": week_num,
        })
    return entries


async def main() -> None:
    from bots.curriculum.coverage_evaluator import CoverageEvaluator
    from integrations.perplexity_service import PerplexityService
    from bots.schedule_agent import PeriodScheduleAgent, PeriodScheduleSchema

    # ── Stage 1: Coverage Evaluation ─────────────────────────────────────────
    print("\n" + "="*60)
    print("STAGE 1: Coverage Evaluation")
    print("="*60)

    ev = CoverageEvaluator()
    cov = ev.evaluate(
        course_name=COURSE_NAME,
        course_description=COURSE_DESCRIPTION,
        has_files=False,
        grade_level=GRADE_LEVEL,
    )
    print(f"  sufficient      : {cov.sufficient}")
    print(f"  gaps            : {cov.gaps}")
    print(f"  research_queries: {cov.research_queries}")

    _check(isinstance(cov.sufficient, bool), "sufficient is bool")
    _check(isinstance(cov.gaps, list), "gaps is list")
    _check(isinstance(cov.research_queries, list), "research_queries is list")

    # ── Stage 2: Perplexity Deep Research ────────────────────────────────────
    research_context: str | None = None

    if not cov.sufficient and cov.research_queries:
        print("\n" + "="*60)
        print(f"STAGE 2: Perplexity Deep Research ({MAX_RESEARCH_QUERIES} queries, {MAX_PERPLEXITY_STEPS} steps each)")
        print("="*60)

        svc = PerplexityService()
        queries = cov.research_queries[:MAX_RESEARCH_QUERIES]
        print(f"  Queries: {queries}")

        research_context = await svc.research(queries, max_steps=MAX_PERPLEXITY_STEPS)
        print(f"  Research context: {len(research_context)} chars")
        print(f"  Preview: {research_context[:300]}...")

        _check(len(research_context) > 100, "research context is non-empty")
    else:
        print("\nSTAGE 2: Perplexity Deep Research — SKIPPED (coverage sufficient)")

    # ── Stage 3: Schedule Generation ─────────────────────────────────────────
    print("\n" + "="*60)
    print(f"STAGE 3: Schedule Generation ({'MOCK' if MOCK_MODE else 'LIVE — calls OpenAI'})")
    print("="*60)

    if MOCK_MODE:
        from bots.provider import MockBotProvider
        schedule_agent = MockBotProvider().create_schedule_agent(
            course_name=COURSE_NAME,
            course_description=COURSE_DESCRIPTION,
            start_date=START_DATE,
            end_date=END_DATE,
            research_context=research_context,
        )
    else:
        schedule_agent = PeriodScheduleAgent(
            vector_store_ids=[],
            course_name=COURSE_NAME,
            course_description=COURSE_DESCRIPTION,
            start_date=START_DATE,
            end_date=END_DATE,
            research_context=research_context,
        )

    if hasattr(schedule_agent, "run_and_get_json_async"):
        schedule_dict = await schedule_agent.run_and_get_json_async()
    else:
        schedule_dict = schedule_agent.run_and_get_json()
    parsed = PeriodScheduleSchema.model_validate(schedule_dict)

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
    valid_bloom = {"Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"}
    _check(
        all(
            s.bloom_level in valid_bloom
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

    # ── Stage 4: Quest Entry Building (simulated teacher selection) ───────────
    print("\n" + "="*60)
    print(f"STAGE 4: Quest Entry Building (teacher enables weeks {QUEST_ENABLED_WEEKS})")
    print("="*60)

    quest_entries = _build_quest_entries(schedule_dict, QUEST_ENABLED_WEEKS)
    for entry in quest_entries:
        print(f"  Week {entry['Week']}: {entry['Name']}")
        print(f"    Skills: {entry['Skills'][:120]}{'...' if len(entry['Skills']) > 120 else ''}")

    _check(len(quest_entries) > 0, "quest entries were built")
    _check(
        all(e.get("Name") and e.get("Skills") and e.get("Week") for e in quest_entries),
        "each quest entry has Name, Skills, Week",
    )
    enabled_in_schedule = [
        w.week_number for w in parsed.weeks if w.week_number in QUEST_ENABLED_WEEKS
    ]
    _check(
        len(quest_entries) == len(enabled_in_schedule),
        f"one quest entry per enabled week ({len(quest_entries)} entries)",
    )

    # ── Stage 5: Quest Generation (HWAgent) ──────────────────────────────────
    print("\n" + "="*60)
    print(f"STAGE 5: Quest Generation — HWAgent ({'MOCK' if MOCK_MODE else 'LIVE — calls OpenAI'})")
    print("="*60)

    if MOCK_MODE:
        from bots.provider import MockBotProvider
        hw_agent = MockBotProvider().create_hw_agent(
            student=MOCK_STUDENT,
            period=MOCK_PERIOD,
            schedule=quest_entries,
        )
    else:
        from bots.quests.quest_agent import HWAgent
        hw_agent = HWAgent(
            student=MOCK_STUDENT,
            period=MOCK_PERIOD,
            schedule=quest_entries,
        )

    quests = hw_agent.run()
    # Normalize to list of dicts
    quest_dicts = []
    for q in quests:
        if hasattr(q, "model_dump"):
            quest_dicts.append(q.model_dump())
        elif isinstance(q, dict):
            quest_dicts.append(q)
        else:
            quest_dicts.append({
                "Name": getattr(q, "Name", ""),
                "Skills": getattr(q, "Skills", ""),
                "Week": getattr(q, "Week", 0),
                "instructions": getattr(q, "instructions", []),
                "rubric": getattr(q, "rubric", {}),
            })

    print(f"  Quests generated: {len(quest_dicts)}")
    for q in quest_dicts:
        print(f"  Week {q.get('Week')}: {q.get('Name')}")
        instructions = q.get("instructions") or []
        print(f"    Instructions: {len(instructions)} steps")
        if instructions:
            print(f"    Step 1: {str(instructions[0])[:100]}")
        rubric = q.get("rubric") or {}
        print(f"    Rubric keys: {list(rubric.keys())[:5]}")

    _check(len(quest_dicts) == len(quest_entries), f"{len(quest_entries)} quest(s) generated")
    _check(
        all(len(q.get("instructions") or []) > 0 for q in quest_dicts),
        "every quest has instructions",
    )
    _check(
        all(len(q.get("rubric") or {}) > 0 for q in quest_dicts),
        "every quest has a rubric",
    )

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("ALL STAGES PASSED")
    print("="*60)
    print(f"  Coverage: sufficient={cov.sufficient}, queries={len(cov.research_queries)}")
    if research_context:
        print(f"  Research: {len(research_context)} chars from {MAX_RESEARCH_QUERIES} Perplexity queries")
    print(f"  Schedule: {len(parsed.weeks)} weeks, {sum(len(w.lessons) for w in parsed.weeks)} lessons")
    print(f"  Quests:   {len(quest_dicts)} quests generated for weeks {QUEST_ENABLED_WEEKS}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
