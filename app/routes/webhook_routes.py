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

@router.post("")
async def handle_webhook(request: Request):
    try:
        data = await request.json()
        logger.info(f"Webhook recebido: {data}")

        # Verifica se é uma mensagem de áudio
        if data.get('type') == 'audio':
            # Adiciona à fila de processamento
            await queue_service.add_to_queue(data)
            
            # Envia mensagem de confirmação imediata
            await ZAPIService.send_text(
                phone=data['phone'],
                message="Recebi seu áudio! Estou processando e já te respondo..."
            )
            
            return JSONResponse({
                "status": "processing",
                "message": "Audio message queued for processing"
            })

        # Verifica se é uma mensagem
        if 'messages' in data:
            message = data['messages'][0]
            phone = message['from']
            
            # Processa áudio se for mensagem de áudio
            if message['type'] == 'audio':
                text = whisper_service.transcribe_audio(message['audio']['url'])
                message['transcript'] = text
            
            # Envia para Zaia
            zaia_response = await ZaiaService.send_message(message)
            
            # Gera resposta em áudio se a mensagem original era áudio
            if message['type'] == 'audio':
                audio_bytes = elevenlabs_service.generate_audio(zaia_response['message'])
                await ZAPIService.send_audio(phone, audio_bytes)
            else:
                await ZAPIService.send_text(phone, zaia_response['message'])
            
            return JSONResponse({"status": "success"})
        
        # Verifica se é uma notificação de status
        elif 'status' in data:
            # Processa status da mensagem (entregue, lida, etc)
            logger.info(f"Status update: {data['status']}")
            return JSONResponse({"status": "success"})
        
        # Verifica se é uma notificação de desconexão
        elif 'connected' in data and not data['connected']:
            # Processa desconexão
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