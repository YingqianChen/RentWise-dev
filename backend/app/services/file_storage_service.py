"""Storage abstraction for uploaded candidate files."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from uuid import uuid4
import re

from fastapi import HTTPException, UploadFile
from .upload_limits import MAX_IMAGE_BYTES, MAX_IMAGE_PIXELS

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
        root = self.root.resolve()
        target = (root / storage_key).resolve()
        if not target.is_relative_to(root) or target == root:
            raise ValueError("Storage key must stay inside the upload directory")
        return target

    def delete_file(self, storage_key: str) -> None:
        """Remove only the named asset, never an arbitrary directory."""
        self.resolve_path(storage_key).unlink(missing_ok=True)

    def delete_project_files(self, project_id: str) -> None:
        from uuid import UUID
        import shutil
        directory = self.resolve_path(f"candidate_uploads/{UUID(project_id)}")
        if directory.exists():
            shutil.rmtree(directory)

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

        content = await upload.read(MAX_IMAGE_BYTES + 1)
        if len(content) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="Each image must be 10 MB or smaller.")
        try:
            from PIL import Image
            with Image.open(BytesIO(content)) as image:
                if image.format not in {"PNG", "JPEG", "WEBP", "BMP"} or image.width * image.height > MAX_IMAGE_PIXELS:
                    raise ValueError("Unsupported or oversized image")
                image.verify()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Use a valid PNG, JPEG, WebP or BMP image of at most 25 megapixels.") from exc
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
