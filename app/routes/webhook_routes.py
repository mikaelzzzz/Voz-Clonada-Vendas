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
                # 1. Transcreve o áudio
                transcript = await whisper_service.transcribe_audio(message['audio']['url'])
                logger.info(f"Áudio transcrito: {transcript}")
                
                # 2. Envia transcrição para Zaia
                zaia_response = await zaia_service.send_message({
                    'transcript': transcript,
                    'phone': phone
                })
                
                # 3. Gera resposta em áudio usando voz clonada
                audio_bytes = elevenlabs_service.generate_audio(zaia_response['message'])
                
                # 4. Envia resposta em áudio
                await ZAPIService.send_audio(phone, audio_bytes)
                
            elif message['type'] == 'text':
                # 1. Envia texto para Zaia
                zaia_response = await zaia_service.send_message({
                    'text': {'body': message['text']['body']},
                    'phone': phone
                })
                
                # 2. Envia resposta em texto
                await ZAPIService.send_text(phone, zaia_response['message'])
            
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
        logger.error(f"Erro ao processar webhook: {str(e)}")
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