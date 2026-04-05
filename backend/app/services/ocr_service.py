"""OCR service abstraction backed by PaddleOCR."""

from __future__ import annotations

import asyncio
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.config import settings


@dataclass
class OCRResult:
    """OCR output for one uploaded file."""

    status: str
    text: str | None
    error: str | None = None


class PaddleOCRService:
    """Run OCR over uploaded images using PaddleOCR when available."""

    _shared_engine = None
    _engine_lock = threading.Lock()

    def _get_engine(self):
        if type(self)._shared_engine is not None:
            return type(self)._shared_engine

        with type(self)._engine_lock:
            if type(self)._shared_engine is not None:
                return type(self)._shared_engine

            os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = (
                "True" if settings.PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK else "False"
            )

            try:
                from paddleocr import PaddleOCR  # type: ignore
            except ImportError as exc:
                raise RuntimeError(
                    "PaddleOCR is not installed. Install `paddleocr` and the required PaddlePaddle runtime before importing image candidates."
                ) from exc

            try:
                type(self)._shared_engine = PaddleOCR(
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
            return type(self)._shared_engine

    def _extract_text_sync(self, image_path: Path) -> OCRResult:
        """Extract text from a single image path."""
        try:
            engine = self._get_engine()
            raw_result = engine.predict(str(image_path))
        except Exception as exc:  # pragma: no cover - exercised by integration environments
            return OCRResult(status="failed", text=None, error=str(exc))

        lines = self._collect_text_lines(raw_result)

        merged_text = "\n".join(lines).strip()
        if not merged_text:
            return OCRResult(status="failed", text=None, error="No OCR text detected")
        return OCRResult(status="succeeded", text=merged_text)

    async def extract_text(self, image_path: Path) -> OCRResult:
        """Run OCR in a worker thread so the async request loop stays responsive."""
        return await asyncio.to_thread(self._extract_text_sync, image_path)

    async def warmup(self) -> None:
        """Warm the shared OCR engine ahead of the first user request."""
        await asyncio.to_thread(self._get_engine)

    def _collect_text_lines(self, value: Any) -> list[str]:
        """Extract recognized text from PaddleOCR results across API versions."""
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
