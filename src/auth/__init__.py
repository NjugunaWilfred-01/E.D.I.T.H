"""
EDITH Authentication Module

Core authentication services with enterprise-grade security.
Handles user registration, login, session management, and security monitoring.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict, Any
import uuid
import secrets
import json

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from src.models import User, UserSession, UserDevice, LoginHistory, UserStatus, SessionStatus
from src.security.password import password_security
from src.security.jwt_handler import jwt_handler, TokenExpiredError, TokenInvalidError
from src.utils.logger import logger
from src.config import config


class AuthenticationError(Exception):
    """Base authentication exception"""
    pass


class InvalidCredentialsError(AuthenticationError):
    """Invalid username or password"""
    pass


class AccountLockedError(AuthenticationError):
    """Account is locked due to security reasons"""
    pass


class AccountNotVerifiedError(AuthenticationError):
    """Account email not verified"""
    pass


class TooManyAttemptsError(AuthenticationError):
    """Too many failed login attempts"""
    pass


class AuthenticationService:
    """Core authentication service with comprehensive security features"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.max_login_attempts = config.security.login_attempts_limit
        self.lockout_duration = timedelta(minutes=config.security.lockout_duration_minutes)
    
    def register_user(self, username: str, email: str, password: str, 
                     ip_address: str, user_agent: str = None) -> User:
        """
        Register new user with comprehensive validation
        
        Args:
            username: Unique username
            email: User email address
            password: Plain text password
            ip_address: Registration IP address
            user_agent: User agent string
            
        Returns:
            Created User object
            
        Raises:
            AuthenticationError: If registration fails
        """
        try:
            # Validate password strength
            is_valid, errors = password_security.validate_password_strength(password)
            if not is_valid:
                raise AuthenticationError(f"Password validation failed: {', '.join(errors)}")
            
            # Check if username or email already exists
            existing_user = self.db.query(User).filter(
                or_(User.username == username.lower(), User.email == email.lower())
            ).first()
            
            if existing_user:
                if existing_user.username == username.lower():
                    raise AuthenticationError("Username already exists")
                else:
                    raise AuthenticationError("Email already registered")
            
            # Hash password
            password_hash, salt = password_security.hash_password(password)
            
            # Create user
            user = User(
                username=username.lower(),
                email=email.lower(),
                password_hash=password_hash,
                password_salt=salt,
                status=UserStatus.PENDING_VERIFICATION,
                is_verified=False
            )
            
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
            
            # Log registration
            logger.audit(
                action="user_registration",
                user_id=str(user.id),
                details={
                    "username": username,
                    "email": email,
                    "ip_address": ip_address,
                    "user_agent": user_agent
                }
            )
            
            logger.info(f"User registered successfully: {username}")
            return user
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"User registration failed: {e}")
            raise AuthenticationError(f"Registration failed: {e}")
    
    def authenticate_user(self, username: str, password: str, ip_address: str,
                         user_agent: str = None, device_fingerprint: str = None,
                         mfa_code: str = None) -> Tuple[User, str, str]:
        """
        Authenticate user with comprehensive security checks
        
        Args:
            username: Username or email
            password: Plain text password
            ip_address: Login IP address
            user_agent: User agent string
            device_fingerprint: Device fingerprint
            mfa_code: MFA code if enabled
            
        Returns:
            Tuple of (User, access_token, refresh_token)
            
        Raises:
            Various authentication errors based on failure reason
        """
        # Record login attempt
        login_history = LoginHistory(
            username_attempted=username,
            success=False,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=device_fingerprint
        )
        
        try:
            # Find user by username or email
            user = self.db.query(User).filter(
                or_(User.username == username.lower(), User.email == username.lower())
            ).first()
            
            if not user:
                login_history.failure_reason = "User not found"
                self.db.add(login_history)
                self.db.commit()
                
                logger.login_failure(username, ip_address, "User not found")
                raise InvalidCredentialsError("Invalid username or password")
            
            # Update login history with user ID
            login_history.user_id = user.id
            
            # Check account status
            if user.status == UserStatus.LOCKED:
                login_history.failure_reason = "Account locked"
                self.db.add(login_history)
                self.db.commit()
                
                logger.login_failure(str(user.id), ip_address, "Account locked")
                raise AccountLockedError("Account is locked")
            
            if user.status == UserStatus.SUSPENDED:
                login_history.failure_reason = "Account suspended"
                self.db.add(login_history)
                self.db.commit()
                
                logger.login_failure(str(user.id), ip_address, "Account suspended")
                raise AccountLockedError("Account is suspended")
            
            if not user.is_verified:
                login_history.failure_reason = "Account not verified"
                self.db.add(login_history)
                self.db.commit()
                
                logger.login_failure(str(user.id), ip_address, "Account not verified")
                raise AccountNotVerifiedError("Please verify your email address")
            
            # Check for too many failed attempts
            if self._is_account_locked_due_to_attempts(user):
                login_history.failure_reason = "Too many failed attempts"
                self.db.add(login_history)
                self.db.commit()
                
                logger.login_failure(str(user.id), ip_address, "Too many failed attempts")
                raise TooManyAttemptsError("Account temporarily locked due to too many failed attempts")
            
            # Verify password
            if not password_security.verify_password(password, user.password_hash, user.password_salt):
                # Increment failed attempts
                user.failed_login_attempts += 1
                login_history.failure_reason = "Invalid password"
                self.db.add(login_history)
                self.db.commit()
                
                logger.login_failure(str(user.id), ip_address, "Invalid password")
                raise InvalidCredentialsError("Invalid username or password")
            
            # Check MFA if enabled
            if user.mfa_enabled and not self._verify_mfa_code(user, mfa_code):
                login_history.failure_reason = "Invalid MFA code"
                self.db.add(login_history)
                self.db.commit()
                
                logger.login_failure(str(user.id), ip_address, "Invalid MFA code")
                raise InvalidCredentialsError("Invalid MFA code")
            
            # Successful authentication - continue in next part
            return self._complete_authentication(user, ip_address, user_agent, device_fingerprint, login_history)
            
        except (InvalidCredentialsError, AccountLockedError, 
                AccountNotVerifiedError, TooManyAttemptsError):
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Authentication error: {e}")
            raise AuthenticationError(f"Authentication failed: {e}")
    
    def _is_account_locked_due_to_attempts(self, user: User) -> bool:
        """Check if account is locked due to failed attempts"""
        if user.failed_login_attempts < self.max_login_attempts:
            return False

        # Check if lockout period has expired
        if user.last_login_at:
            time_since_last_attempt = datetime.utcnow() - user.last_login_at
            if time_since_last_attempt > self.lockout_duration:
                # Reset failed attempts after lockout period
                user.failed_login_attempts = 0
                return False

        return True

    def _complete_authentication(self, user: User, ip_address: str, user_agent: str,
                               device_fingerprint: str, login_history: LoginHistory) -> Tuple[User, str, str]:
        """Complete successful authentication process"""
        # Reset failed attempts
        user.failed_login_attempts = 0
        user.last_login_at = datetime.utcnow()
        user.last_login_ip = ip_address

        # Create session
        session = self._create_user_session(user, ip_address, user_agent, device_fingerprint)

        # Generate tokens
        access_token = jwt_handler.create_access_token(
            user_id=str(user.id),
            username=user.username,
            additional_claims={
                "session_id": str(session.id),
                "is_admin": user.is_admin
            }
        )

        refresh_token = jwt_handler.create_refresh_token(
            user_id=str(user.id),
            session_id=str(session.id)
        )

        # Update session with tokens
        session.session_token = access_token
        session.refresh_token = refresh_token

        # Record successful login
        login_history.success = True
        login_history.failure_reason = None

        self.db.add(login_history)
        self.db.commit()

        logger.login_success(str(user.id), ip_address, user_agent)
        logger.audit(
            action="user_login",
            user_id=str(user.id),
            details={
                "ip_address": ip_address,
                "user_agent": user_agent,
                "session_id": str(session.id)
            }
        )

        return user, access_token, refresh_token

    def _create_user_session(self, user: User, ip_address: str,
                           user_agent: str = None, device_fingerprint: str = None) -> UserSession:
        """Create new user session"""
        # Handle device registration/recognition
        device = None
        if device_fingerprint:
            device = self._get_or_create_device(user, device_fingerprint, ip_address, user_agent)

        # Create session
        session = UserSession(
            user_id=user.id,
            device_id=device.id if device else None,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=datetime.utcnow() + timedelta(minutes=config.security.session_timeout_minutes)
        )

        self.db.add(session)
        return session

    def _get_or_create_device(self, user: User, device_fingerprint: str,
                            ip_address: str, user_agent: str = None) -> UserDevice:
        """Get existing device or create new one"""
        device = self.db.query(UserDevice).filter(
            and_(
                UserDevice.user_id == user.id,
                UserDevice.device_fingerprint == device_fingerprint
            )
        ).first()

        if device:
            # Update last seen information
            device.last_seen_ip = ip_address
            device.last_seen_at = datetime.utcnow()
        else:
            # Create new device
            device = UserDevice(
                user_id=user.id,
                device_name=self._extract_device_name(user_agent),
                device_type=self._detect_device_type(user_agent),
                device_fingerprint=device_fingerprint,
                first_seen_ip=ip_address,
                last_seen_ip=ip_address
            )
            self.db.add(device)

        return device

    def _extract_device_name(self, user_agent: str = None) -> str:
        """Extract device name from user agent"""
        if not user_agent:
            return "Unknown Device"

        # Simple device name extraction (can be enhanced)
        if "Mobile" in user_agent:
            return "Mobile Device"
        elif "Tablet" in user_agent:
            return "Tablet"
        else:
            return "Desktop/Laptop"

    def _detect_device_type(self, user_agent: str = None) -> str:
        """Detect device type from user agent"""
        if not user_agent:
            return "web"

        user_agent_lower = user_agent.lower()
        if "mobile" in user_agent_lower:
            return "mobile"
        elif "tablet" in user_agent_lower:
            return "mobile"
        else:
            return "web"

    def _verify_mfa_code(self, user: User, mfa_code: str = None) -> bool:
        """Verify MFA code (placeholder for now)"""
        if not user.mfa_enabled:
            return True

        if not mfa_code:
            return False

        # TODO: Implement TOTP verification
        # For now, return True for development
        return True
