"""
Redis Cache Manager
Production-safe: works with or without Redis.
Supports Railway REDIS_URL environment variable (auto-set by Railway).
"""

import os
import redis
import json
import logging
from typing import List, Dict, Optional
from datetime import timedelta


class RedisCache:
    """Manages Redis caching for conversation history.
    Gracefully degrades when Redis is unavailable.
    """

    def __init__(self, host: str = 'localhost', port: int = 6379, db: int = 0):
        self.logger = logging.getLogger(__name__)
        self.enabled = False
        self.client = None

        try:
            # Railway sets REDIS_URL or REDIS_PRIVATE_URL automatically
            redis_url = os.getenv("REDIS_URL") or os.getenv("REDIS_PRIVATE_URL")

            if redis_url:
                self.client = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=3
                )
            else:
                self.client = redis.Redis(
                    host=host,
                    port=port,
                    db=db,
                    decode_responses=True,
                    socket_connect_timeout=3
                )

            self.client.ping()
            self.enabled = True
            self.logger.info("Redis connection established")

        except Exception as e:
            self.logger.warning(
                f"Redis unavailable -- running without cache. "
                f"App will work normally, just slower (no caching). Error: {e}"
            )
            self.client = None
            self.enabled = False

    def get_conversation_history(self, user_id: str) -> Optional[List[Dict]]:
        """Get cached conversation history"""
        if not self.enabled:
            return None

        try:
            key = f"conversation:{user_id}"
            data = self.client.get(key)

            if data:
                self.logger.info("Cache hit", extra={"user_id": user_id, "cache_key": key})
                return json.loads(data)

            self.logger.info("Cache miss", extra={"user_id": user_id, "cache_key": key})
            return None

        except Exception as e:
            self.logger.error(f"Cache read error: {e}", exc_info=True)
            return None

    def set_conversation_history(
        self,
        user_id: str,
        history: List[Dict],
        expire_seconds: int = 3600
    ) -> bool:
        """Cache conversation history with expiration"""
        if not self.enabled:
            return False

        try:
            key = f"conversation:{user_id}"
            self.client.setex(key, timedelta(seconds=expire_seconds), json.dumps(history))
            self.logger.info(
                "Cache updated",
                extra={"user_id": user_id, "cache_key": key, "ttl": expire_seconds}
            )
            return True

        except Exception as e:
            self.logger.error(f"Cache write error: {e}", exc_info=True)
            return False

    def invalidate_conversation(self, user_id: str) -> bool:
        """Clear cached conversation for user"""
        if not self.enabled:
            return False

        try:
            key = f"conversation:{user_id}"
            self.client.delete(key)
            self.logger.info("Cache invalidated", extra={"user_id": user_id, "cache_key": key})
            return True

        except Exception as e:
            self.logger.error(f"Cache delete error: {e}", exc_info=True)
            return False

    def get_stats(self) -> Dict:
        """Get Redis cache statistics"""
        if not self.enabled:
            return {
                "status": "disabled",
                "reason": "Redis unavailable at startup -- app running without cache"
            }

        try:
            info = self.client.info()
            return {
                "status": "connected",
                "connected_clients": info.get('connected_clients', 0),
                "used_memory_mb": round(info.get('used_memory', 0) / (1024 * 1024), 2),
                "total_keys": self.client.dbsize(),
                "hits": info.get('keyspace_hits', 0),
                "misses": info.get('keyspace_misses', 0),
                "hit_rate": self._calculate_hit_rate(info)
            }
        except Exception as e:
            self.logger.error(f"Stats error: {e}")
            return {"status": "error", "error": str(e)}

    def _calculate_hit_rate(self, info: Dict) -> float:
        hits = info.get('keyspace_hits', 0)
        misses = info.get('keyspace_misses', 0)
        total = hits + misses
        if total == 0:
            return 0.0
        return round((hits / total) * 100, 2)
