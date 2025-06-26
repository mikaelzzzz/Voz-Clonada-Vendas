import os
import logging
import requests
from app.config import settings

logger = logging.getLogger(__name__)

class ElevenLabsService:
    def __init__(self):
        self.api_key = settings.ELEVENLABS_API_KEY
        self.voice_id = settings.VOICE_ID
        self.model_id = "eleven_multilingual_v2"
        
        # Configurações otimizadas para português brasileiro
        self.voice_settings = {
            "stability": 0.6,           # Estabilidade (0-1) - mais alto = mais consistente
            "similarity_boost": 0.85,   # Similaridade com voz original (0-1)
            "style": 0.25,              # Estilo/expressividade (0-1)
            "use_speaker_boost": True,  # Melhora clareza e consistência
            "speed": 1.15               # Velocidade da fala (0.25-4.0) - mais rápido
        }

    def generate_audio(self, text: str) -> bytes:
        """
        Gera resposta em áudio usando ElevenLabs API REST, otimizado para português brasileiro.
        Configurado para velocidade mais rápida e volume consistente.
        
        Args:
            text: Texto para converter em áudio
            
        Returns:
            bytes: Áudio em formato MP3
        """
        try:
            logger.info(f"Gerando áudio com ElevenLabs (velocidade: {self.voice_settings['speed']}x)")
            
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
            
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.api_key
            }

            # Payload com configurações otimizadas
            data = {
                "text": text,
                "model_id": self.model_id,
                "voice_settings": self.voice_settings,
                "optimize_streaming_latency": 0,  # Prioriza qualidade
                "output_format": "mp3_44100_128",  # Qualidade consistente
                "apply_text_normalization": "auto"  # Normalização automática
            }

            response = requests.post(url, json=data, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"ElevenLabs API error: {response.text}")
                raise Exception(f"ElevenLabs API error: {response.text}")
                
            logger.info("Áudio gerado com sucesso (velocidade otimizada)")
            return response.content
            
        except Exception as e:
            logger.error(f"Erro ao gerar áudio: {str(e)}")
            raise 