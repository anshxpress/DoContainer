import sys
import time
import requests
import traceback
import uuid
import os

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.app.core.db import SessionLocal
from backend.app.models.models import User, Document, ProcessingJob
from backend.app.core.security import create_access_token

EXPECTED_STAGES = [
    "scan_malware",
    "convert_to_pdf",
    "render_pages",
    "embed_and_index",
    "docling_parse",
    "ocr",
    "bge_embed",
    "metadata_enrichment"
]

def run_validation(api_url="http://localhost:8001"):
    print("==================================================")
    print("      DOCSCOPE PIPELINE RUNTIME VALIDATION        ")
    print("==================================================")
    
    db = SessionLocal()
    try:
        # Get or create a test user
        user = db.query(User).first()
        if not user:
            print("[INFO] No user found in database. Please seed the database first.")
            return False
            
        token = create_access_token(user.id)
        headers = {"Authorization": f"Bearer {token}"}
        
        # 1. Create a minimal valid PDF file for testing OCR and parsing
        import base64
        test_filename = f"test_validation_{uuid.uuid4().hex[:8]}.pdf"
        
        # A minimal 1-page valid PDF (blank page)
        MINIMAL_PDF_B64 = (
            "JVBERi0xLjQKJcOkw7zDtsOfCjIgMCBvYmoKPDwvTGVuZ3RoIDMgMCBSL0ZpbHRlci9GbGF0ZURl"
            "Y29kZT4+CnN0cmVhbQp4nDPQM1Qo5ypUMFAwALJMLY31jBQMzYxMtAxNtAwNNQwMDIwtdM0MLc3N"
            "tIwMdM1NM3QVDM2MDHUMDHUtDHUtDA0MjM0tzM1NUzQVDHQVDJQMDXUMDYAoTygxVzBTMDAAAAcK"
            "CgkKZW5kc3RyZWFtCmVuZG9iagoKMyAwIG9iago1OQplbmRvYmoKCjUgMCBvYmoKPDwKL1R5cGUg"
            "L1BhZ2UKL01lZGlhQm94IFswIDAgNTk1LjI4IDg0MS44OV0KL1Jlc291cmNlcyA8PAovUHJvY0Nl"
            "dCBbL1BERiAvVGV4dCAvSW1hZ2VCIC9JbWFnZUMgL0ltYWdlSV0KPj4KL0NvbnRlbnRzIDIgMCBS"
            "Ci9QYXJlbnQgNCAwIFIKPj4KZW5kb2JqCgo0IDAgb2JqCjw8Ci9UeXBlIC9QYWdlcwovS2lkcyBb"
            "NSAwIFJdCi9Db3VudCAxCj4+CmVuZG9iagoKMSAwIG9iago8PAovVHlwZSAvQ2F0YWxvZwovUGFn"
            "ZXMgNCAwIFIKPj4KZW5kb2JqCgp4cmVmCjAgNgowMDAwMDAwMDAwIDY1NTM1IGYgCjAwMDAwMDAy"
            "OTkgMDAwMDAgbiAKMDAwMDAwMDE1IDAwMDAwIG4gCjAwMDAwMDAxNDYgMDAwMDAgbiAKMDAwMDAw"
            "MDI0MCAwMDAwMCBuIAowMDAwMDAwMTY1IDAwMDAwIG4gCnRyYWlsZXIKPDwKL1NpemUgNgovUm9v"
            "dCAxIDAgUgo+PgpzdGFydHhyZWYKMzQ5CiUlRU9GCg=="
        )
        
        with open(test_filename, "wb") as f:
            f.write(base64.b64decode(MINIMAL_PDF_B64))
            
        # 2. Upload file
        print(f"\n[1/3] Uploading test document ({test_filename}) to API...")
        url = f"{api_url}/api/v1/documents/upload"
        
        with open(test_filename, "rb") as f:
            files = {"file": (test_filename, f, "application/pdf")}
            data = {}
            try:
                resp = requests.post(url, headers=headers, files=files, data=data)
            except requests.exceptions.ConnectionError:
                print(f"[ERROR] Could not connect to API at {api_url}")
                print("[ERROR] Ensure the backend server is running.")
                return False
            
        if resp.status_code not in (200, 201):
            print(f"[ERROR] Upload failed! Status: {resp.status_code}")
            print(f"[ERROR] Response: {resp.text}")
            return False
            
        doc_data = resp.json()
        doc_id = doc_data.get("id")
        print(f"[SUCCESS] Document uploaded successfully. Document ID: {doc_id}")
        
        # 3. Monitor jobs
        print("\n[2/3] Monitoring pipeline execution stages...")
        print("Waiting for jobs to be queued and processed (Timeout: 120s)\n")
        
        start_time = time.time()
        completed_stages = set()
        failed_stages = {}
        
        doc_status = "processing"
        
        while time.time() - start_time < 120:
            db.expire_all()
            jobs = db.query(ProcessingJob).filter_by(document_id=doc_id).all()
            
            for job in jobs:
                if job.status == "completed" and job.job_type not in completed_stages:
                    print(f"  [PASS] Stage '{job.job_type}' completed successfully.")
                    completed_stages.add(job.job_type)
                elif job.status == "failed" and job.job_type not in failed_stages:
                    print(f"  [FAIL] Stage '{job.job_type}' failed!")
                    print(f"     └─ Error Message: {job.error_message}")
                    failed_stages[job.job_type] = job.error_message
            
            doc = db.query(Document).filter_by(id=doc_id).first()
            if doc:
                if doc.status == "completed":
                    doc_status = "completed"
                    break
                elif doc.status == "failed":
                    doc_status = "failed"
                    break
                    
            time.sleep(3)
            
        print("\n[3/3] Generating Validation Report...")
        print("==================================================")
        
        all_passed = True
        missing_stages = [s for s in EXPECTED_STAGES if s not in completed_stages and s not in failed_stages]
        
        if doc_status == "completed":
            print(f"[STATUS] COMPLETED (Total time: {time.time() - start_time:.1f}s)")
        elif doc_status == "failed":
            print(f"[STATUS] FAILED (Total time: {time.time() - start_time:.1f}s)")
            all_passed = False
        else:
            print(f"[STATUS] TIMEOUT (Total time: {time.time() - start_time:.1f}s)")
            all_passed = False
            
        print("\n--- Stage Breakdown ---")
        for stage in EXPECTED_STAGES:
            if stage in completed_stages:
                print(f"  [{stage}]: PASS")
            elif stage in failed_stages:
                print(f"  [{stage}]: FAIL - {failed_stages[stage]}")
                all_passed = False
            elif stage in missing_stages:
                # Some stages might be skipped depending on the pipeline routing
                print(f"  [{stage}]: PENDING / SKIPPED")
                
        if failed_stages:
            print("\n[CRITICAL FAILURES DETECTED]")
            for stage, err in failed_stages.items():
                print(f" - Stage '{stage}' failed due to: {err}")
                print(f"   Suggestion: Check the celery worker logs for the '{stage}' task to debug further.")
                
        if missing_stages and doc_status == "completed":
            print("\n[NOTE] Some expected stages did not run. This may be normal if the pipeline skipped them for a .txt file (e.g., OCR might skip if no images are present).")
            
        print("==================================================")
        
        # Cleanup
        try:
            if os.path.exists(test_filename):
                os.remove(test_filename)
        except Exception:
            pass
            
        return all_passed

    except Exception as e:
        print(f"\n[FATAL ERROR] Validation script crashed: {e}")
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = run_validation()
    sys.exit(0 if success else 1)
