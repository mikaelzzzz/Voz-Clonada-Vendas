FROM python:3.9-slim

WORKDIR /app

# Instala dependências do sistema necessárias
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copia os arquivos do projeto
COPY requirements.txt .
COPY app.py .
COPY .env .

# Instala as dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Expõe a porta que o Flask vai usar
EXPOSE 5000

# Comando para iniciar a aplicação
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0"] 