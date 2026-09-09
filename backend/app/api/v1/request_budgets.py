"""HTTP adapters for shared authentication and account operation budgets."""

from fastapi import HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError

from ...core.config import settings
from ...services.rate_limit_service import Budget, BudgetExceeded, consume_budgets


async def _consume(budgets):
    try:
        await consume_budgets(budgets)
    except BudgetExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail=f"Too many attempts. Try again in about {max(1, (exc.retry_after + 59) // 60)} minute(s).",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except SQLAlchemyError as exc:
        # Fail closed when limits cannot be enforced; never expose DB details.
        raise HTTPException(
            status_code=503, detail="The service is temporarily unavailable. Please try again later."
        ) from exc


def _peer(request: Request) -> str:
    # Do not trust arbitrary X-Forwarded-For headers inside the application.
    return request.client.host if request.client else "unknown"


async def guard_registration(request: Request):
    await _consume([Budget("register_ip", _peer(request), settings.REGISTRATION_HOURLY_LIMIT, 3600)])


async def guard_login(request: Request):
    await _consume([Budget("login_ip", _peer(request), settings.LOGIN_MINUTE_LIMIT, 60)])


async def limit_login_identity(email: str):
    await _consume([Budget("login_email", email, settings.LOGIN_EMAIL_HOURLY_LIMIT, 3600)])


async def reserve_ai_operation(user_id):
    await _consume(
        [
            Budget("ai_minute", str(user_id), settings.AI_OPERATIONS_MINUTE_LIMIT, 60),
            Budget("ai_day", str(user_id), settings.AI_OPERATIONS_DAILY_LIMIT, 86400),
        ]
    )
