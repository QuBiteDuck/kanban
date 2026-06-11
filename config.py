from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # JWT
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_DAYS: int = 7
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./kanban.db"
    
    # Files
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 1048576  # 1MB
    ALLOWED_MIME_TYPES: str = "image/jpeg,image/png,image/gif,image/webp,video/mp4,audio/mpeg"
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"
    
    # Debug
    DEBUG: bool = False

    @property
    def allowed_mime_types_list(self) -> List[str]:
        return [mime.strip() for mime in self.ALLOWED_MIME_TYPES.split(",")]

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()