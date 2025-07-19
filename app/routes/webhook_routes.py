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
    
    Args:
        name (str): Nome a ser analisado
        
    Returns:
        bool: True se for provavelmente comercial, False caso contrário
    """
    if not name or not name.strip():
        return False
    
    name_lower = name.lower()
    name_parts = name.split()
    
    # Palavras-chave comerciais e de negócios
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
    
    # Iniciais comuns em inglês que indicam empresa/negócio
    business_initials = [
        'ai', 'aii', 'aiii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x',
        'co', 'corp', 'inc', 'ltd', 'llc', 'plc', 'pty', 'pty ltd',
        'pvt', 'pvt ltd', 'gmbh', 'ag', 'sarl', 'sas', 'spa', 'srl'
    ]
    
    # Critério 1: Contém palavra-chave comercial
    if any(word in name_lower for word in commercial_keywords):
        logger.info(f"Nome '{name}' identificado como comercial por palavra-chave")
        return True
    
    # Critério 2: Contém iniciais de negócio
    if any(initial in name_lower for initial in business_initials):
        logger.info(f"Nome '{name}' identificado como comercial por iniciais")
        return True
    
    # Critério 3: Mais de 3 palavras (provavelmente nome de empresa)
    if len(name_parts) > 3:
        logger.info(f"Nome '{name}' identificado como comercial por ter muitas palavras ({len(name_parts)})")
        return True
    
    # Critério 4: Contém caracteres típicos de empresa
    business_chars = ['&', '/', '|', '-', '@', '+', '(', ')', '[', ']']
    if any(char in name for char in business_chars):
        logger.info(f"Nome '{name}' identificado como comercial por caracteres especiais")
        return True
    
    # Critério 5: Padrão de iniciais (ex: AI Mika, AB Company)
    # Verifica se as primeiras palavras são apenas letras maiúsculas (iniciais)
    if len(name_parts) >= 2:
        first_part = name_parts[0].strip()
        if (len(first_part) <= 3 and 
            first_part.isupper() and 
            first_part.isalpha()):
            logger.info(f"Nome '{name}' identificado como comercial por padrão de iniciais")
            return True
    
    # Critério 6: Contém números (típico de empresas)
    if any(char.isdigit() for char in name):
        logger.info(f"Nome '{name}' identificado como comercial por conter números")
        return True
    
    return False

def extract_first_name(full_name: str) -> str:
    """
    Extrai o primeiro nome de forma natural, removendo sufixos comerciais e tratando casos especiais.
    
    Args:
        full_name (str): Nome completo do cliente
        
    Returns:
        str: Primeiro nome limpo para uso em conversas
    """
    if not full_name or not full_name.strip():
        return "cliente"
    
    # Remove espaços extras e normaliza
    name = full_name.strip()
    
    # Lista de títulos profissionais para pular
    professional_titles = [
        'dr', 'doctor', 'dra', 'doutor', 'doutora', 'eng', 'engineer', 'engenheiro',
        'adv', 'advocacia', 'advogado', 'advogada', 'prof', 'professor', 'professora',
        'cont', 'contador', 'contadora', 'med', 'medicine', 'médico', 'médica'
    ]
    
    # Lista de sufixos comerciais comuns para remover
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
    
    # Remove caracteres especiais e divide o nome em partes
    name_clean = re.sub(r'[^\w\s]', ' ', name)  # Remove caracteres especiais
    # Remove underscores também
    name_clean = name_clean.replace('_', ' ')
    name_parts = name_clean.split()
    
    # Se não há partes válidas após limpeza, retorna cliente
    if not name_parts:
        return "cliente"
    
    # Se tem apenas uma palavra, retorna ela
    if len(name_parts) == 1:
        return name_parts[0].title()
    
    # Procura pelo primeiro nome válido (pula títulos profissionais e sufixos comerciais)
    first_name = None
    for part in name_parts:
        part_lower = part.lower()
        # Se a parte não é um título profissional, não é um sufixo comercial e tem pelo menos 2 caracteres
        if (part_lower not in professional_titles and 
            part_lower not in commercial_suffixes and 
            len(part) >= 2):
            first_name = part.title()
            break
    
    # Se não encontrou um nome válido, usa a primeira parte que não seja um título
    if not first_name:
        for part in name_parts:
            part_lower = part.lower()
            if part_lower not in professional_titles:
                first_name = part.title()
                break
    
    # Se ainda não encontrou, usa a primeira parte
    if not first_name:
        first_name = name_parts[0].title()
    
    # Tratamento especial para nomes muito longos
    if len(first_name) > 20:
        first_name = first_name[:20]
    
    # Remove espaços extras que podem ter sobrado
    first_name = first_name.strip()
    
    # Se ficou vazio após limpeza, usa um nome genérico
    if not first_name:
        first_name = "cliente"
    
    logger.info(f"Nome original: '{full_name}' -> Primeiro nome extraído: '{first_name}'")
    return first_name

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

            # Se for um novo lead, verifica se já fez uma pergunta direta
            if is_new_lead:
                logger.info(f"Novo lead detectado ({phone}). Verificando se já fez uma pergunta direta.")
                
                # Extrai o primeiro nome
                first_name = extract_first_name(sender_name)
                
                # Verifica se a mensagem é uma pergunta direta (não é apenas um cumprimento)
                normalized_message = message_text.strip().lower()
                greetings = ['oi', 'olá', 'ola', 'bom dia', 'boa tarde', 'boa noite', 'opa']
                
                if normalized_message in greetings:
                    # Se for apenas um cumprimento, envia a saudação padrão
                    logger.info("Novo lead enviou apenas cumprimento. Enviando saudação personalizada.")
                    greeting_message = f"Hello Hello, {first_name}! Que bom ter você por aqui. Como posso te ajudar com o seu objetivo em Inglês hoje?"
                    await ZAPIService.send_text_with_typing(phone, greeting_message)
                    return JSONResponse({"status": "new_lead_greeted"})
                else:
                    # Se já fez uma pergunta direta, responde diretamente com contexto
                    logger.info("Novo lead já fez pergunta direta. Respondendo com contexto.")
                    
                    # Constrói o prompt para a Zaia com o contexto do novo lead
                    def build_new_lead_prompt(base_message: str) -> str:
                        parts = [f"Meu nome é {first_name}."]
                        parts.append(f"Minha pergunta é: {base_message}")
                        return " ".join(parts)
                    
                    final_prompt = build_new_lead_prompt(message_text)
                    
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
                    
                    return JSONResponse({"status": "new_lead_direct_question_processed"})

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
                first_name = extract_first_name(sender_name)
                response_message = f"Hello Hello, {first_name}! Como posso te ajudar hoje?"
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
                # Extrai o primeiro nome para usar no prompt da Zaia também
                first_name = extract_first_name(client_name)
                parts = [f"Meu nome é {first_name}."]
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

        except Exception as e:
            error_message = f"Erro ao processar mensagem de {phone}: {e}"
            logger.error(error_message)
            print(f"[WEBHOOK_ERROR] {error_message}")
            return JSONResponse({"status": "error", "detail": error_message}, status_code=500)

    logger.info("Tipo de webhook não processado.")
    return JSONResponse({"status": "event_not_handled"}) 