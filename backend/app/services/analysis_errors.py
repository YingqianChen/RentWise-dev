"""Stable analysis failures exposed to orchestration and API layers."""

from __future__ import annotations


ERROR_MESSAGES = {
    "no_usable_text": (
        "We could not read usable text from this source. Upload a clearer image "
        "or add the listing information as text."
    ),
    "llm_not_configured": (
        "The analysis service is not configured. Your source information is saved; "
        "configure the service and retry."
    ),
    "llm_unavailable": (
        "The analysis service is temporarily unavailable. Your source information "
        "is saved; please retry later."
    ),
    "invalid_model_output": (
        "This analysis did not produce a reliable result. Please retry or review "
        "the source information first."
    ),
    "analysis_internal_error": (
        "The analysis could not be completed. Your source information is saved; "
        "please retry."
    ),
}


class AnalysisError(Exception):
    """A classified analysis failure with safe user-facing metadata."""

    def __init__(self, *, code: str, user_message: str, retryable: bool) -> None:
        super().__init__(code)
        self.code = code
        self.user_message = user_message
        self.retryable = retryable


def analysis_error(code: str, *, retryable: bool) -> AnalysisError:
    """Build a classified error from the stable error catalogue."""
    return AnalysisError(
        code=code,
        user_message=ERROR_MESSAGES[code],
        retryable=retryable,
    )


def classify_extraction_exception(exc: Exception) -> AnalysisError:
    """Map provider and parsing exceptions to the public extraction contract."""
    message = str(exc).lower()

    if (
        "api_key" in message
        and any(marker in message for marker in ("required", "missing", "not configured", "invalid"))
    ) or "unknown llm provider" in message:
        return analysis_error("llm_not_configured", retryable=False)

    if isinstance(exc, (TimeoutError, ConnectionError)) or any(
        marker in message
        for marker in (
            "timed out",
            "timeout",
            "rate limit",
            "rate_limit",
            "status code 429",
            "status code 500",
            "status code 502",
            "status code 503",
            "status code 504",
            "error code: 429",
            "error code: 500",
            "error code: 502",
            "error code: 503",
            "error code: 504",
            "connection error",
            "service unavailable",
        )
    ):
        return analysis_error("llm_unavailable", retryable=True)

    if any(
        marker in message
        for marker in (
            "valid json",
            "json object",
            "jsondecode",
            "model response does not contain",
        )
    ):
        return analysis_error("invalid_model_output", retryable=True)

    return analysis_error("analysis_internal_error", retryable=True)
