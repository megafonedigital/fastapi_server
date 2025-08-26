import json
import logging
import sys
import time
import uuid
from typing import Callable, Dict, Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# Configure logger
def setup_logging() -> logging.Logger:
    """
    Configure structured JSON logging
    
    Returns:
        Logger: Configured logger instance
    """
    logger = logging.getLogger("api")
    logger.setLevel(logging.INFO)
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    
    # Create formatter
    class JsonFormatter(logging.Formatter):
        def format(self, record):
            log_record = {
                "timestamp": self.formatTime(record, self.datefmt),
                "level": record.levelname,
                "message": record.getMessage(),
                "module": record.module,
            }
            
            # Add extra attributes if available
            if hasattr(record, "request_id"):
                log_record["request_id"] = record.request_id
            if hasattr(record, "path"):
                log_record["path"] = record.path
            if hasattr(record, "method"):
                log_record["method"] = record.method
            if hasattr(record, "elapsed_ms"):
                log_record["elapsed_ms"] = record.elapsed_ms
            if hasattr(record, "status_code"):
                log_record["status_code"] = record.status_code
                
            # Add exception info if available
            if record.exc_info:
                log_record["exception"] = self.formatException(record.exc_info)
                
            return json.dumps(log_record)
    
    formatter = JsonFormatter()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger

# Request logging middleware
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for request logging and correlation ID tracking
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.logger = logging.getLogger("api")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate or get request ID
        request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
        
        # Add request ID to request state
        request.state.request_id = request_id
        
        # Start timer
        start_time = time.time()
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate elapsed time
            elapsed_ms = round((time.time() - start_time) * 1000)
            
            # Add request ID to response headers
            response.headers["X-Request-Id"] = request_id
            
            # Log request details
            extra = {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "elapsed_ms": elapsed_ms
            }
            
            # Create log record with extra attributes
            self.logger.info(
                f"{request.method} {request.url.path} {response.status_code} {elapsed_ms}ms",
                extra=extra
            )
            
            return response
        except Exception as e:
            # Calculate elapsed time
            elapsed_ms = round((time.time() - start_time) * 1000)
            
            # Log exception
            extra = {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "elapsed_ms": elapsed_ms
            }
            
            self.logger.exception(f"Error processing request: {str(e)}", extra=extra)
            raise