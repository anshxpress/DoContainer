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

    # Qdrant Settings
    QDRANT_URL: str = Field(default="http://localhost:6333", env="QDRANT_URL")
    QDRANT_COLLECTION_NAME: str = "pages"

    # LLM Settings
    LLM_PROVIDER: str = Field(default="gemini", env="LLM_PROVIDER")  # gemini | mock
    GEMINI_API_KEY: str = Field(default="", env="GEMINI_API_KEY")
    GEMINI_MODEL: str = Field(default="gemini-1.5-flash", env="GEMINI_MODEL")

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
