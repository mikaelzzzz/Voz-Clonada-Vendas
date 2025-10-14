import asyncio
import logging
import re
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.services.z_api_service import ZAPIService
from app.services.zaia_service import ZaiaService
from app.services.cache_service import CacheService
from app.services.elevenlabs_service import ElevenLabsService
from app.services.whisper_service import WhisperService
from app.services.notion_service import NotionService
from app.services.openai_service import OpenAIService
from app.config.settings import Settings
from app.services.qualification_service import QualificationService
from app.services.context_service import ContextService
from langdetect import detect, LangDetectException
from typing import Dict
import random


logger = logging.getLogger(__name__)

router = APIRouter()

BUFFER_SECONDS = 20  # Aumentado para 20 segundos
_message_timers: Dict[str, asyncio.Task] = {}

def _format_zaia_prompt_with_name(name: str, message: str) -> str:
    """
    Formata o prompt para a Zaia, injetando o nome do cliente de forma natural.
    """
    message_strip = message.strip()
    
    # Tenta encontrar o final da primeira frase (após ., ? ou !)
    match = re.search(r'[.!?]', message_strip)
    
    if match:
        end_index = match.end()
        part1 = message_strip[:end_index]
        part2 = message_strip[end_index:]
        return f"{part1.strip()} (me chamo {name}). {part2.strip()}"
    else:
        # Se não houver pontuação, formata de uma maneira padrão
        return f"Meu nome é {name}. {message_strip}"

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
        'media', 'production', 'studio', 'agency', 'partners', 'associates',
        # Portugueses comuns
        'fotografia', 'fotografo', 'fotógrafo', 'barbearia', 'barber', 'salão', 'salao',
        'cabeleireiro', 'cabeleireira', 'imobiliaria', 'imobiliária', 'pizzaria', 'padaria',
        'restaurante', 'clinica', 'clínica', 'estetica', 'estética'
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

        # Após enviar a resposta, tentar capturar variável 'investimento' do retorno da Zaia
        try:
            investimento_value = None
            # Possíveis campos estruturados
            for key in ("variables", "data", "custom", "metadata"):
                section = zaia_response.get(key) or {}
                if isinstance(section, dict) and section.get("investimento"):
                    investimento_value = str(section.get("investimento")).strip()
                    break
            # Fallback: tentar extrair do texto (ex.: "Investimento: R$ 300/mês")
            if not investimento_value and isinstance(ai_response_text, str):
                m = re.search(r"(?i)investimento\s*[:\-]\s*([^\n]+)", ai_response_text)
                if m:
                    investimento_value = m.group(1).strip()
            
            if investimento_value:
                notion_service = NotionService()
                formatted_investimento = f'Lead quer investir: "{investimento_value}"'
                notion_service.update_lead_properties(phone, {"Investimento": formatted_investimento})
                logger.info(f"💾 Investimento capturado e salvo no Notion para {phone}: {formatted_investimento}")
        except Exception as e:
            logger.warning(f"Não foi possível salvar 'Investimento' no Notion: {e}")

async def _process_buffered_messages(phone: str, is_audio: bool, initial_data: dict):
    """
    Função para processar as mensagens no buffer após o tempo de espera.
    """
    logger.info(f"Tempo de espera para {phone} finalizado. Processando mensagens.")
    
    if phone in _message_timers:
        _message_timers.pop(phone)

    message_text = await CacheService.get_and_clear_buffer(phone)
    if not message_text:
        logger.warning(f"Nenhuma mensagem no buffer para {phone} após o tempo de espera.")
        return

    logger.info(f"Mensagens consolidadas para {phone}: '{message_text}'")
    
    sender_name = initial_data.get('senderName')
    notion_service = NotionService()
    qualification_service = QualificationService()
    lead_data = notion_service.get_lead_data_by_phone(phone)

    try:
        if lead_data and lead_data.get('properties', {}).get('Aguardando Confirmação Nome', False):
            lead_props = lead_data.get('properties', {})
            cliente_exibicao = lead_props.get('Cliente') or sender_name
            ai_name_analysis = await qualification_service.analyze_name_with_ai(cliente_exibicao)
            suggested_name = ai_name_analysis.get('extracted_name') or extract_first_name(cliente_exibicao)
            interpretation = await qualification_service.interpret_name_confirmation_with_ai(suggested_name, message_text)

            if interpretation.get("confirmation") == "positive":
                notion_service.update_lead_properties(phone, {"Cliente": suggested_name, "Aguardando Confirmação Nome": False})
                first_message = lead_props.get('Primeira Mensagem') or message_text
                zaia_prompt = f"Meu nome é {suggested_name}. {first_message}"
                zaia_response = await ZaiaService.send_message({"text": zaia_prompt, "phone": phone}, metadata={"name": suggested_name})
                await _handle_zaia_response(phone, is_audio=False, zaia_response=zaia_response)
            
            elif interpretation.get("confirmation") == "new_name":
                new_name = interpretation.get("name") or suggested_name
                notion_service.update_lead_properties(phone, {"Cliente": new_name, "Aguardando Confirmação Nome": False})
                first_message = lead_props.get('Primeira Mensagem') or message_text
                zaia_prompt = f"Meu nome é {new_name}. {first_message}"
                zaia_response = await ZaiaService.send_message({"text": zaia_prompt, "phone": phone}, metadata={"name": new_name})
                await _handle_zaia_response(phone, is_audio=False, zaia_response=zaia_response)

            else:
                await ZAPIService.send_text_with_typing(phone, "Perfeito! Como posso te chamar? Me diga apenas o seu primeiro nome.")
        else:
            is_new_lead = not bool(lead_data)
            if is_new_lead:
                # Salva a primeira mensagem completa no Notion para referência.
                notion_service.create_or_update_lead(sender_name, phone, initial_data.get('photo'), first_message=message_text)
                
                ai_name = await qualification_service.analyze_name_with_ai(sender_name)
                name_type = (ai_name.get('type') or '').lower()
                extracted = ai_name.get('extracted_name')
                looks_commercial = is_commercial_name(sender_name) or name_type in ['empresa', 'empresa com nome']

                if looks_commercial:
                    notion_service.update_lead_properties(phone, {"Aguardando Confirmação Nome": True, "Primeira Mensagem": message_text})
                    if name_type == 'empresa com nome' and extracted:
                        confirm_msg = f"Hello Hello, que bom ter você por aqui! Vi aqui que seu nome está como \"{sender_name}\". Posso te chamar de {extracted} mesmo, ou como prefere que eu te chame?"
                        await ZAPIService.send_text_with_typing(phone, confirm_msg)
                    else:
                        ask_msg = f"Hello Hello, que bom ter você por aqui! Vi aqui que seu nome está como \"{sender_name}\". Como prefere que eu te chame?"
                        await ZAPIService.send_text_with_typing(phone, ask_msg)
                else:
                    first_name = extract_first_name(sender_name)
                    normalized_message = (message_text or '').lower().strip()
                    greetings = ['oi', 'olá', 'ola', 'oii', 'bom dia', 'boa tarde', 'boa noite', 'opa', 'hi', 'hello']
                    if normalized_message in greetings:
                        lang = detect_language(message_text)
                        greeting_message = f"Hello Hello, {first_name}! Que bom ter você por aqui. Como posso te ajudar com o seu objetivo em Inglês hoje?"
                        if lang == 'en':
                            greeting_message = f"Hello Hello, {first_name}! How can I help you with your English goals today?"
                        await ZAPIService.send_text_with_typing(phone, greeting_message)
                    else:
                        # Pergunta direta: injetar o nome no prompt para a Zaia
                        zaia_prompt = _format_zaia_prompt_with_name(first_name, message_text)
                        zaia_response = await ZaiaService.send_message({"text": zaia_prompt, "phone": phone}, metadata={"name": first_name})
                        await _handle_zaia_response(phone, is_audio=is_audio, zaia_response=zaia_response)
            else:
                # Lead existente
                normalized_message = message_text.lower().strip()
                greetings = ['oi', 'olá', 'ola', 'oii', 'bom dia', 'boa tarde', 'boa noite', 'opa']
                if normalized_message in greetings:
                    first_name = extract_first_name(sender_name)
                    response_message = f"Hello Hello, {first_name}! Como posso te ajudar hoje?"
                    await ZAPIService.send_text_with_typing(phone, response_message)
                else:
                    lead_props = lead_data.get('properties', {}) if lead_data else {}
                    cliente_nome = lead_props.get('Cliente') or extract_first_name(sender_name)
                    # Pergunta real: injetar o nome no prompt para a Zaia
                    zaia_prompt = _format_zaia_prompt_with_name(cliente_nome, message_text)
                    zaia_response = await ZaiaService.send_message({"text": zaia_prompt, "phone": phone}, metadata={"name": cliente_nome})
                    await _handle_zaia_response(phone, is_audio=is_audio, zaia_response=zaia_response)

    except Exception as e:
        logger.error(f"Erro ao processar mensagens bufferizadas para {phone}: {e}") 


async def _delayed_message_processor(phone: str, is_audio: bool, initial_data: dict):
    """
    Aguarda um tempo e depois processa a mensagem, usando Redis para coordenação.
    """
    job_id = str(random.randint(1000, 9999))
    timer_key = f"timer_job_id:{phone}"
    
    client = await CacheService._get_redis_client()
    if not client:
        # Fallback para lógica sem Redis (ambiente de dev)
        try:
            await asyncio.sleep(BUFFER_SECONDS)
            await _process_buffered_messages(phone, is_audio, initial_data)
        except asyncio.CancelledError:
            logger.info(f"Timer local cancelado para {phone} (nova mensagem chegou).")
        return

    await client.set(timer_key, job_id, ex=BUFFER_SECONDS + 5)
    
    await asyncio.sleep(BUFFER_SECONDS)

    current_job_id = await client.get(timer_key)
    if current_job_id == job_id:
        await _process_buffered_messages(phone, is_audio, initial_data)
    else:
        logger.info(f"Processamento para {phone} cancelado por um job mais recente.")

@router.post("")
async def handle_webhook(request: Request):
    data = await request.json()
    logger.info(f"--- NOVO WEBHOOK RECEBIDO ---\n{data}")

    try:
        # Ignora webhooks de mensagem editada para evitar duplicidade
        if data.get('isEdit'):
            logger.info(f"Webhook de mensagem editada ignorado para {data.get('phone')}")
            return JSONResponse({"status": "edited_message_ignored"})
            
        # Se for uma mensagem enviada por você (fromMe=True), ativar override humano
        if data.get('type') == 'ReceivedCallback' and data.get('fromMe', False):
            try:
                phone_raw = data.get('phone')
                phone = re.sub(r'\D', '', str(phone_raw)) if phone_raw else None
                if phone:
                    # Se for uma reação ✅ enviada por você, desativar override humano
                    reaction = data.get('reaction') or {}
                    reaction_value = (reaction.get('value') or '').strip()
                    if reaction_value == '✅':
                        await CacheService.set_human_override(phone, False)
                        logger.info(f"▶️ Override humano DESATIVADO via reação ✅ para {phone}")
                        return JSONResponse({"status": "human_override_disabled_by_reaction"})

                    # Se a mensagem veio da API (enviada pelo nosso sistema), não ativar override
                    if data.get('fromApi', False):
                        logger.info(f"ℹ️ Mensagem fromMe originada pela API ignorada para override ({phone})")
                        return JSONResponse({"status": "ignored_api_message"})

                    text_message = ''
                    if isinstance(data.get('text'), dict):
                        text_message = (data.get('text', {}).get('message') or '').strip().lower()

                    # Comandos simples para desativar/ativar o override humano
                    disable_commands = {"bot on", "agente on", "ativar bot", "retomar bot"}
                    enable_commands = {"bot off", "agente off", "pausar bot", "assumir"}

                    if text_message in disable_commands:
                        await CacheService.set_human_override(phone, False)
                        logger.info(f"▶️ Override humano DESATIVADO via comando para {phone}")
                        return JSONResponse({"status": "human_override_disabled"})

                    if text_message in enable_commands or text_message:
                        # Qualquer outra mensagem enviada manualmente por você ativa o override humano
                        await CacheService.set_human_override(phone, True)
                        logger.info(f"🛑 Override humano ativado por mensagem manual para {phone}")
                        return JSONResponse({"status": "human_override_enabled"})
            except Exception as e:
                logger.warning(f"Falha ao ativar override humano: {e}")
                # Mesmo com falha ao registrar, não processar como mensagem do cliente
                return JSONResponse({"status": "human_override_attempted"})

        # Rota 1: Webhook de Qualificação da Zaia
        if 'profissao' in data and 'motivo' in data and 'whatsapp' in data:
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
                # Adiciona investimento se presente no webhook
                if 'investimento' in data and data.get('investimento'):
                    updates["Investimento"] = f'Lead quer investir: "{data.get("investimento")}"'
                notion_service.update_lead_properties(phone, updates)
                return JSONResponse({"status": "lead_status_protected"})

            updates = {
                "Profissão": profissao, "Real Motivação": motivo,
                "Status": "Qualificado pela IA", "Nível de Qualificação": qualification_level
            }
            
            # Adiciona investimento se presente no webhook
            if 'investimento' in data and data.get('investimento'):
                updates["Investimento"] = f'Lead quer investir: "{data.get("investimento")}"'
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
        elif data.get('type') == 'ReceivedCallback' and not data.get('fromMe', False):
            phone_raw = data.get('phone')
            sender_name = data.get('senderName')
            phone = re.sub(r'\D', '', str(phone_raw))

            if not phone or not sender_name:
                return JSONResponse({"status": "invalid_sender_data"})

            if await CacheService.is_human_override_active(phone):
                logger.info(f"🛑 Override humano ativo para {phone}. Não enviaremos resposta automática.")
                return JSONResponse({"status": "human_override_active_skip"})
            
            message_text = ""
            is_audio = 'audio' in data and data.get('audio')
            if is_audio:
                message_text = await WhisperService().transcribe_audio(data['audio']['audioUrl'])
            elif 'text' in data and data.get('text'):
                message_text = data['text'].get('message', '')

            if not message_text.strip():
                return JSONResponse({"status": "empty_message_ignored"})

            is_edit = data.get('isEdit', False)
            message_id = data.get('messageId')

            if is_edit:
                await CacheService.update_message_in_buffer(phone, message_id, message_text)
                logger.info(f"Mensagem de {phone} (ID: {message_id}) atualizada no buffer.")
            else:
                await CacheService.add_message_to_buffer(phone, message_id, message_text)
                logger.info(f"Mensagem de {phone} adicionada ao buffer. Aguardando próximas mensagens.")

            # Reinicia o timer a cada nova mensagem ou edição
            # Cancelamento local (fallback) caso não haja Redis
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Se já existe um timer local para este phone, cancela
            existing_task = _message_timers.get(phone)
            if existing_task and not existing_task.done():
                try:
                    existing_task.cancel()
                except Exception:
                    pass

            task = loop.create_task(_delayed_message_processor(phone, is_audio, data))
            _message_timers[phone] = task

            return JSONResponse({"status": "message_buffered"})
        
        # Se nenhum webhook corresponder
        else:
            logger.info("Tipo de webhook não processado.")
            return JSONResponse({"status": "event_not_handled"})
            
    except Exception as e:
        error_message = f"Erro ao processar webhook: {e}"
        logger.error(error_message)
        print(f"[WEBHOOK_ERROR] {error_message}")
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)
    
    return JSONResponse({"status": "ok"}) 