"""
PDF Renderer

Uses Playwright headless Chromium to convert a standalone HTML string into a
pixel-perfect 16:9 PDF. Each `.slide` section becomes one PDF page (controlled
by `@page { size: 16in 9in; }` and `page-break-after: always` in the base
template).

Requires: `pip install playwright && playwright install chromium`.
"""

from __future__ import annotations


def render_pdf(html: str) -> bytes:
    """Render HTML to PDF bytes using Playwright headless Chromium.

    Args:
        html: A complete standalone HTML document string.

    Returns:
        PDF file bytes (16in × 9in landscape pages).
    """
    # Imported lazily so the rest of the package can be imported in environments
    # where Playwright isn't installed (e.g. CI lint, unit tests).
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        page = context.new_page()
        page.set_content(html, wait_until="networkidle")
        pdf_bytes = page.pdf(
            width="16in",
            height="9in",
            print_background=True,
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            prefer_css_page_size=True,
        )
        browser.close()
    return pdf_bytes
