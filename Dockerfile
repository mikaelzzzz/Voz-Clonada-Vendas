FROM python:3.11-slim

WORKDIR /app

# Instala dependências do sistema necessárias
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copia os arquivos do projeto
COPY requirements.txt .

# Instala as dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código (inclui main.py e pasta app/)
COPY . .

# Cloud Run define a porta via variável $PORT
# Não é necessário EXPOSE, mas não atrapalha; manteremos comentado
# EXPOSE 8080

# Comando para iniciar a aplicação FastAPI usando gunicorn
# Cloud Run injeta $PORT; o app está em main:app
# Use shell form (sem colchetes) para garantir a expansão de $PORT no Cloud Run
CMD gunicorn --workers 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT main:app