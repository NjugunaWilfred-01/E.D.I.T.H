"""
EDITH API Dependencies

FastAPI dependency injection for authentication, authorization, and request validation.
Provides reusable security components across all API endpoints.
"""

from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from src.models import User, UserSession, SessionStatus
from src.security.jwt_handler import jwt_handler, TokenExpiredError, TokenInvalidError
from src.utils.logger import logger
from src.database import get_db_session


# Security scheme for JWT tokens
security = HTTPBearer()


async def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db_session)
) -> Optional[User]:
    """
    Get current user from JWT token (optional - returns None if no token)
    
    Args:
        request: FastAPI request object
        credentials: JWT token credentials
        db: Database session
        
    Returns:
        User object if authenticated, None otherwise
    """
    if not credentials:
        return None
    
    try:
        return await _authenticate_user(request, credentials.credentials, db)
    except HTTPException:
        return None


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db_session)
) -> User:
    """
    Get current user from JWT token (required - raises exception if no valid token)
    
    Args:
        request: FastAPI request object
        credentials: JWT token credentials
        db: Database session
        
    Returns:
        User object
        
    Raises:
        HTTPException: If authentication fails
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return await _authenticate_user(request, credentials.credentials, db)


async def get_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current user and verify admin privileges
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User object with admin privileges
        
    Raises:
        HTTPException: If user is not an admin
    """
    if not current_user.is_admin:
        logger.security_event(
            event_type="unauthorized_access",
            user_id=str(current_user.id),
            additional_data={"attempted_action": "admin_access", "reason": "insufficient_privileges"}
        )
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    return current_user


async def _authenticate_user(request: Request, token: str, db: Session) -> User:
    """
    Internal function to authenticate user from JWT token
    
    Args:
        request: FastAPI request object
        token: JWT token string
        db: Database session
        
    Returns:
        User object
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        # Verify JWT token
        payload = jwt_handler.verify_token(token, token_type="access")
        
        user_id = payload.get("sub")
        session_id = payload.get("session_id")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get user from database
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.security_event(
                event_type="unauthorized_access",
                user_id=user_id,
                ip_address=_get_client_ip(request),
                additional_data={"reason": "user_not_found", "token_user_id": user_id}
            )
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check user status
        if user.status != "active":
            logger.security_event(
                event_type="unauthorized_access",
                user_id=str(user.id),
                ip_address=_get_client_ip(request),
                additional_data={"reason": "inactive_user", "user_status": user.status}
            )
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Account is {user.status}",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verify session if session_id is present
        if session_id:
            session = db.query(UserSession).filter(
                UserSession.id == session_id,
                UserSession.user_id == user.id
            ).first()
            
            if not session:
                logger.security_event(
                    event_type="unauthorized_access",
                    user_id=str(user.id),
                    ip_address=_get_client_ip(request),
                    additional_data={"reason": "session_not_found", "session_id": session_id}
                )
                
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session not found",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            if session.status != SessionStatus.ACTIVE:
                logger.security_event(
                    event_type="unauthorized_access",
                    user_id=str(user.id),
                    ip_address=_get_client_ip(request),
                    additional_data={"reason": "inactive_session", "session_status": session.status}
                )
                
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session is not active",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # Update session activity
            from datetime import datetime
            session.last_activity_at = datetime.utcnow()
            db.commit()
        
        # Log successful authentication
        logger.debug(f"User authenticated successfully: {user.username}")
        
        return user
        
    except TokenExpiredError:
        logger.security_event(
            event_type="token_expired",
            ip_address=_get_client_ip(request),
            additional_data={"token_type": "access"}
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    except TokenInvalidError as e:
        logger.security_event(
            event_type="unauthorized_access",
            ip_address=_get_client_ip(request),
            additional_data={"reason": "invalid_token", "error": str(e)}
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    except HTTPException:
        raise
        
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_request_info(request: Request) -> Dict[str, Any]:
    """
    Extract request information for logging and security monitoring
    
    Args:
        request: FastAPI request object
        
    Returns:
        Dictionary with request information
    """
    return {
        "ip_address": _get_client_ip(request),
        "user_agent": request.headers.get("user-agent"),
        "method": request.method,
        "path": request.url.path,
        "query_params": dict(request.query_params),
        "request_id": getattr(request.state, "request_id", None)
    }


def _get_client_ip(request: Request) -> str:
    """
    Extract client IP address with proxy support
    
    Args:
        request: FastAPI request object
        
    Returns:
        Client IP address
    """
    # Check for forwarded headers (when behind proxy/load balancer)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    return request.client.host if request.client else "unknown"


async def validate_device_fingerprint(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Validate device fingerprint for enhanced security
    
    Args:
        request: FastAPI request object
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Device information
    """
    device_fingerprint = request.headers.get("X-Device-Fingerprint")
    
    if not device_fingerprint:
        logger.security_event(
            event_type="suspicious_activity",
            user_id=str(current_user.id),
            ip_address=_get_client_ip(request),
            additional_data={"reason": "missing_device_fingerprint"}
        )
    
    # In a real implementation, you would validate the device fingerprint
    # against known devices for this user
    
    return {
        "fingerprint": device_fingerprint,
        "ip_address": _get_client_ip(request),
        "user_agent": request.headers.get("user-agent"),
        "is_trusted": False  # Implement device trust logic
    }


class RequirePermission:
    """
    Dependency class for permission-based access control
    """
    
    def __init__(self, permission: str):
        self.permission = permission
    
    def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        """
        Check if user has required permission
        
        Args:
            current_user: Current authenticated user
            
        Returns:
            User object if permission granted
            
        Raises:
            HTTPException: If permission denied
        """
        # In a real implementation, you would check user permissions
        # For now, we'll use admin status as a simple permission check
        
        if self.permission == "admin" and not current_user.is_admin:
            logger.security_event(
                event_type="unauthorized_access",
                user_id=str(current_user.id),
                additional_data={
                    "attempted_permission": self.permission,
                    "reason": "insufficient_privileges"
                }
            )
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{self.permission}' required"
            )
        
        return current_user


# Common permission dependencies
require_admin = RequirePermission("admin")
require_user_management = RequirePermission("user_management")
require_system_access = RequirePermission("system_access")
