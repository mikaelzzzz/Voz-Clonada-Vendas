# WhatsApp AI Assistant com Voz Clonada

Este projeto implementa um assistente de IA para WhatsApp que utiliza voz clonada para responder mensagens de áudio. O sistema integra várias tecnologias:

- **Z-API**: Para integração com WhatsApp
- **Zaia**: Para processamento de linguagem natural e intenções
- **ElevenLabs**: Para clonagem e geração de voz
- **Whisper**: Para transcrição de áudio

## Funcionalidades

- Recebimento e processamento de mensagens de texto e áudio do WhatsApp
- Detecção de intenções usando a Zaia
- Transcrição de áudio usando Whisper
- Geração de respostas em áudio usando voz clonada via ElevenLabs
- Sistema de fila para processamento assíncrono
- Tratamento robusto de erros

## Requisitos

- Python 3.8+
- Flask
- aiohttp
- python-dotenv

## Configuração

1. Clone o repositório:
```bash
git clone [URL_DO_REPOSITORIO]
cd pyserver
```

2. Crie um ambiente virtual e instale as dependências:
```bash
python -m venv venv
source venv/bin/activate  # No Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Configure as variáveis de ambiente em um arquivo `.env`:
```env
# Z-API
Z_API_ID=seu_id
Z_API_TOKEN=seu_token
Z_API_SECURITY_TOKEN=seu_token_seguranca

# Zaia
ZAIA_API_KEY=sua_chave
ZAIA_AGENT_ID=seu_agent_id
ZAIA_BASE_URL=https://api.zaia.tech

# ElevenLabs
ELEVENLABS_API_KEY=sua_chave
VOICE_ID=id_da_voz

# Cloudinary (opcional)
CLOUDINARY_CLOUD_NAME=seu_cloud_name
CLOUDINARY_API_KEY=sua_chave
CLOUDINARY_API_SECRET=seu_secret
```

## Estrutura do Projeto

```
pyserver/
├── app/
│   ├── config/
│   │   └── settings.py
│   ├── routes/
│   │   └── webhook_routes.py
│   └── services/
│       ├── z_api_service.py
│       ├── zaia_service.py
│       ├── elevenlabs_service.py
│       ├── whisper_service.py
│       ├── intent_service.py
│       └── queue_service.py
├── app.py
└── requirements.txt
```

## Deploy

### Local

1. Ative o ambiente virtual:
```bash
source venv/bin/activate  # No Windows: venv\Scripts\activate
```

2. Execute o servidor:
```bash
python app.py
```

### Render

1. Conecte seu repositório GitHub ao Render
2. Crie um novo Web Service
3. Configure as variáveis de ambiente no Render
4. O Render usará automaticamente o `requirements.txt`

## Webhooks

Configure o webhook no Z-API para apontar para:
```
https://[seu-app].onrender.com/webhook
```

## Monitoramento

O endpoint `/health` está disponível para monitoramento:
```
GET https://[seu-app].onrender.com/health
```

## Logs

Os logs são configurados para fornecer informações detalhadas sobre:
- Recebimento de mensagens
- Processamento de áudio
- Detecção de intenções
- Erros e exceções

## Contribuição

1. Faça um Fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## Licença

Este projeto está sob a licença MIT. 