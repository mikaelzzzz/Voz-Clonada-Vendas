#!/usr/bin/env python3
"""
Script de debug para testar a API da Zaia diretamente
ATENÇÃO: Este script contém API key temporária - REVOGAR APÓS USO!
"""

import requests
import json
import asyncio
import aiohttp

# TEMPORÁRIO - REVOGAR ESTA API KEY APÓS O DEBUG!
API_KEY = "d0763f89-7e72-4da2-9172-6d10494d22aa"
AGENT_ID = 52634
BASE_URL = "https://api.zaia.app"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def test_1_agent_info():
    """Teste 1: Verificar se o agent existe e está ativo"""
    print("🔍 TESTE 1: Verificando informações do Agent...")
    
    url = f"{BASE_URL}/v1.1/api/agent/{AGENT_ID}"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Agent encontrado:")
            print(f"   ID: {data.get('id')}")
            print(f"   Nome: {data.get('name')}")
            print(f"   Status: {data.get('status')}")
            print(f"   Criado: {data.get('createdAt')}")
            return True
        else:
            print(f"❌ Erro ao buscar agent: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Erro na requisição: {str(e)}")
        return False

def test_2_create_simple_chat():
    """Teste 2: Criar um chat simples"""
    print("\n🆕 TESTE 2: Criando chat simples...")
    
    url = f"{BASE_URL}/v1.1/api/external-generative-chat/create"
    payload = {"agentId": AGENT_ID}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Resposta: {response.text}")
        
        if response.status_code in [200, 201]:
            data = response.json()
            chat_id = data.get('id')
            print(f"✅ Chat criado com sucesso: {chat_id}")
            return chat_id
        else:
            print(f"❌ Erro ao criar chat: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Erro na requisição: {str(e)}")
        return None

def test_3_send_message_basic(chat_id):
    """Teste 3: Enviar mensagem básica sem externalId"""
    if not chat_id:
        print("\n⏭️ TESTE 3: Pulado (sem chat_id)")
        return False
        
    print(f"\n📤 TESTE 3: Enviando mensagem básica para chat {chat_id}...")
    
    url = f"{BASE_URL}/v1.1/api/external-generative-message/create"
    payload = {
        "agentId": AGENT_ID,
        "externalGenerativeChatId": chat_id,
        "prompt": "Olá, este é um teste básico",
        "streaming": False,
        "asMarkdown": False
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        print(f"Status: {response.status_code}")
        print(f"Resposta: {response.text}")
        
        if response.status_code == 200:
            print("✅ Mensagem enviada com sucesso!")
            return True
        else:
            print(f"❌ Erro ao enviar mensagem: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Erro na requisição: {str(e)}")
        return False

def test_4_send_message_with_external_id(chat_id):
    """Teste 4: Enviar mensagem COM externalId"""
    if not chat_id:
        print("\n⏭️ TESTE 4: Pulado (sem chat_id)")
        return False
        
    print(f"\n📱 TESTE 4: Enviando mensagem COM externalId para chat {chat_id}...")
    
    url = f"{BASE_URL}/v1.1/api/external-generative-message/create"
    payload = {
        "agentId": AGENT_ID,
        "externalGenerativeChatId": chat_id,
        "externalGenerativeChatExternalId": "5511975578651",  # Telefone como ID único
        "prompt": "Olá, este é um teste com externalId",
        "streaming": False,
        "asMarkdown": False,
        "custom": {"whatsapp": "5511975578651"}
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        print(f"Status: {response.status_code}")
        print(f"Resposta: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            returned_chat_id = data.get('externalGenerativeChatId')
            print(f"✅ Mensagem enviada com sucesso!")
            print(f"   Chat ID original: {chat_id}")
            print(f"   Chat ID retornado: {returned_chat_id}")
            
            if returned_chat_id != chat_id:
                print(f"⚠️ ATENÇÃO: Zaia retornou chat ID diferente!")
            
            return True
        else:
            print(f"❌ Erro ao enviar mensagem: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Erro na requisição: {str(e)}")
        return False

def test_5_send_message_only_external_id():
    """Teste 5: Enviar mensagem APENAS com externalId (sem chat_id)"""
    print(f"\n🎯 TESTE 5: Enviando mensagem APENAS com externalId...")
    
    url = f"{BASE_URL}/v1.1/api/external-generative-message/create"
    payload = {
        "agentId": AGENT_ID,
        "externalGenerativeChatExternalId": "5511975578651",  # Apenas external ID
        "prompt": "Olá, este é um teste APENAS com externalId",
        "streaming": False,
        "asMarkdown": False,
        "custom": {"whatsapp": "5511975578651"}
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        print(f"Status: {response.status_code}")
        print(f"Resposta: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            returned_chat_id = data.get('externalGenerativeChatId')
            print(f"✅ Mensagem enviada com sucesso!")
            print(f"   Chat ID retornado pela Zaia: {returned_chat_id}")
            print(f"   🎯 ESTE É O COMPORTAMENTO ESPERADO!")
            return True
        else:
            print(f"❌ Erro ao enviar mensagem: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Erro na requisição: {str(e)}")
        return False

def test_6_list_recent_chats():
    """Teste 6: Listar chats recentes para o telefone"""
    print(f"\n📋 TESTE 6: Listando chats recentes do agent...")
    
    url = f"{BASE_URL}/v1.1/api/external-generative-chat/retrieve-multiple"
    params = {
        "agentIds": [AGENT_ID],
        "limit": 10,
        "offset": 0,
        "sortBy": "createdAt",
        "sortOrder": "desc"
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            chats = data.get("externalGenerativeChats", [])
            print(f"✅ Encontrados {len(chats)} chats:")
            
            for chat in chats[:5]:  # Mostrar apenas os 5 mais recentes
                chat_id = chat.get("id")
                phone = chat.get("phoneNumber")
                channel = chat.get("channel")
                status = chat.get("status")
                created = chat.get("createdAt")
                external_id = chat.get("externalId")
                
                print(f"   Chat {chat_id}: phone={phone}, channel={channel}, status={status}, externalId={external_id}")
                
                if phone == "5511975578651":
                    print(f"   🎯 ESTE É O CHAT DO TELEFONE DE TESTE!")
            
            return True
        else:
            print(f"❌ Erro ao listar chats: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Erro na requisição: {str(e)}")
        return False

def main():
    """Executar todos os testes em sequência"""
    print("🚀 INICIANDO DEBUG DA API ZAIA")
    print("=" * 50)
    
    # Teste 1: Verificar agent
    agent_ok = test_1_agent_info()
    
    if not agent_ok:
        print("\n❌ Agent não encontrado - parando testes")
        return
    
    # Teste 2: Criar chat
    chat_id = test_2_create_simple_chat()
    
    # Teste 3: Enviar mensagem básica
    test_3_send_message_basic(chat_id)
    
    # Teste 4: Enviar mensagem com external ID
    test_4_send_message_with_external_id(chat_id)
    
    # Teste 5: Enviar mensagem APENAS com external ID (comportamento desejado)
    test_5_send_message_only_external_id()
    
    # Teste 6: Listar chats recentes
    test_6_list_recent_chats()
    
    print("\n" + "=" * 50)
    print("🏁 DEBUG CONCLUÍDO")
    print("\n⚠️  IMPORTANTE: REVOGUE A API KEY d0763f89-7e72-4da2-9172-6d10494d22aa IMEDIATAMENTE!")

if __name__ == "__main__":
    main() 