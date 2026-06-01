"""
API key authentication helper.
"""

import hmac
import logging
import os

from flask import request

logger  = logging.getLogger(__name__)
_API_KEY: str = os.environ.get("PDF_API_KEY", "")


def check_api_key() -> bool:
    if not _API_KEY:
        logger.error("PDF_API_KEY environment variable is not set. All requests blocked.")
        return False
    incoming = request.headers.get("X-API-Key", "")
    return hmac.compare_digest(
        incoming.encode("utf-8"),
        _API_KEY.encode("utf-8"),
    )
