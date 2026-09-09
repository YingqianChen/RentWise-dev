from datetime import datetime, timedelta, timezone
import uuid

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from jose import jwt
from pydantic import ValidationError

from app.api.v1.auth import _parse_login_payload
from app.core.config import settings
from app.core.request_limits import JSON_BODY_LIMIT, RequestBodyLimitMiddleware
from app.core.security import decode_access_token
from app.schemas.candidate import CandidateUpdate
from app.schemas.investigation import InvestigationItemUpdate
from app.schemas.project import ProjectUpdate


def body_app():
    app = FastAPI()
    app.add_middleware(RequestBodyLimitMiddleware)

    @app.post("/echo")
    async def echo(request: Request):
        return {"length": len(await request.body())}

    @app.post("/login")
    async def login(request: Request):
        await _parse_login_payload(request)
        return {"ok": True}

    return app


def test_body_limit_rejects_content_length_before_consuming_body():
    client = TestClient(body_app())
    response = client.post("/echo", content=b"small", headers={"Content-Length": str(JSON_BODY_LIMIT + 1)})
    assert response.status_code == 413


async def test_chunked_body_cannot_bypass_byte_limit():
    async def chunks():
        yield b"x" * (JSON_BODY_LIMIT // 2)
        yield b"y" * (JSON_BODY_LIMIT // 2 + 1)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=body_app()), base_url="http://test") as client:
        response = await client.post("/echo", content=chunks())
    assert response.status_code == 413


@pytest.mark.parametrize("length", ["-1", "not-a-number", "9" * 5000])
def test_invalid_or_extreme_length_header_never_causes_500(length):
    response = TestClient(body_app()).post("/echo", content=b"", headers={"Content-Length": length})
    assert response.status_code in (400, 413)


def test_login_validation_does_not_echo_password_or_validator_context():
    secret = "do-not-echo-this-password"
    response = TestClient(body_app()).post("/login", json={"email": "invalid", "password": secret})
    assert response.status_code == 422
    assert secret not in response.text
    assert "ctx" not in response.text


def test_invalid_utf8_login_is_a_client_error():
    response = TestClient(body_app()).post("/login", content=b"\xff", headers={"Content-Type": "application/json"})
    assert response.status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {"sub": "not-a-uuid"},
        {"sub": str(uuid.uuid4())},
        {"sub": "not-a-uuid", "exp": 9999999999},
        {"sub": str(uuid.uuid4()), "exp": 0},
        {"exp": 9999999999},
    ],
)
def test_incomplete_or_invalid_identity_tokens_are_rejected(payload):
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    assert decode_access_token(token) is None


def test_valid_token_keeps_compatible_identity():
    identity = str(uuid.uuid4())
    token = jwt.encode(
        {"sub": identity, "exp": datetime.now(timezone.utc) + timedelta(minutes=1)},
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    assert decode_access_token(token) == identity


@pytest.mark.parametrize(
    "schema,payload",
    [
        (ProjectUpdate, {"title": None}),
        (ProjectUpdate, {"title": "  "}),
        (ProjectUpdate, {"status": None}),
        (ProjectUpdate, {"commute_departure_window": None}),
        (ProjectUpdate, {"max_budget": 2**40}),
        (CandidateUpdate, {"name": None}),
        (CandidateUpdate, {"name": "  "}),
        (InvestigationItemUpdate, {"status": None}),
    ],
)
def test_invalid_patch_values_fail_before_database_write(schema, payload):
    with pytest.raises(ValidationError):
        schema(**payload)


def test_extreme_money_integer_is_validation_error_instead_of_overflow():
    from app.services.candidate_field_registry import CandidateFieldValueError, validate_field_value
    with pytest.raises(CandidateFieldValueError):
        validate_field_value('monthly_rent', 10**2000)


def test_new_logins_have_distinct_session_ids():
    from app.core.security import create_access_token, decode_token_identity
    subject = str(uuid.uuid4())
    first = decode_token_identity(create_access_token(subject))
    second = decode_token_identity(create_access_token(subject))
    assert first.user_id == second.user_id == subject
    assert first.revocation_key != second.revocation_key


def test_revocation_identity_cannot_be_bypassed_by_signature_encoding():
    from app.core.security import create_access_token, decode_token_identity
    token = create_access_token(str(uuid.uuid4()))
    # python-jose accepts padded and unpadded encodings of the same signature.
    variant = token + "="
    assert variant != token
    assert decode_token_identity(variant) == decode_token_identity(token)


@pytest.mark.parametrize("expiry", [True, "9999999999", 1e100, 10**100, None])
def test_expiry_that_cannot_be_persisted_is_rejected(expiry):
    token = jwt.encode({"sub": str(uuid.uuid4()), "exp": expiry}, settings.SECRET_KEY, algorithm="HS256")
    assert decode_access_token(token) is None


def test_expiry_is_rejected_at_its_exact_instant(monkeypatch):
    import app.core.security as security
    expiry = datetime(2030, 1, 1, tzinfo=timezone.utc)
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return expiry + timedelta(microseconds=1)
    monkeypatch.setattr(security, "datetime", Clock)
    token = jwt.encode({"sub": str(uuid.uuid4()), "exp": expiry}, settings.SECRET_KEY, algorithm="HS256")
    assert security.decode_token_identity(token) is None
