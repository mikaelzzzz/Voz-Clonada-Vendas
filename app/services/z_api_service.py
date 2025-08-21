import logging
import base64
import aiohttp
import asyncio
from app.config.settings import Settings
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)

class ZAPIService:
    @staticmethod
    def calculate_typing_duration(message: str) -> float:
        """
        Calcula o tempo de digitação baseado no tamanho da mensagem
        Simula uma velocidade de digitação humana realista, com máximo de 8 segundos.
        """
        # Velocidade média: ~40 palavras por minuto = ~200 caracteres por minuto
        chars_per_second = 3.3
        min_duration = 2.0  # Aumentado para ser mais perceptível
        max_duration = 8.0
        
        calculated_duration = len(message) / chars_per_second
        return max(min_duration, min(calculated_duration, max_duration))

    @staticmethod
    def calculate_audio_duration(message: str) -> float:
        """
        Calcula a duração da fala para uma mensagem de áudio.
        Assume uma velocidade média de fala.
        """
        # Velocidade média de fala: ~150 palavras por minuto. Uma palavra tem ~5 caracteres.
        # 150 * 5 = 750 caracteres por minuto / 60s = ~12.5 caracteres por segundo.
        chars_per_second = 12.5
        min_duration = 1.5  # Mínimo para parecer que gravou algo
        max_duration = 10.0 # Máximo para não deixar o usuário esperando muito
        
        calculated_duration = len(message) / chars_per_second
        return max(min_duration, min(calculated_duration, max_duration))

    @staticmethod
    async def send_text_with_context_delay(phone: str, message: str, context_delay: int = 30):
        """
        Envia mensagem de texto com delay de contexto para evitar perda de contexto.
        
        Este método é crucial para resolver o problema de mensagens quebradas.
        Quando o cliente envia mensagens em partes (ex: "Viagem" + "Vou pra Inglaterra"),
        este delay permite que o agente da Zaia processe cada parte adequadamente
        sem perder o contexto da conversa.
        
        Funcionamento:
        1. Aguarda o delay especificado (padrão: 30 segundos)
        2. Envia a mensagem com delay de digitação normal
        3. Preserva o contexto da conversa
        
        Args:
            phone: Número do telefone (normalizado com 55)
            message: Mensagem a ser enviada
            context_delay: Delay em segundos antes de enviar (padrão: 30s)
        """
        logger.info(f"Enviando mensagem com delay de contexto de {context_delay}s para {phone}")
        
        # Aguarda o delay de contexto
        await asyncio.sleep(context_delay)
        
        # Envia a mensagem com delay de digitação normal
        return await ZAPIService.send_text_with_typing(phone, message)

    @staticmethod
    async def send_text_with_typing(phone: str, message: str):
        """
        Envia mensagem de texto com simulação de digitação usando o delayTyping da Z-API.
        """
        # Respeitar override humano: não enviar mensagens automáticas
        if await CacheService.is_human_override_active(phone):
            logger.info(f"🛑 Override humano ativo para {phone}. Pulando envio de texto.")
            return {"skipped": "human_override_active"}
        typing_duration = ZAPIService.calculate_typing_duration(message)
        return await ZAPIService.send_text(phone, message, delay_typing=int(typing_duration))

    @staticmethod
    async def send_text(phone: str, message: str, delay_typing: int = None):
        """
        Envia mensagem de texto via Z-API, com suporte a delayTyping.
        """
        # Respeitar override humano: não enviar mensagens automáticas
        if await CacheService.is_human_override_active(phone):
            logger.info(f"🛑 Override humano ativo para {phone}. Pulando envio de texto.")
            return {"skipped": "human_override_active"}
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

        # Adiciona delayTyping se fornecido
        if delay_typing and delay_typing > 0:
            payload["delayTyping"] = delay_typing
        
        async with aiohttp.ClientSession() as session:
            try:
                logger.info(f"Enviando mensagem para {phone}. Payload: {payload}")
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
    async def send_audio_with_typing(phone: str, audio_bytes: bytes, original_text: str):
        """
        Envia áudio, usando um delayMessage variável baseado no texto original
        para simular o tempo de gravação.
        """
        # Respeitar override humano: não enviar mensagens automáticas
        if await CacheService.is_human_override_active(phone):
            logger.info(f"🛑 Override humano ativo para {phone}. Pulando envio de áudio.")
            return {"skipped": "human_override_active"}
        settings = Settings()
        url = f"{settings.Z_API_BASE_URL}/send-audio"
        headers = {
            "Content-Type": "application/json",
            "Client-Token": settings.Z_API_SECURITY_TOKEN
        }
        
        audio_data_url = f"data:audio/ogg;base64,{base64.b64encode(audio_bytes).decode('utf-8')}"
        
        # Calcula a duração da gravação com base no texto
        recording_duration = ZAPIService.calculate_audio_duration(original_text)

        payload = {
            "phone": phone,
            "audio": audio_data_url,
            "delayMessage": int(recording_duration),
            "waveform": True
        }
        
        try:
            logger.info(f"Enviando áudio para {phone}. Payload: {payload}")
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        logger.info(f"Áudio enviado para {phone}")
                        return {"success": True}
                    else:
                        error_text = await response.text()
                        logger.error(f"Erro ao enviar áudio: {response.status} - {error_text}")
                        return {"error": error_text}
        except Exception as e:
            logger.error(f"Exceção ao enviar áudio: {str(e)}")
            return {"error": str(e)}

    @staticmethod
    async def send_audio(phone: str, audio_bytes: bytes):
        """
        Envia áudio via Z-API sem delay (mantido para compatibilidade, se necessário).
        """
        # Respeitar override humano: não enviar mensagens automáticas
        if await CacheService.is_human_override_active(phone):
            logger.info(f"🛑 Override humano ativo para {phone}. Pulando envio de áudio.")
            return {"skipped": "human_override_active"}
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