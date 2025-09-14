"""
EDITH Data Models

Security-focused data models for authentication system.
Designed with privacy, audit trails, and data integrity in mind.
"""

from datetime import datetime, timezone
from typing import Optional, List
from enum import Enum
import uuid

from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from pydantic import BaseModel, EmailStr, Field, validator


# SQLAlchemy Base
Base = declarative_base()


class UserStatus(str, Enum):
    """User account status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    LOCKED = "locked"
    PENDING_VERIFICATION = "pending_verification"


class DeviceType(str, Enum):
    """Device type enumeration"""
    WEB = "web"
    MOBILE = "mobile"
    DESKTOP = "desktop"
    API = "api"


class SessionStatus(str, Enum):
    """Session status enumeration"""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


# SQLAlchemy Models
class User(Base):
    """User model with comprehensive security features"""
    __tablename__ = "users"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    
    # Authentication
    password_hash = Column(String(255), nullable=False)
    password_salt = Column(String(255), nullable=False)
    
    # Account status
    status = Column(String(20), default=UserStatus.PENDING_VERIFICATION, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    
    # Security tracking
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    last_login_ip = Column(String(45), nullable=True)  # IPv6 compatible
    password_changed_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # MFA settings
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    mfa_secret = Column(String(255), nullable=True)
    backup_codes = Column(Text, nullable=True)  # JSON array of backup codes
    
    # Audit timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime(timezone=True), nullable=True)  # Soft delete
    
    # Relationships
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    devices = relationship("UserDevice", back_populates="user", cascade="all, delete-orphan")
    login_history = relationship("LoginHistory", back_populates="user", cascade="all, delete-orphan")


class UserSession(Base):
    """User session tracking for security monitoring"""
    __tablename__ = "user_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Session identification
    session_token = Column(String(255), unique=True, nullable=False, index=True)
    refresh_token = Column(String(255), unique=True, nullable=True, index=True)
    
    # Session metadata
    status = Column(String(20), default=SessionStatus.ACTIVE, nullable=False)
    device_id = Column(UUID(as_uuid=True), ForeignKey("user_devices.id"), nullable=True)
    
    # Security context
    ip_address = Column(String(45), nullable=False)
    user_agent = Column(Text, nullable=True)
    location = Column(String(255), nullable=True)  # Geolocation if available
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_activity_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    device = relationship("UserDevice", back_populates="sessions")


class UserDevice(Base):
    """Trusted device management"""
    __tablename__ = "user_devices"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Device identification
    device_name = Column(String(255), nullable=False)
    device_type = Column(String(20), nullable=False)
    device_fingerprint = Column(String(255), unique=True, nullable=False, index=True)
    
    # Device metadata
    browser = Column(String(255), nullable=True)
    os = Column(String(255), nullable=True)
    is_trusted = Column(Boolean, default=False, nullable=False)
    
    # Security tracking
    first_seen_ip = Column(String(45), nullable=False)
    last_seen_ip = Column(String(45), nullable=True)
    last_seen_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="devices")
    sessions = relationship("UserSession", back_populates="device")


class LoginHistory(Base):
    """Comprehensive login attempt tracking"""
    __tablename__ = "login_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # Nullable for failed attempts
    
    # Attempt details
    username_attempted = Column(String(255), nullable=False)
    success = Column(Boolean, nullable=False)
    failure_reason = Column(String(255), nullable=True)
    
    # Security context
    ip_address = Column(String(45), nullable=False)
    user_agent = Column(Text, nullable=True)
    device_fingerprint = Column(String(255), nullable=True)
    
    # Geolocation (if available)
    country = Column(String(2), nullable=True)  # ISO country code
    city = Column(String(255), nullable=True)
    
    # Timestamps
    attempted_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="login_history")


# Pydantic Models for API
class UserBase(BaseModel):
    """Base user model for API responses"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    
    @validator('username')
    def validate_username(cls, v):
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username must contain only letters, numbers, hyphens, and underscores')
        return v.lower()


class UserCreate(UserBase):
    """User creation model"""
    password: str = Field(..., min_length=12, max_length=128)
    
    @validator('password')
    def validate_password(cls, v):
        # Password strength validation
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
            raise ValueError('Password must contain at least one special character')
        return v


class UserResponse(UserBase):
    """User response model (safe for API responses)"""
    id: uuid.UUID
    status: UserStatus
    is_verified: bool
    is_admin: bool
    mfa_enabled: bool
    last_login_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    """User login model"""
    username: str
    password: str
    remember_me: bool = False
    device_name: Optional[str] = None
    mfa_code: Optional[str] = None


class TokenResponse(BaseModel):
    """JWT token response model"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class SessionInfo(BaseModel):
    """Session information model"""
    id: uuid.UUID
    device_name: Optional[str]
    device_type: DeviceType
    ip_address: str
    location: Optional[str]
    last_activity_at: datetime
    is_current: bool = False
    
    class Config:
        from_attributes = True
