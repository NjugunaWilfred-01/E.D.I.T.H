"""
EDITH JWT Token Management

Enterprise-grade JWT token handling with advanced security features.
Implements token generation, validation, refresh, and blacklisting.
"""

import jwt
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple
import uuid

from src.config import config
from src.utils.logger import logger


class JWTTokenError(Exception):
    """Custom JWT token exception"""
    pass


class TokenExpiredError(JWTTokenError):
    """Token has expired"""
    pass


class TokenInvalidError(JWTTokenError):
    """Token is invalid"""
    pass


class JWTHandler:
    """Advanced JWT token management with security features"""
    
    def __init__(self):
        self.secret_key = config.security.jwt_secret_key
        self.algorithm = config.security.jwt_algorithm
        self.access_token_expire_hours = config.security.jwt_expiration_hours
        self.refresh_token_expire_days = config.security.jwt_refresh_expiration_days
        
        # Token blacklist (in production, use Redis or database)
        self._blacklisted_tokens = set()
    
    def create_access_token(self, user_id: str, username: str, 
                          additional_claims: Optional[Dict[str, Any]] = None) -> str:
        """
        Create JWT access token with security claims
        
        Args:
            user_id: User identifier
            username: Username
            additional_claims: Additional claims to include
            
        Returns:
            JWT access token string
        """
        now = datetime.now(timezone.utc)
        expire = now + timedelta(hours=self.access_token_expire_hours)
        
        # Standard JWT claims
        payload = {
            "sub": user_id,  # Subject (user ID)
            "username": username,
            "iat": now,  # Issued at
            "exp": expire,  # Expiration time
            "nbf": now,  # Not before
            "jti": str(uuid.uuid4()),  # JWT ID for tracking
            "type": "access",
            "iss": "edith-auth",  # Issuer
        }
        
        # Add additional claims if provided
        if additional_claims:
            payload.update(additional_claims)
        
        try:
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            logger.debug(f"Access token created for user {username}")
            return token
            
        except Exception as e:
            logger.error(f"Failed to create access token: {e}")
            raise JWTTokenError(f"Token creation failed: {e}")
    
    def create_refresh_token(self, user_id: str, session_id: str) -> str:
        """
        Create JWT refresh token for session management
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            
        Returns:
            JWT refresh token string
        """
        now = datetime.now(timezone.utc)
        expire = now + timedelta(days=self.refresh_token_expire_days)
        
        payload = {
            "sub": user_id,
            "session_id": session_id,
            "iat": now,
            "exp": expire,
            "nbf": now,
            "jti": str(uuid.uuid4()),
            "type": "refresh",
            "iss": "edith-auth",
        }
        
        try:
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            logger.debug(f"Refresh token created for user {user_id}")
            return token
            
        except Exception as e:
            logger.error(f"Failed to create refresh token: {e}")
            raise JWTTokenError(f"Refresh token creation failed: {e}")
    
    def verify_token(self, token: str, token_type: str = "access") -> Dict[str, Any]:
        """
        Verify and decode JWT token with comprehensive validation
        
        Args:
            token: JWT token string
            token_type: Expected token type (access/refresh)
            
        Returns:
            Decoded token payload
            
        Raises:
            TokenExpiredError: If token has expired
            TokenInvalidError: If token is invalid
        """
        try:
            # Check if token is blacklisted
            if self.is_token_blacklisted(token):
                raise TokenInvalidError("Token has been revoked")
            
            # Decode and verify token
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_nbf": True,
                    "verify_signature": True,
                }
            )
            
            # Verify token type
            if payload.get("type") != token_type:
                raise TokenInvalidError(f"Invalid token type. Expected {token_type}")
            
            # Verify issuer
            if payload.get("iss") != "edith-auth":
                raise TokenInvalidError("Invalid token issuer")
            
            logger.debug(f"Token verified successfully for user {payload.get('sub')}")
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token verification failed: Token expired")
            raise TokenExpiredError("Token has expired")
            
        except jwt.InvalidTokenError as e:
            logger.warning(f"Token verification failed: {e}")
            raise TokenInvalidError(f"Invalid token: {e}")
            
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            raise TokenInvalidError(f"Token verification failed: {e}")
    
    def refresh_access_token(self, refresh_token: str) -> Tuple[str, str]:
        """
        Create new access token using refresh token
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            Tuple of (new_access_token, new_refresh_token)
        """
        try:
            # Verify refresh token
            payload = self.verify_token(refresh_token, token_type="refresh")
            
            user_id = payload["sub"]
            session_id = payload["session_id"]
            
            # Create new tokens
            new_access_token = self.create_access_token(user_id, payload.get("username", ""))
            new_refresh_token = self.create_refresh_token(user_id, session_id)
            
            # Blacklist old refresh token
            self.blacklist_token(refresh_token)
            
            logger.info(f"Tokens refreshed for user {user_id}")
            return new_access_token, new_refresh_token
            
        except (TokenExpiredError, TokenInvalidError):
            raise
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            raise JWTTokenError(f"Token refresh failed: {e}")
    
    def blacklist_token(self, token: str):
        """
        Add token to blacklist
        
        Args:
            token: Token to blacklist
        """
        try:
            # Extract JTI (JWT ID) for efficient blacklisting
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": False}  # Don't verify expiration for blacklisting
            )
            
            jti = payload.get("jti")
            if jti:
                self._blacklisted_tokens.add(jti)
                logger.debug(f"Token blacklisted: {jti}")
            
        except Exception as e:
            logger.error(f"Failed to blacklist token: {e}")
    
    def is_token_blacklisted(self, token: str) -> bool:
        """
        Check if token is blacklisted
        
        Args:
            token: Token to check
            
        Returns:
            True if token is blacklisted, False otherwise
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": False}
            )
            
            jti = payload.get("jti")
            return jti in self._blacklisted_tokens
            
        except Exception:
            return True  # Consider invalid tokens as blacklisted
    
    def get_token_claims(self, token: str) -> Dict[str, Any]:
        """
        Extract claims from token without verification (for debugging)
        
        Args:
            token: JWT token
            
        Returns:
            Token claims dictionary
        """
        try:
            return jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": False}
            )
        except Exception as e:
            logger.error(f"Failed to extract token claims: {e}")
            return {}
    
    def create_device_token(self, user_id: str, device_id: str, 
                          device_fingerprint: str) -> str:
        """
        Create device-specific token for trusted devices
        
        Args:
            user_id: User identifier
            device_id: Device identifier
            device_fingerprint: Device fingerprint
            
        Returns:
            Device-specific JWT token
        """
        now = datetime.now(timezone.utc)
        expire = now + timedelta(days=30)  # Longer expiration for trusted devices
        
        payload = {
            "sub": user_id,
            "device_id": device_id,
            "device_fingerprint": device_fingerprint,
            "iat": now,
            "exp": expire,
            "nbf": now,
            "jti": str(uuid.uuid4()),
            "type": "device",
            "iss": "edith-auth",
        }
        
        try:
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            logger.debug(f"Device token created for user {user_id}, device {device_id}")
            return token
            
        except Exception as e:
            logger.error(f"Failed to create device token: {e}")
            raise JWTTokenError(f"Device token creation failed: {e}")
    
    def validate_device_token(self, token: str, expected_fingerprint: str) -> Dict[str, Any]:
        """
        Validate device-specific token
        
        Args:
            token: Device token to validate
            expected_fingerprint: Expected device fingerprint
            
        Returns:
            Decoded token payload
        """
        payload = self.verify_token(token, token_type="device")
        
        # Verify device fingerprint
        if payload.get("device_fingerprint") != expected_fingerprint:
            raise TokenInvalidError("Device fingerprint mismatch")
        
        return payload
    
    def cleanup_expired_blacklist(self):
        """
        Clean up expired tokens from blacklist
        This should be called periodically to prevent memory leaks
        """
        # In production, implement with Redis TTL or database cleanup
        # For now, this is a placeholder
        logger.debug("Blacklist cleanup executed")


# Global JWT handler instance
jwt_handler = JWTHandler()
