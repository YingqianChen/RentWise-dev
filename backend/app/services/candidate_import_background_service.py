"""In-process background work for OCR-backed candidate imports."""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import selectinload

from ..core.config import settings
from ..db.models import CandidateListing, CandidateSourceAsset
from .candidate_work_lock import CandidateWorkBusy, candidate_work_lock
from .analysis_errors import AnalysisError, analysis_error
from .candidate_import_service import build_combined_text
from .candidate_pipeline_service import CandidatePipelineService
from .file_storage_service import LocalFileStorageService
from .ocr_service import OCRService

logger = logging.getLogger(__name__)


class CandidateImportBackgroundService:
    """Run OCR and candidate assessment after the import request returns."""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self.session_factory = session_factory
        self.storage = LocalFileStorageService()
        self.ocr = OCRService()
        self.pipeline = CandidatePipelineService()

    async def process_candidate_import(self, *, project_id: UUID, candidate_id: UUID, should_autoname: bool) -> None:
        """Claim queued work once across workers; duplicate dispatches do no work."""
        try:
            async with candidate_work_lock(project_id=project_id, candidate_id=candidate_id):
                await self.process_claimed_candidate_import(project_id=project_id, candidate_id=candidate_id, should_autoname=should_autoname, queued_only=True)
        except CandidateWorkBusy:
            logger.info("Candidate work is already claimed; ignoring duplicate dispatch")

    async def process_claimed_candidate_import(
        self,
        *,
        project_id: UUID,
        candidate_id: UUID,
        should_autoname: bool,
        queued_only: bool = False,
    ) -> None:
        """Finish OCR and assessment for a queued candidate import."""
        async with self.session_factory() as db:
            try:
                candidate = await self._load_candidate(db, candidate_id=candidate_id, project_id=project_id)
                if candidate is None or (queued_only and candidate.processing_stage != "queued"):
                    return
                project = candidate.project

                async with asyncio.timeout(settings.ANALYSIS_TIMEOUT_SECONDS):
                    if candidate.source_assets:
                        candidate.processing_stage = "running_ocr"
                        candidate.processing_error = None
                        candidate.processing_error_code = None
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
                        failure = analysis_error("no_usable_text", retryable=True)
                        candidate.processing_error = failure.user_message
                        candidate.processing_error_code = failure.code
                        candidate.status = "needs_info"
                        await db.commit()
                        return

                    candidate.processing_stage = "extracting"
                    candidate.processing_error = None
                    candidate.processing_error_code = None
                    await db.commit()

                    await self.pipeline.assess_candidate(db=db, project=project, candidate=candidate)
                    if should_autoname:
                        candidate.name = await self.pipeline.generate_candidate_name(candidate)

                    candidate.processing_stage = "completed"
                    candidate.processing_error = None
                    candidate.processing_error_code = None
                    await db.commit()
            except TimeoutError:
                await db.rollback()
                failure = analysis_error("analysis_timeout", retryable=True)
                await self._mark_candidate_failed(db, candidate_id=candidate_id, code=failure.code, message=failure.user_message)
            except AnalysisError as exc:
                logger.warning("Candidate analysis failed with code %s", exc.code)
                await db.rollback()
                await self._mark_candidate_failed(
                    db,
                    candidate_id=candidate_id,
                    code=exc.code,
                    message=exc.user_message,
                )
            except Exception as exc:  # pragma: no cover - best-effort recovery path
                logger.exception("Candidate background import failed", exc_info=exc)
                await db.rollback()
                failure = analysis_error("analysis_internal_error", retryable=True)
                await self._mark_candidate_failed(
                    db,
                    candidate_id=candidate_id,
                    code=failure.code,
                    message=failure.user_message,
                )

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
        candidate = result.scalar_one_or_none()
        return candidate

    async def _run_ocr(self, source_assets: list[CandidateSourceAsset]) -> None:
        for asset in source_assets:
            if asset.ocr_status == "succeeded" and asset.ocr_text:
                continue
            image_path = self.storage.resolve_path(asset.storage_key)
            ocr_result = await self.ocr.extract_text(image_path)
            asset.ocr_status = ocr_result.status
            asset.ocr_text = ocr_result.text

    async def _mark_candidate_failed(
        self,
        db,
        *,
        candidate_id: UUID,
        code: str,
        message: str,
    ) -> None:
        result = await db.execute(select(CandidateListing).where(CandidateListing.id == candidate_id))
        candidate = result.scalar_one_or_none()
        if candidate is None:
            return
        candidate.processing_stage = "failed"
        candidate.processing_error = message
        candidate.processing_error_code = code
        candidate.status = "needs_info"
        await db.commit()
