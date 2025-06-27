#!/usr/bin/env python3
"""
Teste específico para enviar mensagem com agent 52634
"""

import requests

# TEMPORÁRIO - REVOGAR ESTA API KEY APÓS O DEBUG!
API_KEY = "d0763f89-7e72-4da2-9172-6d10494d22aa"
AGENT_ID = 52634
BASE_URL = "https://api.zaia.app"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def test_send_message_only_external_id():
    """Teste: Enviar mensagem APENAS com externalId"""
    print("🎯 TESTE: Enviando mensagem APENAS com externalId...")
    
    url = f"{BASE_URL}/v1.1/api/external-generative-message/create"
    payload = {
        "agentId": AGENT_ID,
        "externalGenerativeChatExternalId": "5511975578651",
        "prompt": "Teste de mensagem com agent 52634",
        "streaming": False,
        "asMarkdown": False,
        "custom": {"whatsapp": "5511975578651"}
    }
    
    print(f"URL: {url}")
    print(f"Payload: {payload}")
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        print(f"Status: {response.status_code}")
        print(f"Resposta: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ SUCESSO! Mensagem enviada!")
            print(f"Chat ID retornado: {data.get('externalGenerativeChatId')}")
            print(f"Resposta: {data.get('response', 'N/A')}")
            return True
        else:
            print(f"❌ Erro: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Erro na requisição: {str(e)}")
        return False

def test_create_chat_first():
    """Teste: Criar chat primeiro, depois enviar mensagem"""
    print("\n🆕 TESTE: Criar chat primeiro...")
    
    # 1. Criar chat
    create_url = f"{BASE_URL}/v1.1/api/external-generative-chat/create"
    create_payload = {"agentId": AGENT_ID}
    
    try:
        response = requests.post(create_url, headers=headers, json=create_payload, timeout=10)
        print(f"Criação - Status: {response.status_code}")
        print(f"Criação - Resposta: {response.text}")
        
        if response.status_code in [200, 201]:
            data = response.json()
            chat_id = data.get('id')
            print(f"✅ Chat criado: {chat_id}")
            
            # 2. Enviar mensagem para o chat criado
            message_url = f"{BASE_URL}/v1.1/api/external-generative-message/create"
            message_payload = {
                "agentId": AGENT_ID,
                "externalGenerativeChatId": chat_id,
                "externalGenerativeChatExternalId": "5511975578651",
                "prompt": "Teste com chat recém-criado",
                "streaming": False,
                "asMarkdown": False,
                "custom": {"whatsapp": "5511975578651"}
            }
            
            print(f"\n📤 Enviando mensagem para chat {chat_id}...")
            msg_response = requests.post(message_url, headers=headers, json=message_payload, timeout=15)
            print(f"Mensagem - Status: {msg_response.status_code}")
            print(f"Mensagem - Resposta: {msg_response.text}")
            
            if msg_response.status_code == 200:
                print("✅ SUCESSO! Mensagem enviada para chat recém-criado!")
                return True
            else:
                print("❌ Falha ao enviar mensagem para chat recém-criado")
                return False
        else:
            print("❌ Falha ao criar chat")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        return False

def test_with_existing_chat():
    """Teste: Usar chat existente 3300163"""
    print("\n📱 TESTE: Usar chat existente 3300163...")
    
    url = f"{BASE_URL}/v1.1/api/external-generative-message/create"
    payload = {
        "agentId": AGENT_ID,
        "externalGenerativeChatId": 3300163,  # Chat que sabemos que existe
        "externalGenerativeChatExternalId": "5511975578651",
        "prompt": "Teste com chat existente 3300163",
        "streaming": False,
        "asMarkdown": False,
        "custom": {"whatsapp": "5511975578651"}
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        print(f"Status: {response.status_code}")
        print(f"Resposta: {response.text}")
        
        if response.status_code == 200:
            print("✅ SUCESSO! Mensagem enviada para chat existente!")
            return True
        else:
            print("❌ Falha com chat existente")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        return False

def main():
    print("🚀 TESTANDO ENVIO DE MENSAGENS COM AGENT 52634")
    print("=" * 60)
    
    # Teste 1: Apenas com externalId
    success1 = test_send_message_only_external_id()
    
    # Teste 2: Criar chat primeiro
    success2 = test_create_chat_first()
    
    # Teste 3: Chat existente
    success3 = test_with_existing_chat()
    
    print("\n" + "=" * 60)
    print("📊 RESUMO DOS TESTES:")
    print(f"✅ Apenas externalId: {'SIM' if success1 else 'NÃO'}")
    print(f"✅ Chat novo: {'SIM' if success2 else 'NÃO'}")
    print(f"✅ Chat existente: {'SIM' if success3 else 'NÃO'}")
    
    if any([success1, success2, success3]):
        print("\n🎉 PELO MENOS UM TESTE FUNCIONOU!")
    else:
        print("\n😞 TODOS OS TESTES FALHARAM")
    
    print("\n⚠️  IMPORTANTE: REVOGUE A API KEY IMEDIATAMENTE!")

if __name__ == "__main__":
    main() 