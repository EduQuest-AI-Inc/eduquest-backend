from agents import Tool

from bots.tools.chart_tool import generate_chart_image
from bots.tools.content_tool import write_slide_content
from bots.tools.html_tool import render_html_deck
from bots.tools.image_tool import generate_nano_banana_image
from bots.tools.review_tool import review_visual

SLIDE_TOOLS: list[Tool] = [
    write_slide_content,
    generate_nano_banana_image,
    generate_chart_image,
    review_visual,
    render_html_deck,
]
