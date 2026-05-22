"""Tests for the HTML renderer."""

from __future__ import annotations

import pytest

from models.slide_plan import CompletedSlide, CompleteSlideDeck
from utils.rendering.html_renderer import render_html

pytestmark = pytest.mark.unit


def _deck() -> CompleteSlideDeck:
    layouts = ["title", "concept_intro", "two_col", "visual_focus", "skill_card", "summary"]
    slides = []
    for i, layout in enumerate(layouts):
        slides.append(
            CompletedSlide(
                index=i,
                layout=layout,
                title=f"Slide {i}",
                bullets=["Bullet one", "Bullet two"],
                speaker_notes="Notes",
                bloom_level="Apply" if layout == "skill_card" else None,
                difficulty="intermediate" if layout == "skill_card" else None,
                visual_caption="A diagram caption" if layout == "visual_focus" else None,
                prerequisites=["Prior concept"] if layout == "concept_intro" else [],
                visual_status="placeholder",
            )
        )
    return CompleteSlideDeck(lesson_name="Test Lesson", slides=slides)


def test_render_html_returns_string():
    html = render_html(_deck(), {"lesson_name": "Test Lesson"})
    assert isinstance(html, str)
    assert len(html) > 0


def test_render_html_has_doctype_and_styles():
    html = render_html(_deck(), {})
    assert "<!DOCTYPE html>" in html
    assert "<style>" in html
    assert "@page" in html


def test_render_html_one_section_per_slide():
    deck = _deck()
    html = render_html(deck, {})
    section_count = html.count('<section class="slide')
    assert section_count == len(deck.slides)


def test_render_html_includes_meta_subtitle():
    html = render_html(
        _deck(),
        {
            "lesson_name": "Lesson X",
            "period_name": "Biology A",
            "grade_level": "9",
            "week_start": "2026-09-07",
            "week_end": "2026-09-11",
        },
    )
    assert "Biology A" in html
    assert "2026-09-07" in html


def test_render_html_includes_bloom_badge():
    html = render_html(_deck(), {})
    assert "Bloom: Apply" in html
    assert "Difficulty: intermediate" in html


def test_render_html_visual_caption_for_visual_focus():
    html = render_html(_deck(), {})
    assert "A diagram caption" in html


def test_render_html_concept_prerequisites():
    html = render_html(_deck(), {})
    assert "Prior concept" in html


def test_render_html_placeholder_text_for_missing_visual():
    html = render_html(_deck(), {})
    assert "No visual available" in html


# ─── Image embedding ─────────────────────────────────────────────────────────

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc"
    b"\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _visual_focus_deck(visual_path: str, visual_status: str) -> CompleteSlideDeck:
    slide = CompletedSlide(
        index=0,
        layout="visual_focus",
        title="Diagram Slide",
        bullets=["Caption bullet"],
        speaker_notes="Notes",
        visual_path=visual_path,
        visual_status=visual_status,
        visual_caption="Test caption",
    )
    return CompleteSlideDeck(lesson_name="Test", slides=[slide])


def test_render_html_embeds_image_as_base64(tmp_path):
    img_path = tmp_path / "test.png"
    img_path.write_bytes(PNG_BYTES)

    html = render_html(_visual_focus_deck(str(img_path), "approved"), {})

    assert "data:image/png;base64," in html
    assert "file://" not in html


def test_render_html_flagged_image_also_embedded(tmp_path):
    img_path = tmp_path / "test.png"
    img_path.write_bytes(PNG_BYTES)

    html = render_html(_visual_focus_deck(str(img_path), "flagged"), {})

    assert "data:image/png;base64," in html
    assert "file://" not in html


def test_render_html_missing_visual_path_shows_placeholder(tmp_path):
    """If visual_path is set but file is gone, fall back to placeholder."""
    html = render_html(_visual_focus_deck(str(tmp_path / "gone.png"), "approved"), {})

    assert "No visual available" in html
    assert "file://" not in html


def test_render_html_never_emits_file_protocol():
    """No file:// URIs should appear in any rendered HTML."""
    html = render_html(_deck(), {})
    assert "file://" not in html
