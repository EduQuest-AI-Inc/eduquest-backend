"""
Mock bot implementations for fast testing without OpenAI API calls.

Activated when MOCK_AI=true via bots/provider.py. All classes return
realistic-shaped data (real Pydantic types) so downstream service logic
runs unchanged.
"""
from typing import Any, Optional


class MockRunResult:
    """Duck-typed stand-in for the result returned by agents.Runner.run()."""

    def __init__(self, final_output: Any, last_response_id: str = "mock-response-id-001"):
        self.final_output = final_output
        self.last_response_id = last_response_id


class MockRunner:
    """
    Drop-in replacement for agents.Runner. Dispatches on agent.output_type
    so the right Pydantic response model is returned for each conversation agent.

    ProfileResponse turns (tracked via previous_response_id):
      None / unknown → turn 1: ask about subjects          → mock-response-id-001
      mock-response-id-001 → turn 2: follow-up question    → mock-response-id-002
      mock-response-id-002 → turn 3: complete with profile → mock-response-id-003
    """

    @staticmethod
    async def run(agent: Any, message: str, **kwargs) -> MockRunResult:
        from bots.ltg_agent import LTGResponse
        from bots.profile_agent import ProfileResponse, StudentProfile
        from bots.teacher_feedback_agent import TeacherFeedbackResponse

        output_type = getattr(agent, "output_type", None)

        if output_type is LTGResponse:
            prev = kwargs.get("previous_response_id")
            if prev == "mock-ltg-response-id-001":
                # Turn 2: student picked a goal — confirm and close the conversation
                ltg_payload = LTGResponse(
                    message="[MOCK] Excellent choice! I've selected 'Build a portfolio project that applies core course concepts' as your long-term goal.",
                    goal_1=None,
                    goal_2=None,
                    goal_3=None,
                    chosen_goal="Build a portfolio project that applies core course concepts",
                )
                return MockRunResult(final_output=ltg_payload, last_response_id="mock-ltg-response-id-002")
            # Turn 1 (initiate) — no previous_response_id
            ltg_payload = LTGResponse(
                message="[MOCK] Here are three long-term goal options based on your course. Which one resonates with you?",
                goal_1="Build a portfolio project that applies core course concepts",
                goal_2="Teach a concept you learned to a peer or family member",
                goal_3="Apply a skill from class to solve a real-world problem you care about",
                chosen_goal=None,
            )
            return MockRunResult(final_output=ltg_payload, last_response_id="mock-ltg-response-id-001")

        if output_type is ProfileResponse:
            prev = kwargs.get("previous_response_id")
            if prev == "mock-response-id-001":
                profile_payload = ProfileResponse(
                    response="[MOCK] That's great! Tell me about something you find challenging in school and how you usually like to learn new things.",
                    profile=None,
                )
                return MockRunResult(final_output=profile_payload, last_response_id="mock-response-id-002")
            if prev == "mock-response-id-002":
                profile_payload = ProfileResponse(
                    response="[MOCK] Thanks for sharing! I have everything I need to personalize your experience. Let's get started!",
                    profile=StudentProfile(
                        strengths=["Analytical thinking", "Problem-solving"],
                        weaknesses=["Time management", "Public speaking"],
                        interests=["Technology", "Science"],
                        learning_styles=["Visual", "Hands-on"],
                    ),
                )
                return MockRunResult(final_output=profile_payload, last_response_id="mock-response-id-003")
            # Turn 1 (initiate) — no previous_response_id
            profile_payload = ProfileResponse(
                response="[MOCK] Hi! I'm EduQuest. I'd love to learn more about you. What subjects do you enjoy most?",
                profile=None,
            )
            return MockRunResult(final_output=profile_payload, last_response_id="mock-response-id-001")

        if output_type is TeacherFeedbackResponse:
            feedback_payload = TeacherFeedbackResponse(
                response="[MOCK] Based on the quest data, this student shows strong engagement with hands-on tasks and may benefit from more open-ended challenges.",
                suggested_change=None,
            )
            return MockRunResult(final_output=feedback_payload)

        raise ValueError(f"MockRunner: unrecognized agent output_type {output_type!r}")


class MockHWAgent:
    """Fast replacement for HWAgent — returns one IndividualQuest per schedule item."""

    def __init__(self, student, period, schedule, conversation_id=None, previous_response_id=None):
        self.schedule = schedule

    def run(self) -> list:
        from bots.agent import IndividualQuest

        results = []
        for quest in self.schedule:
            name = quest.get("Name", "Quest") if isinstance(quest, dict) else getattr(quest, "Name", "Quest")
            skills = quest.get("Skills", "") if isinstance(quest, dict) else getattr(quest, "Skills", "")
            week = quest.get("Week", 1) if isinstance(quest, dict) else getattr(quest, "Week", 1)
            results.append(IndividualQuest(
                Name=f"[MOCK] {name}",
                Skills=skills,
                Week=week,
                instructions=[
                    {"step": 1, "text": "[MOCK] Review the week's material carefully."},
                    {"step": 2, "text": "Complete the main activity described in class."},
                    {"step": 3, "text": "Reflect on what you learned and submit your work."},
                ],
                rubric={
                    "Criteria": {
                        "Understanding": {
                            "Score_0": "No attempt",
                            "Score_1": "Minimal understanding",
                            "Score_2": "Partial understanding",
                            "Score_3": "Satisfactory understanding",
                            "Score_4": "Good understanding",
                            "Score_5": "Excellent understanding",
                        }
                    }
                },
            ))
        return results


class MockGradingOrchestrator:
    """Fast replacement for GradingOrchestrator."""

    async def grade_submission(self, grading_input: Any) -> Any:
        from bots.grading_agent import GradingResult

        skill_mastery = {skill: 0.75 for skill in (grading_input.skills or ["general"])}
        return GradingResult(
            numerical_grade=38,
            feedback=(
                "[MOCK] Good effort! Your submission demonstrates solid understanding of the core concepts. "
                "Consider expanding your analysis with more specific examples in future work."
            ),
            skill_mastery=skill_mastery,
            homework_changes_recommended=False,
            recommended_changes=None,
        )


class MockConversationsSession:
    """Duck-typed stand-in for agents.OpenAIConversationsSession."""

    def __init__(self, conversation_id=None):
        self._session_id = conversation_id or "mock-conversation-id-001"


class MockPeriodScheduleAgent:
    """Fast replacement for PeriodScheduleAgent — returns new nested schema shape."""

    def __init__(
        self,
        vector_store_ids: Optional[list] = None,
        course_name: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        course_description: Optional[str] = None,
        research_context: Optional[str] = None,
    ):
        self.course_name = course_name or "Course"
        self.start_date = start_date
        self.end_date = end_date

    def run_and_get_json(self) -> dict:
        return {
            "weeks": [
                {
                    "week_number": 1,
                    "start_date": "Not specified",
                    "end_date": "Not specified",
                    "lessons": [
                        {
                            "lesson_name": f"[MOCK] Introduction to {self.course_name}",
                            "concepts": [
                                {
                                    "concept_name": "Course Overview",
                                    "description": f"Foundational introduction to {self.course_name} and its key themes.",
                                    "prerequisites": [],
                                    "common_misconceptions": [
                                        "Students often assume prior knowledge is required."
                                    ],
                                    "key_takeaways": [
                                        f"{self.course_name} builds on logical reasoning.",
                                        "Active participation improves outcomes.",
                                    ],
                                    "skills": [
                                        {
                                            "skill_name": "Identify Core Vocabulary",
                                            "description": "Recognize and define key terms used throughout the course.",
                                            "bloom_level": "Remember",
                                            "difficulty": "beginner",
                                            "mastery_criteria": {
                                                "descriptor": "Student can correctly define at least 80% of core vocabulary terms.",
                                                "passing_score": 0.8,
                                            },
                                        }
                                    ],
                                }
                            ],
                        },
                        {
                            "lesson_name": "[MOCK] Key Themes and Objectives",
                            "concepts": [
                                {
                                    "concept_name": "Learning Objectives",
                                    "description": "Understanding the goals and expectations for the course.",
                                    "prerequisites": ["Course Overview"],
                                    "common_misconceptions": [
                                        "Objectives are merely administrative — they don't guide daily learning."
                                    ],
                                    "key_takeaways": [
                                        "Clear objectives focus effort.",
                                        "Objectives align assessments with instruction.",
                                    ],
                                    "skills": [
                                        {
                                            "skill_name": "Interpret Learning Goals",
                                            "description": "Explain course objectives in their own words.",
                                            "bloom_level": "Understand",
                                            "difficulty": "beginner",
                                            "mastery_criteria": {
                                                "descriptor": "Student can paraphrase each major course objective accurately.",
                                                "passing_score": 0.75,
                                            },
                                        }
                                    ],
                                }
                            ],
                        },
                    ],
                },
                {
                    "week_number": 2,
                    "start_date": "Not specified",
                    "end_date": "Not specified",
                    "lessons": [
                        {
                            "lesson_name": "[MOCK] Deep Dive into Primary Topics",
                            "concepts": [
                                {
                                    "concept_name": "Core Principles",
                                    "description": "The foundational principles that underpin the subject area.",
                                    "prerequisites": ["Course Overview", "Learning Objectives"],
                                    "common_misconceptions": [
                                        "Core principles are abstract and not practically useful."
                                    ],
                                    "key_takeaways": [
                                        "Principles provide a framework for solving novel problems.",
                                        "Mastery requires both recall and application.",
                                    ],
                                    "skills": [
                                        {
                                            "skill_name": "Apply Core Principles",
                                            "description": "Use foundational principles to solve structured problems.",
                                            "bloom_level": "Apply",
                                            "difficulty": "intermediate",
                                            "mastery_criteria": {
                                                "descriptor": "Student can apply core principles correctly to at least 3 worked examples.",
                                                "passing_score": 0.8,
                                            },
                                        },
                                        {
                                            "skill_name": "Analyze Principle Relationships",
                                            "description": "Identify how core principles interact and depend on each other.",
                                            "bloom_level": "Analyze",
                                            "difficulty": "intermediate",
                                            "mastery_criteria": {
                                                "descriptor": "Student can diagram relationships between at least 2 core principles.",
                                                "passing_score": 0.75,
                                            },
                                        },
                                    ],
                                }
                            ],
                        },
                        {
                            "lesson_name": "[MOCK] Guided Practice and Discussion",
                            "concepts": [
                                {
                                    "concept_name": "Collaborative Problem Solving",
                                    "description": "Using peer discussion to deepen understanding of course material.",
                                    "prerequisites": ["Core Principles"],
                                    "common_misconceptions": [
                                        "Group work means one person does all the thinking."
                                    ],
                                    "key_takeaways": [
                                        "Articulating reasoning strengthens understanding.",
                                        "Diverse perspectives reveal blind spots.",
                                    ],
                                    "skills": [
                                        {
                                            "skill_name": "Demonstrate Foundational Understanding",
                                            "description": "Explain a concept clearly enough that a peer can understand it.",
                                            "bloom_level": "Understand",
                                            "difficulty": "beginner",
                                            "mastery_criteria": {
                                                "descriptor": "Student can explain a concept without reference to notes.",
                                                "passing_score": 0.7,
                                            },
                                        }
                                    ],
                                }
                            ],
                        },
                    ],
                },
            ]
        }
