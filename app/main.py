from fastapi import FastAPI, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi

from app.api import routes_downloads, routes_transcriptions, routes_health
from app.core.config import settings
from app.core.security import api_key_auth
from app.core.logging import setup_logging, RequestLoggingMiddleware

# Setup logging
logger = setup_logging()

# Create FastAPI app
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    docs_url=None,  # Disable default docs
    redoc_url=None,  # Disable default redoc
    openapi_url=None if not settings.API_DEBUG else "/openapi.json",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Can be configured via env var
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Include routers
app.include_router(routes_health.router, tags=["health"])
app.include_router(
    routes_downloads.router,
    prefix="/downloads",
    tags=["downloads"],
    dependencies=[Depends(api_key_auth)],
)
app.include_router(
    routes_transcriptions.router,
    prefix="/transcriptions",
    tags=["transcriptions"],
    dependencies=[Depends(api_key_auth)],
)

# Custom OpenAPI and documentation routes
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{settings.API_TITLE} - Swagger UI",
    )

@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url="/openapi.json",
        title=f"{settings.API_TITLE} - ReDoc",
    )

@app.get("/openapi.json", include_in_schema=False)
async def get_open_api_endpoint():
    return get_openapi(
        title=settings.API_TITLE,
        version=settings.API_VERSION,
        routes=app.routes,
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)