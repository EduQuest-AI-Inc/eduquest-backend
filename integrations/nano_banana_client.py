"""
Nano Banana (Gemini Image) Client

Wraps Google's Gemini image-generation models — informally known as
"Nano Banana" — and returns PNG bytes for a given text prompt. Replaces the
earlier Seedance/Seedream client; the public surface (``generate_image`` /
``generate_image_to_file``) is intentionally unchanged so the rest of the
slide pipeline does not need to know which provider produced the bytes.

Configuration (via environment variables):
  GEMINI_API_KEY      - required. Issued from Google AI Studio.
  GOOGLE_API_KEY      - fallback name accepted by google-genai.
  GEMINI_IMAGE_MODEL  - optional. Defaults to ``gemini-2.5-flash-image``.
                        Set to ``gemini-3.1-flash-image-preview`` or
                        ``gemini-3-pro-image-preview`` for newer/higher
                        quality if your account has access.

Compliance notes:
  - Treat Google as a third-party AI sub-processor. Confirm DPA coverage
    before sending any production student-context prompts.
  - Slide prompts must use synthetic / lesson-only content. Never include
    student names, IDs, grades, or other PII in image prompts.
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
from typing import Any

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gemini-2.5-flash-image"


class NanoBananaError(Exception):
    """Raised for any failure in the Nano Banana / Gemini image pipeline."""


class NanoBananaClient:
    """Thin wrapper around ``google-genai`` for slide-illustration generation."""

    def __init__(self, model: str | None = None) -> None:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise NanoBananaError(
                "GEMINI_API_KEY is not set. Add it to your .env file or "
                "environment (GOOGLE_API_KEY is also accepted)."
            )

        try:
            from google import genai  # type: ignore
            from google.genai import types as genai_types  # type: ignore
        except ImportError as exc:
            raise NanoBananaError(
                "google-genai is not installed. Run "
                "`pip install -r requirements.txt`."
            ) from exc

        self._genai = genai
        self._types = genai_types
        self._client = genai.Client(api_key=api_key)
        self._model = model or os.getenv("GEMINI_IMAGE_MODEL", _DEFAULT_MODEL)

    def generate_image(self, prompt: str, aspect_ratio: str = "16:9") -> bytes:
        """Generate an image for ``prompt`` and return raw PNG bytes.

        Args:
            prompt: Detailed description of the desired image.
            aspect_ratio: Slide-friendly aspect ratio. ``16:9`` matches the
                default PowerPoint deck shape.

        Raises:
            NanoBananaError: On API errors, missing image data, or unexpected
                response shapes.
        """
        config = self._build_config(aspect_ratio)

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=config,
            )
        except Exception as exc:  # noqa: BLE001 - SDK raises diverse errors
            raise NanoBananaError(
                f"Gemini image generation failed: {exc}"
            ) from exc

        png_bytes = _extract_image_bytes(response)
        if not png_bytes:
            raise NanoBananaError(
                "Gemini response contained no image data. The prompt may have "
                "been refused by the safety filter."
            )
        return png_bytes

    def _build_config(self, aspect_ratio: str) -> Any:
        """Construct the SDK config object, tolerating older google-genai versions."""
        types = getattr(self, "_types", None)
        if types is None:
            return None
        try:
            return types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
            )
        except (AttributeError, TypeError):
            try:
                return types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                )
            except (AttributeError, TypeError):
                return None

    def generate_image_to_file(
        self, prompt: str, aspect_ratio: str = "16:9"
    ) -> str:
        """Generate an image and write it to a temp file.

        Returns:
            Absolute path to the PNG temp file. The caller is responsible
            for cleanup.
        """
        png_bytes = self.generate_image(prompt, aspect_ratio=aspect_ratio)

        suffix = f"_nano_banana_{int(time.time())}.png"
        fd, path = tempfile.mkstemp(suffix=suffix)
        try:
            os.write(fd, png_bytes)
        finally:
            os.close(fd)
        return path


def _extract_image_bytes(response: Any) -> bytes | None:
    """Pull the first inline image payload out of a Gemini response."""
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            inline = getattr(part, "inline_data", None)
            if inline is None:
                continue
            data = getattr(inline, "data", None)
            if data:
                return data
    return None
