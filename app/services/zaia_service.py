import logging
import aiohttp
from app.config.settings import Settings
import requests

logger = logging.getLogger(__name__)

class ZaiaService:
    def __init__(self):
        pass

    @staticmethod
    async def send_message(message: dict, metadata: dict = None):
        """
        Envia mensagem para a Zaia.
        O contexto do CRM é injetado diretamente no prompt.
        """
        logger.info(f"=== ENVIANDO MENSAGEM PARA ZAIA ===")
        logger.info(f"📨 Dados: {message} | Metadados: {metadata}")
        
        settings = Settings()
        base_url = settings.ZAIA_BASE_URL.rstrip("/")
        agent_id = settings.ZAIA_AGENT_ID
        api_key = settings.ZAIA_API_KEY
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        message_text = message.get('text')
        if not message_text:
            raise Exception("Texto da mensagem (prompt) não encontrado")
            
        phone = message.get('phone')
        if not phone:
            raise Exception("Telefone não informado")
            
        logger.info(f"📱 Mensagem: '{message_text}' | Telefone: {phone}")
        
        try:
            custom_data = {"whatsapp": phone}
            if metadata:
                custom_data.update(metadata)

            payload = {
                "agentId": int(agent_id),
                "externalGenerativeChatExternalId": phone,
                "prompt": message_text,
                "streaming": False,
                "asMarkdown": False,
                "custom": custom_data
            }
            
            url_message = f"{base_url}/v1.1/api/external-generative-message/create"
            logger.info(f"📤 Enviando mensagem para Zaia...")
            logger.info(f"📤 Payload completo: {payload}")

            async with aiohttp.ClientSession() as session:
                async with session.post(url_message, headers=headers, json=payload) as response:
                    logger.info(f"📥 Status: {response.status}")
                    
                    if response.status == 200:
                        response_json = await response.json()
                        chat_id = response_json.get('externalGenerativeChatId')
                        ai_response = response_json.get('text', 'Erro ao obter resposta')
                        
                        logger.info(f"✅ Chat ID usado pela Zaia: {chat_id}")
                        logger.info(f"🤖 Resposta da IA: {ai_response[:100]}...")
                        
                        return response_json
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Erro na API Zaia: {response.status} - {error_text}")
                        logger.error(f"📤 Payload enviado: {payload}")
                        raise Exception(f"Erro ao enviar mensagem: {response.status} - {error_text}")
                        
        except Exception as e:
            logger.error(f"❌ Erro ao processar mensagem para {phone}: {str(e)}")
            raise 