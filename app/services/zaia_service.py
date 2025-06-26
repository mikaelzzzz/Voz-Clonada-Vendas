import logging
import aiohttp
from app.config import settings
from app.services.intent_service import IntentService

logger = logging.getLogger(__name__)

class ZaiaService:
    def __init__(self):
        self.intent_service = IntentService()

    @staticmethod
    async def get_or_create_chat(phone: str):
        """
        Cria um chat na Zaia usando externalId (telefone) ou recupera se já existir.
        Retorna o chat_id.
        """
        base_url = settings.ZAIA_BASE_URL.rstrip("/")
        agent_id = settings.ZAIA_AGENT_ID
        api_key = settings.ZAIA_API_KEY
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        # 1. Tenta criar o chat
        payload = {
            "agentId": agent_id,
            "externalId": phone
        }
        create_url = f"{base_url}/v1.1/api/external-generative-chat/create"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(create_url, headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        logger.info(f"Chat criado na Zaia: {data}")
                        return data["id"]
                    elif resp.status == 409:
                        # Chat já existe, buscar pelo externalId
                        logger.info(f"Chat já existe para {phone}, buscando...")
                        retrieve_url = f"{base_url}/v1.1/api/external-generative-chat/retrieve-multiple?agentIds={agent_id}&externalIds={phone}"
                        async with session.get(retrieve_url, headers=headers) as get_resp:
                            get_data = await get_resp.json()
                            chats = get_data.get("externalGenerativeChats", [])
                            if chats:
                                logger.info(f"Chat recuperado: {chats[0]}")
                                return chats[0]["id"]
                            else:
                                logger.error(f"Nenhum chat encontrado para {phone}")
                                raise Exception("Nenhum chat encontrado para o telefone informado.")
                    else:
                        error_text = await resp.text()
                        logger.error(f"Erro ao criar chat: Status={resp.status}, Response={error_text}")
                        raise Exception(f"Erro ao criar chat: {error_text}")
            except Exception as e:
                logger.error(f"Erro em get_or_create_chat: {str(e)}")
                raise

    @staticmethod
    async def send_message(message: dict):
        """
        Envia mensagem para a Zaia e retorna a resposta, garantindo que o chat existe.
        
        Args:
            message: Dicionário contendo:
                - text.body: Texto da mensagem (para mensagens de texto)
                - transcript: Texto transcrito (para mensagens de áudio)
                - phone: Número do telefone do usuário
        """
        base_url = settings.ZAIA_BASE_URL.rstrip("/")
        agent_id = settings.ZAIA_AGENT_ID
        api_key = settings.ZAIA_API_KEY
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Extrai o texto da mensagem
        message_text = message.get('transcript') or message.get('text', {}).get('body')
        if not message_text:
            raise Exception("Texto da mensagem não encontrado")
            
        phone = message.get('phone')
        if not phone:
            raise Exception("Telefone não informado na mensagem para Zaia.")
            
        # 1. Garante que o chat existe
        chat_id = await ZaiaService.get_or_create_chat(phone)
        
        # 2. Detecta a intenção
        intent_service = IntentService()
        intent = await intent_service.detect_intent(message_text, chat_id)
        
        # 3. Monta o payload
        payload = {
            "agentId": agent_id,
            "externalGenerativeChatId": chat_id,
            "prompt": message_text,
            "custom": {"whatsapp": phone},
            "intent": intent
        }
        
        url_message = f"{base_url}/v1.1/api/external-generative-message/create"
        async with aiohttp.ClientSession() as session:
            try:
                logger.info(f"Enviando mensagem para Zaia. URL: {url_message}")
                logger.info(f"Payload: {payload}")
                async with session.post(url_message, headers=headers, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Erro ao enviar mensagem: Status={response.status}, Response={error_text}")
                        raise Exception(f"Erro ao enviar mensagem: {error_text}")
                        
                    response_json = await response.json()
                    logger.info(f"Resposta da Zaia: {response_json}")
                    response_json['detected_intent'] = intent
                    return response_json
            except Exception as e:
                logger.error(f"Erro ao enviar mensagem para Zaia: {str(e)}")
                raise 