import os
import logging
import json
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List, Union
from uuid import uuid4

import yt_dlp
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings
from app.core.storage import storage
from app.models.dto import VideoMetadata
from app.models.types import TaskManager

# Configure logger
logger = logging.getLogger("api")

class DownloadError(Exception):
    """Exception raised for errors during video download"""
    pass

class VideoDownloader:
    """
    Service for downloading videos from various platforms using yt-dlp
    """
    
    def __init__(self):
        """
        Initialize the downloader with default settings
        """
        self.workdir = Path(settings.WORKDIR)
        self.workdir.mkdir(parents=True, exist_ok=True)
    
    def _get_ydl_opts(self, 
                     format_str: str = "mp4", 
                     quality: str = "best", 
                     audio_only: bool = False,
                     extract_audio: bool = False) -> Dict[str, Any]:
        """
        Get yt-dlp options based on parameters
        
        Args:
            format_str: Video format
            quality: Video quality
            audio_only: Whether to download audio only
            extract_audio: Whether to extract audio from video
            
        Returns:
            Dict[str, Any]: yt-dlp options
        """
        # Create temporary directory for downloads
        temp_dir = tempfile.mkdtemp(dir=self.workdir)
        
        # Base options
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "outtmpl": os.path.join(temp_dir, "%(title)s.%(ext)s"),
            "restrictfilenames": True,  # Avoid special characters in filenames
            "noplaylist": True,  # Download single video, not playlist
            "writeinfojson": True,  # Write video metadata to JSON file
            "progress_hooks": [self._progress_hook],
        }
        
        # Handle audio-only downloads
        if audio_only:
            ydl_opts.update({
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
            })
        # Handle video downloads with audio extraction
        elif extract_audio:
            ydl_opts.update({
                "format": f"best[ext={format_str}]/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
            })
        # Handle regular video downloads
        else:
            # Format selection based on quality
            if quality == "best":
                format_spec = f"best[ext={format_str}]/best"
            elif quality == "worst":
                format_spec = f"worst[ext={format_str}]/worst"
            else:
                # Handle specific quality like 720p
                format_spec = f"bestvideo[height<={quality.rstrip('p')}][ext={format_str}]+bestaudio/best[ext={format_str}]/best"
            
            ydl_opts.update({
                "format": format_spec,
            })
        
        return ydl_opts
    
    def _progress_hook(self, d: Dict[str, Any]) -> None:
        """
        Progress hook for yt-dlp
        
        Args:
            d: Progress information
        """
        if d["status"] == "downloading":
            if "_percent_str" in d and "_eta_str" in d:
                logger.info(f"Downloading: {d['_percent_str']} ETA: {d['_eta_str']}")
                
                # Update task progress if task_id is available
                if "task_id" in d:
                    try:
                        percent = float(d["_percent_str"].strip("%")) / 100
                        TaskManager.update_task(
                            d["task_id"],
                            progress=percent,
                            status="processing"
                        )
                    except (ValueError, KeyError):
                        pass
        
        elif d["status"] == "finished":
            logger.info(f"Download finished: {d['filename']}")
            
            # Update task status if task_id is available
            if "task_id" in d:
                TaskManager.update_task(
                    d["task_id"],
                    progress=1.0,
                    status="processing"  # Still processing (post-processing)
                )
    
    @retry(
        retry=retry_if_exception_type((yt_dlp.utils.DownloadError, yt_dlp.utils.ExtractorError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def download_video(
        self,
        url: str,
        format_str: str = "mp4",
        quality: str = "best",
        audio_only: bool = False,
        extract_audio: bool = False,
        task_id: Optional[str] = None,
    ) -> Tuple[VideoMetadata, Path, List[Path]]:
        """
        Download a video from a URL
        
        Args:
            url: Video URL
            format_str: Video format
            quality: Video quality
            audio_only: Whether to download audio only
            extract_audio: Whether to extract audio from video
            task_id: Task ID for tracking progress
            
        Returns:
            Tuple[VideoMetadata, Path, List[Path]]: Video metadata, video file path, and additional files
            
        Raises:
            DownloadError: If download fails
        """
        try:
            # Get yt-dlp options
            ydl_opts = self._get_ydl_opts(format_str, quality, audio_only, extract_audio)
            temp_dir = Path(ydl_opts["outtmpl"]).parent
            
            # Add task_id to progress hook context if available
            if task_id:
                ydl_opts["progress_hooks"] = [lambda d: self._progress_hook({**d, "task_id": task_id})]
            
            # Download video
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info(f"Downloading video from URL: {url}")
                info = ydl.extract_info(url, download=True)
                
                # Handle playlist case (should be disabled, but just in case)
                if "entries" in info:
                    info = info["entries"][0]
            
            # Find downloaded files
            downloaded_files = list(temp_dir.glob("*"))
            if not downloaded_files:
                raise DownloadError(f"No files downloaded from URL: {url}")
            
            # Find main media file and info JSON
            media_file = None
            info_file = None
            additional_files = []
            
            for file in downloaded_files:
                if file.suffix == ".json":
                    info_file = file
                elif file.suffix in [".mp4", ".webm", ".mkv", ".mp3", ".m4a", ".wav"]:
                    if not media_file or file.stat().st_mtime > media_file.stat().st_mtime:
                        if media_file:
                            additional_files.append(media_file)
                        media_file = file
                else:
                    additional_files.append(file)
            
            if not media_file:
                raise DownloadError(f"No media file found after download from URL: {url}")
            
            # Load info JSON if available
            if info_file:
                with open(info_file, "r", encoding="utf-8") as f:
                    info = json.load(f)
            
            # Generate video ID
            video_id = str(uuid4())
            
            # Create video metadata
            metadata = VideoMetadata(
                video_id=video_id,
                title=info.get("title", "Unknown"),
                duration=float(info.get("duration", 0)),
                format=media_file.suffix.lstrip("."),
                width=info.get("width"),
                height=info.get("height"),
                fps=info.get("fps"),
                audio_codec=info.get("acodec"),
                video_codec=info.get("vcodec"),
                file_size=media_file.stat().st_size,
                upload_date=info.get("upload_date"),
                extractor=info.get("extractor"),
                webpage_url=info.get("webpage_url"),
            )
            
            logger.info(f"Downloaded video: {metadata.title} ({metadata.video_id})")
            return metadata, media_file, additional_files
        
        except (yt_dlp.utils.DownloadError, yt_dlp.utils.ExtractorError) as e:
            logger.error(f"Error downloading video: {str(e)}")
            if task_id:
                TaskManager.update_task(
                    task_id,
                    status="failed",
                    error={
                        "code": "download_error",
                        "message": "Erro ao baixar o vídeo",
                        "details": str(e)
                    }
                )
            raise DownloadError(f"Error downloading video: {str(e)}") from e
        
        except Exception as e:
            logger.exception(f"Unexpected error downloading video: {str(e)}")
            if task_id:
                TaskManager.update_task(
                    task_id,
                    status="failed",
                    error={
                        "code": "unexpected_error",
                        "message": "Erro inesperado ao baixar o vídeo",
                        "details": str(e)
                    }
                )
            raise DownloadError(f"Unexpected error downloading video: {str(e)}") from e
        
        finally:
            # Cleanup will be handled by the caller
            pass
    
    async def upload_to_storage(
        self,
        metadata: VideoMetadata,
        media_file: Path,
        additional_files: List[Path],
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upload downloaded files to MinIO storage
        
        Args:
            metadata: Video metadata
            media_file: Path to the media file
            additional_files: List of additional files
            task_id: Task ID for tracking progress
            
        Returns:
            Dict[str, Any]: Upload results with object keys and URLs
            
        Raises:
            Exception: If upload fails
        """
        try:
            result = {
                "video_id": metadata.video_id,
                "title": metadata.title,
                "duration": metadata.duration,
                "bucket": settings.MINIO_BUCKET,
                "files": {}
            }
            
            # Upload main media file
            object_key = f"videos/{metadata.video_id}/{media_file.name}"
            storage.upload_file(
                file_path=media_file,
                object_name=object_key,
            )
            
            # Generate presigned URL
            presigned_url = storage.get_presigned_url(object_key)
            
            result["object_key"] = object_key
            result["presigned_url"] = presigned_url
            result["files"]["media"] = {
                "object_key": object_key,
                "presigned_url": presigned_url,
                "filename": media_file.name,
            }
            
            # Upload additional files
            for file in additional_files:
                if file.suffix == ".json":
                    # Upload metadata JSON
                    object_key = f"videos/{metadata.video_id}/metadata.json"
                    storage.upload_file(
                        file_path=file,
                        object_name=object_key,
                        content_type="application/json",
                    )
                    
                    result["files"]["metadata"] = {
                        "object_key": object_key,
                        "presigned_url": storage.get_presigned_url(object_key),
                        "filename": file.name,
                    }
                else:
                    # Upload other files
                    object_key = f"videos/{metadata.video_id}/{file.name}"
                    storage.upload_file(
                        file_path=file,
                        object_name=object_key,
                    )
                    
                    file_type = "audio" if file.suffix in [".mp3", ".m4a", ".wav"] else "other"
                    result["files"][file_type] = {
                        "object_key": object_key,
                        "presigned_url": storage.get_presigned_url(object_key),
                        "filename": file.name,
                    }
            
            logger.info(f"Uploaded video files to storage: {metadata.video_id}")
            return result
        
        except Exception as e:
            logger.exception(f"Error uploading files to storage: {str(e)}")
            if task_id:
                TaskManager.update_task(
                    task_id,
                    status="failed",
                    error={
                        "code": "storage_error",
                        "message": "Erro ao fazer upload dos arquivos",
                        "details": str(e)
                    }
                )
            raise
    
    def cleanup(self, temp_dir: Union[str, Path]) -> None:
        """
        Clean up temporary files
        
        Args:
            temp_dir: Temporary directory to clean up
        """
        try:
            if isinstance(temp_dir, str):
                temp_dir = Path(temp_dir)
            
            if temp_dir.exists() and temp_dir.is_dir():
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temporary directory: {temp_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up temporary directory: {str(e)}")

# Create a singleton instance
downloader = VideoDownloader()