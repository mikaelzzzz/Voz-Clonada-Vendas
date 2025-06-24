import logging
import base64
import aiohttp
from app.config import settings

logger = logging.getLogger(__name__)

class ZAPIService:
    @staticmethod
    async def send_text(phone: str, message: str):
        """
        Envia mensagem de texto via Z-API
        """
        url = f"{settings.Z_API_BASE_URL}/send-text"
        headers = {
            "Content-Type": "application/json",
            "Client-Token": settings.Z_API_SECURITY_TOKEN
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

    @staticmethod
    async def send_audio(phone: str, audio_bytes: bytes):
        """
        Envia áudio via Z-API.
        O áudio deve estar em formato OGG ou MP3 (preferencialmente OGG para WhatsApp PTT).
        """
        url = f"{settings.Z_API_BASE_URL}/send-audio"
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
                "Client-Token": settings.Z_API_SECURITY_TOKEN
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