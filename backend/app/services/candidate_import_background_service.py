"""In-process background work for OCR-backed candidate imports."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import selectinload

from ..db.models import CandidateListing, CandidateSourceAsset, SearchProject
from .candidate_import_service import build_combined_text
from .candidate_pipeline_service import CandidatePipelineService
from .file_storage_service import LocalFileStorageService
from .ocr_service import PaddleOCRService

logger = logging.getLogger(__name__)


class CandidateImportBackgroundService:
    """Run OCR and candidate assessment after the import request returns."""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self.session_factory = session_factory
        self.storage = LocalFileStorageService()
        self.ocr = PaddleOCRService()
        self.pipeline = CandidatePipelineService()

    async def process_candidate_import(
        self,
        *,
        project_id: UUID,
        candidate_id: UUID,
        should_autoname: bool,
    ) -> None:
        """Finish OCR and assessment for a queued candidate import."""
        async with self.session_factory() as db:
            try:
                candidate = await self._load_candidate(db, candidate_id=candidate_id, project_id=project_id)
                project = candidate.project

                if candidate.source_assets:
                    candidate.processing_stage = "running_ocr"
                    candidate.processing_error = None
                    await db.commit()
                    await self._run_ocr(candidate.source_assets)
                    await db.commit()

                candidate.combined_text = build_combined_text(
                    candidate.raw_listing_text,
                    candidate.raw_chat_text,
                    candidate.raw_note_text,
                    *[asset.ocr_text for asset in candidate.source_assets],
                )

                if not candidate.combined_text:
                    candidate.processing_stage = "failed"
                    candidate.processing_error = (
                        "OCR could not read any usable text from the uploaded images. "
                        "Try a clearer screenshot or add text manually."
                    )
                    candidate.status = "needs_info"
                    await db.commit()
                    return

                candidate.processing_stage = "extracting"
                candidate.processing_error = None
                await db.commit()

                await self.pipeline.assess_candidate(db=db, project=project, candidate=candidate)
                if should_autoname:
                    candidate.name = await self.pipeline.generate_candidate_name(candidate)

                candidate.processing_stage = "completed"
                candidate.processing_error = None
                await db.commit()
            except Exception as exc:  # pragma: no cover - best-effort recovery path
                logger.exception("Candidate background import failed", exc_info=exc)
                await db.rollback()
                await self._mark_candidate_failed(db, candidate_id=candidate_id, message=str(exc))

    async def _load_candidate(
        self,
        db,
        *,
        candidate_id: UUID,
        project_id: UUID,
    ) -> CandidateListing:
        result = await db.execute(
            select(CandidateListing)
            .options(
                selectinload(CandidateListing.project),
                selectinload(CandidateListing.source_assets),
            )
            .where(
                CandidateListing.id == candidate_id,
                CandidateListing.project_id == project_id,
            )
        )
        candidate = result.scalar_one()
        return candidate

    async def _run_ocr(self, source_assets: list[CandidateSourceAsset]) -> None:
        for asset in source_assets:
            image_path = self.storage.resolve_path(asset.storage_key)
            ocr_result = await self.ocr.extract_text(image_path)
            asset.ocr_status = ocr_result.status
            asset.ocr_text = ocr_result.text

    async def _mark_candidate_failed(self, db, *, candidate_id: UUID, message: str) -> None:
        result = await db.execute(select(CandidateListing).where(CandidateListing.id == candidate_id))
        candidate = result.scalar_one_or_none()
        if candidate is None:
            return
        candidate.processing_stage = "failed"
        candidate.processing_error = message
        candidate.status = "needs_info"
        await db.commit()
