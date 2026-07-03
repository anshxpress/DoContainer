import json
import logging
from typing import Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from backend.app.core.security import decode_token
from backend.app.tasks.partition_tasks import log_audit_event_task

logger = logging.getLogger(__name__)

class AuditLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Process request first to get response
        response = await call_next(request)

        # 2. Check if this is an endpoint we want to audit
        try:
            path = request.url.path
            method = request.method

            action = None
            resource = path

            # Determine action based on route and method
            if "/api/v1/search" in path and method == "POST":
                action = "document.search"
            elif "/api/v1/chat" in path and method == "POST":
                action = "chat.ask"
            elif "/api/v1/retention" in path:
                if method == "POST":
                    action = "retention.create"
                elif method == "DELETE":
                    action = "retention.delete"
            elif "/lock" in path:
                if method == "POST":
                    action = "document.lock.acquire"
                elif method == "PUT":
                    action = "document.lock.renew"
                elif method == "DELETE":
                    action = "document.lock.release"
            elif "/acl" in path:
                if method == "POST":
                    action = "document.acl.grant"
                elif method == "DELETE":
                    action = "document.acl.revoke"
            elif "/approval" in path:
                if method == "POST" and "submit" in path:
                    action = "document.approval.submit"
                elif method == "POST" and "decide" in path:
                    action = "document.approval.decide"
            elif "/versions" in path:
                if method == "POST":
                    action = "document.version.upload"
            elif "/api/v1/documents" in path:
                if method == "POST":
                    action = "document.upload"
                elif method in ["PATCH", "PUT"]:
                    action = "document.edit"
                elif method == "DELETE":
                    action = "document.delete"
                elif method == "GET" and "download" in path:
                    action = "document.download"
            # If the request matches our audit targets, trigger async log
            if action:
                user_id_str = None
                
                # Extract token from Authorization header
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    token = auth_header.split(" ")[1]
                    payload = decode_token(token)
                    if payload:
                        user_id_str = payload.get("sub")

                # If no token, maybe check cookies or session if relevant, but Bearer is default
                ip_address = request.headers.get("x-forwarded-for") or request.headers.get("x-real-ip")
                if ip_address:
                    # Capture first IP if forwarded-for contains chain
                    ip_address = ip_address.split(",")[0].strip()
                else:
                    if request.client:
                        ip_address = request.client.host
                    else:
                        ip_address = "unknown"

                # Setup metadata (e.g. query parameters)
                meta = {
                    "query_params": dict(request.query_params),
                    "status_code": response.status_code,
                    "method": method
                }
                metadata_json = json.dumps(meta)

                # Send task to Celery queue asynchronously
                log_audit_event_task.delay(
                    user_id_str=user_id_str,
                    ip_address=ip_address,
                    action=action,
                    resource=resource,
                    metadata_json=metadata_json
                )
        except Exception as exc:
            # Never let audit log failures block API requests
            logger.error(f"Error in AuditLogMiddleware: {exc}")

        return response
