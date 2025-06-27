import logging
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from app.services.z_api_service import ZAPIService
from app.services.zaia_service import ZaiaService
from app.services.elevenlabs_service import ElevenLabsService
from app.services.whisper_service import WhisperService
from app.services.queue_service import queue_service, QueueService
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)

router = APIRouter()

# Serviços serão instanciados quando necessário

@router.post("")
async def handle_webhook(request: Request):
    try:
        data = await request.json()
        logger.info(f"Webhook recebido: {data}")

        # Verifica se é uma mensagem recebida (formato Z-API)
        if data.get('type') == 'ReceivedCallback' and not data.get('fromMe', False):
            phone = data.get('phone')
            
            if not phone:
                logger.warning("Telefone não encontrado na mensagem")
                return JSONResponse({"status": "no_phone"})
            
            # Processa baseado no conteúdo da mensagem
            if 'audio' in data and data['audio']:
                try:
                    logger.info(f"Processando mensagem de áudio de {phone}")
                    
                    # 1. Transcreve o áudio
                    audio_url = data['audio']['audioUrl']
                    whisper_service = WhisperService()
                    transcript = await whisper_service.transcribe_audio(audio_url)
                    logger.info(f"Áudio transcrito: {transcript}")
                    
                    # 2. Envia transcrição para Zaia
                    message_data = {
                        'transcript': transcript,
                        'phone': phone
                    }
                    zaia_service = ZaiaService()
                    zaia_response = await zaia_service.send_message(message_data)
                    logger.info(f"Resposta da Zaia recebida: {zaia_response}")
                    
                    # 3. Verifica se há mensagem na resposta
                    if 'text' in zaia_response and zaia_response['text']:
                        # 4. Gera resposta em áudio usando voz clonada
                        elevenlabs_service = ElevenLabsService()
                        audio_bytes = elevenlabs_service.generate_audio(zaia_response['text'])
                        
                        # 5. Envia resposta em áudio com simulação de gravação
                        await ZAPIService.send_audio_with_typing(phone, audio_bytes)
                        logger.info(f"Áudio enviado para {phone} com simulação de gravação")
                    else:
                        logger.warning(f"Zaia não retornou mensagem válida: {zaia_response}")
                        
                except Exception as e:
                    logger.error(f"Erro ao processar áudio de {phone}: {str(e)}")
                    # Não envia mensagem de erro para o cliente - apenas loga
                
            elif 'text' in data and data['text']:
                try:
                    message_text = data['text'].get('message', '')
                    logger.info(f"Processando mensagem de texto de {phone}: {message_text}")
                    
                    # 1. Envia texto para Zaia
                    message_data = {
                        'text': {'body': message_text},
                        'phone': phone
                    }
                    zaia_service = ZaiaService()
                    zaia_response = await zaia_service.send_message(message_data)
                    logger.info(f"Resposta da Zaia recebida: {zaia_response}")
                    
                    # 2. Verifica se há mensagem na resposta
                    if 'text' in zaia_response and zaia_response['text']:
                        # 3. Envia resposta em texto com simulação de digitação
                        await ZAPIService.send_text_with_typing(phone, zaia_response['text'])
                        logger.info(f"Texto enviado para {phone} com simulação de digitação")
                    else:
                        logger.warning(f"Zaia não retornou mensagem válida: {zaia_response}")
                        
                except Exception as e:
                    logger.error(f"Erro ao processar texto de {phone}: {str(e)}")
                    # Não envia mensagem de erro para o cliente - apenas loga
            
            else:
                logger.info(f"Tipo de mensagem não suportado ou vazio para {phone}")
            
            return JSONResponse({"status": "success"})
        
        # Verifica se é uma mensagem no formato antigo (compatibilidade)
        elif 'messages' in data:
            message = data['messages'][0]
            phone = message['from']
            
            # Processa baseado no tipo de mensagem
            if message['type'] == 'audio':
                try:
                    logger.info(f"Processando mensagem de áudio de {phone} (formato antigo)")
                    
                    # 1. Transcreve o áudio
                    whisper_service = WhisperService()
                    transcript = await whisper_service.transcribe_audio(message['audio']['url'])
                    logger.info(f"Áudio transcrito: {transcript}")
                    
                    # 2. Envia transcrição para Zaia
                    message_data = {
                        'transcript': transcript,
                        'phone': phone
                    }
                    zaia_service = ZaiaService()
                    zaia_response = await zaia_service.send_message(message_data)
                    logger.info(f"Resposta da Zaia recebida: {zaia_response}")
                    
                    # 3. Verifica se há mensagem na resposta
                    if 'text' in zaia_response and zaia_response['text']:
                        # 4. Gera resposta em áudio usando voz clonada
                        elevenlabs_service = ElevenLabsService()
                        audio_bytes = elevenlabs_service.generate_audio(zaia_response['text'])
                        
                        # 5. Envia resposta em áudio com simulação de gravação
                        await ZAPIService.send_audio_with_typing(phone, audio_bytes)
                        logger.info(f"Áudio enviado para {phone} com simulação de gravação")
                    else:
                        logger.warning(f"Zaia não retornou mensagem válida: {zaia_response}")
                        
                except Exception as e:
                    logger.error(f"Erro ao processar áudio de {phone} (formato antigo): {str(e)}")
                    # Não envia mensagem de erro para o cliente - apenas loga
                
            elif message['type'] == 'text':
                try:
                    logger.info(f"Processando mensagem de texto de {phone}: {message['text']['body']}")
                    
                    # 1. Envia texto para Zaia
                    message_data = {
                        'text': {'body': message['text']['body']},
                        'phone': phone
                    }
                    zaia_service = ZaiaService()
                    zaia_response = await zaia_service.send_message(message_data)
                    logger.info(f"Resposta da Zaia recebida: {zaia_response}")
                    
                    # 2. Verifica se há mensagem na resposta
                    if 'text' in zaia_response and zaia_response['text']:
                        # 3. Envia resposta em texto com simulação de digitação
                        await ZAPIService.send_text_with_typing(phone, zaia_response['text'])
                        logger.info(f"Texto enviado para {phone} com simulação de digitação")
                    else:
                        logger.warning(f"Zaia não retornou mensagem válida: {zaia_response}")
                        
                except Exception as e:
                    logger.error(f"Erro ao processar texto de {phone}: {str(e)}")
                    # Não envia mensagem de erro para o cliente - apenas loga
            
            return JSONResponse({"status": "success"})
        
        # Verifica se é uma notificação de status
        elif 'status' in data:
            logger.info(f"Status update: {data['status']}")
            return JSONResponse({"status": "success"})
        
        # Verifica se é uma notificação de desconexão
        elif 'connected' in data and not data['connected']:
            logger.info("Z-API disconnected")
            return JSONResponse({"status": "success"})
            
        return JSONResponse({"status": "unknown_event"})
        
    except Exception as e:
        logger.error(f"Erro geral ao processar webhook: {str(e)}")
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)

@router.get("/health")
async def health_check():
    """Endpoint de health check para verificar status do serviço e Redis"""
    try:
        # Verificar Redis se habilitado
        redis_status = "disabled"
        if CacheService.get_client():
            redis_status = "connected"
        else:
            redis_status = "not_available"
        
        return {
            "status": "healthy",
            "redis": redis_status,
            "message": "Serviço funcionando corretamente"
        }
    except Exception as e:
        logger.error(f"Health check falhou: {str(e)}")
        return {
            "status": "unhealthy",
            "redis": "error",
            "message": str(e)
        }

@router.post("/webhook")
async def webhook(request: Request):
    """Webhook para receber mensagens do Z-API"""
    try:
        data = await request.json()
        logger.info(f"Webhook recebido: {data}")
        
        # Processar mensagem em background
        await QueueService.process_message(data)
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Erro no webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 