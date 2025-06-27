import redis
import logging
import json
from typing import Optional
from app.config.settings import settings

logger = logging.getLogger(__name__)

class CacheService:
    _redis_client = None
    
    @classmethod
    def get_client(cls):
        """Obtém o cliente Redis (singleton)"""
        if cls._redis_client is None and settings.REDIS_ENABLED:
            try:
                cls._redis_client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                # Teste de conexão
                cls._redis_client.ping()
                logger.info("✅ Redis conectado com sucesso")
            except Exception as e:
                logger.warning(f"⚠️ Redis não disponível, usando cache local: {str(e)}")
                cls._redis_client = None
        return cls._redis_client
    
    @classmethod
    async def get_chat_id(cls, phone: str) -> Optional[int]:
        """Obtém o chat ID do cache para um telefone"""
        try:
            client = cls.get_client()
            if client:
                chat_id = client.get(f"chat:{phone}")
                if chat_id:
                    logger.info(f"🔄 Chat ID do Redis para {phone}: {chat_id}")
                    return int(chat_id)
            return None
        except Exception as e:
            logger.warning(f"⚠️ Erro ao ler cache Redis para {phone}: {str(e)}")
            return None
    
    @classmethod
    async def set_chat_id(cls, phone: str, chat_id: int, ttl: int = 43200):
        """Armazena o chat ID no cache para um telefone (TTL padrão: 12h)"""
        try:
            client = cls.get_client()
            if client:
                client.setex(f"chat:{phone}", ttl, str(chat_id))
                logger.info(f"💾 Chat ID salvo no Redis para {phone}: {chat_id}")
            else:
                logger.debug(f"📝 Redis não disponível, usando cache local para {phone}")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao salvar cache Redis para {phone}: {str(e)}")
    
    @classmethod
    async def clear_chat_id(cls, phone: str):
        """Remove o chat ID do cache para um telefone"""
        try:
            client = cls.get_client()
            if client:
                client.delete(f"chat:{phone}")
                logger.info(f"🗑️ Cache Redis limpo para {phone}")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao limpar cache Redis para {phone}: {str(e)}")
    
    @classmethod
    async def clear_all_chats(cls):
        """Limpa todos os chats do cache"""
        try:
            client = cls.get_client()
            if client:
                keys = client.keys("chat:*")
                if keys:
                    client.delete(*keys)
                    logger.info(f"🗑️ {len(keys)} chats removidos do cache Redis")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao limpar cache Redis completo: {str(e)}") 