"""Application settings using pydantic-settings"""

from functools import lru_cache
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings"""
    
    # Bot Configuration
    bot_token: str = Field(..., alias="BOT_TOKEN")
    
    # Database Configuration
    database_url: str = Field(..., alias="DATABASE_URL")
    
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
    
    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    
    model_config = SettingsConfigDict(
        env_file=".env",
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


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

