"""
Redis Cache Manager - Production Safe Version
Handles Railway's REDIS_URL format with graceful fallback
"""

import redis
import json
import logging
import os
from typing import List, Dict, Optional
from datetime import timedelta


class RedisCache:
    """Manages Redis caching with graceful fallback when Redis is unavailable"""

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

    def get_conversation_history(self, phone_number: str, limit: int = 10) -> List[Dict]:
        if not self.enabled:
            return []
        try:
            key = f"conv:{phone_number}"
            data = self.client.get(key)
            if data:
                history = json.loads(data)
                return history[-limit:]
            return []
        except Exception as e:
            self.logger.warning(f"Redis get error: {e}")
            return []

    def set_conversation_history(self, phone_number: str, history: List[Dict], ttl_hours: int = 24):
        if not self.enabled:
            return
        try:
            key = f"conv:{phone_number}"
            self.client.setex(
                key,
                timedelta(hours=ttl_hours),
                json.dumps(history)
            )
        except Exception as e:
            self.logger.warning(f"Redis set error: {e}")

    def invalidate_conversation(self, phone_number: str):
        if not self.enabled:
            return
        try:
            key = f"conv:{phone_number}"
            self.client.delete(key)
        except Exception as e:
            self.logger.warning(f"Redis delete error: {e}")

    def get_stats(self) -> Dict:
        if not self.enabled:
            return {"status": "disabled", "reason": "Redis unavailable, app running without cache"}
        try:
            info = self.client.info()
            return {
                "status": "connected",
                "used_memory": info.get("used_memory_human", "N/A"),
                "connected_clients": info.get("connected_clients", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
