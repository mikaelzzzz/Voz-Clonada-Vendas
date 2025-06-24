import logging
import aiohttp
from app.config import settings

logger = logging.getLogger(__name__)

class IntentService:
    @staticmethod
    async def detect_intent(message: str, chat_id: str = None) -> str:
        """
        Detecta a intenção da mensagem usando a API da Zaia
        
        Args:
            message: Texto da mensagem
            chat_id: ID opcional do chat para contexto
            
        Returns:
            str: Nome da intenção detectada (ex: "reenviar_boleto", "ajuda_prova_flexge", "duvida_gramatical")
        """
        try:
            # A URL específica para detecção de intenção (ajuste conforme documentação da Zaia)
            url = f"{settings.ZAIA_BASE_URL}/chat/{settings.ZAIA_AGENT_ID}/detect-intent"
            
            headers = {
                "Authorization": f"Bearer {settings.ZAIA_API_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "message": message,
                "channel": "whatsapp"
            }
            
            # Adiciona chat_id se fornecido
            if chat_id:
                payload["chat_id"] = chat_id
            
            logger.info(f"Detectando intenção para mensagem: {message}")
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        intent = data.get('intent', 'unknown')
                        logger.info(f"Intenção detectada: {intent}")
                        return intent
                    else:
                        error_text = await response.text()
                        logger.error(f"Erro ao detectar intenção: Status={response.status}, Response={error_text}")
                        return "unknown"
                        
        except Exception as e:
            logger.error(f"Erro ao detectar intenção: {str(e)}")
            return "unknown" 