import sys
sys.path.append("d:/docscope")
import uuid
from datetime import datetime, timezone
from backend.app.api.v1.analytics import DashboardAnalyticsResponse

totals = {
    "documents": 5,
    "pages_rendered": int(10.0),
    "storage_bytes": int(1024.0),
    "api_tokens": int(50),
    "active_users": 2
}

recent_audits_list = [
    {
        "action": "test",
        "user": "test@test.com",
        "time": datetime.now(timezone.utc).isoformat()
    }
]

daily_trends = [
    {
        "date": "Jun 29",
        "tokens": int(10.0),
        "pages": int(5.0),
        "storage_mb": round(1024.0 / (1024 * 1024), 2)
    }
]

file_type_breakdown = [
    {
        "name": "PDF",
        "value": 5,
        "size_mb": round((1024 or 0) / (1024 * 1024), 2)
    }
]

metrics = {
    "totals": totals,
    "recent_audits": recent_audits_list,
    "daily_trends": daily_trends,
    "file_type_breakdown": file_type_breakdown
}

try:
    resp = DashboardAnalyticsResponse(**metrics)
    print("Success:", resp)
except Exception as e:
    print("Validation Error:", e)
