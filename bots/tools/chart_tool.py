"""
chart_tool — generates a chart/diagram PNG and returns its file path.
"""

from __future__ import annotations

import asyncio
import json

from agents import function_tool

_CHART_TIMEOUT_S = 15

from models.slide_plan import ChartSpec
from utils.rendering import chart_generator


@function_tool
async def generate_chart_image(
    chart_type: str,
    description: str,
    data_hints_json: str,
) -> str:
    """Render a chart/diagram with matplotlib and return the temp PNG file path.

    Use this when the slide benefits from a structured visual (formula plot,
    process flow, concept map, bar/line/scatter/pie). For free-form
    illustrations or photo-realistic imagery, use `generate_nano_banana_image`
    instead.

    Args:
      chart_type: One of `bar | line | equation_plot | process_flow |
                   concept_map | scatter | pie`.
      description: Human-readable title shown above the chart.
      data_hints_json: JSON-encoded string of chart_type-specific data. Examples:
        - bar/pie:        {"labels": [...], "values": [...]}
        - line/scatter:   {"x": [...], "y": [...], "x_label": "…", "y_label": "…"}
        - equation_plot:  {"formula": "y = x**2", "x_min": -5, "x_max": 5}
        - process_flow:   {"steps": ["Step 1", "Step 2", ...]}
        - concept_map:    {"center": "Photosynthesis",
                           "nodes": ["Light", "CO2", ...],
                           "edge_labels": ["needs", "absorbs", ...]}

    Returns:
      Absolute path to a temp PNG file (caller cleans up).

    Side effects: writes a temp file; no network calls.
    Retry safety: idempotent — safe to retry.
    """
    try:
        data_hints = json.loads(data_hints_json) if data_hints_json else {}
    except json.JSONDecodeError:
        data_hints = {}
    spec = ChartSpec(
        chart_type=chart_type,
        description=description,
        data_hints=data_hints,
    )
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(chart_generator.generate_chart_to_file, spec),
            timeout=_CHART_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        raise RuntimeError(
            f"Chart generation timed out after {_CHART_TIMEOUT_S} s"
        )
