#!/usr/bin/env python3
"""
Script para listar todos os agents disponíveis na conta Zaia
"""

import requests

# TEMPORÁRIO - REVOGAR ESTA API KEY APÓS O DEBUG!
API_KEY = "d0763f89-7e72-4da2-9172-6d10494d22aa"
BASE_URL = "https://api.zaia.app"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def list_all_agents():
    """Listar todos os agents disponíveis"""
    print("🔍 LISTANDO TODOS OS AGENTS DISPONÍVEIS...")
    
    url = f"{BASE_URL}/v1.1/api/agent"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            agents = data.get('agents', []) or data.get('data', []) or [data] if isinstance(data, dict) else data
            
            print(f"✅ Encontrados {len(agents)} agents:")
            print("-" * 50)
            
            for agent in agents:
                agent_id = agent.get('id')
                name = agent.get('name', 'Sem nome')
                status = agent.get('status', 'Desconhecido')
                created = agent.get('createdAt', 'N/A')
                
                print(f"ID: {agent_id}")
                print(f"Nome: {name}")
                print(f"Status: {status}")
                print(f"Criado: {created}")
                print("-" * 30)
                
            return agents
        else:
            print(f"❌ Erro ao listar agents: {response.status_code}")
            print(f"Resposta: {response.text}")
            return []
            
    except Exception as e:
        print(f"❌ Erro na requisição: {str(e)}")
        return []

def test_chat_with_correct_format():
    """Testar busca de chats com formato correto do agentIds"""
    print("\n🔍 TESTANDO BUSCA DE CHATS COM FORMATO ARRAY...")
    
    # Primeiro tentar com o agent 52634 no formato array
    url = f"{BASE_URL}/v1.1/api/external-generative-chat/retrieve-multiple"
    
    # Testar diferentes formatos
    formats_to_test = [
        {"agentIds": [52634], "limit": 5},  # Array de números
        {"agentIds": "52634", "limit": 5},   # String
        {"agentId": 52634, "limit": 5},      # Campo singular
    ]
    
    for i, params in enumerate(formats_to_test, 1):
        print(f"\n--- Teste {i}: {params} ---")
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                chats = data.get("externalGenerativeChats", [])
                print(f"✅ Sucesso! Encontrados {len(chats)} chats")
                
                # Mostrar alguns chats do WhatsApp
                whatsapp_chats = [c for c in chats if c.get('channel') == 'whatsapp'][:3]
                if whatsapp_chats:
                    print("📱 Chats do WhatsApp encontrados:")
                    for chat in whatsapp_chats:
                        chat_id = chat.get('id')
                        phone = chat.get('phoneNumber')
                        status = chat.get('status')
                        print(f"   Chat {chat_id}: {phone} ({status})")
                
                return True
            else:
                print(f"❌ Erro: {response.status_code}")
                print(f"Resposta: {response.text}")
                
        except Exception as e:
            print(f"❌ Erro: {str(e)}")
    
    return False

def main():
    print("🚀 DESCOBRINDO AGENTS CORRETOS")
    print("=" * 50)
    
    # Listar todos os agents
    agents = list_all_agents()
    
    # Testar formato correto para busca de chats
    test_chat_with_correct_format()
    
    print("\n" + "=" * 50)
    print("🏁 ANÁLISE CONCLUÍDA")
    print("\n⚠️  IMPORTANTE: REVOGUE A API KEY IMEDIATAMENTE!")

if __name__ == "__main__":
    main() 