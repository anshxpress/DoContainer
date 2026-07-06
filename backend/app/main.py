from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings, features
from backend.app.api.v1 import auth
from backend.app.api.v1 import search as search_router_module
from backend.app.api.v1 import chat as chat_router_module

import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Remove all default handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)

setup_logging()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

from backend.app.core.telemetry import instrument_app
instrument_app(app)

# Enterprise Feature Disabled — Prometheus metrics endpoint
# Restore by uncommenting the two lines below when running in Enterprise mode.
# from prometheus_fastapi_instrumentator import Instrumentator
# Instrumentator().instrument(app).expose(app)



# CORS configuration
# In production, this should be restricted to specific domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.app.core.middleware import AuditLogMiddleware
# Enterprise Feature Disabled — AuditLogMiddleware (writes to audit_logs table).
# Restore by uncommenting the line below when running in Enterprise mode.
# app.add_middleware(AuditLogMiddleware)


# Mount routes
from backend.app.api.v1 import documents as documents_router_module
from backend.app.api.v1 import folders as folders_router_module
from backend.app.api.v1 import analytics as analytics_router_module
from backend.app.api.v1 import admin as admin_router_module
from backend.app.api.v1 import storage as storage_router_module

# Sprint 11 modules
from backend.app.api.v1 import approvals as approvals_router_module
from backend.app.api.v1 import locks as locks_router_module
from backend.app.api.v1 import acl as acl_router_module
from backend.app.api.v1 import retention as retention_router_module

app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["authentication"])

# ─── Personal Edition Core Routes ──────────────────────────────────────────────
if features.ENABLE_SEARCH:
    app.include_router(search_router_module.router, prefix=f"{settings.API_V1_STR}/search", tags=["search"])

if features.ENABLE_AI_CHAT:
    app.include_router(chat_router_module.router, prefix=f"{settings.API_V1_STR}/chat", tags=["chat"])

app.include_router(documents_router_module.router, prefix=f"{settings.API_V1_STR}/documents", tags=["documents"])

if features.ENABLE_FOLDERS:
    app.include_router(folders_router_module.router, prefix=f"{settings.API_V1_STR}/folders", tags=["folders"])

app.include_router(storage_router_module.router, prefix=f"{settings.API_V1_STR}/admin", tags=["storage"])

# ─── Enterprise Feature Disabled — Analytics & Admin Dashboard ─────────────────
# Restore by setting ENABLE_ANALYTICS=True (Enterprise mode) or uncommenting:
# app.include_router(analytics_router_module.router, prefix=f"{settings.API_V1_STR}/analytics", tags=["analytics"])
# app.include_router(admin_router_module.router, prefix=f"{settings.API_V1_STR}/admin", tags=["admin"])
if features.ENABLE_ANALYTICS:
    app.include_router(analytics_router_module.router, prefix=f"{settings.API_V1_STR}/analytics", tags=["analytics"])
    app.include_router(admin_router_module.router, prefix=f"{settings.API_V1_STR}/admin", tags=["admin"])

# ─── Enterprise Feature Disabled — Approval Workflow ───────────────────────────
# Restore by setting ENABLE_APPROVAL=True (Enterprise mode).
if features.ENABLE_APPROVAL:
    app.include_router(approvals_router_module.router, prefix=f"{settings.API_V1_STR}", tags=["approvals"])

# ─── Enterprise Feature Disabled — Document Locking ────────────────────────────
# Restore by setting ENABLE_VERSIONING=True (Team/Enterprise mode).
if features.ENABLE_VERSIONING:
    app.include_router(locks_router_module.router, prefix=f"{settings.API_V1_STR}", tags=["locks"])

# ─── Enterprise Feature Disabled — ACL & Retention Policies ────────────────────
# Restore by setting ENABLE_ACL=True (Enterprise mode).
if features.ENABLE_ACL:
    app.include_router(acl_router_module.router, prefix=f"{settings.API_V1_STR}", tags=["acl"])
    app.include_router(retention_router_module.router, prefix=f"{settings.API_V1_STR}/admin", tags=["retention"])

# Sprint 13 routes
from backend.app.api.v1 import comments as comments_router_module
from backend.app.api.v1 import tasks as tasks_router_module
from backend.app.api.v1 import notifications as notifications_router_module

# ─── Enterprise Feature Disabled — Comments (Team Collaboration) ────────────────
# Restore by setting ENABLE_TEAM=True (Team/Enterprise mode).
if features.ENABLE_TEAM:
    app.include_router(comments_router_module.router, prefix=f"{settings.API_V1_STR}", tags=["comments"])

# ─── Enterprise Feature Disabled — Tasks ────────────────────────────────────────
# Restore by setting ENABLE_TASKS=True (Team/Enterprise mode).
if features.ENABLE_TASKS:
    app.include_router(tasks_router_module.router, prefix=f"{settings.API_V1_STR}", tags=["tasks"])
    app.include_router(tasks_router_module.docs_router, prefix=f"{settings.API_V1_STR}", tags=["tasks"])

# ─── Enterprise Feature Disabled — Notifications ────────────────────────────────
# Restore by setting ENABLE_NOTIFICATIONS=True (Team/Enterprise mode).
if features.ENABLE_NOTIFICATIONS:
    app.include_router(notifications_router_module.router, prefix=f"{settings.API_V1_STR}", tags=["notifications"])



from backend.app.api.deps import get_current_user_context, CurrentUserContext
from fastapi import Depends, HTTPException, status

@app.get(f"{settings.API_V1_STR}/tenant-test/{{org_id}}")
def test_tenant_isolation(org_id: str, current_context: CurrentUserContext = Depends(get_current_user_context)):
    if current_context.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cross-tenant request rejected."
        )
    return {"message": "Access granted", "org_id": org_id}

@app.get("/")
def read_root():
    return {"message": "Welcome to DoContainer Personal AI Workspace — Lightweight Document Intelligence API"}

@app.get("/health", tags=["system"])
def health_check():
    """
    GET /health
    Basic health check endpoint for load balancers and orchestrators.
    """
    return {"status": "ok", "service": "DoContainer-api"}


from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger = logging.getLogger("DoContainer")
    logger.exception(f"Unhandled error on {request.method} {request.url}", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"}
    )
