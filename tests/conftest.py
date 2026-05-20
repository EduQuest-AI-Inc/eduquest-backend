# HOW TO RUN TESTS (from eduquest-backend/ with venv active):
#   pytest                                    # all tests
#   pytest -m unit                            # unit tests only (no network)
#   pytest -m integration                     # integration tests (hits real Supabase)
#   pytest -m api                             # API tests (hits real Supabase and makes HTTP calls to test app)
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
# bots.provider is NOT stubbed — real module must be importable so BotProviderProtocol
# and MockBotProvider are real classes (see 'Bot mocking uses MockBotProvider() constructor
# injection' in ARCH_DECISIONS.md). Individual agent modules are still stubbed because they
# import from the OpenAI SDK at module level; they are only loaded lazily inside provider
# factory methods.
sys.modules['bots.quest_agent'] = MagicMock()  # arch-ok
sys.modules['bots.profile_agent'] = MagicMock()  # arch-ok
sys.modules['bots.ltg_agent'] = MagicMock()  # arch-ok
sys.modules['bots.grading_agent'] = MagicMock()  # arch-ok
sys.modules['bots.teacher_feedback_agent'] = MagicMock()  # arch-ok
sys.modules['bots.coverage_evaluator'] = MagicMock()  # arch-ok
sys.modules['bots.guardrails'] = MagicMock()  # arch-ok
sys.modules['bots.schemas'] = MagicMock()  # arch-ok
sys.modules['bots.schemas.rubric'] = MagicMock()  # arch-ok
sys.modules['bots.slideshow'] = MagicMock()  # arch-ok
sys.modules['bots.slideshow.pptx_agent'] = MagicMock()  # arch-ok
sys.modules['bots.slideshow.orchestrator_agent'] = MagicMock()  # arch-ok
sys.modules['bots.slideshow.content_writer_agent'] = MagicMock()  # arch-ok
sys.modules['bots.slideshow.visual_review_agent'] = MagicMock()  # arch-ok
sys.modules['bots.tools'] = MagicMock()  # arch-ok
sys.modules['bots.tools.content_tool'] = MagicMock()  # arch-ok
sys.modules['bots.tools.image_tool'] = MagicMock()  # arch-ok
sys.modules['bots.tools.chart_tool'] = MagicMock()  # arch-ok
sys.modules['bots.tools.review_tool'] = MagicMock()  # arch-ok
sys.modules['bots.tools.html_tool'] = MagicMock()  # arch-ok

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

# Prevent RuntimeError from get_admin/user_supabase_client() during unit test imports.
# Without these, any module import chain that reaches SupabaseBaseDAO.__init__
# will raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set").
os.environ.setdefault('SUPABASE_URL', 'http://localhost:54321')
os.environ.setdefault('SUPABASE_SERVICE_ROLE_KEY', 'test-service-role-key')
os.environ.setdefault('SUPABASE_ANON_KEY', 'test-anon-key')

# Eagerly import main so all routers/services are cached in sys.modules while
# mocks are active. Without this, tests/unit/bots/conftest.py removes bots mocks
# at collection time (before route test files are imported), causing 'from main
# import app' in those files to see un-mocked bots and produce broken app state.
import main  # noqa: F401

