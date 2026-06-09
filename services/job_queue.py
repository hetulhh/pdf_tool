"""
Async job queue — in-memory, thread-based.
No Redis or Celery required; works on Render free tier with a single worker.

Job lifecycle:  pending → running → done | failed
"""

from __future__ import annotations

import logging
import threading
import time
import traceback
import uuid
from typing import Callable

logger = logging.getLogger(__name__)

# How long to keep completed/failed jobs in memory (seconds)
JOB_TTL = 60 * 30   # 30 minutes
# Maximum concurrent background threads
MAX_WORKERS = 4


# ─────────────────────────────────────────────
# Internal state (module-level, shared)
# ─────────────────────────────────────────────

_jobs: dict[str, dict] = {}
_lock = threading.Lock()
_semaphore = threading.Semaphore(MAX_WORKERS)


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def submit(fn: Callable, *args, **kwargs) -> str:
    """Enqueue *fn(*args, **kwargs)* and return a job_id."""
    job_id = str(uuid.uuid4())
    job = {
        "id":         job_id,
        "status":     "pending",
        "created_at": time.time(),
        "updated_at": time.time(),
        "result":     None,          # bytes | None
        "content_type": None,
        "filename":   None,
        "headers":    {},
        "error":      None,
    }
    with _lock:
        _jobs[job_id] = job

    t = threading.Thread(target=_run, args=(job_id, fn, args, kwargs), daemon=True)
    t.start()
    return job_id


def get(job_id: str) -> dict | None:
    """Return a *safe* (no raw bytes) snapshot of the job, or None."""
    with _lock:
        job = _jobs.get(job_id)
    if not job:
        return None
    return _safe_snapshot(job)


def get_result(job_id: str) -> dict | None:
    """Return the full job including raw bytes result, or None."""
    with _lock:
        return _jobs.get(job_id)


def reap_expired() -> int:
    """Delete jobs older than JOB_TTL. Returns number reaped."""
    cutoff = time.time() - JOB_TTL
    expired = []
    with _lock:
        for jid, job in _jobs.items():
            if job["status"] in ("done", "failed") and job["updated_at"] < cutoff:
                expired.append(jid)
        for jid in expired:
            del _jobs[jid]
    return len(expired)


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

def _run(job_id: str, fn: Callable, args: tuple, kwargs: dict):
    _set(job_id, status="running")
    _semaphore.acquire()
    try:
        result = fn(*args, **kwargs)
        # fn must return a dict:
        # { "data": bytes, "content_type": str, "filename": str, "headers": dict }
        _set(job_id,
             status="done",
             result=result.get("data"),
             content_type=result.get("content_type"),
             filename=result.get("filename"),
             headers=result.get("headers", {}))
    except Exception:
        tb = traceback.format_exc()
        logger.error("Job %s failed:\n%s", job_id, tb)
        _set(job_id, status="failed", error=tb.splitlines()[-1])
    finally:
        _semaphore.release()
        # Kick off a light reap pass
        threading.Thread(target=reap_expired, daemon=True).start()


def _set(job_id: str, **kwargs):
    with _lock:
        job = _jobs.get(job_id)
        if job:
            job.update(kwargs)
            job["updated_at"] = time.time()


def _safe_snapshot(job: dict) -> dict:
    """Strip raw bytes before returning to API consumers."""
    return {
        "id":           job["id"],
        "status":       job["status"],
        "created_at":   job["created_at"],
        "updated_at":   job["updated_at"],
        "content_type": job["content_type"],
        "filename":     job["filename"],
        "headers":      job["headers"],
        "error":        job["error"],
    }
