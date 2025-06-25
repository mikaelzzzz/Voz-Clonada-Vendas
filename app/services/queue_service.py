import asyncio
import logging
from typing import Dict, Any
from collections import deque

logger = logging.getLogger(__name__)

class QueueService:
    def __init__(self):
        self.processing_queue = deque()
        self.is_processing = False

    async def add_to_queue(self, task_data: Dict[str, Any]):
        """
        Adiciona uma tarefa à fila de processamento
        """
        self.processing_queue.append(task_data)
        logger.info(f"Tarefa adicionada à fila. Total na fila: {len(self.processing_queue)}")
        
        if not self.is_processing:
            asyncio.create_task(self.process_queue())

    async def process_queue(self):
        """
        Processa as tarefas na fila
        """
        if self.is_processing:
            return

        self.is_processing = True
        
        try:
            while self.processing_queue:
                task_data = self.processing_queue.popleft()
                await self.process_task(task_data)
        finally:
            self.is_processing = False

    async def process_task(self, task_data: Dict[str, Any]):
        """
        Processa uma tarefa individual
        """
        try:
            from app.services.whisper_service import WhisperService
            from app.services.zaia_service import ZaiaService
            from app.services.elevenlabs_service import ElevenLabsService
            from app.services.z_api_service import ZAPIService

            logger.info(f"Processando tarefa: {task_data}")
            
            # 1. Transcrição do áudio
            audio_url = task_data['audio']['url']
            transcript = await WhisperService().transcribe_audio(audio_url)
            
            # 2. Processamento na Zaia
            message = {
                'transcript': transcript,
                'chat_id': task_data.get('chat_id')
            }
            zaia_response = await ZaiaService.send_message(message)
            
            elevenlabs_service = ElevenLabsService()
            # 3. Geração do áudio de resposta
            audio_response = elevenlabs_service.generate_audio(zaia_response['message'])
            
            # 4. Envio da resposta
            await ZAPIService.send_audio(
                phone=task_data['phone'],
                audio_url=audio_response['audio_url']
            )
            
            logger.info(f"Tarefa processada com sucesso para {task_data['phone']}")
            
        except Exception as e:
            logger.error(f"Erro ao processar tarefa: {str(e)}")
            # Envia mensagem de erro para o usuário
            try:
                await ZAPIService.send_text(
                    phone=task_data['phone'],
                    message="Desculpe, tive um problema ao processar sua mensagem. Por favor, tente novamente."
                )
            except Exception as send_error:
                logger.error(f"Erro ao enviar mensagem de erro: {str(send_error)}")

queue_service = QueueService() 