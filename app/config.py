from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    FLASK_ENV: str = "development"
    MONGO_URI: str
    JWT_SECRET_KEY: str
    CORS_ORIGINS: List[str] = ["http://localhost:5000"]
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()