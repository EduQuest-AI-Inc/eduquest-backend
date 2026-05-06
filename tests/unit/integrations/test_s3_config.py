import importlib
import pytest
import integrations.s3_service as s3_mod


@pytest.mark.unit
class TestS3ClientConfig:
    def setup_method(self):
        importlib.reload(s3_mod)

    def test_endpoint_uses_regional_url(self):
        import boto3
        _, kwargs = boto3.client.call_args
        assert kwargs["endpoint_url"] == "https://s3.us-east-2.amazonaws.com"

    def test_addressing_style_is_virtual(self):
        from botocore.config import Config
        _, kwargs = Config.call_args
        assert kwargs["s3"] == {"addressing_style": "virtual"}

    def test_region_matches_env(self):
        assert s3_mod._region == "us-east-2"
