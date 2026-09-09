"""Durable cleanup for files belonging to explicitly deleted records."""

import asyncio
from datetime import timedelta
import logging
from uuid import UUID, uuid4

from sqlalchemy import select

from ..db.database import get_session_factory, utc_now
from ..db.models import FileCleanupJob
from .file_storage_service import LocalFileStorageService

logger = logging.getLogger(__name__)


def enqueue_file_cleanup(db, keys: list[str]) -> list[UUID]:
    ids = []
    scope = LocalFileStorageService().storage_scope() if keys else None
    for key in dict.fromkeys(keys):
        job = FileCleanupJob(
            id=uuid4(), kind="file", storage_key=key, storage_scope=scope, attempts=0, next_attempt_at=utc_now()
        )
        db.add(job)
        ids.append(job.id)
    return ids


def enqueue_project_cleanup(db, project_id: UUID) -> list[UUID]:
    job = FileCleanupJob(
        id=uuid4(),
        kind="project",
        storage_key=str(project_id),
        storage_scope=LocalFileStorageService().storage_scope(),
        attempts=0,
        next_attempt_at=utc_now(),
    )
    db.add(job)
    return [job.id]


async def process_cleanup_jobs(
    *, job_ids: list[UUID] | None = None, session_factory=None, storage=None
) -> dict[str, int]:
    storage = storage or LocalFileStorageService()
    factory = session_factory or get_session_factory()
    counts = {"removed": 0, "pending": 0}
    async with factory() as db, db.begin():
        query = (
            select(FileCleanupJob)
            .where(FileCleanupJob.next_attempt_at <= utc_now(), FileCleanupJob.storage_scope == storage.storage_scope())
            .order_by(FileCleanupJob.next_attempt_at)
            .limit(25)
            .with_for_update(skip_locked=True)
        )
        if job_ids is not None:
            query = query.where(FileCleanupJob.id.in_(job_ids))
        jobs = (await db.execute(query)).scalars().all()
        for job in jobs:
            try:
                if job.kind == "file":
                    await asyncio.to_thread(storage.delete_file, job.storage_key)
                elif job.kind == "project":
                    await asyncio.to_thread(storage.delete_project_files, str(UUID(job.storage_key)))
                else:
                    raise ValueError("Unsupported cleanup job")
            except (OSError, ValueError) as exc:
                job.attempts += 1
                job.last_error = type(exc).__name__
                job.next_attempt_at = utc_now() + timedelta(seconds=min(3600, 30 * 2 ** min(job.attempts - 1, 7)))
                counts["pending"] += 1
                logger.warning("File cleanup deferred for job %s (%s)", job.id, job.last_error)
            else:
                await db.delete(job)
                counts["removed"] += 1
    return counts


async def attempt_cleanup(job_ids: list[UUID]) -> None:
    if not job_ids:
        return
    try:
        await process_cleanup_jobs(job_ids=job_ids)
    except Exception:
        # Deletion and its cleanup intent have already committed together.
        # A later worker can retry even when this response loses DB access.
        logger.warning("Immediate file cleanup unavailable; durable jobs remain pending")


async def cleanup_forever() -> None:
    while True:
        try:
            await process_cleanup_jobs()
        except Exception:
            logger.warning("File cleanup worker unavailable; retrying later")
        await asyncio.sleep(30)
