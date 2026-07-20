"""Regex-only PII redaction layer — no LLM call, no network.

Called synchronously before every AI prompt that touches learner-submitted text.
Best-effort: reduces PII exposure but is not a compliance guarantee.
"""
import re


class PIIRedactor:
    _PATTERNS: list[tuple[re.Pattern, str]] = [
        # Email addresses
        (re.compile(r'\b[\w.+\-]+@[\w\-]+\.[\w.\-]+\b'), "[EMAIL]"),
        # US phone numbers (various formats)
        (re.compile(
            r'\b(?:\+?1[\s.\-]?)?(?:\(\d{3}\)|\d{3})[\s.\-]\d{3}[\s.\-]\d{4}\b'
        ), "[PHONE]"),
        # US Social Security numbers
        (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), "[SSN]"),
        # Honorific + name (Mr. Jane Doe, Dr. Smith)
        (re.compile(
            r'\b(?:Mr\.|Mrs\.|Ms\.|Miss|Dr\.|Prof\.)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
        ), "[NAME]"),
        # Two consecutive capitalized words that look like a full name
        # Heuristic: avoids common title-case phrases by requiring both words to be 3+ chars
        (re.compile(r'\b([A-Z][a-z]{2,})\s([A-Z][a-z]{2,})\b'), "[NAME]"),
    ]

    def redact(self, text: str) -> str:
        """Return text with PII patterns replaced by bracketed placeholders."""
        for pattern, replacement in self._PATTERNS:
            text = pattern.sub(replacement, text)
        return text
