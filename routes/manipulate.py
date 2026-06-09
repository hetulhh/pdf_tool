"""
PDF manipulation routes — /pdf/merge, /pdf/split, /pdf/rotate, /pdf/compress
All support both synchronous and async (?async=true) execution.
"""

from __future__ import annotations

import json
import logging

from flask import Blueprint, request, send_file
import io

from services import job_queue
from services.pdf_manipulate import compress, merge, rotate, split
from utils.auth import check_api_key
from utils.request import extract_pdf_bytes
from utils.response import cors_response

logger = logging.getLogger(__name__)

manipulate_bp = Blueprint("manipulate", __name__, url_prefix="/pdf")


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _unauthorized():
    return cors_response(
        json.dumps({"error": "Unauthorized", "detail": "Invalid or missing API key"}),
        401, {"Content-Type": "application/json"},
    )

def _bad(msg: str):
    return cors_response(json.dumps({"error": msg}), 400, {"Content-Type": "application/json"})

def _err(msg: str):
    return cors_response(json.dumps({"error": msg}), 500, {"Content-Type": "application/json"})

def _is_async() -> bool:
    return request.args.get("async", "").lower() in ("1", "true", "yes")

def _accepted(job_id: str):
    body = json.dumps({
        "job_id":     job_id,
        "status":     "pending",
        "status_url": f"/jobs/{job_id}",
        "result_url": f"/jobs/{job_id}/result",
    })
    return cors_response(body, 202, {"Content-Type": "application/json"})

def _result_response(result: dict):
    """Turn a service result dict into a Flask response."""
    return cors_response(
        result["data"],
        200,
        {
            "Content-Type":        result["content_type"],
            "Content-Disposition": f'attachment; filename="{result["filename"]}"',
            **result.get("headers", {}),
        },
    )


# ─────────────────────────────────────────────
# POST /pdf/merge
# Body: multipart with multiple "file" fields  OR  JSON { "files": [b64, b64, ...] }
# ─────────────────────────────────────────────

@manipulate_bp.route("/merge", methods=["POST", "OPTIONS"])
def pdf_merge():
    if request.method == "OPTIONS":
        return cors_response("", 204)
    if not check_api_key():
        return _unauthorized()

    try:
        pdf_list = _extract_multiple_pdfs()
    except ValueError as e:
        return _bad(str(e))

    filename = request.args.get("filename", "merged.pdf")

    if _is_async():
        job_id = job_queue.submit(merge, pdf_list, filename)
        return _accepted(job_id)

    try:
        result = merge(pdf_list, filename)
    except Exception as e:
        logger.exception("Merge failed")
        return _err(f"Merge failed: {e}")

    return _result_response(result)


# ─────────────────────────────────────────────
# POST /pdf/split
# Body: single PDF  +  query params or JSON for ranges
# ?ranges=1-3,5-7   OR  JSON { "ranges": [[1,3],[5,7]] }
# ─────────────────────────────────────────────

@manipulate_bp.route("/split", methods=["POST", "OPTIONS"])
def pdf_split():
    if request.method == "OPTIONS":
        return cors_response("", 204)
    if not check_api_key():
        return _unauthorized()

    try:
        pdf_bytes = extract_pdf_bytes()
        ranges    = _parse_ranges()
    except ValueError as e:
        return _bad(str(e))

    if _is_async():
        job_id = job_queue.submit(_split_to_zip, pdf_bytes, ranges)
        return _accepted(job_id)

    try:
        parts   = split(pdf_bytes, ranges)
        zip_data = _parts_to_zip(parts)
    except Exception as e:
        logger.exception("Split failed")
        return _err(f"Split failed: {e}")

    filename = request.args.get("filename", "split_parts.zip")
    return cors_response(zip_data, 200, {
        "Content-Type":        "application/zip",
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Parts":             str(len(parts)),
    })


# ─────────────────────────────────────────────
# POST /pdf/rotate
# ?angle=90  &pages=1,3,5  (pages optional — omit to rotate all)
# ─────────────────────────────────────────────

@manipulate_bp.route("/rotate", methods=["POST", "OPTIONS"])
def pdf_rotate():
    if request.method == "OPTIONS":
        return cors_response("", 204)
    if not check_api_key():
        return _unauthorized()

    try:
        pdf_bytes = extract_pdf_bytes()
        angle, pages = _parse_rotate_params()
    except ValueError as e:
        return _bad(str(e))

    filename = request.args.get("filename", "rotated.pdf")

    if _is_async():
        job_id = job_queue.submit(rotate, pdf_bytes, angle, pages, filename)
        return _accepted(job_id)

    try:
        result = rotate(pdf_bytes, angle, pages, filename)
    except Exception as e:
        logger.exception("Rotate failed")
        return _err(f"Rotate failed: {e}")

    return _result_response(result)


# ─────────────────────────────────────────────
# POST /pdf/compress
# ─────────────────────────────────────────────

@manipulate_bp.route("/compress", methods=["POST", "OPTIONS"])
def pdf_compress():
    if request.method == "OPTIONS":
        return cors_response("", 204)
    if not check_api_key():
        return _unauthorized()

    try:
        pdf_bytes = extract_pdf_bytes()
    except ValueError as e:
        return _bad(str(e))

    filename = request.args.get("filename", "compressed.pdf")

    if _is_async():
        job_id = job_queue.submit(compress, pdf_bytes, filename)
        return _accepted(job_id)

    try:
        result = compress(pdf_bytes, filename)
    except Exception as e:
        logger.exception("Compress failed")
        return _err(f"Compress failed: {e}")

    return _result_response(result)


# ─────────────────────────────────────────────
# Parameter parsing helpers
# ─────────────────────────────────────────────

def _extract_multiple_pdfs() -> list[bytes]:
    """Support multipart (multiple 'file' fields) or JSON array."""
    content_type = request.content_type or ""

    if "multipart/form-data" in content_type:
        files = request.files.getlist("file")
        if not files:
            raise ValueError("No 'file' fields found in multipart data.")
        results = []
        for f in files:
            data = f.read()
            if data:
                results.append(data)
        if not results:
            raise ValueError("All uploaded files were empty.")
        return results

    if "application/json" in content_type:
        import base64
        body = request.get_json(silent=True) or {}
        b64_list = body.get("files") or []
        if not b64_list:
            raise ValueError("JSON body must include a 'files' array of base64 strings.")
        decoded = []
        for i, b64 in enumerate(b64_list):
            try:
                decoded.append(base64.b64decode(b64))
            except Exception:
                raise ValueError(f"Item {i} in 'files' is not valid base64.")
        return decoded

    raise ValueError(
        "For merge, send multipart/form-data with multiple 'file' fields, "
        "or JSON with a 'files' array of base64-encoded PDFs."
    )


def _parse_ranges() -> list[tuple[int, int]]:
    """Parse ?ranges=1-3,5-7  or JSON body { 'ranges': [[1,3],[5,7]] }."""
    raw_qs = request.args.get("ranges")
    if raw_qs:
        return _ranges_from_string(raw_qs)

    if "application/json" in (request.content_type or ""):
        body = request.get_json(silent=True) or {}
        raw_json = body.get("ranges")
        if raw_json:
            if isinstance(raw_json, str):
                return _ranges_from_string(raw_json)
            if isinstance(raw_json, list):
                result = []
                for item in raw_json:
                    if isinstance(item, (list, tuple)) and len(item) == 2:
                        result.append((int(item[0]), int(item[1])))
                    elif isinstance(item, str):
                        result.extend(_ranges_from_string(item))
                return result

    raise ValueError(
        "Provide page ranges via ?ranges=1-3,5-7 "
        "or JSON body { 'ranges': [[1,3],[5,7]] }."
    )


def _ranges_from_string(s: str) -> list[tuple[int, int]]:
    result = []
    for part in s.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            result.append((int(a.strip()), int(b.strip())))
        else:
            n = int(part)
            result.append((n, n))
    return result


def _parse_rotate_params() -> tuple[int, list[int] | None]:
    angle_str = request.args.get("angle")
    pages_str = request.args.get("pages")

    if not angle_str and "application/json" in (request.content_type or ""):
        body      = request.get_json(silent=True) or {}
        angle_str = str(body.get("angle", ""))
        if not pages_str:
            pages_raw = body.get("pages")
            if pages_raw:
                pages_str = ",".join(str(p) for p in pages_raw) if isinstance(pages_raw, list) else str(pages_raw)

    if not angle_str:
        raise ValueError("Provide ?angle=90 (or 180, 270).")

    try:
        angle = int(angle_str)
    except ValueError:
        raise ValueError("'angle' must be an integer (90, 180, or 270).")

    pages = None
    if pages_str:
        pages = [int(p.strip()) for p in pages_str.split(",") if p.strip()]

    return angle, pages


# ─────────────────────────────────────────────
# ZIP helper for split results
# ─────────────────────────────────────────────

def _parts_to_zip(parts: list[dict]) -> bytes:
    """Bundle split PDF parts into a ZIP archive."""
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for part in parts:
            zf.writestr(part["filename"], part["data"])
    return buf.getvalue()


def _split_to_zip(pdf_bytes: bytes, ranges: list) -> dict:
    """Wrapper so split+zip works as a single job_queue task."""
    parts    = split(pdf_bytes, ranges)
    zip_data = _parts_to_zip(parts)
    return {
        "data":         zip_data,
        "content_type": "application/zip",
        "filename":     "split_parts.zip",
        "headers":      {"X-Parts": str(len(parts))},
    }
