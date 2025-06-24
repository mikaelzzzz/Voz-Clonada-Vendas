import os
import logging
import tempfile
from elevenlabs import generate, save, set_api_key
from app.config import settings

logger = logging.getLogger(__name__)

class ElevenLabsService:
    def __init__(self):
        set_api_key(settings.ELEVENLABS_API_KEY)

    def generate_audio(self, text: str) -> bytes:
        """
        Gera resposta em áudio usando ElevenLabs e retorna os bytes do áudio
        """
        try:
            logger.info("Gerando áudio com ElevenLabs")
            audio = generate(
                text=text,
                voice=settings.VOICE_ID,
                model="eleven_multilingual_v2"
            )
            
            # Converte o áudio para bytes
            if isinstance(audio, bytes):
                return audio
            else:
                # Se o áudio não for bytes, salva temporariamente e lê os bytes
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio:
                    save(audio, temp_audio.name)
                    with open(temp_audio.name, 'rb') as f:
                        audio_bytes = f.read()
                    os.unlink(temp_audio.name)
                    return audio_bytes
        except Exception as e:
            logger.error(f"Erro ao gerar áudio: {str(e)}")
            raise 