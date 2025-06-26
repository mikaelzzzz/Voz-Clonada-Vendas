import logging
import aiohttp
from app.config import settings
import requests
import time

logger = logging.getLogger(__name__)

class ZaiaService:
    def __init__(self):
        pass  # Removido IntentService - Zaia detecta intenções automaticamente

    @staticmethod
    async def get_or_create_chat(phone: str):
        """
        Busca um chat existente na Zaia para o telefone ou cria um novo se não existir.
        Usa a API da Zaia como fonte única da verdade para manter histórico.
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
        
        # Buscar chat existente do WhatsApp para este telefone específico
        chat_id = await ZaiaService._find_whatsapp_chat(base_url, headers, agent_id, phone)
        
        if chat_id:
            logger.info(f"✅ CHAT EXISTENTE ENCONTRADO para {phone} - Chat ID: {chat_id}")
            return chat_id
        
        # Se não encontrou, criar novo chat
        logger.info(f"❌ Nenhum chat ativo do WhatsApp encontrado para {phone}")
        return await ZaiaService._create_new_chat(base_url, headers, agent_id, phone)

    @staticmethod
    async def _find_whatsapp_chat(base_url: str, headers: dict, agent_id: str, phone: str) -> int:
        """
        Busca por chat do WhatsApp existente para o telefone específico.
        Otimizada para encontrar rapidamente o chat correto.
        """
        logger.info(f"🔍 BUSCANDO chat do WhatsApp para {phone}...")
        
        # Buscar com paginação otimizada - chats mais recentes primeiro
        limit = 100  # Maior limite para buscar mais chats por vez
        offset = 0
        max_pages = 10  # Limitar busca para evitar loops infinitos
        
        for page in range(max_pages):
            url = f"{base_url}/v1.1/api/external-generative-chat/retrieve-multiple"
            params = {
                "agentIds": [int(agent_id)],
                "limit": limit,
                "offset": offset
            }
            
            logger.info(f"🔍 Página {page + 1}: offset {offset}, limit {limit}")
            
            try:
                response = requests.get(url, params=params, headers=headers, timeout=10)
                
                if response.status_code != 200:
                    logger.error(f"❌ Erro na busca: {response.status_code} - {response.text}")
                    break
                    
                data = response.json()
                chats = data.get("externalGenerativeChats", [])
                
                if not chats:
                    logger.info(f"📄 Nenhum chat encontrado na página {page + 1}")
                    break
                
                logger.info(f"📋 Analisando {len(chats)} chats na página {page + 1}")
                
                # Procurar por chat do WhatsApp ativo para este telefone
                for chat in chats:
                    chat_id = chat.get("id")
                    chat_phone = chat.get("phoneNumber")
                    channel = chat.get("channel")
                    status = chat.get("status")
                    
                    # Log apenas para chats do WhatsApp
                    if channel == "whatsapp":
                        logger.info(f"🔍 WhatsApp Chat ID {chat_id}: phone={chat_phone}, status={status}")
                    
                    # Verificar se é o chat correto
                    if (chat_phone == phone and 
                        channel == "whatsapp" and 
                        status == "active"):
                        logger.info(f"✅ CHAT ENCONTRADO para {phone} - Chat ID: {chat_id}")
                        return chat_id
                
                # Verificar se há mais páginas
                if len(chats) < limit:
                    logger.info(f"📄 Fim da paginação - página {page + 1}")
                    break
                    
                offset += limit
                
            except Exception as e:
                logger.error(f"❌ Erro na busca página {page + 1}: {str(e)}")
                break
        
        logger.info(f"❌ Chat não encontrado após buscar {page + 1} páginas")
        return None

    @staticmethod
    async def _create_new_chat(base_url: str, headers: dict, agent_id: str, phone: str) -> int:
        """
        Cria um novo chat na Zaia para o telefone especificado.
        """
        logger.info(f"🆕 CRIANDO NOVO CHAT para {phone}")
        
        payload = {
            "agentId": int(agent_id),
            "externalId": phone,
            "channel": "whatsapp",
            "phoneNumber": phone
        }
        
        url = f"{base_url}/v1.1/api/external-generative-chat/create"
        logger.info(f"🆕 URL: {url}")
        logger.info(f"🆕 Payload: {payload}")
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            logger.info(f"🆕 Resposta da criação - Status: {response.status_code}")
            
            if response.status_code == 201:
                chat_data = response.json()
                chat_id = chat_data.get("id")
                logger.info(f"✅ NOVO CHAT CRIADO para {phone} - Chat ID: {chat_id}")
                return chat_id
                
            elif response.status_code == 409:
                # Conflito - chat já existe, tentar buscar novamente
                logger.info(f"🔄 Conflito detectado - chat pode já existir, buscando novamente...")
                time.sleep(1)  # Pequeno delay
                
                # Buscar novamente com foco apenas neste telefone
                found_chat_id = await ZaiaService._find_whatsapp_chat(base_url, headers, agent_id, phone)
                if found_chat_id:
                    logger.info(f"✅ CHAT ENCONTRADO após conflito para {phone} - Chat ID: {found_chat_id}")
                    return found_chat_id
                else:
                    raise Exception(f"Chat não encontrado após conflito para {phone}")
                    
            else:
                error_text = response.text
                logger.error(f"❌ Erro ao criar chat: {response.status_code} - {error_text}")
                raise Exception(f"Erro ao criar chat: {response.status_code} - {error_text}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro de rede ao criar chat: {str(e)}")
            raise Exception(f"Erro de rede ao criar chat: {str(e)}")

    @staticmethod
    async def send_message(message: dict):
        """
        Envia mensagem para a Zaia e retorna a resposta.
        Sempre usa a API da Zaia para encontrar/manter o chat correto.
        
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
            # 1. Buscar ou criar chat na Zaia (fonte única da verdade)
            logger.info(f"🔄 Obtendo chat via API da Zaia para {phone}...")
            chat_id = await ZaiaService.get_or_create_chat(phone)
            logger.info(f"✅ Chat ID obtido para {phone}: {chat_id}")
            
            # 2. Enviar mensagem usando o chat correto
            payload = {
                "agentId": int(agent_id),
                "externalGenerativeChatId": chat_id,
                "prompt": message_text,
                "streaming": False,
                "asMarkdown": False,
                "custom": {"whatsapp": phone}
            }
            
            url_message = f"{base_url}/v1.1/api/external-generative-message/create"
            logger.info(f"📤 Enviando mensagem para Zaia - URL: {url_message}")
            logger.info(f"📤 Chat ID usado: {chat_id} (para telefone: {phone})")
            logger.info(f"📤 Payload: {payload}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url_message, headers=headers, json=payload) as response:
                    logger.info(f"📥 Resposta da Zaia - Status: {response.status}")
                    
                    if response.status == 200:
                        response_json = await response.json()
                        logger.info(f"✅ Resposta da Zaia para {phone} (Chat {chat_id}): {response_json}")
                        return response_json
                        
                    elif response.status == 404:
                        # Chat não existe mais - buscar/criar novo
                        logger.info(f"🔄 Chat {chat_id} não encontrado, buscando/criando novo...")
                        new_chat_id = await ZaiaService.get_or_create_chat(phone)
                        payload["externalGenerativeChatId"] = new_chat_id
                        
                        # Tentar novamente com novo chat
                        async with session.post(url_message, headers=headers, json=payload) as retry_response:
                            if retry_response.status == 200:
                                response_json = await retry_response.json()
                                logger.info(f"✅ Resposta da Zaia (retry) para {phone} (Chat {new_chat_id}): {response_json}")
                                return response_json
                            else:
                                error_text = await retry_response.text()
                                raise Exception(f"Erro no retry: Status {retry_response.status} - {error_text}")
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Erro ao enviar mensagem: Status={response.status}, Response={error_text}")
                        raise Exception(f"Erro ao enviar mensagem: Status {response.status} - {error_text}")
                    
        except Exception as e:
            logger.error(f"❌ Erro ao enviar mensagem para Zaia (telefone: {phone}): {str(e)}")
            raise 