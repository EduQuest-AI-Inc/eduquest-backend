import logging
import os

logger = logging.getLogger(__name__)

_SIZE_THRESHOLD_BYTES = 20 * 1024 * 1024  # 20 MB

_STRUCTURAL_KEYWORDS = ("objective", "summary", "conclusion", "glossary", "key term")


def preprocess_pdf(file_path: str) -> str:
    """Return a path to a preprocessed .txt file for large digital PDFs, or the original path.

    Falls back to the original path for: files under 20 MB, scanned/image PDFs, or any
    extraction error.
    """
    if os.path.getsize(file_path) < _SIZE_THRESHOLD_BYTES:
        return file_path

    try:
        import fitz  # pymupdf

        doc = fitz.open(file_path)

        # Detect scanned PDFs: check first 5 pages for selectable text
        has_text = any(doc[i].get_text("text").strip() for i in range(min(5, len(doc))))
        if not has_text:
            logger.warning("Scanned/image PDF detected, skipping preprocessing: %s", os.path.basename(file_path))
            doc.close()
            return file_path

        kept_blocks: list[str] = []

        for page in doc:
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                if block.get("type") != 0:  # 0 = text block
                    continue
                lines = block.get("lines", [])
                if not lines:
                    continue

                # Collect all spans across all lines in the block
                all_spans = [span for line in lines for span in line.get("spans", [])]
                if not all_spans:
                    continue

                raw = " ".join(span["text"] for span in all_spans).strip()
                if not raw:
                    continue
                # PyMuPDF can return surrogate or otherwise non-UTF-8-encodable
                # characters when glyph-to-Unicode mapping is incomplete; replace them.
                block_text = raw.encode("utf-8", errors="replace").decode("utf-8")

                max_size = max(span["size"] for span in all_spans)
                is_bold = any(span["flags"] & 16 for span in all_spans)  # bit 4 = bold

                # Keep headings (large or bold text)
                if max_size > 14 or is_bold:
                    kept_blocks.append(block_text)
                    continue

                # Keep blocks that match structural keywords
                lower = block_text.lower()
                if any(lower.startswith(kw) for kw in _STRUCTURAL_KEYWORDS):
                    kept_blocks.append(block_text)
                    continue

                # Keep first sentence of each body paragraph
                first_sentence = block_text.split(".")[0].strip()
                if first_sentence:
                    kept_blocks.append(first_sentence + ".")

        doc.close()

        output_path = os.path.splitext(file_path)[0] + "_preprocessed.txt"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(kept_blocks))

        logger.info(
            "Preprocessed %s → %s (%.1f MB → %.1f MB)",
            os.path.basename(file_path),
            os.path.basename(output_path),
            os.path.getsize(file_path) / (1024 * 1024),
            os.path.getsize(output_path) / (1024 * 1024),
        )
        return output_path

    except Exception as e:
        logger.warning("PDF preprocessing failed for %s, using original: %s", os.path.basename(file_path), e)
        return file_path
