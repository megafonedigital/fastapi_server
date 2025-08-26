from typing import Optional, List, Dict, Any, Union
from enum import Enum
from pydantic import BaseModel, Field, HttpUrl
from uuid import UUID

# Enums
class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class WhisperModel(str, Enum):
    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"

class ComputeType(str, Enum):
    AUTO = "auto"
    FLOAT16 = "float16"
    INT8 = "int8"

# Request models
class DownloadRequest(BaseModel):
    url: HttpUrl = Field(..., description="URL do vídeo a ser baixado")
    format: Optional[str] = Field("mp4", description="Formato do vídeo (ex: mp4, webm)")
    quality: Optional[str] = Field("best", description="Qualidade do vídeo (ex: best, worst, 720p)")
    audio_only: Optional[bool] = Field(False, description="Baixar apenas o áudio")
    extract_audio: Optional[bool] = Field(False, description="Extrair áudio do vídeo")
    
    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "format": "mp4",
                "quality": "best",
                "audio_only": False,
                "extract_audio": False
            }
        }

class TranscriptionRequest(BaseModel):
    video_id: Optional[str] = Field(None, description="ID do vídeo já baixado")
    url: Optional[HttpUrl] = Field(None, description="URL do vídeo a ser transcrito (se não estiver baixado)")
    language: Optional[str] = Field(None, description="Idioma do áudio (ex: pt, en, es)")
    model: Optional[WhisperModel] = Field(None, description="Modelo Whisper a ser utilizado")
    persist_media: Optional[bool] = Field(True, description="Persistir o vídeo/áudio após a transcrição")
    
    class Config:
        json_schema_extra = {
            "example": {
                "video_id": "abc123",
                "language": "pt",
                "model": "medium"
            }
        }

# Response models
class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Optional[str] = None

class DownloadResponse(BaseModel):
    video_id: str
    title: str
    duration: float
    bucket: str
    object_key: str
    presigned_url: str
    task_id: Optional[str] = None
    status: TaskStatus = TaskStatus.COMPLETED

class TranscriptionResponse(BaseModel):
    transcription_id: str
    json_url: str
    srt_url: str
    vtt_url: str
    language: str
    task_id: Optional[str] = None
    status: TaskStatus = TaskStatus.COMPLETED

class TaskStatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    progress: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[ErrorResponse] = None

class HealthResponse(BaseModel):
    status: str
    version: str
    minio_status: str

# Internal models
class VideoMetadata(BaseModel):
    video_id: str
    title: str
    duration: float
    format: str
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    audio_codec: Optional[str] = None
    video_codec: Optional[str] = None
    file_size: Optional[int] = None
    upload_date: Optional[str] = None
    extractor: Optional[str] = None
    webpage_url: Optional[str] = None

class TranscriptionSegment(BaseModel):
    id: int
    start: float
    end: float
    text: str

class TranscriptionResult(BaseModel):
    text: str
    segments: List[TranscriptionSegment]
    language: str