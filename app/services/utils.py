import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
import logging

# Configure logger
logger = logging.getLogger("api")

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to avoid special characters
    
    Args:
        filename: Original filename
        
    Returns:
        str: Sanitized filename
    """
    # Replace special characters with underscore
    sanitized = re.sub(r'[^\w\-\.]', '_', filename)
    
    # Remove multiple underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')
    
    # Ensure filename is not empty
    if not sanitized:
        sanitized = "file"
    
    return sanitized

def create_temp_dir(base_dir: Optional[Union[str, Path]] = None) -> Path:
    """
    Create a temporary directory
    
    Args:
        base_dir: Base directory for temporary directory
        
    Returns:
        Path: Path to the temporary directory
    """
    if base_dir is None:
        from app.core.config import settings
        base_dir = settings.WORKDIR
    
    # Create base directory if it doesn't exist
    if isinstance(base_dir, str):
        base_dir = Path(base_dir)
    
    base_dir.mkdir(parents=True, exist_ok=True)
    
    # Create temporary directory
    temp_dir = Path(tempfile.mkdtemp(dir=base_dir))
    logger.info(f"Created temporary directory: {temp_dir}")
    
    return temp_dir

def cleanup_temp_dir(temp_dir: Union[str, Path]) -> None:
    """
    Clean up temporary directory
    
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

def format_error_response(code: str, message: str, details: Optional[str] = None) -> Dict[str, Any]:
    """
    Format error response
    
    Args:
        code: Error code
        message: Error message
        details: Error details
        
    Returns:
        Dict[str, Any]: Formatted error response
    """
    response = {
        "code": code,
        "message": message,
    }
    
    if details:
        response["details"] = details
    
    return response