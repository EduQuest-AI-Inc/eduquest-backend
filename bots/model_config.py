"""Central model policy for EduQuest AI workloads."""

# Conversation agents
PROFILE_CONVERSATION_MODEL = "gpt-4.1-mini"
LTG_CONVERSATION_MODEL = "gpt-5.4-mini"
TEACHER_FEEDBACK_MODEL = "gpt-5.4-mini"

# Student safety and moderation
STUDENT_SAFETY_MODEL = "gpt-5.4-nano"

# Grading agents
GRADING_NUMERICAL_MODEL = "gpt-5.4"
GRADING_FEEDBACK_MODEL = "gpt-5.4-mini"
GRADING_MASTERY_MODEL = "gpt-5.4"
GRADING_ADAPTATION_MODEL = "gpt-5.4-mini"

# Curriculum generation
COVERAGE_EVALUATOR_MODEL = "gpt-5.4-nano"
CURRICULUM_SCHEDULE_MODEL = "gpt-5.4"
CURRICULUM_SCHEDULE_REASONING_EFFORT = "medium"

# Quest generation
QUEST_INSTRUCTION_MODEL = "gpt-5.4-mini"
QUEST_RUBRIC_MODEL = "gpt-5.4"
LTG_SCHEDULE_MODEL = "gpt-5.4-mini"
CURRICULUM_ONLY_LTG_MODEL = "gpt-5.4-mini"
CURRICULUM_ONLY_QUEST_NAME_MODEL = "gpt-5.4-mini"
CURRICULUM_ONLY_INSTRUCTION_MODEL = "gpt-5.4-mini"
CURRICULUM_ONLY_RUBRIC_MODEL = "gpt-5.4"

# Landing page demo (no auth, single call)
DEMO_LTG_MODEL = "gpt-5.4-mini"

# Slide generation
SLIDE_ORCHESTRATOR_MODEL = "gpt-5.4"
SLIDE_CONTENT_WRITER_MODEL = "gpt-5.4-mini"
SLIDE_VISUAL_REVIEW_MODEL = "gpt-5.4-mini"
