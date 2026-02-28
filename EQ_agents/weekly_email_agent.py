from data_access.period_dao import PeriodDAO
from agents import Agent, ModelSettings

from typing import Optional, List
from pydantic import BaseModel, Field
from openai.types.shared import Reasoning



from EQ_agents.guardrails import check_student_output_safety


EMAIL_PROMPT = """  You are writing a weekly progress email to a teacher.

  Your job is to write a short, friendly, professional email summarizing how the class performed this week based only on the provided class-
  level skill metrics.

  Important rules:
  - Do not mention individual students.
  - Do not invent reasons for performance.
  - Do not add recommendations unless they are directly supported by the metrics.
  - Keep the tone warm, supportive, and concise.
  - Keep the email around 200-300 words.
  - Use only the provided data.

  You will receive:
  - teacher_name
  - week_number
  - period_names
  
  For each period, you will receive:
  - skill_metrics for the current week

  Write the email in this structure:

  1. Subject line
  Format:
  EduQuest Weekly Class Progress Update - Week {week_number} 

  2. Friendly opening
  - Greet the teacher by name.
  - Briefly explain whether the class is doing well, mixed, or struggling.

  3. Overall summary paragraph
  - Write 2-3 sentences summarizing how the class is doing this week overall.
  - Mention whether understanding seems strong, mixed, or uneven across skills.

  4. Periods section
  Start with:
  "Here is a breakdown of class performance by period this week:"

  Then for each period, list each skill in this format:
  Period: {period_name}
  - {skill_name}: {percentage}% average understanding ({label})

  Where label should be:
  - "Strong understanding" for high percentages
  - "Developing understanding" for middle percentages
  - "Needs reinforcement" for lower percentages

  5. Key takeaway paragraph
  - Briefly mention the strongest skill and the weakest skill.
  - Summarize the class trend in 1-2 sentences.

  6. Friendly closing
  - End with 2 short sentences thanking the teacher and closing warmly.

  Input:
  teacher_name: {teacher_name}
  week_number: {week_number}
  class_name: {class_name}
  skill_metrics: {skill_metrics}"""


class WeeklyEmailAgent:
    def __init__(self, teacher_id: str):
        self.teacher_id = teacher_id
        self.period_ids = self.get_periods()
        self.skill_metrics = self.get_skill_metrics()
        self.agent = Agent(
            name="Weekly Email Agent",
            instructions=EMAIL_PROMPT,
            model="gpt-5.1",
            model_settings=ModelSettings(
                reasoning=Reasoning(effort="medium"),
                verbosity="medium",
            ),
        )
        
    def get_periods(self):
        periods = PeriodDAO().get_periods_by_teacher_id(self.teacher_id)
        return [period.course for period in periods]
    
    def get_skill_metrics(self, period_id: str):
        raise NotImplementedError("Not implemented")
    
