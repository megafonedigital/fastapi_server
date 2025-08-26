from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # API settings
    API_TITLE: str = "Media Downloader API"
    API_VERSION: str = "1.0.0"
    API_DEBUG: bool = False
    API_KEY: str
    
    # MinIO settings
    MINIO_ENDPOINT: str
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET: str = "media"
    MINIO_SECURE: bool = False
    
    # Working directory for temporary files
    WORKDIR: str = "/app/data"
    
    # Whisper settings
    WHISPER_MODEL: str = "medium"  # tiny, base, small, medium, large
    WHISPER_LANGUAGE: str = "pt"
    
    # URL expiration time in seconds (default: 24 hours)
    URL_EXPIRATION: int = 86400
    
    model_config = SettingsConfigDict(env_file=[".env", "app/.env"], env_file_encoding="utf-8", extra="ignore")

# Create settings instance
settings = Settings()