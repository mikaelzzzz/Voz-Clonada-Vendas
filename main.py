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

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.routes.webhook_routes import router as webhook_router

# Carrega variáveis de ambiente do .env (se existir)
load_dotenv()

# Configura o logging básico
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cria a aplicação FastAPI
app = FastAPI(
    title="KarolVendas AI Agent",
    description="Serviço para automatizar conversas de vendas com IA.",
    version="1.0.0"
)

# Configura o CORS para permitir todas as origens (útil para desenvolvimento e APIs públicas)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rota de Health Check para o Render
@app.get("/", tags=["Health Check"])
async def health_check():
    """
    Verifica se o serviço está no ar. O Render usa esta rota para o Health Check.
    """
    logger.info("Health check solicitado.")
    return {"status": "ok", "message": "Service is running"}

# Inclui o roteador principal que contém toda a lógica de webhooks
app.include_router(webhook_router, prefix="/webhook", tags=["Webhooks"])

logger.info("Aplicação iniciada com sucesso.") 