"""
Redis caching service for Smart Farming Assistant
"""
import os
import json
import logging
import redis
from typing import Optional, Any
from functools import wraps

logger = logging.getLogger(__name__)

class CacheService:
    """Redis-based caching service with fallback to memory cache"""
    
    def __init__(self):
        self.redis_client = None
        self.memory_cache = {}
        self.use_redis = False
        
        # Try to connect to Redis
        try:
            redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            # Test connection
            self.redis_client.ping()
            self.use_redis = True
            logger.info("Redis cache connected successfully")
        except Exception as e:
            logger.warning(f"Redis not available, using memory cache: {e}")
            self.use_redis = False
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            if self.use_redis and self.redis_client:
                value = self.redis_client.get(key)
                if value:
                    return json.loads(value)
            else:
                return self.memory_cache.get(key)
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache with TTL"""
        try:
            serialized_value = json.dumps(value, default=str)
            
            if self.use_redis and self.redis_client:
                return self.redis_client.setex(key, ttl, serialized_value)
            else:
                self.memory_cache[key] = value
                return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False

# Global cache instance
cache_service = CacheService()

def cached(ttl: int = 3600, key_prefix: str = ""):
    """Decorator for caching function results"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            import hashlib
            key_str = str(args) + str(sorted(kwargs.items()))
            cache_key_value = f"{key_prefix}{func.__name__}_{hashlib.md5(key_str.encode()).hexdigest()}"
            
            # Try to get from cache
            cached_result = cache_service.get(cache_key_value)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_service.set(cache_key_value, result, ttl)
            logger.debug(f"Cached result for {func.__name__}")
            
            return result
        return wrapper
    return decorator
