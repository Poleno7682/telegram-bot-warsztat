"""Application settings using pydantic-settings"""

import os
from pathlib import Path
from functools import lru_cache
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings"""
    
    # Bot Configuration
    bot_token: str = Field(..., alias="BOT_TOKEN")
    
    # Database Configuration
    # Option 1: Full database URL (takes precedence if set)
    database_url: str = Field(default="", alias="DATABASE_URL")
    
    # Option 2: PostgreSQL connection parameters (used if DATABASE_URL is empty)
    db_host: str = Field(default="", alias="DB_HOST")
    db_port: int = Field(default=5432, alias="DB_PORT")
    db_user: str = Field(default="", alias="DB_USER")
    db_password: str = Field(default="", alias="DB_PASSWORD")
    db_name: str = Field(default="", alias="DB_NAME")
    
    # Admin Configuration
    admin_ids: str = Field(..., alias="ADMIN_IDS")
    
    # Mechanic Configuration
    mechanic_ids: str = Field(default="", alias="MECHANIC_IDS")
    
    # User Configuration
    user_ids: str = Field(default="", alias="USER_IDS")
    
    # Default Settings
    default_work_start: str = Field(default="08:00", alias="DEFAULT_WORK_START")
    default_work_end: str = Field(default="16:00", alias="DEFAULT_WORK_END")
    default_time_step: int = Field(default=10, alias="DEFAULT_TIME_STEP")
    default_buffer_time: int = Field(default=15, alias="DEFAULT_BUFFER_TIME")
    
    # Timezone
    timezone: str = Field(default="Europe/Warsaw", alias="TIMEZONE")
    
    # Supported Languages
    supported_languages: str = Field(default="pl,ru", alias="SUPPORTED_LANGUAGES")
    
    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    @property
    def admin_ids_list(self) -> List[int]:
        """Parse admin IDs from comma-separated string"""
        if not self.admin_ids:
            return []
        return [int(id_.strip()) for id_ in self.admin_ids.split(",") if id_.strip()]
    
    @property
    def mechanic_ids_list(self) -> List[int]:
        """Parse mechanic IDs from comma-separated string"""
        if not self.mechanic_ids:
            return []
        return [int(id_.strip()) for id_ in self.mechanic_ids.split(",") if id_.strip()]
    
    @property
    def user_ids_list(self) -> List[int]:
        """Parse user IDs from comma-separated string"""
        if not self.user_ids:
            return []
        return [int(id_.strip()) for id_ in self.user_ids.split(",") if id_.strip()]
    
    @property
    def supported_languages_list(self) -> List[str]:
        """Parse supported languages from comma-separated string"""
        if not self.supported_languages:
            return ["pl", "ru"]  # Default fallback
        return [lang.strip() for lang in self.supported_languages.split(",") if lang.strip()]
    
    def get_database_url(self) -> str:
        """
        Get database URL, constructing it from PostgreSQL parameters if DATABASE_URL is not set
        
        Returns:
            Database connection URL
        """
        # If DATABASE_URL is explicitly set, use it
        if self.database_url:
            return self.database_url
        
        # If PostgreSQL parameters are provided, construct URL
        if self.db_host and self.db_user and self.db_name:
            # URL encode password if it contains special characters
            from urllib.parse import quote_plus
            password = quote_plus(self.db_password) if self.db_password else ""
            
            if password:
                return f"postgresql+asyncpg://{self.db_user}:{password}@{self.db_host}:{self.db_port}/{self.db_name}"
            else:
                return f"postgresql+asyncpg://{self.db_user}@{self.db_host}:{self.db_port}/{self.db_name}"
        
        # Default: SQLite for development/testing
        return "sqlite+aiosqlite:///./db/bot.db"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    # Settings loads from .env via model_config, not constructor args
    return Settings()  # type: ignore[call-arg]

