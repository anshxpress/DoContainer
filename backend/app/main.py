from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings
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

from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)



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
app.add_middleware(AuditLogMiddleware)


# Mount routes
from backend.app.api.v1 import documents as documents_router_module
from backend.app.api.v1 import folders as folders_router_module
from backend.app.api.v1 import analytics as analytics_router_module
from backend.app.api.v1 import admin as admin_router_module

app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["authentication"])
app.include_router(search_router_module.router, prefix=f"{settings.API_V1_STR}/search", tags=["search"])
app.include_router(chat_router_module.router, prefix=f"{settings.API_V1_STR}/chat", tags=["chat"])
app.include_router(documents_router_module.router, prefix=f"{settings.API_V1_STR}/documents", tags=["documents"])
app.include_router(folders_router_module.router, prefix=f"{settings.API_V1_STR}/folders", tags=["folders"])
app.include_router(analytics_router_module.router, prefix=f"{settings.API_V1_STR}/analytics", tags=["analytics"])
app.include_router(admin_router_module.router, prefix=f"{settings.API_V1_STR}/admin", tags=["admin"])



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
    return {"message": "Welcome to DOCSCOPE AI - Enterprise Multimodal Document Intelligence API"}

@app.get("/health", tags=["system"])
def health_check():
    """
    GET /health
    Basic health check endpoint for load balancers and orchestrators.
    """
    return {"status": "ok", "service": "docscope-api"}
