from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Path, Query
from typing import Dict, Any, Optional
import logging
import tempfile
from pathlib import Path as PathLib

from app.core.config import settings
from app.core.storage import storage
from app.models.dto import TranscriptionRequest, TranscriptionResponse, TaskStatusResponse, ErrorResponse
from app.models.types import TaskManager
from app.services.downloader import downloader
from app.services.transcription import transcriber
from app.services.utils import cleanup_temp_dir, format_error_response

# Configure logger
logger = logging.getLogger("api")

# Create router
router = APIRouter()

async def _process_transcription(task_id: str, request: TranscriptionRequest) -> None:
    """
    Background task for processing transcription
    
    Args:
        task_id: Task ID
        request: Transcription request
    """
    temp_dir = None
    try:
        # Update task status
        TaskManager.update_task(task_id, status="processing", progress=0.1)
        
        # Create temporary directory
        temp_dir = PathLib(tempfile.mkdtemp(dir=settings.WORKDIR))
        
        # Get media file
        media_file = None
        transcription_id = None
        
        if request.video_id:
            # Use existing video
            transcription_id = request.video_id
            
            # Find media file in storage
            try:
                # List objects in video directory
                objects = storage.client.list_objects(
                    storage.bucket, 
                    prefix=f"videos/{request.video_id}/", 
                    recursive=True
                )
                
                media_object_key = None
                for obj in objects:
                    if obj.object_name.endswith((".mp4", ".webm", ".mkv", ".mp3", ".m4a", ".wav")):
                        media_object_key = obj.object_name
                        break
                
                if not media_object_key:
                    raise Exception(f"No media file found for video ID: {request.video_id}")
                
                # Download media file
                media_file = temp_dir / media_object_key.split("/")[-1]
                storage.download_file(media_object_key, media_file)
                
                # Update task progress
                TaskManager.update_task(task_id, progress=0.3)
                
            except Exception as e:
                logger.error(f"Error getting media file from storage: {str(e)}")
                raise Exception(f"Error getting media file: {str(e)}")
        
        elif request.url:
            # Download video from URL
            TaskManager.update_task(task_id, progress=0.1, status="processing")
            
            # Download video
            metadata, downloaded_file, additional_files = await downloader.download_video(
                url=str(request.url),
                format_str="mp4",  # Default format
                audio_only=True,  # Audio is sufficient for transcription
                task_id=task_id,
            )
            
            # Set media file and transcription ID
            media_file = downloaded_file
            transcription_id = metadata.video_id
            
            # Update task progress
            TaskManager.update_task(task_id, progress=0.3)
            
            # Upload to storage if requested
            if request.persist_media:
                await downloader.upload_to_storage(
                    metadata=metadata,
                    media_file=media_file,
                    additional_files=additional_files,
                    task_id=task_id,
                )
        
        else:
            # Neither video_id nor URL provided
            raise Exception("Either video_id or url must be provided")
        
        # Transcribe media
        transcription_result = await transcriber.transcribe_media(
            media_file=media_file,
            language=request.language or settings.WHISPER_LANGUAGE,
            model_name=request.model or settings.WHISPER_MODEL,
            task_id=task_id,
        )
        
        # Update task progress
        TaskManager.update_task(task_id, progress=0.9)
        
        # Upload transcription to storage
        result = await transcriber.upload_transcription(
            transcription_id=transcription_id,
            result=transcription_result,
            task_id=task_id,
        )
        
        # Update task status
        TaskManager.update_task(
            task_id,
            status="completed",
            progress=1.0,
            result=result,
        )
    
    except Exception as e:
        logger.exception(f"Error processing transcription task: {str(e)}")
        
        # Update task status
        TaskManager.update_task(
            task_id,
            status="failed",
            error=format_error_response(
                code="transcription_error",
                message="Erro ao processar a transcrição",
                details=str(e),
            ),
        )
    
    finally:
        # Clean up temporary files
        if temp_dir:
            cleanup_temp_dir(temp_dir)

@router.post(
    "",
    response_model=TranscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Iniciar transcrição de áudio/vídeo",
    responses={
        201: {"description": "Transcrição iniciada com sucesso"},
        400: {"model": ErrorResponse, "description": "Requisição inválida"},
        401: {"model": ErrorResponse, "description": "Não autorizado"},
        404: {"model": ErrorResponse, "description": "Vídeo não encontrado"},
        500: {"model": ErrorResponse, "description": "Erro interno do servidor"},
    },
)
async def create_transcription(request: TranscriptionRequest, background_tasks: BackgroundTasks):
    """
    Inicia a transcrição de um áudio/vídeo.
    
    Args:
        request: Parâmetros da transcrição
        background_tasks: Tarefas em segundo plano
        
    Returns:
        TranscriptionResponse: Informações da transcrição
    """
    try:
        # Validate request
        if not request.video_id and not request.url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=format_error_response(
                    code="invalid_request",
                    message="Parâmetros inválidos",
                    details="É necessário fornecer video_id ou url",
                ),
            )
        
        # Create task ID for tracking
        task_id = TaskManager.create_task("transcription")
        
        # Add transcription task to background tasks
        background_tasks.add_task(_process_transcription, task_id, request)
        
        return TranscriptionResponse(
            transcription_id="pending",  # Will be updated when transcription completes
            json_url="",
            srt_url="",
            vtt_url="",
            language=request.language or settings.WHISPER_LANGUAGE,
            task_id=task_id,
            status="pending",
        )
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.exception(f"Error creating transcription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response(
                code="server_error",
                message="Erro ao iniciar a transcrição",
                details=str(e),
            ),
        )

@router.get(
    "/{transcription_id}",
    response_model=TranscriptionResponse,
    summary="Obter informações da transcrição",
    responses={
        200: {"description": "Informações da transcrição obtidas com sucesso"},
        401: {"model": ErrorResponse, "description": "Não autorizado"},
        404: {"model": ErrorResponse, "description": "Transcrição não encontrada"},
        500: {"model": ErrorResponse, "description": "Erro interno do servidor"},
    },
)
async def get_transcription(transcription_id: str = Path(..., description="ID da transcrição")):
    """
    Obtém informações de uma transcrição.
    
    Args:
        transcription_id: ID da transcrição
        
    Returns:
        TranscriptionResponse: Informações da transcrição
    """
    try:
        # Check if transcription exists in storage
        json_object_key = f"transcriptions/{transcription_id}/transcription.json"
        srt_object_key = f"transcriptions/{transcription_id}/transcription.srt"
        vtt_object_key = f"transcriptions/{transcription_id}/transcription.vtt"
        
        try:
            # Try to get transcription files from storage
            json_url = storage.get_presigned_url(json_object_key)
            srt_url = storage.get_presigned_url(srt_object_key)
            vtt_url = storage.get_presigned_url(vtt_object_key)
        except Exception as e:
            logger.error(f"Error getting transcription files: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response(
                    code="transcription_not_found",
                    message="Transcrição não encontrada",
                    details=f"Não foi possível encontrar a transcrição com ID: {transcription_id}",
                ),
            )
        
        # Determine language (simplified for now)
        language = settings.WHISPER_LANGUAGE
        
        return TranscriptionResponse(
            transcription_id=transcription_id,
            json_url=json_url,
            srt_url=srt_url,
            vtt_url=vtt_url,
            language=language,
            status="completed",
        )
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.exception(f"Error getting transcription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response(
                code="server_error",
                message="Erro ao obter informações da transcrição",
                details=str(e),
            ),
        )

@router.get(
    "/status/{task_id}",
    response_model=TaskStatusResponse,
    summary="Verificar status da transcrição",
    responses={
        200: {"description": "Status da transcrição obtido com sucesso"},
        401: {"model": ErrorResponse, "description": "Não autorizado"},
        404: {"model": ErrorResponse, "description": "Tarefa não encontrada"},
        500: {"model": ErrorResponse, "description": "Erro interno do servidor"},
    },
)
async def get_transcription_status(task_id: str = Path(..., description="ID da tarefa de transcrição")):
    """
    Verifica o status de uma tarefa de transcrição.
    
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