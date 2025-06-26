import os
import logging
import tempfile
from elevenlabs import generate, set_api_key
from app.config import settings

logger = logging.getLogger(__name__)

class ElevenLabsService:
    def __init__(self):
        set_api_key(settings.ELEVENLABS_API_KEY)

    def generate_audio(self, text: str) -> bytes:
        """
        Gera resposta em áudio usando ElevenLabs, otimizado para português brasileiro.
        
        Args:
            text: Texto para converter em áudio
            
        Returns:
            bytes: Áudio em formato MP3
        """
        try:
            logger.info("Gerando áudio com ElevenLabs")
            
            audio = generate(
                text=text,
                voice=settings.VOICE_ID,
                model="eleven_multilingual_v2"
            )
            
            logger.info("Áudio gerado com sucesso")
            return audio
            
        except Exception as e:
            logger.error(f"Erro ao gerar áudio: {str(e)}")
            raise 