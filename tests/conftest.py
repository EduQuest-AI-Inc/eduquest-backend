# HOW TO RUN TESTS (from eduquest-backend/ with venv active):
#   pytest                                    # all tests
#   pytest -m unit                            # unit tests only (no network)
#   pytest -m integration                       # integration tests (hits real Supabase)
#   pytest tests/test_teacher_dao.py          # single file
#   pytest --cov=. --cov-report=html          # coverage report

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock
from dotenv import load_dotenv

# Load .env so integration tests pick up real SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY
load_dotenv(Path(__file__).parent.parent / ".env", override=False)

os.environ['OPENAI_API_KEY'] = 'test-key-for-ci'
os.environ['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'test-secret-key')
os.environ['AWS_ACCESS_KEY_ID'] = 'test-aws-key'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'test-aws-secret'
os.environ['AWS_REGION'] = 'us-east-2'

sys.modules['agents'] = MagicMock()
sys.modules['agents._config'] = MagicMock()
sys.modules['agents.models'] = MagicMock()
sys.modules['agents.model_settings'] = MagicMock()
sys.modules['bots'] = MagicMock()
sys.modules['bots.agent'] = MagicMock()
sys.modules['bots.profile_agent'] = MagicMock()
sys.modules['bots.ltg_agent'] = MagicMock()
sys.modules['bots.grading_agent'] = MagicMock()
sys.modules['bots.teacher_feedback_agent'] = MagicMock()
sys.modules['bots.schedule_agent'] = MagicMock()
sys.modules['bots.guardrails'] = MagicMock()
sys.modules['bots.schemas'] = MagicMock()
sys.modules['bots.schemas.rubric'] = MagicMock()
sys.modules['bots.provider'] = MagicMock()

mock_openai_module = MagicMock()
mock_openai_client = MagicMock()
mock_openai_module.OpenAI = MagicMock(return_value=mock_openai_client)
mock_openai_module.api_key = 'test-key'

sys.modules['openai'] = mock_openai_module
sys.modules['openai._types'] = MagicMock()
sys.modules['openai.types'] = MagicMock()
sys.modules['openai.types.responses'] = MagicMock()
sys.modules['openai.types.shared'] = MagicMock()
sys.modules['openai.types.shared.reasoning'] = MagicMock()
sys.modules['openai.types.shared_params'] = MagicMock()
sys.modules['openai.types.shared_params.response_format_json_schema'] = MagicMock()
sys.modules['openai.beta'] = MagicMock()
sys.modules['openai.beta.assistants'] = MagicMock()
sys.modules['openai.beta.threads'] = MagicMock()
sys.modules['openai.beta.threads.messages'] = MagicMock()
sys.modules['openai.beta.threads.runs'] = MagicMock()

mock_boto3 = MagicMock()
mock_boto3.resource = MagicMock(return_value=MagicMock())
mock_boto3.client = MagicMock(return_value=MagicMock())
sys.modules['boto3'] = mock_boto3
sys.modules['botocore'] = MagicMock()
sys.modules['botocore.config'] = MagicMock()
sys.modules['botocore.exceptions'] = MagicMock()

# Prevent RuntimeError from get_supabase_client() during unit test imports.
# Without these, any module import chain that reaches SupabaseBaseDAO.__init__
# will raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set").
os.environ.setdefault('SUPABASE_URL', 'http://localhost:54321')
os.environ.setdefault('SUPABASE_SERVICE_ROLE_KEY', 'test-service-role-key')

