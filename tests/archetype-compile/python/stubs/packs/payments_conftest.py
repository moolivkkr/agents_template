"""harness: the app-level payment_service fixture testing/external-service-mocks.md's Stripe test uses — a
small client that calls Stripe's REST API with httpx (which pytest-httpx intercepts)."""
from __future__ import annotations

from dataclasses import dataclass

import httpx
import pytest


@dataclass
class PaymentIntent:
    id: str
    status: str


class PaymentService:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def create_intent(self, *, amount: int, currency: str) -> PaymentIntent:
        resp = await self._client.post("/v1/payment_intents", data={"amount": amount, "currency": currency})
        resp.raise_for_status()
        body = resp.json()
        return PaymentIntent(id=body["id"], status=body["status"])


@pytest.fixture
async def payment_service():
    async with httpx.AsyncClient(base_url="https://api.stripe.com", auth=("sk_test_harness", "")) as client:
        yield PaymentService(client)
