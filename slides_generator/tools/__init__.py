"""
Slide-generation tools.

These `@function_tool`-decorated callables are passed to the orchestrator
agent as `tools=[...]`. Each one wraps a specialist (content writer agent,
chart generator, Nano Banana client, visual review agent) so the orchestrator
can invoke them as just-another tool call.

Mirrors the pattern in `eduquest-backend/bots/tools/knowledge_graph_tools.py`.
"""

from slides_generator.tools.chart_tool import generate_chart_image
from slides_generator.tools.content_tool import write_slide_content
from slides_generator.tools.html_tool import render_html_deck
from slides_generator.tools.image_tool import generate_nano_banana_image
from slides_generator.tools.review_tool import review_visual

SLIDE_TOOLS = [
    write_slide_content,
    generate_chart_image,
    generate_nano_banana_image,
    review_visual,
    render_html_deck,
]

__all__ = [
    "SLIDE_TOOLS",
    "write_slide_content",
    "generate_chart_image",
    "generate_nano_banana_image",
    "review_visual",
    "render_html_deck",
]
