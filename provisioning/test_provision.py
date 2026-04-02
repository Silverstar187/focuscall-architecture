"""
test_provision.py — Unit tests for provision.py
All Docker/IO calls are mocked — no real Docker daemon required.
All tests use the provision_env fixture for file isolation.
"""

import json

import pytest
from unittest.mock import MagicMock, patch
import docker.errors

from provision import provision_container, deprovision_container, list_containers


def _make_docker_mock(container_id="abc123def456abc", ip="172.17.0.2"):
    """Build a mock docker.from_env() that behaves like a real Docker client."""
    mock_container = MagicMock()
    mock_container.id = container_id
    mock_container.attrs = {
        "NetworkSettings": {
            "IPAddress": ip,
            "Networks": {},
        }
    }
    mock_container.reload.return_value = None
    mock_container.stop.return_value = None
    mock_container.remove.return_value = None

    mock_client = MagicMock()
    # containers.get raises NotFound (no stale container to remove)
    mock_client.containers.get.side_effect = docker.errors.NotFound("not found")
    mock_client.containers.run.return_value = mock_container

    mock_docker = MagicMock()
    mock_docker.return_value = mock_client

    return mock_docker, mock_container, mock_client


def _make_urlopen_mock(status=200):
    """Build a mock for urllib.request.urlopen that returns given HTTP status."""
    mock_resp = MagicMock()
    mock_resp.status = status
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    mock_urlopen = MagicMock(return_value=mock_resp)
    return mock_urlopen


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_provision_happy_path(provision_env):
    mock_docker, mock_container, mock_client = _make_docker_mock()
    mock_urlopen = _make_urlopen_mock(status=200)

    with patch("provision.docker.from_env", mock_docker), \
         patch("provision.urllib.request.urlopen", mock_urlopen), \
         patch("provision.time.sleep"):

        result = provision_container("user1", "agent1", "llm_key_val", "bot_token_val", "openrouter")

    assert result["status"] == "running"
    assert result["port"] == 42000

    # Registry was written correctly
    registry_path = provision_env["registry"]
    assert registry_path.exists()
    registry = json.loads(registry_path.read_text())
    assert "user1-agent1" in registry["instances"]
    assert registry["instances"]["user1-agent1"]["status"] == "running"

    # Workspace and subdirs were created
    workspace = provision_env["workspaces"] / "user1" / "agent1"
    assert workspace.is_dir()

    # config.toml was rendered
    config_file = workspace / "config.toml"
    assert config_file.exists()
    config_text = config_file.read_text()
    assert "user1" in config_text


def test_provision_existing_running_instance(provision_env):
    # Pre-seed registry with a running instance
    registry_data = {
        "next_port": 42001,
        "instances": {
            "user1-agent1": {
                "port": 42000,
                "status": "running",
                "container_id": "existing123",
            }
        },
    }
    provision_env["registry"].write_text(json.dumps(registry_data))

    # No Docker mock needed — function returns early before touching Docker
    result = provision_container("user1", "agent1", "k", "t", "openrouter")

    assert result == {"status": "running", "port": 42000, "container_id": "existing123"}


def test_provision_health_check_failure(provision_env):
    mock_docker, mock_container, mock_client = _make_docker_mock()
    # urlopen always raises an exception → all health checks fail
    mock_urlopen = MagicMock(side_effect=Exception("connection refused"))

    with patch("provision.docker.from_env", mock_docker), \
         patch("provision.urllib.request.urlopen", mock_urlopen), \
         patch("provision.time.sleep"):

        result = provision_container("user1", "agent1", "k", "t", "openrouter")

    assert result["status"] == "error"

    # Container cleanup (stop + remove) must have been called
    mock_container.stop.assert_called_once()
    mock_container.remove.assert_called_once()


def test_deprovision_removes_all(provision_env):
    # Pre-seed registry with one instance
    registry_data = {
        "next_port": 42001,
        "instances": {
            "user1-agent1": {
                "port": 42000,
                "status": "running",
                "container_id": "abc123",
            }
        },
    }
    provision_env["registry"].write_text(json.dumps(registry_data))

    # Create workspace dir with a dummy file
    workspace = provision_env["workspaces"] / "user1" / "agent1"
    workspace.mkdir(parents=True)
    (workspace / "dummy.txt").write_text("data")

    mock_container = MagicMock()
    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container
    mock_docker = MagicMock(return_value=mock_client)

    with patch("provision.docker.from_env", mock_docker):
        result = deprovision_container("user1", "agent1")

    assert result["status"] == "removed"

    # Container stop/remove were called
    mock_container.stop.assert_called_once()
    mock_container.remove.assert_called_once()

    # Workspace no longer exists
    assert not workspace.exists()

    # Registry entry removed
    registry = json.loads(provision_env["registry"].read_text())
    assert "user1-agent1" not in registry["instances"]


def test_list_containers_returns_registry(provision_env):
    registry_data = {
        "next_port": 42002,
        "instances": {
            "user1-agent1": {"port": 42000, "status": "running"},
            "user2-agent2": {"port": 42001, "status": "starting"},
        },
    }
    provision_env["registry"].write_text(json.dumps(registry_data))

    result = list_containers()

    assert len(result["instances"]) == 2
    assert result["next_port"] == 42002


def test_port_allocation_increments(provision_env):
    mock_docker, mock_container, mock_client = _make_docker_mock()
    mock_urlopen = _make_urlopen_mock(status=200)

    with patch("provision.docker.from_env", mock_docker), \
         patch("provision.urllib.request.urlopen", mock_urlopen), \
         patch("provision.time.sleep"):

        result1 = provision_container("u1", "a1", "k", "t", "openrouter")

    assert result1["port"] == 42000

    # Reset container mock for second call
    mock_docker2, mock_container2, mock_client2 = _make_docker_mock(
        container_id="def456abc123def", ip="172.17.0.3"
    )
    mock_urlopen2 = _make_urlopen_mock(status=200)

    with patch("provision.docker.from_env", mock_docker2), \
         patch("provision.urllib.request.urlopen", mock_urlopen2), \
         patch("provision.time.sleep"):

        result2 = provision_container("u2", "a2", "k", "t", "openrouter")

    assert result2["port"] == 42001

    registry = json.loads(provision_env["registry"].read_text())
    assert registry["next_port"] == 42002
