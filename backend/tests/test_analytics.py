import uuid
import pytest
from unittest.mock import patch, MagicMock
from backend.app.api.deps import get_current_user_context, PermissionChecker
from backend.app.models.models import Organization, Document, UsageMetric, AuditLog

@pytest.fixture(autouse=True)
def override_auth_and_permissions():
    from backend.app.main import app
    from backend.app.api.deps import get_current_user_context, PermissionChecker
    
    mock_ctx = MagicMock()
    mock_ctx.user = MagicMock()
    mock_ctx.user.id = uuid.uuid4()
    mock_ctx.org_id = str(uuid.uuid4())
    mock_ctx.role_name = "Organization Admin"
    mock_ctx.permissions = ["analytics:read"]
    
    app.dependency_overrides[get_current_user_context] = lambda: mock_ctx
    
    checker_read = PermissionChecker("analytics:read")
    app.dependency_overrides[checker_read] = lambda: mock_ctx
    
    yield mock_ctx
    
    app.dependency_overrides.pop(get_current_user_context, None)
    app.dependency_overrides.pop(checker_read, None)


def test_get_dashboard_analytics_success(client, db, override_auth_and_permissions):
    org_id = uuid.UUID(override_auth_and_permissions.org_id)
    
    # Setup data in DB
    db.add(Organization(id=org_id, name="Test Org"))
    db.commit()

    # Log some dummy documents
    db.add(Document(
        id=uuid.uuid4(),
        org_id=org_id,
        name="doc.pdf",
        storage_path="path/doc.pdf",
        status="completed",
        file_type="pdf",
        file_size=1048576
    ))

    # Log some usage metrics
    db.add(UsageMetric(
        id=uuid.uuid4(),
        org_id=org_id,
        metric_type="pages_rendered",
        value=5.0
    ))
    db.add(UsageMetric(
        id=uuid.uuid4(),
        org_id=org_id,
        metric_type="storage_bytes",
        value=1048576.0
    ))
    db.add(UsageMetric(
        id=uuid.uuid4(),
        org_id=org_id,
        metric_type="api_tokens",
        value=1200.0
    ))
    
    # Log an audit entry
    db.add(AuditLog(
        id=uuid.uuid4(),
        org_id=org_id,
        user_id=override_auth_and_permissions.user.id,
        action="document.search",
        resource="/api/v1/search"
    ))
    db.commit()

    response = client.get("/api/v1/analytics/dashboard")
    assert response.status_code == 200
    
    resp_data = response.json()
    assert "totals" in resp_data
    assert resp_data["totals"]["documents"] == 1
    assert resp_data["totals"]["pages_rendered"] == 5
    assert resp_data["totals"]["storage_bytes"] == 1048576
    assert resp_data["totals"]["api_tokens"] == 1200
    assert resp_data["totals"]["active_users"] == 1
    
    assert len(resp_data["recent_audits"]) == 1
    assert resp_data["recent_audits"][0]["action"] == "document.search"
    
    assert len(resp_data["daily_trends"]) == 7
    # Verify file type breakdown
    assert len(resp_data["file_type_breakdown"]) == 1
    assert resp_data["file_type_breakdown"][0]["name"] == "PDF"
    assert resp_data["file_type_breakdown"][0]["value"] == 1


def test_metrics_endpoint(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "process_cpu_seconds_total" in response.text or "http_requests_total" in response.text

