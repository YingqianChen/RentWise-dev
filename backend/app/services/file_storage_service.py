"""Storage abstraction for uploaded candidate files."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from uuid import uuid4
import re

from fastapi import UploadFile

from ..core.config import settings


def _sanitize_filename(filename: str) -> str:
    stem = Path(filename).stem or "upload"
    suffix = Path(filename).suffix.lower()
    safe_stem = re.sub(r"[^A-Za-z0-9_-]+", "-", stem).strip("-") or "upload"
    return f"{safe_stem}{suffix}"


@dataclass
class StoredFile:
    """Saved file metadata returned by the storage layer."""

    storage_provider: str
    storage_key: str
    absolute_path: Path
    original_filename: str
    content_type: str | None
    file_size: int


class LocalFileStorageService:
    """Persist uploaded files in a local development storage root."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or settings.LOCAL_UPLOAD_ROOT)

    def resolve_path(self, storage_key: str) -> Path:
        """Resolve a stored relative key back to an absolute local path."""
        return self.root / Path(storage_key)

    async def save_candidate_image(
        self,
        *,
        project_id: str,
        candidate_id: str,
        upload: UploadFile,
    ) -> StoredFile:
        """Save an uploaded image and return the resulting metadata."""
        safe_name = _sanitize_filename(upload.filename or "upload")
        relative_dir = Path("candidate_uploads") / project_id / candidate_id
        absolute_dir = self.root / relative_dir
        absolute_dir.mkdir(parents=True, exist_ok=True)

        storage_name = f"{uuid4().hex}_{safe_name}"
        relative_key = relative_dir / storage_name
        absolute_path = self.root / relative_key

        content = await upload.read()
        content = self._prepare_image_bytes(content=content, suffix=Path(safe_name).suffix.lower())
        absolute_path.write_bytes(content)

        return StoredFile(
            storage_provider="local",
            storage_key=relative_key.as_posix(),
            absolute_path=absolute_path,
            original_filename=upload.filename or safe_name,
            content_type=upload.content_type,
            file_size=len(content),
        )

    def _prepare_image_bytes(self, *, content: bytes, suffix: str) -> bytes:
        """Shrink oversized images before OCR to reduce CPU-bound latency."""
        max_dimension = settings.effective_ocr_max_image_dimension
        if max_dimension <= 0:
            return content

        try:
            from PIL import Image, ImageOps  # type: ignore
        except ImportError:
            return content

        try:
            with Image.open(BytesIO(content)) as image:
                image = ImageOps.exif_transpose(image)
                if max(image.size) <= max_dimension:
                    return content

                image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
                output = BytesIO()
                image_format = (image.format or "").upper() or self._infer_image_format(suffix)

                if image_format in {"JPEG", "JPG"}:
                    if image.mode not in {"RGB", "L"}:
                        image = image.convert("RGB")
                    image.save(output, format="JPEG", optimize=True, quality=85)
                elif image_format == "PNG":
                    image.save(output, format="PNG", optimize=True)
                elif image_format == "WEBP":
                    image.save(output, format="WEBP", quality=85, method=6)
                elif image_format == "BMP":
                    image.save(output, format="PNG", optimize=True)
                else:
                    return content

                optimized = output.getvalue()
                return optimized or content
        except Exception:
            return content

    def _infer_image_format(self, suffix: str) -> str:
        if suffix in {".jpg", ".jpeg"}:
            return "JPEG"
        if suffix == ".png":
            return "PNG"
        if suffix == ".webp":
            return "WEBP"
        if suffix == ".bmp":
            return "BMP"
        return ""
