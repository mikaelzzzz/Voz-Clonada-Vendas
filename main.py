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
from flask import Flask, request, jsonify, send_from_directory
import requests
from dotenv import load_dotenv
from openai import OpenAI
import tempfile
import cloudinary
import cloudinary.uploader
import cloudinary.api
from elevenlabs import generate, save, set_api_key
import whisper
from io import BytesIO
from app.config import settings
from app.routes.webhook_routes import webhook_bp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load .env if present
load_dotenv()

def create_app():
    """
    Cria e configura a aplicação Flask
    """
    app = Flask(__name__)
    
    # Configuração do Cloudinary
    cloudinary.config(**settings.CLOUDINARY_CONFIG)
    
    # Registra as rotas
    app.register_blueprint(webhook_bp, url_prefix='/webhook')
    
    return app

# Environment variables
ELEVEN_API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = os.getenv("VOICE_ID")
MODEL_ID = os.getenv("MODEL_ID", "eleven_multilingual_v2")
STABILITY = float(os.getenv("STABILITY", "0.5"))
SIMILARITY = float(os.getenv("SIMILARITY", "0.8"))
SAVE_AUDIO = os.getenv("SAVE_AUDIO", "false").lower() == "true"

# Zaia Configuration
ZAIA_API_KEY = os.getenv("ZAIA_API_KEY")
ZAIA_AGENT_ID = os.getenv("ZAIA_AGENT_ID")
ZAIA_API_URL = "https://core-service.zaia.app/v1.1/api/message-cross-channel/create"

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("Missing OPENAI_API_KEY environment variable")

openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Public URL Configuration
PUBLIC_URL = os.getenv("PUBLIC_URL")
if not PUBLIC_URL:
    raise ValueError("Missing PUBLIC_URL environment variable")

# Ensure audio directory exists
AUDIO_DIR = Path("audio_files")
AUDIO_DIR.mkdir(exist_ok=True)

# Z-API Configuration
Z_API_ID = os.getenv("Z_API_ID")
Z_API_TOKEN = os.getenv("Z_API_TOKEN")
Z_API_SECURITY_TOKEN = os.getenv("Z_API_SECURITY_TOKEN")

# Configuração do ElevenLabs
set_api_key(ELEVEN_API_KEY)

# Modelo Whisper para transcrição
model = whisper.load_model("base")

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
    url = f"https://api.zaia.app/v1.1/api/chat/{ZAIA_AGENT_ID}/message"
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

def process_audio_message(audio_url):
    """
    Processa mensagem de áudio: baixa, transcreve e retorna o texto
    """
    # Download do arquivo de áudio
    audio_response = requests.get(audio_url)
    
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio:
        temp_audio.write(audio_response.content)
        temp_audio_path = temp_audio.name
    
    # Transcreve o áudio
    result = model.transcribe(temp_audio_path)
    
    # Remove o arquivo temporário
    os.unlink(temp_audio_path)
    
    return result["text"]

def generate_audio_response(text):
    """
    Gera resposta em áudio usando ElevenLabs e retorna os bytes do áudio
    """
    audio = generate(
        text=text,
        voice=VOICE_ID,
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

@APP.route("/", methods=["GET"])
def healthcheck():
    """Health check endpoint."""
    return jsonify({"status": "ok"})

@APP.route("/tts", methods=["POST"])
def text_to_speech():
    """Generate audio from text using ElevenLabs."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data received"}), 400
            
        # Handle single text or array of messages
        text = data.get("text", "")
        if not text and "messages" in data:
            text = " ".join(data["messages"])
            
        if not text:
            return jsonify({"error": "No text provided"}), 400
            
        # Generate audio
        audio_content = generate_audio(text)
        
        # Save file if enabled
        if SAVE_AUDIO:
            filename = f"tmp/audio_{uuid.uuid4()}.mp3"
            with open(filename, "wb") as f:
                f.write(audio_content)
                
        # Convert to base64
        audio_base64 = base64.b64encode(audio_content).decode()
        
        return jsonify({
            "audioBase64": audio_base64,
            "mime": "audio/mpeg"
        })
        
    except Exception as e:
        logger.error(f"Error in /tts: {str(e)}")
        return jsonify({"error": str(e)}), 500

@APP.route("/audio/<filename>")
def serve_audio(filename):
    """Serve audio files from audio_files directory."""
    return send_from_directory(AUDIO_DIR, filename)

def save_audio_file(audio_content: bytes) -> str:
    """
    Save audio content to file and return public URL.
    
    Args:
        audio_content: Audio file content in bytes
    Returns:
        str: Public URL for the audio file
    """
    filename = f"audio_{uuid.uuid4()}.mp3"
    filepath = AUDIO_DIR / filename
    
    with open(filepath, "wb") as f:
        f.write(audio_content)
        
    return f"{PUBLIC_URL}/audio/{filename}"

@APP.route("/webhook", methods=["POST"])
async def webhook_zaia():
    """Handle incoming messages from Zaia webhook."""
    try:
        payload = request.get_json()
        
        if not payload:
            return jsonify({"error": "No data received"}), 400

        # Extrai informações da mensagem
        channel = payload.get("channel")
        chat_id = payload.get("externalGenerativeChatId")
        phone = payload.get("whatsAppPhoneNumber")
        recipient_id = payload.get("externalRecipientId")
        message_type = payload.get("type", "text")
        
        # Parâmetros específicos do canal
        channel_params = {}
        if channel in ["whatsapp", "whatsapp_business"]:
            if phone:
                channel_params["whatsAppPhoneNumber"] = phone
            if chat_id:
                channel_params["externalGenerativeChatId"] = chat_id
        elif channel == "instagram":
            if recipient_id:
                channel_params["externalRecipientId"] = recipient_id
            if chat_id:
                channel_params["externalGenerativeChatId"] = chat_id
        elif channel in ["widget", "api"]:
            if chat_id:
                channel_params["externalGenerativeChatId"] = chat_id

        # Processa a mensagem de acordo com o tipo
        if message_type == "text":
            texto = payload.get("text", "")
            if texto:
                # Para mensagens de texto, responde com texto
                await enviar_mensagem_zaia(
                    channel=channel,
                    message=texto,  # Envia o texto diretamente
                    **channel_params
                )
                
        elif message_type == "audio":
            audio_url = payload.get("audioUrl")
            if audio_url:
                try:
                    # Download do áudio
                    audio_path = await download_audio(audio_url)
                    
                    # Transcreve o áudio para texto usando Whisper
                    texto_transcrito = await transcribe_audio(audio_path)
                    logger.info(f"Áudio transcrito: {texto_transcrito}")
                    
                    # Gera resposta em áudio usando a voz clonada
                    audio_bytes = generate_audio_response(texto_transcrito)
                    logger.info(f"Áudio enviado para Cloudinary: {audio_url}")
                    
                    # Envia resposta em áudio
                    await enviar_mensagem_zaia(
                        channel=channel,
                        audio_url=audio_url,
                        **channel_params
                    )
                except Exception as e:
                    logger.error(f"Erro ao processar áudio: {str(e)}")
                    # Em caso de erro, envia mensagem de texto explicando
                    await enviar_mensagem_zaia(
                        channel=channel,
                        message="Desculpe, tive um problema ao processar seu áudio. Pode tentar novamente?",
                        **channel_params
                    )
        
        return jsonify({"status": "ok"})
        
    except Exception as e:
        logger.error(f"Error in webhook: {str(e)}")
        return jsonify({"error": str(e)}), 500

@APP.route('/webhook/z-api', methods=['POST'])
async def z_api_webhook():
    """
    Webhook para receber mensagens da Z-API
    """
    try:
        data = request.json
        
        # Verifica se é uma mensagem
        if 'messages' in data:
            message = data['messages'][0]
            phone = message['from']
            
            # Processa áudio se for mensagem de áudio
            if message['type'] == 'audio':
                text = process_audio_message(message['audio']['url'])
                message['transcript'] = text
            
            # Envia para Zaia
            zaia_response = await send_to_zaia(message)
            
            # Gera resposta em áudio se a mensagem original era áudio
            if message['type'] == 'audio':
                audio_bytes = generate_audio_response(zaia_response['message'])
                await send_audio_via_z_api(phone, audio_bytes)
            else:
                await send_text_via_z_api(phone, zaia_response['message'])
            
            return jsonify({"status": "success"})
        
        # Verifica se é uma notificação de status
        elif 'status' in data:
            # Processa status da mensagem (entregue, lida, etc)
            logger.info(f"Status update: {data['status']}")
            return jsonify({"status": "success"})
        
        # Verifica se é uma notificação de desconexão
        elif 'connected' in data and not data['connected']:
            # Processa desconexão
            logger.info("Z-API disconnected")
            return jsonify({"status": "success"})
            
        return jsonify({"status": "unknown_event"})
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@APP.route('/health', methods=['GET'])
def health_check():
    """
    Endpoint para verificar se o servidor está funcionando
    """
    return jsonify({"status": "healthy"})

if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", 3000))
    app.run(host="0.0.0.0", port=port)

app = create_app() 