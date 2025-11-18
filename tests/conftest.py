import os
import sys
from unittest.mock import MagicMock

os.environ['OPENAI_API_KEY'] = 'test-key-for-ci'
os.environ['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'test-secret-key')

mock_openai_module = MagicMock()
mock_openai_client = MagicMock()
mock_openai_module.OpenAI = MagicMock(return_value=mock_openai_client)
mock_openai_module.api_key = 'test-key'

sys.modules['openai'] = mock_openai_module
sys.modules['openai.types'] = MagicMock()
sys.modules['openai.types.shared_params'] = MagicMock()
sys.modules['openai.types.shared_params.response_format_json_schema'] = MagicMock()
sys.modules['openai.beta'] = MagicMock()
sys.modules['openai.beta.assistants'] = MagicMock()
sys.modules['openai.beta.threads'] = MagicMock()
sys.modules['openai.beta.threads.messages'] = MagicMock()
sys.modules['openai.beta.threads.runs'] = MagicMock()
