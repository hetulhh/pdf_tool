"""
CORS-aware response helper.
"""


def cors_response(body, status: int = 200, extra_headers: dict = None):
    headers = {
        "Access-Control-Allow-Origin":  "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-API-Key",
    }
    if extra_headers:
        headers.update(extra_headers)
    return body, status, headers
