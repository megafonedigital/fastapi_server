# FastAPI Video Downloader e Transcrição

API para download de vídeos e transcrição de áudio/vídeo utilizando FastAPI, MinIO, yt-dlp e faster-whisper.

## Funcionalidades

- Download de vídeos de diversas plataformas (YouTube, Vimeo, etc.)
- Transcrição de áudio/vídeo utilizando o modelo Whisper da OpenAI
- Armazenamento de arquivos em MinIO (compatível com S3)
- Processamento assíncrono de tarefas em background
- Autenticação via API Key
- Logging estruturado em formato JSON

## Requisitos

- Python 3.10+
- Docker e Docker Compose (para execução em contêineres)
- FFmpeg (para processamento de áudio/vídeo)

## Configuração

### Variáveis de Ambiente

Copie o arquivo `.env.example` para `.env` e ajuste as configurações conforme necessário:

```bash
cp app/.env.example app/.env
```

Principais variáveis:

- `API_KEY`: Chave de API para autenticação
- `MINIO_*`: Configurações do MinIO
- `WHISPER_*`: Configurações do modelo Whisper

## Instalação

### Usando Docker (recomendado)

```bash
# Clone o repositório
git clone <repositório>
cd fastapi_server

# Inicie os contêineres
docker-compose up -d
```

A API estará disponível em http://localhost:8000 e a interface do MinIO em http://localhost:9001.

### Instalação Local

```bash
# Clone o repositório
git clone <repositório>
cd fastapi_server

# Crie um ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Instale as dependências
pip install -r requirements.txt

# Inicie o servidor
uvicorn app.main:app --reload
```

## Uso da API

### Documentação

A documentação interativa da API está disponível em:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Autenticação

Todas as requisições devem incluir o cabeçalho `X-API-Key` com a chave de API configurada.

### Endpoints Principais

#### Download de Vídeos

```bash
# Iniciar download
curl -X POST http://localhost:8000/api/v1/downloads \
  -H "X-API-Key: your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "format": "mp4"}'

# Verificar status do download
curl -X GET http://localhost:8000/api/v1/downloads/status/{task_id} \
  -H "X-API-Key: your-api-key-here"

# Obter informações do vídeo
curl -X GET http://localhost:8000/api/v1/downloads/{video_id} \
  -H "X-API-Key: your-api-key-here"
```

#### Transcrição de Áudio/Vídeo

```bash
# Iniciar transcrição
curl -X POST http://localhost:8000/api/v1/transcriptions \
  -H "X-API-Key: your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "language": "pt"}'

# Verificar status da transcrição
curl -X GET http://localhost:8000/api/v1/transcriptions/status/{task_id} \
  -H "X-API-Key: your-api-key-here"

# Obter resultado da transcrição
curl -X GET http://localhost:8000/api/v1/transcriptions/{transcription_id} \
  -H "X-API-Key: your-api-key-here"
```

## Estrutura do Projeto

```
.
├── app/
│   ├── api/                # Rotas da API
│   ├── core/               # Configurações e funcionalidades centrais
│   ├── models/             # Modelos de dados
│   ├── services/           # Serviços de negócio
│   └── main.py             # Ponto de entrada da aplicação
├── tests/                  # Testes
├── Dockerfile              # Configuração do Docker
├── docker-compose.yml      # Configuração do Docker Compose
└── requirements.txt        # Dependências Python
```

## Desenvolvimento

### Testes

```bash
pytest
```

### Logs

Os logs são gerados em formato JSON e incluem um ID de correlação para rastreamento de requisições.

## Licença

Este projeto está licenciado sob a licença MIT - veja o arquivo LICENSE para detalhes.