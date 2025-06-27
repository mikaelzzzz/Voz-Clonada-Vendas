import logging
import base64
import aiohttp
import asyncio
from app.config.settings import Settings

logger = logging.getLogger(__name__)

class ZAPIService:
    @staticmethod
    async def start_typing(phone: str):
        """
        Simula que está digitando no WhatsApp
        """
        settings = Settings()
        url = f"{settings.Z_API_BASE_URL}/send-chat-state"
        headers = {
            "Content-Type": "application/json",
            "Client-Token": settings.Z_API_SECURITY_TOKEN
        }
        
        payload = {
            "phone": phone,
            "chatState": "typing"
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                logger.info(f"Iniciando status 'digitando' para {phone}")
                async with session.post(url, headers=headers, json=payload) as response:
                    response_text = await response.text()
                    logger.info(f"Resposta do Z-API (typing): Status={response.status}, Body={response_text}")
                    if response.status == 200:
                        logger.info(f"Status 'digitando' ativado para {phone}")
                        return {"success": True}
                    else:
                        error_text = f"Status: {response.status}, Response: {response_text}"
                        logger.error(f"Erro ao ativar status 'digitando': {error_text}")
                        return {"error": error_text}
            except Exception as e:
                logger.error(f"Exceção ao ativar status 'digitando': {str(e)}")
                return {"error": str(e)}

    @staticmethod
    async def stop_typing(phone: str):
        """
        Para de simular que está digitando no WhatsApp
        """
        settings = Settings()
        url = f"{settings.Z_API_BASE_URL}/send-chat-state"
        headers = {
            "Content-Type": "application/json",
            "Client-Token": settings.Z_API_SECURITY_TOKEN
        }
        
        payload = {
            "phone": phone,
            "chatState": "available"
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                logger.info(f"Parando status 'digitando' para {phone}")
                async with session.post(url, headers=headers, json=payload) as response:
                    response_text = await response.text()
                    logger.info(f"Resposta do Z-API (stop typing): Status={response.status}, Body={response_text}")
                    return {"success": True}
            except Exception as e:
                logger.error(f"Exceção ao parar status 'digitando': {str(e)}")
                return {"error": str(e)}

    @staticmethod
    def calculate_typing_duration(message: str) -> float:
        """
        Calcula o tempo de digitação baseado no tamanho da mensagem
        Simula uma velocidade de digitação humana realista
        """
        # Velocidade média de digitação: ~40 palavras por minuto = ~200 caracteres por minuto
        # Isso equivale a ~3.3 caracteres por segundo
        chars_per_second = 3.3
        
        # Tempo base mínimo e máximo
        min_duration = 1.0  # 1 segundo mínimo
        max_duration = 8.0  # 8 segundos máximo
        
        # Calcula baseado no tamanho da mensagem
        calculated_duration = len(message) / chars_per_second
        
        # Aplica os limites
        return max(min_duration, min(calculated_duration, max_duration))

    @staticmethod
    async def send_text_with_typing(phone: str, message: str, typing_duration: float = None):
        """
        Envia mensagem de texto com simulação de digitação
        Se typing_duration não for especificado, calcula automaticamente baseado no tamanho da mensagem
        """
        if typing_duration is None:
            typing_duration = ZAPIService.calculate_typing_duration(message)
        
        # Simula que está digitando
        await ZAPIService.start_typing(phone)
        
        # Aguarda um tempo simulando a digitação
        await asyncio.sleep(typing_duration)
        
        # Para de simular digitação e envia a mensagem
        await ZAPIService.stop_typing(phone)
        return await ZAPIService.send_text(phone, message)

    @staticmethod
    async def send_text(phone: str, message: str):
        """
        Envia mensagem de texto via Z-API
        """
        settings = Settings()
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
    async def send_audio_with_typing(phone: str, audio_bytes: bytes, typing_duration: float = 1.5):
        """
        Envia áudio com simulação de digitação/gravação
        """
        # Para áudio, simula que está gravando
        settings = Settings()
        url = f"{settings.Z_API_BASE_URL}/send-chat-state"
        headers = {
            "Content-Type": "application/json",
            "Client-Token": settings.Z_API_SECURITY_TOKEN
        }
        
        payload = {
            "phone": phone,
            "chatState": "recording"
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                logger.info(f"Iniciando status 'gravando' para {phone}")
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        logger.info(f"Status 'gravando' ativado para {phone}")
                    
                    # Aguarda simulando a gravação
                    await asyncio.sleep(typing_duration)
                    
                    # Para de simular gravação
                    payload["chatState"] = "available"
                    await session.post(url, headers=headers, json=payload)
                    
            except Exception as e:
                logger.error(f"Erro ao simular gravação: {str(e)}")
        
        # Envia o áudio
        return await ZAPIService.send_audio(phone, audio_bytes)

    @staticmethod
    async def send_audio(phone: str, audio_bytes: bytes):
        """
        Envia áudio via Z-API.
        O áudio deve estar em formato OGG ou MP3 (preferencialmente OGG para WhatsApp PTT).
        """
        settings = Settings()
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