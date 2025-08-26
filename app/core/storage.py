from typing import Optional, BinaryIO, Union, Dict, Any
from pathlib import Path
import logging
from io import BytesIO

from minio import Minio
from minio.error import S3Error
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings

# Configure logger
logger = logging.getLogger("api")

class MinioStorage:
    """
    MinIO storage client for handling object storage operations
    """
    
    def __init__(self):
        """
        Initialize MinIO client with settings from environment variables
        """
        self.client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        self.bucket = settings.MINIO_BUCKET
        
        # Ensure bucket exists
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self) -> None:
        """
        Create bucket if it doesn't exist
        """
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info(f"Created bucket: {self.bucket}")
            else:
                logger.info(f"Bucket already exists: {self.bucket}")
        except S3Error as e:
            logger.error(f"Error ensuring bucket exists: {str(e)}")
            raise
    
    @retry(
        retry=retry_if_exception_type(S3Error),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    def upload_file(
        self, 
        file_path: Union[str, Path], 
        object_name: str, 
        content_type: Optional[str] = None
    ) -> str:
        """
        Upload a file to MinIO
        
        Args:
            file_path: Path to the file to upload
            object_name: Name of the object in MinIO
            content_type: Content type of the file
            
        Returns:
            str: Object name in MinIO
            
        Raises:
            S3Error: If upload fails
        """
        try:
            file_path = Path(file_path) if isinstance(file_path, str) else file_path
            
            # Determine content type if not provided
            if not content_type:
                content_type = self._get_content_type(file_path.name)
            
            # Upload file
            self.client.fput_object(
                bucket_name=self.bucket,
                object_name=object_name,
                file_path=str(file_path),
                content_type=content_type,
            )
            
            logger.info(f"Uploaded file to MinIO: {object_name}")
            return object_name
        except S3Error as e:
            logger.error(f"Error uploading file to MinIO: {str(e)}")
            raise
    
    @retry(
        retry=retry_if_exception_type(S3Error),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    def upload_bytes(
        self, 
        data: Union[bytes, BinaryIO, BytesIO], 
        object_name: str, 
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Upload bytes data to MinIO
        
        Args:
            data: Bytes data to upload
            object_name: Name of the object in MinIO
            content_type: Content type of the data
            metadata: Optional metadata to store with the object
            
        Returns:
            str: Object name in MinIO
            
        Raises:
            S3Error: If upload fails
        """
        try:
            # Determine content type if not provided
            if not content_type:
                content_type = self._get_content_type(object_name)
            
            # Convert to BytesIO if bytes
            if isinstance(data, bytes):
                data = BytesIO(data)
            
            # Get data length
            data.seek(0, 2)  # Seek to end
            length = data.tell()
            data.seek(0)  # Reset to beginning
            
            # Upload data
            self.client.put_object(
                bucket_name=self.bucket,
                object_name=object_name,
                data=data,
                length=length,
                content_type=content_type,
                metadata=metadata,
            )
            
            logger.info(f"Uploaded bytes to MinIO: {object_name}")
            return object_name
        except S3Error as e:
            logger.error(f"Error uploading bytes to MinIO: {str(e)}")
            raise
    
    @retry(
        retry=retry_if_exception_type(S3Error),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    def download_file(self, object_name: str, file_path: Union[str, Path]) -> None:
        """
        Download a file from MinIO
        
        Args:
            object_name: Name of the object in MinIO
            file_path: Path to save the file
            
        Raises:
            S3Error: If download fails
        """
        try:
            file_path = Path(file_path) if isinstance(file_path, str) else file_path
            
            # Create parent directory if it doesn't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Download file
            self.client.fget_object(
                bucket_name=self.bucket,
                object_name=object_name,
                file_path=str(file_path),
            )
            
            logger.info(f"Downloaded file from MinIO: {object_name}")
        except S3Error as e:
            logger.error(f"Error downloading file from MinIO: {str(e)}")
            raise
    
    @retry(
        retry=retry_if_exception_type(S3Error),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    def get_presigned_url(self, object_name: str, expires: int = None) -> str:
        """
        Generate a presigned URL for an object
        
        Args:
            object_name: Name of the object in MinIO
            expires: Expiration time in seconds (default: 24 hours)
            
        Returns:
            str: Presigned URL
            
        Raises:
            S3Error: If URL generation fails
        """
        try:
            # Use default expiration if not provided
            if expires is None:
                expires = settings.URL_EXPIRATION
            
            # Generate presigned URL
            url = self.client.presigned_get_object(
                bucket_name=self.bucket,
                object_name=object_name,
                expires=expires,
            )
            
            logger.info(f"Generated presigned URL for: {object_name}")
            return url
        except S3Error as e:
            logger.error(f"Error generating presigned URL: {str(e)}")
            raise
    
    @retry(
        retry=retry_if_exception_type(S3Error),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    def delete_object(self, object_name: str) -> None:
        """
        Delete an object from MinIO
        
        Args:
            object_name: Name of the object in MinIO
            
        Raises:
            S3Error: If deletion fails
        """
        try:
            self.client.remove_object(
                bucket_name=self.bucket,
                object_name=object_name,
            )
            
            logger.info(f"Deleted object from MinIO: {object_name}")
        except S3Error as e:
            logger.error(f"Error deleting object from MinIO: {str(e)}")
            raise
    
    def _get_content_type(self, filename: str) -> str:
        """
        Determine content type based on file extension
        
        Args:
            filename: Name of the file
            
        Returns:
            str: Content type
        """
        extension = Path(filename).suffix.lower()
        
        # Map extensions to content types
        content_types = {
            ".mp4": "video/mp4",
            ".mp3": "audio/mpeg",
            ".m4a": "audio/mp4",
            ".wav": "audio/wav",
            ".json": "application/json",
            ".srt": "application/x-subrip",
            ".vtt": "text/vtt",
            ".txt": "text/plain",
            ".webm": "video/webm",
            ".mkv": "video/x-matroska",
            ".avi": "video/x-msvideo",
            ".mov": "video/quicktime",
            ".flv": "video/x-flv",
            ".ogg": "audio/ogg",
            ".opus": "audio/opus",
        }
        
        return content_types.get(extension, "application/octet-stream")

# Create a singleton instance
storage = MinioStorage()