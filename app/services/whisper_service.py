import os
import logging
import tempfile
import requests
import openai

logger = logging.getLogger(__name__)

class WhisperService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")

    def transcribe_audio(self, audio_url: str) -> str:
        """
        Processa mensagem de áudio: baixa, transcreve usando OpenAI Whisper API e retorna o texto
        """
        try:
            logger.info(f"Baixando áudio de {audio_url}")
            # Download do arquivo de áudio
            audio_response = requests.get(audio_url)
            
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio:
                temp_audio.write(audio_response.content)
                temp_audio_path = temp_audio.name
            
            logger.info("Transcrevendo áudio com OpenAI Whisper API")
            with open(temp_audio_path, "rb") as audio_file:
                transcript = openai.Audio.transcribe(
                    model="whisper-1",
                    file=audio_file,
                    api_key=self.api_key
                )
            # Remove o arquivo temporário
            os.unlink(temp_audio_path)
            
            logger.info(f"Transcrição concluída: {transcript['text']}")
            return transcript["text"]
        except Exception as e:
            logger.error(f"Erro ao transcrever áudio: {str(e)}")
            raise 