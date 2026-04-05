"""FastAPI application entry point."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1 import api_router
from .core.config import settings
from .services.ocr_service import PaddleOCRService


app = FastAPI(
    title="RentWise API",
    description="API for RentWise - Hong Kong Rental Research Agent",
    version="1.0.0",
)

logger = logging.getLogger(__name__)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api/v1")


@app.on_event("startup")
async def warmup_services() -> None:
    """Warm expensive services during startup so the first user request is faster."""
    if settings.OCR_PROVIDER == "paddleocr" and settings.OCR_PREWARM_ON_STARTUP:
        try:
            await PaddleOCRService().warmup()
            logger.info("PaddleOCR engine warmed up during startup")
        except Exception as exc:  # pragma: no cover - environment dependent
            logger.warning("PaddleOCR warmup skipped: %s", exc)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "environment": settings.APP_ENV}
