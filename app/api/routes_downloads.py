from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Path, Query
from typing import Dict, Any, Optional
import logging

from app.core.config import settings
from app.core.storage import storage
from app.models.dto import DownloadRequest, DownloadResponse, TaskStatusResponse, ErrorResponse
from app.models.types import TaskManager
from app.services.downloader import downloader
from app.services.utils import cleanup_temp_dir, format_error_response

# Configure logger
logger = logging.getLogger("api")

# Create router
router = APIRouter()

async def _process_download(task_id: str, request: DownloadRequest) -> None:
    """
    Background task for processing video download
    
    Args:
        task_id: Task ID
        request: Download request
    """
    try:
        # Update task status
        TaskManager.update_task(task_id, status="processing", progress=0.1)
        
        # Download video
        metadata, media_file, additional_files = await downloader.download_video(
            url=str(request.url),
            format_str=request.format,
            quality=request.quality,
            audio_only=request.audio_only,
            extract_audio=request.extract_audio,
            task_id=task_id,
        )
        
        # Update task progress
        TaskManager.update_task(task_id, progress=0.7)
        
        # Upload to storage
        result = await downloader.upload_to_storage(
            metadata=metadata,
            media_file=media_file,
            additional_files=additional_files,
            task_id=task_id,
        )
        
        # Update task status
        TaskManager.update_task(
            task_id,
            status="completed",
            progress=1.0,
            result=result,
        )
        
        # Clean up temporary files
        if media_file:
            cleanup_temp_dir(media_file.parent)
    
    except Exception as e:
        logger.exception(f"Error processing download task: {str(e)}")
        
        # Update task status
        TaskManager.update_task(
            task_id,
            status="failed",
            error=format_error_response(
                code="download_error",
                message="Erro ao processar o download",
                details=str(e),
            ),
        )
        
        # Clean up temporary files
        if 'media_file' in locals() and media_file:
            cleanup_temp_dir(media_file.parent)

@router.post(
    "",
    response_model=DownloadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Iniciar download de vídeo",
    responses={
        201: {"description": "Download iniciado com sucesso"},
        400: {"model": ErrorResponse, "description": "Requisição inválida"},
        401: {"model": ErrorResponse, "description": "Não autorizado"},
        500: {"model": ErrorResponse, "description": "Erro interno do servidor"},
    },
)
async def create_download(request: DownloadRequest, background_tasks: BackgroundTasks):
    """
    Inicia o download de um vídeo a partir de uma URL.
    
    Args:
        request: Parâmetros do download
        background_tasks: Tarefas em segundo plano
        
    Returns:
        DownloadResponse: Informações do download
    """
    try:
        # Create task ID for tracking
        task_id = TaskManager.create_task("download")
        
        # Add download task to background tasks
        background_tasks.add_task(_process_download, task_id, request)
        
        return DownloadResponse(
            video_id="pending",  # Will be updated when download completes
            title="Downloading...",
            duration=0.0,
            bucket=settings.MINIO_BUCKET,
            object_key="",
            presigned_url="",
            task_id=task_id,
            status="pending",
        )
    
    except Exception as e:
        logger.exception(f"Error creating download: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response(
                code="server_error",
                message="Erro ao iniciar o download",
                details=str(e),
            ),
        )

@router.get(
    "/{video_id}",
    response_model=DownloadResponse,
    summary="Obter informações do vídeo",
    responses={
        200: {"description": "Informações do vídeo obtidas com sucesso"},
        401: {"model": ErrorResponse, "description": "Não autorizado"},
        404: {"model": ErrorResponse, "description": "Vídeo não encontrado"},
        500: {"model": ErrorResponse, "description": "Erro interno do servidor"},
    },
)
async def get_download(video_id: str = Path(..., description="ID do vídeo")):
    """
    Obtém informações de um vídeo baixado.
    
    Args:
        video_id: ID do vídeo
        
    Returns:
        DownloadResponse: Informações do vídeo
    """
    try:
        # Check if video exists in storage
        object_key = f"videos/{video_id}/metadata.json"
        
        try:
            # Try to get metadata from storage
            metadata_url = storage.get_presigned_url(object_key)
        except Exception as e:
            logger.error(f"Error getting video metadata: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response(
                    code="video_not_found",
                    message="Vídeo não encontrado",
                    details=f"Não foi possível encontrar o vídeo com ID: {video_id}",
                ),
            )
        
        # Find media file
        media_files = []
        try:
            # List objects in video directory
            objects = storage.client.list_objects(storage.bucket, prefix=f"videos/{video_id}/", recursive=True)
            for obj in objects:
                if obj.object_name.endswith((".mp4", ".webm", ".mkv", ".mp3", ".m4a", ".wav")):
                    media_files.append(obj.object_name)
        except Exception as e:
            logger.error(f"Error listing video files: {str(e)}")
        
        if not media_files:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response(
                    code="media_not_found",
                    message="Arquivo de mídia não encontrado",
                    details=f"Não foi possível encontrar o arquivo de mídia para o vídeo com ID: {video_id}",
                ),
            )
        
        # Get media file URL
        media_object_key = media_files[0]
        media_url = storage.get_presigned_url(media_object_key)
        
        # Get video metadata (simplified for now)
        title = media_object_key.split("/")[-1]
        
        return DownloadResponse(
            video_id=video_id,
            title=title,
            duration=0.0,  # Would need to parse metadata.json for accurate duration
            bucket=settings.MINIO_BUCKET,
            object_key=media_object_key,
            presigned_url=media_url,
            status="completed",
        )
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.exception(f"Error getting download: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response(
                code="server_error",
                message="Erro ao obter informações do vídeo",
                details=str(e),
            ),
        )

@router.get(
    "/status/{task_id}",
    response_model=TaskStatusResponse,
    summary="Verificar status do download",
    responses={
        200: {"description": "Status do download obtido com sucesso"},
        401: {"model": ErrorResponse, "description": "Não autorizado"},
        404: {"model": ErrorResponse, "description": "Tarefa não encontrada"},
        500: {"model": ErrorResponse, "description": "Erro interno do servidor"},
    },
)
async def get_download_status(task_id: str = Path(..., description="ID da tarefa de download")):
    """
    Verifica o status de uma tarefa de download.
    
    Args:
        task_id: ID da tarefa
        
    Returns:
        TaskStatusResponse: Status da tarefa
    """
    try:
        # Get task status
        task = TaskManager.get_task(task_id)
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response(
                    code="task_not_found",
                    message="Tarefa não encontrada",
                    details=f"Não foi possível encontrar a tarefa com ID: {task_id}",
                ),
            )
        
        return TaskStatusResponse(
            task_id=task_id,
            status=task["status"],
            progress=task.get("progress"),
            result=task.get("result"),
            error=task.get("error"),
        )
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.exception(f"Error getting task status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response(
                code="server_error",
                message="Erro ao obter status da tarefa",
                details=str(e),
            ),
        )