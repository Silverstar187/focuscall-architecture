"""
test_webhook.py — FastAPI endpoint tests for webhook-receiver.py

NOTE: webhook-receiver.py uses a hyphen in the filename, so it cannot be
imported with a plain `import` statement. We use importlib instead.
"""

import importlib
import time

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch

webhook_receiver = importlib.import_module("webhook-receiver")
app = webhook_receiver.app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ── Health ─────────────────────────────────────────────────────────────────────

async def test_health_returns_200(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "webhook-receiver"}


# ── POST /provision — auth failures ───────────────────────────────────────────

async def test_provision_missing_headers_returns_401(client):
    body = {
        "user_id": "u1",
        "agent_id": "a1",
        "llm_key": "k",
        "bot_token": "t",
        "llm_provider": "openrouter",
    }
    response = await client.post("/provision", json=body)
    assert response.status_code == 401


async def test_provision_expired_timestamp_returns_401(client, make_hmac_headers):
    import hashlib
    import hmac
    import os

    # Timestamp 10 minutes in the past — exceeds 300s limit
    old_ts = str(int(time.time()) - 600)
    secret = os.environ["WEBHOOK_SECRET"]
    message = f"u1:a1:{old_ts}"
    sig = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

    headers = {"X-Timestamp": old_ts, "X-Signature": sig}
    body = {
        "user_id": "u1",
        "agent_id": "a1",
        "llm_key": "k",
        "bot_token": "t",
        "llm_provider": "openrouter",
    }
    response = await client.post("/provision", json=body, headers=headers)
    assert response.status_code == 401


async def test_provision_wrong_signature_returns_401(client):
    headers = {
        "X-Timestamp": str(int(time.time())),
        "X-Signature": "0" * 64,
    }
    body = {
        "user_id": "u1",
        "agent_id": "a1",
        "llm_key": "k",
        "bot_token": "t",
        "llm_provider": "openrouter",
    }
    response = await client.post("/provision", json=body, headers=headers)
    assert response.status_code == 401


# ── POST /provision — success ──────────────────────────────────────────────────

async def test_provision_valid_request_returns_202(client, make_hmac_headers):
    headers = make_hmac_headers("u1", "a1")
    body = {
        "user_id": "u1",
        "agent_id": "a1",
        "llm_key": "k",
        "bot_token": "t",
        "llm_provider": "openrouter",
    }
    with patch.object(
        webhook_receiver,
        "provision_container",
        return_value={"status": "running", "port": 42000},
    ):
        response = await client.post("/provision", json=body, headers=headers)

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "provisioning"


# ── DELETE /provision/{user_id}/{agent_id} ─────────────────────────────────────

async def test_deprovision_missing_headers_returns_401(client):
    response = await client.delete("/provision/u1/a1")
    assert response.status_code == 401


async def test_deprovision_valid_request_returns_200(client, make_hmac_headers):
    headers = make_hmac_headers("u1", "a1")
    with patch.object(
        webhook_receiver,
        "deprovision_container",
        return_value={"status": "removed", "user_id": "u1", "agent_id": "a1"},
    ):
        response = await client.delete("/provision/u1/a1", headers=headers)

    assert response.status_code == 200
