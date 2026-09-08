"""Helpers for candidate import with OCR-backed image uploads."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from fastapi import HTTPException, UploadFile, status

from ..db.models import CandidateListing, CandidateSourceAsset
from .file_storage_service import LocalFileStorageService
from .upload_limits import MAX_IMAGE_COUNT, MAX_IMAGE_BYTES, MAX_TOTAL_IMAGE_BYTES, MAX_SOURCE_TEXT_CHARS


def validate_source_text(*parts: str | None) -> None:
    if sum(len(part or "") for part in parts) > MAX_SOURCE_TEXT_CHARS:
        raise HTTPException(status_code=413, detail="Keep listing, chat and notes within 30,000 characters in total.")

SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def _has_text(value: str | None) -> bool:
    return bool(value and value.strip())


def build_combined_text(*parts: str | None) -> str | None:
    """Join meaningful text chunks into a single analysis payload."""
    combined = "\n\n".join(part.strip() for part in parts if _has_text(part))
    return combined or None


def infer_source_type(
    *,
    source_type: str | None,
    has_listing_text: bool,
    has_chat_text: bool,
    has_note_text: bool,
    has_images: bool,
) -> str:
    """Infer a stable source type for the candidate."""
    if source_type:
        return source_type
    if has_images and (has_listing_text or has_chat_text or has_note_text):
        return "mixed"
    if has_images:
        return "image_upload"
    if has_listing_text and has_chat_text:
        return "mixed"
    if has_listing_text:
        return "manual_text"
    return "chat_log"


def validate_uploaded_images(images: Iterable[UploadFile]) -> list[UploadFile]:
    """Reject unsupported upload types early."""
    images = list(images)
    if len(images) > MAX_IMAGE_COUNT:
        raise HTTPException(status_code=413, detail="Upload at most 8 images per candidate.")
    if any(upload.size is not None and upload.size > MAX_IMAGE_BYTES for upload in images):
        raise HTTPException(status_code=413, detail="Each image must be 10 MB or smaller.")
    if sum(upload.size or 0 for upload in images) > MAX_TOTAL_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Images must total 30 MB or less.")
    validated: list[UploadFile] = []
    for upload in images:
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix in SUPPORTED_IMAGE_SUFFIXES:
            validated.append(upload)
            continue
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported upload type for {upload.filename or 'file'}. Please upload image files only.",
        )
    return validated


@dataclass
class PreparedCandidateImport:
    """Prepared import payload before persistence."""

    source_type: str
    combined_text: str
    source_assets: list[CandidateSourceAsset]


class CandidateImportService:
    """Handle candidate source images before assessment begins."""

    def __init__(self) -> None:
        self.storage = LocalFileStorageService()

    async def prepare_uploaded_images(
        self,
        *,
        candidate: CandidateListing,
        uploaded_images: list[UploadFile],
    ) -> list[CandidateSourceAsset]:
        """Persist uploaded images and create pending OCR asset records."""
        assets: list[CandidateSourceAsset] = []
        for upload in uploaded_images:
            if upload.size is None:
                upload.file.seek(0, 2)
                upload.size = upload.file.tell()
                await upload.seek(0)
        validate_uploaded_images(uploaded_images)

        try:
            for upload in validate_uploaded_images(uploaded_images):
                stored = await self.storage.save_candidate_image(
                    project_id=str(candidate.project_id),
                    candidate_id=str(candidate.id),
                    upload=upload,
                )
                assets.append(
                    CandidateSourceAsset(
                        candidate_id=candidate.id,
                        storage_provider=stored.storage_provider,
                        storage_key=stored.storage_key,
                        original_filename=stored.original_filename,
                        content_type=stored.content_type,
                        file_size=stored.file_size,
                        ocr_status="pending",
                        ocr_text=None,
                    )
                )
        except Exception:
            for asset in assets:
                self.storage.delete_file(asset.storage_key)
            raise
        return assets
