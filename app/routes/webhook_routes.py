import logging
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from app.services.z_api_service import ZAPIService
from app.services.zaia_service import ZaiaService
from app.services.elevenlabs_service import ElevenLabsService
from app.services.whisper_service import WhisperService
from app.services.queue_service import queue_service

logger = logging.getLogger(__name__)

router = APIRouter()

# Instancia os serviços
elevenlabs_service = ElevenLabsService()
whisper_service = WhisperService()
zaia_service = ZaiaService()

@router.post("")
async def handle_webhook(request: Request):
    try:
        data = await request.json()
        logger.info(f"Webhook recebido: {data}")

        # Verifica se é uma mensagem
        if 'messages' in data:
            message = data['messages'][0]
            phone = message['from']
            
            # Processa baseado no tipo de mensagem
            if message['type'] == 'audio':
                try:
                    logger.info(f"Processando mensagem de áudio de {phone}")
                    
                    # 1. Transcreve o áudio
                    transcript = await whisper_service.transcribe_audio(message['audio']['url'])
                    logger.info(f"Áudio transcrito: {transcript}")
                    
                    # 2. Envia transcrição para Zaia (formato correto)
                    message_data = {
                        'transcript': transcript,
                        'phone': phone
                    }
                    zaia_response = await zaia_service.send_message(message_data)
                    logger.info(f"Resposta da Zaia recebida: {zaia_response}")
                    
                    # 3. Verifica se há mensagem na resposta
                    if 'message' in zaia_response and zaia_response['message']:
                        # 4. Gera resposta em áudio usando voz clonada
                        audio_bytes = elevenlabs_service.generate_audio(zaia_response['message'])
                        
                        # 5. Envia resposta em áudio
                        await ZAPIService.send_audio(phone, audio_bytes)
                        logger.info(f"Áudio enviado para {phone}")
                    else:
                        logger.warning(f"Zaia não retornou mensagem válida: {zaia_response}")
                        
                except Exception as e:
                    logger.error(f"Erro ao processar áudio: {str(e)}")
                    # Envia mensagem de erro em texto
                    await ZAPIService.send_text(phone, "Desculpe, ocorreu um erro ao processar seu áudio.")
                
            elif message['type'] == 'text':
                try:
                    logger.info(f"Processando mensagem de texto de {phone}: {message['text']['body']}")
                    
                    # 1. Envia texto para Zaia (formato correto)
                    message_data = {
                        'text': {'body': message['text']['body']},
                        'phone': phone
                    }
                    zaia_response = await zaia_service.send_message(message_data)
                    logger.info(f"Resposta da Zaia recebida: {zaia_response}")
                    
                    # 2. Verifica se há mensagem na resposta
                    if 'message' in zaia_response and zaia_response['message']:
                        # 3. Envia resposta em texto
                        await ZAPIService.send_text(phone, zaia_response['message'])
                        logger.info(f"Texto enviado para {phone}")
                    else:
                        logger.warning(f"Zaia não retornou mensagem válida: {zaia_response}")
                        
                except Exception as e:
                    logger.error(f"Erro ao processar texto: {str(e)}")
                    # Envia mensagem de erro
                    await ZAPIService.send_text(phone, "Desculpe, ocorreu um erro ao processar sua mensagem.")
            
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
def health_check():
    """
    Endpoint para verificar se o servidor está funcionando
    """
    return {"status": "healthy"} 