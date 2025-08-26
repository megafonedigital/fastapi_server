import os
import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List, Union
from uuid import uuid4

import ffmpeg
from faster_whisper import WhisperModel

from app.core.config import settings
from app.core.storage import storage
from app.models.dto import TranscriptionResult, TranscriptionSegment
from app.models.types import TaskManager
from app.services.downloader import downloader

# Configure logger
logger = logging.getLogger("api")

class TranscriptionError(Exception):
    """Exception raised for errors during transcription"""
    pass

class AudioTranscriber:
    """
    Service for transcribing audio/video using faster-whisper
    """
    
    def __init__(self):
        """
        Initialize the transcriber with default settings
        """
        self.workdir = Path(settings.WORKDIR)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.model = None
        self.model_name = settings.WHISPER_MODEL
        self.compute_type = settings.WHISPER_COMPUTE_TYPE
    
    def _load_model(self, model_name: Optional[str] = None, compute_type: Optional[str] = None) -> None:
        """
        Load the Whisper model
        
        Args:
            model_name: Name of the model to load
            compute_type: Compute type for the model
        """
        # Use provided values or defaults from settings
        model_name = model_name or self.model_name
        compute_type = compute_type or self.compute_type
        
        # Check if model is already loaded with the same parameters
        if self.model is not None and self.model_name == model_name and self.compute_type == compute_type:
            return
        
        # Load model
        logger.info(f"Loading Whisper model: {model_name} with compute type: {compute_type}")
        self.model = WhisperModel(model_name, device="auto", compute_type=compute_type)
        self.model_name = model_name
        self.compute_type = compute_type
    
    def _extract_audio(self, media_file: Path, output_file: Optional[Path] = None) -> Path:
        """
        Extract audio from video file or convert audio to WAV format
        
        Args:
            media_file: Path to the media file
            output_file: Path to save the extracted audio
            
        Returns:
            Path: Path to the extracted audio file
            
        Raises:
            TranscriptionError: If audio extraction fails
        """
        try:
            # Generate output file path if not provided
            if output_file is None:
                output_file = media_file.with_suffix(".wav")
            
            # Extract audio using ffmpeg
            (ffmpeg
                .input(str(media_file))
                .output(str(output_file), acodec="pcm_s16le", ac=1, ar="16000")
                .overwrite_output()
                .run(quiet=True, capture_stdout=True, capture_stderr=True)
            )
            
            logger.info(f"Extracted audio from {media_file} to {output_file}")
            return output_file
        
        except ffmpeg.Error as e:
            error_message = e.stderr.decode() if hasattr(e, "stderr") else str(e)
            logger.error(f"Error extracting audio: {error_message}")
            raise TranscriptionError(f"Error extracting audio: {error_message}") from e
        
        except Exception as e:
            logger.exception(f"Unexpected error extracting audio: {str(e)}")
            raise TranscriptionError(f"Unexpected error extracting audio: {str(e)}") from e
    
    async def transcribe_media(
        self,
        media_file: Path,
        language: Optional[str] = None,
        model_name: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> TranscriptionResult:
        """
        Transcribe audio/video file
        
        Args:
            media_file: Path to the media file
            language: Language code (e.g., "pt", "en")
            model_name: Name of the Whisper model to use
            task_id: Task ID for tracking progress
            
        Returns:
            TranscriptionResult: Transcription result
            
        Raises:
            TranscriptionError: If transcription fails
        """
        try:
            # Update task status if task_id is provided
            if task_id:
                TaskManager.update_task(
                    task_id,
                    status="processing",
                    progress=0.1,
                )
            
            # Extract audio from media file
            audio_file = self._extract_audio(media_file)
            
            # Update task progress
            if task_id:
                TaskManager.update_task(
                    task_id,
                    progress=0.3,
                )
            
            # Load model
            self._load_model(model_name)
            
            # Update task progress
            if task_id:
                TaskManager.update_task(
                    task_id,
                    progress=0.4,
                )
            
            # Use default language from settings if not provided
            if language is None:
                language = settings.WHISPER_LANGUAGE
            
            # Transcribe audio
            logger.info(f"Transcribing audio: {audio_file} (language: {language})")
            segments, info = self.model.transcribe(
                str(audio_file),
                language=language,
                task="transcribe",
                beam_size=5,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500},
            )
            
            # Process segments
            transcription_segments = []
            full_text = ""
            
            for i, segment in enumerate(segments):
                # Update task progress
                if task_id:
                    progress = 0.4 + (0.5 * (i / (len(list(segments)) or 1)))
                    TaskManager.update_task(
                        task_id,
                        progress=min(0.9, progress),
                    )
                
                # Add segment to result
                transcription_segments.append(
                    TranscriptionSegment(
                        id=i,
                        start=segment.start,
                        end=segment.end,
                        text=segment.text.strip(),
                    )
                )
                
                # Add to full text
                full_text += segment.text + " "
            
            # Create transcription result
            result = TranscriptionResult(
                text=full_text.strip(),
                segments=transcription_segments,
                language=info.language,
            )
            
            logger.info(f"Transcription completed: {len(transcription_segments)} segments")
            return result
        
        except TranscriptionError as e:
            logger.error(f"Error transcribing media: {str(e)}")
            if task_id:
                TaskManager.update_task(
                    task_id,
                    status="failed",
                    error={
                        "code": "transcription_error",
                        "message": "Erro ao transcrever o áudio",
                        "details": str(e)
                    }
                )
            raise
        
        except Exception as e:
            logger.exception(f"Unexpected error transcribing media: {str(e)}")
            if task_id:
                TaskManager.update_task(
                    task_id,
                    status="failed",
                    error={
                        "code": "unexpected_error",
                        "message": "Erro inesperado ao transcrever o áudio",
                        "details": str(e)
                    }
                )
            raise TranscriptionError(f"Unexpected error transcribing media: {str(e)}") from e
    
    def _generate_srt(self, result: TranscriptionResult) -> str:
        """
        Generate SRT subtitle format from transcription result
        
        Args:
            result: Transcription result
            
        Returns:
            str: SRT subtitle content
        """
        srt_content = ""
        
        for segment in result.segments:
            # Format timestamps (HH:MM:SS,mmm)
            start_time = self._format_timestamp(segment.start)
            end_time = self._format_timestamp(segment.end)
            
            # Add segment to SRT
            srt_content += f"{segment.id + 1}\n"
            srt_content += f"{start_time} --> {end_time}\n"
            srt_content += f"{segment.text}\n\n"
        
        return srt_content
    
    def _generate_vtt(self, result: TranscriptionResult) -> str:
        """
        Generate WebVTT subtitle format from transcription result
        
        Args:
            result: Transcription result
            
        Returns:
            str: WebVTT subtitle content
        """
        vtt_content = "WEBVTT\n\n"
        
        for segment in result.segments:
            # Format timestamps (HH:MM:SS.mmm)
            start_time = self._format_timestamp(segment.start, vtt=True)
            end_time = self._format_timestamp(segment.end, vtt=True)
            
            # Add segment to VTT
            vtt_content += f"{start_time} --> {end_time}\n"
            vtt_content += f"{segment.text}\n\n"
        
        return vtt_content
    
    def _format_timestamp(self, seconds: float, vtt: bool = False) -> str:
        """
        Format timestamp for subtitles
        
        Args:
            seconds: Time in seconds
            vtt: Whether to format for VTT (True) or SRT (False)
            
        Returns:
            str: Formatted timestamp
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        
        if vtt:
            # VTT format: HH:MM:SS.mmm
            return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}".replace(".", ".")
        else:
            # SRT format: HH:MM:SS,mmm
            return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}".replace(".", ",")
    
    async def upload_transcription(
        self,
        transcription_id: str,
        result: TranscriptionResult,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upload transcription results to storage
        
        Args:
            transcription_id: Transcription ID
            result: Transcription result
            task_id: Task ID for tracking progress
            
        Returns:
            Dict[str, Any]: Upload results with object keys and URLs
            
        Raises:
            Exception: If upload fails
        """
        try:
            # Generate subtitle formats
            srt_content = self._generate_srt(result)
            vtt_content = self._generate_vtt(result)
            
            # Create result dictionary
            upload_result = {
                "transcription_id": transcription_id,
                "language": result.language,
                "files": {}
            }
            
            # Upload JSON result
            json_object_key = f"transcriptions/{transcription_id}/transcription.json"
            storage.upload_bytes(
                data=json.dumps(result.model_dump(), ensure_ascii=False).encode("utf-8"),
                object_name=json_object_key,
                content_type="application/json",
            )
            
            json_url = storage.get_presigned_url(json_object_key)
            upload_result["json_url"] = json_url
            upload_result["files"]["json"] = {
                "object_key": json_object_key,
                "presigned_url": json_url,
            }
            
            # Upload SRT subtitle
            srt_object_key = f"transcriptions/{transcription_id}/transcription.srt"
            storage.upload_bytes(
                data=srt_content.encode("utf-8"),
                object_name=srt_object_key,
                content_type="application/x-subrip",
            )
            
            srt_url = storage.get_presigned_url(srt_object_key)
            upload_result["srt_url"] = srt_url
            upload_result["files"]["srt"] = {
                "object_key": srt_object_key,
                "presigned_url": srt_url,
            }
            
            # Upload VTT subtitle
            vtt_object_key = f"transcriptions/{transcription_id}/transcription.vtt"
            storage.upload_bytes(
                data=vtt_content.encode("utf-8"),
                object_name=vtt_object_key,
                content_type="text/vtt",
            )
            
            vtt_url = storage.get_presigned_url(vtt_object_key)
            upload_result["vtt_url"] = vtt_url
            upload_result["files"]["vtt"] = {
                "object_key": vtt_object_key,
                "presigned_url": vtt_url,
            }
            
            logger.info(f"Uploaded transcription files for: {transcription_id}")
            return upload_result
        
        except Exception as e:
            logger.exception(f"Error uploading transcription: {str(e)}")
            if task_id:
                TaskManager.update_task(
                    task_id,
                    status="failed",
                    error={
                        "code": "storage_error",
                        "message": "Erro ao fazer upload da transcrição",
                        "details": str(e)
                    }
                )
            raise

# Create a singleton instance
transcriber = AudioTranscriber()