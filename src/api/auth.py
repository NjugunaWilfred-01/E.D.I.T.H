"""
EDITH Authentication API Endpoints

RESTful API endpoints for user authentication, registration, and session management.
Implements comprehensive security measures and input validation.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from src.models import (
    User, UserSession, UserCreate, UserLogin, UserResponse, TokenResponse,
    SessionInfo, UserStatus
)
from src.auth import (
    AuthenticationService, AuthenticationError, InvalidCredentialsError,
    AccountLockedError, AccountNotVerifiedError, TooManyAttemptsError
)
from src.security.jwt_handler import jwt_handler, TokenExpiredError, TokenInvalidError
from src.api.dependencies import (
    get_current_user, get_admin_user, get_request_info, get_db_session
)
from src.utils.logger import logger



# Create authentication router
auth_router = APIRouter()


@auth_router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    request: Request,
    db: Session = Depends(get_db_session)
):
    """
    Register a new user account
    
    - **username**: Unique username (3-50 characters, alphanumeric + underscore/hyphen)
    - **email**: Valid email address
    - **password**: Strong password (min 12 chars, uppercase, lowercase, number, special char)
    
    Returns user information (excluding sensitive data)
    """
    request_info = get_request_info(request)
    
    try:
        # Create authentication service
        auth_service = AuthenticationService(db)
        
        # Register user
        user = auth_service.register_user(
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            ip_address=request_info["ip_address"],
            user_agent=request_info["user_agent"]
        )
        
        logger.info(f"User registered successfully: {user.username}")
        
        return UserResponse.from_orm(user)
        
    except AuthenticationError as e:
        logger.warning(f"Registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@auth_router.post("/login", response_model=TokenResponse)
async def login_user(
    login_data: UserLogin,
    request: Request,
    db: Session = Depends(get_db_session)
):
    """
    Authenticate user and return access tokens
    
    - **username**: Username or email address
    - **password**: User password
    - **remember_me**: Keep session active longer (optional)
    - **device_name**: Device name for tracking (optional)
    - **mfa_code**: Multi-factor authentication code (if MFA enabled)
    
    Returns access token, refresh token, and user information
    """
    request_info = get_request_info(request)
    
    try:
        # Create authentication service
        auth_service = AuthenticationService(db)
        
        # Extract device fingerprint from headers
        device_fingerprint = request.headers.get("X-Device-Fingerprint")
        
        # Authenticate user
        user, access_token, refresh_token = auth_service.authenticate_user(
            username=login_data.username,
            password=login_data.password,
            ip_address=request_info["ip_address"],
            user_agent=request_info["user_agent"],
            device_fingerprint=device_fingerprint,
            mfa_code=login_data.mfa_code
        )
        
        logger.info(f"User logged in successfully: {user.username}")
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=3600,  # 1 hour
            user=UserResponse.from_orm(user)
        )
        
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    except AccountLockedError as e:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=str(e)
        )
    except AccountNotVerifiedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except TooManyAttemptsError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e)
        )
    except AuthenticationError as e:
        logger.warning(f"Login failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@auth_router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    refresh_token: str,
    db: Session = Depends(get_db_session)
):
    """
    Refresh access token using refresh token
    
    - **refresh_token**: Valid refresh token
    
    Returns new access token and refresh token
    """
    request_info = get_request_info(request)
    
    try:
        # Refresh tokens
        new_access_token, new_refresh_token = jwt_handler.refresh_access_token(refresh_token)
        
        # Get user information from new token
        payload = jwt_handler.get_token_claims(new_access_token)
        user_id = payload.get("sub")
        
        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                logger.info(f"Token refreshed for user: {user.username}")
                
                return TokenResponse(
                    access_token=new_access_token,
                    refresh_token=new_refresh_token,
                    token_type="bearer",
                    expires_in=3600,
                    user=UserResponse.from_orm(user)
                )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
        
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired"
        )
    except TokenInvalidError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@auth_router.post("/logout")
async def logout_user(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Logout user and invalidate tokens
    
    Requires valid access token in Authorization header
    """
    request_info = get_request_info(request)
    
    try:
        # Get authorization header
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            
            # Blacklist the token
            jwt_handler.blacklist_token(token)
            
            # TODO: Invalidate refresh token and session in database
            
            logger.audit(
                action="user_logout",
                user_id=str(current_user.id),
                details=request_info
            )
            
            logger.info(f"User logged out: {current_user.username}")
            
            return {"message": "Logged out successfully"}
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No token provided"
        )
        
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


@auth_router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user information
    
    Requires valid access token in Authorization header
    """
    return UserResponse.from_orm(current_user)


@auth_router.get("/sessions", response_model=List[SessionInfo])
async def get_user_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Get all active sessions for current user
    
    Requires valid access token in Authorization header
    """
    try:
        # Get user sessions from database
        sessions = db.query(UserSession).filter(
            UserSession.user_id == current_user.id,
            UserSession.status == "active"
        ).all()
        
        session_info = []
        for session in sessions:
            info = SessionInfo(
                id=session.id,
                device_name=session.device.device_name if session.device else "Unknown Device",
                device_type=session.device.device_type if session.device else "web",
                ip_address=session.ip_address,
                location=session.location,
                last_activity_at=session.last_activity_at,
                is_current=False  # TODO: Determine current session
            )
            session_info.append(info)
        
        return session_info
        
    except Exception as e:
        logger.error(f"Get sessions error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sessions"
        )
