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
        logger.info(f"Iniciando get_or_create_chat para telefone: {phone}")
        
        base_url = settings.ZAIA_BASE_URL.rstrip("/")
        agent_id = settings.ZAIA_AGENT_ID
        api_key = settings.ZAIA_API_KEY
        
        # Verificar se as configurações estão definidas
        if not api_key:
            raise Exception("ZAIA_API_KEY não está configurada")
        if not agent_id:
            raise Exception("ZAIA_AGENT_ID não está configurada")
        if not base_url:
            raise Exception("ZAIA_BASE_URL não está configurada")
            
        logger.info(f"Configurações Zaia - Base URL: {base_url}, Agent ID: {agent_id}")
        
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
        
        logger.info(f"Tentando criar chat - URL: {create_url}")
        logger.info(f"Payload: {payload}")
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(create_url, headers=headers, json=payload) as resp:
                    logger.info(f"Resposta do create chat - Status: {resp.status}")
                    
                    if resp.status == 200:
                        data = await resp.json()
                        logger.info(f"Chat criado na Zaia: {data}")
                        return data["id"]
                    elif resp.status == 409:
                        # Chat já existe, buscar pelo externalId
                        logger.info(f"Chat já existe para {phone}, buscando...")
                        retrieve_url = f"{base_url}/v1.1/api/external-generative-chat/retrieve-multiple?agentIds={agent_id}&externalIds={phone}"
                        logger.info(f"URL de busca: {retrieve_url}")
                        
                        async with session.get(retrieve_url, headers=headers) as get_resp:
                            logger.info(f"Resposta da busca - Status: {get_resp.status}")
                            get_data = await get_resp.json()
                            logger.info(f"Dados da busca: {get_data}")
                            
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
                        raise Exception(f"Erro ao criar chat: Status {resp.status} - {error_text}")
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
        logger.info(f"Iniciando send_message com dados: {message}")
        
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
            logger.error("Texto da mensagem não encontrado")
            raise Exception("Texto da mensagem não encontrado")
            
        phone = message.get('phone')
        if not phone:
            logger.error("Telefone não informado na mensagem")
            raise Exception("Telefone não informado na mensagem para Zaia.")
            
        logger.info(f"Processando mensagem: '{message_text}' do telefone: {phone}")
        
        try:
            # 1. Garante que o chat existe
            logger.info("Obtendo ou criando chat...")
            chat_id = await ZaiaService.get_or_create_chat(phone)
            logger.info(f"Chat ID obtido: {chat_id}")
            
            # 2. Detecta a intenção
            logger.info("Detectando intenção...")
            intent_service = IntentService()
            intent = await intent_service.detect_intent(message_text, chat_id)
            logger.info(f"Intenção detectada: {intent}")
            
            # 3. Monta o payload
            payload = {
                "agentId": agent_id,
                "externalGenerativeChatId": chat_id,
                "prompt": message_text,
                "custom": {"whatsapp": phone},
                "intent": intent
            }
            
            url_message = f"{base_url}/v1.1/api/external-generative-message/create"
            logger.info(f"Enviando mensagem para Zaia - URL: {url_message}")
            logger.info(f"Payload completo: {payload}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url_message, headers=headers, json=payload) as response:
                    logger.info(f"Resposta da Zaia - Status: {response.status}")
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Erro ao enviar mensagem: Status={response.status}, Response={error_text}")
                        raise Exception(f"Erro ao enviar mensagem: Status {response.status} - {error_text}")
                        
                    response_json = await response.json()
                    logger.info(f"Resposta da Zaia (JSON): {response_json}")
                    response_json['detected_intent'] = intent
                    return response_json
                    
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem para Zaia: {str(e)}")
            raise 