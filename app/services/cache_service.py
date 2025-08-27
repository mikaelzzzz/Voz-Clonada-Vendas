# app/services/cache_service.py
import logging
import json
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import redis.asyncio as redis
from app.config.settings import settings

logger = logging.getLogger(__name__)

class CacheService:
    _redis_client: Optional[redis.Redis] = None

    # Fallback caches in-memory
    _context_cache: Dict[str, dict] = {}
    _chat_cache: Dict[str, str] = {}
    _human_override_cache: Dict[str, dict] = {}
    _message_buffer_cache: Dict[str, list] = {}
    
    _message_timers: Dict[str, asyncio.Task] = {}

    @classmethod
    async def _get_redis_client(cls) -> redis.Redis:
        if cls._redis_client is None:
            try:
                cls._redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
                await cls._redis_client.ping()
                logger.info("Cliente Redis conectado com sucesso.")
            except Exception as e:
                logger.error(f"Não foi possível conectar ao Redis: {e}. Usando fallback em memória.")
                cls._redis_client = None
        return cls._redis_client

    @staticmethod
    async def set_context_data(phone: str, context_data: dict):
        if settings.is_redis_enabled:
            client = await CacheService._get_redis_client()
            if client:
                await client.set(f"context:{phone}", json.dumps(context_data), ex=timedelta(hours=24))
        else:
            CacheService._context_cache[phone] = context_data
        logger.info(f"💾 Contexto armazenado para {phone}")

    @staticmethod
    async def get_context_data(phone: str) -> Optional[dict]:
        if settings.is_redis_enabled:
            client = await CacheService._get_redis_client()
            if client:
                data = await client.get(f"context:{phone}")
                return json.loads(data) if data else None
        return CacheService._context_cache.get(phone)

    @staticmethod
    async def clear_context_data(phone: str):
        if settings.is_redis_enabled:
            client = await CacheService._get_redis_client()
            if client:
                await client.delete(f"context:{phone}")
        else:
            CacheService._context_cache.pop(phone, None)
        logger.info(f"🧹 Contexto limpo para {phone}")

    @staticmethod
    async def set_chat_id(phone: str, chat_id: str):
        if settings.is_redis_enabled:
            client = await CacheService._get_redis_client()
            if client:
                await client.set(f"chat_id:{phone}", chat_id, ex=timedelta(days=7))
        else:
            CacheService._chat_cache[phone] = chat_id
        logger.info(f"🆔 Chat ID armazenado para {phone}: {chat_id}")

    @staticmethod
    async def get_chat_id(phone: str) -> Optional[str]:
        if settings.is_redis_enabled:
            client = await CacheService._get_redis_client()
            if client:
                return await client.get(f"chat_id:{phone}")
        return CacheService._chat_cache.get(phone)

    @staticmethod
    async def clear_chat_id(phone: str):
        if settings.is_redis_enabled:
            client = await CacheService._get_redis_client()
            if client:
                await client.delete(f"chat_id:{phone}")
        else:
            CacheService._chat_cache.pop(phone, None)
        logger.info(f"🆔 Chat ID limpo para {phone}")

    @staticmethod
    async def clear_all_chats():
        if settings.is_redis_enabled:
            client = await CacheService._get_redis_client()
            if client:
                async for key in client.scan_iter("chat_id:*"):
                    await client.delete(key)
        else:
            CacheService._chat_cache.clear()
        logger.info("🧹 Todos os chat IDs foram limpos")

    @staticmethod
    async def get_all_context_data() -> Dict[str, dict]:
        if settings.is_redis_enabled:
            client = await CacheService._get_redis_client()
            if client:
                contexts = {}
                async for key in client.scan_iter("context:*"):
                    phone = key.split(":")[-1]
                    data = await client.get(key)
                    if data:
                        contexts[phone] = json.loads(data)
                return contexts
        return CacheService._context_cache.copy()

    @staticmethod
    async def get_all_chat_ids() -> Dict[str, str]:
        if settings.is_redis_enabled:
            client = await CacheService._get_redis_client()
            if client:
                chats = {}
                async for key in client.scan_iter("chat_id:*"):
                    phone = key.split(":")[-1]
                    chat_id = await client.get(key)
                    if chat_id:
                        chats[phone] = chat_id
                return chats
        return CacheService._chat_cache.copy()

    @staticmethod
    async def set_human_override(phone: str, active: bool = True):
        if settings.is_redis_enabled:
            client = await CacheService._get_redis_client()
            if client:
                key = f"human_override:{phone}"
                if active:
                    data = {"active": True, "since": datetime.utcnow().isoformat()}
                    await client.set(key, json.dumps(data), ex=timedelta(hours=24))
                    logger.info(f"🛑 Override humano ATIVADO para {phone}")
                else:
                    await client.delete(key)
                    logger.info(f"▶️ Override humano DESATIVADO para {phone}")
        else:
            if active:
                CacheService._human_override_cache[phone] = {
                    "active": True,
                    "since": datetime.utcnow().isoformat()
                }
                logger.info(f"🛑 Override humano ATIVADO para {phone}")
            else:
                CacheService._human_override_cache.pop(phone, None)
                logger.info(f"▶️ Override humano DESATIVADO para {phone}")

    @staticmethod
    async def is_human_override_active(phone: str) -> bool:
        if settings.is_redis_enabled:
            client = await CacheService._get_redis_client()
            if client:
                key = f"human_override:{phone}"
                data = await client.get(key)
                if data:
                    return json.loads(data).get("active", False)
                return False
        
        data = CacheService._human_override_cache.get(phone)
        return bool(data and data.get("active"))

    @staticmethod
    async def clear_human_override(phone: str):
        if settings.is_redis_enabled:
            client = await CacheService._get_redis_client()
            if client:
                await client.delete(f"human_override:{phone}")
        else:
            CacheService._human_override_cache.pop(phone, None)
        logger.info(f"▶️ Override humano limpo para {phone}")

    @classmethod
    async def add_to_buffer(cls, phone: str, message: str) -> int:
        """Adiciona uma mensagem ao buffer de um telefone e retorna o novo tamanho do buffer."""
        client = await cls._get_redis_client() if settings.is_redis_enabled else None
        if client:
            key = f"buffer:{phone}"
            await client.rpush(key, message)
            await client.expire(key, 30)  # Garante que o buffer expire
            return await client.llen(key)
        else:
            if phone not in cls._message_buffer_cache:
                cls._message_buffer_cache[phone] = []
            cls._message_buffer_cache[phone].append(message)
            return len(cls._message_buffer_cache[phone])

    @classmethod
    async def get_and_clear_buffer(cls, phone: str) -> str:
        """Obtém todas as mensagens do buffer, as une e limpa o buffer."""
        client = await cls._get_redis_client() if settings.is_redis_enabled else None
        if client:
            key = f"buffer:{phone}"
            messages = await client.lrange(key, 0, -1)
            await client.delete(key)
            return " ".join(messages)
        else:
            messages = cls._message_buffer_cache.pop(phone, [])
            return " ".join(messages)