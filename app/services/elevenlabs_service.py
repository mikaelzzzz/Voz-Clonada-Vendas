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
        Gera resposta em áudio usando ElevenLabs, otimizado para português brasileiro.
        
        Args:
            text: Texto para converter em áudio
            
        Returns:
            bytes: Áudio em formato MP3
        """
        try:
            logger.info("Gerando áudio com ElevenLabs")
            
            # Configurações otimizadas para português brasileiro
            voice_settings = {
                "stability": 0.5,  # Equilíbrio entre estabilidade e naturalidade
                "similarity_boost": 0.8,  # Alta fidelidade à voz original
                "style": 0.35,  # Adiciona expressividade natural
                "use_speaker_boost": True  # Melhora a clareza da voz
            }
            
            audio = self.client.generate(
                text=text,
                voice=settings.VOICE_ID,
                model="eleven_multilingual_v2",
                voice_settings=voice_settings
            )
            
            logger.info("Áudio gerado com sucesso")
            return audio
            
        except Exception as e:
            logger.error(f"Erro ao gerar áudio: {str(e)}")
            raise 