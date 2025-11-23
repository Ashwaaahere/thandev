"""
Caching utilities with Redis support and in-memory fallback
"""
import os
import json
import hashlib
import logging
from typing import Optional, Any
import time

logger = logging.getLogger(__name__)

# Try to import Redis
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available, using in-memory cache")

# In-memory cache fallback
_memory_cache = {}
_cache_ttl = 300  # 5 minutes default

class Cache:
    """Cache manager with Redis and in-memory fallback"""
    
    def __init__(self):
        self.redis_client = None
        self.use_redis = False
        
        if REDIS_AVAILABLE:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            try:
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
                # Test connection
                self.redis_client.ping()
                self.use_redis = True
                logger.info("Redis cache initialized")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}, using in-memory cache")
                self.use_redis = False
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if self.use_redis and self.redis_client:
            try:
                value = self.redis_client.get(key)
                if value:
                    return json.loads(value)
            except Exception as e:
                logger.error(f"Redis get error: {e}")
                return None
        else:
            # In-memory cache
            if key in _memory_cache:
                value, timestamp = _memory_cache[key]
                if time.time() - timestamp < _cache_ttl:
                    return value
                else:
                    del _memory_cache[key]
        return None
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache"""
        ttl = ttl or _cache_ttl
        
        if self.use_redis and self.redis_client:
            try:
                self.redis_client.setex(key, ttl, json.dumps(value))
                return True
            except Exception as e:
                logger.error(f"Redis set error: {e}")
                return False
        else:
            # In-memory cache
            _memory_cache[key] = (value, time.time())
            return True
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if self.use_redis and self.redis_client:
            try:
                self.redis_client.delete(key)
                return True
            except Exception as e:
                logger.error(f"Redis delete error: {e}")
                return False
        else:
            if key in _memory_cache:
                del _memory_cache[key]
                return True
        return False
    
    def clear(self) -> bool:
        """Clear all cache"""
        if self.use_redis and self.redis_client:
            try:
                self.redis_client.flushdb()
                return True
            except Exception as e:
                logger.error(f"Redis clear error: {e}")
                return False
        else:
            _memory_cache.clear()
            return True

# Global cache instance
cache = Cache()

def get_cache_key(*args, **kwargs) -> str:
    """Generate cache key from arguments"""
    key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
    return hashlib.md5(key_data.encode()).hexdigest()

