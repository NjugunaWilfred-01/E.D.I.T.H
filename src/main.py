"""
EDITH Main Application

FastAPI application with enterprise-grade security and authentication.
Configured with rate limiting, CORS, security headers, and comprehensive monitoring.
"""

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time
import uuid
from typing import Optional

from src.config import config
from src.utils.logger import logger
from src.api.auth import auth_router
from src.api.middleware import SecurityHeadersMiddleware, RateLimitMiddleware
from src.api.dependencies import get_current_user
from src.models import User


# Security scheme for JWT tokens
security = HTTPBearer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    logger.info("🚀 EDITH Authentication System starting up...")
    logger.info(f"Environment: {config.environment.value}")
    logger.info(f"Security configuration loaded: {config.get_config_summary()}")
    
    yield
    
    # Shutdown
    logger.info("🔒 EDITH Authentication System shutting down...")


# Create FastAPI application
app = FastAPI(
    title="EDITH Authentication System",
    description="Elite-Grade Artificial Intelligence Authentication API",
    version="1.0.0",
    docs_url="/docs" if config.environment.value != "production" else None,
    redoc_url="/redoc" if config.environment.value != "production" else None,
    lifespan=lifespan
)

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Add rate limiting middleware
app.add_middleware(RateLimitMiddleware)

# Add CORS middleware
if config.environment.value != "production":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:8080"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

# Add trusted host middleware for production
if config.environment.value == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["yourdomain.com", "*.yourdomain.com"]
    )


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log all requests for security monitoring"""
    start_time = time.time()
    request_id = str(uuid.uuid4())
    
    # Add request ID to request state
    request.state.request_id = request_id
    
    # Log request
    logger.info(
        f"Request started: {request.method} {request.url.path}",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "client_ip": request.client.host,
            "user_agent": request.headers.get("user-agent")
        }
    )
    
    try:
        response = await call_next(request)
        
        # Calculate processing time
        process_time = time.time() - start_time
        
        # Log response
        logger.info(
            f"Request completed: {response.status_code}",
            extra={
                "request_id": request_id,
                "status_code": response.status_code,
                "process_time": process_time
            }
        )
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(process_time)
        
        return response
        
    except Exception as e:
        # Log error
        logger.error(
            f"Request failed: {str(e)}",
            extra={
                "request_id": request_id,
                "error": str(e)
            }
        )
        raise


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler"""
    request_id = getattr(request.state, "request_id", "unknown")
    
    # Log security-relevant errors
    if exc.status_code in [401, 403, 429]:
        logger.security_event(
            event_type="unauthorized_access" if exc.status_code in [401, 403] else "rate_limit_exceeded",
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            additional_data={
                "status_code": exc.status_code,
                "detail": exc.detail,
                "path": request.url.path
            }
        )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "request_id": request_id,
                "timestamp": time.time()
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler for unhandled errors"""
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.error(
        f"Unhandled exception: {str(exc)}",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "client_ip": request.client.host
        }
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": 500,
                "message": "Internal server error",
                "request_id": request_id,
                "timestamp": time.time()
            }
        }
    )


# Health check endpoint
@app.get("/health", tags=["System"])
async def health_check():
    """System health check endpoint"""
    return {
        "status": "healthy",
        "service": "EDITH Authentication System",
        "version": "1.0.0",
        "environment": config.environment.value,
        "timestamp": time.time()
    }


# System info endpoint (protected)
@app.get("/system/info", tags=["System"])
async def system_info(current_user: User = Depends(get_current_user)):
    """Get system information (admin only)"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return {
        "system": "EDITH Authentication System",
        "version": "1.0.0",
        "environment": config.environment.value,
        "configuration": config.get_config_summary(),
        "timestamp": time.time()
    }


# Include authentication routes
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])


# Root endpoint
@app.get("/", tags=["System"])
async def root():
    """Root endpoint with system information"""
    return {
        "message": "EDITH Authentication System",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs" if config.environment.value != "production" else "disabled",
        "timestamp": time.time()
    }


if __name__ == "__main__":
    import uvicorn
    
    # Development server configuration
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True if config.environment.value == "development" else False,
        log_level="info",
        access_log=True
    )
