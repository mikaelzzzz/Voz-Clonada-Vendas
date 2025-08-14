# Melhorias de Contexto - Sistema de WhatsApp

## Problemas Resolvidos

### 1. **Mensagens Quebradas e Perda de Contexto**
- **Problema**: Quando o cliente envia mensagens quebradas, o agente da Zaia perde o contexto
- **Solução**: Implementado delay de 30 segundos para mensagens que precisam de contexto

### 2. **Mensagens do Sistema Perdendo Contexto**
- **Problema**: Quando outros códigos enviam mensagens (ex: confirmação de reunião), o agente da Zaia fica perdido
- **Solução**: Sistema de marcação de mensagens do sistema com delay de contexto automático

## Como Funciona

### Sistema de Delay de Contexto

O sistema agora verifica automaticamente se deve usar delay de contexto baseado em:

1. **Tempo da última mensagem do sistema**: Se foi enviada há menos de 5 minutos
2. **Tipo de mensagem**: Mensagens marcadas como "system", "meeting_confirmation", etc.

### Endpoint para Marcar Mensagens do Sistema

Para que outros códigos marquem quando enviam mensagens do sistema:

```bash
POST /webhook
Content-Type: application/json

{
    "type": "system_message_sent",
    "phone": "5511999999999",
    "message_type": "meeting_confirmation"
}
```

**Tipos de mensagem suportados:**
- `system` - Mensagem genérica do sistema
- `meeting_confirmation` - Confirmação de reunião agendada
- `payment_confirmation` - Confirmação de pagamento
- `reminder` - Lembrete automático
- `notification` - Notificação geral

## Implementação no Seu Código

### 1. **Quando Enviar Confirmação de Reunião**

No seu código que agenda reuniões, após enviar a mensagem de confirmação:

```python
import requests

# Após enviar a mensagem de confirmação
confirmation_message = "Sua reunião foi agendada para o dia XX às 12:00"
# ... código para enviar mensagem ...

# Marca no sistema de contexto
webhook_data = {
    "type": "system_message_sent",
    "phone": "5511999999999",  # Telefone do cliente
    "message_type": "meeting_confirmation"
}

response = requests.post("https://seu-dominio.com/webhook", json=webhook_data)
```

### 2. **Delay Automático**

Quando o cliente responder à confirmação de reunião:
- O sistema detecta automaticamente que foi enviada uma mensagem do sistema
- Aplica um delay de 30 segundos antes de responder
- Evita que o agente da Zaia perca o contexto

## Configuração

### Variáveis de Ambiente

```env
# O delay padrão é de 30 segundos, mas pode ser configurado
CONTEXT_DELAY_SECONDS=30
```

### Cache

O sistema usa cache em memória por padrão, mas pode ser expandido para Redis no futuro.

## Monitoramento

### Logs

O sistema registra todas as ações de contexto:

```
📝 Mensagem do sistema marcada para 5511999999999: meeting_confirmation
⏰ Usando delay de contexto para 5511999999999 (última mensagem do sistema há 45s)
✅ Sem delay de contexto para 5511999999999 (última mensagem do sistema há 6m 30s)
```

### Status de Resposta

```json
{
    "status": "system_message_marked",
    "phone": "5511999999999",
    "message_type": "meeting_confirmation",
    "timestamp": "2024-01-15T10:30:00"
}
```

## Benefícios

1. **Contexto Preservado**: O agente da Zaia não perde o contexto das conversas
2. **Experiência do Cliente**: Respostas mais naturais e contextualizadas
3. **Integração Simples**: Fácil integração com outros sistemas
4. **Automático**: Não requer intervenção manual
5. **Configurável**: Delay e tipos de mensagem personalizáveis

## Troubleshooting

### Problema: Delay não está funcionando

**Verificar:**
1. Se a mensagem do sistema foi marcada corretamente
2. Se o webhook está sendo chamado
3. Logs do sistema para ver se o delay foi aplicado

### Problema: Contexto ainda está sendo perdido

**Verificar:**
1. Se o telefone está sendo normalizado corretamente
2. Se o cache está funcionando
3. Se há conflitos de timezone

### Problema: Performance lenta

**Soluções:**
1. Reduzir o delay de contexto (padrão: 30s)
2. Implementar cache Redis para melhor performance
3. Otimizar verificações de contexto
