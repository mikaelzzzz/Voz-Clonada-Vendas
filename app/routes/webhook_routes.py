import logging
import re
from datetime import datetime
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
from app.services.context_service import ContextService
from langdetect import detect, LangDetectException


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
        return True
    
    name_words = name_lower.split()
    for word in name_words:
        if word in business_initials:
            return True
    
    if len(name_parts) > 3:
        return True
    
    business_chars = ['&', '/', '|', '-', '@', '+', '(', ')', '[', ']']
    if any(char in name for char in business_chars):
        return True
    
    if len(name_parts) >= 2:
        first_part = name_parts[0].strip()
        if (len(first_part) <= 3 and first_part.isupper() and first_part.isalpha()):
            return True
    
    if any(char.isdigit() for char in name):
        return True
    
    return False

def extract_first_name(full_name: str) -> str:
    """
    Extrai o primeiro nome de forma natural.
    """
    if not full_name or not full_name.strip():
        return "cliente"
    
    name = full_name.strip()
    
    professional_titles = [
        'dr', 'doctor', 'dra', 'doutor', 'doutora', 'eng', 'engineer', 'engenheiro',
        'adv', 'advocacia', 'advogado', 'advogada', 'prof', 'professor', 'professora'
    ]
    
    commercial_suffixes = [
        'beauty', 'hair', 'dresser', 'salon', 'studio', 'clinic', 'consultoria'
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
            if part.lower() not in professional_titles:
                first_name = part.title()
                break
    
    if not first_name:
        first_name = name_parts[0].title()
    
    if len(first_name) > 20:
        first_name = first_name[:20]
    
    first_name = first_name.strip()
    
    logger.info(f"Nome original: '{full_name}' -> Primeiro nome extraído: '{first_name}'")
    return first_name

def detect_language(text: str) -> str:
    """
    Detecta o idioma de um texto (inglês ou português) usando langdetect.
    Retorna 'en' para inglês, 'pt' para português (padrão).
    """
    if not text or not text.strip():
        return 'pt' # Padrão para português se o texto for vazio

    try:
        # A detecção pode lançar uma exceção para textos muito curtos ou ambíguos
        lang = detect(text)
        logger.info(f"Idioma detectado para o texto '{text[:30]}...': {lang}")
        if lang == 'en':
            return 'en'
    except LangDetectException:
        logger.warning(f"Não foi possível detectar o idioma para o texto: '{text}'. Assumindo português.")
        # Para textos muito curtos como "ok", "sim", a detecção pode falhar.
        # Assumir português é uma escolha segura.
        pass
    
    return 'pt'

async def _handle_zaia_response(phone: str, is_audio: bool, zaia_response: dict):
    """
    Processa a resposta da Zaia, verificando links e enviando áudio/texto conforme necessário.
    """
    if zaia_response.get('text'):
        ai_response_text = zaia_response.get('text')
        
        # Regex para detectar URLs na resposta da IA
        url_pattern = r'https?://[^\s]+'
        contains_link = re.search(url_pattern, ai_response_text)

        # Se a mensagem original era áudio E a resposta NÃO contém link, envia áudio
        if is_audio and not contains_link:
            logger.info("Resposta para áudio sem link. Gerando áudio.")
            elevenlabs_service = ElevenLabsService()
            audio_bytes = elevenlabs_service.generate_audio(ai_response_text)
            await ZAPIService.send_audio_with_typing(phone, audio_bytes, original_text=ai_response_text)
        # Em todos os outros casos (resposta de texto, ou resposta com link), envia texto
        else:
            if contains_link:
                logger.info("Resposta contém um link. Enviando como texto por padrão.")
            
            # A verificação de delay de contexto foi movida para o fluxo principal
            await ZAPIService.send_text_with_typing(phone, ai_response_text)

@router.post("")
async def handle_webhook(request: Request):
    data = await request.json()
    logger.info(f"--- NOVO WEBHOOK RECEBIDO ---\n{data}")

    try:
        # Rota 0: Mensagem enviada por um humano da equipe (hibernação)
        if data.get('fromMe', False) and not data.get('isStatusReply', False):
            phone = re.sub(r'\D', '', str(data.get('phone', '')))
            if phone:
                # Lógica de hibernação foi removida, apenas ignoramos
                logger.info(f"👨‍💼 Mensagem de humano detectada para {phone}. Ignorando.")
            return JSONResponse({"status": "human_message_ignored"})

        # Rota 1: Webhook de Qualificação da Zaia
        elif 'profissao' in data and 'motivo' in data and 'whatsapp' in data:
            phone_raw = data.get('whatsapp')
            if not phone_raw or '{{' in str(phone_raw):
                return JSONResponse({"status": "invalid_phone_variable"}, status_code=400)

            phone = re.sub(r'\D', '', str(phone_raw))
            profissao = data.get('profissao')
            motivo = data.get('motivo')
            logger.info(f"Processando qualificação para {phone}")

            notion_service = NotionService()
            qualification_service = QualificationService()
            openai_service = OpenAIService()
            settings = Settings()

            qualification_level = await qualification_service.classify_lead(motivo, profissao)
            logger.info(f"Lead {phone} classificado como: {qualification_level}")

            lead_current_data = notion_service.get_lead_data_by_phone(phone)
            current_status = (lead_current_data.get('properties', {}).get('Status') or '') if lead_current_data else ''

            protected_statuses = ["Agendado Reunião", "Reunião Realizada", "Fechado", "Perdido", "Convertido"]
            if current_status.lower() in [s.lower() for s in protected_statuses]:
                logger.info(f"Lead {phone} com status protegido '{current_status}'. Atualizando apenas dados.")
                updates = {"Profissão": profissao, "Real Motivação": motivo, "Nível de Qualificação": qualification_level}
                notion_service.update_lead_properties(phone, updates)
                return JSONResponse({"status": "lead_status_protected"})

            updates = {
                "Profissão": profissao, "Real Motivação": motivo,
                "Status": "Qualificado pela IA", "Nível de Qualificação": qualification_level
            }
            notion_service.update_lead_properties(phone, updates)
            
            lead_full_data = notion_service.get_lead_data_by_phone(phone)
            lead_properties = lead_full_data.get('properties', {}) if lead_full_data else {}
            alerta_enviado = lead_properties.get('Alerta Enviado', False)

            if qualification_level == 'Alto' and not alerta_enviado:
                logger.info(f"Lead {phone} é de alta prioridade. Notificando equipe.")
                summary_text = await openai_service.generate_sales_summary(lead_properties)
                notion_url = lead_full_data.get('url', '')
                final_message = f"{summary_text}\n\n🔗 *Link do Notion:* {notion_url}\n📱 *WhatsApp do Lead:* https://wa.me/{phone}"
                for sales_phone in settings.SALES_TEAM_PHONES:
                    await ZAPIService.send_text(sales_phone, final_message)
                notion_service.update_lead_properties(phone, {"Alerta Enviado": True})
                logger.info(f"Alerta para {phone} enviado e marcado.")

            return JSONResponse({"status": "lead_qualified_processed"})

        # Rota 2: Mensagem do Cliente da Z-API
        elif data.get('type') == 'ReceivedCallback':
            if data.get('isGroup'):
                return JSONResponse({"status": "group_message_ignored"})

            phone_raw = data.get('phone')
            sender_name = data.get('senderName')
            phone = re.sub(r'\D', '', str(phone_raw))

            if not phone or not sender_name:
                return JSONResponse({"status": "invalid_sender_data"})

            logger.info(f"Processando mensagem de '{sender_name}' ({phone})")

            message_text = ""
            is_audio = 'audio' in data and data.get('audio')
            if is_audio:
                message_text = await WhisperService().transcribe_audio(data['audio']['audioUrl'])
            elif 'text' in data and data.get('text'):
                message_text = data['text'].get('message', '')

            notion_service = NotionService()
            lead_data = notion_service.get_lead_data_by_phone(phone)

            if lead_data and lead_data.get('properties', {}).get('Aguardando Confirmação Nome', False):
                # Lógica de confirmação de nome
                # ...
                return JSONResponse({"status": "name_confirmation_processed"})
            
            is_new_lead = not bool(lead_data)
            if is_new_lead:
                # Lógica de novo lead
                # ...
                return JSONResponse({"status": "new_lead_processed"})
            else:
                # Lógica de lead existente
                # ...
                return JSONResponse({"status": "existing_lead_processed"})

        # Rota 3: Mensagem do sistema (para contexto)
        elif data.get('type') == 'system_message_sent':
            phone = re.sub(r'\D', '', str(data.get('phone', '')))
            message_type = data.get('message_type', 'system')
            if phone:
                # await ContextService.mark_system_message_sent(phone, message_type) # Lógica de cache removida
                logger.info(f"Marcação de mensagem do sistema recebida para {phone}.")
            return JSONResponse({"status": "system_message_marked"})

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