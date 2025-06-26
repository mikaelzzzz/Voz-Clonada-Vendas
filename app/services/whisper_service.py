import os
import logging
import tempfile
import requests
from openai import OpenAI
import httpx

logger = logging.getLogger(__name__)

class WhisperService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        # Inicializa o cliente OpenAI com configuração explícita de httpx
        http_client = httpx.Client(
            timeout=60.0,
            follow_redirects=True
        )
        self.client = OpenAI(
            api_key=self.api_key,
            http_client=http_client
        )

    async def transcribe_audio(self, audio_url: str) -> str:
        """
        Processa mensagem de áudio: baixa, transcreve usando OpenAI Whisper API e retorna o texto
        """
        try:
            logger.info(f"Baixando áudio de {audio_url}")
            # Download do arquivo de áudio
            audio_response = requests.get(audio_url)
            audio_response.raise_for_status()  # Verifica se o download foi bem-sucedido
            
            # Determina a extensão do arquivo baseado no Content-Type ou URL
            content_type = audio_response.headers.get('content-type', '')
            if 'ogg' in content_type or audio_url.endswith('.ogg'):
                suffix = ".ogg"
            elif 'mp3' in content_type or audio_url.endswith('.mp3'):
                suffix = ".mp3"
            elif 'wav' in content_type or audio_url.endswith('.wav'):
                suffix = ".wav"
            else:
                suffix = ".ogg"  # Padrão para Z-API
            
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_audio:
                temp_audio.write(audio_response.content)
                temp_audio_path = temp_audio.name
            
            logger.info(f"Transcrevendo áudio com OpenAI Whisper API (arquivo: {suffix})")
            with open(temp_audio_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="pt"  # Especifica português para melhor precisão
                )
            
            # Remove o arquivo temporário
            os.unlink(temp_audio_path)
            
            logger.info(f"Transcrição concluída: {transcript.text}")
            return transcript.text
            
        except Exception as e:
            logger.error(f"Erro ao transcrever áudio: {str(e)}")
            # Limpa arquivo temporário em caso de erro
            try:
                if 'temp_audio_path' in locals():
                    os.unlink(temp_audio_path)
            except:
                pass
            raise 