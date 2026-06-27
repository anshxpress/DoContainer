import io
import uuid
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from backend.app.api.deps import get_current_user_context, PermissionChecker
from backend.app.models.models import AuditLog, Document, Organization

@pytest.fixture(autouse=True)
def override_auth_and_permissions():
    """Override user context and permission checkers to return a stub user context."""
    from backend.app.main import app
    from backend.app.api.deps import get_current_user_context, PermissionChecker
    
    mock_ctx = MagicMock()
    mock_ctx.user = MagicMock()
    mock_ctx.user.id = uuid.uuid4()
    mock_ctx.org_id = str(uuid.uuid4())
    mock_ctx.role_name = "Organization Admin"
    mock_ctx.permissions = ["documents:write", "documents:read"]
    
    app.dependency_overrides[get_current_user_context] = lambda: mock_ctx
    
    # Override permission check instances
    checker_write = PermissionChecker("documents:write")
    checker_read = PermissionChecker("documents:read")
    app.dependency_overrides[checker_write] = lambda: mock_ctx
    app.dependency_overrides[checker_read] = lambda: mock_ctx
    
    yield mock_ctx
    
    app.dependency_overrides.pop(get_current_user_context, None)
    app.dependency_overrides.pop(checker_write, None)
    app.dependency_overrides.pop(checker_read, None)


@patch("backend.app.api.v1.documents.s3_storage")
@patch("backend.app.api.v1.documents.chain")
def test_upload_document_success(mock_chain, mock_s3, client, db, override_auth_and_permissions):
    # Setup mocks
    mock_s3.upload_fileobj.return_value = True
    mock_s3.bucket_name = "test-bucket"
    mock_chain_instance = MagicMock()
    mock_chain.return_value = mock_chain_instance
    
    # Pre-insert matching organization to avoid FK violations
    org_id = uuid.UUID(override_auth_and_permissions.org_id)
    db.add(Organization(id=org_id, name="Test Org"))
    db.commit()

    file_content = b"%PDF-1.4\n%pdf-header-content\n%%EOF"
    file_name = "test.pdf"
    
    # Mock magic number checks by patching filetype
    with patch("backend.app.services.validation.filetype") as mock_ft:
        mock_kind = MagicMock()
        mock_kind.mime = "application/pdf"
        mock_kind.extension = "pdf"
        mock_ft.guess.return_value = mock_kind

        response = client.post(
            "/api/v1/documents/upload",
            files={"file": (file_name, io.BytesIO(file_content), "application/pdf")},
            data={"folder_id": str(uuid.uuid4())}
        )
    
    assert response.status_code == 201
    resp_data = response.json()
    assert resp_data["name"] == file_name
    assert resp_data["status"] == "queued"
    assert resp_data["file_type"] == "pdf"
    
    # Assert database has the document
    doc = db.query(Document).filter(Document.id == uuid.UUID(resp_data["id"])).first()
    assert doc is not None
    assert doc.name == file_name
    
    # Assert Celery ingestion pipeline was triggered
    mock_chain.assert_called_once()
    mock_chain_instance.apply_async.assert_called_once()


def test_list_documents(client, db, override_auth_and_permissions):
    org_id = uuid.UUID(override_auth_and_permissions.org_id)
    db.add(Organization(id=org_id, name="Test Org"))
    
    # Add dummy document
    doc = Document(
        id=uuid.uuid4(),
        org_id=org_id,
        name="doc1.pdf",
        storage_path="path/doc1.pdf",
        status="completed",
        file_type="pdf",
        file_size=1024
    )
    db.add(doc)
    db.commit()

    response = client.get("/api/v1/documents")
    assert response.status_code == 200
    resp_data = response.json()
    assert len(resp_data) == 1
    assert resp_data[0]["name"] == "doc1.pdf"

    # Test GET single document
    response_single = client.get(f"/api/v1/documents/{doc.id}")
    assert response_single.status_code == 200
    assert response_single.json()["name"] == "doc1.pdf"



@patch("backend.app.core.middleware.log_audit_event_task")
def test_audit_log_middleware_trigger(mock_log_task, client, db, override_auth_and_permissions):
    org_id = uuid.UUID(override_auth_and_permissions.org_id)
    db.add(Organization(id=org_id, name="Test Org"))
    
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        org_id=org_id,
        name="doc_to_delete.pdf",
        storage_path="path/doc_to_delete.pdf",
        status="completed",
        file_type="pdf",
        file_size=1024
    )
    db.add(doc)
    db.commit()

    with patch("backend.app.api.v1.documents.s3_storage") as mock_s3, \
         patch("backend.app.core.qdrant.qdrant_client") as mock_qd:
        response = client.delete(f"/api/v1/documents/{doc_id}")
        assert response.status_code == 204

    # Verify that the middleware intercepted the request and triggered the Celery task
    mock_log_task.delay.assert_called_once()
    kwargs = mock_log_task.delay.call_args.kwargs
    assert kwargs["action"] == "document.delete"
    assert str(doc_id) in kwargs["resource"]

