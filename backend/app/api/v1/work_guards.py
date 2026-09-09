"""Authorize and serialize writes before loading mutable candidate snapshots."""

from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.database import get_db
from ...db.models import CandidateListing, SearchProject, User
from ...services.candidate_work_lock import CandidateWorkBusy, candidate_work_lock
from .auth import get_current_user


@asynccontextmanager
async def _guard(project_id, user, db, *, candidate_id=None, exclusive_project=False):
    owned = await db.scalar(
        select(SearchProject.id).where(SearchProject.id == project_id, SearchProject.user_id == user.id)
    )
    if owned is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if candidate_id is not None:
        exists = await db.scalar(
            select(CandidateListing.id).where(
                CandidateListing.id == candidate_id, CandidateListing.project_id == project_id
            )
        )
        if exists is None:
            raise HTTPException(status_code=404, detail="Candidate not found")
    try:
        async with candidate_work_lock(
            project_id=project_id, candidate_id=candidate_id, exclusive_project=exclusive_project
        ):
            try:
                yield
                # Persist before releasing the guard; get_db's later commit is empty.
                await db.commit()
            except BaseException:
                await db.rollback()
                raise
    except CandidateWorkBusy as exc:
        raise HTTPException(
            status_code=409,
            detail="An operation is still running for this candidate or project. Please wait and try again.",
            headers={"Retry-After": "3"},
        ) from exc


async def guard_candidate_write(
    project_id: UUID, candidate_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    async with _guard(project_id, user, db, candidate_id=candidate_id):
        yield


async def guard_candidate_import(
    project_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    async with _guard(project_id, user, db):
        yield


async def guard_project_write(
    project_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    async with _guard(project_id, user, db, exclusive_project=True):
        yield
