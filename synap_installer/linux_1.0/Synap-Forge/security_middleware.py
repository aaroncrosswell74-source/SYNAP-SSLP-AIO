# security_middleware.py
"""
SYNAP·FORGE Security Middleware
Enforces authentication and authorization on all protected routes
"""

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import jwt
import os
from typing import List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class SecurityMiddleware(BaseHTTPMiddleware):
    """Security enforcement middleware"""
    
    def __init__(self, app, secret_key: str, public_paths: List[str] = None,
                 excluded_methods: List[str] = None):
        super().__init__(app)
        self.secret_key = secret_key
        self.public_paths = public_paths or [
            "/health",
            "/health/live",
            "/health/ready",
            "/api/rl/dashboard",
            "/docs",
            "/openapi.json"
        ]
        self.excluded_methods = excluded_methods or ["OPTIONS"]
    
    async def dispatch(self, request: Request, call_next):
        # Skip auth for excluded methods
        if request.method in self.excluded_methods:
            return await call_next(request)
        
        # Skip auth for public paths
        for path in self.public_paths:
            if request.url.path.startswith(path):
                return await call_next(request)
        
        # Check for auth token
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return JSONResponse(
                {"error": "Authentication required", "code": "MISSING_AUTH"},
                status_code=401
            )
        
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                {"error": "Invalid authentication format", "code": "INVALID_FORMAT"},
                status_code=401
            )
        
        token = auth_header.replace("Bearer ", "")
        
        try:
            # Decode token
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            
            # Check expiration
            exp = payload.get("exp")
            if exp and datetime.fromtimestamp(exp) < datetime.now():
                return JSONResponse(
                    {"error": "Token expired", "code": "TOKEN_EXPIRED"},
                    status_code=401
                )
            
            # Attach user info to request
            request.state.user = {
                "id": payload.get("sub"),
                "roles": payload.get("roles", []),
                "permissions": payload.get("permissions", [])
            }
            
            # Log authenticated request
            logger.debug(f"Authenticated request: {request.method} {request.url.path} by {payload.get('sub')}")
            
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return JSONResponse(
                {"error": "Invalid authentication token", "code": "INVALID_TOKEN"},
                status_code=401
            )
        except Exception as e:
            logger.error(f"Auth error: {e}")
            return JSONResponse(
                {"error": "Authentication error", "code": "AUTH_ERROR"},
                status_code=500
            )
        
        # Continue request
        return await call_next(request)

# Apply middleware (in synap_server.py)
app.add_middleware(
    SecurityMiddleware,
    secret_key=os.getenv("JWT_SECRET", "your-secret-key-change-in-production"),
    public_paths=["/health", "/health/live", "/health/ready", "/api/rl/dashboard"]
)