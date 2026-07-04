from pydantic import BaseModel
from backend.app.core.app_mode import AppMode

class FeatureFlags(BaseModel):
    # Core Document Features
    ENABLE_AI_CHAT: bool = True
    ENABLE_OCR: bool = True
    ENABLE_SUMMARY: bool = True
    ENABLE_SEARCH: bool = True
    ENABLE_DUPLICATE_DETECTION: bool = True
    ENABLE_FOLDERS: bool = True
    ENABLE_TAGS: bool = True
    
    # Enterprise Modules
    ENABLE_VERSIONING: bool = False
    ENABLE_APPROVAL: bool = False
    ENABLE_ACL: bool = False
    ENABLE_TEAM: bool = False
    ENABLE_ORGANIZATION: bool = False
    ENABLE_NOTIFICATIONS: bool = False
    ENABLE_TASKS: bool = False
    ENABLE_AUDIT: bool = False
    ENABLE_ANALYTICS: bool = False
    ENABLE_MONITORING: bool = False
    ENABLE_KNOWLEDGE_GRAPH: bool = False

def get_feature_flags(mode: AppMode) -> FeatureFlags:
    if mode == AppMode.PERSONAL:
        return FeatureFlags(
            ENABLE_VERSIONING=False,
            ENABLE_APPROVAL=False,
            ENABLE_ACL=False,
            ENABLE_TEAM=False,
            ENABLE_ORGANIZATION=False,
            ENABLE_NOTIFICATIONS=False,
            ENABLE_TASKS=False,
            ENABLE_AUDIT=False,
            ENABLE_ANALYTICS=False,
            ENABLE_MONITORING=False,
            ENABLE_KNOWLEDGE_GRAPH=False
        )
    elif mode == AppMode.TEAM:
        # Future Team mode
        return FeatureFlags(
            ENABLE_VERSIONING=True,
            ENABLE_APPROVAL=False,
            ENABLE_ACL=False,
            ENABLE_TEAM=True,
            ENABLE_ORGANIZATION=True,
            ENABLE_NOTIFICATIONS=True,
            ENABLE_TASKS=True,
            ENABLE_AUDIT=False,
            ENABLE_ANALYTICS=False,
            ENABLE_MONITORING=False,
            ENABLE_KNOWLEDGE_GRAPH=False
        )
    elif mode == AppMode.ENTERPRISE:
        return FeatureFlags(
            ENABLE_VERSIONING=True,
            ENABLE_APPROVAL=True,
            ENABLE_ACL=True,
            ENABLE_TEAM=True,
            ENABLE_ORGANIZATION=True,
            ENABLE_NOTIFICATIONS=True,
            ENABLE_TASKS=True,
            ENABLE_AUDIT=True,
            ENABLE_ANALYTICS=True,
            ENABLE_MONITORING=True,
            ENABLE_KNOWLEDGE_GRAPH=True
        )
    return FeatureFlags()
