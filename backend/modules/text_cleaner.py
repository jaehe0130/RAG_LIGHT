import re
from typing import List


MIN_TEXT_LENGTH = 20


def clean_ocr_text(text: str, warnings: List[str] | None = None) -> str:
    """Clean OCR text so it can be passed to RAG as one plain string."""
    warnings = warnings if warnings is not None else []

    if not text:
        warnings.append("OCR text is empty.")
        return ""

    # Normalize Windows and old Mac line endings first.
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")

    # Trim each line, collapse repeated spaces/tabs, and remove empty edge lines.
    lines = []
    for line in cleaned.split("\n"):
        line = re.sub(r"[ \t]+", " ", line).strip()
        lines.append(line)

    cleaned = "\n".join(lines).strip()

    # Keep paragraph breaks, but remove excessive blank lines.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    # RAG usually works best with a single string, not a list of OCR fragments.
    cleaned = re.sub(r"[ \t]+", " ", cleaned).strip()

    if len(cleaned.replace(" ", "").replace("\n", "")) < MIN_TEXT_LENGTH:
        warnings.append("OCR text is too short. The file may be blank, scanned poorly, or unsupported.")

    return cleaned
