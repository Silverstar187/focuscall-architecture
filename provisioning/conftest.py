"""
conftest.py — Shared pytest fixtures for provisioning test suite.

IMPORTANT: WEBHOOK_SECRET must be set BEFORE any app imports, because
webhook-receiver.py reads it at module level with os.environ["WEBHOOK_SECRET"].
"""

import os

# Set BEFORE any app imports — webhook-receiver.py reads this at import time
os.environ["WEBHOOK_SECRET"] = "test_secret_64chars_" + "x" * 44

import hashlib
import hmac
import time

import pytest


@pytest.fixture
def make_hmac_headers():
    """Return a function that generates valid X-Timestamp and X-Signature headers."""
    def _make(user_id: str, agent_id: str, secret: str | None = None) -> dict[str, str]:
        secret = secret or os.environ["WEBHOOK_SECRET"]
        ts = str(int(time.time()))
        message = f"{user_id}:{agent_id}:{ts}"
        sig = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
        return {"X-Timestamp": ts, "X-Signature": sig}
    return _make


@pytest.fixture
def provision_env(tmp_path, monkeypatch):
    """
    Redirect REGISTRY_PATH, WORKSPACE_BASE, CONFIG_TEMPLATE_PATH to tmp_path.
    Patches both env vars AND the module-level globals in provision.py (since
    provision.py reads them at import time into module-level variables).
    """
    registry = tmp_path / "registry.json"
    workspaces = tmp_path / "workspaces"
    workspaces.mkdir()
    tmpl = tmp_path / "config.toml.tmpl"
    tmpl.write_text(
        "[agent]\nport = $PORT\nuser = $USER_ID\nagent = $AGENT_ID\nprovider = $LLM_PROVIDER\n"
    )

    monkeypatch.setenv("REGISTRY_PATH", str(registry))
    monkeypatch.setenv("WORKSPACE_BASE", str(workspaces))
    monkeypatch.setenv("CONFIG_TEMPLATE_PATH", str(tmpl))

    # Also patch the module-level variables in provision.py
    import provision
    monkeypatch.setattr(provision, "REGISTRY_PATH", str(registry))
    monkeypatch.setattr(provision, "WORKSPACE_BASE", str(workspaces))
    monkeypatch.setattr(provision, "CONFIG_TEMPLATE_PATH", str(tmpl))

    return {"registry": registry, "workspaces": workspaces, "tmpl": tmpl}
