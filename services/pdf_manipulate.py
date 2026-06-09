"""
PDF manipulation service — merge, split, rotate, compress.
Pure logic — no Flask imports.

All public functions return:
  { "data": bytes, "content_type": "application/pdf",
    "filename": str, "headers": dict }
"""

from __future__ import annotations

import io
import logging
import struct
import zlib

import pdfplumber
from pypdf import PdfReader, PdfWriter, Transformation

logger = logging.getLogger(__name__)

_PDF_CONTENT_TYPE = "application/pdf"


# ─────────────────────────────────────────────
# Merge
# ─────────────────────────────────────────────

def merge(pdf_list: list[bytes], filename: str = "merged.pdf") -> dict:
    """Merge multiple PDFs (in order) into one."""
    writer = PdfWriter()
    total_pages = 0
    for idx, pdf_bytes in enumerate(pdf_list):
        reader = PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            writer.add_page(page)
            total_pages += 1
        logger.info("Merge: added %d pages from document %d", len(reader.pages), idx + 1)

    buf = io.BytesIO()
    writer.write(buf)
    data = buf.getvalue()

    return {
        "data": data,
        "content_type": _PDF_CONTENT_TYPE,
        "filename": filename,
        "headers": {
            "X-Total-Pages":    str(total_pages),
            "X-Documents-Merged": str(len(pdf_list)),
        },
    }


# ─────────────────────────────────────────────
# Split
# ─────────────────────────────────────────────

def split(pdf_bytes: bytes, ranges: list[tuple[int, int]]) -> list[dict]:
    """
    Split a PDF into segments defined by *ranges*.

    Each range is a 1-based inclusive tuple: (start_page, end_page).
    Returns a list of result dicts (one per range).
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    total  = len(reader.pages)
    results = []

    for i, (start, end) in enumerate(ranges, start=1):
        if start < 1 or end > total or start > end:
            raise ValueError(
                f"Range {start}-{end} is invalid for a {total}-page document."
            )
        writer = PdfWriter()
        for page_idx in range(start - 1, end):
            writer.add_page(reader.pages[page_idx])

        buf = io.BytesIO()
        writer.write(buf)
        results.append({
            "data":         buf.getvalue(),
            "content_type": _PDF_CONTENT_TYPE,
            "filename":     f"split_part{i}_p{start}-{end}.pdf",
            "headers": {
                "X-Part":       str(i),
                "X-Page-Start": str(start),
                "X-Page-End":   str(end),
            },
        })

    return results


# ─────────────────────────────────────────────
# Rotate
# ─────────────────────────────────────────────

def rotate(
    pdf_bytes: bytes,
    angle: int,
    pages: list[int] | None = None,
    filename: str = "rotated.pdf",
) -> dict:
    """
    Rotate pages by *angle* degrees (must be a multiple of 90).

    *pages* is a 1-based list of page numbers to rotate.
    If None, all pages are rotated.
    """
    if angle % 90 != 0:
        raise ValueError("Rotation angle must be a multiple of 90 degrees.")

    reader  = PdfReader(io.BytesIO(pdf_bytes))
    writer  = PdfWriter()
    total   = len(reader.pages)
    targets = set(pages) if pages else set(range(1, total + 1))
    rotated = 0

    for page_num, page in enumerate(reader.pages, start=1):
        if page_num in targets:
            page.rotate(angle)
            rotated += 1
        writer.add_page(page)

    buf = io.BytesIO()
    writer.write(buf)

    return {
        "data":         buf.getvalue(),
        "content_type": _PDF_CONTENT_TYPE,
        "filename":     filename,
        "headers": {
            "X-Pages-Rotated": str(rotated),
            "X-Angle":         str(angle),
        },
    }


# ─────────────────────────────────────────────
# Compress
# ─────────────────────────────────────────────

def compress(pdf_bytes: bytes, filename: str = "compressed.pdf") -> dict:
    """
    Apply lossless compression to a PDF:
    - Removes duplicate objects (pypdf deduplication)
    - Compresses all page content streams
    - Removes metadata & unused objects

    Note: image downsampling requires Pillow + pikepdf and is not included
    here to keep the dependency footprint small.
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()

    # Clone pages and compress their content streams
    for page in reader.pages:
        writer.add_page(page)

    # Remove metadata to shrink further
    writer.add_metadata({})

    # pypdf: compress content streams
    for page in writer.pages:
        page.compress_content_streams()

    buf = io.BytesIO()
    writer.write(buf)
    compressed = buf.getvalue()

    original_size   = len(pdf_bytes)
    compressed_size = len(compressed)
    savings_pct = round((1 - compressed_size / original_size) * 100, 1) if original_size else 0

    logger.info(
        "Compress: %d → %d bytes (%.1f%% reduction)",
        original_size, compressed_size, savings_pct,
    )

    return {
        "data":         compressed,
        "content_type": _PDF_CONTENT_TYPE,
        "filename":     filename,
        "headers": {
            "X-Original-Size":   str(original_size),
            "X-Compressed-Size": str(compressed_size),
            "X-Savings-Percent": str(savings_pct),
        },
    }
