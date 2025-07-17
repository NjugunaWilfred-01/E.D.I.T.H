"""
EDITH Logging Framework

Advanced logging system with security event tracking and audit capabilities.
Designed for forensic analysis and real-time monitoring.
"""

import logging
import logging.handlers
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass, asdict

from src.config import config


class LogLevel(Enum):
    """Custom log levels for EDITH system"""
    SECURITY = 25  # Between INFO and WARNING
    AUDIT = 35     # Between WARNING and ERROR


class SecurityEventType(Enum):
    """Types of security events to track"""
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGIN_BLOCKED = "login_blocked"
    PASSWORD_CHANGE = "password_change"
    MFA_ENABLED = "mfa_enabled"
    MFA_DISABLED = "mfa_disabled"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    TOKEN_EXPIRED = "token_expired"
    DEVICE_REGISTERED = "device_registered"
    DEVICE_REMOVED = "device_removed"


@dataclass
class SecurityEvent:
    """Security event data structure"""
    event_type: SecurityEventType
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    device_id: Optional[str] = None
    session_id: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class SecurityEventFormatter(logging.Formatter):
    """Custom formatter for security events"""
    
    def format(self, record):
        if hasattr(record, 'security_event'):
            event_data = {
                'timestamp': record.security_event.timestamp.isoformat(),
                'level': record.levelname,
                'event_type': record.security_event.event_type.value,
                'user_id': record.security_event.user_id,
                'ip_address': record.security_event.ip_address,
                'user_agent': record.security_event.user_agent,
                'device_id': record.security_event.device_id,
                'session_id': record.security_event.session_id,
                'additional_data': record.security_event.additional_data,
                'message': record.getMessage()
            }
            return json.dumps(event_data, default=str)
        
        return super().format(record)


class EDITHLogger:
    """Enhanced logger with security event tracking"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.security_logger = logging.getLogger(f"{name}.security")
        self.audit_logger = logging.getLogger(f"{name}.audit")
        
        # Add custom log levels
        logging.addLevelName(LogLevel.SECURITY.value, "SECURITY")
        logging.addLevelName(LogLevel.AUDIT.value, "AUDIT")
        
        self._setup_loggers()
    
    def _setup_loggers(self):
        """Configure all loggers with appropriate handlers"""
        # Ensure logs directory exists
        os.makedirs(os.path.dirname(config.logging.file_path), exist_ok=True)
        
        # Main application logger
        self._setup_main_logger()
        
        # Security events logger
        self._setup_security_logger()
        
        # Audit logger
        self._setup_audit_logger()
    
    def _setup_main_logger(self):
        """Setup main application logger"""
        self.logger.setLevel(getattr(logging, config.logging.level))
        
        # File handler
        file_handler = logging.handlers.RotatingFileHandler(
            config.logging.file_path,
            maxBytes=config.logging.max_file_size,
            backupCount=config.logging.backup_count
        )
        file_handler.setFormatter(logging.Formatter(config.logging.format))
        self.logger.addHandler(file_handler)
        
        # Console handler (if enabled)
        if config.logging.enable_console:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(logging.Formatter(config.logging.format))
            self.logger.addHandler(console_handler)
    
    def _setup_security_logger(self):
        """Setup security events logger"""
        self.security_logger.setLevel(LogLevel.SECURITY.value)
        
        # Security events file
        security_file = config.logging.file_path.replace('.log', '_security.log')
        security_handler = logging.handlers.RotatingFileHandler(
            security_file,
            maxBytes=config.logging.max_file_size,
            backupCount=config.logging.backup_count
        )
        security_handler.setFormatter(SecurityEventFormatter())
        self.security_logger.addHandler(security_handler)
    
    def _setup_audit_logger(self):
        """Setup audit logger"""
        self.audit_logger.setLevel(LogLevel.AUDIT.value)
        
        # Audit file
        audit_file = config.logging.file_path.replace('.log', '_audit.log')
        audit_handler = logging.handlers.RotatingFileHandler(
            audit_file,
            maxBytes=config.logging.max_file_size,
            backupCount=config.logging.backup_count
        )
        audit_handler.setFormatter(logging.Formatter(
            '%(asctime)s - AUDIT - %(message)s'
        ))
        self.audit_logger.addHandler(audit_handler)
    
    # Standard logging methods
    def debug(self, message: str, **kwargs):
        self.logger.debug(message, **kwargs)
    
    def info(self, message: str, **kwargs):
        self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self.logger.error(message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        self.logger.critical(message, **kwargs)
    
    # Security event logging
    def security_event(self, event: SecurityEvent, message: str = ""):
        """Log a security event"""
        record = self.security_logger.makeRecord(
            self.security_logger.name,
            LogLevel.SECURITY.value,
            __file__,
            0,
            message or f"Security event: {event.event_type.value}",
            (),
            None
        )
        record.security_event = event
        self.security_logger.handle(record)
    
    def audit(self, action: str, user_id: str = None, details: Dict[str, Any] = None):
        """Log an audit event"""
        audit_data = {
            'action': action,
            'user_id': user_id,
            'details': details or {},
            'timestamp': datetime.utcnow().isoformat()
        }
        self.audit_logger.log(
            LogLevel.AUDIT.value,
            json.dumps(audit_data, default=str)
        )
    
    # Convenience methods for common security events
    def login_success(self, user_id: str, ip_address: str, user_agent: str = None):
        """Log successful login"""
        event = SecurityEvent(
            event_type=SecurityEventType.LOGIN_SUCCESS,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        self.security_event(event, f"User {user_id} logged in successfully")
    
    def login_failure(self, user_id: str, ip_address: str, reason: str = None):
        """Log failed login attempt"""
        event = SecurityEvent(
            event_type=SecurityEventType.LOGIN_FAILURE,
            user_id=user_id,
            ip_address=ip_address,
            additional_data={'reason': reason} if reason else None
        )
        self.security_event(event, f"Login failed for user {user_id}")
    
    def suspicious_activity(self, description: str, user_id: str = None, 
                          ip_address: str = None, additional_data: Dict = None):
        """Log suspicious activity"""
        event = SecurityEvent(
            event_type=SecurityEventType.SUSPICIOUS_ACTIVITY,
            user_id=user_id,
            ip_address=ip_address,
            additional_data=additional_data
        )
        self.security_event(event, f"Suspicious activity detected: {description}")


# Global logger instance
logger = EDITHLogger("edith")
