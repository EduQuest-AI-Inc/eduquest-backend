"""
Integration tests for utils/pdf_utils.py — preprocess_pdf().

PDF fixtures are generated at test time using PyMuPDF so no binary files need
to be checked into the repo. The size threshold is patched to 64 KB in all
"large PDF" tests so fixture generation takes ~15 pages instead of ~5000.
"""
import os
import tempfile
import pytest
import fitz  # pymupdf

import utils.pdf_utils as pdf_utils_module
from utils.pdf_utils import preprocess_pdf

_TEST_THRESHOLD = 4 * 1024  # 4 KB — sits between the small (~2 KB) and large (~17 KB) fixtures


# ── Fixture builders ──────────────────────────────────────────────────────────

def _make_digital_pdf(tmp_path: str, page_count: int = 3) -> str:
    """Create a digital (selectable-text) PDF with headings and body paragraphs."""
    doc = fitz.open()
    for page_num in range(page_count):
        page = doc.new_page()
        # Heading — large font (>14pt) so preprocess_pdf keeps it
        page.insert_text((72, 72), f"Chapter {page_num + 1}: Important Topic", fontsize=20)
        # Body paragraph — normal size; only first sentence should be kept
        body = (
            "This is the first sentence of a body paragraph. "
            "This second sentence should be stripped by preprocessing. "
            "And this third sentence too."
        )
        page.insert_text((72, 120), body, fontsize=11)

    path = os.path.join(tmp_path, "digital.pdf")
    doc.save(path)
    doc.close()
    return path


def _make_large_digital_pdf(tmp_path: str) -> str:
    """Create a digital PDF that exceeds _TEST_THRESHOLD bytes (~17 KB at 25 pages)."""
    doc = fitz.open()
    for page_num in range(25):
        page = doc.new_page()
        page.insert_text((72, 72), f"Section {page_num}: Big Heading Here", fontsize=20)
        body = ("Word " * 300).strip() + ". Second sentence discarded by preprocessing."
        page.insert_text((72, 120), body, fontsize=11)

    path = os.path.join(tmp_path, "large_digital.pdf")
    doc.save(path, deflate=False)  # no deflate keeps file large
    doc.close()
    return path


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_small_pdf_returns_original_path(monkeypatch):
    monkeypatch.setattr(pdf_utils_module, "_SIZE_THRESHOLD_BYTES", _TEST_THRESHOLD)
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = _make_digital_pdf(tmp)
        assert os.path.getsize(pdf_path) < _TEST_THRESHOLD, "fixture is unexpectedly large"

        result = preprocess_pdf(pdf_path)

        assert result == pdf_path


@pytest.mark.integration
def test_large_digital_pdf_returns_preprocessed_txt_path(monkeypatch):
    monkeypatch.setattr(pdf_utils_module, "_SIZE_THRESHOLD_BYTES", _TEST_THRESHOLD)
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = _make_large_digital_pdf(tmp)
        assert os.path.getsize(pdf_path) >= _TEST_THRESHOLD, "fixture did not reach threshold"

        result = preprocess_pdf(pdf_path)

        assert result != pdf_path
        assert result.endswith("_preprocessed.txt")
        assert os.path.exists(result)


@pytest.mark.integration
def test_large_digital_pdf_preprocessed_content_contains_headings(monkeypatch):
    monkeypatch.setattr(pdf_utils_module, "_SIZE_THRESHOLD_BYTES", _TEST_THRESHOLD)
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = _make_large_digital_pdf(tmp)
        result = preprocess_pdf(pdf_path)

        with open(result, encoding="utf-8") as f:
            content = f.read()

        assert "Section 0: Big Heading Here" in content


@pytest.mark.integration
def test_large_digital_pdf_body_text_truncated_to_first_sentence(monkeypatch):
    monkeypatch.setattr(pdf_utils_module, "_SIZE_THRESHOLD_BYTES", _TEST_THRESHOLD)
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = _make_large_digital_pdf(tmp)
        result = preprocess_pdf(pdf_path)

        with open(result, encoding="utf-8") as f:
            content = f.read()

        assert "Second sentence discarded by preprocessing" not in content
