"""
EDITH Security Middleware

Advanced security middleware for FastAPI with rate limiting, security headers,
and request monitoring capabilities.
"""

import time
import json
from typing import Dict, Optional, Tuple
from collections import defaultdict, deque
from datetime import datetime, timedelta
import asyncio

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import config
from src.utils.logger import logger


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses"""
    
    def __init__(self, app):
        super().__init__(app)
        self.security_headers = {
            # Prevent XSS attacks
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            
            # HTTPS enforcement
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            
            # Content Security Policy
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self'; "
                "connect-src 'self'; "
                "frame-ancestors 'none';"
            ),
            
            # Referrer Policy
            "Referrer-Policy": "strict-origin-when-cross-origin",
            
            # Permissions Policy
            "Permissions-Policy": (
                "geolocation=(), "
                "microphone=(), "
                "camera=(), "
                "payment=(), "
                "usb=(), "
                "magnetometer=(), "
                "gyroscope=(), "
                "speaker=()"
            ),
            
            # Server identification
            "Server": "EDITH/1.0",
            
            # Cache control for sensitive endpoints
            "Cache-Control": "no-store, no-cache, must-revalidate, private",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    
    async def dispatch(self, request: Request, call_next):
        """Add security headers to response"""
        response = await call_next(request)
        
        # Add security headers
        for header, value in self.security_headers.items():
            response.headers[header] = value
        
        # Remove server information leakage
        if "server" in response.headers:
            response.headers["server"] = "EDITH/1.0"
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Advanced rate limiting middleware with multiple strategies"""
    
    def __init__(self, app):
        super().__init__(app)
        
        # Rate limiting storage (in production, use Redis)
        self.request_counts: Dict[str, deque] = defaultdict(deque)
        self.blocked_ips: Dict[str, datetime] = {}
        
        # Rate limiting configuration
        self.rate_limits = {
            # General API limits
            "default": {"requests": 100, "window": 60},  # 100 requests per minute
            
            # Authentication endpoints (more restrictive)
            "/api/v1/auth/login": {"requests": 5, "window": 60},  # 5 login attempts per minute
            "/api/v1/auth/register": {"requests": 3, "window": 300},  # 3 registrations per 5 minutes
            "/api/v1/auth/forgot-password": {"requests": 2, "window": 300},  # 2 password resets per 5 minutes
            
            # Token refresh (moderate)
            "/api/v1/auth/refresh": {"requests": 10, "window": 60},  # 10 refreshes per minute
        }
        
        # Progressive delay configuration
        self.progressive_delays = {
            1: 0,      # First request - no delay
            2: 1,      # Second request - 1 second delay
            3: 2,      # Third request - 2 second delay
            4: 5,      # Fourth request - 5 second delay
            5: 10,     # Fifth request - 10 second delay
        }
        
        # Cleanup task
        asyncio.create_task(self._cleanup_task())
    
    async def dispatch(self, request: Request, call_next):
        """Apply rate limiting to requests"""
        client_ip = self._get_client_ip(request)
        path = request.url.path
        
        # Check if IP is temporarily blocked
        if await self._is_ip_blocked(client_ip):
            logger.security_event(
                event_type="rate_limit_exceeded",
                ip_address=client_ip,
                user_agent=request.headers.get("user-agent"),
                additional_data={"path": path, "reason": "IP blocked"}
            )
            
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": 429,
                        "message": "Too many requests. IP temporarily blocked.",
                        "retry_after": 300
                    }
                }
            )
        
        # Apply rate limiting
        rate_limit_result = await self._check_rate_limit(client_ip, path)
        
        if not rate_limit_result["allowed"]:
            # Log rate limit violation
            logger.security_event(
                event_type="rate_limit_exceeded",
                ip_address=client_ip,
                user_agent=request.headers.get("user-agent"),
                additional_data={
                    "path": path,
                    "requests_made": rate_limit_result["requests_made"],
                    "limit": rate_limit_result["limit"]
                }
            )
            
            # Block IP if too many violations
            await self._handle_rate_limit_violation(client_ip, path)
            
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": 429,
                        "message": "Rate limit exceeded",
                        "retry_after": rate_limit_result["retry_after"]
                    }
                },
                headers={
                    "X-RateLimit-Limit": str(rate_limit_result["limit"]),
                    "X-RateLimit-Remaining": str(rate_limit_result["remaining"]),
                    "X-RateLimit-Reset": str(rate_limit_result["reset_time"]),
                    "Retry-After": str(rate_limit_result["retry_after"])
                }
            )
        
        # Apply progressive delay for repeated requests
        delay = self._calculate_progressive_delay(client_ip, path)
        if delay > 0:
            await asyncio.sleep(delay)
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to successful responses
        response.headers["X-RateLimit-Limit"] = str(rate_limit_result["limit"])
        response.headers["X-RateLimit-Remaining"] = str(rate_limit_result["remaining"])
        response.headers["X-RateLimit-Reset"] = str(rate_limit_result["reset_time"])
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address with proxy support"""
        # Check for forwarded headers (when behind proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host
    
    async def _check_rate_limit(self, client_ip: str, path: str) -> Dict:
        """Check if request is within rate limits"""
        # Determine rate limit for this path
        limit_config = self.rate_limits.get(path, self.rate_limits["default"])
        max_requests = limit_config["requests"]
        window_seconds = limit_config["window"]
        
        # Create key for this IP and path combination
        key = f"{client_ip}:{path}"
        
        # Get current time
        now = time.time()
        window_start = now - window_seconds
        
        # Clean old requests
        request_times = self.request_counts[key]
        while request_times and request_times[0] < window_start:
            request_times.popleft()
        
        # Check if within limits
        current_requests = len(request_times)
        allowed = current_requests < max_requests
        
        if allowed:
            # Add current request
            request_times.append(now)
        
        return {
            "allowed": allowed,
            "requests_made": current_requests,
            "limit": max_requests,
            "remaining": max(0, max_requests - current_requests - (1 if allowed else 0)),
            "reset_time": int(window_start + window_seconds),
            "retry_after": window_seconds
        }
    
    async def _is_ip_blocked(self, client_ip: str) -> bool:
        """Check if IP is temporarily blocked"""
        if client_ip in self.blocked_ips:
            block_time = self.blocked_ips[client_ip]
            if datetime.utcnow() - block_time < timedelta(minutes=5):
                return True
            else:
                # Remove expired block
                del self.blocked_ips[client_ip]
        
        return False
    
    async def _handle_rate_limit_violation(self, client_ip: str, path: str):
        """Handle rate limit violations with progressive blocking"""
        # Count violations in the last hour
        violation_key = f"{client_ip}:violations"
        now = time.time()
        hour_ago = now - 3600
        
        violations = self.request_counts[violation_key]
        while violations and violations[0] < hour_ago:
            violations.popleft()
        
        violations.append(now)
        
        # Block IP if too many violations
        if len(violations) >= 10:  # 10 violations in an hour
            self.blocked_ips[client_ip] = datetime.utcnow()
            logger.security_event(
                event_type="ip_blocked",
                ip_address=client_ip,
                additional_data={
                    "reason": "Too many rate limit violations",
                    "violations_count": len(violations)
                }
            )
    
    def _calculate_progressive_delay(self, client_ip: str, path: str) -> float:
        """Calculate progressive delay based on recent requests"""
        key = f"{client_ip}:{path}"
        request_times = self.request_counts[key]
        
        # Count requests in the last 10 seconds
        now = time.time()
        recent_requests = sum(1 for t in request_times if now - t <= 10)
        
        return self.progressive_delays.get(recent_requests, 15)  # Max 15 second delay
    
    async def _cleanup_task(self):
        """Periodic cleanup of old data"""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                
                now = time.time()
                hour_ago = now - 3600
                
                # Clean old request counts
                for key in list(self.request_counts.keys()):
                    request_times = self.request_counts[key]
                    while request_times and request_times[0] < hour_ago:
                        request_times.popleft()
                    
                    # Remove empty deques
                    if not request_times:
                        del self.request_counts[key]
                
                # Clean expired IP blocks
                expired_blocks = [
                    ip for ip, block_time in self.blocked_ips.items()
                    if datetime.utcnow() - block_time > timedelta(hours=1)
                ]
                
                for ip in expired_blocks:
                    del self.blocked_ips[ip]
                
                logger.debug("Rate limiting cleanup completed")
                
            except Exception as e:
                logger.error(f"Rate limiting cleanup error: {e}")
