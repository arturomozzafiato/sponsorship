from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Try PyMuPDF (fitz) but degrade gracefully if unavailable
try:
    import fitz  # type: ignore
except Exception:  # ImportError or platform-specific errors
    fitz = None  # type: ignore


def extract_text_from_pdf(pdf_path: str, max_pages: int = 30) -> str:
    """Extracts text from a PDF using PyMuPDF if available.
    If PyMuPDF is not installed or fails to open the file, returns an empty string
    so the rest of the app can continue (you can paste org info manually).
    """
    if fitz is None:  # type: ignore
        # PyMuPDF not available in this environment
        return ""
    try:
        doc = fitz.open(pdf_path)  # type: ignore
        texts: list[str] = []
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            try:
                texts.append(page.get_text("text"))  # type: ignore
            except Exception:
                # If one page fails, skip it and continue
                continue
        return "\n\n".join(texts).strip()
    except Exception:
        # Any failure opening/parsing the PDF -> return empty so UI doesn't crash
        return ""
