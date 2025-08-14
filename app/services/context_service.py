import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)

class ContextService:
    """
    Serviço para gerenciar o contexto das conversas e evitar perda de contexto
    quando mensagens são enviadas por outros sistemas.
    """
    
    # Cache para armazenar o último contexto por telefone
    _context_cache: Dict[str, dict] = {}
    
    @staticmethod
    async def mark_system_message_sent(phone: str, message_type: str = "system"):
        """
        Marca que uma mensagem do sistema foi enviada para um telefone específico.
        Isso ajuda a evitar perda de contexto no agente da Zaia.
        
        Args:
            phone: Número do telefone
            message_type: Tipo da mensagem (ex: "system", "meeting_confirmation", etc.)
        """
        timestamp = datetime.now()
        
        context_data = {
            "last_system_message": timestamp.isoformat(),
            "message_type": message_type,
            "phone": phone
        }
        
        # Armazena no cache local
        ContextService._context_cache[phone] = context_data
        
        # Armazena no cache persistente
        await CacheService.set_context_data(phone, context_data)
        
        logger.info(f"📝 Mensagem do sistema marcada para {phone}: {message_type}")
    
    @staticmethod
    async def should_use_context_delay(phone: str) -> bool:
        """
        Verifica se deve usar delay de contexto para um telefone específico.
        
        Args:
            phone: Número do telefone
            
        Returns:
            bool: True se deve usar delay de contexto
        """
        # Busca dados do cache local
        context_data = ContextService._context_cache.get(phone)
        
        if not context_data:
            # Tenta buscar do cache persistente
            context_data = await CacheService.get_context_data(phone)
            if context_data:
                ContextService._context_cache[phone] = context_data
        
        if not context_data:
            return False
        
        # Verifica se a última mensagem do sistema foi enviada há menos de 5 minutos
        last_message_time = datetime.fromisoformat(context_data["last_system_message"])
        time_diff = datetime.now() - last_message_time
        
        # Se foi enviada há menos de 5 minutos, usa delay de contexto
        should_delay = time_diff < timedelta(minutes=5)
        
        if should_delay:
            logger.info(f"⏰ Usando delay de contexto para {phone} (última mensagem do sistema há {time_diff.total_seconds():.0f}s)")
        else:
            logger.info(f"✅ Sem delay de contexto para {phone} (última mensagem do sistema há {time_diff.total_seconds():.0f}s)")
        
        return should_delay
    
    @staticmethod
    async def clear_context(phone: str):
        """
        Limpa o contexto para um telefone específico.
        
        Args:
            phone: Número do telefone
        """
        ContextService._context_cache.pop(phone, None)
        await CacheService.clear_context_data(phone)
        logger.info(f"🧹 Contexto limpo para {phone}")
    
    @staticmethod
    async def get_context_info(phone: str) -> Optional[dict]:
        """
        Obtém informações do contexto para um telefone específico.
        
        Args:
            phone: Número do telefone
            
        Returns:
            dict: Informações do contexto ou None se não existir
        """
        context_data = ContextService._context_cache.get(phone)
        
        if not context_data:
            context_data = await CacheService.get_context_data(phone)
            if context_data:
                ContextService._context_cache[phone] = context_data
        
        return context_data
