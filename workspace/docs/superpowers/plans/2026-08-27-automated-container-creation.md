# Automated Container Creation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable the Openlayer backend to automatically create Docker containers on-demand when a sandbox is requested with `auto_create: true`, rather than requiring pre-existing containers.

**Architecture:** When `auto_create` is true and the specified container doesn't exist, the backend will use docker-py to create and start a fresh container from a specified image with resource limits. Auto-created containers are tracked in the database with an `auto_created` flag for cleanup during sandbox deletion. The existing flow (tmux session creation, exec socket, WebSocket) remains unchanged.

**Tech Stack:** Python, FastAPI, docker-py SDK, SQLite, Pytest

**Spec:** `docs/superpowers/specs/2026-08-27-automated-container-creation.md`

## Global Constraints

- Python 3.13 (dev), Python 3.11 (prod) - match existing setup
- docker-py already installed and used in `docker_pty.py`
- Backward compatible: existing API requests without `auto_create` must work unchanged
- All env vars validated via existing `env_config.py` rules (no DOCKER_*, no AWS_*, etc.)
- Tests must mock docker SDK calls (no actual Docker daemon access in CI)

---

## Task 1: Add Container Creation Functions to `docker_pty.py`

**Files:**
- Modify: `backend/docker_pty.py`
- Test: `backend/tests/test_docker_pty.py` (new)

**Interfaces:**
- Consumes: docker SDK client (`_client` from `docker.from_env()`)
- Produces:
  - `create_container(image, container_id, env=None, auto_remove=True) -> str` (returns container ID)
  - `container_exists(container_id) -> bool`
  - `remove_container(container_id) -> bool`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_docker_pty.py
"""Tests for docker_pty container creation functions."""
import pytest
from unittest.mock import MagicMock, patch


class TestContainerExists:
    @patch("docker_pty._client")
    def test_container_exists_found(self, mock_client):
        from docker_pty import container_exists
        mock_client.containers.get.return_value = MagicMock(status="running")
        assert container_exists("my-container") is True
        mock_client.containers.get.assert_called_once_with("my-container")

    @patch("docker_pty._client")
    def test_container_exists_not_found(self, mock_client):
        from docker_pty import container_exists
        from docker.errors import NotFound
        mock_client.containers.get.side_effect = NotFound("not found")
        assert container_exists("nonexistent") is False


class TestCreateContainer:
    @patch("docker_pty._client")
    def test_create_container_success(self, mock_client):
        from docker_pty import create_container
        mock_container = MagicMock()
        mock_container.id = "abc123"
        mock_container.status = "running"
        mock_client.containers.create.return_value = mock_container

        result = create_container(
            image="ubuntu:22.04",
            container_id="my-sandbox",
            env={"FOO": "bar"},
            auto_remove=True
        )
        assert result == "my-sandbox"  # We use the specified container_id

    @patch("docker_pty._client")
    def test_create_container_without_env(self, mock_client):
        from docker_pty import create_container
        mock_container = MagicMock()
        mock_container.id = "abc123"
        mock_client.containers.create.return_value = mock_container

        result = create_container(
            image="ubuntu:22.04",
            container_id="test-sandbox"
        )
        assert result is not None


class TestRemoveContainer:
    @patch("docker_pty._client")
    def test_remove_container_success(self, mock_client):
        from docker_pty import remove_container
        mock_container = MagicMock()
        mock_client.containers.get.return_value = mock_container

        result = remove_container("my-container")
        assert result is True
        mock_container.remove.assert_called_once_with(force=True)

    @patch("docker_pty._client")
    def test_remove_container_not_found(self, mock_client):
        from docker_pty import remove_container
        from docker.errors import NotFound
        mock_client.containers.get.side_effect = NotFound("not found")

        result = remove_container("nonexistent")
        assert result is False
```

Run: `pytest backend/tests/test_docker_pty.py -v`
Expected: FAIL (functions don't exist)

- [ ] **Step 2: Implement container_exists**

```python
def container_exists(container_id: str) -> bool:
    """Check if a container with the given ID exists (running or stopped)."""
    try:
        c = _client.containers.get(container_id)
        return True
    except Exception:
        return False
```

- [ ] **Step 3: Implement create_container**

```python
def create_container(
    image: str,
    container_id: str,
    env: dict[str, str] | None = None,
    auto_remove: bool = True,
    cpu_limit: str | None = None,
    memory_limit: str | None = None,
) -> str:
    """Create and start a new Docker container with the given ID.
    
    Args:
        image: Docker image to use
        container_id: Name/ID to assign to the container
        env: Environment variables to inject
        auto_remove: Whether to auto-remove on exit (sets --rm flag)
        cpu_limit: CPU quota (e.g. "1.0" = 1 CPU)
        memory_limit: Memory limit (e.g. "512m")
        
    Returns:
        The container_id on success
        
    Raises:
        docker.errors.APIError: On creation or start failure
    """
    # Build container configuration
    host_config = _client.api.create_host_config(
        auto_remove=auto_remove,
        network="openlayer-network" if "openlayer-network" in _get_network_names() else None
    )
    
    # Apply resource limits if specified
    if cpu_limit:
        host_config["CpuQuota"] = int(float(cpu_limit) * 100000)
        host_config["CpuPeriod"] = 100000
    
    kwargs: dict[str, Any] = {
        "name": container_id,
        "image": image,
        "command": "sleep infinity",  # Keep container running
        "stdin_open": True,
        "tty": True,
        "host_config": host_config,
    }
    
    if env:
        kwargs["environment"] = env
    
    c = _client.containers.create(**kwargs)
    c.start()
    return container_id


def _get_network_names() -> list[str]:
    """Get list of available Docker network names."""
    try:
        return [n.name for n in _client.networks.list()]
    except Exception:
        return []
```

Wait - actually, let me reconsider. The `auto_remove` in host_config isn't a host_config option. Let me fix this approach.<tool_call>Read<arg_key>file_path</arg_key><arg_value>/workspace/openlayer/backend/requirements.txt