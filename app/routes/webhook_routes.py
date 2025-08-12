import logging
import re
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from langdetect import detect, LangDetectException
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

def is_commercial_name(name: str) -> bool:
    """
    Determina se um nome é provavelmente comercial ou de negócio.
    """
    if not name or not name.strip():
        return False
    
    name_lower = name.lower()
    name_parts = name.split()
    
    commercial_keywords = [
        'beauty', 'hair', 'dresser', 'salon', 'studio', 'clinic', 'consultoria',
        'consulting', 'services', 'solutions', 'enterprise', 'company', 'ltd',
        'inc', 'corp', 'associates', 'group', 'team', 'center', 'institute',
        'academy', 'school', 'training', 'coaching', 'mentoring', 'design',
        'designer', 'photography', 'photographer', 'makeup', 'makeup artist',
        'nails', 'nail artist', 'spa', 'wellness', 'fitness', 'personal trainer',
        'coach', 'instructor', 'teacher', 'professor', 'law', 'lawyer', 'attorney',
        'arch', 'architect', 'accountant', 'dentistry', 'dental', 'veterinary', 
        'vet', 'pharmacy', 'pharmacist', 'office', 'consulting', 'solutions',
        'technology', 'tech', 'digital', 'online', 'web', 'mobile', 'app',
        'software', 'system', 'network', 'security', 'marketing', 'advertising',
        'media', 'production', 'studio', 'agency', 'partners', 'associates'
    ]
    
    business_initials = [
        'ai', 'aii', 'aiii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x',
        'co', 'corp', 'inc', 'ltd', 'llc', 'plc', 'pty', 'pty ltd',
        'pvt', 'pvt ltd', 'gmbh', 'ag', 'sarl', 'sas', 'spa', 'srl'
    ]
    
    if any(word in name_lower for word in commercial_keywords):
        logger.info(f"Nome '{name}' identificado como comercial por palavra-chave")
        return True
    
    if any(initial in name_lower for initial in business_initials):
        logger.info(f"Nome '{name}' identificado como comercial por iniciais")
        return True
    
    if len(name_parts) > 3:
        logger.info(f"Nome '{name}' identificado como comercial por ter muitas palavras ({len(name_parts)})")
        return True
    
    business_chars = ['&', '/', '|', '-', '@', '+', '(', ')', '[', ']']
    if any(char in name for char in business_chars):
        logger.info(f"Nome '{name}' identificado como comercial por caracteres especiais")
        return True
    
    if len(name_parts) >= 2:
        first_part = name_parts[0].strip()
        if (len(first_part) <= 3 and first_part.isupper() and first_part.isalpha()):
            logger.info(f"Nome '{name}' identificado como comercial por padrão de iniciais")
            return True
    
    if any(char.isdigit() for char in name):
        logger.info(f"Nome '{name}' identificado como comercial por conter números")
        return True
    
    return False

def extract_first_name(full_name: str) -> str:
    """
    Extrai o primeiro nome de forma natural, removendo sufixos comerciais e tratando casos especiais.
    """
    if not full_name or not full_name.strip():
        return "cliente"
    
    name = full_name.strip()
    
    professional_titles = [
        'dr', 'doctor', 'dra', 'doutor', 'doutora', 'eng', 'engineer', 'engenheiro',
        'adv', 'advocacia', 'advogado', 'advogada', 'prof', 'professor', 'professora',
        'cont', 'contador', 'contadora', 'med', 'medicine', 'médico', 'médica'
    ]
    
    commercial_suffixes = [
        'beauty', 'hair', 'dresser', 'salon', 'studio', 'clinic', 'consultoria',
        'consulting', 'services', 'solutions', 'enterprise', 'company', 'ltd',
        'inc', 'corp', 'associates', 'group', 'team', 'center', 'institute',
        'academy', 'school', 'training', 'coaching', 'mentoring', 'consulting',
        'design', 'designer', 'photography', 'photographer', 'makeup', 'makeup artist',
        'nails', 'nail artist', 'spa', 'wellness', 'fitness', 'personal trainer',
        'coach', 'instructor', 'teacher', 'professor', 'law', 'lawyer', 'attorney',
        'arch', 'architect', 'accountant', 'dentistry', 'dental', 'veterinary', 
        'vet', 'pharmacy', 'pharmacist'
    ]
    
    name_clean = re.sub(r'[^\w\s]', ' ', name)
    name_clean = name_clean.replace('_', ' ')
    name_parts = name_clean.split()
    
    if not name_parts:
        return "cliente"
    
    if len(name_parts) == 1:
        return name_parts[0].title()
    
    first_name = None
    for part in name_parts:
        part_lower = part.lower()
        if (part_lower not in professional_titles and 
            part_lower not in commercial_suffixes and 
            len(part) >= 2):
            first_name = part.title()
            break
    
    if not first_name:
        for part in name_parts:
            part_lower = part.lower()
            if part_lower not in professional_titles:
                first_name = part.title()
                break
    
    if not first_name:
        first_name = name_parts[0].title()
    
    if len(first_name) > 20:
        first_name = first_name[:20]
    
    first_name = first_name.strip()
    
    if not first_name:
        first_name = "cliente"
    
    logger.info(f"Nome original: '{full_name}' -> Primeiro nome extraído: '{first_name}'")
    return first_name

def detect_language(text: str) -> str:
    """
    Detecta o idioma de um texto (inglês ou português) usando langdetect.
    Retorna 'en' para inglês, 'pt' para português (padrão).
    """
    if not text or not text.strip():
        return 'pt'
    try:
        lang = detect(text)
        logger.info(f"Idioma detectado para o texto '{text[:30]}...': {lang}")
        if lang == 'en':
            return 'en'
    except LangDetectException:
        logger.warning(f"Não foi possível detectar o idioma para o texto: '{text}'. Assumindo português.")
    return 'pt'

async def _handle_zaia_response(phone: str, is_audio: bool, zaia_response: dict):
    """
    Processa a resposta da Zaia, verificando links e enviando áudio/texto conforme necessário.
    """
    if not zaia_response or not zaia_response.get('text'):
        logger.warning("Resposta da Zaia vazia ou inválida.")
        return

    ai_response_text = zaia_response.get('text')
    url_pattern = r'https?://[^\s]+'
    contains_link = re.search(url_pattern, ai_response_text)

    if is_audio and not contains_link:
        logger.info("Resposta para áudio sem link. Gerando áudio.")
        elevenlabs_service = ElevenLabsService()
        audio_bytes = elevenlabs_service.generate_audio(ai_response_text)
        await ZAPIService.send_audio_with_typing(phone, audio_bytes, original_text=ai_response_text)
    else:
        if contains_link:
            logger.info("Resposta contém um link. Enviando como texto por padrão.")
        await ZAPIService.send_text_with_typing(phone, ai_response_text)

@router.post("")
async def handle_webhook(request: Request):
    data = await request.json()
    logger.info(f"Webhook recebido: {data}")

    try:
        # Rota 0: Mensagem de humano da equipe -> Ativa hibernação
        if data.get('fromMe', False) and not data.get('isStatusReply', False):
            phone = re.sub(r'\D', '', str(data.get('phone', '')))
            if phone:
                logger.info(f"👨‍💼 Mensagem de humano detectada para {phone}. Ativando modo de hibernação.")
                # await CacheService.activate_hibernation(phone) # -> Lógica de cache removida
            return JSONResponse({"status": "human_message_detected"})

        # Rota 1: Webhook de Qualificação da Zaia
        elif 'profissao' in data and 'motivo' in data and 'whatsapp' in data:
            phone_raw = data.get('whatsapp')
            if not phone_raw or '{{' in str(phone_raw):
                return JSONResponse({"status": "invalid_phone_variable"}, status_code=400)
            
            phone = re.sub(r'\D', '', str(phone_raw))
            profissao = data.get('profissao')
            motivo = data.get('motivo')
            logger.info(f"Processando qualificação de lead para {phone} (original: {phone_raw})")
            
            notion_service = NotionService()
            openai_service = OpenAIService()
            qualification_service = QualificationService()
            settings = Settings()
            
            qualification_level = await qualification_service.classify_lead(motivo, profissao)
            logger.info(f"Lead {phone} classificado como: {qualification_level}")
            
            updates = {
                "Profissão": profissao, "Real Motivação": motivo,
                "Status": "Qualificado pela IA", "Nível de Qualificação": qualification_level
            }
            notion_service.update_lead_properties(phone, updates)
            
            lead_full_data = notion_service.get_lead_data_by_phone(phone)
            lead_properties = lead_full_data.get('properties', {}) if lead_full_data else {}
            alerta_enviado = lead_properties.get('Alerta Enviado', False)

            if qualification_level == 'Alto' and not alerta_enviado:
                logger.info(f"Lead {phone} é de alta prioridade. Notificando a equipe.")
                summary_text = await openai_service.generate_sales_summary(lead_properties)
                notion_url = lead_full_data.get('url', 'URL não encontrada.')
                final_message = (
                    f"{summary_text}\n\n"
                    f"🔗 *Link do Notion:* {notion_url}\n"
                    f"📱 *WhatsApp do Lead:* https://wa.me/{phone}"
                )
                for sales_phone in settings.SALES_TEAM_PHONES:
                    await ZAPIService.send_text(sales_phone, final_message)
                notion_service.update_lead_properties(phone, {"Alerta Enviado": True})
                logger.info(f"Alerta para {phone} enviado e marcado.")
            elif alerta_enviado:
                logger.info(f"Alerta para {phone} já enviado. Ignorando.")
            else:
                logger.info(f"Lead {phone} de baixa prioridade. Nenhuma notificação enviada.")

            return JSONResponse({"status": "lead_qualified_processed"})

        # Rota 2: Mensagem do Cliente da Z-API
        elif data.get('type') == 'ReceivedCallback':
            if data.get('isGroup'):
                return JSONResponse({"status": "group_message_ignored"})

            phone_raw = data.get('phone')
            sender_name = data.get('senderName')
            phone = re.sub(r'\D', '', str(phone_raw))

            # if await CacheService.is_hibernating(phone): # -> Lógica de cache removida
            #     return JSONResponse({"status": "hibernation_mode_active"})

            if not phone or not sender_name:
                return JSONResponse({"status": "invalid_sender_data"})

            logger.info(f"Processando mensagem de {sender_name} ({phone})")
            
            message_text = ""
            is_audio = 'audio' in data and data.get('audio')
            whisper_service = WhisperService()
            if is_audio:
                message_text = await whisper_service.transcribe_audio(data['audio']['audioUrl'])
            elif 'text' in data and data.get('text'):
                message_text = data['text'].get('message', '')

            notion_service = NotionService()
            is_new_lead = notion_service.create_or_update_lead(
                sender_name=sender_name, phone=phone, photo_url=data.get('photo')
            )

            if is_new_lead:
                first_name = extract_first_name(sender_name)
                normalized_message = message_text.strip().lower()
                greetings = ['oi', 'olá', 'ola', 'oii', 'bom dia', 'boa tarde', 'boa noite', 'opa']
                english_greetings = ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening']
                
                is_greeting = normalized_message in greetings or normalized_message in english_greetings
                lang = detect_language(message_text)

                if is_greeting:
                    logger.info(f"Novo lead enviou cumprimento em '{lang}'.")
                    greeting_message = f"Hello Hello, {first_name}! Que bom ter você por aqui. Como posso te ajudar com o seu objetivo em Inglês hoje?"
                    if lang == 'en':
                        greeting_message = f"Hello Hello, {first_name}! It's great to have you here. How can I help you with your English goal today?"
                    await ZAPIService.send_text_with_typing(phone, greeting_message)
                    return JSONResponse({"status": "new_lead_greeted"})
                else:
                    logger.info("Novo lead fez pergunta direta.")
                    def build_new_lead_prompt(base_message: str, detected_lang: str) -> str:
                        lang_instruction = "Instrução: Responda em inglês." if detected_lang == 'en' else "Instrução: Responda em português."
                        parts = [lang_instruction, f"Meu nome é {first_name}.", f"Minha pergunta é: {base_message}"]
                        return " ".join(parts)
                    
                    final_prompt = build_new_lead_prompt(message_text, lang)
                    zaia_service = ZaiaService()
                    zaia_response = await zaia_service.send_message({'text': final_prompt, 'phone': phone})
                    await _handle_zaia_response(phone, is_audio, zaia_response)
                    return JSONResponse({"status": "new_lead_direct_question_processed"})

            # Lead existente
            logger.info(f"Lead existente ({phone}). Analisando mensagem.")
            normalized_message = message_text.strip().lower()
            greetings = ['oi', 'olá', 'ola', 'oii', 'bom dia', 'boa tarde', 'boa noite', 'opa']
            english_greetings = ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening']
            
            is_greeting = normalized_message in greetings or normalized_message in english_greetings
            lang = detect_language(message_text)

            if is_greeting:
                logger.info(f"Cumprimento de lead existente em '{lang}'.")
                first_name = extract_first_name(sender_name)
                response_message = f"Hello Hello, {first_name}! Como posso te ajudar hoje?"
                if lang == 'en':
                    response_message = f"Hello Hello, {first_name}! How can I help you today?"
                
                if is_audio:
                    elevenlabs_service = ElevenLabsService()
                    audio_bytes = elevenlabs_service.generate_audio(response_message)
                    await ZAPIService.send_audio_with_typing(phone, audio_bytes, original_text=response_message)
                else:
                    await ZAPIService.send_text_with_typing(phone, response_message)
                return JSONResponse({"status": "existing_lead_greeted"})

            logger.info("Pergunta de lead existente. Enviando para Zaia com contexto.")
            lead_full_data = notion_service.get_lead_data_by_phone(phone)
            lead_properties = lead_full_data.get('properties', {}) if lead_full_data else {}

            def build_final_prompt(base_message: str) -> str:
                client_name = lead_properties.get('Cliente', 'cliente')
                first_name = extract_first_name(client_name)
                lang2 = detect_language(base_message)
                lang_instruction = "Instrução: Responda em inglês." if lang2 == 'en' else "Instrução: Responda em português."
                parts = [lang_instruction, f"Meu nome é {first_name}."]
                if lead_properties.get('Profissão') and lead_properties.get('Profissão') != 'não informado':
                    parts.append(f"Eu trabalho como {lead_properties.get('Profissão')}.")
                parts.append(f"Minha pergunta é: {base_message}")
                return " ".join(parts)
            
            final_prompt = build_final_prompt(message_text)
            zaia_service = ZaiaService()
            zaia_response = await zaia_service.send_message({'text': final_prompt, 'phone': phone})
            await _handle_zaia_response(phone, is_audio, zaia_response)
            return JSONResponse({"status": "message_processed_by_zaia"})

        # Se nenhum webhook corresponder
        else:
            logger.info("Tipo de webhook não processado.")
            return JSONResponse({"status": "event_not_handled"})
        
    except Exception as e:
        error_message = f"Erro fatal no processamento do webhook: {e}"
        logger.error(error_message, exc_info=True)
        phone_for_log = data.get('phone') or data.get('whatsapp') or 'não identificado'
        print(f"[WEBHOOK_ERROR] Erro ao processar mensagem de {phone_for_log}: {error_message}")
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)
