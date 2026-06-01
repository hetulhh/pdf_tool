"""
PDF bytes extraction from incoming Flask requests.
Supports multipart/form-data, application/json (base64), and raw binary.
"""

import base64

from flask import request


def extract_pdf_bytes() -> bytes:
    content_type = request.content_type or ""

    # ── multipart/form-data (field name: "file") ────────────────────
    if "multipart/form-data" in content_type:
        file = request.files.get("file")
        if not file:
            raise ValueError("No 'file' field found in multipart form data.")
        data = file.read()
        if not data:
            raise ValueError("Uploaded file is empty.")
        return data

    # ── application/json  { "pdf_base64": "<b64>" } ─────────────────
    if "application/json" in content_type:
        body = request.get_json(silent=True) or {}
        b64  = body.get("pdf_base64") or body.get("file")
        if not b64:
            raise ValueError("JSON body must include a 'pdf_base64' key.")
        try:
            return base64.b64decode(b64)
        except Exception:
            raise ValueError("'pdf_base64' is not valid base64.")

    # ── Raw binary body ─────────────────────────────────────────────
    data = request.get_data()
    if data:
        return data

    raise ValueError(
        "Send the PDF as: multipart/form-data (field='file'), "
        "JSON {'pdf_base64': '<b64>'}, or a raw binary body."
    )
