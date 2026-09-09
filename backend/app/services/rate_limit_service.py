"""Atomic, shared request budgets stored independently of request rollbacks."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import math

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from ..core.config import settings
from ..db.models import RequestBudget
from .candidate_work_lock import get_lock_engine


@dataclass(frozen=True)
class Budget:
    scope: str
    identity: str
    limit: int
    seconds: int


class BudgetExceeded(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after


def budget_key(identity: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), identity.encode(), hashlib.sha256).hexdigest()


async def consume_budgets(budgets: list[Budget], *, engine=None) -> None:
    # Dedicated transaction: failed login / analysis must not refund attempts.
    async with (engine or get_lock_engine()).begin() as connection:
        now = await connection.scalar(select(func.clock_timestamp()))
        await connection.execute(delete(RequestBudget).where(RequestBudget.expires_at <= now))
        for budget in budgets:
            start = datetime.fromtimestamp(int(now.timestamp()) // budget.seconds * budget.seconds, tz=timezone.utc)
            end = start + timedelta(seconds=budget.seconds)
            statement = insert(RequestBudget).values(
                scope=budget.scope,
                identity_hash=budget_key(budget.identity),
                window_start=start,
                expires_at=end,
                used=1,
            )
            statement = statement.on_conflict_do_update(
                index_elements=[RequestBudget.scope, RequestBudget.identity_hash, RequestBudget.window_start],
                set_={"used": RequestBudget.used + 1},
                where=RequestBudget.used < budget.limit,
            ).returning(RequestBudget.used)
            if await connection.scalar(statement) is None:
                raise BudgetExceeded(max(1, math.ceil((end - now).total_seconds())))
