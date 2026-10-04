import json
import redis.asyncio as redis
from typing import Optional, Any, List, Dict
from app.config import settings

class CacheService:
    def __init__(self):
        self.redis = redis.from_url(settings.REDIS_URL, decode_responses=False)
        self.str_redis = redis.from_url(settings.REDIS_URL, decode_responses=True)

    async def get(self, key: str) -> Optional[bytes]:
        return await self.redis.get(key)

    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        await self.redis.set(key, value, ex=ttl_seconds)

    async def delete(self, key: str) -> None:
        await self.redis.delete(key)

    async def get_embedding(self, doc_id: str, chunk_seq: int, version: str) -> Optional[List[float]]:
        key = f"emb:{doc_id}:{chunk_seq}:{version}"
        data = await self.str_redis.get(key)
        if data:
            return json.loads(data)
        return None

    async def set_embedding(self, doc_id: str, chunk_seq: int, version: str, embedding: List[float], ttl: int = 3600):
        key = f"emb:{doc_id}:{chunk_seq}:{version}"
        await self.str_redis.set(key, json.dumps(embedding), ex=ttl)

    async def get_retrieval(self, query_hash: str, doc_version: str) -> Optional[List[Dict]]:
        key = f"ret:{query_hash}:{doc_version}"
        data = await self.str_redis.get(key)
        if data:
            return json.loads(data)
        return None

    async def set_retrieval(self, query_hash: str, doc_version: str, results: List[Dict], ttl: int = 1800):
        key = f"ret:{query_hash}:{doc_version}"
        await self.str_redis.set(key, json.dumps(results), ex=ttl)

    async def get_response(self, query_hash: str) -> Optional[str]:
        key = f"resp:{query_hash}"
        return await self.str_redis.get(key)

    async def set_response(self, query_hash: str, response: str, ttl: int = 3600):
        key = f"resp:{query_hash}"
        await self.str_redis.set(key, response, ex=ttl)

    async def invalidate_by_version(self, doc_id: str, old_version: str) -> None:
        pass
