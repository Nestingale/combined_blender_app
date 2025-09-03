from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List

class Settings(BaseSettings):
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Nestingale Blender API"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
    
    # CORS Settings
    BACKEND_CORS_ORIGINS: List[str] = ["*"]
    
    # AWS Settings
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "nestingale-dev-digital-assets"
    S3_PRODUCT_3D_ASSETS_BUCKET: str = "nestingale-dev-product-3d-assets"
    SQS_QUEUE_URL: str = "https://sqs.us-east-1.amazonaws.com/311504593279/EmailMarketing"
    
    # Blender Settings
    BLENDER_SCRIPTS_PATH: str = "app/scripts"
    BLENDER_OUTPUT_PATH: str = "app/scripts/generated_files"
    BLENDER_PATH: str = "/usr/local/bin/blender"  # Default path to blender executable
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # Timeout Settings
    REQUEST_TIMEOUT: int = 3600  # 1 hour timeout for requests
    KEEP_ALIVE_TIMEOUT: int = 300  # 5 minutes for keep-alive
    GRACEFUL_SHUTDOWN_TIMEOUT: int = 600  # 10 minutes for graceful shutdown
    BLENDER_PROCESS_TIMEOUT: int = 3500  # 58.3 minutes for Blender processes

    # Additional settings
    S3_REGION: str = ""
    LOG_LEVEL: str = "INFO"
    
    model_config = {
        "case_sensitive": True,
        "env_file": ".env",
        "extra": "allow"  # Allow extra fields from environment variables
    }

@lru_cache()
def get_settings() -> Settings:
    return Settings()
