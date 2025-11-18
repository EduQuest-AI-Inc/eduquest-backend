import os
import sys
from unittest.mock import MagicMock

os.environ['OPENAI_API_KEY'] = 'test-key-for-ci'
os.environ['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'test-secret-key')
os.environ['AWS_ACCESS_KEY_ID'] = 'test-aws-key'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'test-aws-secret'
os.environ['AWS_REGION'] = 'us-east-2'

mock_openai_module = MagicMock()
mock_openai_client = MagicMock()
mock_openai_module.OpenAI = MagicMock(return_value=mock_openai_client)
mock_openai_module.api_key = 'test-key'

sys.modules['openai'] = mock_openai_module
sys.modules['openai._types'] = MagicMock()
sys.modules['openai.types'] = MagicMock()
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
sys.modules['boto3.dynamodb'] = MagicMock()
sys.modules['boto3.dynamodb.conditions'] = MagicMock()
sys.modules['botocore'] = MagicMock()
sys.modules['botocore.exceptions'] = MagicMock()
