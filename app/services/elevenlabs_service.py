import os
import logging
import tempfile
from elevenlabs.client import ElevenLabs
from app.config import settings

logger = logging.getLogger(__name__)

class ElevenLabsService:
    def __init__(self):
        self.client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)

    def generate_audio(self, text: str) -> bytes:
        """
        Gera resposta em áudio usando ElevenLabs e retorna os bytes do áudio
        """
        try:
            logger.info("Gerando áudio com ElevenLabs")
            audio = self.client.generate(
                text=text,
                voice=settings.VOICE_ID,
                model="eleven_multilingual_v2"
            )
            # O método já retorna bytes
            return audio
        except Exception as e:
            logger.error(f"Erro ao gerar áudio: {str(e)}")
            raise 