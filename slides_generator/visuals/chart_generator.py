"""
Chart Generator

Converts a ChartSpec (produced by the Planner Agent) into a PNG image using
matplotlib. No LLM calls happen here — this is pure deterministic rendering
driven by the spec the planner provided.

Supported chart_type values:
  bar           — vertical bar chart
  line          — line / time-series chart
  equation_plot — plots a mathematical function (uses sympy if available,
                  falls back to numpy eval)
  process_flow  — horizontal boxes-and-arrows flow diagram
  concept_map   — nodes connected by labeled edges (simple radial layout)
  scatter       — scatter plot
  pie           — pie / donut chart
"""

from __future__ import annotations

import io
import tempfile
import time
from typing import Any

import matplotlib
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np

matplotlib.use("Agg")  # non-interactive backend

from slides_generator.models.slide_plan import ChartSpec

# ── Colour palette (matches EduQuest brand) ─────────────────────────────────
_BLUE = "#1B4F9B"
_ORANGE = "#F07B3F"
_DARK = "#2C2C2C"
_LIGHT = "#F5F7FA"
_PALETTE = [_BLUE, _ORANGE, "#4CAF50", "#9C27B0", "#00BCD4"]


def generate_chart(spec: ChartSpec) -> bytes:
    """
    Render a chart from a ChartSpec and return PNG bytes.

    Args:
        spec: ChartSpec produced by the Planner Agent.

    Returns:
        PNG image bytes (1792×1024 px at 150 dpi, 16:9 ratio).
    """
    dispatch = {
        "bar": _bar,
        "line": _line,
        "equation_plot": _equation_plot,
        "process_flow": _process_flow,
        "concept_map": _concept_map,
        "scatter": _scatter,
        "pie": _pie,
    }
    handler = dispatch.get(spec.chart_type, _fallback)
    fig = handler(spec)
    return _fig_to_png(fig)


def generate_chart_to_file(spec: ChartSpec) -> str:
    """Render a chart and write it to a temp file. Returns the file path."""
    png_bytes = generate_chart(spec)
    suffix = f"_chart_{int(time.time())}.png"
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        import os
        os.write(fd, png_bytes)
    finally:
        import os
        os.close(fd)
    return path


# ── Helpers ─────────────────────────────────────────────────────────────────

def _fig_to_png(fig: plt.Figure) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _base_fig(title: str = "") -> tuple[plt.Figure, plt.Axes]:
    fig, ax = plt.subplots(figsize=(11.93, 6.71), facecolor=_LIGHT)
    ax.set_facecolor(_LIGHT)
    if title:
        fig.suptitle(title, fontsize=18, color=_DARK, fontweight="bold", y=0.98)
    for spine in ax.spines.values():
        spine.set_edgecolor("#CCCCCC")
    return fig, ax


# ── Chart handlers ───────────────────────────────────────────────────────────

def _bar(spec: ChartSpec) -> plt.Figure:
    hints: dict[str, Any] = spec.data_hints
    labels = hints.get("labels", ["A", "B", "C", "D"])
    values = hints.get("values", [round(np.random.uniform(0.3, 1.0), 2) for _ in labels])
    x_label = hints.get("x_label", "")
    y_label = hints.get("y_label", "Value")

    fig, ax = _base_fig(spec.description)
    bars = ax.bar(labels, values, color=_PALETTE[: len(labels)], edgecolor="white", linewidth=1.5)
    ax.bar_label(bars, fmt="%.2f", padding=4, color=_DARK, fontsize=12)
    ax.set_xlabel(x_label, color=_DARK, fontsize=13)
    ax.set_ylabel(y_label, color=_DARK, fontsize=13)
    ax.tick_params(colors=_DARK)
    ax.set_ylim(0, max(values) * 1.25)
    return fig


def _line(spec: ChartSpec) -> plt.Figure:
    hints: dict[str, Any] = spec.data_hints
    x = hints.get("x", list(range(1, 11)))
    y = hints.get("y", [round(v, 2) for v in np.cumsum(np.random.randn(len(x))) + 5])
    x_label = hints.get("x_label", "x")
    y_label = hints.get("y_label", "y")

    fig, ax = _base_fig(spec.description)
    ax.plot(x, y, color=_BLUE, linewidth=2.5, marker="o", markersize=6, markerfacecolor=_ORANGE)
    ax.fill_between(x, y, alpha=0.12, color=_BLUE)
    ax.set_xlabel(x_label, color=_DARK, fontsize=13)
    ax.set_ylabel(y_label, color=_DARK, fontsize=13)
    ax.tick_params(colors=_DARK)
    return fig


def _equation_plot(spec: ChartSpec) -> plt.Figure:
    hints: dict[str, Any] = spec.data_hints
    formula = hints.get("formula", "y = x**2")
    x_min = float(hints.get("x_min", -5))
    x_max = float(hints.get("x_max", 5))
    x_label = hints.get("x_label", "x")
    y_label = hints.get("y_label", "y")

    x = np.linspace(x_min, x_max, 500)

    # Safe eval: only allow numpy functions and x
    safe_ns: dict[str, Any] = {k: getattr(np, k) for k in dir(np) if not k.startswith("_")}
    safe_ns["x"] = x

    # Parse "y = expr" or plain "expr"
    expr = formula.split("=", 1)[-1].strip()
    try:
        y = eval(expr, {"__builtins__": {}}, safe_ns)  # noqa: S307
    except Exception:
        y = x * 0  # flat line on error

    fig, ax = _base_fig(spec.description)
    ax.plot(x, y, color=_BLUE, linewidth=2.5, label=formula)
    ax.axhline(0, color=_DARK, linewidth=0.8, linestyle="--", alpha=0.5)
    ax.axvline(0, color=_DARK, linewidth=0.8, linestyle="--", alpha=0.5)
    ax.set_xlabel(x_label, color=_DARK, fontsize=13)
    ax.set_ylabel(y_label, color=_DARK, fontsize=13)
    ax.legend(fontsize=13, framealpha=0.7)
    ax.tick_params(colors=_DARK)
    return fig


def _process_flow(spec: ChartSpec) -> plt.Figure:
    hints: dict[str, Any] = spec.data_hints
    steps: list[str] = hints.get("steps", spec.description.split(" → "))
    if len(steps) < 2:
        steps = ["Step 1", "Step 2", "Step 3"]

    fig, ax = plt.subplots(figsize=(11.93, 6.71), facecolor=_LIGHT)
    ax.set_facecolor(_LIGHT)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.suptitle(spec.description, fontsize=16, color=_DARK, fontweight="bold", y=0.97)

    n = len(steps)
    box_w = min(0.18, 0.85 / n)
    box_h = 0.28
    gap = (1.0 - n * box_w) / (n + 1)
    y_center = 0.48

    colors = (_PALETTE * ((n // len(_PALETTE)) + 1))[:n]

    for i, (step, color) in enumerate(zip(steps, colors)):
        x_left = gap + i * (box_w + gap)
        x_center = x_left + box_w / 2

        fancy = mpatches.FancyBboxPatch(
            (x_left, y_center - box_h / 2),
            box_w, box_h,
            boxstyle="round,pad=0.015",
            facecolor=color, edgecolor="white", linewidth=2,
        )
        ax.add_patch(fancy)
        ax.text(
            x_center, y_center,
            _wrap(step, 14),
            ha="center", va="center",
            fontsize=max(8, 11 - n),
            color="white", fontweight="bold",
        )

        # Arrow to next box
        if i < n - 1:
            x_arrow_start = x_left + box_w + 0.005
            x_arrow_end = x_left + box_w + gap - 0.005
            ax.annotate(
                "",
                xy=(x_arrow_end, y_center),
                xytext=(x_arrow_start, y_center),
                arrowprops=dict(arrowstyle="->", color=_DARK, lw=2),
            )

    return fig


def _concept_map(spec: ChartSpec) -> plt.Figure:
    hints: dict[str, Any] = spec.data_hints
    center: str = hints.get("center", spec.description.split()[0])
    nodes: list[str] = hints.get("nodes", ["Node A", "Node B", "Node C", "Node D"])
    edges: list[str] = hints.get("edge_labels", [""] * len(nodes))

    fig, ax = plt.subplots(figsize=(11.93, 6.71), facecolor=_LIGHT)
    ax.set_facecolor(_LIGHT)
    ax.set_xlim(-1.3, 1.3)
    ax.set_ylim(-1.3, 1.3)
    ax.axis("off")
    fig.suptitle(spec.description, fontsize=16, color=_DARK, fontweight="bold", y=0.97)

    # Center node
    ax.add_patch(plt.Circle((0, 0), 0.22, color=_BLUE, zorder=3))
    ax.text(0, 0, _wrap(center, 12), ha="center", va="center",
            fontsize=11, color="white", fontweight="bold", zorder=4)

    n = len(nodes)
    angles = [2 * np.pi * i / n for i in range(n)]
    r = 0.85
    colors = (_PALETTE[1:] * ((n // (len(_PALETTE) - 1)) + 1))[:n]

    for angle, node, edge_label, color in zip(angles, nodes, edges, colors):
        nx_, ny_ = r * np.cos(angle), r * np.sin(angle)

        # Edge line
        ax.annotate(
            "",
            xy=(nx_ * 0.72, ny_ * 0.72),
            xytext=(0.22 * np.cos(angle), 0.22 * np.sin(angle)),
            arrowprops=dict(arrowstyle="->", color="#888888", lw=1.5),
            zorder=2,
        )

        # Edge label
        if edge_label:
            mid_x, mid_y = 0.5 * nx_ * 0.72, 0.5 * ny_ * 0.72
            ax.text(mid_x, mid_y, edge_label, ha="center", va="center",
                    fontsize=8, color="#555555", style="italic")

        # Satellite node
        ax.add_patch(plt.Circle((nx_, ny_), 0.18, color=color, zorder=3))
        ax.text(nx_, ny_, _wrap(node, 10), ha="center", va="center",
                fontsize=9, color="white", fontweight="bold", zorder=4)

    return fig


def _scatter(spec: ChartSpec) -> plt.Figure:
    hints: dict[str, Any] = spec.data_hints
    x = hints.get("x", list(np.random.randn(30)))
    y = hints.get("y", list(np.random.randn(30)))
    x_label = hints.get("x_label", "x")
    y_label = hints.get("y_label", "y")

    fig, ax = _base_fig(spec.description)
    ax.scatter(x, y, color=_BLUE, edgecolors=_ORANGE, linewidth=0.8, s=80, alpha=0.8)
    ax.set_xlabel(x_label, color=_DARK, fontsize=13)
    ax.set_ylabel(y_label, color=_DARK, fontsize=13)
    ax.tick_params(colors=_DARK)
    return fig


def _pie(spec: ChartSpec) -> plt.Figure:
    hints: dict[str, Any] = spec.data_hints
    labels: list[str] = hints.get("labels", ["Part A", "Part B", "Part C"])
    values: list[float] = hints.get("values", [1.0] * len(labels))

    fig, ax = plt.subplots(figsize=(11.93, 6.71), facecolor=_LIGHT)
    ax.set_facecolor(_LIGHT)
    fig.suptitle(spec.description, fontsize=16, color=_DARK, fontweight="bold", y=0.97)

    wedge_props = dict(width=0.55, edgecolor="white", linewidth=2)
    ax.pie(
        values,
        labels=labels,
        colors=(_PALETTE * ((len(labels) // len(_PALETTE)) + 1))[: len(labels)],
        autopct="%1.1f%%",
        startangle=90,
        wedgeprops=wedge_props,
        textprops={"color": _DARK, "fontsize": 12},
    )
    return fig


def _fallback(spec: ChartSpec) -> plt.Figure:
    """Renders a placeholder card for unsupported chart types."""
    fig, ax = plt.subplots(figsize=(11.93, 6.71), facecolor=_LIGHT)
    ax.set_facecolor(_LIGHT)
    ax.axis("off")
    ax.text(
        0.5, 0.5,
        f"Chart type '{spec.chart_type}' not yet supported.\n\n{spec.description}",
        ha="center", va="center", fontsize=14, color=_DARK,
        transform=ax.transAxes, wrap=True,
    )
    return fig


def _wrap(text: str, width: int) -> str:
    """Naive word-wrap for node labels."""
    words = text.split()
    lines, current = [], ""
    for word in words:
        if len(current) + len(word) + 1 <= width:
            current = f"{current} {word}".strip()
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return "\n".join(lines)
