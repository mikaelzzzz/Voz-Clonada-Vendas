import logging
import json
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CacheService:
    """
    Serviço de cache para armazenar dados de contexto e chat IDs.
    Por enquanto usa cache em memória, mas pode ser expandido para Redis.
    """
    
    # Cache em memória para dados de contexto
    _context_cache: Dict[str, dict] = {}
    # Cache em memória para chat IDs
    _chat_cache: Dict[str, str] = {}
    
    @staticmethod
    async def set_context_data(phone: str, context_data: dict):
        """
        Armazena dados de contexto para um telefone específico.
        
        Args:
            phone: Número do telefone
            context_data: Dados do contexto
        """
        CacheService._context_cache[phone] = context_data
        logger.info(f"💾 Contexto armazenado para {phone}")
    
    @staticmethod
    async def get_context_data(phone: str) -> Optional[dict]:
        """
        Obtém dados de contexto para um telefone específico.
        
        Args:
            phone: Número do telefone
            
        Returns:
            dict: Dados do contexto ou None se não existir
        """
        return CacheService._context_cache.get(phone)
    
    @staticmethod
    async def clear_context_data(phone: str):
        """
        Limpa dados de contexto para um telefone específico.
        
        Args:
            phone: Número do telefone
        """
        CacheService._context_cache.pop(phone, None)
        logger.info(f"🧹 Contexto limpo para {phone}")
    
    @staticmethod
    async def set_chat_id(phone: str, chat_id: str):
        """
        Armazena o chat ID para um telefone específico.
        
        Args:
            phone: Número do telefone
            chat_id: ID do chat
        """
        CacheService._chat_cache[phone] = chat_id
        logger.info(f"💾 Chat ID armazenado para {phone}: {chat_id}")
    
    @staticmethod
    async def get_chat_id(phone: str) -> Optional[str]:
        """
        Obtém o chat ID para um telefone específico.
        
        Args:
            phone: Número do telefone
            
        Returns:
            str: ID do chat ou None se não existir
        """
        return CacheService._chat_cache.get(phone)
    
    @staticmethod
    async def clear_chat_id(phone: str):
        """
        Limpa o chat ID para um telefone específico.
        
        Args:
            phone: Número do telefone
        """
        CacheService._chat_cache.pop(phone, None)
        logger.info(f"🧹 Chat ID limpo para {phone}")
    
    @staticmethod
    async def clear_all_chats():
        """
        Limpa todos os chat IDs armazenados.
        """
        CacheService._chat_cache.clear()
        logger.info("🧹 Todos os chat IDs foram limpos")
    
    @staticmethod
    async def get_all_context_data() -> Dict[str, dict]:
        """
        Obtém todos os dados de contexto armazenados.
        
        Returns:
            Dict[str, dict]: Todos os dados de contexto
        """
        return CacheService._context_cache.copy()
    
    @staticmethod
    async def get_all_chat_ids() -> Dict[str, str]:
        """
        Obtém todos os chat IDs armazenados.
        
        Returns:
            Dict[str, str]: Todos os chat IDs
        """
        return CacheService._chat_cache.copy()
