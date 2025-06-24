import logging
import aiohttp
from app.config import settings
from app.services.intent_service import IntentService

logger = logging.getLogger(__name__)

class ZaiaService:
    def __init__(self):
        self.intent_service = IntentService()

    @staticmethod
    async def send_message(message: dict):
        """
        Envia mensagem para a Zaia e retorna a resposta
        """
        url = f"{settings.ZAIA_BASE_URL}/chat/{settings.ZAIA_AGENT_ID}/message"
        headers = {
            "Authorization": f"Bearer {settings.ZAIA_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Extrai o texto da mensagem
        message_text = message['text']['body'] if 'text' in message else message['transcript']
        
        # Detecta a intenção
        intent = await IntentService.detect_intent(message_text, message.get('chat_id'))
        
        payload = {
            "message": message_text,
            "channel": "whatsapp",
            "intent": intent  # Inclui a intenção detectada na requisição
        }
        
        # Adiciona chat_id se disponível
        if 'chat_id' in message:
            payload['chat_id'] = message['chat_id']
        
        async with aiohttp.ClientSession() as session:
            try:
                logger.info(f"Enviando mensagem para Zaia. URL: {url}")
                logger.info(f"Payload: {payload}")
                async with session.post(url, headers=headers, json=payload) as response:
                    response_json = await response.json()
                    logger.info(f"Resposta da Zaia: {response_json}")
                    
                    # Adiciona a intenção detectada à resposta
                    response_json['detected_intent'] = intent
                    
                    return response_json
            except Exception as e:
                logger.error(f"Erro ao enviar mensagem para Zaia: {str(e)}")
                raise 