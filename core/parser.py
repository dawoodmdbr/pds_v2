"""
core/parser.py
Extracts all text from a PDF or DOCX file.
Returns a single string or None if unreadable.
"""

from pathlib import Path

_MONOSPACE = {"courier new", "courier", "consolas", "lucida console", "monaco", "menlo"}


def parse(filepath: Path) -> str | None:
    suffix = filepath.suffix.lower()
    try:
        if suffix == ".pdf":
            return _parse_pdf(filepath)
        elif suffix == ".docx":
            return _parse_docx(filepath)
    except Exception:
        return None
    return None


def _parse_pdf(filepath: Path) -> str | None:
    import pdfplumber
    pages = []
    with pdfplumber.open(str(filepath)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n".join(pages) if pages else None


def _parse_docx(filepath: Path) -> str | None:
    from docx import Document
    doc = Document(str(filepath))
    lines = []
    for para in doc.paragraphs:
        if not para.text.strip():
            continue
        is_code = any(
            (run.font.name or "").lower() in _MONOSPACE
            for run in para.runs
        )
        lines.append(f"[CODE] {para.text}" if is_code else para.text)
    return "\n".join(lines) if lines else None
