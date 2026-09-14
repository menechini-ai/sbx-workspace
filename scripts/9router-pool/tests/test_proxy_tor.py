"""Tests for Tor proxy on 9Router slaves.

- Unit: config.json has proxy, configure_slave creates proxy pool (mocked)
- Integration: Tor SOCKS reachable, slaves have proxy pool via API (needs docker up)

Run:
  pytest tests/test_proxy_tor.py -v
  pytest tests/test_proxy_tor.py -v -k integration --run-integration
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
CONFIG_FILE = BASE_DIR / "config.json"

sys.path.insert(0, str(SRC_DIR))


# ---------------------------------------------------------------------------
# Unit: config.json
# ---------------------------------------------------------------------------

class TestProxyConfig:
    def test_defaults_has_proxy(self):
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        assert "proxy" in data["defaults"], "defaults.proxy missing in config.json"
        proxy = data["defaults"]["proxy"]
        assert proxy["name"] == "tor-proxy"
        assert proxy["url"] == "socks5://sbx-tor:9050"
        assert proxy["type"] == "socks5"
        assert "noProxy" in proxy

    def test_proxy_not_on_master(self):
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        # proxy must be under defaults, not master — only slaves use it
        assert "proxy" not in data["master"]
        for slave in data["slaves"]:
            assert "proxy" not in slave, f"slave {slave['name']} should not have inline proxy, use defaults.proxy"


# ---------------------------------------------------------------------------
# Unit: configure_slave creates proxy pool (mocked)
# ---------------------------------------------------------------------------

class TestConfigureSlaveProxy:
    def _make_slave(self, name="rs001", host="localhost:20129"):
        from server_pool.models import Instance
        return Instance(name=name, host=host, password="123456", docker_host=f"9router-slave-001:20129")

    def test_creates_proxy_pool_when_missing(self):
        from server_pool import sync as sync_mod

        slave = self._make_slave()
        defaults = {
            "models": ["oc/big-pickle"],
            "combos": [{"name": "claude-sonnet-5", "models": ["oc/big-pickle"]}],
            "proxy": {"name": "tor-proxy", "url": "socks5://sbx-tor:9050", "type": "socks5", "noProxy": "localhost,127.0.0.1"},
        }

        mock_client = MagicMock()
        mock_client.get_proxy_pools.return_value = []  # none exists
        mock_client.get_api_keys.return_value = []
        mock_client.create_api_key.return_value = {"key": "sk-test"}
        mock_client.get_combos.return_value = []
        mock_client.get_custom_models.return_value = []

        with patch.object(sync_mod, "RouterClient", return_value=mock_client), \
             patch.object(sync_mod, "wait_for_instance", return_value=True):
            sync_mod.configure_slave(slave, defaults)

        mock_client.create_proxy_pool.assert_called_once_with(
            name="tor-proxy",
            proxy_url="socks5://sbx-tor:9050",
            pool_type="socks5",
            no_proxy="localhost,127.0.0.1",
        )

    def test_skips_when_already_configured(self):
        from server_pool import sync as sync_mod

        slave = self._make_slave()
        defaults = {
            "models": [],
            "combos": [],
            "proxy": {"name": "tor-proxy", "url": "socks5://sbx-tor:9050", "type": "socks5", "noProxy": "localhost,127.0.0.1"},
        }

        mock_client = MagicMock()
        mock_client.get_proxy_pools.return_value = [
            {"name": "tor-proxy", "proxyUrl": "socks5://sbx-tor:9050"}
        ]
        mock_client.get_api_keys.return_value = []
        mock_client.create_api_key.return_value = {"key": "sk-test"}
        mock_client.get_combos.return_value = []
        mock_client.get_custom_models.return_value = []

        with patch.object(sync_mod, "RouterClient", return_value=mock_client), \
             patch.object(sync_mod, "wait_for_instance", return_value=True):
            sync_mod.configure_slave(slave, defaults)

        mock_client.create_proxy_pool.assert_not_called()

    def test_uses_defaults_when_proxy_missing(self):
        """Fallback to socks5://sbx-tor:9050 when defaults.proxy absent."""
        from server_pool import sync as sync_mod

        slave = self._make_slave()
        defaults = {"models": [], "combos": []}  # no proxy key

        mock_client = MagicMock()
        mock_client.get_proxy_pools.return_value = []
        mock_client.get_api_keys.return_value = []
        mock_client.create_api_key.return_value = {"key": "sk-test"}
        mock_client.get_combos.return_value = []
        mock_client.get_custom_models.return_value = []

        with patch.object(sync_mod, "RouterClient", return_value=mock_client), \
             patch.object(sync_mod, "wait_for_instance", return_value=True):
            sync_mod.configure_slave(slave, defaults)

        mock_client.create_proxy_pool.assert_called_once()
        _, kwargs = mock_client.create_proxy_pool.call_args
        assert kwargs["proxy_url"] == "socks5://sbx-tor:9050"
        assert kwargs["pool_type"] == "socks5"

    def test_does_not_fail_when_proxy_api_unavailable(self):
        from server_pool import sync as sync_mod

        slave = self._make_slave()
        defaults = {"models": [], "combos": []}

        mock_client = MagicMock()
        mock_client.get_proxy_pools.side_effect = RuntimeError("api down")
        mock_client.get_api_keys.return_value = []
        mock_client.create_api_key.return_value = {"key": "sk-test"}
        mock_client.get_combos.return_value = []
        mock_client.get_custom_models.return_value = []

        with patch.object(sync_mod, "RouterClient", return_value=mock_client), \
             patch.object(sync_mod, "wait_for_instance", return_value=True):
            api_key = sync_mod.configure_slave(slave, defaults)

        # still returns api key, proxy failure is non-fatal
        assert api_key == "sk-test"
        mock_client.create_proxy_pool.assert_not_called()


# ---------------------------------------------------------------------------
# Integration: needs docker + sbx-tor + 9router up
# Run with: pytest --run-integration
# ---------------------------------------------------------------------------

def _should_run_integration(request):
    return request.config.getoption("--run-integration", default=False)


@pytest.mark.integration
class TestTorIntegration:
    """Requires: make setup (tor + 9router-pool + ai-memory) running."""

    def test_tor_socks_reachable_via_docker_network(self, request):
        if not _should_run_integration(request):
            pytest.skip("pass --run-integration to run")
        import subprocess
        # From inside sbx-net, sbx-tor:9050 must be reachable; fallback to host 127.0.0.1:9050
        for target in ["sbx-tor:9050", "127.0.0.1:9050"]:
            host, port = target.split(":")
            # try via a ephemeral container on sbx-net
            r = subprocess.run(
                ["docker", "run", "--rm", "--network", "sbx-net", "curlimages/curl:8.5.0",
                 "-s", "--socks5-hostname", target, "https://check.torproject.org/api/ip", "-m", "15"],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0 and "IsTor" in r.stdout:
                assert True
                return
        pytest.skip("Tor SOCKS not reachable (is sbx-tor running?)")

    def test_slaves_have_tor_proxy_pool(self, request):
        if not _should_run_integration(request):
            pytest.skip("pass --run-integration to run")
        import requests

        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        for slave in data["slaves"]:
            host = slave["host"]
            pwd = slave.get("password", "123456")
            s = requests.Session()
            r = s.post(f"http://{host}/api/auth/login", json={"password": pwd}, timeout=10)
            assert r.status_code == 200, f"login failed for {slave['name']}"
            r = s.get(f"http://{host}/api/proxy-pools", timeout=10)
            assert r.status_code == 200
            body = r.json()
            pools = body.get("pools", body.get("proxyPools", body.get("data", [])))
            # must have tor-proxy
            assert any(
                p.get("name") == "tor-proxy" and "sbx-tor:9050" in p.get("proxyUrl", "")
                for p in pools
            ), f"{slave['name']} missing tor-proxy pool, got: {pools}"

    def test_master_has_no_tor_proxy(self, request):
        if not _should_run_integration(request):
            pytest.skip("pass --run-integration to run")
        import requests

        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        master = data["master"]
        s = requests.Session()
        r = s.post(f"http://{master['host']}/api/auth/login", json={"password": master["password"]}, timeout=10)
        assert r.status_code == 200
        r = s.get(f"http://{master['host']}/api/proxy-pools", timeout=10)
        if r.status_code == 200:
            body = r.json()
            pools = body.get("pools", body.get("proxyPools", body.get("data", [])))
            assert not any(p.get("name") == "tor-proxy" for p in pools), \
                f"master must NOT have tor-proxy, got: {pools}"
