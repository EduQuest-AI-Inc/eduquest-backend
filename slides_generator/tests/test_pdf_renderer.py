"""Tests for the PDF renderer (mocks Playwright so no real browser is launched)."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest


def test_render_pdf_returns_bytes(monkeypatch):
    """The renderer should return whatever bytes Playwright's page.pdf() returns."""
    fake_pdf = b"%PDF-1.4 fake bytes"

    fake_page = MagicMock()
    fake_page.pdf.return_value = fake_pdf
    fake_context = MagicMock()
    fake_context.new_page.return_value = fake_page
    fake_browser = MagicMock()
    fake_browser.new_context.return_value = fake_context
    fake_browser.new_page.return_value = fake_page

    fake_pw = MagicMock()
    fake_pw.chromium.launch.return_value = fake_browser

    fake_cm = MagicMock()
    fake_cm.__enter__.return_value = fake_pw
    fake_cm.__exit__.return_value = False

    fake_sync_api = types.ModuleType("playwright.sync_api")
    fake_sync_api.sync_playwright = lambda: fake_cm
    fake_playwright_pkg = types.ModuleType("playwright")
    fake_playwright_pkg.sync_api = fake_sync_api
    monkeypatch.setitem(sys.modules, "playwright", fake_playwright_pkg)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", fake_sync_api)

    from slides_generator.renderer.pdf_renderer import render_pdf

    result = render_pdf("<html><body><section class='slide'>Hi</section></body></html>")
    assert result == fake_pdf
    fake_page.set_content.assert_called_once()
    fake_page.pdf.assert_called_once()
