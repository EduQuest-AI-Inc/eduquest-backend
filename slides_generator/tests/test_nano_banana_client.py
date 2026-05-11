"""
Tests for the Nano Banana (Gemini) image client.

The google-genai SDK is fully mocked so no real API calls are made.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

from slides_generator.visuals.nano_banana_client import (
    NanoBananaClient,
    NanoBananaError,
    _extract_image_bytes,
)

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc"
    b"\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _build_response(image_bytes: bytes | None) -> MagicMock:
    """Construct a fake google-genai response object."""
    part = MagicMock()
    if image_bytes is None:
        part.inline_data = None
    else:
        inline = MagicMock()
        inline.data = image_bytes
        inline.mime_type = "image/png"
        part.inline_data = inline

    content = MagicMock()
    content.parts = [part]
    candidate = MagicMock()
    candidate.content = content
    response = MagicMock()
    response.candidates = [candidate]
    return response


@pytest.fixture(autouse=True)
def _api_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_IMAGE_MODEL", raising=False)
    yield


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(NanoBananaError, match="GEMINI_API_KEY"):
        NanoBananaClient()


def _make_stub_client(fake_models_client: MagicMock) -> NanoBananaClient:
    """Build a NanoBananaClient that bypasses google-genai imports."""
    client = NanoBananaClient.__new__(NanoBananaClient)
    client._genai = MagicMock()
    client._types = None  # _build_config tolerates None and returns None
    client._client = fake_models_client
    client._model = "gemini-2.5-flash-image"
    return client


def test_generate_image_returns_bytes():
    fake_models_client = MagicMock()
    fake_models_client.models.generate_content.return_value = _build_response(PNG_BYTES)

    client = _make_stub_client(fake_models_client)
    result = client.generate_image("draw a chloroplast diagram")

    assert result == PNG_BYTES
    fake_models_client.models.generate_content.assert_called_once()
    kwargs = fake_models_client.models.generate_content.call_args.kwargs
    assert kwargs["model"] == "gemini-2.5-flash-image"
    assert kwargs["contents"] == "draw a chloroplast diagram"


def test_generate_image_to_file_writes_temp_file():
    fake_models_client = MagicMock()
    fake_models_client.models.generate_content.return_value = _build_response(PNG_BYTES)

    client = _make_stub_client(fake_models_client)

    path = client.generate_image_to_file("a labeled cell")
    try:
        assert os.path.exists(path)
        assert path.endswith(".png")
        with open(path, "rb") as fh:
            assert fh.read() == PNG_BYTES
    finally:
        if os.path.exists(path):
            os.unlink(path)


def test_generate_image_raises_when_no_image_data():
    fake_models_client = MagicMock()
    fake_models_client.models.generate_content.return_value = _build_response(None)

    client = _make_stub_client(fake_models_client)

    with pytest.raises(NanoBananaError, match="no image data"):
        client.generate_image("a labeled cell")


def test_generate_image_wraps_sdk_errors():
    fake_models_client = MagicMock()
    fake_models_client.models.generate_content.side_effect = RuntimeError("network down")

    client = _make_stub_client(fake_models_client)

    with pytest.raises(NanoBananaError, match="network down"):
        client.generate_image("a labeled cell")


def test_extract_image_bytes_handles_empty_response():
    response = MagicMock()
    response.candidates = []
    assert _extract_image_bytes(response) is None


def test_extract_image_bytes_skips_text_parts():
    text_part = MagicMock()
    text_part.inline_data = None
    image_part = MagicMock()
    image_part.inline_data = MagicMock(data=PNG_BYTES, mime_type="image/png")

    content = MagicMock()
    content.parts = [text_part, image_part]
    candidate = MagicMock()
    candidate.content = content
    response = MagicMock()
    response.candidates = [candidate]

    assert _extract_image_bytes(response) == PNG_BYTES
