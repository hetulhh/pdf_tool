"""
PDF routes — /pdf/to-excel, /pdf/to-word, /pdf/to-text, and /pdf/metadata
All HTTP handling lives here; conversion logic is in services/.
"""

import json
import logging

from flask import Blueprint, request

from services.pdf_metadata import extract as extract_metadata
from services.pdf_to_excel import convert as convert_to_excel
from services.pdf_to_text import convert as convert_to_text
from services.pdf_to_word import convert as convert_to_word
from utils.auth import check_api_key
from utils.request import extract_pdf_bytes
from utils.response import cors_response

logger = logging.getLogger(__name__)

pdf_bp = Blueprint("pdf", __name__, url_prefix="/pdf")


def _attachment_filename(default_name: str) -> str:
    filename = request.args.get("filename")
    if not filename and request.content_type and "application/json" in request.content_type:
        body = request.get_json(silent=True) or {}
        filename = body.get("filename")
    return filename or default_name


def _unauthorized_response() -> tuple:
    return cors_response(
        json.dumps({"error": "Unauthorized", "detail": "Invalid or missing API key"}),
        401,
        {"Content-Type": "application/json"},
    )


def _bad_request(message: str) -> tuple:
    return cors_response(json.dumps({"error": message}), 400,
                         {"Content-Type": "application/json"})


def _server_error(message: str) -> tuple:
    return cors_response(json.dumps({"error": message}), 500,
                         {"Content-Type": "application/json"})


# ─────────────────────────────────────────────
# POST /pdf/to-excel
# ─────────────────────────────────────────────

@pdf_bp.route("/to-excel", methods=["POST", "OPTIONS"])
def pdf_to_excel():
    if request.method == "OPTIONS":
        return cors_response("", 204)

    if not check_api_key():
        return _unauthorized_response()

    try:
        pdf_bytes = extract_pdf_bytes()
    except ValueError as e:
        return _bad_request(str(e))

    try:
        xlsx_bytes, summary = convert_to_excel(pdf_bytes)
    except Exception as e:
        logger.exception("Excel conversion failed")
        return _server_error(f"Conversion failed: {e}")

    filename = _attachment_filename("converted.xlsx")
    logger.info("Excel conversion successful: %s", summary)
    return cors_response(xlsx_bytes, 200, {
        "Content-Type":        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Pages":             str(summary["pages"]),
        "X-Tables-Found":      str(summary["tables_found"]),
        "X-Text-Sheets":       str(summary["text_sheets"]),
    })


# ─────────────────────────────────────────────
# POST /pdf/to-word
# ─────────────────────────────────────────────

@pdf_bp.route("/to-word", methods=["POST", "OPTIONS"])
def pdf_to_word():
    if request.method == "OPTIONS":
        return cors_response("", 204)

    if not check_api_key():
        return _unauthorized_response()

    try:
        pdf_bytes = extract_pdf_bytes()
    except ValueError as e:
        return _bad_request(str(e))

    try:
        docx_bytes = convert_to_word(pdf_bytes)
    except Exception as e:
        logger.exception("Word conversion failed")
        return _server_error(f"Conversion failed: {e}")

    filename = _attachment_filename("converted.docx")
    logger.info("Word conversion successful")
    return cors_response(docx_bytes, 200, {
        "Content-Type":        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "Content-Disposition": f'attachment; filename="{filename}"',
    })


# ─────────────────────────────────────────────
# POST /pdf/to-text
# ─────────────────────────────────────────────

@pdf_bp.route("/to-text", methods=["POST", "OPTIONS"])
def pdf_to_text():
    if request.method == "OPTIONS":
        return cors_response("", 204)

    if not check_api_key():
        return _unauthorized_response()

    try:
        pdf_bytes = extract_pdf_bytes()
    except ValueError as e:
        return _bad_request(str(e))

    try:
        text_bytes, summary = convert_to_text(pdf_bytes)
    except Exception as e:
        logger.exception("Text conversion failed")
        return _server_error(f"Conversion failed: {e}")

    filename = _attachment_filename("converted.txt")
    logger.info("Text conversion successful: %s", summary)
    return cors_response(text_bytes, 200, {
        "Content-Type":        "text/plain; charset=utf-8",
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Pages":             str(summary["pages"]),
        "X-Characters":        str(summary["chars"]),
        "X-Word-Count":        str(summary["words"]),
    })


# ─────────────────────────────────────────────
# POST /pdf/metadata
# ─────────────────────────────────────────────

@pdf_bp.route("/metadata", methods=["POST", "OPTIONS"])
def pdf_metadata():
    if request.method == "OPTIONS":
        return cors_response("", 204)

    if not check_api_key():
        return _unauthorized_response()

    try:
        pdf_bytes = extract_pdf_bytes()
    except ValueError as e:
        return _bad_request(str(e))

    try:
        metadata = extract_metadata(pdf_bytes)
    except Exception as e:
        logger.exception("Metadata extraction failed")
        return _server_error(f"Extraction failed: {e}")

    logger.info("Metadata extraction successful")
    return cors_response(json.dumps(metadata), 200, {
        "Content-Type": "application/json",
    })
