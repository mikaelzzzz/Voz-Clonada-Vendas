import os
import logging
import tempfile
import requests
import whisper

logger = logging.getLogger(__name__)

class WhisperService:
    def __init__(self):
        self.model = whisper.load_model("base")

    def transcribe_audio(self, audio_url: str) -> str:
        """
        Processa mensagem de áudio: baixa, transcreve e retorna o texto
        """
        try:
            logger.info(f"Baixando áudio de {audio_url}")
            # Download do arquivo de áudio
            audio_response = requests.get(audio_url)
            
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio:
                temp_audio.write(audio_response.content)
                temp_audio_path = temp_audio.name
            
            logger.info("Transcrevendo áudio com Whisper")
            # Transcreve o áudio
            result = self.model.transcribe(temp_audio_path)
            
            # Remove o arquivo temporário
            os.unlink(temp_audio_path)
            
            logger.info(f"Transcrição concluída: {result['text']}")
            return result["text"]
        except Exception as e:
            logger.error(f"Erro ao transcrever áudio: {str(e)}")
            raise 