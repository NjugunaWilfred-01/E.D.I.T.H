"""
EDITH Configuration Management Module

This module handles all configuration settings for the EDITH authentication system.
Security-first approach with environment-based configuration isolation.
"""

import os
from typing import Dict, Any
from dataclasses import dataclass
from enum import Enum


class Environment(Enum):
    """Environment types for configuration isolation"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


@dataclass
class SecurityConfig:
    """Security-related configuration settings"""
    # JWT Configuration
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    jwt_refresh_expiration_days: int = 30
    
    # Password Security
    password_min_length: int = 12
    password_require_special: bool = True
    password_require_numbers: bool = True
    password_require_uppercase: bool = True
    password_hash_rounds: int = 12
    
    # Rate Limiting
    login_attempts_limit: int = 5
    lockout_duration_minutes: int = 30
    
    # Session Security
    session_timeout_minutes: int = 60
    secure_cookies: bool = True
    
    # MFA Settings
    totp_issuer: str = "EDITH"
    backup_codes_count: int = 10


@dataclass
class DatabaseConfig:
    """Database configuration settings"""
    host: str
    port: int
    name: str
    username: str
    password: str
    ssl_mode: str = "require"
    connection_pool_size: int = 10
    
    @property
    def connection_string(self) -> str:
        """Generate database connection string"""
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.name}?sslmode={self.ssl_mode}"


@dataclass
class LoggingConfig:
    """Logging configuration settings"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: str = "logs/edith.log"
    max_file_size: int = 10485760  # 10MB
    backup_count: int = 5
    enable_console: bool = True


class Config:
    """Main configuration class with environment-specific settings"""
    
    def __init__(self, environment: Environment = None):
        self.environment = environment or self._detect_environment()
        self.security = self._load_security_config()
        self.database = self._load_database_config()
        self.logging = self._load_logging_config()
    
    def _detect_environment(self) -> Environment:
        """Detect current environment from environment variables"""
        env_name = os.getenv("EDITH_ENV", "development").lower()
        try:
            return Environment(env_name)
        except ValueError:
            return Environment.DEVELOPMENT
    
    def _load_security_config(self) -> SecurityConfig:
        """Load security configuration based on environment"""
        jwt_secret = os.getenv("JWT_SECRET_KEY")
        if not jwt_secret:
            if self.environment == Environment.PRODUCTION:
                raise ValueError("JWT_SECRET_KEY must be set in production")
            jwt_secret = "dev-secret-key-change-in-production"
        
        return SecurityConfig(
            jwt_secret_key=jwt_secret,
            jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
            jwt_expiration_hours=int(os.getenv("JWT_EXPIRATION_HOURS", "24")),
            password_min_length=int(os.getenv("PASSWORD_MIN_LENGTH", "12")),
            login_attempts_limit=int(os.getenv("LOGIN_ATTEMPTS_LIMIT", "5")),
            session_timeout_minutes=int(os.getenv("SESSION_TIMEOUT_MINUTES", "60")),
            secure_cookies=self.environment == Environment.PRODUCTION,
        )
    
    def _load_database_config(self) -> DatabaseConfig:
        """Load database configuration based on environment"""
        if self.environment == Environment.TESTING:
            return DatabaseConfig(
                host="localhost",
                port=5432,
                name="edith_test",
                username="test_user",
                password="test_password"
            )
        
        return DatabaseConfig(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            name=os.getenv("DB_NAME", "edith"),
            username=os.getenv("DB_USERNAME", "edith_user"),
            password=os.getenv("DB_PASSWORD", "change_me"),
        )
    
    def _load_logging_config(self) -> LoggingConfig:
        """Load logging configuration based on environment"""
        level = "DEBUG" if self.environment == Environment.DEVELOPMENT else "INFO"
        
        return LoggingConfig(
            level=os.getenv("LOG_LEVEL", level),
            file_path=os.getenv("LOG_FILE_PATH", "logs/edith.log"),
            enable_console=self.environment != Environment.PRODUCTION
        )
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get non-sensitive configuration summary for debugging"""
        return {
            "environment": self.environment.value,
            "security": {
                "jwt_algorithm": self.security.jwt_algorithm,
                "password_min_length": self.security.password_min_length,
                "login_attempts_limit": self.security.login_attempts_limit,
                "session_timeout_minutes": self.security.session_timeout_minutes,
            },
            "database": {
                "host": self.database.host,
                "port": self.database.port,
                "name": self.database.name,
                "ssl_mode": self.database.ssl_mode,
            },
            "logging": {
                "level": self.logging.level,
                "file_path": self.logging.file_path,
            }
        }


# Global configuration instance
config = Config()
