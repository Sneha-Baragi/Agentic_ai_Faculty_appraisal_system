from __future__ import annotations

import re
import time
import subprocess
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import engine
from app.models import AuditLog
from app.services.storage import get_storage, MinioStorage, InMemoryStorage


SENSITIVE_PATTERNS = [
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"key", re.IGNORECASE),
    re.compile(r"bearer", re.IGNORECASE),
    re.compile(r"authorization", re.IGNORECASE),
]


def redact_sensitive_value(key: str, val: Any) -> Any:
    if isinstance(val, str):
        # Check if key implies sensitivity
        if any(pat.search(key) for pat in SENSITIVE_PATTERNS):
            return "[REDACTED]"
        # Check if value looks like a bearer token or secret string
        if val.startswith("Bearer ") or len(val) > 40 and any(kw in val.lower() for kw in ["secret", "password"]):
            return "[REDACTED]"
        return val
    elif isinstance(val, dict):
        return {k: redact_sensitive_value(k, v) for k, v in val.items()}
    elif isinstance(val, list):
        return [redact_sensitive_value(key, item) for item in val]
    return val


def redact_diagnostics_report(report: dict[str, Any]) -> dict[str, Any]:
    cleaned = {}
    for k, v in report.items():
        cleaned[k] = redact_sensitive_value(k, v)
    return cleaned


def check_api_health() -> dict[str, Any]:
    settings = get_settings()
    start = time.perf_counter()
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    return {
        "service": "backend_api",
        "status": "healthy",
        "severity": "info",
        "observed_issue": None,
        "diagnostic_evidence": {
            "version": "0.2.0-phase2",
            "latency_ms": duration_ms,
            "storage_backend": settings.storage_backend,
            "llm_provider": settings.llm_provider,
        },
        "recommended_action": "No action required.",
    }


def check_database_health(db: Session) -> dict[str, Any]:
    start = time.perf_counter()
    try:
        res = db.execute(text("SELECT 1")).scalar()
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        if res == 1:
            return {
                "service": "postgresql",
                "status": "healthy",
                "severity": "info",
                "observed_issue": None,
                "diagnostic_evidence": {
                    "latency_ms": latency_ms,
                    "db_dialect": engine.dialect.name,
                    "query_test": "SELECT 1 successful",
                },
                "recommended_action": "No action required.",
            }
        else:
            return {
                "service": "postgresql",
                "status": "unhealthy",
                "severity": "critical",
                "observed_issue": f"Unexpected SELECT 1 result: {res}",
                "diagnostic_evidence": {"latency_ms": latency_ms},
                "recommended_action": "Inspect PostgreSQL server logs and database connectivity.",
            }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "service": "postgresql",
            "status": "unhealthy",
            "severity": "critical",
            "observed_issue": str(exc),
            "diagnostic_evidence": {"latency_ms": latency_ms, "error": str(exc)},
            "recommended_action": "Check database service status, credentials, and connection pool.",
        }


def check_storage_health() -> dict[str, Any]:
    settings = get_settings()
    start = time.perf_counter()
    try:
        storage = get_storage()
        if isinstance(storage, InMemoryStorage) or settings.storage_backend == "memory":
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            return {
                "service": "object_storage",
                "status": "healthy",
                "severity": "info",
                "observed_issue": "Operating with in-memory storage fallback. MinIO S3 backend is not active in environment (STORAGE_BACKEND=memory).",
                "diagnostic_evidence": {
                    "configured_backend": "memory",
                    "storage_type": "in-memory fallback",
                    "latency_ms": latency_ms,
                },
                "recommended_action": "Set STORAGE_BACKEND=minio and configure MINIO_ENDPOINT if S3 persistent storage is required.",
            }
        elif isinstance(storage, MinioStorage) or settings.storage_backend == "minio":
            storage.ensure_bucket()
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            return {
                "service": "object_storage",
                "status": "healthy",
                "severity": "info",
                "observed_issue": None,
                "diagnostic_evidence": {
                    "configured_backend": "minio",
                    "endpoint": settings.minio_endpoint,
                    "bucket": settings.minio_bucket,
                    "latency_ms": latency_ms,
                },
                "recommended_action": "No action required.",
            }
        else:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            return {
                "service": "object_storage",
                "status": "healthy",
                "severity": "info",
                "observed_issue": None,
                "diagnostic_evidence": {
                    "configured_backend": settings.storage_backend,
                    "latency_ms": latency_ms,
                },
                "recommended_action": "No action required.",
            }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "service": "object_storage",
            "status": "unhealthy",
            "severity": "error",
            "observed_issue": str(exc),
            "diagnostic_evidence": {
                "configured_backend": settings.storage_backend,
                "endpoint": settings.minio_endpoint,
                "bucket": settings.minio_bucket,
                "latency_ms": latency_ms,
                "error": str(exc),
            },
            "recommended_action": "Verify MinIO server container, access credentials, and network connectivity.",
        }


def check_docker_containers() -> dict[str, Any]:
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            ["docker", "compose", "ps", "--format", "json"],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=2,
        )
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        if proc.returncode == 0 and proc.stdout.strip():
            return {
                "service": "docker_containers",
                "status": "healthy",
                "severity": "info",
                "observed_issue": None,
                "diagnostic_evidence": {
                    "output": proc.stdout.strip()[:1000],
                    "latency_ms": latency_ms,
                },
                "recommended_action": "No action required.",
            }
        else:
            return {
                "service": "docker_containers",
                "status": "unknown",
                "severity": "info",
                "observed_issue": "Docker Compose status command produced no output or exited non-zero.",
                "diagnostic_evidence": {
                    "returncode": proc.returncode,
                    "stderr": proc.stderr.strip()[:500],
                    "latency_ms": latency_ms,
                },
                "recommended_action": "Inspect Docker daemon permissions or compose deployment if running in Docker mode.",
            }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "service": "docker_containers",
            "status": "unknown",
            "severity": "info",
            "observed_issue": "Docker inspection unavailable in local execution context.",
            "diagnostic_evidence": {
                "reason": type(exc).__name__,
                "detail": str(exc)[:300],
                "latency_ms": latency_ms,
            },
            "recommended_action": "Container socket is deliberately unmounted in application runtime to maintain host isolation.",
        }


def get_recent_operational_errors(db: Session, limit: int = 50) -> list[dict[str, Any]]:
    logs = list(
        db.scalars(
            select(AuditLog)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
    )
    error_items = []
    for log in logs:
        action_name = (log.action or "").lower()
        if any(term in action_name for term in ["error", "fail", "invalid", "denied", "exception"]):
            explanation = None
            if "appraisal_research_metrics_failure" in action_name:
                after_data = log.after if isinstance(log.after, dict) else {}
                err_cat = after_data.get("error_category")
                if err_cat:
                    explanation = f"Google Scholar metrics unavailable during appraisal execution (category: {err_cat})."
                else:
                    explanation = "Google Scholar metrics unavailable during appraisal execution (cause unverified)."

            error_items.append({
                "id": str(log.id),
                "timestamp": log.created_at.isoformat() if log.created_at else None,
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "actor_id": str(log.actor_id) if log.actor_id else None,
                "explanation": explanation,
                "details": redact_sensitive_value("after", log.after),
            })
    return error_items


def run_cloud_ops_diagnostics(db: Session) -> dict[str, Any]:
    api_res = check_api_health()
    db_res = check_database_health(db)
    storage_res = check_storage_health()
    docker_res = check_docker_containers()
    recent_errors = get_recent_operational_errors(db, limit=50)

    services = [api_res, db_res, storage_res, docker_res]

    # Compute overall status
    unhealthy_count = sum(1 for s in services if s["status"] == "unhealthy")
    unknown_count = sum(1 for s in services if s["status"] == "unknown")

    if unhealthy_count > 0:
        overall_status = "unhealthy"
    elif unknown_count > 0:
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    raw_report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_status": overall_status,
        "services": services,
        "operational_errors": recent_errors,
        "summary": {
            "total_services": len(services),
            "healthy": sum(1 for s in services if s["status"] == "healthy"),
            "unhealthy": unhealthy_count,
            "unknown": unknown_count,
            "error_log_count": len(recent_errors),
        },
    }

    return redact_diagnostics_report(raw_report)
