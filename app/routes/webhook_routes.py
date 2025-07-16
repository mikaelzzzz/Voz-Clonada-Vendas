import logging
import re
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
        phone_raw = data.get('whatsapp')

        # Validação para garantir que a variável da Zaia foi substituída
        if not phone_raw or '{{' in str(phone_raw):
            error_msg = f"Webhook de qualificação recebido com telefone inválido: {phone_raw}"
            logger.error(error_msg)
            return JSONResponse({"status": "invalid_phone_variable", "detail": error_msg}, status_code=400)

        phone = re.sub(r'\D', '', str(phone_raw)) # Normaliza o número, mantendo apenas dígitos
        profissao = data.get('profissao')
        motivo = data.get('motivo')
        logger.info(f"Processando qualificação de lead para {phone} (original: {phone_raw})")

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
                lead_full_data = notion_service.get_lead_data_by_phone(phone)

                if lead_full_data and lead_full_data.get('properties'):
                    lead_properties = lead_full_data.get('properties', {})
                    notion_url = lead_full_data.get('url', 'URL do Notion não encontrada.')

                    # Gera o resumo de texto com a IA
                    summary_text = await openai_service.generate_sales_summary(lead_properties)
                    
                    # Monta a mensagem final com os links
                    final_message = (
                        f"{summary_text}\n\n"
                        f"🔗 *Link do Notion:* {notion_url}\n"
                        f"📱 *WhatsApp do Lead:* https://wa.me/{phone}"
                    )

                    for sales_phone in settings.SALES_TEAM_PHONES:
                        await ZAPIService.send_text(sales_phone, final_message)
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

        phone_raw = data.get('phone')
        sender_name = data.get('senderName')
        phone = re.sub(r'\D', '', str(phone_raw)) # Normaliza o número

        # Validação básica do número normalizado
        if not phone or not sender_name:
            logger.warning(f"Telefone ou nome do remetente inválidos após normalização. Original: {phone_raw}")
            return JSONResponse({"status": "invalid_sender_data"})

        logger.info(f"Processando mensagem de {sender_name} ({phone})")

        try:
            # Garante que o lead existe no Notion e verifica se é novo
            notion_service = NotionService()
            is_new_lead = notion_service.create_or_update_lead(
                sender_name=sender_name,
                phone=phone,
                photo_url=data.get('photo')
            )

            # Se for um novo lead, nossa aplicação envia a primeira saudação
            if is_new_lead:
                logger.info(f"Novo lead detectado ({phone}). Enviando saudação personalizada diretamente.")
                greeting_message = f"Hello Hello, {sender_name}! Que bom ter você por aqui. Como posso te ajudar hoje?"
                await ZAPIService.send_text_with_typing(phone, greeting_message)
                return JSONResponse({"status": "new_lead_greeted"})

            # Se não for novo, o tratamento inteligente começa aqui
            logger.info(f"Lead existente ({phone}). Analisando a mensagem.")

            message_text = ""
            is_audio = 'audio' in data and data.get('audio')
            if is_audio:
                whisper_service = WhisperService()
                message_text = await whisper_service.transcribe_audio(data['audio']['audioUrl'])
            elif 'text' in data and data.get('text'):
                message_text = data['text'].get('message', '')

            normalized_message = message_text.strip().lower()
            greetings = ['oi', 'olá', 'ola', 'bom dia', 'boa tarde', 'boa noite', 'opa']

            # Se for um simples cumprimento, nosso código responde diretamente
            if normalized_message in greetings:
                logger.info("Mensagem é um cumprimento. Respondendo diretamente.")
                response_message = f"Hello Hello, {sender_name}! Que bom te ver de novo. Como posso ajudar?"
                # Se a mensagem original era áudio, respondemos com áudio
                if is_audio:
                    elevenlabs_service = ElevenLabsService()
                    audio_bytes = elevenlabs_service.generate_audio(response_message)
                    await ZAPIService.send_audio_with_typing(phone, audio_bytes)
                else:
                    await ZAPIService.send_text_with_typing(phone, response_message)
                return JSONResponse({"status": "existing_lead_greeted"})

            # Se for uma pergunta real, enriquecemos o contexto e enviamos para a Zaia
            logger.info("Mensagem é uma pergunta. Enviando para a Zaia com contexto.")
            lead_full_data = notion_service.get_lead_data_by_phone(phone)
            lead_properties = lead_full_data.get('properties', {}) if lead_full_data else {}

            # Constrói o prompt final para a Zaia
            def build_final_prompt(base_message: str) -> str:
                client_name = lead_properties.get('Cliente', 'cliente')
                parts = [f"Meu nome é {client_name}."]
                if lead_properties.get('Profissão') and lead_properties.get('Profissão') != 'não informado':
                    parts.append(f"Eu trabalho como {lead_properties.get('Profissão')}.")
                
                parts.append(f"Minha pergunta é: {base_message}")
                return " ".join(parts)
            
            final_prompt = build_final_prompt(message_text)

            zaia_service = ZaiaService()
            zaia_response = await zaia_service.send_message({'text': final_prompt, 'phone': phone})
            
            if zaia_response.get('text'):
                 # Se a mensagem original era áudio, respondemos com áudio
                if is_audio:
                    elevenlabs_service = ElevenLabsService()
                    audio_bytes = elevenlabs_service.generate_audio(zaia_response['text'])
                    await ZAPIService.send_audio_with_typing(phone, audio_bytes)
                else:
                    await ZAPIService.send_text_with_typing(phone, zaia_response['text'])
            
            return JSONResponse({"status": "message_processed_by_zaia"})

        except Exception as e:
            error_message = f"Erro ao processar mensagem de {phone}: {e}"
            logger.error(error_message)
            print(f"[WEBHOOK_ERROR] {error_message}")
            return JSONResponse({"status": "error", "detail": error_message}, status_code=500)

    logger.info("Tipo de webhook não processado.")
    return JSONResponse({"status": "event_not_handled"}) 