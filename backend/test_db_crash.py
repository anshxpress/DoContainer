import sys
sys.path.append("d:/docscope")
import uuid
from backend.app.db.session import SessionLocal
from backend.app.models.models import Organization, Document, Folder, UsageMetric
from backend.app.services.metrics_service import get_aggregated_metrics
from backend.app.api.v1.analytics import DashboardAnalyticsResponse

def test():
    db = SessionLocal()
    try:
        org = db.query(Organization).first()
        if not org:
            print("No orgs found")
            return
        
        print(f"Testing with org: {org.id}")
        
        # Test documents/processing query
        docs = db.query(Document).filter(
            Document.org_id == org.id,
            Document.status.in_(["queued", "processing", "failed"])
        ).order_by(Document.created_at.desc()).all()
        print(f"Processing docs count: {len(docs)}")
        
        # Test folders query
        folders = db.query(Folder).filter(Folder.org_id == org.id).all()
        print(f"Folders count: {len(folders)}")
        
        # Test analytics
        metrics = get_aggregated_metrics(db, org.id)
        print("Metrics dict generated")
        
        resp = DashboardAnalyticsResponse(**metrics)
        print("Pydantic validation passed")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test()
