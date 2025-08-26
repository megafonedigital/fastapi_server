from fastapi import Security, HTTPException, status, Depends
from fastapi.security.api_key import APIKeyHeader
from app.core.config import settings

# API Key header
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

async def api_key_auth(api_key: str = Security(API_KEY_HEADER)):
    """
    Dependency for API Key authentication.
    
    Args:
        api_key: The API key from the X-API-Key header
        
    Returns:
        The API key if valid
        
    Raises:
        HTTPException: If the API key is invalid or missing
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "unauthorized",
                "message": "API Key não fornecida",
                "details": "Forneça uma API Key válida no header X-API-Key"
            }
        )
    
    if api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "invalid_api_key",
                "message": "API Key inválida",
                "details": "A API Key fornecida não é válida"
            }
        )
    
    return api_key