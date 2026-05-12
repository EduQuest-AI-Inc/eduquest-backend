"""
Tests for the chart generator. No mocking needed — pure Python rendering.
"""

from __future__ import annotations

import os

import pytest

from models.slide_plan import ChartSpec

pytestmark = pytest.mark.unit
from utils.rendering.chart_generator import generate_chart, generate_chart_to_file


def _spec(chart_type: str, description: str = "Test chart", data_hints: dict | None = None) -> ChartSpec:
    return ChartSpec(chart_type=chart_type, description=description, data_hints=data_hints or {})


def test_bar_chart_returns_bytes():
    spec = _spec("bar", data_hints={"labels": ["A", "B", "C"], "values": [10, 20, 15]})
    result = generate_chart(spec)
    assert isinstance(result, bytes)
    assert result[:4] == b"\x89PNG"  # PNG magic bytes


def test_line_chart_returns_bytes():
    spec = _spec("line", data_hints={"x": [1, 2, 3, 4, 5], "y": [2, 4, 3, 6, 5]})
    result = generate_chart(spec)
    assert isinstance(result, bytes)
    assert len(result) > 1000


def test_equation_plot_returns_bytes():
    spec = _spec("equation_plot", data_hints={"formula": "y = x**2", "x_min": -3, "x_max": 3})
    result = generate_chart(spec)
    assert isinstance(result, bytes)
    assert result[:4] == b"\x89PNG"


def test_process_flow_returns_bytes():
    spec = _spec(
        "process_flow",
        description="Photosynthesis Steps",
        data_hints={"steps": ["Sunlight absorbed", "Water split", "ATP produced", "Glucose formed"]},
    )
    result = generate_chart(spec)
    assert isinstance(result, bytes)
    assert len(result) > 1000


def test_concept_map_returns_bytes():
    spec = _spec(
        "concept_map",
        data_hints={
            "center": "Cell",
            "nodes": ["Nucleus", "Mitochondria", "Ribosome"],
            "edge_labels": ["contains", "powers", "builds"],
        },
    )
    result = generate_chart(spec)
    assert isinstance(result, bytes)


def test_scatter_returns_bytes():
    spec = _spec("scatter", data_hints={"x": [1, 2, 3], "y": [3, 1, 2]})
    result = generate_chart(spec)
    assert isinstance(result, bytes)


def test_pie_returns_bytes():
    spec = _spec("pie", data_hints={"labels": ["ATP", "NADPH", "Other"], "values": [40, 35, 25]})
    result = generate_chart(spec)
    assert isinstance(result, bytes)


def test_unknown_chart_type_returns_fallback():
    spec = _spec("spider_web_diagram")
    result = generate_chart(spec)
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_generate_chart_to_file_creates_file():
    spec = _spec("bar", data_hints={"labels": ["X", "Y"], "values": [5, 10]})
    path = generate_chart_to_file(spec)
    try:
        assert os.path.exists(path)
        assert os.path.getsize(path) > 1000
        assert path.endswith(".png")
    finally:
        os.unlink(path)


def test_equation_plot_bad_formula_does_not_raise():
    spec = _spec("equation_plot", data_hints={"formula": "y = import os; os.system('rm -rf /')"})
    result = generate_chart(spec)
    assert isinstance(result, bytes)
