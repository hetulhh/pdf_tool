"""
Async job polling routes.

GET  /jobs/<job_id>          → job status (JSON, no binary)
GET  /jobs/<job_id>/result   → download result when status == "done"
GET  /jobs                   → list all jobs (useful for debugging)
"""

from __future__ import annotations

import json
import logging

from flask import Blueprint

from services import job_queue
from utils.auth import check_api_key
from utils.response import cors_response

logger = logging.getLogger(__name__)

jobs_bp = Blueprint("jobs", __name__, url_prefix="/jobs")


def _unauthorized():
    return cors_response(
        json.dumps({"error": "Unauthorized"}),
        401, {"Content-Type": "application/json"},
    )


# ─────────────────────────────────────────────
# GET /jobs/<job_id>
# ─────────────────────────────────────────────

@jobs_bp.route("/<job_id>", methods=["GET", "OPTIONS"])
def job_status(job_id: str):
    if not check_api_key():
        return _unauthorized()

    job = job_queue.get(job_id)
    if not job:
        return cors_response(
            json.dumps({"error": "Job not found", "job_id": job_id}),
            404, {"Content-Type": "application/json"},
        )

    payload = {
        **job,
        "status_url": f"/jobs/{job_id}",
        "result_url": f"/jobs/{job_id}/result" if job["status"] == "done" else None,
    }
    return cors_response(json.dumps(payload), 200, {"Content-Type": "application/json"})


# ─────────────────────────────────────────────
# GET /jobs/<job_id>/result
# ─────────────────────────────────────────────

@jobs_bp.route("/<job_id>/result", methods=["GET", "OPTIONS"])
def job_result(job_id: str):
    if not check_api_key():
        return _unauthorized()

    job = job_queue.get_result(job_id)
    if not job:
        return cors_response(
            json.dumps({"error": "Job not found", "job_id": job_id}),
            404, {"Content-Type": "application/json"},
        )

    status = job["status"]

    if status == "pending" or status == "running":
        return cors_response(
            json.dumps({
                "error":      "Job not complete yet",
                "status":     status,
                "status_url": f"/jobs/{job_id}",
            }),
            202, {"Content-Type": "application/json"},
        )

    if status == "failed":
        return cors_response(
            json.dumps({"error": "Job failed", "detail": job.get("error")}),
            500, {"Content-Type": "application/json"},
        )

    # status == "done"
    data         = job.get("result") or b""
    content_type = job.get("content_type") or "application/octet-stream"
    filename     = job.get("filename") or "result"
    extra        = job.get("headers") or {}

    return cors_response(data, 200, {
        "Content-Type":        content_type,
        "Content-Disposition": f'attachment; filename="{filename}"',
        **extra,
    })


# ─────────────────────────────────────────────
# GET /jobs   (debug / admin view)
# ─────────────────────────────────────────────

@jobs_bp.route("", methods=["GET", "OPTIONS"])
def list_jobs():
    if not check_api_key():
        return _unauthorized()

    # Reap stale jobs first
    reaped = job_queue.reap_expired()
    logger.debug("Reaped %d expired jobs", reaped)

    # Collect snapshots (no binary)
    snapshots = []
    import threading
    # Access internal _jobs safely via the public get() interface
    # We iterate IDs from a snapshot of keys
    from services.job_queue import _jobs, _lock
    with _lock:
        ids = list(_jobs.keys())

    for jid in ids:
        snap = job_queue.get(jid)
        if snap:
            snap["status_url"]  = f"/jobs/{jid}"
            snap["result_url"]  = f"/jobs/{jid}/result" if snap["status"] == "done" else None
            snapshots.append(snap)

    snapshots.sort(key=lambda j: j["created_at"], reverse=True)
    return cors_response(
        json.dumps({"jobs": snapshots, "count": len(snapshots)}),
        200, {"Content-Type": "application/json"},
    )
