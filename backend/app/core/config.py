from pydantic_settings import BaseSettings
from pydantic import Field
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "DOCSCOPE AI"
    API_V1_STR: str = "/api/v1"
    
    # Database Settings
    DATABASE_URL: str = Field(
        default="postgresql://postgres:postgres@localhost:5435/docscope",
        env="DATABASE_URL"
    )

    # JWT Settings (RS256)
    JWT_ALGORITHM: str = "RS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Path to RSA key pairs
    RSA_PRIVATE_KEY_PATH: str = Field(
        default="certs/private_key.pem",
        env="RSA_PRIVATE_KEY_PATH"
    )
    RSA_PUBLIC_KEY_PATH: str = Field(
        default="certs/public_key.pem",
        env="RSA_PUBLIC_KEY_PATH"
    )

    # S3 Settings
    S3_ENDPOINT_URL: str = Field(default="http://localhost:9000", env="S3_ENDPOINT_URL") # MinIO default
    S3_BUCKET_NAME: str = Field(default="docscope-storage", env="S3_BUCKET_NAME")
    AWS_ACCESS_KEY_ID: str = Field(default="minioadmin", env="AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: str = Field(default="minioadmin", env="AWS_SECRET_ACCESS_KEY")
    AWS_REGION: str = Field(default="us-east-1", env="AWS_REGION")

    # Celery Settings
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0", env="CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/0", env="CELERY_RESULT_BACKEND")

    # ClamAV Settings
    CLAMAV_HOST: str = Field(default="localhost", env="CLAMAV_HOST")
    CLAMAV_PORT: int = Field(default=3310, env="CLAMAV_PORT")

    # Qdrant Settings — Vision Collection (ColQwen2, existing)
    QDRANT_URL: str = Field(default="http://localhost:6333", env="QDRANT_URL")
    QDRANT_COLLECTION_NAME: str = "pages"

    # Qdrant Settings — Text Collection (BGE-M3, NEW)
    QDRANT_TEXT_COLLECTION_NAME: str = Field(default="text_chunks", env="QDRANT_TEXT_COLLECTION_NAME")

    # LLM Settings
    LLM_PROVIDER: str = Field(default="gemini", env="LLM_PROVIDER")  # gemini | mock
    GEMINI_API_KEY: str = Field(default="", env="GEMINI_API_KEY")
    GEMINI_MODEL: str = Field(default="gemini-1.5-flash", env="GEMINI_MODEL")

    # ─────────────────────────────────────────────────────────────────────────
    # Hybrid Pipeline: OCR (PaddleOCR)
    # ─────────────────────────────────────────────────────────────────────────
    PADDLE_HOME: str = Field(default="/app/.paddle", env="PADDLE_HOME")
    # Pages with embedded text shorter than this are treated as scanned (OCR triggered)
    OCR_SCANNED_TEXT_THRESHOLD: int = Field(default=50, env="OCR_SCANNED_TEXT_THRESHOLD")
    # Minimum PaddleOCR confidence to store a chunk (0.0 – 1.0)
    OCR_CONFIDENCE_MIN: float = Field(default=0.6, env="OCR_CONFIDENCE_MIN")
    # Concurrent OCR worker processes
    OCR_WORKERS: int = Field(default=2, env="OCR_WORKERS")

    # ─────────────────────────────────────────────────────────────────────────
    # Hybrid Pipeline: BGE-M3 Text Embeddings
    # ─────────────────────────────────────────────────────────────────────────
    BGE_M3_MODEL_PATH: str = Field(default="BAAI/bge-m3", env="BGE_M3_MODEL_PATH")
    BGE_M3_BATCH_SIZE: int = Field(default=8, env="BGE_M3_BATCH_SIZE")
    # Maximum token length per text chunk before splitting
    BGE_M3_MAX_TOKENS: int = Field(default=512, env="BGE_M3_MAX_TOKENS")

    # ─────────────────────────────────────────────────────────────────────────
    # Hybrid Pipeline: BGE-Reranker-v2-m3
    # ─────────────────────────────────────────────────────────────────────────
    BGE_RERANKER_MODEL_PATH: str = Field(default="BAAI/bge-reranker-v2-m3", env="BGE_RERANKER_MODEL_PATH")
    # Number of merged candidates fed into the cross-encoder
    RERANKER_TOP_K_INPUT: int = Field(default=20, env="RERANKER_TOP_K_INPUT")
    # Final top-K passed to Gemini Flash as context
    RERANKER_TOP_K_OUTPUT: int = Field(default=5, env="RERANKER_TOP_K_OUTPUT")

    # ─────────────────────────────────────────────────────────────────────────
    # Hybrid Pipeline: Docling Document Parser
    # ─────────────────────────────────────────────────────────────────────────
    DOCLING_ENABLED: bool = Field(default=True, env="DOCLING_ENABLED")

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()

