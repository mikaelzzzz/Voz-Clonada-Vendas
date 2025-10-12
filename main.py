"""Flask service to handle messages via Zaia API and generate audio responses with ElevenLabs.

Endpoints:
GET  /          -> healthcheck
POST /tts       -> expects JSON { "text": "..." }  or { "messages": ["..."] }
                  returns { "audioBase64": "...", "mime": "audio/mpeg" }
POST /webhook   -> Zaia webhook endpoint
GET  /audio/<filename> -> Serve audio files

Env vars (can be set in .env):
ELEVENLABS_API_KEY    required
VOICE_ID              required (your cloned voice)
MODEL_ID              optional (default eleven_multilingual_v2)
STABILITY             optional float (0-1)
SIMILARITY            optional float (0-1)
PORT                  optional
SAVE_AUDIO            optional true/false (save mp3 in tmp/)
ZAIA_API_KEY          required (Bearer token for Zaia API)
ZAIA_AGENT_ID         required (Your agent's ID)
OPENAI_API_KEY        required (for Whisper transcription)
PUBLIC_URL            required (your server's public URL, e.g. https://your-server.com)
CLOUDINARY_URL        required (Cloudinary URL from dashboard)
Z_API_ID              required (Z-API instance ID)
Z_API_TOKEN           required (Z-API token)
Z_API_SECURITY_TOKEN  required (Z-API security token)
"""

import base64
import os
import uuid
import logging
from pathlib import Path
import json
import aiohttp
from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
from dotenv import load_dotenv
import tempfile
import cloudinary
import cloudinary.uploader
import cloudinary.api
from app.config.settings import Settings
from app.routes.webhook_routes import router as webhook_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load .env if present
load_dotenv()

app = FastAPI()

# CORS Middleware (opcional, mas recomendado para APIs)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuração do Cloudinary
settings = Settings()
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET
)

# Register routers
app.include_router(webhook_router, prefix="/webhook")

# Forçando reconstrução da imagem no Cloud Run
@app.get("/")
async def healthcheck():
    return {"status": "ok"}

@app.post("/tts")
async def text_to_speech(request: Request):
    try:
        data = await request.json()
        text = data.get("text", "")
        if not text and "messages" in data:
            text = " ".join(data["messages"])
        if not text:
            raise HTTPException(status_code=400, detail="No text provided")
        audio_content = generate_audio(text)
        if SAVE_AUDIO:
            filename = f"tmp/audio_{uuid.uuid4()}.mp3"
            with open(filename, "wb") as f:
                f.write(audio_content)
        audio_base64 = base64.b64encode(audio_content).decode()
        return {"audioBase64": audio_base64, "mime": "audio/mpeg"}
    except Exception as e:
        logger.error(f"Error in /tts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/audio/{filename}")
async def serve_audio(filename: str):
    file_path = AUDIO_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)

# Funções auxiliares (mantidas fora do app)
def generate_audio(text: str) -> bytes:
    """
    Generate audio using ElevenLabs API, optimized for Brazilian Portuguese.
    
    Args:
        text: Text to convert to speech (in Portuguese)
    Returns:
        bytes: MP3 audio content
    """
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVEN_API_KEY
    }

    # Configurações otimizadas para português brasileiro
    data = {
        "text": text,
        "model_id": MODEL_ID,
        "voice_settings": {
            "stability": STABILITY,
            "similarity_boost": SIMILARITY,
            "style": 0.35,               # Adiciona mais expressividade natural
            "use_speaker_boost": True    # Melhora a clareza da voz
        },
        "optimize_streaming_latency": 0,  # Prioriza qualidade sobre velocidade
        "voice_language": "pt-BR",       # Força idioma português brasileiro
        "language_id": "pt-BR"           # Força idioma português brasileiro
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code != 200:
            logger.error(f"ElevenLabs API error: {response.text}")
            raise Exception(f"ElevenLabs API error: {response.text}")
            
        return response.content
        
    except Exception as e:
        logger.error(f"Error generating audio: {str(e)}")
        raise



# Environment variables
ELEVEN_API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = os.getenv("VOICE_ID")
MODEL_ID = os.getenv("MODEL_ID", "eleven_multilingual_v2")
STABILITY = float(os.getenv("STABILITY", "0.5"))
SIMILARITY = float(os.getenv("SIMILARITY", "0.8"))
SAVE_AUDIO = os.getenv("SAVE_AUDIO", "false").lower() == "true"
AUDIO_DIR = Path("tmp")

# Zaia Configuration
ZAIA_API_KEY = os.getenv("ZAIA_API_KEY")
ZAIA_AGENT_ID = os.getenv("ZAIA_AGENT_ID")
ZAIA_API_URL = f"{settings.ZAIA_BASE_URL}/v1.1/api/message-cross-channel/create"

# OpenAI Configuration
import openai
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("Missing OPENAI_API_KEY environment variable")

openai_client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)

# Z-API Configuration
Z_API_ID = os.getenv("Z_API_ID")
Z_API_TOKEN = os.getenv("Z_API_TOKEN")
Z_API_SECURITY_TOKEN = os.getenv("Z_API_SECURITY_TOKEN")

# ElevenLabs configuration is handled via environment variable

if not all([ELEVEN_API_KEY, VOICE_ID, ZAIA_API_KEY, ZAIA_AGENT_ID, Z_API_ID, Z_API_TOKEN, Z_API_SECURITY_TOKEN]):
    raise ValueError("Missing required environment variables. Check .env file.")

# Create tmp directory if SAVE_AUDIO is enabled
if SAVE_AUDIO:
    Path("tmp").mkdir(exist_ok=True)

async def enviar_mensagem_zaia(channel: str, message: str = None, audio_url: str = None, image_url: str = None, **kwargs):
    """
    Envia mensagem via API da Zaia.
    
    Args:
        channel: Canal de envio ('whatsapp', 'instagram', 'widget', 'api', 'whatsapp_business')
        message: Texto da mensagem (opcional)
        audio_url: URL do áudio (opcional)
        image_url: URL da imagem (opcional)
        **kwargs: Parâmetros específicos do canal:
            - whatsapp/whatsapp_business: whatsAppPhoneNumber ou externalGenerativeChatId
            - instagram: externalRecipientId ou externalGenerativeChatId
            - widget: externalGenerativeChatId
            - api: externalGenerativeChatId ou externalGenerativeChatExternalId
    """
    headers = {
        "Authorization": f"Bearer {ZAIA_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "agentId": ZAIA_AGENT_ID,
        "channel": channel,
        **kwargs  # Inclui parâmetros específicos do canal
    }

    # Adiciona conteúdo se fornecido
    if message:
        payload["message"] = message
    if audio_url:
        payload["audioUrl"] = audio_url
    if image_url:
        payload["imageUrl"] = image_url

    async with aiohttp.ClientSession() as session:
        try:
            logger.info(f"Enviando mensagem via Zaia. Payload: {payload}")
            async with session.post(ZAIA_API_URL, headers=headers, json=payload) as response:
                response_text = await response.text()
                logger.info(f"Resposta da Zaia: Status={response.status}, Body={response_text}")
                
                if response.status == 200:
                    logger.info("Mensagem enviada com sucesso")
                    return {"success": True, "data": json.loads(response_text)}
                else:
                    error_text = f"Status: {response.status}, Response: {response_text}"
                    logger.error(f"Erro ao enviar mensagem: {error_text}")
                    return {"error": error_text}
        except Exception as e:
            logger.error(f"Exceção ao enviar mensagem: {str(e)}")
            return {"error": str(e)}

async def download_audio(url: str) -> str:
    """
    Download audio from URL and save to temporary file.
    
    Args:
        url: URL of the audio file
    Returns:
        str: Path to temporary file
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise Exception(f"Failed to download audio: {response.status}")
            
            # Create temporary file with .mp3 extension
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
            temp_file.close()
            
            # Write audio content to file
            with open(temp_file.name, 'wb') as f:
                f.write(await response.read())
            
            return temp_file.name

async def transcribe_audio(audio_path: str) -> str:
    """
    Transcribe audio file using OpenAI Whisper API.
    
    Args:
        audio_path: Path to audio file
    Returns:
        str: Transcribed text
    """
    try:
        with open(audio_path, "rb") as audio_file:
            logger.info("Iniciando transcrição com Whisper")
            transcript = await openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="pt",
                response_format="text"
            )
            logger.info(f"Transcrição concluída: {transcript}")
            return transcript
    except Exception as e:
        logger.error(f"Erro na transcrição: {str(e)}")
        raise
    finally:
        # Limpa o arquivo temporário
        try:
            os.unlink(audio_path)
        except:
            pass

def upload_to_cloudinary(audio_content: bytes) -> str:
    """
    Upload audio content to Cloudinary and return public URL.
    
    Args:
        audio_content: Audio file content in bytes
    Returns:
        str: Public URL for the audio file
    """
    try:
        # Cria um arquivo temporário para upload
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            temp_file.write(audio_content)
            temp_file.flush()
            
            # Upload para o Cloudinary
            logger.info("Iniciando upload para Cloudinary")
            result = cloudinary.uploader.upload(
                temp_file.name,
                resource_type="video",  # Cloudinary usa "video" para arquivos de áudio
                folder="karol_vendas_audio",  # Pasta personalizada no Cloudinary
                format="mp3",
                overwrite=True
            )
            logger.info(f"Upload concluído: {result['secure_url']}")
            
            # Retorna a URL segura (HTTPS)
            return result['secure_url']
    except Exception as e:
        logger.error(f"Erro no upload para Cloudinary: {str(e)}")
        raise
    finally:
        # Limpa o arquivo temporário
        try:
            os.unlink(temp_file.name)
        except:
            pass

async def send_to_zaia(message):
    """
    Envia mensagem para a Zaia e retorna a resposta
    """
    url = f"{settings.ZAIA_BASE_URL}/v1.1/api/external-generative-message/create"
    headers = {
        "Authorization": f"Bearer {ZAIA_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "message": message['text']['body'] if 'text' in message else message['transcript'],
        "channel": "whatsapp"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            return await response.json()

async def send_text_via_z_api(phone: str, message: str):
    """
    Envia mensagem de texto via Z-API
    """
    url = f"https://api.z-api.io/instances/{Z_API_ID}/token/{Z_API_TOKEN}/send-text"
    headers = {
        "Content-Type": "application/json",
        "Client-Token": Z_API_SECURITY_TOKEN
    }
    
    payload = {
        "phone": phone,
        "message": message
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            logger.info(f"Enviando mensagem para {phone}. URL: {url}")
            logger.info(f"Payload: {payload}")
            async with session.post(url, headers=headers, json=payload) as response:
                response_text = await response.text()
                logger.info(f"Resposta do Z-API: Status={response.status}, Body={response_text}")
                if response.status == 200:
                    logger.info(f"Mensagem enviada para {phone}")
                    return {"success": True}
                else:
                    error_text = f"Status: {response.status}, Response: {response_text}"
                    logger.error(f"Erro ao enviar mensagem: {error_text}")
                    return {"error": error_text}
        except Exception as e:
            logger.error(f"Exceção ao enviar mensagem: {str(e)}")
            return {"error": str(e)}

async def send_audio_via_z_api(phone: str, audio_bytes: bytes):
    """
    Envia áudio via Z-API.
    O áudio deve estar em formato OGG ou MP3 (preferencialmente OGG para WhatsApp PTT).
    """
    url = f"https://api.z-api.io/instances/{Z_API_ID}/token/{Z_API_TOKEN}/send-audio"
    try:
        # Codificar o áudio em base64 e adicionar o prefixo
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        audio_data_url = f"data:audio/ogg;base64,{audio_base64}"

        payload = {
            "phone": phone,
            "audio": audio_data_url,
            "viewOnce": False,
            "waveform": True
        }

        headers = {
            "Content-Type": "application/json",
            "Client-Token": Z_API_SECURITY_TOKEN
        }

        async with aiohttp.ClientSession() as session:
            logger.info(f"Enviando áudio para {phone}. URL: {url}")
            async with session.post(url, headers=headers, json=payload) as response:
                response_text = await response.text()
                logger.info(f"Resposta do Z-API (áudio): Status={response.status}, Body={response_text}")
                if response.status == 200:
                    logger.info(f"Áudio enviado para {phone}")
                    return {"success": True}
                else:
                    error_text = f"Status: {response.status}, Response: {response_text}"
                    logger.error(f"Erro ao enviar áudio: {error_text}")
                    return {"error": error_text}
    except Exception as e:
        logger.error(f"Exceção ao enviar áudio: {str(e)}")
        return {"error": str(e)}

async def process_audio_message(audio_url):
    """
    Processa mensagem de áudio: baixa, transcreve e retorna o texto
    """
    # Download do arquivo de áudio
    audio_response = requests.get(audio_url)
    
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio:
        temp_audio.write(audio_response.content)
        temp_audio_path = temp_audio.name
    
    try:
        # Transcreve o áudio usando OpenAI Whisper API
        with open(temp_audio_path, "rb") as audio_file:
            transcript = await openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="pt",
                response_format="text"
            )
        return transcript
    finally:
        # Remove o arquivo temporário
        os.unlink(temp_audio_path)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port) 