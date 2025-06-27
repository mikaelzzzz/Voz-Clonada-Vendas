#!/usr/bin/env python3
"""
Teste para verificar se as mensagens estão sendo agrupadas no mesmo chat
usando o endpoint retrieve-multiple da Zaia API.
"""

import asyncio
import aiohttp
from app.config.settings import Settings
from app.services.zaia_service import ZaiaService
from app.services.cache_service import CacheService
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_retrieve_messages():
    """
    Testa o endpoint retrieve-multiple para verificar mensagens de um chat específico
    """
    settings = Settings()
    
    # Número de telefone de teste (usar um que já tenha histórico)
    test_phone = "5511975578651"  # Substitua pelo número que você está testando
    
    logger.info(f"🧪 INICIANDO TESTE para telefone: {test_phone}")
    
    try:
        # 1. Buscar o chat ID atual para este telefone
        chat_id = await ZaiaService.get_or_create_chat(test_phone)
        logger.info(f"📱 Chat ID encontrado/criado: {chat_id}")
        
        # 2. Usar o endpoint retrieve-multiple para buscar mensagens
        base_url = settings.ZAIA_BASE_URL.rstrip("/")
        api_key = settings.ZAIA_API_KEY
        
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        # Endpoint conforme documentação
        url = f"{base_url}/v1.1/api/external-generative-message/retrieve-multiple"
        params = {
            "externalGenerativeChatIds": str(chat_id)  # Pode ser múltiplos separados por vírgula
        }
        
        logger.info(f"🔍 Consultando: {url}")
        logger.info(f"🔍 Parâmetros: {params}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                logger.info(f"📥 Status da resposta: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ Dados recebidos: {data}")
                    
                    # Analisar as mensagens
                    messages = data.get("externalGenerativeMessages", [])
                    logger.info(f"📨 Total de mensagens encontradas: {len(messages)}")
                    
                    if messages:
                        logger.info("📋 HISTÓRICO DE MENSAGENS:")
                        for i, msg in enumerate(messages, 1):
                            msg_id = msg.get("id")
                            origin = msg.get("origin")  # "user" ou "assistant"
                            text = msg.get("text", "")[:100] + "..." if len(msg.get("text", "")) > 100 else msg.get("text", "")
                            created_at = msg.get("createdAt")
                            chat_id_msg = msg.get("externalGenerativeChatId")
                            
                            logger.info(f"  {i}. [{origin}] {text} (Chat: {chat_id_msg}, Criado: {created_at})")
                        
                        # Verificar se todas as mensagens estão no mesmo chat
                        unique_chat_ids = set(msg.get("externalGenerativeChatId") for msg in messages)
                        logger.info(f"🎯 Chat IDs únicos encontrados: {unique_chat_ids}")
                        
                        if len(unique_chat_ids) == 1:
                            logger.info("✅ SUCESSO: Todas as mensagens estão no mesmo chat!")
                        else:
                            logger.warning(f"⚠️ PROBLEMA: Mensagens estão em {len(unique_chat_ids)} chats diferentes!")
                            for chat_id in unique_chat_ids:
                                count = sum(1 for msg in messages if msg.get("externalGenerativeChatId") == chat_id)
                                logger.warning(f"   Chat {chat_id}: {count} mensagens")
                    else:
                        logger.info("📄 Nenhuma mensagem encontrada neste chat")
                        
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Erro na consulta: {response.status} - {error_text}")
                    
    except Exception as e:
        logger.error(f"❌ Erro no teste: {str(e)}")

async def test_send_multiple_messages():
    """
    Envia múltiplas mensagens de teste para verificar se ficam no mesmo chat
    """
    test_phone = "5511975578651"  # Substitua pelo número que você está testando
    
    logger.info(f"🧪 TESTE DE MÚLTIPLAS MENSAGENS para: {test_phone}")
    
    messages_to_test = [
        "Olá, esta é a primeira mensagem de teste",
        "Esta é a segunda mensagem de teste",
        "E esta é a terceira mensagem de teste"
    ]
    
    try:
        for i, text in enumerate(messages_to_test, 1):
            logger.info(f"📤 Enviando mensagem {i}: {text}")
            
            # Simular estrutura de mensagem do webhook
            message_data = {
                "text": {"body": text},
                "phone": test_phone
            }
            
            # Enviar mensagem
            response = await ZaiaService.send_message(message_data)
            logger.info(f"📥 Resposta {i}: {response}")
            
            # Aguardar um pouco entre as mensagens
            await asyncio.sleep(2)
            
        logger.info("✅ Todas as mensagens de teste foram enviadas!")
        
        # Aguardar um pouco e então verificar o histórico
        logger.info("⏳ Aguardando 5 segundos antes de verificar o histórico...")
        await asyncio.sleep(5)
        
        # Verificar o histórico
        await test_retrieve_messages()
        
    except Exception as e:
        logger.error(f"❌ Erro no teste de múltiplas mensagens: {str(e)}")

async def main():
    """
    Função principal para executar os testes
    """
    logger.info("🚀 INICIANDO TESTES DA ZAIA API")
    
    # Teste 1: Verificar mensagens existentes
    logger.info("\n" + "="*50)
    logger.info("TESTE 1: Verificar mensagens existentes")
    logger.info("="*50)
    await test_retrieve_messages()
    
    # Teste 2: Enviar múltiplas mensagens e verificar agrupamento
    logger.info("\n" + "="*50)
    logger.info("TESTE 2: Enviar múltiplas mensagens")
    logger.info("="*50)
    
    # Perguntar se deve executar o teste de envio
    print("\n🤔 Deseja executar o teste de envio de múltiplas mensagens? (y/n): ", end="")
    # Para automação, vamos pular a interação
    # response = input().lower().strip()
    # if response == 'y':
    #     await test_send_multiple_messages()
    # else:
    #     logger.info("⏭️ Teste de envio pulado")
    
    logger.info("⏭️ Teste de envio pulado (descomente o código acima para ativar)")
    
    logger.info("\n🏁 TESTES CONCLUÍDOS")

if __name__ == "__main__":
    asyncio.run(main()) 