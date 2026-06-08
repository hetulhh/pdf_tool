"""
PDF metadata extraction service.
Pure logic — no Flask imports.
"""

import io

import pdfplumber


def extract(pdf_bytes: bytes) -> dict:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        metadata = pdf.metadata or {}
        normalized_metadata = {
            str(key): str(value) if value is not None else ""
            for key, value in metadata.items()
        }
        page_sizes = [
            {
                "page": page_num,
                "width": round(page.width, 2),
                "height": round(page.height, 2),
            }
            for page_num, page in enumerate(pdf.pages, start=1)
        ]

    return {
        "pages": len(page_sizes),
        "metadata": normalized_metadata,
        "page_sizes": page_sizes,
    }
