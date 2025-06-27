#!/usr/bin/env python3
"""
Teste de diferentes versões da API Zaia
"""

import requests
import time

# TEMPORÁRIO - REVOGAR ESTA API KEY APÓS O DEBUG!
API_KEY = "d0763f89-7e72-4da2-9172-6d10494d22aa"
AGENT_ID = 52634
BASE_URL = "https://api.zaia.app"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def test_different_api_versions():
    """Testar diferentes versões da API"""
    versions = ["v1.0", "v1.1", "v2.0"]
    
    for version in versions:
        print(f"\n🔍 TESTANDO API {version}")
        print("-" * 40)
        
        # 1. Criar chat
        create_url = f"{BASE_URL}/{version}/api/external-generative-chat/create"
        create_payload = {"agentId": AGENT_ID}
        
        try:
            response = requests.post(create_url, headers=headers, json=create_payload, timeout=10)
            print(f"Criar chat - Status: {response.status_code}")
            
            if response.status_code in [200, 201]:
                data = response.json()
                chat_id = data.get('id')
                print(f"✅ Chat criado: {chat_id}")
                
                # Aguardar um pouco
                print("⏳ Aguardando 3 segundos...")
                time.sleep(3)
                
                # 2. Tentar enviar mensagem
                message_url = f"{BASE_URL}/{version}/api/external-generative-message/create"
                message_payload = {
                    "agentId": AGENT_ID,
                    "externalGenerativeChatId": chat_id,
                    "prompt": f"Teste com API {version}",
                    "streaming": False
                }
                
                msg_response = requests.post(message_url, headers=headers, json=message_payload, timeout=15)
                print(f"Enviar mensagem - Status: {msg_response.status_code}")
                
                if msg_response.status_code == 200:
                    print(f"✅ SUCESSO COM API {version}!")
                    print(f"Resposta: {msg_response.text}")
                    return version
                else:
                    print(f"❌ Falha: {msg_response.text}")
            else:
                print(f"❌ Falha ao criar chat: {response.text}")
                
        except Exception as e:
            print(f"❌ Erro com API {version}: {str(e)}")
    
    return None

def test_minimal_payload():
    """Testar com payload mínimo"""
    print(f"\n🎯 TESTE: Payload mínimo")
    print("-" * 40)
    
    # Criar chat primeiro
    create_url = f"{BASE_URL}/v1.1/api/external-generative-chat/create"
    create_payload = {"agentId": AGENT_ID}
    
    try:
        response = requests.post(create_url, headers=headers, json=create_payload, timeout=10)
        if response.status_code in [200, 201]:
            chat_id = response.json().get('id')
            print(f"Chat criado: {chat_id}")
            
            # Payload super mínimo
            message_url = f"{BASE_URL}/v1.1/api/external-generative-message/create"
            minimal_payload = {
                "agentId": AGENT_ID,
                "externalGenerativeChatId": chat_id,
                "prompt": "teste"
            }
            
            print(f"Payload mínimo: {minimal_payload}")
            
            time.sleep(2)  # Aguardar um pouco
            
            msg_response = requests.post(message_url, headers=headers, json=minimal_payload, timeout=15)
            print(f"Status: {msg_response.status_code}")
            print(f"Resposta: {msg_response.text}")
            
            if msg_response.status_code == 200:
                print("✅ SUCESSO com payload mínimo!")
                return True
            else:
                print("❌ Falha com payload mínimo")
                return False
        else:
            print("❌ Falha ao criar chat para teste mínimo")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        return False

def test_check_chat_exists():
    """Verificar se o chat realmente existe após criação"""
    print(f"\n🔍 TESTE: Verificar existência do chat")
    print("-" * 40)
    
    # Criar chat
    create_url = f"{BASE_URL}/v1.1/api/external-generative-chat/create"
    create_payload = {"agentId": AGENT_ID}
    
    try:
        response = requests.post(create_url, headers=headers, json=create_payload, timeout=10)
        if response.status_code in [200, 201]:
            chat_id = response.json().get('id')
            print(f"Chat criado: {chat_id}")
            
            # Verificar se o chat existe na listagem
            list_url = f"{BASE_URL}/v1.1/api/external-generative-chat/retrieve-multiple"
            params = {"agentIds": [AGENT_ID], "limit": 10}
            
            list_response = requests.get(list_url, headers=headers, params=params, timeout=10)
            if list_response.status_code == 200:
                chats = list_response.json().get("externalGenerativeChats", [])
                chat_ids = [c.get('id') for c in chats]
                
                if chat_id in chat_ids:
                    print(f"✅ Chat {chat_id} encontrado na listagem!")
                    
                    # Tentar buscar chat específico
                    retrieve_url = f"{BASE_URL}/v1.1/api/external-generative-chat/retrieve"
                    retrieve_params = {"id": chat_id}
                    
                    retrieve_response = requests.get(retrieve_url, headers=headers, params=retrieve_params, timeout=10)
                    print(f"Busca específica - Status: {retrieve_response.status_code}")
                    
                    if retrieve_response.status_code == 200:
                        print("✅ Chat encontrado na busca específica!")
                        chat_data = retrieve_response.json()
                        print(f"Status do chat: {chat_data.get('status')}")
                        return True
                    else:
                        print(f"❌ Chat não encontrado na busca específica: {retrieve_response.text}")
                        return False
                else:
                    print(f"❌ Chat {chat_id} NÃO encontrado na listagem!")
                    return False
            else:
                print("❌ Falha ao listar chats")
                return False
        else:
            print("❌ Falha ao criar chat")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        return False

def main():
    print("🚀 TESTANDO DIFERENTES VERSÕES E MÉTODOS DA API ZAIA")
    print("=" * 60)
    
    # Teste 1: Diferentes versões da API
    working_version = test_different_api_versions()
    
    # Teste 2: Payload mínimo
    minimal_works = test_minimal_payload()
    
    # Teste 3: Verificar se chat existe
    chat_exists = test_check_chat_exists()
    
    print("\n" + "=" * 60)
    print("📊 RESUMO:")
    print(f"✅ Versão que funciona: {working_version or 'NENHUMA'}")
    print(f"✅ Payload mínimo: {'SIM' if minimal_works else 'NÃO'}")
    print(f"✅ Chat existe após criação: {'SIM' if chat_exists else 'NÃO'}")
    
    print("\n⚠️  IMPORTANTE: REVOGUE A API KEY IMEDIATAMENTE!")

if __name__ == "__main__":
    main() 