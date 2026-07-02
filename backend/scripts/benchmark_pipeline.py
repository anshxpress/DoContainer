import argparse
import sys
import os
import uuid
import time
from sqlalchemy.orm import Session

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.core.db import SessionLocal
from backend.app.models.models import Document, Organization, ProcessingMetrics
from backend.app.tasks.ocr_tasks import ocr_task, bge_embed_task

def run_benchmark(file_path: str, org_name: str = "BenchmarkOrg"):
    db = SessionLocal()
    
    # 1. Setup mock org
    org = db.query(Organization).filter(Organization.name == org_name).first()
    if not org:
        org = Organization(name=org_name)
        db.add(org)
        db.commit()
        db.refresh(org)

    # 2. Setup mock document (Note: In a real benchmark, you would upload the file to S3 
    # and create DocumentPage entries first. For this script, we assume the pipeline 
    # has already parsed the PDF into pages in S3, or we just run the tasks on an existing document).
    # Since we can't easily mock S3 and PDF parsing in a standalone script without the full pipeline,
    # we will query an existing document ID if provided, or instruct the user.
    
    try:
        doc_uuid = uuid.UUID(file_path)
        doc = db.query(Document).filter(Document.id == doc_uuid).first()
        if not doc:
            print(f"Document {doc_uuid} not found in DB.")
            return
            
        print(f"--- Starting Benchmark for Document {doc_uuid} ---")
        
        # We run the Celery tasks synchronously
        print("Running OCR Task...")
        ocr_res = ocr_task(str(doc_uuid))
        print("OCR Task Result:", ocr_res)
        
        print("Running Embedding Task...")
        embed_res = bge_embed_task(str(doc_uuid))
        print("Embedding Task Result:", embed_res)
        
        # 3. Print Metrics
        print("\n--- Benchmark Results ---")
        metrics = db.query(ProcessingMetrics).filter(ProcessingMetrics.document_id == doc_uuid).order_by(ProcessingMetrics.started_at).all()
        
        if not metrics:
            print("No metrics recorded.")
        else:
            print(f"{'Stage':<15} | {'Duration (ms)':<15} | {'CPU %':<10} | {'GPU Mem (MB)':<15} | {'Status'}")
            print("-" * 75)
            for m in metrics:
                print(f"{m.stage:<15} | {m.duration_ms or 0:<15} | {m.cpu_percent or 0:<10} | {m.gpu_memory_mb or 0:<15} | {m.status}")

    except ValueError:
        print("Please provide a valid Document UUID that has already been parsed into pages.")
        print("Usage: python benchmark_pipeline.py <document_uuid>")
        
    db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark Document Processing Pipeline")
    parser.add_argument("document_id", help="UUID of the document to benchmark")
    args = parser.parse_args()
    
    run_benchmark(args.document_id)
