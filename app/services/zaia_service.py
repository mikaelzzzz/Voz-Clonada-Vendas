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
        
        # Buscar chat existente com paginação correta
        limit = 50  # Quantidade por página
        offset = 0
        
        while True:
            url = f"{base_url}/v1.1/api/external-generative-chat/retrieve-multiple"
            params = {
                "agentIds": [int(agent_id)],  # Array de números conforme documentação
                "limit": limit,
                "offset": offset
            }
                
            logger.info(f"🔍 BUSCANDO chat existente (offset {offset}) - URL: {url}")
            logger.info(f"🔍 Parâmetros: {params}")
            
            response = requests.get(url, params=params, headers=headers)
            logger.info(f"📋 Resposta da busca - Status: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"❌ Erro na busca de chats: {response.status_code} - {response.text}")
                break
                
            data = response.json()
            logger.info(f"📋 Dados da busca (offset {offset}): {data}")
            
            chats = data.get("externalGenerativeChats", [])
            if not chats:
                logger.info(f"📄 Nenhum chat encontrado no offset {offset}")
                break
            
            # Procurar por chat do WhatsApp ativo
            for chat in chats:
                chat_id = chat.get("id")
                chat_phone = chat.get("phoneNumber")
                channel = chat.get("channel")
                status = chat.get("status")
                
                logger.info(f"🔍 Analisando chat ID {chat_id}: phone={chat_phone}, channel={channel}, status={status}")
                
                # Verificar se é o chat correto
                if (chat_phone == phone and 
                    channel == "whatsapp" and 
                    status == "active"):
                    logger.info(f"✅ CHAT EXISTENTE ENCONTRADO para {phone} - Chat ID: {chat_id}")
                    logger.info(f"✅ Chat details: {chat}")
                    return chat_id
            
            # Verificar se há mais páginas baseado na quantidade retornada
            if len(chats) < limit:
                logger.info(f"📄 Fim da paginação - retornados {len(chats)} chats (menos que limit {limit})")
                break
                
            offset += limit
            if offset > 1000:  # Limite de segurança para evitar loops infinitos
                logger.warning(f"⚠️ Limite de offset atingido (1000), parando busca")
                break
        
        # Se não encontrou, criar novo chat
        logger.info(f"❌ Nenhum chat ativo do WhatsApp encontrado para {phone}")
        logger.info(f"🆕 CRIANDO NOVO CHAT - URL: {base_url}/v1.1/api/external-generative-chat/create")
        
        payload = {
            "agentId": int(agent_id),
            "externalId": phone,
            "channel": "whatsapp",
            "phoneNumber": phone
        }
        logger.info(f"🆕 Payload: {payload}")
        
        response = requests.post(
            f"{base_url}/v1.1/api/external-generative-chat/create",
            json=payload,
            headers=headers
        )
        
        logger.info(f"🆕 Resposta da criação - Status: {response.status_code}")
        
        if response.status_code == 201:
            chat_data = response.json()
            chat_id = chat_data.get("id")
            logger.info(f"✅ NOVO CHAT CRIADO para {phone} - Chat ID: {chat_id}")
            logger.info(f"✅ Dados do novo chat: {chat_data}")
            return chat_id
        elif response.status_code == 409:
            # Race condition - tentar buscar novamente
            logger.info(f"🔄 Race condition detectado, buscando chat novamente...")
            
            # Buscar novamente com delay
            time.sleep(1)
            
            response = requests.get(
                f"{base_url}/v1.1/api/external-generative-chat/retrieve-multiple",
                params={
                    "agentIds": [int(agent_id)],
                    "limit": 100  # Buscar mais chats na recuperação pós-race condition
                },
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"🔄 Dados da busca pós-race condition: {data}")
                
                # Procurar novamente por chat do WhatsApp ativo
                for chat in data.get("externalGenerativeChats", []):
                    if (chat.get("phoneNumber") == phone and 
                        chat.get("channel") == "whatsapp" and 
                        chat.get("status") == "active"):
                        chat_id = chat.get("id")
                        logger.info(f"✅ CHAT ENCONTRADO após race condition para {phone} - Chat ID: {chat_id}")
                        return chat_id
            
            logger.error(f"❌ Falha ao recuperar chat após race condition para {phone}")
            raise Exception("Falha ao recuperar chat após conflito de criação")
        else:
            logger.error(f"❌ Erro ao criar chat: {response.status_code} - {response.text}")
            raise Exception(f"Erro ao criar chat: {response.status_code}")

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
                "streaming": False,  # Resposta síncrona
                "asMarkdown": False,  # Texto puro, não markdown
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