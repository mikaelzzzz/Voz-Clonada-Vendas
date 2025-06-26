import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# ElevenLabs
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
VOICE_ID = os.getenv('VOICE_ID')

# Zaia
ZAIA_API_KEY = os.getenv('ZAIA_API_KEY')
ZAIA_AGENT_ID = os.getenv('ZAIA_AGENT_ID')
ZAIA_BASE_URL = os.getenv('ZAIA_BASE_URL', 'https://api.zaia.app')

# Z-API
Z_API_ID = os.getenv('Z_API_ID')
Z_API_TOKEN = os.getenv('Z_API_TOKEN')
Z_API_SECURITY_TOKEN = os.getenv('Z_API_SECURITY_TOKEN')

# Cloudinary
CLOUDINARY_CONFIG = {
    'cloud_name': os.getenv('CLOUDINARY_CLOUD_NAME'),
    'api_key': os.getenv('CLOUDINARY_API_KEY'),
    'api_secret': os.getenv('CLOUDINARY_API_SECRET')
}

# URLs base
Z_API_BASE_URL = f"https://api.z-api.io/instances/{Z_API_ID}/token/{Z_API_TOKEN}"

# Configurações do servidor
PORT = int(os.getenv('PORT', 5000)) 