#!/usr/bin/env python3
"""Configuration management for the bot"""

import os
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Bot configuration"""
    
    # Discord
    BOT_TOKEN: str = os.getenv("DISCORD_BOT_TOKEN", "")
    GUILD_ID: Optional[int] = None
    
    # Admin users
    ADMIN_USER_IDS: List[str] = [
        uid.strip() for uid in os.getenv("ADMIN_USER_IDS", "").split(",") if uid.strip()
    ]
    
    # Alert settings
    FALLBACK_CHANNEL_ID: Optional[int] = None
    
    @classmethod
    def _get_int_env(cls, key: str) -> Optional[int]:
        """Get integer environment variable"""
        value = os.getenv(key)
        if value and value.strip():
            try:
                return int(value.strip())
            except ValueError:
                return None
        return None
    
    # Database
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "price_tracker.db")
    
    # Scraper settings
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    RATE_LIMIT_DELAY: int = int(os.getenv("RATE_LIMIT_DELAY", "2"))
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR: str = os.getenv("LOG_DIR", "logs")
    
    # Bot settings
    COMMAND_PREFIX: str = "!"
    CHECK_INTERVAL_MINUTES: int = 5
    
    @classmethod
    def validate(cls) -> bool:
        """Validate configuration"""
        # Initialize integer environment variables
        cls.GUILD_ID = cls._get_int_env("DISCORD_GUILD_ID")
        cls.FALLBACK_CHANNEL_ID = cls._get_int_env("FALLBACK_CHANNEL_ID")
        
        if not cls.BOT_TOKEN:
            print("❌ DISCORD_BOT_TOKEN not set in .env file")
            return False
            
        if not cls.ADMIN_USER_IDS:
            print("❌ ADMIN_USER_IDS not set in .env file")
            return False
            
        # Create directories
        Path(cls.LOG_DIR).mkdir(exist_ok=True)
        
        return True
    
    @classmethod
    def is_admin(cls, user_id: int) -> bool:
        """Check if user is admin"""
        return str(user_id) in cls.ADMIN_USER_IDS