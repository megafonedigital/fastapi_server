import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.core.config import settings
from app.models.types import TaskManager

# Cliente de teste
client = TestClient(app)

# Mock API Key para testes
TEST_API_KEY = "test-api-key"

# Headers de autenticação
auth_headers = {"X-API-Key": TEST_API_KEY}


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Configuração e limpeza para cada teste"""
    # Setup - sobrescreve a API key para testes
    original_api_key = settings.API_KEY
    settings.API_KEY = TEST_API_KEY
    
    # Limpa o gerenciador de tarefas antes de cada teste
    TaskManager._tasks = {}
    
    yield
    
    # Teardown - restaura a API key original
    settings.API_KEY = original_api_key
    
    # Limpa o gerenciador de tarefas após cada teste
    TaskManager._tasks = {}


def test_health_check():
    """Testa o endpoint de health check"""
    with patch("app.core.storage.storage.check_connection", return_value=True):
        response = client.get("/api/v1/health", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert data["storage"] == "connected"


def test_health_check_storage_error():
    """Testa o endpoint de health check com erro no storage"""
    with patch("app.core.storage.storage.check_connection", side_effect=Exception("Connection error")):
        response = client.get("/api/v1/health", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert data["storage"] == "error"


def test_unauthorized_access():
    """Testa acesso não autorizado"""
    response = client.get("/api/v1/health")  # Sem cabeçalho de autenticação
    assert response.status_code == 401
    
    response = client.get("/api/v1/health", headers={"X-API-Key": "invalid-key"})
    assert response.status_code == 401


def test_create_download():
    """Testa a criação de uma tarefa de download"""
    # Mock para o método de download
    with patch("app.services.downloader.downloader.download_video"):
        response = client.post(
            "/api/v1/downloads",
            headers=auth_headers,
            json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "pending"


def test_get_download_status():
    """Testa a obtenção do status de uma tarefa de download"""
    # Cria uma tarefa de teste
    task_id = TaskManager.create_task("download")
    TaskManager.update_task(task_id, status="processing", progress=0.5)
    
    response = client.get(f"/api/v1/downloads/status/{task_id}", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == task_id
    assert data["status"] == "processing"
    assert data["progress"] == 0.5


def test_get_download_status_not_found():
    """Testa a obtenção do status de uma tarefa inexistente"""
    response = client.get("/api/v1/downloads/status/non-existent-task", headers=auth_headers)
    
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "task_not_found"


def test_create_transcription():
    """Testa a criação de uma tarefa de transcrição"""
    # Mock para o método de transcrição
    with patch("app.services.transcription.transcriber.transcribe_media"):
        response = client.post(
            "/api/v1/transcriptions",
            headers=auth_headers,
            json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "language": "pt"}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "pending"


def test_get_transcription_status():
    """Testa a obtenção do status de uma tarefa de transcrição"""
    # Cria uma tarefa de teste
    task_id = TaskManager.create_task("transcription")
    TaskManager.update_task(task_id, status="processing", progress=0.5)
    
    response = client.get(f"/api/v1/transcriptions/status/{task_id}", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == task_id
    assert data["status"] == "processing"
    assert data["progress"] == 0.5


def test_get_transcription_status_not_found():
    """Testa a obtenção do status de uma tarefa inexistente"""
    response = client.get("/api/v1/transcriptions/status/non-existent-task", headers=auth_headers)
    
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "task_not_found"