import sys
sys.path.append("d:/docscope")
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.db import SessionLocal
from backend.app.models.models import User
from backend.app.core.security import create_access_token
import traceback

def test():
    db = SessionLocal()
    # Get the admin user
    user = db.query(User).filter(User.email == "admin@docscope.io").first()
    if not user:
        user = db.query(User).first()
        
    print(f"Testing with user: {user.email}")
    token = create_access_token(user.id)
    db.close()
    
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    
    print("Fetching /documents/processing...")
    try:
        r = client.get("/api/v1/documents/processing", headers=headers)
        print("Status:", r.status_code)
    except Exception as e:
        print("Crash on processing:")
        traceback.print_exc()

    print("Fetching /folders...")
    try:
        r = client.get("/api/v1/folders", headers=headers)
        print("Status:", r.status_code)
    except Exception as e:
        print("Crash on folders:")
        traceback.print_exc()

    print("Fetching /analytics/dashboard...")
    try:
        r = client.get("/api/v1/analytics/dashboard", headers=headers)
        print("Status:", r.status_code)
    except Exception as e:
        print("Crash on analytics:")
        traceback.print_exc()

if __name__ == "__main__":
    test()
