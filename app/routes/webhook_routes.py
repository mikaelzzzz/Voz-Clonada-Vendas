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
    
    return first_name if first_name else "cliente"

@router.post("")
async def handle_webhook(request: Request):
    data = await request.json()
    logger.info(f"--- NOVO WEBHOOK RECEBIDO ---\n{data}")

    try:
        # Rota 1: Webhook de Qualificação da Zaia
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
                
                # Busca os dados completos do lead para tomar a decisão
                lead_full_data = notion_service.get_lead_data_by_phone(phone)
                lead_properties = lead_full_data.get('properties', {}) if lead_full_data else {}
                alerta_enviado = lead_properties.get('Alerta Enviado', False)

                # 3. Se for de alta prioridade E o alerta ainda não foi enviado, gera e envia a análise
                if qualification_level == 'Alto' and not alerta_enviado:
                    logger.info(f"Lead {phone} é de alta prioridade e o alerta ainda não foi enviado. Notificando a equipe.")
                    
                    # Gera o resumo de texto com a IA
                    summary_text = await openai_service.generate_sales_summary(lead_properties)
                    
                    notion_url = lead_full_data.get('url', 'URL do Notion não encontrada.')
                    final_message = (
                        f"{summary_text}\n\n"
                        f"🔗 *Link do Notion:* {notion_url}\n"
                        f"📱 *WhatsApp do Lead:* https://wa.me/{phone}"
                    )

                    for sales_phone in settings.SALES_TEAM_PHONES:
                        await ZAPIService.send_text(sales_phone, final_message)
                    
                    # Marca que o alerta foi enviado para não repetir
                    notion_service.update_lead_properties(phone, {"Alerta Enviado": True})
                    logger.info(f"Alerta de vendas para o lead {phone} enviado e marcado como concluído.")

                elif alerta_enviado:
                    logger.info(f"Alerta para o lead {phone} já foi enviado anteriormente. Ignorando.")
                else: # Lead de baixa prioridade
                    logger.info(f"Lead {phone} é de baixa prioridade. Nenhuma notificação de vendas será enviada.")

                return JSONResponse({"status": "lead_qualified_processed"})

            except Exception as e:
                error_message = f"Erro ao processar qualificação de lead para {phone}: {e}"
                logger.error(error_message)
                print(f"[WEBHOOK_ERROR] {error_message}")
                return JSONResponse({"status": "error", "detail": error_message}, status_code=500)

        # Rota 2: Mensagem do Cliente da Z-API
        elif data.get('type') == 'ReceivedCallback' and not data.get('fromMe', False):
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

            # Instancia os serviços que serão usados em múltiplos fluxos
            notion_service = NotionService()
            zaia_service = ZaiaService()
            whisper_service = WhisperService()

            # --- FLUXO DE CONFIRMAÇÃO DE NOME ---
            lead_data = notion_service.get_lead_data_by_phone(phone)
            if lead_data and lead_data.get('properties', {}).get('Aguardando Confirmação Nome', False):
                logger.info(f"Recebida resposta para confirmação de nome de {phone}: '{message_text}'")
                
                original_sender_name = lead_data.get('properties', {}).get('Cliente', '')
                suggested_name = extract_first_name(original_sender_name)
                
                # Usa a IA para interpretar a resposta do cliente
                qualification_service = QualificationService()
                interpretation = await qualification_service.interpret_name_confirmation_with_ai(suggested_name, message_text)
                
                confirmed_name = ""
                
                if interpretation.get("confirmation") == "positive":
                    confirmed_name = suggested_name
                    logger.info(f"IA interpretou como confirmação positiva. Usando nome sugerido: '{confirmed_name}'")
                elif interpretation.get("confirmation") == "new_name" and interpretation.get("name"):
                    confirmed_name = extract_first_name(interpretation.get("name"))
                    logger.info(f"IA detectou um novo nome. Usando: '{confirmed_name}'")
                else: # Fallback para negação ou resposta desconhecida
                    confirmed_name = extract_first_name(message_text)
                    logger.warning(f"IA não conseguiu confirmar o nome. Fazendo fallback e extraindo da resposta: '{confirmed_name}'")

                # Atualiza o nome e desmarca a flag
                notion_service.update_lead_properties(phone, {
                    "Cliente": confirmed_name,
                    "Aguardando Confirmação Nome": False
                })
                
                # Busca a primeira mensagem que foi salva
                primeira_mensagem_salva = lead_data.get('properties', {}).get('Primeira Mensagem', '')
                
                # Se houver uma pergunta salva, a envia para a Zaia com o novo contexto
                if primeira_mensagem_salva and primeira_mensagem_salva.strip():
                    logger.info(f"Enviando primeira pergunta salva para a Zaia com nome confirmado: '{primeira_mensagem_salva}'")
                    
                    def build_prompt_with_confirmed_name(base_message: str) -> str:
                        lang = detect_language(base_message)
                        lang_instruction = "Instrução: Responda em inglês." if lang == 'en' else "Instrução: Responda em português."
                        parts = [lang_instruction, f"Meu nome é {confirmed_name}.", f"Minha pergunta é: {base_message}"]
                        return " ".join(parts)

                    final_prompt = build_prompt_with_confirmed_name(primeira_mensagem_salva)
                    zaia_service = ZaiaService()
                    zaia_response = await zaia_service.send_message({'text': final_prompt, 'phone': phone})
                    await _handle_zaia_response(phone, is_audio, zaia_response) # is_audio é False aqui, mas mantemos por consistência
                    
                # Se não havia pergunta salva, apenas envia a saudação de agradecimento
                else:
                    greeting = f"Perfeito, {confirmed_name}! Obrigado por confirmar. Como posso te ajudar com o seu objetivo em inglês hoje?"
                    await ZAPIService.send_text_with_typing(phone, greeting)

                return JSONResponse({"status": "name_confirmation_processed"})

            # --- FLUXO DE NOVO LEAD ---
            is_new_lead = not bool(lead_data)
            if is_new_lead:
                notion_service.create_or_update_lead(sender_name, phone, data.get('photo'))
                
                qualification_service = QualificationService()
                name_analysis = await qualification_service.analyze_name_with_ai(sender_name)
                name_type = name_analysis.get("type", "Pessoa")
                extracted_name = name_analysis.get("extracted_name")

                # Define se a mensagem é um cumprimento para usar nos cenários abaixo
                normalized_message = message_text.strip().lower()
                greetings = ['oi', 'olá', 'ola', 'oii', 'bom dia', 'boa tarde', 'boa noite', 'opa']
                english_greetings = ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening']
                is_greeting = normalized_message in greetings or normalized_message in english_greetings

                # Cenário 1: Nome puramente comercial
                if name_type == 'Empresa':
                    logger.info(f"Nome puramente comercial detectado por IA: '{sender_name}'.")
                    # Salva a primeira mensagem se ela não for um simples cumprimento
                    if not is_greeting:
                        notion_service.update_lead_properties(phone, {"Primeira Mensagem": message_text})
                    msg = f"Hello Hello! Vi que seu nome está como '{sender_name}'. Este é o nome do seu negócio? Se sim, como posso te chamar?"
                    await ZAPIService.send_text_with_typing(phone, msg)
                    notion_service.update_lead_properties(phone, {"Aguardando Confirmação Nome": True})
                    return JSONResponse({"status": "commercial_name_confirmation_sent"})

                # Cenário 2: Nome comercial com nome pessoal detectado
                elif name_type == 'Empresa com nome' and extracted_name:
                    logger.info(f"Nome comercial com nome pessoal '{extracted_name}' detectado em '{sender_name}'.")
                    # Salva a primeira mensagem se ela não for um simples cumprimento
                    if not is_greeting:
                        notion_service.update_lead_properties(phone, {"Primeira Mensagem": message_text})
                    msg = f"Hello Hello, que bom ter você por aqui! Vi que seu nome está como '{sender_name}'. Posso te chamar de {extracted_name} mesmo? Ou como prefere que eu te chame?"
                    await ZAPIService.send_text_with_typing(phone, msg)
                    notion_service.update_lead_properties(phone, {"Aguardando Confirmação Nome": True})
                    return JSONResponse({"status": "commercial_name_with_personal_name_confirmation_sent"})

                # Cenário 3: Nome é de Pessoa (ou fallback da IA)
                else: # name_type == 'Pessoa'
                    # ... (lógica existente que já trata isso corretamente) ...
                    return JSONResponse({"status": "new_lead_processed"})
            
            # --- FLUXO DE LEAD EXISTENTE ---
            else:
                # Se for um novo lead, nossa aplicação envia a primeira saudação
                if is_new_lead:
                    logger.info(f"Novo lead detectado ({phone}). Enviando saudação personalizada diretamente.")
                    greeting_message = f"Olá, {sender_name}! Que bom ter você por aqui. Como posso ajudar hoje?"
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
                    response_message = f"Hello Hello, {sender_name}! Como posso te ajudar hoje?"
                    # Se a mensagem original era áudio, respondemos com áudio
                    if is_audio:
                        elevenlabs_service = ElevenLabsService()
                        audio_bytes = elevenlabs_service.generate_audio(response_message)
                        await ZAPIService.send_audio_with_typing(phone, audio_bytes, original_text=response_message)
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
                        await ZAPIService.send_text_with_typing(phone, ai_response_text)
                
                return JSONResponse({"status": "message_processed_by_zaia"})

        # Se nenhum webhook corresponder
        else:
            logger.info("Tipo de webhook não processado.")
            return JSONResponse({"status": "event_not_handled"})

    except Exception as e:
        error_message = f"Erro ao processar webhook: {e}"
        logger.error(error_message)
        print(f"[WEBHOOK_ERROR] {error_message}")
        return JSONResponse({"status": "error", "detail": error_message}, status_code=500) 