"""FastAPI application entry point."""

import asyncio
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .core.request_limits import RequestBodyLimitMiddleware
from fastapi.middleware.cors import CORSMiddleware

from .api.v1 import api_router
from .core.config import settings
from .services.ocr_service import OCRService
from .services.file_cleanup_service import cleanup_forever


@asynccontextmanager
async def lifespan(app: FastAPI):
    await warmup_services()
    cleanup_task = asyncio.create_task(cleanup_forever()) if settings.APP_ENV != "test" else None
    try:
        yield
    finally:
        if cleanup_task is not None:
            cleanup_task.cancel()
            await asyncio.gather(cleanup_task, return_exceptions=True)


app = FastAPI(
    lifespan=lifespan,
    title="RentWise API",
    description="API for RentWise - Hong Kong Rental Research Agent",
    version="1.0.0",
)

logger = logging.getLogger(__name__)

# Body bounds run before multipart/JSON parsing, inside the CORS wrapper.
app.add_middleware(RequestBodyLimitMiddleware)


@app.exception_handler(RequestValidationError)
async def safe_validation_error(request: Request, exc: RequestValidationError):
    # Do not echo passwords, source text, or unserializable validator contexts.
    errors = [{key: error[key] for key in ("loc", "msg", "type") if key in error} for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.middleware("http")
async def private_response_cache_policy(request: Request, call_next):
    response = await call_next(request)
    if request.headers.get("authorization") or request.url.path.startswith("/api/v1/auth/"):
        response.headers["Cache-Control"] = "no-store"
    return response


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api/v1")


async def warmup_services() -> None:
    """Warm expensive services during startup so the first user request is faster."""
    if settings.effective_ocr_prewarm_on_startup:
        try:
            await OCRService().warmup()
            logger.info("%s engine warmed up during startup", settings.OCR_PROVIDER)
        except Exception as exc:  # pragma: no cover - environment dependent
            logger.warning("%s warmup skipped: %s", settings.OCR_PROVIDER, exc)


@app.get("/")
async def root():
    """Root endpoint for Render default health check."""
    return {"status": "healthy"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "environment": settings.APP_ENV}
