import redis
import logging
import json
from typing import Optional
from app.config.settings import Settings

logger = logging.getLogger(__name__)

class CacheService:
    _redis_client = None
    
    @classmethod
    def get_client(cls):
        """Obtém o cliente Redis (singleton)"""
        settings = Settings()
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
    async def set_chat_id(cls, phone: str, chat_id: int, ttl: int = 172800):
        """Armazena o chat ID no cache para um telefone (TTL padrão: 48h)"""
        try:
            client = cls.get_client()
            if client:
                client.setex(f"chat:{phone}", ttl, str(chat_id))
                logger.info(f"💾 Chat ID salvo no Redis para {phone}: {chat_id} (TTL: {ttl}s = {ttl//3600}h)")
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
            
    # --- Lógica de Hibernação ---
    
    @classmethod
    async def activate_hibernation(cls, phone: str, grace_minutes: int = 15):
        """Ativa o modo de hibernação por 12h e cria uma janela de segurança (grace)."""
        try:
            client = cls.get_client()
            if client:
                # Flag principal de hibernação por 12 horas
                client.setex(f"hibernate:{phone}", 12 * 3600, "true")
                # Janela de segurança (grace) para resistir a reinícios/corridas
                client.setex(f"hibernate_grace:{phone}", grace_minutes * 60, "true")
                logger.info(f"🤖 Hibernação ativada para {phone} (12h, grace {grace_minutes} min).")
        except Exception as e:
            logger.error(f"❌ Erro ao ativar hibernação para {phone}: {e}")

    @classmethod
    async def is_hibernating(cls, phone: str) -> bool:
        """Verifica se um telefone está em modo de hibernação."""
        try:
            client = cls.get_client()
            if client:
                status = client.get(f"hibernate:{phone}")
                if status:
                    logger.info(f"🤖 Verificação de hibernação para {phone}: ATIVA")
                    return True
            logger.info(f"🤖 Verificação de hibernação para {phone}: INATIVA")
            return False
        except Exception as e:
            logger.error(f"❌ Erro ao verificar hibernação para {phone}: {e}")
            return False  # Em caso de erro, não hiberna para não perder o lead.

    @classmethod
    async def is_recently_hibernated(cls, phone: str) -> bool:
        """Verifica se está na janela de segurança (grace)."""
        try:
            client = cls.get_client()
            if client:
                in_grace = client.exists(f"hibernate_grace:{phone}") == 1
                if in_grace:
                    logger.info(f"🤖 Verificação de grace para {phone}: ATIVA")
                return in_grace
            return False
        except Exception as e:
            logger.error(f"❌ Erro ao verificar grace para {phone}: {e}")
            return False

    @classmethod
    async def deactivate_hibernation(cls, phone: str):
        """Desativa o modo de hibernação manualmente para um telefone (remove grace também)."""
        try:
            client = cls.get_client()
            if client:
                client.delete(f"hibernate:{phone}", f"hibernate_grace:{phone}")
                logger.info(f"🤖 Hibernação desativada para {phone}.")
        except Exception as e:
            logger.error(f"❌ Erro ao desativar hibernação para {phone}: {e}")
