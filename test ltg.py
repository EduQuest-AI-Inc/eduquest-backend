import sys
import os

# Add the parent directory to Python path so we can import from eduquest-backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import assistants
import openai
from openai import OpenAI
import time
import os
import json
from dotenv import load_dotenv
from openai.types.shared_params.response_format_json_schema import ResponseFormatJSONSchema
import decimal

def convert_decimal(obj):
    if isinstance(obj, list):
        return [convert_decimal(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, decimal.Decimal):
        return float(obj)
    else:
        return obj

load_dotenv()

student_data = """{
  "student_id": {
    "S": "GoldenHCH1"
  },
  "enrollments": {
    "L": [
      {
        "S": "PRECALC-58F9-88F5"
      }
    ]
  },
  "first_name": {
    "S": "Golden"
  },
  "grade": {
    "N": "11"
  },
  "interest": {
    "L": [
      {
        "S": "golf"
      },
      {
        "S": "calligraphy"
      },
      {
        "S": "math"
      },
      {
        "S": "stocks"
      },
      {
        "S": "AI"
      },
      {
        "S": "computer science"
      }
    ]
  },
  "last_login": {
    "S": "2025-07-21T21:04:17.092954+00:00"
  },
  "last_name": {
    "S": "Huang"
  },
  "learning_style": {
    "L": [
      {
        "S": "visual"
      },
      {
        "S": "hands-on"
      },
      {
        "S": "utilizes technology"
      }
    ]
  },
  "long_term_goal": {
    "L": []
  },
  "password": {
    "S": "scrypt:32768:8:1$PRHwZdUQNTnsPwwb$91bf7cb012c2b9794a38af5af5d14478583f0436e641198100cfdaa5bcbdf3e650cf87a2898c540dc2fbe4378f18701b220204cd6deda03f11d9ce0e0ae34c01"
  },
  "quests": {
    "L": []
  },
  "strength": {
    "L": [
      {
        "S": "analytical thinking"
      },
      {
        "S": "problem-solving"
      }
    ]
  },
  "weakness": {
    "L": [
      {
        "S": "team management"
      },
      {
        "S": "frustration with others' performance"
      }
    ]
  }
}"""

ltg_ass = assistants.ltg(student_data, "asst_8Rz4EFUBR8L6KUAiy7aWpIuf")

print(type(ltg_ass.initiate()))