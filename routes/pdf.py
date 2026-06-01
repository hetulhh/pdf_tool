"""
PDF routes — /pdf/to-excel and /pdf/to-word
All HTTP handling lives here; conversion logic is in services/.
"""

import json
import logging

from flask import Blueprint, request

from services.pdf_to_excel import convert as convert_to_excel
from services.pdf_to_word import convert as convert_to_word
from utils.auth import check_api_key
from utils.request import extract_pdf_bytes
from utils.response import cors_response

logger = logging.getLogger(__name__)

pdf_bp = Blueprint("pdf", __name__, url_prefix="/pdf")


# ─────────────────────────────────────────────
# POST /pdf/to-excel
# ─────────────────────────────────────────────

@pdf_bp.route("/to-excel", methods=["POST", "OPTIONS"])
def pdf_to_excel():
    if request.method == "OPTIONS":
        return cors_response("", 204)

    if not check_api_key():
        return cors_response(
            json.dumps({"error": "Unauthorized", "detail": "Invalid or missing API key"}),
            401,
            {"Content-Type": "application/json"},
        )

    try:
        pdf_bytes = extract_pdf_bytes()
    except ValueError as e:
        return cors_response(json.dumps({"error": str(e)}), 400,
                             {"Content-Type": "application/json"})

    try:
        xlsx_bytes, summary = convert_to_excel(pdf_bytes)
    except Exception as e:
        logger.exception("Excel conversion failed")
        return cors_response(json.dumps({"error": f"Conversion failed: {e}"}), 500,
                             {"Content-Type": "application/json"})

    return cors_response(xlsx_bytes, 200, {
        "Content-Type":        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "Content-Disposition": 'attachment; filename="converted.xlsx"',
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
        return cors_response(
            json.dumps({"error": "Unauthorized", "detail": "Invalid or missing API key"}),
            401,
            {"Content-Type": "application/json"},
        )

    try:
        pdf_bytes = extract_pdf_bytes()
    except ValueError as e:
        return cors_response(json.dumps({"error": str(e)}), 400,
                             {"Content-Type": "application/json"})

    try:
        docx_bytes = convert_to_word(pdf_bytes)
    except Exception as e:
        logger.exception("Word conversion failed")
        return cors_response(json.dumps({"error": f"Conversion failed: {e}"}), 500,
                             {"Content-Type": "application/json"})

    return cors_response(docx_bytes, 200, {
        "Content-Type":        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "Content-Disposition": 'attachment; filename="converted.docx"',
    })
