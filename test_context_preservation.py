#!/usr/bin/env python3
"""
Teste para descobrir como manter contexto na API da Zaia
"""

import requests
import time
import json

# TEMPORÁRIO - REVOGAR ESTA API KEY APÓS O DEBUG!
API_KEY = "d0763f89-7e72-4da2-9172-6d10494d22aa"
AGENT_ID = 52634
BASE_URL = "https://api.zaia.app"
TEST_PHONE = "5511975578651"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def test_1_external_id_behavior():
    """Teste 1: Como o externalId se comporta - Conversa natural"""
    print("🧪 TESTE 1: Comportamento do externalId - Conversa Natural")
    print("=" * 50)
    
    url = f"{BASE_URL}/v1.1/api/external-generative-message/create"
    
    # 1. Saudação inicial
    print("👋 Enviando saudação inicial...")
    payload1 = {
        "agentId": AGENT_ID,
        "externalGenerativeChatExternalId": TEST_PHONE,
        "prompt": "Oi! Boa tarde!",
        "streaming": False
    }
    
    try:
        response1 = requests.post(url, headers=headers, json=payload1, timeout=15)
        print(f"Status: {response1.status_code}")
        
        if response1.status_code == 200:
            data1 = response1.json()
            chat_id_1 = data1.get('externalGenerativeChatId')
            response_text_1 = data1.get('text', '')
            
            print(f"✅ Chat ID: {chat_id_1}")
            print(f"🤖 Zaia respondeu: {response_text_1}")
            
            time.sleep(2)
            
            # 2. Apresentação com informações pessoais
            print("\n👤 Me apresentando...")
            payload2 = {
                "agentId": AGENT_ID,
                "externalGenerativeChatExternalId": TEST_PHONE,
                "prompt": "Meu nome é João Silva, tenho 35 anos e trabalho como engenheiro de software. Estou interessado em conhecer mais sobre seus produtos.",
                "streaming": False
            }
            
            response2 = requests.post(url, headers=headers, json=payload2, timeout=15)
            print(f"Status: {response2.status_code}")
            
            if response2.status_code == 200:
                data2 = response2.json()
                chat_id_2 = data2.get('externalGenerativeChatId')
                response_text_2 = data2.get('text', '')
                
                print(f"✅ Chat ID: {chat_id_2}")
                print(f"🤖 Zaia respondeu: {response_text_2}")
                
                time.sleep(2)
                
                # 3. Pergunta sobre contexto
                print("\n❓ Testando se lembra do contexto...")
                payload3 = {
                    "agentId": AGENT_ID,
                    "externalGenerativeChatExternalId": TEST_PHONE,
                    "prompt": "Você pode me dizer qual é o meu nome e minha profissão?",
                    "streaming": False
                }
                
                response3 = requests.post(url, headers=headers, json=payload3, timeout=15)
                print(f"Status: {response3.status_code}")
                
                if response3.status_code == 200:
                    data3 = response3.json()
                    chat_id_3 = data3.get('externalGenerativeChatId')
                    response_text_3 = data3.get('text', '')
                    
                    print(f"✅ Chat ID: {chat_id_3}")
                    print(f"🤖 Zaia respondeu: {response_text_3}")
                    
                    # Verificar consistência dos chat IDs
                    if chat_id_1 == chat_id_2 == chat_id_3:
                        print("✅ MESMO CHAT ID em todas as mensagens!")
                        
                        # Verificar se lembrou das informações
                        response_lower = response_text_3.lower()
                        remembers_name = "joão" in response_lower or "silva" in response_lower
                        remembers_job = "engenheiro" in response_lower or "software" in response_lower
                        
                        if remembers_name and remembers_job:
                            print("🎉 CONTEXTO PERFEITO! Lembrou nome E profissão!")
                            return True, chat_id_1
                        elif remembers_name or remembers_job:
                            print("⚠️ CONTEXTO PARCIAL - Lembrou algumas informações")
                            return True, chat_id_1
                        else:
                            print("❌ Contexto perdido - Não lembrou das informações")
                            return False, chat_id_1
                    else:
                        print(f"❌ CHAT IDs DIFERENTES! {chat_id_1} → {chat_id_2} → {chat_id_3}")
                        return False, None
                else:
                    print(f"❌ Erro na terceira mensagem: {response3.text}")
                    return False, chat_id_2
            else:
                print(f"❌ Erro na segunda mensagem: {response2.text}")
                return False, chat_id_1
        else:
            print(f"❌ Erro na primeira mensagem: {response1.text}")
            return False, None
            
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        return False, None

def test_2_chat_id_with_external_id(chat_id):
    """Teste 2: Continuar conversa no mesmo chat - simulando retorno do cliente"""
    if not chat_id:
        print("\n⏭️ TESTE 2: Pulado (sem chat_id)")
        return False
        
    print(f"\n🧪 TESTE 2: Continuação da conversa no chat {chat_id}")
    print("=" * 50)
    
    url = f"{BASE_URL}/v1.1/api/external-generative-message/create"
    
    # Simular que o cliente voltou depois de um tempo
    print("🔄 Cliente retornando à conversa...")
    payload1 = {
        "agentId": AGENT_ID,
        "externalGenerativeChatId": chat_id,
        "externalGenerativeChatExternalId": TEST_PHONE,
        "prompt": "Oi, voltei! Estava pensando no que você me disse antes.",
        "streaming": False
    }
    
    try:
        response1 = requests.post(url, headers=headers, json=payload1, timeout=15)
        print(f"Status: {response1.status_code}")
        
        if response1.status_code == 200:
            data1 = response1.json()
            response_text_1 = data1.get('text', '')
            print(f"🤖 Zaia respondeu: {response_text_1}")
            
            time.sleep(2)
            
            # Testar se ainda lembra das informações anteriores
            print("\n🧠 Testando memória da conversa anterior...")
            payload2 = {
                "agentId": AGENT_ID,
                "externalGenerativeChatId": chat_id,
                "externalGenerativeChatExternalId": TEST_PHONE,
                "prompt": "Só para confirmar, você ainda lembra do meu nome e profissão?",
                "streaming": False
            }
            
            response2 = requests.post(url, headers=headers, json=payload2, timeout=15)
            print(f"Status: {response2.status_code}")
            
            if response2.status_code == 200:
                data2 = response2.json()
                response_text_2 = data2.get('text', '')
                print(f"🤖 Zaia respondeu: {response_text_2}")
                
                # Verificar se ainda lembra das informações da conversa anterior
                response_lower = response_text_2.lower()
                remembers_name = "joão" in response_lower or "silva" in response_lower
                remembers_job = "engenheiro" in response_lower or "software" in response_lower
                
                if remembers_name and remembers_job:
                    print("🎉 CONTEXTO MANTIDO! Ainda lembra de tudo!")
                    
                    # Adicionar nova informação
                    print("\n➕ Adicionando nova informação...")
                    payload3 = {
                        "agentId": AGENT_ID,
                        "externalGenerativeChatId": chat_id,
                        "externalGenerativeChatExternalId": TEST_PHONE,
                        "prompt": "Ah, esqueci de mencionar: moro em São Paulo e tenho um cachorro chamado Rex.",
                        "streaming": False
                    }
                    
                    response3 = requests.post(url, headers=headers, json=payload3, timeout=15)
                    if response3.status_code == 200:
                        data3 = response3.json()
                        response_text_3 = data3.get('text', '')
                        print(f"🤖 Zaia respondeu: {response_text_3}")
                        
                        # Testar se consegue lembrar de TUDO agora
                        time.sleep(2)
                        print("\n🎯 Teste final: lembrar de TODAS as informações...")
                        payload4 = {
                            "agentId": AGENT_ID,
                            "externalGenerativeChatId": chat_id,
                            "externalGenerativeChatExternalId": TEST_PHONE,
                            "prompt": "Pode me fazer um resumo de tudo que você sabe sobre mim?",
                            "streaming": False
                        }
                        
                        response4 = requests.post(url, headers=headers, json=payload4, timeout=15)
                        if response4.status_code == 200:
                            data4 = response4.json()
                            response_text_4 = data4.get('text', '')
                            print(f"🤖 Resumo da Zaia: {response_text_4}")
                            
                            final_response = response_text_4.lower()
                            has_name = "joão" in final_response or "silva" in final_response
                            has_job = "engenheiro" in final_response
                            has_city = "são paulo" in final_response
                            has_pet = "rex" in final_response or "cachorro" in final_response
                            
                            total_remembered = sum([has_name, has_job, has_city, has_pet])
                            
                            print(f"\n📊 Informações lembradas: {total_remembered}/4")
                            print(f"   Nome: {'✅' if has_name else '❌'}")
                            print(f"   Profissão: {'✅' if has_job else '❌'}")
                            print(f"   Cidade: {'✅' if has_city else '❌'}")
                            print(f"   Pet: {'✅' if has_pet else '❌'}")
                            
                            if total_remembered >= 3:
                                print("🎉 EXCELENTE! Contexto muito bem mantido!")
                                return True
                            elif total_remembered >= 2:
                                print("👍 BOM! Contexto parcialmente mantido")
                                return True
                            else:
                                print("❌ Contexto mal mantido")
                                return False
                        
                    return True
                elif remembers_name or remembers_job:
                    print("⚠️ CONTEXTO PARCIAL - Lembrou algumas informações")
                    return True
                else:
                    print("❌ Contexto perdido - Não lembra da conversa anterior")
                    return False
            else:
                print(f"❌ Erro na segunda mensagem: {response2.text}")
                return False
        else:
            print(f"❌ Erro na primeira mensagem: {response1.text}")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        return False

def test_3_retrieve_messages(chat_id):
    """Teste 3: Verificar mensagens no chat"""
    if not chat_id:
        print("\n⏭️ TESTE 3: Pulado (sem chat_id)")
        return []
        
    print(f"\n🧪 TESTE 3: Recuperar mensagens do chat {chat_id}")
    print("=" * 50)
    
    url = f"{BASE_URL}/v1.1/api/external-generative-message/retrieve-multiple"
    params = {"externalGenerativeChatIds": str(chat_id)}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            messages = data.get("externalGenerativeMessages", [])
            
            print(f"📨 Encontradas {len(messages)} mensagens:")
            
            for i, msg in enumerate(messages[-5:], 1):  # Últimas 5 mensagens
                origin = msg.get("origin")
                text = msg.get("text", "")[:80]
                created = msg.get("createdAt")
                
                print(f"  {i}. [{origin}] {text}... ({created})")
            
            return messages
        else:
            print(f"❌ Erro: {response.text}")
            return []
            
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        return []

def test_4_context_transfer():
    """Teste 4: Transferir contexto entre chats"""
    print(f"\n🧪 TESTE 4: Transferência de contexto")
    print("=" * 50)
    
    # 1. Criar primeiro chat com contexto
    print("📤 Criando primeiro chat...")
    create_url = f"{BASE_URL}/v1.1/api/external-generative-chat/create"
    create_payload = {"agentId": AGENT_ID}
    
    try:
        response = requests.post(create_url, headers=headers, json=create_payload, timeout=10)
        if response.status_code == 200:
            chat_1 = response.json().get('id')
            print(f"✅ Chat 1 criado: {chat_1}")
            
            # Estabelecer contexto no chat 1
            message_url = f"{BASE_URL}/v1.1/api/external-generative-message/create"
            context_payload = {
                "agentId": AGENT_ID,
                "externalGenerativeChatId": chat_1,
                "prompt": "Contexto importante: Sou Pedro, trabalho como engenheiro e moro em São Paulo",
                "streaming": False
            }
            
            requests.post(message_url, headers=headers, json=context_payload, timeout=15)
            print("📝 Contexto estabelecido no chat 1")
            
            time.sleep(2)
            
            # 2. Buscar histórico do chat 1
            print("📜 Recuperando histórico do chat 1...")
            history_url = f"{BASE_URL}/v1.1/api/external-generative-message/retrieve-multiple"
            history_params = {"externalGenerativeChatIds": str(chat_1)}
            
            history_response = requests.get(history_url, headers=headers, params=history_params, timeout=10)
            if history_response.status_code == 200:
                history_data = history_response.json()
                messages = history_data.get("externalGenerativeMessages", [])
                
                # Construir contexto
                context_summary = "CONTEXTO DA CONVERSA ANTERIOR:\n"
                for msg in messages[-3:]:  # Últimas 3 mensagens
                    origin = "Cliente" if msg.get("origin") == "user" else "Assistente"
                    text = msg.get("text", "")
                    context_summary += f"{origin}: {text}\n"
                
                print(f"📋 Contexto recuperado: {len(messages)} mensagens")
                
                # 3. Criar segundo chat
                response2 = requests.post(create_url, headers=headers, json=create_payload, timeout=10)
                if response2.status_code == 200:
                    chat_2 = response2.json().get('id')
                    print(f"✅ Chat 2 criado: {chat_2}")
                    
                    # 4. Enviar mensagem com contexto transferido
                    transfer_payload = {
                        "agentId": AGENT_ID,
                        "externalGenerativeChatId": chat_2,
                        "prompt": f"{context_summary}\n\nMENSAGEM ATUAL:\nQual é meu nome e profissão?",
                        "streaming": False
                    }
                    
                    transfer_response = requests.post(message_url, headers=headers, json=transfer_payload, timeout=15)
                    if transfer_response.status_code == 200:
                        transfer_data = transfer_response.json()
                        response_text = transfer_data.get('text', '')
                        
                        print(f"📝 Resposta com contexto transferido: {response_text[:150]}...")
                        
                        if "pedro" in response_text.lower() and "engenheiro" in response_text.lower():
                            print("🎉 CONTEXTO TRANSFERIDO COM SUCESSO!")
                            return True
                        else:
                            print("❌ Contexto não foi transferido corretamente")
                            return False
                    else:
                        print("❌ Erro ao enviar mensagem com contexto")
                        return False
                else:
                    print("❌ Erro ao criar chat 2")
                    return False
            else:
                print("❌ Erro ao recuperar histórico")
                return False
        else:
            print("❌ Erro ao criar chat 1")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        return False

def main():
    print("🚀 TESTES DE PRESERVAÇÃO DE CONTEXTO NA ZAIA")
    print("=" * 60)
    
    # Teste 1: Comportamento do externalId
    context_maintained_1, chat_id = test_1_external_id_behavior()
    
    # Teste 2: Chat ID específico + externalId
    context_maintained_2 = test_2_chat_id_with_external_id(chat_id)
    
    # Teste 3: Verificar mensagens
    messages = test_3_retrieve_messages(chat_id)
    
    # Teste 4: Transferência de contexto
    context_transfer_works = test_4_context_transfer()
    
    print("\n" + "=" * 60)
    print("📊 RESUMO DOS RESULTADOS:")
    print(f"✅ ExternalId mantém contexto: {'SIM' if context_maintained_1 else 'NÃO'}")
    print(f"✅ ChatId + ExternalId mantém contexto: {'SIM' if context_maintained_2 else 'NÃO'}")
    print(f"✅ Recuperação de mensagens: {'SIM' if messages else 'NÃO'}")
    print(f"✅ Transferência de contexto: {'SIM' if context_transfer_works else 'NÃO'}")
    
    print("\n🎯 ESTRATÉGIA RECOMENDADA:")
    if context_maintained_1:
        print("→ Usar APENAS externalGenerativeChatExternalId")
        print("→ A Zaia mantém contexto automaticamente")
    elif context_maintained_2:
        print("→ Usar externalGenerativeChatId + externalGenerativeChatExternalId")
        print("→ Manter chat específico para preservar contexto")
    elif context_transfer_works:
        print("→ Transferir contexto manualmente quando chat fica inválido")
        print("→ Buscar histórico e incluir na nova mensagem")
    else:
        print("→ Investigar outras estratégias")
    
    print("\n⚠️  IMPORTANTE: REVOGUE A API KEY IMEDIATAMENTE!")

if __name__ == "__main__":
    main() 