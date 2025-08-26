FROM python:3.11-slim

WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    build-essential \
    cmake \
    patchelf \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copiar arquivos de requisitos primeiro para aproveitar o cache do Docker
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Corrigir permissões para ctranslate2
RUN find /usr/local/lib/python3.11/site-packages/ctranslate2 -name "*.so*" -exec patchelf --remove-needed libc.so.6 {} \; || true
RUN find /usr/local/lib/python3.11/site-packages/ctranslate2 -name "*.so*" -exec patchelf --set-rpath '$ORIGIN' {} \; || true

# Desativar verificação de segurança da pilha executável
ENV PYTHONMALLOC=malloc
ENV CT2_USE_EXPERIMENTAL_PACKED_GEMM=1
ENV CT2_VERBOSE=1

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