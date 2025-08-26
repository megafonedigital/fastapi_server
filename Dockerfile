FROM python:3.11-slim

WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copiar arquivos de requisitos primeiro para aproveitar o cache do Docker
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Configuração do ambiente
# Nenhuma configuração especial necessária para o Whisper da OpenAI

# Copiar o código da aplicação
COPY app/ ./app/

# Ensure app directory exists
RUN mkdir -p /app/app

# Criar diretório de trabalho temporário
RUN mkdir -p /tmp/workdir && chmod 777 /tmp/workdir

# Expor a porta da aplicação
EXPOSE 8000

# Copiar e configurar o script de inicialização
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Comando para iniciar a aplicação
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]