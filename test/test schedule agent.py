import sys
import os

# Add the parent directory to Python path so we can import from eduquest-backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from typing import Dict, Any
from data_access.period_dao import PeriodDAO
from data_access.session_dao import SessionDAO
from data_access.student_dao import StudentDAO
from data_access.conversation_dao import ConversationDAO
from data_access.enrollment_dao import EnrollmentDAO
from models.conversation import Conversation
from models.enrollment import Enrollment
from models.session import Session
from assistants import ltg
from datetime import datetime, timezone
from EQ_agents.agent import SchedulesAgent, HWAgent
from routes.quest.quest_service import QuestService
import json
from dotenv import load_dotenv
from openai import OpenAI
from models.student import Student
from models.period import Period
# from models.homework import HomeworkSchedule
import openai
from flask_jwt_extended import create_access_token
from flask import Flask

load_dotenv()

# Initialize Flask app for JWT token creation (if needed)
app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'fallback-secret')

openai.api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

period_dao = PeriodDAO()
session_dao = SessionDAO()
student_dao = StudentDAO()
conversation_dao = ConversationDAO()
enrollment_dao = EnrollmentDAO()
quest_service = QuestService()
student = student_dao.get_student_by_id("Golden")
weekly_schedule = quest_service.get_weekly_quests_for_student('Golden', 'PRECALC-58F9-88F5')
period = period_dao.get_period_by_id('PRECALC-58F9-88F5')

schedule_agent = SchedulesAgent(student, period)

schedule = schedule_agent.run()
print(type(schedule))