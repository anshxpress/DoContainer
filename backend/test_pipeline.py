import sys
import time
import requests
import traceback
sys.path.append("d:/docscope")
from backend.app.core.db import SessionLocal
from backend.app.models.models import User, Document, ProcessingJob
from backend.app.core.security import create_access_token

def run():
    db = SessionLocal()
    user = db.query(User).first()
    if not user:
        print("No user found")
        return
    token = create_access_token(user.id)
    db.close()

    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Create a dummy txt file
    with open("dummy.txt", "w") as f:
        f.write("This is a dummy test file to verify the pipeline. It has some words in English.")

    # 2. Upload file
    print("Uploading file...")
    url = "http://localhost:8001/api/v1/documents/upload"
    try:
        with open("dummy.txt", "rb") as f:
            files = {"file": ("dummy.txt", f, "text/plain")}
            data = {"folder_id": "root"}
            resp = requests.post(url, headers=headers, files=files, data=data)
            
        print("Upload Status:", resp.status_code)
        if resp.status_code != 200 and resp.status_code != 201:
            print("Response:", resp.text)
            return
            
        doc_data = resp.json()
        doc_id = doc_data.get("id")
        print("Document created with ID:", doc_id)
        
        # 3. Monitor jobs
        print("Monitoring pipeline stages...")
        db = SessionLocal()
        
        start_time = time.time()
        completed_stages = set()
        failed_stages = set()
        
        while time.time() - start_time < 60:
            db.expire_all()
            jobs = db.query(ProcessingJob).filter_by(document_id=doc_id).all()
            
            for job in jobs:
                if job.status == "completed" and job.job_type not in completed_stages:
                    print(f"[PASS] Stage: {job.job_type}")
                    completed_stages.add(job.job_type)
                elif job.status == "failed" and job.job_type not in failed_stages:
                    print(f"[FAIL] Stage: {job.job_type} - Error: {job.error_message}")
                    failed_stages.add(job.job_type)
            
            doc = db.query(Document).filter_by(id=doc_id).first()
            if doc and doc.status == "completed":
                print("Document processing finished completely.")
                break
            elif doc and doc.status == "failed":
                print("Document processing failed.")
                break
                
            time.sleep(2)
            
    except Exception as e:
        traceback.print_exc()
        
if __name__ == "__main__":
    run()
