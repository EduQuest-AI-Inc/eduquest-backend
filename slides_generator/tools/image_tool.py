"""
image_tool - generates a Nano Banana (Gemini) illustration and returns its
file path.
"""

from __future__ import annotations

from agents import function_tool

from slides_generator.visuals.nano_banana_client import (
    NanoBananaClient,
    NanoBananaError,
)

_client: NanoBananaClient | None = None


def _get_client() -> NanoBananaClient:
    global _client
    if _client is None:
        _client = NanoBananaClient()
    return _client


@function_tool
def generate_nano_banana_image(prompt: str) -> str:
    """Generate an AI illustration via Nano Banana (Gemini) and return its temp PNG file path.

    Use this for free-form illustrations: anatomy diagrams, historical scenes,
    science illustrations, depictions of objects/processes that don't fit a
    chart. For structured charts/diagrams use `generate_chart_image`.

    Args:
      prompt: Detailed image-generation prompt. Be specific about style,
              labels, background, and what to include/exclude.
              Example: "Cross-section diagram of a human muscle cell showing
              cytoplasm, mitochondria, and ATP molecules, educational science
              illustration style, clean white background, labeled in English."

    Returns:
      Absolute path to a temp PNG (caller cleans up). On API errors, returns
      a string starting with "ERROR:" so the orchestrator can fall back to
      a placeholder layout.

    Side effects: ONE Gemini API call; writes a temp file.
    Retry safety: idempotent but not free - avoid blind retries.
    """
    try:
        return _get_client().generate_image_to_file(prompt)
    except NanoBananaError as exc:
        return f"ERROR: Nano Banana generation failed: {exc}"
