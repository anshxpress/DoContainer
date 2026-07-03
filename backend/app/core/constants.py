from enum import Enum

class DocumentStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Roles(str, Enum):
    ADMIN = "admin"
    APPROVER = "approver"
    VIEWER = "viewer"
    EDITOR = "editor"

class Permissions(str, Enum):
    READ = "read"
    WRITE = "write"
    APPROVE = "approve"
    DOWNLOAD = "download"

class QueueNames(str, Enum):
    DEFAULT = "celery"
    OCR = "ocr"
    EMBEDDING = "embedding"
    VISION = "vision"

class MetadataTypes(str, Enum):
    SUMMARY = "summary"
    KEYWORD = "keyword"
    ENTITY = "entity"

class CollectionNames(str, Enum):
    VISION = "pages"
    TEXT = "text_chunks"
