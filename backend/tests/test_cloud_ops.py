import pytest
from unittest.mock import patch, MagicMock

from sqlalchemy.orm import Session

from app.models import AuditLog
from app.services.cloud_ops import (
    run_cloud_ops_diagnostics,
    check_database_health,
    check_storage_health,
    check_docker_containers,
    get_recent_operational_errors,
    redact_diagnostics_report,
)
from .conftest import auth_headers, login, make_user


def test_cloud_ops_diagnostics_healthy(client, db_session: Session):
    admin_user = make_user(db_session, "cloudadmin@demo.local", ["admin"])
    token = login(client, "cloudadmin@demo.local")

    res = client.get("/api/v1/admin/cloud-ops/diagnostics", headers=auth_headers(token))
    assert res.status_code == 200, res.text
    data = res.json()

    assert "overall_status" in data
    assert data["overall_status"] in ["healthy", "degraded", "unhealthy"]
    assert "services" in data
    assert len(data["services"]) >= 4

    service_names = [s["service"] for s in data["services"]]
    assert "backend_api" in service_names
    assert "postgresql" in service_names
    assert "object_storage" in service_names
    assert "docker_containers" in service_names


def test_cloud_ops_storage_memory_vs_minio():
    # Test memory mode
    with patch("app.services.cloud_ops.get_settings") as mock_settings, \
         patch("app.services.cloud_ops.get_storage") as mock_storage:
        from app.services.storage import InMemoryStorage
        mock_settings.return_value.storage_backend = "memory"
        mock_storage.return_value = InMemoryStorage()

        health = check_storage_health()
        assert health["service"] == "object_storage"
        assert health["status"] == "healthy"
        assert health["diagnostic_evidence"]["configured_backend"] == "memory"
        assert "fallback" in health["observed_issue"].lower()

    # Test minio healthy mode
    with patch("app.services.cloud_ops.get_settings") as mock_settings, \
         patch("app.services.cloud_ops.get_storage") as mock_storage:
        from app.services.storage import MinioStorage
        mock_settings.return_value.storage_backend = "minio"
        mock_settings.return_value.minio_endpoint = "localhost:9000"
        mock_settings.return_value.minio_bucket = "faculty-evidence"

        mock_minio = MagicMock(spec=MinioStorage)
        mock_minio.ensure_bucket.return_value = None
        mock_storage.return_value = mock_minio

        health = check_storage_health()
        assert health["service"] == "object_storage"
        assert health["status"] == "healthy"
        assert health["diagnostic_evidence"]["configured_backend"] == "minio"
        assert health["observed_issue"] is None


def test_cloud_ops_unhealthy_db(db_session: Session):
    mock_db = MagicMock(spec=Session)
    mock_db.execute.side_effect = Exception("DB Connection Refused")

    health = check_database_health(mock_db)
    assert health["status"] == "unhealthy"
    assert health["severity"] == "critical"
    assert "DB Connection Refused" in health["observed_issue"]


def test_cloud_ops_docker_unknown():
    health = check_docker_containers()
    assert health["service"] == "docker_containers"
    assert health["status"] in ["healthy", "unknown"]
    assert health["severity"] == "info"


def test_cloud_ops_rbac(client, db_session: Session):
    user = make_user(db_session, "faculty_cloud@demo.local", ["faculty"])
    token = login(client, "faculty_cloud@demo.local")

    res = client.get("/api/v1/admin/cloud-ops/diagnostics", headers=auth_headers(token))
    assert res.status_code == 403


def test_cloud_ops_sensitive_data_redaction():
    sample_report = {
        "api_key": "secret_1234567890",
        "user_password": "super_secret_password",
        "jwt_secret": "my_jwt_token_secret",
        "auth_header": "Bearer secret_bearer_token",
        "safe_value": "healthy",
        "nested": {
            "db_password": "postgres_pass",
            "normal_field": 123,
        },
    }

    redacted = redact_diagnostics_report(sample_report)
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["user_password"] == "[REDACTED]"
    assert redacted["jwt_secret"] == "[REDACTED]"
    assert redacted["auth_header"] == "[REDACTED]"
    assert redacted["safe_value"] == "healthy"
    assert redacted["nested"]["db_password"] == "[REDACTED]"
    assert redacted["nested"]["normal_field"] == 123


def test_cloud_ops_audit_log_created(client, db_session: Session):
    admin_user = make_user(db_session, "auditadmin@demo.local", ["admin"])
    token = login(client, "auditadmin@demo.local")

    res = client.get("/api/v1/admin/cloud-ops/diagnostics", headers=auth_headers(token))
    assert res.status_code == 200

    log = db_session.query(AuditLog).filter(AuditLog.action == "cloud_operations_diagnostics").first()
    assert log is not None
    assert log.actor_id == admin_user.id
    assert log.entity_type == "system"
    assert log.entity_id == "cloud_ops"
    assert "overall_status" in log.after


def test_cloud_ops_research_metrics_failure_explanation(db_session: Session):
    db_session.add(
        AuditLog(
            action="appraisal_research_metrics_failure",
            entity_type="faculty_profile",
            entity_id="test_fac_1",
            after={"error_category": "unconfigured_scholar_id"},
        )
    )
    db_session.commit()

    errors = get_recent_operational_errors(db_session, limit=10)
    assert len(errors) > 0
    failure_event = next(e for e in errors if e["action"] == "appraisal_research_metrics_failure")
    assert "unconfigured_scholar_id" in failure_event["explanation"]


def test_minio_storage_persistence_integration():
    from app.services.storage import InMemoryStorage, MinioStorage
    # Verify InMemoryStorage operates as fallback
    mem = InMemoryStorage()
    mem.put("test_key.txt", b"evidence_content", "text/plain")
    assert mem.exists("test_key.txt")
    assert mem.get("test_key.txt") == b"evidence_content"

    # Verify MinioStorage class interface compliance
    with patch("app.services.storage.Minio") as mock_minio_cls, \
         patch("app.services.storage.get_settings") as mock_settings:
        mock_settings.return_value.minio_access_key = "minioadmin"
        mock_settings.return_value.minio_secret_key = "minioadmin"
        mock_settings.return_value.minio_endpoint = "localhost:9000"
        mock_settings.return_value.minio_bucket = "faculty-evidence"
        mock_settings.return_value.minio_secure = False

        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = False
        mock_minio_cls.return_value = mock_client

        storage = MinioStorage()
        storage.ensure_bucket()

        mock_client.bucket_exists.assert_called_with("faculty-evidence")
        mock_client.make_bucket.assert_called_with("faculty-evidence")

        storage.put("evidence_123.pdf", b"pdf_data", "application/pdf")
        assert mock_client.put_object.called
