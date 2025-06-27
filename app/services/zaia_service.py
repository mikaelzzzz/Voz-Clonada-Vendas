import logging
import aiohttp
from app.config.settings import Settings
from app.services.cache_service import CacheService
import requests
import time

logger = logging.getLogger(__name__)

class ZaiaService:
    # Cache para armazenar o último chat ID válido por telefone
    _chat_cache = {}
    
    def __init__(self):
        pass  # Removido IntentService - Zaia detecta intenções automaticamente
    
    @staticmethod
    async def clear_chat_cache(phone: str = None):
        """
        Limpa o cache de chats. Se phone for especificado, limpa apenas para esse telefone.
        """
        if phone:
            await CacheService.clear_chat_id(phone)
            ZaiaService._chat_cache.pop(phone, None)
            logger.info(f"🗑️ Cache limpo para {phone}")
        else:
            await CacheService.clear_all_chats()
            ZaiaService._chat_cache.clear()
            logger.info(f"🗑️ Cache completo limpo")

    @staticmethod
    async def get_or_create_chat(phone: str):
        """
        Busca um chat existente na Zaia para o telefone ou cria um novo se não existir.
        Usa cache inteligente para manter consistência entre mensagens.
        Retorna o chat_id.
        """
        logger.info(f"=== INICIANDO get_or_create_chat para telefone: {phone} ===")
        
        settings = Settings()
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
        
        # Estratégia 1: Verificar cache Redis/local
        cached_chat_id = await CacheService.get_chat_id(phone)
        if not cached_chat_id:
            # Fallback para cache local se Redis não estiver disponível
            cached_chat_id = ZaiaService._chat_cache.get(phone)
        
        if cached_chat_id:
            logger.info(f"🔄 Usando chat do cache para {phone}: {cached_chat_id}")
            return cached_chat_id
        
        # Estratégia 2: Buscar último chat usado por este telefone
        logger.info(f"🔍 Cache vazio, buscando último chat usado para {phone}")
        last_chat_id = await ZaiaService.find_last_chat_by_phone(phone)
        
        if last_chat_id:
            logger.info(f"✅ ÚLTIMO CHAT ENCONTRADO para {phone} - Chat ID: {last_chat_id}")
            # Atualizar cache Redis e local
            await CacheService.set_chat_id(phone, last_chat_id)
            ZaiaService._chat_cache[phone] = last_chat_id
            return last_chat_id
        
        # Estratégia 3: Criar novo chat se nenhum foi encontrado
        logger.info(f"🆕 Nenhum chat existente, criando novo para {phone}")
        new_chat_id = await ZaiaService._create_new_chat(base_url, headers, agent_id, phone)
        # Atualizar cache Redis e local
        await CacheService.set_chat_id(phone, new_chat_id)
        ZaiaService._chat_cache[phone] = new_chat_id
        return new_chat_id

    @staticmethod
    async def _find_existing_chat(base_url: str, headers: dict, agent_id: str, phone: str) -> int:
        """
        Busca chat existente para o telefone usando a API correta da Zaia.
        Usa o endpoint retrieve-multiple com filtros adequados.
        """
        logger.info(f"🔍 BUSCANDO chat existente para {phone}")
        
        try:
            # Usar o endpoint correto conforme documentação
            url = f"{base_url}/v1.1/api/external-generative-chat/retrieve-multiple"
            params = {
                "agentIds": [int(agent_id)],  # Array de números conforme documentação
                "limit": 50,
                "offset": 0
            }
            
            logger.info(f"🔍 Consultando API Zaia: {url}")
            logger.info(f"🔍 Parâmetros: {params}")
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"❌ Erro na busca: {response.status_code} - {response.text}")
                return None
                
            data = response.json()
            chats = data.get("externalGenerativeChats", [])
            
            if not chats:
                logger.info(f"📄 Nenhum chat encontrado para o agente {agent_id}")
                return None
            
            logger.info(f"📋 Encontrados {len(chats)} chats, analisando...")
            
            # Buscar chat para este telefone específico
            # Ordenar por data de criação (mais recentes primeiro)
            chats_sorted = sorted(chats, key=lambda x: x.get('createdAt', ''), reverse=True)
            
            for chat in chats_sorted:
                chat_id = chat.get("id")
                chat_phone = chat.get("phoneNumber")
                channel = chat.get("channel")
                status = chat.get("status")
                external_id = chat.get("externalId")
                created_at = chat.get("createdAt")
                
                logger.info(f"🔍 Analisando chat {chat_id}: phone={chat_phone}, channel={channel}, status={status}, externalId={external_id}")
                
                # Filtrar apenas chats ativos do WhatsApp para este telefone
                if (status == "active" and 
                    channel == "whatsapp" and 
                    chat_phone == phone):
                    
                    logger.info(f"✅ CHAT ENCONTRADO para {phone} - Chat ID: {chat_id} (criado em: {created_at})")
                    return chat_id
            
            logger.info(f"❌ Nenhum chat ativo encontrado para {phone}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Erro na busca de chats: {str(e)}")
            return None

    @staticmethod
    async def _verify_chat_functional(base_url: str, headers: dict, chat_id: int) -> bool:
        """
        Verifica se um chat está realmente funcional fazendo uma verificação leve.
        """
        try:
            # Fazer uma requisição simples para verificar se o chat existe
            url = f"{base_url}/v1.1/api/external-generative-chat/retrieve"
            params = {"id": chat_id}
            
            response = requests.get(url, params=params, headers=headers, timeout=5)
            
            if response.status_code == 200:
                chat_data = response.json()
                status = chat_data.get("status")
                logger.info(f"🔍 Chat {chat_id} verificado - Status: {status}")
                return status == "active"
            else:
                logger.warning(f"⚠️ Chat {chat_id} não encontrado na verificação: {response.status_code}")
                return False
                
        except Exception as e:
            logger.warning(f"⚠️ Erro ao verificar chat {chat_id}: {str(e)}")
            return False

    @staticmethod
    async def _create_new_chat(base_url: str, headers: dict, agent_id: str, phone: str) -> int:
        """
        Cria um novo chat na Zaia usando payload mínimo conforme documentação.
        """
        logger.info(f"🆕 CRIANDO NOVO CHAT para {phone}")
        
        # Payload mínimo conforme documentação da Zaia
        payload = {
            "agentId": int(agent_id)
        }
        
        url = f"{base_url}/v1.1/api/external-generative-chat/create"
        logger.info(f"🆕 URL: {url}")
        logger.info(f"🆕 Payload: {payload}")
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            logger.info(f"🆕 Resposta da criação - Status: {response.status_code}")
            logger.info(f"🆕 Resposta completa: {response.text}")
            
            if response.status_code in [200, 201]:
                chat_data = response.json()
                chat_id = chat_data.get("id")
                logger.info(f"✅ NOVO CHAT CRIADO para {phone} - Chat ID: {chat_id}")
                return chat_id
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
        Usa chat_id e externalId para manter consistência conforme documentação.
        Implementa retry inteligente em caso de chat inválido.
        
        Args:
            message: Dicionário contendo:
                - text.body: Texto da mensagem (para mensagens de texto)
                - transcript: Texto transcrito (para mensagens de áudio)
                - phone: Número do telefone do usuário
        """
        logger.info(f"=== INICIANDO send_message ===")
        logger.info(f"📨 Dados da mensagem: {message}")
        
        settings = Settings()
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
        
        # Máximo de 2 tentativas
        for attempt in range(2):
            try:
                # 1. Buscar ou criar chat na Zaia
                logger.info(f"🔄 Tentativa {attempt + 1}: Obtendo chat via API da Zaia para {phone}...")
                
                if attempt == 0:
                    # Primeira tentativa: buscar chat existente
                    chat_id = await ZaiaService.get_or_create_chat(phone)
                else:
                    # Segunda tentativa: forçar criação de novo chat
                    logger.info(f"🆕 Forçando criação de novo chat para {phone}")
                    chat_id = await ZaiaService._create_new_chat(base_url, headers, agent_id, phone)
                
                logger.info(f"✅ Chat ID obtido para {phone}: {chat_id}")
                
                # 2. Enviar mensagem usando o chat correto
                # Não usar externalId no payload de mensagem - usar apenas o chat_id
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
                logger.info(f"📤 Chat ID: {chat_id} (telefone: {phone})")
                logger.info(f"📤 Payload: {payload}")
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(url_message, headers=headers, json=payload) as response:
                        logger.info(f"📥 Resposta da Zaia - Status: {response.status}")
                        
                        if response.status == 200:
                            response_json = await response.json()
                            logger.info(f"✅ Resposta da Zaia para {phone} (Chat {chat_id}): {response_json}")
                            
                            # IMPORTANTE: Atualizar cache com o chat ID da resposta da Zaia
                            # A Zaia pode retornar um chat ID diferente do que enviamos
                            response_chat_id = response_json.get('externalGenerativeChatId')
                            if response_chat_id and response_chat_id != chat_id:
                                logger.info(f"🔄 Atualizando cache: Chat ID {chat_id} → {response_chat_id} para {phone}")
                                await CacheService.set_chat_id(phone, response_chat_id)
                                ZaiaService._chat_cache[phone] = response_chat_id
                            
                            return response_json
                            
                        elif response.status == 404:
                            # Chat não existe - tentar próxima iteração se ainda há tentativas
                            error_text = await response.text()
                            logger.warning(f"⚠️ Chat {chat_id} retornou 404: {error_text}")
                            
                            if attempt < 1:  # Se não é a última tentativa
                                logger.info(f"🔄 Tentando novamente com novo chat...")
                                continue
                            else:
                                raise Exception(f"Chat não funcional após {attempt + 1} tentativas: {error_text}")
                        else:
                            error_text = await response.text()
                            logger.error(f"❌ Erro ao enviar mensagem: Status={response.status}, Response={error_text}")
                            raise Exception(f"Erro ao enviar mensagem: Status {response.status} - {error_text}")
                        
            except Exception as e:
                if attempt < 1:  # Se não é a última tentativa
                    logger.warning(f"⚠️ Tentativa {attempt + 1} falhou: {str(e)}")
                    continue
                else:
                    logger.error(f"❌ Erro ao enviar mensagem para Zaia após {attempt + 1} tentativas (telefone: {phone}): {str(e)}")
                    raise 

    @staticmethod
    async def buscar_historico_zaia(chat_id: int) -> list:
        """
        Busca o histórico completo de mensagens de um chat na Zaia.
        Retorna uma lista de dicionários com origin e text.
        """
        settings = Settings()
        base_url = settings.ZAIA_BASE_URL.rstrip("/")
        api_key = settings.ZAIA_API_KEY
        
        url_retrieve = f"{base_url}/v1.1/api/external-generative-message/retrieve-multiple?externalGenerativeChatIds={chat_id}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url_retrieve, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        chats = data.get("externalGenerativeChats", [])
                        if chats:
                            messages = chats[0].get("externalGenerativeMessages", [])
                            logger.info(f"📜 Encontradas {len(messages)} mensagens no histórico do chat {chat_id}")
                            return [{"origin": m.get("origin"), "text": m.get("text")} for m in messages]
                        return []
                    else:
                        raw_text = await resp.text()
                        logger.error(f"❌ Erro ao buscar histórico da Zaia (status {resp.status}): {raw_text}")
                        return []
        except Exception as e:
            logger.error(f"❌ Erro ao buscar histórico do chat {chat_id}: {str(e)}")
            return [] 

    @staticmethod
    async def find_last_chat_by_phone(phone: str) -> int:
        """
        Encontra o último chat usado por um telefone específico
        através da busca no histórico de todos os chats.
        """
        settings = Settings()
        base_url = settings.ZAIA_BASE_URL.rstrip("/")
        agent_id = settings.ZAIA_AGENT_ID
        api_key = settings.ZAIA_API_KEY
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        try:
            # Buscar todos os chats do agente (mais recentes primeiro)
            url = f"{base_url}/v1.1/api/external-generative-chat/retrieve-multiple"
            params = {
                "agentIds": [int(agent_id)],  # Array de números conforme documentação
                "limit": 50,  # Reduzir para focar nos mais recentes
                "offset": 0,
                "sortBy": "createdAt",  # Ordenar por data de criação
                "sortOrder": "desc"     # Mais recentes primeiro
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"❌ Erro na busca de chats: {response.status_code} - {response.text}")
                return None
                
            data = response.json()
            chats = data.get("externalGenerativeChats", [])
            
            if not chats:
                logger.info(f"📄 Nenhum chat encontrado para busca por histórico")
                return None
            
            # Filtrar chats do WhatsApp para este telefone e ordenar por data
            phone_chats = []
            for chat in chats:
                if (chat.get("channel") == "whatsapp" and 
                    chat.get("phoneNumber") == phone and
                    chat.get("status") == "active"):
                    phone_chats.append(chat)
            
            if not phone_chats:
                logger.info(f"📄 Nenhum chat do WhatsApp encontrado para {phone}")
                return None
            
            # Ordenar por data de criação (mais recente primeiro)
            phone_chats.sort(key=lambda x: x.get('createdAt', ''), reverse=True)
            
            # Pegar o chat mais recente
            latest_chat = phone_chats[0]
            chat_id = latest_chat.get("id")
            created_at = latest_chat.get("createdAt")
            
            logger.info(f"🎯 Último chat encontrado para {phone}: {chat_id} (criado em: {created_at})")
            return chat_id
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar último chat por telefone: {str(e)}")
            return None 