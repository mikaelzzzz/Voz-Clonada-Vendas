import os
from dotenv import load_dotenv
from pydantic import computed_field
from pydantic_settings import BaseSettings
from typing import List

# Carrega variáveis de ambiente
load_dotenv()

# ElevenLabs
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
VOICE_ID = os.getenv('VOICE_ID', 'ie5yJLYeLpsuijLaojmF')

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

class Settings(BaseSettings):
    # Configurações da aplicação
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Configurações do Z-API
    Z_API_INSTANCE_ID: str = os.getenv("Z_API_INSTANCE_ID", "")
    Z_API_TOKEN: str = os.getenv("Z_API_TOKEN", "")
    Z_API_SECURITY_TOKEN: str = os.getenv("Z_API_SECURITY_TOKEN", "")
    Z_API_BASE_URL: str = f"https://api.z-api.io/instances/{os.getenv('Z_API_ID', '')}/token/{os.getenv('Z_API_TOKEN', '')}"
    
    # Configurações da Zaia
    ZAIA_BASE_URL: str = os.getenv("ZAIA_BASE_URL", "https://api.zaia.app")
    ZAIA_API_KEY: str = os.getenv("ZAIA_API_KEY", "")
    ZAIA_AGENT_ID: str = os.getenv("ZAIA_AGENT_ID", "")
    
    # Configurações do OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # Configurações do ElevenLabs
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
    ELEVENLABS_VOICE_ID: str = os.getenv("ELEVENLABS_VOICE_ID", "ie5yJLYeLpsuijLaojmF")
    
    # Configurações do Cloudinary
    CLOUDINARY_CLOUD_NAME: str = os.getenv("CLOUDINARY_CLOUD_NAME", "")
    CLOUDINARY_API_KEY: str = os.getenv("CLOUDINARY_API_KEY", "")
    CLOUDINARY_API_SECRET: str = os.getenv("CLOUDINARY_API_SECRET", "")
    
    # Compatibilidade com código legado
    @property
    def VOICE_ID(self) -> str:
        return self.ELEVENLABS_VOICE_ID
    
    # Configurações do Redis para cache distribuído
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_ENABLED: bool = os.getenv("REDIS_ENABLED", "False").lower() == "true"
    
    # Notion
    NOTION_API_KEY: str = os.getenv("NOTION_API_KEY")
    NOTION_DATABASE_ID: str = os.getenv("NOTION_DATABASE_ID")

    # Sales Team: lê a variável como uma string para evitar erros de parse
    SALES_TEAM_PHONES_STR: str = os.getenv("SALES_TEAM_PHONES", "5511975578651,5511957708562,5511955911993")

    @computed_field
    @property
    def SALES_TEAM_PHONES(self) -> List[str]:
        """Converte a string de telefones em uma lista, de forma segura."""
        if not self.SALES_TEAM_PHONES_STR:
            return []
        return [p.strip() for p in self.SALES_TEAM_PHONES_STR.split(',') if p.strip()]

    @property
    def is_redis_enabled(self) -> bool:
        return self.REDIS_ENABLED

    class Config:
        env_file = ".env"

settings = Settings() 