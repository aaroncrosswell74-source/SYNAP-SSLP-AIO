"""Distributed rate limiting with Redis support"""

import time
import logging
from typing import Optional
from .config import RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW, REDIS_HOST, REDIS_PORT, REDIS_DB

logger = logging.getLogger("RateLimiter")

class RateLimiter:
    """Token bucket rate limiter with optional Redis support"""
    
    def __init__(self):
        self._redis = None
        self._local_cache = {}
        
        if REDIS_HOST:
            try:
                import redis
                self._redis = redis.Redis(
                    host=REDIS_HOST,
                    port=REDIS_PORT,
                    db=REDIS_DB,
                    decode_responses=True
                )
                self._redis.ping()
                logger.info(f"Redis connected for rate limiting: {REDIS_HOST}:{REDIS_PORT}")
            except Exception as e:
                logger.warning(f"Redis unavailable, using local rate limiting: {e}")
                self._redis = None
    
    def is_allowed(self, key: str) -> tuple[bool, Optional[int]]:
        """
        Check if request is allowed.
        Returns: (allowed, retry_after_seconds)
        """
        if self._redis:
            return self._is_allowed_redis(key)
        else:
            return self._is_allowed_local(key)
    
    def _is_allowed_redis(self, key: str) -> tuple[bool, Optional[int]]:
        """Rate limit using Redis"""
        try:
            now = time.time()
            window_key = f"ratelimit:{key}:{int(now / RATE_LIMIT_WINDOW)}"
            
            count = self._redis.incr(window_key)
            if count == 1:
                self._redis.expire(window_key, RATE_LIMIT_WINDOW + 5)
            
            if count > RATE_LIMIT_REQUESTS:
                ttl = self._redis.ttl(window_key)
                return False, max(1, ttl)
            
            return True, None
        except Exception as e:
            logger.warning(f"Redis rate limit error: {e}")
            # Fail open - allow request if Redis is down
            return True, None
    
    def _is_allowed_local(self, key: str) -> tuple[bool, Optional[int]]:
        """Rate limit using local cache (single instance only)"""
        now = time.time()
        window = int(now / RATE_LIMIT_WINDOW)
        cache_key = f"{key}:{window}"
        
        if cache_key not in self._local_cache:
            self._local_cache[cache_key] = 1
            # Clean old entries
            for k in list(self._local_cache.keys()):
                if not k.startswith(f"{key}:"):
                    continue
                k_window = int(k.split(":")[-1])
                if k_window < window:
                    del self._local_cache[k]
        else:
            self._local_cache[cache_key] += 1
        
        count = self._local_cache.get(cache_key, 0)
        if count > RATE_LIMIT_REQUESTS:
            return False, RATE_LIMIT_WINDOW
        
        return True, None

# Singleton instance
_rate_limiter = None

def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter
