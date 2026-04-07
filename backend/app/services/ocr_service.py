"""OCR service abstraction with switchable OCR providers."""

from __future__ import annotations

import asyncio
import base64
import importlib
import mimetypes
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from ..core.config import settings


_CLOUD_PROVIDERS = {"mistral", "ocr_space"}


@dataclass
class OCRResult:
    """OCR output for one uploaded file."""

    status: str
    text: str | None
    error: str | None = None


class OCRService:
    """Run OCR over uploaded images using the configured backend."""

    _shared_engines: dict[str, Any] = {}
    _engine_lock = threading.Lock()

    def _get_engine(self):
        provider = settings.OCR_PROVIDER.lower().strip()
        if provider in type(self)._shared_engines:
            return type(self)._shared_engines[provider]

        with type(self)._engine_lock:
            if provider in type(self)._shared_engines:
                return type(self)._shared_engines[provider]

            if provider == "rapidocr":
                engine = self._build_rapidocr_engine()
            elif provider == "paddleocr":
                engine = self._build_paddleocr_engine()
            elif provider in _CLOUD_PROVIDERS:
                # Cloud providers are stateless HTTP clients; sentinel marks "ready".
                engine = "cloud"
            else:
                raise RuntimeError(
                    f"Unsupported OCR_PROVIDER `{settings.OCR_PROVIDER}`."
                )

            type(self)._shared_engines[provider] = engine
            return engine

    def _build_rapidocr_engine(self):
        try:
            rapidocr_module = importlib.import_module("rapidocr_onnxruntime")
        except ImportError as exc:
            raise RuntimeError(
                "RapidOCR is not installed. Install `rapidocr_onnxruntime` before importing image candidates."
            ) from exc

        RapidOCR = getattr(rapidocr_module, "RapidOCR", None)
        if RapidOCR is None:
            raise RuntimeError(
                "RapidOCR is installed, but the `RapidOCR` entrypoint could not be loaded."
            )

        try:
            return RapidOCR()
        except Exception as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(f"RapidOCR failed to initialize: {exc}") from exc

    def _build_paddleocr_engine(self):
        os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = (
            "True" if settings.PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK else "False"
        )

        try:
            paddleocr_module = importlib.import_module("paddleocr")
        except ImportError as exc:
            raise RuntimeError(
                "PaddleOCR is not installed. Install `paddleocr` and the required PaddlePaddle runtime before importing image candidates."
            ) from exc

        PaddleOCR = getattr(paddleocr_module, "PaddleOCR", None)
        if PaddleOCR is None:
            raise RuntimeError(
                "PaddleOCR is installed, but the `PaddleOCR` entrypoint could not be loaded."
            )

        try:
            return PaddleOCR(
                lang=settings.PADDLEOCR_LANG,
                use_doc_orientation_classify=settings.OCR_USE_DOC_ORIENTATION,
                use_doc_unwarping=settings.OCR_USE_DOC_UNWARPING,
                use_textline_orientation=settings.OCR_USE_TEXTLINE_ORIENTATION,
            )
        except ModuleNotFoundError as exc:
            if exc.name == "paddle":
                raise RuntimeError(
                    "PaddleOCR was found, but PaddlePaddle is missing in the active backend virtual environment. Install `paddlepaddle` into `backend\\venv` and restart the API server."
                ) from exc
            raise

    def _extract_text_sync(self, image_path: Path) -> OCRResult:
        """Extract text from a single image path."""
        try:
            engine = self._get_engine()
            raw_result = self._run_engine(engine, image_path)
        except Exception as exc:  # pragma: no cover - exercised by integration environments
            return OCRResult(status="failed", text=None, error=str(exc))

        lines = self._collect_text_lines(raw_result)

        merged_text = "\n".join(lines).strip()
        if not merged_text:
            return OCRResult(status="failed", text=None, error="No OCR text detected")
        return OCRResult(status="succeeded", text=merged_text)

    async def extract_text(self, image_path: Path) -> OCRResult:
        """Run OCR using the configured backend, keeping the event loop responsive."""
        provider = settings.OCR_PROVIDER.lower().strip()
        try:
            if provider == "mistral":
                return await self._extract_text_via_mistral(image_path)
            return await asyncio.to_thread(self._extract_text_sync, image_path)
        finally:
            self._release_engine_if_needed()

    async def warmup(self) -> None:
        """Warm the shared OCR engine ahead of the first user request."""
        provider = settings.OCR_PROVIDER.lower().strip()
        if provider in _CLOUD_PROVIDERS:
            return
        await asyncio.to_thread(self._get_engine)

    async def _extract_text_via_mistral(self, image_path: Path) -> OCRResult:
        """Call Mistral OCR API and return its markdown output as text."""
        api_key = settings.MISTRAL_API_KEY
        if not api_key:
            return OCRResult(
                status="failed",
                text=None,
                error="MISTRAL_API_KEY is not configured",
            )

        try:
            image_bytes = image_path.read_bytes()
        except OSError as exc:
            return OCRResult(status="failed", text=None, error=f"Cannot read image: {exc}")

        mime, _ = mimetypes.guess_type(str(image_path))
        if not mime or not mime.startswith("image/"):
            mime = "image/jpeg"
        b64 = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:{mime};base64,{b64}"

        payload = {
            "model": settings.MISTRAL_OCR_MODEL,
            "document": {"type": "image_url", "image_url": data_url},
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        last_error: str | None = None
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        "https://api.mistral.ai/v1/ocr",
                        json=payload,
                        headers=headers,
                    )
                if response.status_code >= 400:
                    last_error = f"Mistral OCR HTTP {response.status_code}: {response.text[:300]}"
                    continue
                data = response.json()
                pages = data.get("pages") or []
                chunks: list[str] = []
                for page in pages:
                    md = page.get("markdown") if isinstance(page, dict) else None
                    if isinstance(md, str) and md.strip():
                        chunks.append(md.strip())
                merged = "\n\n".join(chunks).strip()
                if not merged:
                    return OCRResult(
                        status="failed",
                        text=None,
                        error="Mistral OCR returned no text",
                    )
                return OCRResult(status="succeeded", text=merged)
            except (httpx.HTTPError, ValueError) as exc:
                last_error = f"Mistral OCR request failed: {exc}"
                continue

        return OCRResult(status="failed", text=None, error=last_error or "Mistral OCR failed")

    def _release_engine_if_needed(self) -> None:
        """Drop the shared OCR engine after use in low-memory deployments."""
        if not settings.LOW_MEMORY_MODE:
            return

        provider = settings.OCR_PROVIDER.lower().strip()
        if provider in _CLOUD_PROVIDERS:
            return
        with type(self)._engine_lock:
            type(self)._shared_engines.pop(provider, None)

    def _run_engine(self, engine: Any, image_path: Path) -> Any:
        provider = settings.OCR_PROVIDER.lower().strip()
        if provider == "rapidocr":
            return engine(str(image_path))
        return engine.predict(str(image_path))

    def _collect_text_lines(self, value: Any) -> list[str]:
        """Extract recognized text across supported OCR result formats."""
        lines: list[str] = []
        seen: set[str] = set()

        def add_line(text: Any) -> None:
            if not isinstance(text, str):
                return
            normalized = text.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                lines.append(normalized)

        def walk(node: Any) -> None:
            if node is None:
                return
            if isinstance(node, str):
                add_line(node)
                return
            if isinstance(node, dict):
                for key in ("rec_text", "rec_texts", "text", "texts", "ocr_text"):
                    if key in node:
                        value = node[key]
                        if isinstance(value, str):
                            add_line(value)
                        elif isinstance(value, (list, tuple)):
                            for item in value:
                                if isinstance(item, str):
                                    add_line(item)
                                else:
                                    walk(item)
                for value in node.values():
                    walk(value)
                return
            if isinstance(node, (list, tuple, set)):
                for item in node:
                    walk(item)
                return

            for attr in ("rec_text", "rec_texts", "text", "texts", "ocr_text"):
                if hasattr(node, attr):
                    value = getattr(node, attr)
                    if isinstance(value, str):
                        add_line(value)
                    elif isinstance(value, (list, tuple)):
                        for item in value:
                            if isinstance(item, str):
                                add_line(item)
                            else:
                                walk(item)

            if hasattr(node, "__dict__"):
                walk(vars(node))

        walk(value)
        return lines


PaddleOCRService = OCRService
