"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ollama_base_url: str = "http://localhost:11434"
    ollama_timeout_seconds: float = 60.0
    
    # DB Config
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "appia"
    
    class Config:
        env_file = ".env"

settings = Settings()
