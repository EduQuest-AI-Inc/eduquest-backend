import pytest

from bots import model_config


@pytest.mark.unit
def test_model_config_critical_mappings():
    assert model_config.GRADING_NUMERICAL_MODEL == "gpt-5.4"
    assert model_config.GRADING_MASTERY_MODEL == "gpt-5.4"
    assert model_config.STUDENT_SAFETY_MODEL == "gpt-5.4-nano"
    assert model_config.COVERAGE_EVALUATOR_MODEL == "gpt-5.4-nano"


@pytest.mark.unit
def test_model_config_lower_cost_generation_mappings():
    assert model_config.LTG_CONVERSATION_MODEL == "gpt-5.4-mini"
    assert model_config.TEACHER_FEEDBACK_MODEL == "gpt-5.4-mini"
    assert model_config.QUEST_INSTRUCTION_MODEL == "gpt-5.4-mini"
    assert model_config.QUEST_RUBRIC_MODEL == "gpt-5.4"
    assert model_config.CURRICULUM_SCHEDULE_MODEL == "gpt-5.4"
    assert model_config.CURRICULUM_SCHEDULE_REASONING_EFFORT == "medium"
