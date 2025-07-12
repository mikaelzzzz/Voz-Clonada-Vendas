import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.services.z_api_service import ZAPIService
from app.services.zaia_service import ZaiaService
from app.services.elevenlabs_service import ElevenLabsService
from app.services.whisper_service import WhisperService
from app.services.notion_service import NotionService
from app.services.openai_service import OpenAIService
from app.config.settings import Settings
from app.services.qualification_service import QualificationService


logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("")
async def handle_webhook(request: Request):
    data = await request.json()
    logger.info(f"Webhook recebido: {data}")

    # Rota 1: Webhook de Qualificação de Lead da Zaia
    if 'profissao' in data and 'motivo' in data and 'whatsapp' in data:
        phone = data.get('whatsapp')

        # Validação para garantir que a variável da Zaia foi substituída
        if not phone or '{{' in str(phone):
            error_msg = f"Webhook de qualificação recebido com telefone inválido: {phone}"
            logger.error(error_msg)
            return JSONResponse({"status": "invalid_phone_variable", "detail": error_msg}, status_code=400)

        profissao = data.get('profissao')
        motivo = data.get('motivo')
        logger.info(f"Processando qualificação de lead para {phone}")

        try:
            notion_service = NotionService()
            openai_service = OpenAIService()
            qualification_service = QualificationService()
            settings = Settings()

            # 1. Classifica o lead
            qualification_level = await qualification_service.classify_lead(motivo, profissao)
            logger.info(f"Lead {phone} classificado como: {qualification_level}")

            # 2. Atualiza o Notion com todas as informações
            updates = {
                "Profissão": profissao,
                "Real Motivação": motivo,
                "Status": "Qualificado pela IA",
                "Nível de Qualificação": qualification_level
            }
            notion_service.update_lead_properties(phone, updates)
            
            # 3. Se for de alta prioridade, gera e envia a análise de vendas
            if qualification_level == 'Alto':
                logger.info(f"Lead {phone} é de alta prioridade. Gerando alerta para equipe de vendas.")
                lead_data = notion_service.get_lead_data_by_phone(phone)

                if lead_data:
                    sales_message = await openai_service.generate_sales_message(lead_data)
                    for sales_phone in settings.SALES_TEAM_PHONES:
                        await ZAPIService.send_text(sales_phone, sales_message)
                    logger.info(f"Alerta de vendas para o lead {phone} enviado com sucesso.")
                else:
                    logger.warning(f"Não foi possível encontrar dados do lead {phone} para gerar alerta.")
            else:
                logger.info(f"Lead {phone} é de baixa prioridade. Nenhuma notificação de vendas será enviada.")

            return JSONResponse({"status": "lead_qualified_processed"})

        except Exception as e:
            error_message = f"Erro ao processar qualificação de lead para {phone}: {e}"
            logger.error(error_message)
            print(f"[WEBHOOK_ERROR] {error_message}")
            return JSONResponse({"status": "error", "detail": error_message}, status_code=500)

    # Rota 2: Webhook de Mensagem do Cliente da Z-API
    elif data.get('type') == 'ReceivedCallback' and not data.get('fromMe', False):
        
        # VERIFICAÇÃO: Ignora mensagens de grupo
        if data.get('isGroup'):
            logger.info("Mensagem de grupo recebida. Ignorando.")
            return JSONResponse({"status": "group_message_ignored"})

        phone = data.get('phone')
        sender_name = data.get('senderName')
        logger.info(f"Processando mensagem de {sender_name} ({phone})")

        try:
            # Garante que o lead existe no Notion
            notion_service = NotionService()
            notion_service.create_or_update_lead(
                sender_name=sender_name,
                phone=phone,
                photo_url=data.get('photo')
            )

            # Continua com o fluxo de IA (áudio ou texto)
            if 'audio' in data and data.get('audio'):
                # Processamento de áudio...
                audio_url = data['audio']['audioUrl']
                whisper_service = WhisperService()
                transcript = await whisper_service.transcribe_audio(audio_url)

                zaia_service = ZaiaService()
                zaia_response = await zaia_service.send_message({'transcript': transcript, 'phone': phone})

                if zaia_response.get('text'):
                    elevenlabs_service = ElevenLabsService()
                    audio_bytes = elevenlabs_service.generate_audio(zaia_response['text'])
                    await ZAPIService.send_audio_with_typing(phone, audio_bytes)

            elif 'text' in data and data.get('text'):
                # Processamento de texto...
                message_text = data['text'].get('message', '')
                zaia_service = ZaiaService()
                zaia_response = await zaia_service.send_message({'text': {'body': message_text}, 'phone': phone})

                if zaia_response.get('text'):
                    await ZAPIService.send_text_with_typing(phone, zaia_response['text'])

            return JSONResponse({"status": "message_processed"})

        except Exception as e:
            error_message = f"Erro ao processar mensagem de {phone}: {e}"
            logger.error(error_message)
            print(f"[WEBHOOK_ERROR] {error_message}")
            return JSONResponse({"status": "error", "detail": error_message}, status_code=500)

    logger.info("Tipo de webhook não processado.")
    return JSONResponse({"status": "event_not_handled"}) 