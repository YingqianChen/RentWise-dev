"""Verify provider retries with an in-memory HTTP transport, never a live API."""

import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase

import httpx
from groq import InternalServerError

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.integrations.llm.provider import GroqProvider
from app.core.config import settings


class ProviderRequestLimitsTests(IsolatedAsyncioTestCase):
    async def test_service_error_sends_one_request_without_sdk_retry(self):
        attempts = []

        def respond(request):
            attempts.append(request)
            return httpx.Response(503, json={"error": {"message": "Synthetic outage"}})

        provider = GroqProvider(api_key="synthetic-not-a-real-key")
        self.assertEqual(provider.client.timeout, settings.LLM_REQUEST_TIMEOUT_SECONDS)
        original_client = provider.client
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            provider.client = original_client.with_options(http_client=http)
            with self.assertRaises(InternalServerError):
                await provider.chat_completion_json(
                    messages=[{"role": "user", "content": "Synthetic listing"}], model="synthetic-model"
                )
        await original_client.close()
        self.assertEqual(len(attempts), 1)
