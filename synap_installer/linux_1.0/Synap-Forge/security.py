# app/security.py
"""Production security layer"""

import secrets
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Header, HTTPException, Depends, Security
from fastapi.security import APIKeyHeader
from jose import JWTError, jwt
from passlib.context import CryptContext

# ── Configuration ──
SECRET_KEY = os.getenv("SYNAP_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# ── Rate Limiting ──
from collections import defaultdict
from time import time

class RateLimiter:
    """Token bucket rate limiter"""
    
    def __init__(self, rate: int = 60, per: int = 60):
        self.rate = rate  # requests
        self.per = per    # seconds
        self.buckets = defaultdict(lambda: (time(), 0))
    
    def allow(self, key: str) -> bool:
        now = time()
        last_check, tokens = self.buckets[key]
        
        elapsed = now - last_check
        tokens += elapsed * (self.rate / self.per)
        
        if tokens >= self.rate:
            tokens = self.rate
        
        self.buckets[key] = (now, tokens)
        
        if tokens >= 1:
            self.buckets[key] = (now, tokens - 1)
            return True
        return False

rate_limiter = RateLimiter(rate=60, per=60)

# ── Authentication ──
class SecurityManager:
    def __init__(self):
        self.api_keys = {}
        self._load_keys()
    
    def _load_keys(self):
        """Load API keys from environment"""
        keys = os.getenv("SYNAP_API_KEYS", "")
        for key in keys.split(","):
            key = key.strip()
            if key:
                name, value = key.split(":", 1) if ":" in key else ("default", key)
                self.api_keys[name] = value
    
    def verify_key(self, api_key: str) -> bool:
        """Verify API key"""
        return any(api_key == v for v in self.api_keys.values())
    
    def create_token(self, user_id: str) -> str:
        """Create JWT token"""
        expires = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {
            "sub": user_id,
            "exp": expires,
            "iat": datetime.utcnow()
        }
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    
    def verify_token(self, token: str) -> Optional[dict]:
        """Verify JWT token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            return None

security = SecurityManager()

# ── Dependencies ──
async def verify_api_key(
    api_key: str = Security(api_key_header)
) -> str:
    """Verify API key dependency"""
    if not api_key or not security.verify_key(api_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )
    
    # Rate limit by API key
    if not rate_limiter.allow(api_key):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded"
        )
    
    return api_key

async def verify_admin_key(
    api_key: str = Security(api_key_header)
) -> str:
    """Admin-only API key verification"""
    if not api_key:
        raise HTTPException(401, "API key required")
    
    # Check admin keys
    admin_keys = os.getenv("SYNAP_ADMIN_KEYS", "").split(",")
    if api_key not in admin_keys:
        raise HTTPException(403, "Admin privileges required")
    
    return api_key