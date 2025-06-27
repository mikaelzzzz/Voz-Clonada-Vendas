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
    # Cache de backup para persistir entre instâncias
    _persistent_cache = {}
    
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
            ZaiaService._persistent_cache.pop(phone, None)
            logger.info(f"🗑️ Cache limpo para {phone}")
        else:
            await CacheService.clear_all_chats()
            ZaiaService._chat_cache.clear()
            ZaiaService._persistent_cache.clear()
            logger.info(f"🗑️ Cache completo limpo")

    @staticmethod
    async def get_or_create_chat(phone: str):
        """
        ESTRATÉGIA SIMPLES: Um chat por telefone
        1. Busca na API da Zaia por chats ativos deste telefone
        2. Se encontrar, usa o mais recente
        3. Se não encontrar, cria um novo
        4. Mantém cache apenas para performance
        """
        logger.info(f"=== BUSCANDO/CRIANDO CHAT ÚNICO para telefone: {phone} ===")
        
        settings = Settings()
        base_url = settings.ZAIA_BASE_URL.rstrip("/")
        agent_id = settings.ZAIA_AGENT_ID
        api_key = settings.ZAIA_API_KEY
        
        # Verificar configurações
        if not all([api_key, agent_id, base_url]):
            raise Exception("Configurações da Zaia incompletas")
            
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # PASSO 1: Verificar cache rápido (só para performance)
        cached_chat_id = await CacheService.get_chat_id(phone)
        if cached_chat_id:
            logger.info(f"💾 Chat em cache para {phone}: {cached_chat_id}")
            # Verificar se ainda é válido
            if await ZaiaService._verify_chat_functional(base_url, headers, cached_chat_id):
                logger.info(f"✅ Chat do cache é válido: {cached_chat_id}")
                return cached_chat_id
            else:
                logger.warning(f"⚠️ Chat do cache inválido, removendo: {cached_chat_id}")
                await CacheService.clear_chat_id(phone)
        
        # PASSO 2: Buscar na API da Zaia o chat ativo deste telefone
        logger.info(f"🔍 Buscando chat ativo na API da Zaia para {phone}")
        active_chat_id = await ZaiaService._find_active_chat_by_phone(phone)
        
        if active_chat_id:
            logger.info(f"✅ CHAT ATIVO ENCONTRADO para {phone}: {active_chat_id}")
            # Verificar se este chat ainda é funcional antes de usar
            if await ZaiaService._verify_chat_functional(base_url, headers, active_chat_id):
                logger.info(f"✅ Chat encontrado é funcional: {active_chat_id}")
                # Salvar no cache para próximas consultas
                await CacheService.set_chat_id(phone, active_chat_id)
                return active_chat_id
            else:
                logger.warning(f"⚠️ Chat encontrado não é funcional: {active_chat_id}")
                # Continuar para criar novo chat
        
        # PASSO 3: Criar novo chat se não existe nenhum ativo
        logger.info(f"🆕 Nenhum chat ativo encontrado, criando novo para {phone}")
        new_chat_id = await ZaiaService._create_new_chat(base_url, headers, agent_id, phone)
        
        # Salvar no cache
        await CacheService.set_chat_id(phone, new_chat_id)
        logger.info(f"✅ NOVO CHAT CRIADO para {phone}: {new_chat_id}")
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
        ESTRATÉGIA COMPROVADA: Contexto automático com externalId
        
        ✅ TESTES CONFIRMARAM:
        - A Zaia mantém contexto perfeitamente usando apenas externalGenerativeChatExternalId
        - Mesmo chat ID é reutilizado automaticamente para o mesmo telefone
        - Contexto 100% preservado (nome, profissão, histórico completo)
        - Não precisa gerenciar chat IDs manualmente
        
        Args:
            message: Dicionário contendo:
                - text.body: Texto da mensagem (para mensagens de texto)  
                - transcript: Texto transcrito (para mensagens de áudio)
                - phone: Número do telefone do usuário
        """
        logger.info(f"=== ENVIANDO MENSAGEM ===")
        logger.info(f"📨 Dados: {message}")
        
        settings = Settings()
        base_url = settings.ZAIA_BASE_URL.rstrip("/")
        agent_id = settings.ZAIA_AGENT_ID
        api_key = settings.ZAIA_API_KEY
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Extrair dados da mensagem
        message_text = message.get('transcript') or message.get('text', {}).get('body')
        if not message_text:
            raise Exception("Texto da mensagem não encontrado")
            
        phone = message.get('phone')
        if not phone:
            raise Exception("Telefone não informado")
            
        logger.info(f"📱 Mensagem: '{message_text}' | Telefone: {phone}")
        
        try:
            # ESTRATÉGIA COMPROVADA: Usar APENAS externalId para contexto automático!
            # ✅ TESTES CONFIRMARAM: A Zaia mantém contexto perfeitamente com externalId
            # ✅ Mesmo chat ID reutilizado automaticamente
            # ✅ Contexto 100% preservado (nome, profissão, cidade, etc.)
            # ✅ Não precisa gerenciar chat IDs manualmente
            
            logger.info(f"📱 Enviando mensagem com contexto automático para: {phone}")
            
            # Payload SIMPLES e EFICAZ - apenas externalId
            payload = {
                "agentId": int(agent_id),
                "externalGenerativeChatExternalId": phone,  # TELEFONE = CONTEXTO ÚNICO
                "prompt": message_text,
                "streaming": False,
                "asMarkdown": False,
                "custom": {"whatsapp": phone}
            }
            
            url_message = f"{base_url}/v1.1/api/external-generative-message/create"
            logger.info(f"📤 Enviando mensagem para Zaia...")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url_message, headers=headers, json=payload) as response:
                    logger.info(f"📥 Status: {response.status}")
                    
                    if response.status == 200:
                        response_json = await response.json()
                        
                        # Extrair informações da resposta
                        chat_id = response_json.get('externalGenerativeChatId')
                        ai_response = response_json.get('text', 'Erro ao obter resposta')
                        
                        logger.info(f"✅ Chat ID usado pela Zaia: {chat_id}")
                        logger.info(f"🤖 Resposta da IA: {ai_response[:100]}...")
                        
                        # Salvar chat ID no cache para logs futuros (opcional)
                        if chat_id:
                            await CacheService.set_chat_id(phone, chat_id)
                        
                        return response_json
                        
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Erro na API Zaia: {response.status} - {error_text}")
                        logger.error(f"📤 Payload enviado: {payload}")
                        raise Exception(f"Erro ao enviar mensagem: {response.status} - {error_text}")
                        
        except Exception as e:
            logger.error(f"❌ Erro ao processar mensagem para {phone}: {str(e)}")
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
    async def _find_active_chat_by_phone(phone: str) -> int:
        """
        Busca o chat ativo para um telefone específico na API da Zaia.
        Retorna o chat_id do chat ativo mais recente ou None se não encontrar.
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
            # Buscar chats do agente, ordenados por data de criação (mais recentes primeiro)
            url = f"{base_url}/v1.1/api/external-generative-chat/retrieve-multiple"
            params = {
                "agentIds": [int(agent_id)],
                "limit": 50,  # Buscar uma quantidade razoável
                "offset": 0,
                "sortBy": "createdAt",
                "sortOrder": "desc"
            }
            
            logger.info(f"🔍 Consultando API Zaia: {url}")
            response = requests.get(url, params=params, headers=headers, timeout=15)
            
            if response.status_code != 200:
                logger.error(f"❌ Erro na busca de chats: {response.status_code} - {response.text}")
                return None
                
            data = response.json()
            all_chats = data.get("externalGenerativeChats", [])
            
            logger.info(f"📋 Encontrados {len(all_chats)} chats totais")
            
            # Filtrar apenas chats ativos do WhatsApp para este telefone específico
            # Primeiro, coletar todos os chats válidos para este telefone
            valid_chats = []
            for chat in all_chats:
                chat_id = chat.get("id")
                chat_phone = chat.get("phoneNumber")
                channel = chat.get("channel")
                status = chat.get("status")
                created_at = chat.get("createdAt")
                
                logger.info(f"🔍 Chat {chat_id}: phone={chat_phone}, channel={channel}, status={status}")
                
                # Encontrar chat ativo do WhatsApp para este telefone
                if (channel == "whatsapp" and 
                    chat_phone == phone and
                    status == "active"):
                    
                    valid_chats.append({
                        "id": chat_id,
                        "created_at": created_at
                    })
                    logger.info(f"✅ Chat válido encontrado: {chat_id} (criado: {created_at})")
            
            # Se encontrou chats válidos, retornar o mais recente
            if valid_chats:
                # Ordenar por data de criação (mais recente primeiro)
                valid_chats.sort(key=lambda x: x["created_at"], reverse=True)
                most_recent_chat = valid_chats[0]
                logger.info(f"🎯 CHAT MAIS RECENTE para {phone}: {most_recent_chat['id']} (criado: {most_recent_chat['created_at']})")
                return most_recent_chat["id"]
            
            logger.info(f"❌ Nenhum chat ativo encontrado para {phone}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar chat ativo: {str(e)}")
            return None

    @staticmethod
    async def find_last_chat_by_phone(phone: str) -> int:
        """
        Busca robusta que encontra o chat mais recente com atividade para um telefone específico.
        Analisa múltiplos chats e suas mensagens para determinar qual foi usado por último.
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
            # 1. Buscar todos os chats do agente (mais recentes primeiro)
            url = f"{base_url}/v1.1/api/external-generative-chat/retrieve-multiple"
            params = {
                "agentIds": [int(agent_id)],
                "limit": 100,  # Aumentar limite para busca mais ampla
                "offset": 0,
                "sortBy": "createdAt",
                "sortOrder": "desc"
            }
            
            logger.info(f"🔍 Buscando chats para {phone} na API da Zaia...")
            response = requests.get(url, params=params, headers=headers, timeout=15)
            
            if response.status_code != 200:
                logger.error(f"❌ Erro na busca de chats: {response.status_code} - {response.text}")
                return None
                
            data = response.json()
            all_chats = data.get("externalGenerativeChats", [])
            
            if not all_chats:
                logger.info(f"📄 Nenhum chat encontrado no agente {agent_id}")
                return None
            
            logger.info(f"📋 Encontrados {len(all_chats)} chats totais, filtrando por telefone {phone}...")
            
            # 2. Filtrar chats do WhatsApp para este telefone específico
            phone_chats = []
            for chat in all_chats:
                chat_id = chat.get("id")
                chat_phone = chat.get("phoneNumber")
                channel = chat.get("channel")
                status = chat.get("status")
                created_at = chat.get("createdAt")
                
                logger.info(f"🔍 Analisando chat {chat_id}: phone={chat_phone}, channel={channel}, status={status}")
                
                # Filtrar apenas chats ativos do WhatsApp para este telefone
                if (channel == "whatsapp" and 
                    chat_phone == phone and
                    status == "active"):
                    phone_chats.append(chat)
                    logger.info(f"✅ Chat válido encontrado: {chat_id} (criado: {created_at})")
            
            if not phone_chats:
                logger.info(f"📄 Nenhum chat ativo do WhatsApp encontrado para {phone}")
                return None
            
            logger.info(f"📋 {len(phone_chats)} chats válidos encontrados para {phone}")
            
            # 3. Ordenar chats por data de criação (mais recentes primeiro) e pegar o primeiro
            phone_chats.sort(key=lambda x: x.get('createdAt', ''), reverse=True)
            
            # Primeiro, tentar encontrar chats com atividade recente (últimas 24h)
            from datetime import datetime, timedelta
            now = datetime.utcnow()
            recent_threshold = now - timedelta(hours=24)
            
            chat_with_last_activity = None
            latest_activity_time = None
            
            for chat in phone_chats:
                chat_id = chat.get("id")
                created_at = chat.get("createdAt")
                
                try:
                    # Buscar mensagens deste chat específico
                    messages_url = f"{base_url}/v1.1/api/external-generative-message/retrieve-multiple"
                    messages_params = {
                        "externalGenerativeChatIds": [chat_id],
                        "limit": 10,  # Aumentar para ter mais contexto
                        "offset": 0,
                        "sortBy": "createdAt",
                        "sortOrder": "desc"
                    }
                    
                    messages_response = requests.get(messages_url, params=messages_params, headers=headers, timeout=10)
                    
                    if messages_response.status_code == 200:
                        messages_data = messages_response.json()
                        chat_messages = messages_data.get("externalGenerativeMessages", [])
                        
                        if chat_messages:
                            # Pegar a mensagem mais recente
                            last_message = chat_messages[0]
                            last_message_time = last_message.get("createdAt")
                            
                            logger.info(f"📅 Chat {chat_id}: última mensagem em {last_message_time} ({len(chat_messages)} mensagens)")
                            
                            # Priorizar chats com atividade muito recente
                            try:
                                message_date = datetime.fromisoformat(last_message_time.replace('Z', '+00:00'))
                                if message_date > recent_threshold:
                                    logger.info(f"🔥 Chat {chat_id} tem atividade recente (últimas 24h)")
                                    if latest_activity_time is None or last_message_time > latest_activity_time:
                                        latest_activity_time = last_message_time
                                        chat_with_last_activity = chat
                                        logger.info(f"🎯 Novo chat mais recente: {chat_id}")
                                        break  # Se encontrou um chat com atividade recente, usar esse
                            except:
                                pass
                            
                            # Comparar com o chat mais ativo até agora
                            if latest_activity_time is None or last_message_time > latest_activity_time:
                                latest_activity_time = last_message_time
                                chat_with_last_activity = chat
                                logger.info(f"🎯 Novo chat mais recente: {chat_id}")
                        else:
                            # Se não há mensagens, usar data de criação do chat apenas se não temos nada melhor
                            logger.info(f"📅 Chat {chat_id}: sem mensagens, usando data de criação {created_at}")
                            if latest_activity_time is None:
                                latest_activity_time = created_at
                                chat_with_last_activity = chat
                    else:
                        logger.warning(f"⚠️ Erro ao buscar mensagens do chat {chat_id}: {messages_response.status_code}")
                        # Só usar data de criação se não temos nada melhor
                        if latest_activity_time is None:
                            latest_activity_time = created_at
                            chat_with_last_activity = chat
                            
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao analisar atividade do chat {chat_id}: {str(e)}")
                    continue
            
            # 4. Retornar o chat com atividade mais recente
            if chat_with_last_activity:
                final_chat_id = chat_with_last_activity.get("id")
                logger.info(f"🎯 CHAT MAIS RECENTE para {phone}: {final_chat_id} (última atividade: {latest_activity_time})")
                return final_chat_id
            else:
                logger.info(f"❌ Nenhum chat com atividade encontrado para {phone}")
                return None
            
        except Exception as e:
            logger.error(f"❌ Erro na busca robusta de chat por telefone: {str(e)}")
            return None 