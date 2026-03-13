"""
Configuration Module
Handles environment variables and application settings
"""

import os
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional

class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Application
    APP_NAME: str = "Distributed Search & Cache Engine"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Database
    DATABASE_URL: str = "sqlite:///./data/dsce.db"
    DATABASE_POOL_SIZE: int = 20
    
    # Redis Cache
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_MAX_CONNECTIONS: int = 10
    CACHE_TTL: int = 300
    CACHE_POPULAR_TTL_MULTIPLIER: int = 4
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 60
    
    # Indexing
    MAX_DOCUMENT_SIZE: int = 1048576  # 1MB
    BATCH_INDEX_SIZE: int = 100
    
    # Sharding
    SHARD_CONFIG: dict = {
        "A-F": {"node": "node-1", "range": ("A", "F")},
        "G-M": {"node": "node-2", "range": ("G", "M")},
        "N-Z": {"node": "node-3", "range": ("N", "Z")}
    }
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Security
    SECRET_KEY: str = "your-secret-key-here-change-this-in-production"
    CORS_ORIGINS: list = ["http://localhost:8000", "http://localhost:3000"]
    
    class Config:
        env_file = ".env"
        extra = "ignore"  # This allows extra fields in .env file

@lru_cache()
def get_settings():
    """Get cached settings"""
    return Settings()

settings = get_settings()