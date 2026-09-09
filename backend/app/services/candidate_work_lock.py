"""Cross-process coordination using transaction-scoped PostgreSQL advisory locks.

The lock connection is separate from the work session: pipeline commits cannot
release it. PostgreSQL releases locks on transaction/connection termination, so
an interrupted process does not leave a permanent lock or require a lease timer.
"""

from contextlib import asynccontextmanager
from hashlib import blake2b
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from ..core.config import settings

_lock_engine: AsyncEngine | None = None


def get_lock_engine() -> AsyncEngine:
    global _lock_engine
    if _lock_engine is None:
        # Lock holders must not consume the same finite pool needed to finish
        # their work. NullPool also closes each guard connection on release.
        _lock_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    return _lock_engine


class CandidateWorkBusy(Exception):
    """Another request is changing this candidate or its project."""


def _lock_key(kind: str, resource_id: UUID) -> int:
    return int.from_bytes(
        blake2b(f"rentwise:{kind}:{resource_id}".encode(), digest_size=8).digest(), "big", signed=True
    )


@asynccontextmanager
async def candidate_work_lock(
    *, project_id: UUID, candidate_id: UUID | None = None, exclusive_project: bool = False, engine=None
):
    # Never wait with a pooled connection for another analysis to finish.
    async with (engine or get_lock_engine()).begin() as connection:
        project_function = "pg_try_advisory_xact_lock" if exclusive_project else "pg_try_advisory_xact_lock_shared"
        acquired = await connection.scalar(
            text(f"SELECT {project_function}(:key)"), {"key": _lock_key("project", project_id)}
        )
        if not acquired:
            raise CandidateWorkBusy
        if candidate_id is not None:
            acquired = await connection.scalar(
                text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": _lock_key("candidate", candidate_id)}
            )
            if not acquired:
                raise CandidateWorkBusy
        yield
