import logging
import aiohttp
from app.config import settings

logger = logging.getLogger(__name__)

class ZaiaService:
    def __init__(self):
        pass  # Removido IntentService - Zaia detecta intenções automaticamente

    @staticmethod
    async def get_or_create_chat(phone: str):
        """
        Cria um chat na Zaia usando externalId (telefone) ou recupera se já existir.
        Cada número de telefone terá seu próprio chat individual.
        Retorna o chat_id.
        """
        logger.info(f"=== INICIANDO get_or_create_chat para telefone: {phone} ===")
        
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
        
        async with aiohttp.ClientSession() as session:
            try:
                # 1. Buscar chat existente usando endpoint múltiplo (CORRETO)
                retrieve_url = f"{base_url}/v1.1/api/external-generative-chat/retrieve-multiple?agentIds={agent_id}&externalIds={phone}"
                logger.info(f"🔍 BUSCANDO chat existente - URL: {retrieve_url}")
                
                async with session.get(retrieve_url, headers=headers) as get_resp:
                    logger.info(f"📋 Resposta da busca - Status: {get_resp.status}")
                    
                    if get_resp.status == 200:
                        get_data = await get_resp.json()
                        logger.info(f"📋 Dados da busca: {get_data}")
                        
                        chats = get_data.get("externalGenerativeChats", [])
                        if chats:
                            # Filtrar pelo phoneNumber correto
                            matching_chat = None
                            for chat in chats:
                                chat_phone = chat.get('phoneNumber')
                                chat_channel = chat.get('channel')
                                chat_status = chat.get('status')
                                
                                logger.info(f"🔍 Analisando chat ID {chat['id']}: phone={chat_phone}, channel={chat_channel}, status={chat_status}")
                                
                                # Busca chat ativo do WhatsApp com o número correto
                                if (chat_phone == phone and 
                                    chat_channel == 'whatsapp' and 
                                    chat_status == 'active'):
                                    matching_chat = chat
                                    break
                            
                            if matching_chat:
                                existing_chat_id = matching_chat["id"]
                                logger.info(f"✅ CHAT EXISTENTE ENCONTRADO para {phone} - Chat ID: {existing_chat_id}")
                                logger.info(f"✅ Chat details: {matching_chat}")
                                return existing_chat_id
                            else:
                                logger.info(f"❌ Nenhum chat ativo do WhatsApp encontrado para {phone}")
                        else:
                            logger.info(f"❌ Nenhum chat existente encontrado para {phone}")
                    else:
                        logger.warning(f"⚠️ Erro na busca de chat existente: Status {get_resp.status}")
                
                # 2. Se não encontrou, criar novo chat
                payload = {
                    "agentId": int(agent_id),
                    "externalId": phone,
                    "channel": "whatsapp",
                    "phoneNumber": phone
                }
                create_url = f"{base_url}/v1.1/api/external-generative-chat/create"
                
                logger.info(f"🆕 CRIANDO NOVO CHAT - URL: {create_url}")
                logger.info(f"🆕 Payload: {payload}")
                
                async with session.post(create_url, headers=headers, json=payload) as resp:
                    logger.info(f"🆕 Resposta da criação - Status: {resp.status}")
                    
                    if resp.status == 200:
                        data = await resp.json()
                        new_chat_id = data["id"]
                        logger.info(f"✅ NOVO CHAT CRIADO para {phone} - Chat ID: {new_chat_id}")
                        logger.info(f"✅ Dados completos do novo chat: {data}")
                        return new_chat_id
                    elif resp.status == 409:
                        # Chat foi criado por race condition, buscar novamente
                        logger.info(f"🔄 Race condition detectado, buscando chat novamente...")
                        
                        async with session.get(retrieve_url, headers=headers) as get_resp2:
                            if get_resp2.status == 200:
                                get_data2 = await get_resp2.json()
                                logger.info(f"🔄 Dados da busca pós-race condition: {get_data2}")
                                
                                chats2 = get_data2.get("externalGenerativeChats", [])
                                for chat in chats2:
                                    if (chat.get('phoneNumber') == phone and 
                                        chat.get('channel') == 'whatsapp' and 
                                        chat.get('status') == 'active'):
                                        race_chat_id = chat["id"]
                                        logger.info(f"✅ CHAT RECUPERADO após race condition para {phone} - Chat ID: {race_chat_id}")
                                        return race_chat_id
                        
                        logger.error(f"❌ Falha ao recuperar chat após race condition para {phone}")
                        raise Exception("Falha ao recuperar chat após conflito de criação")
                    else:
                        error_text = await resp.text()
                        logger.error(f"❌ Erro ao criar chat: Status={resp.status}, Response={error_text}")
                        raise Exception(f"Erro ao criar chat: Status {resp.status} - {error_text}")
                        
            except Exception as e:
                logger.error(f"❌ Erro em get_or_create_chat para {phone}: {str(e)}")
                raise

    @staticmethod
    async def send_message(message: dict):
        """
        Envia mensagem para a Zaia e retorna a resposta, garantindo que o chat existe.
        A Zaia detecta automaticamente a intenção do usuário.
        
        Args:
            message: Dicionário contendo:
                - text.body: Texto da mensagem (para mensagens de texto)
                - transcript: Texto transcrito (para mensagens de áudio)
                - phone: Número do telefone do usuário
        """
        logger.info(f"=== INICIANDO send_message ===")
        logger.info(f"📨 Dados da mensagem: {message}")
        
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
            logger.error("❌ Texto da mensagem não encontrado")
            raise Exception("Texto da mensagem não encontrado")
            
        phone = message.get('phone')
        if not phone:
            logger.error("❌ Telefone não informado na mensagem")
            raise Exception("Telefone não informado na mensagem para Zaia.")
            
        logger.info(f"📱 Processando mensagem: '{message_text}' do telefone: {phone}")
        
        try:
            # 1. Garante que o chat existe para este número específico
            logger.info(f"🔄 Obtendo chat individual para {phone}...")
            chat_id = await ZaiaService.get_or_create_chat(phone)
            logger.info(f"✅ Chat ID obtido para {phone}: {chat_id}")
            
            # 2. Monta o payload (Zaia detecta intenções automaticamente)
            payload = {
                "agentId": int(agent_id),  # Converte para inteiro
                "externalGenerativeChatId": chat_id,
                "prompt": message_text,
                "custom": {"whatsapp": phone}
            }
            
            url_message = f"{base_url}/v1.1/api/external-generative-message/create"
            logger.info(f"📤 Enviando mensagem para Zaia - URL: {url_message}")
            logger.info(f"📤 Chat ID usado: {chat_id} (para telefone: {phone})")
            logger.info(f"📤 Payload completo: {payload}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url_message, headers=headers, json=payload) as response:
                    logger.info(f"📥 Resposta da Zaia - Status: {response.status}")
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"❌ Erro ao enviar mensagem: Status={response.status}, Response={error_text}")
                        raise Exception(f"Erro ao enviar mensagem: Status {response.status} - {error_text}")
                        
                    response_json = await response.json()
                    logger.info(f"✅ Resposta da Zaia para {phone} (Chat {chat_id}): {response_json}")
                    return response_json
                    
        except Exception as e:
            logger.error(f"❌ Erro ao enviar mensagem para Zaia (telefone: {phone}): {str(e)}")
            raise 