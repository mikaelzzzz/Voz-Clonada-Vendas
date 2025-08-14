# app/services/context_service.py
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)

class ContextService:
    """
    Serviço para gerenciar o contexto das conversas e evitar perda de contexto.
    
    Este serviço é o coração do sistema de preservação de contexto da Zaia.
    Ele resolve dois problemas principais:
    
    1. **Mensagens quebradas**: Quando o cliente envia mensagens em partes
       (ex: "Viagem" + "Vou pra Inglaterra"), o agente não perde o contexto
    
    2. **Mensagens do sistema**: Quando outros códigos enviam mensagens
       (ex: confirmação de reunião), o agente sabe que deve preservar contexto
    
    Funcionamento:
    - Marca quando mensagens do sistema são enviadas
    - Aplica delay de contexto quando necessário
    - Preserva histórico de conversas por telefone
    """
    
    # Cache para armazenar o último contexto por telefone
    _context_cache: Dict[str, dict] = {}
    
    @staticmethod
    async def mark_system_message_sent(phone: str, message_type: str = "system"):
        """
        Marca que uma mensagem do sistema foi enviada para um telefone específico.
        
        Este método é fundamental para o sistema de contexto. Sempre que uma
        mensagem automática é enviada (confirmação de reunião, lembretes, etc.),
        este método é chamado para registrar o timestamp e tipo da mensagem.
        
        Quando o cliente responder, o sistema saberá se deve aplicar delay
        de contexto para preservar a conversa.
        
        Args:
            phone: Número do telefone (normalizado)
            message_type: Tipo da mensagem:
                - "meeting_confirmation": Confirmação de reunião agendada
                - "reminder": Lembretes agendados (1 dia antes, 4h antes)
                - "test_notification": Notificações de teste
                - "system": Mensagens genéricas do sistema
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
        
        logger.info(f"📝 Contexto marcado para {phone}: {message_type}")
    
    @staticmethod
    async def should_use_context_delay(phone: str) -> bool:
        """
        Verifica se deve usar delay de contexto para um telefone específico.
        
        Este método é a inteligência do sistema de contexto. Ele decide
        quando aplicar um delay de 30 segundos antes de responder ao cliente.
        
        Lógica de decisão:
        - Se a última mensagem do sistema foi enviada há menos de 5 minutos → APLICA delay
        - Se foi enviada há mais de 5 minutos → NÃO aplica delay
        
        O delay de contexto evita que o agente da Zaia perca o contexto
        quando o cliente responde rapidamente a mensagens do sistema.
        
        Args:
            phone: Número do telefone (normalizado)
            
        Returns:
            bool: True se deve usar delay de contexto (mensagem recente do sistema)
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