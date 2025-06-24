# Karol Vendas - Serviço de Voz Clonada

Este serviço integra WhatsApp (via Z-API) com a plataforma Zaia, usando voz clonada do ElevenLabs para respostas em áudio.

## Funcionalidades

- Recebe mensagens do WhatsApp via Z-API
- Processa mensagens de texto e áudio
- Integra com a plataforma Zaia para respostas inteligentes
- Gera respostas em áudio usando voz clonada do ElevenLabs
- Armazena áudios no Cloudinary

## Configuração

1. Clone o repositório
2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Configure as variáveis de ambiente em um arquivo `.env`:

```env
# ElevenLabs Configuration
ELEVENLABS_API_KEY=your_elevenlabs_api_key
VOICE_ID=your_voice_id

# Zaia Configuration
ZAIA_API_KEY=your_zaia_api_key
ZAIA_AGENT_ID=your_zaia_agent_id

# Z-API Configuration
Z_API_ID=your_z_api_instance_id
Z_API_TOKEN=your_z_api_instance_token

# Cloudinary Configuration
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret

# Server Configuration
PORT=5000
PUBLIC_URL=https://your-server.com
```

4. Configure os webhooks na Z-API:
   - Acesse o painel da Z-API
   - Vá em "Editar instância"
   - Configure os seguintes webhooks apontando para seu servidor:
     * Webhook de recebimento: `{seu-servidor}/webhook/z-api`
     * Webhook de status: `{seu-servidor}/webhook/z-api`
     * Webhook de desconexão: `{seu-servidor}/webhook/z-api`

## Executando o Servidor

```bash
python app.py
```

O servidor estará disponível na porta especificada na variável de ambiente PORT (padrão: 5000).

## Endpoints

- `POST /webhook/z-api`: Webhook para receber eventos da Z-API
- `GET /health`: Endpoint de verificação de saúde do servidor

## Fluxo de Funcionamento

1. **Mensagem de Texto**:
   - WhatsApp -> Z-API -> Servidor -> Zaia -> Servidor -> Z-API -> WhatsApp

2. **Mensagem de Áudio**:
   - Recebimento: WhatsApp -> Z-API -> Servidor
   - Transcrição: Whisper
   - Processamento: Zaia
   - Resposta em Áudio: ElevenLabs -> Cloudinary
   - Envio: Servidor -> Z-API -> WhatsApp

## Docker

O serviço pode ser executado em um container Docker:

```bash
docker build -t karol-vendas-voice .
docker run -p 5000:5000 --env-file .env karol-vendas-voice
```

## Monitoramento

- Use o endpoint `/health` para monitorar a saúde do serviço
- Monitore os logs do servidor para debug
- Verifique o painel da Z-API para status da conexão com WhatsApp

## Limitações

- A Z-API requer uma sessão do WhatsApp Web
- O WhatsApp tem limites de envio de mensagens
- Arquivos de áudio devem ter menos de 16MB
- O servidor precisa ter HTTPS para receber webhooks da Z-API 