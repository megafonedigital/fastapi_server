from fastapi import APIRouter, Depends, HTTPException, status
from app.core.config import settings
from app.core.storage import storage
from app.models.dto import HealthResponse

# Create router
router = APIRouter()

@router.get("/health", response_model=HealthResponse, summary="Verificar status da API")
async def health_check():
    """
    Verifica o status da API e suas dependências.
    
    Returns:
        HealthResponse: Status da API e suas dependências
    """
    # Check MinIO connection
    minio_status = "ok"
    try:
        # Check if bucket exists
        storage.client.bucket_exists(storage.bucket)
    except Exception as e:
        minio_status = f"error: {str(e)}"
    
    return HealthResponse(
        status="ok",
        version=settings.API_VERSION,
        minio_status=minio_status,
    )