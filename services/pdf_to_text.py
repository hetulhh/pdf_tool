"""
PDF → plain text conversion service.
Pure logic — no Flask imports.
"""

import io

import pdfplumber


def convert(pdf_bytes: bytes) -> tuple[bytes, dict]:
    pages = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = (page.extract_text(x_tolerance=3, y_tolerance=3) or "").strip()
            pages.append(f"--- Page {page_num} ---\n{text}")

    document_text = "\n\n".join(pages).strip()
    summary = {
        "pages": len(pages),
        "chars": len(document_text),
        "words": len(document_text.split()),
    }
    return document_text.encode("utf-8"), summary
