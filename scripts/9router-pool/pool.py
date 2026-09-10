#!/usr/bin/env python3
"""
9Router Pool Manager (CRUD API version)

Estrutura:

    config.json
        ├── master
        ├── defaults
        │    ├── models
        │    ├── combos
        │    └── publish
        │
        └── slaves
             ├── rs001
             ├── rs002
             └── rs003

Operações:

    python pool.py list
    python pool.py test

    python pool.py sync
    python pool.py sync --dry-run

    python pool.py slave add rs004 localhost:20132
    python pool.py slave delete rs004

    python pool.py backup
    python pool.py backup --output master-backup.json

Arquitetura:

    Master
        ├── providerNodes (anthropic-compatible) ← apontam para slaves
        ├── providerConnections (usam node ID como provider type)
        ├── customModels (modelos customizados por node)
        ├── combos (modelos prefixados: rs001/modelo)
        └── settings (round-robin por provider)

    Slaves
        ├── providerConnections (upstream: kilocode, openrouter, etc.)
        ├── proxyPools (Tor)
        ├── combos (modelos do defaults)
        └── customModels (modelos upstream)

Versão: 2.1 (CRUD API — arquitetura providerNodes)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


# ============================================================================
# CONFIG
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"

DEFAULT_TIMEOUT = 15


# ============================================================================
# CORES
# ============================================================================

class C:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    CYAN = "\033[0;36m"
    BLUE = "\033[0;34m"
    BOLD = "\033[1m"
    END = "\033[0m"


def info(text: str) -> None:
    print(f"{C.CYAN}[*]{C.END} {text}")


def success(text: str) -> None:
    print(f"{C.GREEN}[+]{C.END} {text}")


def warning(text: str) -> None:
    print(f"{C.YELLOW}[!]{C.END} {text}")


def error(text: str) -> None:
    print(f"{C.RED}[-]{C.END} {text}", file=sys.stderr)


def title(text: str) -> None:
    print()
    print(f"{C.BOLD}{C.BLUE}{text}{C.END}")
    print("─" * 70)


# ============================================================================
# CONFIGURATION
# ============================================================================

def load_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        error(f"Arquivo não encontrado: {CONFIG_FILE}")
        sys.exit(1)

    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as exc:
        error(f"config.json inválido: {exc}")
        sys.exit(1)

    validate_config(config)
    return config


def save_config(config: dict[str, Any]) -> None:
    temp_file = CONFIG_FILE.with_suffix(".tmp")

    with temp_file.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.write("\n")

    temp_file.replace(CONFIG_FILE)


def validate_config(config: dict[str, Any]) -> None:
    if "master" not in config:
        raise RuntimeError("config.json precisa possuir 'master'")

    if "defaults" not in config:
        raise RuntimeError("config.json precisa possuir 'defaults'")

    if "slaves" not in config:
        raise RuntimeError("config.json precisa possuir 'slaves'")

    defaults = config["defaults"]

    if "models" not in defaults:
        defaults["models"] = []

    if "combos" not in defaults:
        defaults["combos"] = []

    if "publish" not in defaults:
        defaults["publish"] = []

    if not isinstance(config["slaves"], list):
        raise RuntimeError("'slaves' precisa ser uma lista")


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Instance:
    name: str
    host: str
    password: str
    docker_host: str = ""

    @property
    def base_url(self) -> str:
        return f"http://{self.host}"

    @property
    def docker_url(self) -> str:
        return f"http://{self.docker_host}" if self.docker_host else self.base_url


def master_instance(config: dict[str, Any]) -> Instance:
    data = config["master"]

    return Instance(
        name=data["name"],
        host=data["host"],
        password=data["password"],
    )


def slave_instances(config: dict[str, Any]) -> list[Instance]:
    result = []

    defaults = config["defaults"]

    for item in config["slaves"]:
        result.append(
            Instance(
                name=item["name"],
                host=item["host"],
                docker_host=item.get("docker_host", ""),
                password=item.get(
                    "password",
                    defaults.get("password", "123456")
                ),
            )
        )

    return result


# ============================================================================
# HTTP CLIENT
# ============================================================================

class RouterClient:
    def __init__(
        self,
        instance: Instance,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.instance = instance
        self.timeout = timeout
        self.session = requests.Session()
        self.logged_in = False

    # ------------------------------------------------------------------------
    # LOGIN
    # ------------------------------------------------------------------------

    def login(self) -> bool:
        try:
            response = self.session.post(
                f"{self.instance.base_url}/api/auth/login",
                json={
                    "password": self.instance.password
                },
                timeout=self.timeout,
            )

            response.raise_for_status()

            data = response.json()

        except requests.RequestException as exc:
            warning(
                f"{self.instance.name}: erro de conexão/login: {exc}"
            )
            return False

        except ValueError:
            warning(
                f"{self.instance.name}: resposta inválida no login"
            )
            return False

        self.logged_in = bool(data.get("success"))

        return self.logged_in

    # ------------------------------------------------------------------------
    # REQUIRE LOGIN
    # ------------------------------------------------------------------------

    def require_login(self) -> None:
        if not self.logged_in:
            if not self.login():
                raise RuntimeError(
                    f"login falhou: {self.instance.name}"
                )

    # ------------------------------------------------------------------------
    # PROVIDER NODES
    # ------------------------------------------------------------------------

    def get_provider_nodes(self) -> list[dict[str, Any]]:
        self.require_login()

        response = self.session.get(
            f"{self.instance.base_url}/api/provider-nodes",
            timeout=self.timeout,
        )

        response.raise_for_status()

        data = response.json()

        return data.get("nodes", [])

    def create_provider_node(
        self,
        name: str,
        prefix: str,
        base_url: str,
        node_type: str = "anthropic-compatible",
    ) -> dict[str, Any]:
        self.require_login()

        response = self.session.post(
            f"{self.instance.base_url}/api/provider-nodes",
            json={
                "name": name,
                "type": node_type,
                "prefix": prefix,
                "baseUrl": base_url,
            },
            timeout=self.timeout,
        )

        response.raise_for_status()

        data = response.json()

        return data.get("node", {})

    def delete_provider_node(self, node_id: str) -> bool:
        self.require_login()

        response = self.session.delete(
            f"{self.instance.base_url}/api/provider-nodes/{node_id}",
            timeout=self.timeout,
        )

        response.raise_for_status()

        return True

    # ------------------------------------------------------------------------
    # PROVIDERS (CONNECTIONS)
    # ------------------------------------------------------------------------

    def get_providers(self) -> list[dict[str, Any]]:
        self.require_login()

        response = self.session.get(
            f"{self.instance.base_url}/api/providers",
            timeout=self.timeout,
        )

        response.raise_for_status()

        data = response.json()

        return data.get("connections", [])

    def create_provider(
        self,
        provider_type: str,
        name: str,
        api_key: str,
        base_url: str | None = None,
        priority: int = 1,
        default_model: str | None = None,
        provider_specific_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.require_login()

        payload: dict[str, Any] = {
            "provider": provider_type,
            "name": name,
            "apiKey": api_key,
            "priority": priority,
        }

        if default_model:
            payload["defaultModel"] = default_model

        if provider_specific_data:
            payload["providerSpecificData"] = provider_specific_data

        response = self.session.post(
            f"{self.instance.base_url}/api/providers",
            json=payload,
            timeout=self.timeout,
        )

        response.raise_for_status()

        data = response.json()

        connection = data.get("connection", {})
        conn_id = connection.get("id")

        if base_url and conn_id:
            self.update_provider(
                conn_id,
                provider_specific_data={"baseUrl": base_url},
            )

        return connection

    def update_provider(
        self,
        provider_id: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.require_login()

        response = self.session.put(
            f"{self.instance.base_url}/api/providers/{provider_id}",
            json=kwargs,
            timeout=self.timeout,
        )

        response.raise_for_status()

        data = response.json()

        return data.get("connection", {})

    def delete_provider(self, provider_id: str) -> bool:
        self.require_login()

        response = self.session.delete(
            f"{self.instance.base_url}/api/providers/{provider_id}",
            timeout=self.timeout,
        )

        response.raise_for_status()

        return True

    def test_provider(self, provider_id: str) -> dict[str, Any]:
        self.require_login()

        response = self.session.post(
            f"{self.instance.base_url}/api/providers/{provider_id}/test",
            json={},
            timeout=self.timeout,
        )

        response.raise_for_status()

        return response.json()

    # ------------------------------------------------------------------------
    # CUSTOM MODELS
    # ------------------------------------------------------------------------

    def get_custom_models(self) -> list[dict[str, Any]]:
        self.require_login()

        response = self.session.get(
            f"{self.instance.base_url}/api/models/custom",
            timeout=self.timeout,
        )

        response.raise_for_status()

        data = response.json()

        return data.get("models", [])

    def add_custom_model(
        self,
        provider_alias: str,
        model_id: str,
        model_name: str,
        model_type: str = "llm",
    ) -> bool:
        self.require_login()

        response = self.session.post(
            f"{self.instance.base_url}/api/models/custom",
            json={
                "providerAlias": provider_alias,
                "id": model_id,
                "type": model_type,
                "name": model_name,
            },
            timeout=self.timeout,
        )

        response.raise_for_status()

        return True

    def delete_custom_model(
        self,
        provider_alias: str,
        model_id: str,
    ) -> bool:
        self.require_login()

        response = self.session.delete(
            f"{self.instance.base_url}/api/models/custom",
            params={
                "providerAlias": provider_alias,
                "id": model_id,
            },
            timeout=self.timeout,
        )

        response.raise_for_status()

        return True

    # ------------------------------------------------------------------------
    # API KEYS
    # ------------------------------------------------------------------------

    def get_api_keys(self) -> list[dict[str, Any]]:
        self.require_login()

        response = self.session.get(
            f"{self.instance.base_url}/api/keys",
            timeout=self.timeout,
        )

        response.raise_for_status()

        data = response.json()

        return data.get("keys", [])

    def create_api_key(
        self,
        name: str,
    ) -> dict[str, Any]:
        self.require_login()

        response = self.session.post(
            f"{self.instance.base_url}/api/keys",
            json={
                "name": name,
            },
            timeout=self.timeout,
        )

        response.raise_for_status()

        return response.json()

    def delete_api_key(self, key_id: str) -> bool:
        self.require_login()

        response = self.session.delete(
            f"{self.instance.base_url}/api/keys/{key_id}",
            timeout=self.timeout,
        )

        response.raise_for_status()

        return True

    # ------------------------------------------------------------------------
    # COMBOS
    # ------------------------------------------------------------------------

    def get_combos(self) -> list[dict[str, Any]]:
        self.require_login()

        response = self.session.get(
            f"{self.instance.base_url}/api/combos",
            timeout=self.timeout,
        )

        response.raise_for_status()

        data = response.json()

        return data.get("combos", [])

    def create_combo(
        self,
        name: str,
        models: list[str],
    ) -> dict[str, Any]:
        self.require_login()

        response = self.session.post(
            f"{self.instance.base_url}/api/combos",
            json={
                "name": name,
                "models": models,
            },
            timeout=self.timeout,
        )

        response.raise_for_status()

        return response.json()

    def delete_combo(self, combo_id: str) -> bool:
        self.require_login()

        response = self.session.delete(
            f"{self.instance.base_url}/api/combos/{combo_id}",
            timeout=self.timeout,
        )

        response.raise_for_status()

        return True

    # ------------------------------------------------------------------------
    # SETTINGS
    # ------------------------------------------------------------------------

    def get_settings(self) -> dict[str, Any]:
        self.require_login()

        response = self.session.get(
            f"{self.instance.base_url}/api/settings",
            timeout=self.timeout,
        )

        response.raise_for_status()

        return response.json()

    def update_settings(
        self,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.require_login()

        response = self.session.patch(
            f"{self.instance.base_url}/api/settings",
            json=kwargs,
            timeout=self.timeout,
        )

        response.raise_for_status()

        if not response.content:
            return {}

        return response.json()

    # ------------------------------------------------------------------------
    # MODELS
    # ------------------------------------------------------------------------

    def get_models(self) -> list[dict[str, Any]]:
        self.require_login()

        response = self.session.get(
            f"{self.instance.base_url}/api/models",
            timeout=self.timeout,
        )

        response.raise_for_status()

        data = response.json()

        return data.get("models", [])

    # ------------------------------------------------------------------------
    # PROXY POOLS
    # ------------------------------------------------------------------------

    def get_proxy_pools(self) -> list[dict[str, Any]]:
        self.require_login()

        response = self.session.get(
            f"{self.instance.base_url}/api/proxy-pools",
            timeout=self.timeout,
        )

        response.raise_for_status()

        data = response.json()

        return data.get("pools", data.get("proxyPools", []))

    def create_proxy_pool(
        self,
        name: str,
        proxy_url: str,
        pool_type: str = "http",
        no_proxy: str = "localhost,127.0.0.1",
    ) -> dict[str, Any]:
        self.require_login()

        response = self.session.post(
            f"{self.instance.base_url}/api/proxy-pools",
            json={
                "name": name,
                "proxyUrl": proxy_url,
                "type": pool_type,
                "noProxy": no_proxy,
            },
            timeout=self.timeout,
        )

        response.raise_for_status()

        return response.json()

    # ------------------------------------------------------------------------
    # BACKUP (export full state)
    # ------------------------------------------------------------------------

    def get_backup(self) -> dict[str, Any]:
        self.require_login()

        return {
            "settings": self.get_settings(),
            "providerConnections": self.get_providers(),
            "providerNodes": self.get_provider_nodes(),
            "proxyPools": self.get_proxy_pools(),
            "apiKeys": [],
            "combos": self.get_combos(),
            "modelAliases": {},
            "customModels": self.get_custom_models(),
            "mitmAlias": {},
            "pricing": {},
        }


# ============================================================================
# HEALTH CHECK HELPER
# ============================================================================

def wait_for_instance(
    instance: Instance,
    max_attempts: int = 20,
    delay: int = 3,
) -> bool:
    """Wait for an instance HTTP API to be ready."""
    info(f"Aguardando {instance.name} ({instance.base_url})...")
    client = RouterClient(instance)
    for attempt in range(max_attempts):
        try:
            response = client.session.post(
                f"{instance.base_url}/api/auth/login",
                json={"password": instance.password},
                timeout=5,
            )
            if response.status_code == 200:
                success(f"{instance.name}: API pronta")
                return True
        except requests.RequestException:
            pass
        info(f"{instance.name}: ainda inicializando... ({attempt + 1}/{max_attempts})")
        time.sleep(delay)
    warning(f"{instance.name}: pode não estar totalmente pronto")
    return False


# ============================================================================
# SLAVE CONFIGURATION
# ============================================================================

def configure_slave(
    slave: Instance,
    defaults: dict[str, Any],
    dry_run: bool = False,
) -> str | None:
    """Configure slave and return API key for master to use."""

    title(
        f"SLAVE {slave.name} → {slave.host}"
    )

    models = defaults.get("models", [])
    combos = defaults.get("combos", [])

    info(
        f"Models configurados: {len(models)}"
    )

    info(
        f"Combos configurados: {len(combos)}"
    )

    if dry_run:

        print()

        for model in models:
            print(f"  model: {model}")

        for combo in combos:
            print(
                f"  combo: {combo['name']} "
                f"({len(combo.get('models', []))} models)"
            )

        return None

    client = RouterClient(slave)

    # Health check antes do login
    wait_for_instance(slave, max_attempts=15, delay=3)

    if not client.login():
        error(
            f"{slave.name}: login falhou"
        )
        return None

    success(
        f"{slave.name}: login OK"
    )

    # ------------------------------------------------------------------------
    # REMOVER API KEY EXISTENTE "pool-key"
    # ------------------------------------------------------------------------

    existing_keys = client.get_api_keys()

    for key in existing_keys:
        if key.get("name") == "pool-key":
            try:
                client.delete_api_key(key["id"])
                info(
                    f"{slave.name}: API key 'pool-key' removida"
                )
            except Exception as exc:
                warning(
                    f"{slave.name}: erro ao remover API key: {exc}"
                )

    # ------------------------------------------------------------------------
    # CRIAR NOVA API KEY "pool-key"
    # ------------------------------------------------------------------------

    api_key = ""

    try:
        key_data = client.create_api_key(name="pool-key")
        api_key = key_data.get("key", "")
        success(
            f"{slave.name}: API key criada"
        )
    except Exception as exc:
        error(
            f"{slave.name}: erro ao criar API key: {exc}"
        )

    # ------------------------------------------------------------------------
    # REMOVER COMBOS EXISTENTES
    # ------------------------------------------------------------------------

    existing_combos = client.get_combos()

    for combo in existing_combos:
        combo_id = combo.get("id")
        combo_name = combo.get("name")

        if combo_id:
            try:
                client.delete_combo(combo_id)
                info(
                    f"{slave.name}: combo '{combo_name}' removido"
                )
            except Exception as exc:
                warning(
                    f"{slave.name}: erro ao remover combo '{combo_name}': {exc}"
                )

    # ------------------------------------------------------------------------
    # HEALTH CHECK ANTES DE CRIAR COMBOS
    # ------------------------------------------------------------------------

    info(f"{slave.name}: verificando saúde...")

    try:
        r = client.session.get(
            f"{client.instance.base_url}/api/combos",
            timeout=client.timeout,
        )
        r.raise_for_status()
        success(f"{slave.name}: saudável")
    except Exception as exc:
        error(f"{slave.name}: não saudável: {exc}")
        return None

    # ------------------------------------------------------------------------
    # CRIAR COMBOS DO DEFAULTS
    # ------------------------------------------------------------------------

    for combo_config in combos:

        combo_name = combo_config["name"]
        combo_models = combo_config.get(
            "models",
            [],
        )

        try:
            client.create_combo(
                name=combo_name,
                models=combo_models,
            )

            success(
                f"{slave.name}: combo '{combo_name}' criado"
            )

        except Exception as exc:
            error(
                f"{slave.name}: erro ao criar combo '{combo_name}': {exc}"
            )

    # ------------------------------------------------------------------------
    # VERIFICAR COMBOS CRIADOS
    # ------------------------------------------------------------------------

    combos_criados = client.get_combos()
    nomes_esperados = {c["name"] for c in combos}
    nomes_criados = {c["name"] for c in combos_criados}

    if nomes_esperados == nomes_criados:
        success(
            f"{slave.name}: todos os {len(nomes_criados)} combos verificados"
        )
    else:
        faltando = nomes_esperados - nomes_criados
        if faltando:
            error(
                f"{slave.name}: combos faltando: {faltando}"
            )

    # ------------------------------------------------------------------------
    # REMOVER CUSTOM MODELS EXISTENTES (não criar novos no slave)
    # ------------------------------------------------------------------------

    existing_custom = client.get_custom_models()

    for cm in existing_custom:
        pa = cm.get("providerAlias", "")
        mid = cm.get("id", "")

        # Só remover modelos que NÃO estão em nenhum combo
        in_any_combo = any(
            mid in combo.get("models", [])
            for combo in combos
        )

        if not in_any_combo and pa in ("oc", "kc"):
            try:
                client.delete_custom_model(pa, mid)
                info(
                    f"{slave.name}: custom model '{pa}/{mid}' removido"
                )
            except Exception:
                pass

    success(
        f"{slave.name}: configuração aplicada"
    )

    return api_key


# ============================================================================
# MASTER SYNC
# ============================================================================

def sync_master(
    config: dict[str, Any],
    slave_api_keys: dict[str, str],
    dry_run: bool = False,
) -> None:

    master = master_instance(config)

    defaults = config["defaults"]
    slaves = slave_instances(config)

    title(f"MASTER {master.host}")

    # Health check antes de começar
    wait_for_instance(master, max_attempts=20, delay=3)

    master_client = RouterClient(master)

    if not master_client.login():
        error("Não foi possível fazer login no master")
        return

    success("Master: login OK")

    # ------------------------------------------------------------------------
    # REMOVER TODOS OS PROVIDER NODES EXISTENTES
    # ------------------------------------------------------------------------

    existing_nodes = master_client.get_provider_nodes()

    for node in existing_nodes:
        node_id = node.get("id")
        node_name = node.get("name")

        if dry_run:
            info(f"[dry-run] removeria provider node '{node_name}'")
        else:
            try:
                master_client.delete_provider_node(node_id)
                info(f"master: provider node '{node_name}' removido")
            except Exception as exc:
                warning(f"master: erro ao remover provider node '{node_name}': {exc}")

    # ------------------------------------------------------------------------
    # REMOVER TODAS AS PROVIDER CONNECTIONS EXISTENTES
    # ------------------------------------------------------------------------

    existing_providers = master_client.get_providers()

    for provider in existing_providers:
        provider_id = provider.get("id")
        provider_name = provider.get("name")

        if dry_run:
            info(f"[dry-run] removeria provider connection '{provider_name}'")
        else:
            try:
                master_client.delete_provider(provider_id)
                info(f"master: provider connection '{provider_name}' removido")
            except Exception as exc:
                warning(f"master: erro ao remover provider connection '{provider_name}': {exc}")

    # ------------------------------------------------------------------------
    # REMOVER TODOS OS CUSTOM MODELS
    # ------------------------------------------------------------------------

    existing_custom = master_client.get_custom_models()

    for cm in existing_custom:
        pa = cm.get("providerAlias", "")
        mid = cm.get("id", "")

        if dry_run:
            info(f"[dry-run] removeria custom model '{pa}/{mid}'")
        else:
            try:
                master_client.delete_custom_model(pa, mid)
                info(f"master: custom model '{pa}/{mid}' removido")
            except Exception as exc:
                warning(f"master: erro ao remover custom model '{pa}/{mid}': {exc}")

    # ------------------------------------------------------------------------
    # REMOVER COMBOS DOS SLAVES
    # ------------------------------------------------------------------------

    existing_combos = master_client.get_combos()

    for combo in existing_combos:
        combo_id = combo.get("id")
        combo_name = combo.get("name")

        if combo_name in defaults.get("publish", []):
            if dry_run:
                info(
                    f"[dry-run] removeria combo '{combo_name}'"
                )
            else:
                try:
                    master_client.delete_combo(combo_id)
                    info(
                        f"master: combo '{combo_name}' removido"
                    )
                except Exception as exc:
                    warning(
                        f"master: erro ao remover combo '{combo_name}': {exc}"
                    )

    if dry_run:
        return

    # ------------------------------------------------------------------------
    # 1. CRIAR PROVIDER NODES PARA CADA SLAVE
    # ------------------------------------------------------------------------

    node_ids: dict[str, str] = {}

    for slave in slaves:
        if slave.name not in slave_api_keys:
            warning(
                f"{slave.name}: não configurado, pulando publicação"
            )
            continue

        try:
            node = master_client.create_provider_node(
                name=slave.name,
                prefix=slave.name,
                base_url=f"{slave.docker_url}/v1",
                node_type="anthropic-compatible",
            )

            node_id = node.get("id", "")
            node_ids[slave.name] = node_id

            success(
                f"master: provider node '{slave.name}' criado "
                f"(→ {slave.docker_url}/v1, id={node_id})"
            )

        except Exception as exc:
            error(
                f"master: erro ao criar provider node '{slave.name}': {exc}"
            )

    # ------------------------------------------------------------------------
    # 2. CRIAR PROVIDER CONNECTIONS PARA CADA SLAVE
    # ------------------------------------------------------------------------

    for slave in slaves:
        if slave.name not in slave_api_keys:
            continue

        node_id = node_ids.get(slave.name, "")

        if not node_id:
            warning(
                f"{slave.name}: node ID não disponível"
            )
            continue

        try:
            api_key = slave_api_keys.get(slave.name, slave.password)

            master_client.create_provider(
                provider_type=node_id,
                name=slave.name,
                api_key=api_key,
                base_url=f"{slave.docker_url}/v1",
                priority=1,
                default_model="claude-sonnet-5",
                provider_specific_data={
                    "prefix": slave.name,
                    "baseUrl": f"{slave.docker_url}/v1",
                    "nodeName": slave.name,
                },
            )

            success(
                f"master: provider connection '{slave.name}' criado "
                f"(→ {slave.docker_url}/v1)"
            )

        except Exception as exc:
            error(
                f"master: erro ao criar provider connection '{slave.name}': {exc}"
            )

    # ------------------------------------------------------------------------
    # VERIFICAR HEALTH DOS PROVIDERS
    # ------------------------------------------------------------------------

    info("Aguardando providers inicializarem...")
    time.sleep(30)

    title("HEALTH CHECK")

    providers = master_client.get_providers()

    for provider in providers:
        provider_id = provider.get("id")
        provider_name = provider.get("name")

        if not provider_id:
            continue

        for attempt in range(3):
            try:
                time.sleep(5)
                # Usar timeout maior para health check (90s)
                response = master_client.session.post(
                    f"{master_client.instance.base_url}/api/providers/{provider_id}/test",
                    json={},
                    timeout=90,
                )
                response.raise_for_status()
                result = response.json()
                valid = result.get("valid", False)
                err = result.get("error")

                if valid:
                    success(
                        f"master: provider '{provider_name}' → SAUDÁVEL"
                    )
                else:
                    warning(
                        f"master: provider '{provider_name}' → FALHOU: {err}"
                    )
                break

            except Exception as exc:
                if attempt < 2:
                    warning(f"master: retry {attempt + 1}/3 health check para '{provider_name}'")
                    time.sleep(5)
                    try:
                        master_client.login()
                    except Exception:
                        pass
                else:
                    error(
                        f"master: provider '{provider_name}' → ERRO: {exc}"
                    )

    # ------------------------------------------------------------------------
    # 3. CRIAR CUSTOM MODELS PARA CADA NODE
    # ------------------------------------------------------------------------

    for slave in slaves:
        if slave.name not in node_ids:
            continue

        node_id = node_ids[slave.name]

        # Modelos dos defaults (com retry)
        for model in defaults.get("models", []):
            parts = model.split("/", 1)
            if len(parts) == 2:
                alias, model_id = parts
            else:
                alias = "oc"
                model_id = model

            for attempt in range(3):
                try:
                    master_client.add_custom_model(
                        provider_alias=node_id,
                        model_id=model_id,
                        model_name=model_id,
                    )
                    info(
                        f"master: custom model '{node_id}/{model_id}' adicionado"
                    )
                    break
                except Exception as exc:
                    if attempt < 2:
                        warning(f"master: retry {attempt + 1}/3 para custom model '{node_id}/{model_id}'")
                        time.sleep(5)
                        # Re-login after connection error
                        try:
                            master_client.login()
                        except Exception:
                            pass
                    else:
                        warning(
                            f"master: erro ao adicionar custom model '{node_id}/{model_id}': {exc}"
                        )

        # Modelos dos combos (com retry)
        for combo_config in defaults.get("combos", []):
            for model in combo_config.get("models", []):
                parts = model.split("/", 1)
                if len(parts) == 2:
                    alias, model_id = parts
                else:
                    alias = "oc"
                    model_id = model

                for attempt in range(3):
                    try:
                        master_client.add_custom_model(
                            provider_alias=node_id,
                            model_id=model_id,
                            model_name=model_id,
                        )
                        break
                    except Exception:
                        if attempt < 2:
                            time.sleep(5)
                            try:
                                master_client.login()
                            except Exception:
                                pass

    # ------------------------------------------------------------------------
    # 4. CRIAR COMBOS NO MASTER
    #
    # Cada combo contém:
    #   - Modelos originais do combo (sem prefixo)
    #   - defaults.models prefixados com cada slave (excluindo nomes de outros combos)
    # ------------------------------------------------------------------------

    publish = defaults.get("publish", [])
    all_models = defaults.get("models", [])

    # Nomes de todos os combos publicados (para excluir de prefixed models)
    other_combo_names = set()
    for c in defaults.get("combos", []):
        if c["name"] in publish:
            other_combo_names.add(c["name"])

    for combo_config in defaults.get("combos", []):
        combo_name = combo_config["name"]
        combo_models = combo_config.get("models", [])

        if combo_name not in publish:
            continue

        final_models = []

        # 1. Modelos originais do combo (sem prefixo)
        for model in combo_models:
            final_models.append(model)

        # 2. defaults.models prefixados com cada slave
        #    Exclui modelos cujo nome é de OUTRO combo (ex: claude-sonnet-5 no combo claude-opus-5)
        for slave in slaves:
            if slave.name not in node_ids:
                continue

            for model in all_models:
                if model in other_combo_names and model != combo_name:
                    continue
                prefixed = f"{slave.name}/{model}"
                final_models.append(prefixed)

        if not final_models:
            warning(
                f"master: combo '{combo_name}' sem modelos para publicar"
            )
            continue

        for attempt in range(3):
            try:
                master_client.create_combo(
                    name=combo_name,
                    models=final_models,
                )

                success(
                    f"master: combo '{combo_name}' criado "
                    f"({len(final_models)} modelos)"
                )
                break

            except Exception as exc:
                if attempt < 2:
                    warning(f"master: retry {attempt + 1}/3 para combo '{combo_name}'")
                    time.sleep(5)
                    try:
                        master_client.login()
                    except Exception:
                        pass
                else:
                    error(
                        f"master: erro ao criar combo '{combo_name}': {exc}"
                    )

    # ------------------------------------------------------------------------
    # 5. CONFIGURAR ROUND-ROBIN NO MASTER
    # ------------------------------------------------------------------------

    settings = master_client.get_settings()

    provider_strategies = settings.get("providerStrategies", {})

    for slave in slaves:
        if slave.name in node_ids:
            node_id = node_ids[slave.name]
            provider_strategies[node_id] = {
                "fallbackStrategy": "round-robin",
                "stickyRoundRobinLimit": 1,
            }

    try:
        master_client.update_settings(
            providerStrategies=provider_strategies,
            stickyRoundRobinLimit=3,
            comboStrategy="round-robin",
            comboStickyRoundRobinLimit=3,
        )

        success(
            "master: round-robin configurado"
        )

    except Exception as exc:
        warning(
            f"master: erro ao configurar round-robin: {exc}"
        )


# ============================================================================
# SYNC POOL
# ============================================================================

def sync_pool(
    config: dict[str, Any],
    dry_run: bool = False,
) -> None:

    defaults = config["defaults"]
    slaves = slave_instances(config)
    master = master_instance(config)

    title("9ROUTER POOL SYNC")

    print(
        f"Slaves: {len(slaves)}"
    )

    print(
        f"Models: {len(defaults.get('models', []))}"
    )

    print(
        f"Combos: {len(defaults.get('combos', []))}"
    )

    print(
        f"Publish: {defaults.get('publish', [])}"
    )

    if dry_run:

        title("DRY RUN")

        for slave in slaves:

            print(
                f"\n{C.BOLD}{slave.name}{C.END} "
                f"→ {slave.host}"
            )

            print(
                "  Models:"
            )

            for model in defaults.get(
                "models",
                [],
            ):
                print(
                    f"    - {model}"
                )

            print(
                "  Combos:"
            )

            for combo in defaults.get(
                "combos",
                [],
            ):
                print(
                    f"    - {combo['name']}"
                )

                for model in combo.get(
                    "models",
                    [],
                ):
                    print(
                        f"        {model}"
                    )

            print(
                "  Publish:"
            )

            for combo_name in defaults.get(
                "publish",
                [],
            ):
                print(
                    f"    - {combo_name}"
                )

        return

    # ------------------------------------------------------------------------
    # 1. CONFIGURAR TODOS OS SLAVES
    # ------------------------------------------------------------------------

    slave_api_keys: dict[
        str,
        str
    ] = {}

    for slave in slaves:

        try:

            api_key = configure_slave(
                slave,
                defaults,
                dry_run=False,
            )

            if api_key:
                slave_api_keys[
                    slave.name
                ] = api_key

        except Exception as exc:

            error(
                f"{slave.name}: {exc}"
            )

    # ------------------------------------------------------------------------
    # 2. PUBLICAR NO MASTER
    # ------------------------------------------------------------------------

    sync_master(
        config,
        slave_api_keys,
        dry_run=False,
    )

    # ------------------------------------------------------------------------
    # EXPORTAR API KEY DO MASTER
    # ------------------------------------------------------------------------

    try:
        master_client = RouterClient(master)
        if master_client.login():
            keys = master_client.get_api_keys()
            
            # Se não tem API key, criar uma
            if not keys:
                info("Criando API key no master...")
                key_data = master_client.create_api_key(name="pool-key")
                if key_data:
                    keys = [key_data]
                    success("API key criada no master")
            
            if keys:
                default_key = keys[0].get("key", "")
                print()
                success("API Key do Master (use nos clientes):")
                info(f"  {default_key}")
                print()
                info("Exemplo OpenCode:")
                info(f'  apiKey: "{default_key}"')
                info(f'  baseUrl: "http://{master.host}/v1"')
            else:
                warning("Não foi possível criar API key no master")
        else:
            warning("Login no master falhou para exportar API key")
    except Exception as exc:
        warning(f"Erro ao exportar API key: {exc}")

    success(
        "\nSync concluído!"
    )


# ============================================================================
# LIST
# ============================================================================

def list_pool(config: dict[str, Any]) -> None:

    defaults = config["defaults"]
    slaves = slave_instances(config)
    master = master_instance(config)

    title("9ROUTER POOL")

    print(
        f"Master: {C.BOLD}{master.host}{C.END}"
    )

    print(
        f"Slaves: {len(slaves)}"
    )

    for slave in slaves:
        print(
            f"  - {slave.name} → {slave.host}"
        )

    print()

    models = defaults.get("models", [])
    combos = defaults.get("combos", [])
    publish = defaults.get("publish", [])

    print(
        f"Models: {len(models)}"
    )

    for model in models:
        print(f"  - {model}")

    print()

    print(
        f"Combos: {len(combos)}"
    )

    for combo in combos:
        print(
            f"  - {combo['name']} "
            f"({len(combo.get('models', []))} models)"
        )

        for model in combo.get("models", []):
            print(f"      {model}")

    print()

    print(
        f"Publish: {publish}"
    )


# ============================================================================
# TEST
# ============================================================================

def test_pool(config: dict[str, Any]) -> None:

    slaves = slave_instances(config)
    master = master_instance(config)

    title("9ROUTER POOL TEST")

    all_instances = [master] + slaves

    ok_count = 0

    for instance in all_instances:

        print(
            f"\n{C.BOLD}{instance.name}{C.END} → {instance.host}"
        )

        client = RouterClient(instance)

        if client.login():
            success("login OK")

            try:
                nodes = client.get_provider_nodes()
                info(f"provider nodes: {len(nodes)}")
            except Exception as exc:
                warning(f"provider nodes: {exc}")

            try:
                providers = client.get_providers()
                info(f"provider connections: {len(providers)}")

                # Health check for master providers
                if instance.name == master.name and providers:
                    print()
                    info("Aguardando providers inicializarem...")
                    time.sleep(10)
                    for provider in providers:
                        pid = provider.get("id")
                        pname = provider.get("name")
                        if pid:
                            try:
                                # Usar timeout maior (90s) para health check
                                response = client.session.post(
                                    f"{client.instance.base_url}/api/providers/{pid}/test",
                                    json={},
                                    timeout=90,
                                )
                                response.raise_for_status()
                                result = response.json()
                                valid = result.get("valid", False)
                                err = result.get("error")
                                if valid:
                                    success(f"  {pname} → SAUDÁVEL")
                                else:
                                    warning(f"  {pname} → FALHOU: {err}")
                            except Exception as exc:
                                error(f"  {pname} → ERRO: {exc}")

            except Exception as exc:
                warning(f"provider connections: {exc}")

            try:
                combos = client.get_combos()
                info(f"combos: {len(combos)}")
            except Exception as exc:
                warning(f"combos: {exc}")

            try:
                custom = client.get_custom_models()
                info(f"custom models: {len(custom)}")
            except Exception as exc:
                warning(f"custom models: {exc}")

            try:
                models = client.get_models()
                info(f"models: {len(models)}")
            except Exception as exc:
                warning(f"models: {exc}")

            ok_count += 1

        else:
            error("login falhou")

    print()

    if ok_count == len(all_instances):
        success(
            f"Todos os {ok_count} instâncias OK"
        )
    else:
        warning(
            f"{ok_count}/{len(all_instances)} instâncias OK"
        )


# ============================================================================
# DOCKER COMPOSE GENERATION
# ============================================================================

def generate_docker_compose(config: dict[str, Any], num_slaves: int) -> str:
    """Generate docker-compose.yaml with N slaves using named volumes."""
    master_port = 20128
    base_port = 20129

    slave_services = []
    volumes_def = []
    for i in range(1, num_slaves + 1):
        slave_num = f"{i:03d}"
        port = base_port + i - 1
        vol_name = f"9router-slave-{slave_num}-data"
        slave_services.append(f"""
  9router-slave-{slave_num}:
    <<: *service-slave
    image: decolua/9router:${{NINEROUTER_TAG:-latest}}
    container_name: sbx-9router-slave-{slave_num}
    pull_policy: missing
    ports:
      - "${{ROUTER_PORT_SLAVE_{slave_num}:-{port}}}:{port}"
    volumes:
      - {vol_name}:/app/data
    healthcheck:
      test: ["CMD", "wget", "-q", "-O", "/dev/null", "--timeout=5", "http://127.0.0.1:{port}/"]
      interval: 10s
      timeout: 10s
      retries: 10
      start_period: 30s
    environment:
      DATA_DIR: /app/data
      PORT: "${{ROUTER_PORT_SLAVE_{slave_num}:-{port}}}"
      HOSTNAME: 0.0.0.0
      ROLE: slave
      JWT_SECRET: "${{JWT_SECRET:-P4s5w0rd}}"
      MACHINE_ID_SALT: $(openssl rand -hex 32)
      INITIAL_PASSWORD: "${{INITIAL_PASSWORD:-123456}}"
      HTTP_PROXY: "http://tor:8118"
      HTTPS_PROXY: "http://tor:8118"
      ALL_PROXY: "socks5://tor:9050"
      NO_PROXY: "localhost,127.0.0.1,tor,9router-master"
    networks:
      - sbx-net""")
        volumes_def.append(f"  {vol_name}:")

    compose = f"""x-common: &common
  restart: unless-stopped
  stop_grace_period: 10s
  env_file: .env
  logging:
    driver: json-file
    options:
      max-size: "20m"
      max-file: "3"

x-service-master: &service-master
  <<: *common
  deploy:
    resources:
      limits:
        memory: 512M
        cpus: "1.0"
      reservations:
        memory: 256M
        cpus: "0.25"

x-service-slave: &service-slave
  <<: *common
  deploy:
    resources:
      limits:
        memory: 256M
        cpus: "0.5"
      reservations:
        memory: 128M
        cpus: "0.125"

services:
  tor:
    <<: *service-slave
    image: dockurr/tor
    container_name: sbx-tor
    pull_policy: missing
    ports:
      - "9050:9050"
      - "8118:8118"
    volumes:
      - ./torrc:/etc/tor/torrc:ro
      - 9router-tor-data:/var/lib/tor
    environment:
      PASSWORD: "${{TOR_PASSWORD:-password}}"
      CHECK: "${{TOR_CHECK:-false}}"
      DEBUG: "${{TOR_DEBUG:-false}}"
    networks:
      - sbx-net

  9router-master:
    <<: *service-master
    image: decolua/9router:${{NINEROUTER_TAG:-latest}}
    container_name: sbx-9router-master
    pull_policy: missing
    ports:
      - "${{ROUTER_PORT_MASTER:-{master_port}}}:{master_port}"
    volumes:
      - 9router-master-data:/app/data
    healthcheck:
      test: ["CMD", "wget", "-q", "-O", "/dev/null", "--timeout=5", "http://127.0.0.1:{master_port}/"]
      interval: 10s
      timeout: 10s
      retries: 10
      start_period: 30s
    environment:
      DATA_DIR: /app/data
      PORT: "${{ROUTER_PORT_MASTER:-{master_port}}}"
      MACHINE_ID_SALT: $(openssl rand -hex 32)
      HOSTNAME: 0.0.0.0
      ROLE: master
      JWT_SECRET: "${{JWT_SECRET:-P4s5w0rd}}"
      INITIAL_PASSWORD: "${{INITIAL_PASSWORD:-123456}}"
    networks:
      - sbx-net
{"".join(slave_services)}

volumes:
  9router-tor-data:
  9router-master-data:
{chr(10).join(volumes_def)}

networks:
  sbx-net:
    name: sbx-net
    driver: bridge
"""
    return compose


# ============================================================================
# ENV FILE GENERATION
# ============================================================================

def generate_env(num_slaves: int) -> str:
    """Generate .env file with port assignments."""
    base_port = 20129
    lines = [
        "# sbx — Providers Environment",
        "TZ=America/Sao_Paulo",
        "ROUTER_PORT_MASTER=20128",
    ]
    for i in range(1, num_slaves + 1):
        slave_num = f"{i:03d}"
        port = base_port + i - 1
        lines.append(f"ROUTER_PORT_SLAVE_{slave_num}={port}")
    lines.extend([
        "ROUTER_DEBUG=false",
        "",
        "JWT_SECRET=N7ZndMLMYqJu8QLRtY+dE1VynAdESAJfc7maXp+lHqY=",
        "INITIAL_PASSWORD=123456",
        "",
        "# Tor Proxy",
        "TOR_SOCKS_PORT=9050",
        "TOR_HTTP_PORT=8118",
        "TOR_PASSWORD=password",
        "TOR_CHECK=true",
        "TOR_DEBUG=false",
    ])
    return "\n".join(lines) + "\n"


# ============================================================================
# CONFIG UPDATE & DATA DIRECTORY CREATION
# ============================================================================

def update_config_for_scale(config: dict[str, Any], num_slaves: int) -> dict[str, Any]:
    """Update config.json with N slaves."""
    base_port = 20129
    password = config["defaults"].get("password", "123456")
    slaves = []
    for i in range(1, num_slaves + 1):
        slave_num = f"{i:03d}"
        port = base_port + i - 1
        slaves.append({
            "name": f"rs{slave_num}",
            "host": f"localhost:{port}",
            "docker_host": f"9router-slave-{slave_num}:{port}",
            "password": password,
        })
    config["slaves"] = slaves
    return config


def create_data_directories(num_slaves: int) -> None:
    """Create data directories for each slave."""
    base_dir = BASE_DIR / "data" / "9router" / "slave"

    for i in range(1, num_slaves + 1):
        slave_num = f"{i:03d}"
        slave_dir = base_dir / slave_num

        try:
            slave_dir.mkdir(parents=True, exist_ok=True)
            info(f"Diretório: {slave_dir}")
        except PermissionError:
            warning(f"Sem permissão para criar: {slave_dir}")
            info(f"Execute: sudo chown -R access:access {base_dir}")
        except Exception as exc:
            warning(f"Erro ao criar {slave_dir}: {exc}")


def remove_data_directories(from_slave: int, to_slave: int) -> None:
    """Remove data directories for slaves from_slave..to_slave."""
    import shutil
    base_dir = BASE_DIR / "data" / "9router" / "slave"

    for i in range(from_slave, to_slave + 1):
        slave_num = f"{i:03d}"
        slave_dir = base_dir / slave_num

        if not slave_dir.exists():
            continue

        try:
            shutil.rmtree(slave_dir)
            info(f"Diretório removido: {slave_dir}")
        except PermissionError:
            warning(f"Sem permissão para remover: {slave_dir}")
            info(f"Execute: sudo rm -rf {slave_dir}")
        except Exception as exc:
            warning(f"Erro ao remover {slave_dir}: {exc}")


def scale_pool(
    config: dict[str, Any],
    num_slaves: int,
    dry_run: bool = False,
    no_sync: bool = False,
) -> None:
    """Scale pool to N slaves (1-50)."""
    title(f"SCALE → {num_slaves} slaves")

    if num_slaves < 1:
        error("Número de slaves deve ser >= 1")
        return
    if num_slaves > 50:
        error("Número máximo de slaves: 50")
        return

    current_count = len(config["slaves"])

    # No-op
    if num_slaves == current_count:
        info(f"Pool já tem {num_slaves} slaves — nada a fazer")
        return

    is_scale_down = num_slaves < current_count

    if is_scale_down:
        info(f"Removendo {current_count - num_slaves} slaves...")
    else:
        info(f"Adicionando {num_slaves - current_count} slaves...")

    # 1. Generate docker-compose.yaml
    info("Gerando docker-compose.yaml...")
    compose_content = generate_docker_compose(config, num_slaves)
    if dry_run:
        info("[dry-run] escreveria docker-compose.yaml")
    else:
        compose_path = BASE_DIR / "docker-compose.yaml"
        with compose_path.open("w", encoding="utf-8") as f:
            f.write(compose_content)
        success(f"docker-compose.yaml atualizado ({num_slaves} slaves)")

    # 2. Generate .env
    info("Gerando .env...")
    env_content = generate_env(num_slaves)
    if dry_run:
        info("[dry-run] escreveria .env")
    else:
        env_path = BASE_DIR / ".env"
        with env_path.open("w", encoding="utf-8") as f:
            f.write(env_content)
        success(f".env atualizado ({num_slaves} slaves)")

    # 3. Update config.json
    info("Atualizando config.json...")
    config = update_config_for_scale(config, num_slaves)
    if dry_run:
        info("[dry-run] escreveria config.json")
    else:
        save_config(config)
        success(f"config.json atualizado ({num_slaves} slaves)")

    # 5. Run docker compose (com --remove-orphans para limpar containers antigos)
    if not dry_run:
        info("Executando docker compose up -d --remove-orphans...")
        result = subprocess.run(
            ["docker", "compose", "up", "-d", "--remove-orphans"],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            success("docker compose up -d --remove-orphans concluído")
        else:
            error(f"docker compose up -d --remove-orphans falhou:")
            if result.stdout:
                info(result.stdout.strip())
            if result.stderr:
                error(result.stderr.strip())
            return

    # 6. Remover volumes órfãos (escala para baixo)
    if is_scale_down and not dry_run:
        info("Removendo volumes órfãos...")
        for i in range(num_slaves + 1, current_count + 1):
            vol_name = f"9routerv2_9router-slave-{i:03d}-data"
            result = subprocess.run(
                ["docker", "volume", "rm", vol_name],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                info(f"volume '{vol_name}' removido")
            else:
                warning(f"volume '{vol_name}' não encontrado ou em uso")

    # 7. Sync to master (skip on scale-down — slaves removed, not added)
    if not no_sync and not dry_run and not is_scale_down:
        info("Aguardando containers ficarem healthy...")
        expected = num_slaves + 1  # slaves + master (tor não tem healthcheck)
        for attempt in range(30):
            time.sleep(3)
            check = subprocess.run(
                ["docker", "compose", "ps", "--format", "json"],
                cwd=BASE_DIR,
                capture_output=True,
                text=True,
            )
            if check.returncode == 0:
                healthy = 0
                for line in check.stdout.strip().split("\n"):
                    if not line:
                        continue
                    data = json.loads(line)
                    state = data.get("State", "")
                    health = data.get("Health", "")
                    if state == "running" and health == "healthy":
                        healthy += 1
                if healthy >= expected:
                    break
                info(f"Healthy: {healthy}/{expected}... ({attempt + 1}/30)")
        else:
            warning("Containers podem não estar totalmente prontos")
        info("Sincronizando com master...")
        sync_pool(config, dry_run=False)

    print()
    if is_scale_down:
        success(f"Pool reduzido para {num_slaves} slaves")
    else:
        success(f"Pool escalado para {num_slaves} slaves!")
    info(f"Portas: 20128 (master), 20129-{20128 + num_slaves} (slaves)")


# ============================================================================
# SLAVE ADD / DELETE
# ============================================================================

def slave_add(
    config: dict[str, Any],
    name: str,
    host: str,
    docker_host: str = "",
) -> None:

    for slave in config["slaves"]:
        if slave["name"] == name:
            error(f"Slave '{name}' já existe")
            return

    config["slaves"].append({
        "name": name,
        "host": host,
        "docker_host": docker_host,
        "password": config["defaults"].get(
            "password", "123456"
        ),
    })

    save_config(config)

    success(f"Slave '{name}' adicionado → {host} (docker: {docker_host or host})")


def slave_delete(
    config: dict[str, Any],
    name: str,
    dry_run: bool = False,
) -> None:

    found = False

    for i, slave in enumerate(config["slaves"]):
        if slave["name"] == name:
            found = True

            if dry_run:
                info(
                    f"[dry-run] removeria slave '{name}'"
                )
            else:
                config["slaves"].pop(i)
                save_config(config)
                success(f"Slave '{name}' removido")

            break

    if not found:
        error(f"Slave '{name}' não encontrado")


# ============================================================================
# BACKUP
# ============================================================================

def backup_pool(
    config: dict[str, Any],
    output: str | None = None,
) -> None:

    master = master_instance(config)

    title(f"BACKUP {master.host}")

    client = RouterClient(master)

    if not client.login():
        error("login falhou")
        return

    backup_data = client.get_backup()

    if output:
        output_path = Path(output)
    else:
        timestamp = __import__("datetime").datetime.now().strftime(
            "%Y%m%d-%H%M%S"
        )
        output_path = BASE_DIR / f"backup-{timestamp}.json"

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(backup_data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    success(f"Backup salvo em: {output_path}")
    info(f"Provider nodes: {len(backup_data.get('providerNodes', []))}")
    info(f"Provider connections: {len(backup_data.get('providerConnections', []))}")
    info(f"Combos: {len(backup_data.get('combos', []))}")
    info(f"Custom models: {len(backup_data.get('customModels', []))}")


# ============================================================================
# CLEAN
# ============================================================================


def clean_pool(
    config: dict[str, Any],
    dry_run: bool = False,
) -> None:
    """Limpa tudo: containers, dados, configs."""

    title("CLEAN — Remover tudo")

    master = master_instance(config)
    slaves = slave_instances(config)
    total = len(slaves) + 2  # slaves + master + tor

    info(f"Containers para remover: {total}")
    info(f"  - sbx-tor")
    info(f"  - sbx-9router-master")
    for slave in slaves:
        info(f"  - sbx-{slave.name}")

    if dry_run:
        info("[dry-run] nada será removido")
        return

    # 1. Docker compose down (com -v remove volumes)
    info("Parando containers e removendo volumes...")
    result = subprocess.run(
        ["docker", "compose", "down", "-v", "--remove-orphans"],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        success("containers e volumes removidos")
    else:
        error(f"docker compose down falhou: {result.stderr}")

    # 2. Reset config.json para 1 slave
    info("Resetando config.json para 1 slave...")
    config["slaves"] = [
        {
            "name": "rs001",
            "host": "localhost:20129",
            "docker_host": "9router-slave-001:20129",
            "password": "123456",
        }
    ]
    save_config(config)
    success("config.json resetado (1 slave)")

    # 3. Gerar docker-compose.yaml e .env para 1 slave
    info("Gerando docker-compose.yaml para 1 slave...")
    compose_content = generate_docker_compose(config, 1)
    compose_path = BASE_DIR / "docker-compose.yaml"
    with compose_path.open("w", encoding="utf-8") as f:
        f.write(compose_content)
    success("docker-compose.yaml atualizado")

    info("Gerando .env para 1 slave...")
    env_content = generate_env(1)
    env_path = BASE_DIR / ".env"
    with env_path.open("w", encoding="utf-8") as f:
        f.write(env_content)
    success(".env atualizado")

    print()
    success("Pool limpo! Tudo removido.")


def fetch_opencode_free_models() -> dict[str, list[str]]:
    """Busca modelos free do opencode via suggested-models e testa thinking."""
    import re
    import requests as req

    title("FETCH — Buscar modelos opencode free")

    # 1. Login no master e obter API key
    info("Fazendo login no master...")
    s = req.Session()
    try:
        r = s.post(
            "http://localhost:20128/api/auth/login",
            json={"password": "123456"},
            timeout=10,
        )
        # Obter API key via /api/keys
        r2 = s.get("http://localhost:20128/api/keys", timeout=10)
        if r2.status_code == 200:
            keys = r2.json().get("keys", [])
            api_key = keys[0].get("key", "") if keys else ""
        else:
            api_key = ""
    except Exception as exc:
        error(f"Erro ao fazer login: {exc}")
        return {"thinking": [], "no_thinking": []}

    if not api_key:
        error("Não obteve API key")
        return {"thinking": [], "no_thinking": []}

    info(f"API key: {api_key[:20]}...")

    # 2. Buscar lista de modelos free
    info("Buscando modelos opencode free...")
    try:
        r = s.get(
            "http://localhost:20128/api/providers/suggested-models",
            params={
                "url": "https://opencode.ai/zen/v1/models",
                "type": "opencode-free",
            },
            timeout=15,
        )
        if r.status_code != 200:
            error(f"Erro ao buscar modelos: {r.status_code}")
            return {"thinking": [], "no_thinking": []}

        data = r.json()
        models = [m["id"] for m in data.get("data", [])]
        success(f"Encontrados {len(models)} modelos free")
    except Exception as exc:
        error(f"Erro ao conectar: {exc}")
        return {"thinking": [], "no_thinking": []}

    # 3. Testar thinking de cada modelo
    info("Testando thinking de cada modelo...")
    thinking = []
    no_thinking = []

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    for model_id in models:
        full_model = f"oc/{model_id}"
        try:
            payload = {
                "model": full_model,
                "input": "What is 2+2? Think step by step.",
                "max_output_tokens": 2000,
            }
            r = req.post(
                "http://localhost:20128/v1/responses",
                json=payload,
                headers=headers,
                timeout=60,
            )
            text = r.text

            reasoning_match = re.search(
                r'"reasoning_tokens":\s*(\d+)', text
            )
            reasoning_tokens = (
                int(reasoning_match.group(1)) if reasoning_match else 0
            )

            has_thinking = reasoning_tokens > 10

            if has_thinking:
                thinking.append(full_model)
                info(f"  ✓ {full_model} → THINKING ({reasoning_tokens} tokens)")
            else:
                no_thinking.append(full_model)
                info(f"  ✓ {full_model} → NO THINKING")

        except Exception as exc:
            warning(f"  ✗ {full_model} → FALHOU: {exc}")

    success(
        f"Result: {len(thinking)} thinking, {len(no_thinking)} no thinking"
    )
    return {"thinking": thinking, "no_thinking": no_thinking}


def update_config_with_models(
    config: dict[str, Any],
    models: dict[str, list[str]],
) -> None:
    """Atualiza config.json com modelos descobertos."""
    thinking = models.get("thinking", [])
    no_thinking = models.get("no_thinking", [])
    all_models = thinking + no_thinking

    if not all_models:
        warning("Nenhum modelo encontrado, mantendo config atual")
        return

    title("UPDATE — Atualizando config.json")

    # defaults.models = todos os modelos
    config["defaults"]["models"] = all_models
    info(f"defaults.models: {len(all_models)} modelos")

    # combos
    config["defaults"]["combos"] = []

    if thinking:
        config["defaults"]["combos"].append(
            {"name": "claude-opus-5", "models": thinking}
        )
        info(f"combo claude-opus-5: {len(thinking)} modelos (thinking)")

    if no_thinking:
        config["defaults"]["combos"].append(
            {"name": "claude-sonnet-5", "models": no_thinking}
        )
        info(f"combo claude-sonnet-5: {len(no_thinking)} modelos (no thinking)")

    # publish = nomes dos combos
    config["defaults"]["publish"] = [
        c["name"] for c in config["defaults"]["combos"]
    ]

    save_config(config)
    success("config.json atualizado")


def create_pool(
    config: dict[str, Any],
    dry_run: bool = False,
) -> None:
    """Cria pool básico: 1 master + 1 slave, sobe e sincroniza."""

    title("CREATE — Criar pool básico (1 master + 1 slave)")

    if dry_run:
        info("[dry-run] nada será criado")
        return

    master = master_instance(config)

    # 1. Reset config.json para 1 slave
    info("Resetando config.json para 1 slave...")
    config["slaves"] = [
        {
            "name": "rs001",
            "host": "localhost:20129",
            "docker_host": "9router-slave-001:20129",
            "password": "123456",
        }
    ]
    save_config(config)
    success("config.json resetado (1 slave)")

    # 2. Gerar docker-compose.yaml e .env
    info("Gerando docker-compose.yaml...")
    compose_content = generate_docker_compose(config, 1)
    compose_path = BASE_DIR / "docker-compose.yaml"
    with compose_path.open("w", encoding="utf-8") as f:
        f.write(compose_content)
    success("docker-compose.yaml atualizado")

    info("Gerando .env...")
    env_content = generate_env(1)
    env_path = BASE_DIR / ".env"
    with env_path.open("w", encoding="utf-8") as f:
        f.write(env_content)
    success(".env atualizado")

    # 3. Docker compose up
    info("Iniciando containers...")
    result = subprocess.run(
        ["docker", "compose", "up", "-d", "--remove-orphans"],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        success("containers iniciados")
    else:
        error(f"docker compose up falhou: {result.stderr}")
        return

    # 4. Aguardar containers ficarem healthy
    time.sleep(5)
    info("Aguardando containers ficarem healthy...")
    for attempt in range(30):
        time.sleep(3)
        check = subprocess.run(
            ["docker", "compose", "ps", "--format", "json"],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
        )
        if check.returncode == 0:
            healthy = 0
            for line in check.stdout.strip().split("\n"):
                if not line:
                    continue
                data = json.loads(line)
                state = data.get("State", "")
                health = data.get("Health", "")
                if state == "running" and health == "healthy":
                    healthy += 1
            if healthy >= 2:  # master + slave (tor não tem healthcheck)
                break
            info(f"Healthy: {healthy}/2... ({attempt + 1}/30)")
    else:
        warning("Containers podem não estar totalmente prontos")

    # 5. Health check no master via API (double-check)
    wait_for_instance(master, max_attempts=10, delay=3)

    # 6. Buscar modelos opencode free e atualizar config
    models = fetch_opencode_free_models()
    update_config_with_models(config, models)

    # 7. Sync
    info("Sincronizando com master...")
    sync_pool(config, dry_run=False)

    print()
    success("Pool criado! 1 master + 1 slave")
    info("Portas: 20128 (master), 20129 (slave)")


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:

    parser = argparse.ArgumentParser(
        description="9Router Pool Manager"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        help="Comandos disponíveis",
    )

    # list
    subparsers.add_parser(
        "list",
        help="Listar configuração do pool",
    )

    # create
    create_parser = subparsers.add_parser(
        "create",
        help="Criar pool básico: 1 master + 1 slave, sobe e sincroniza",
    )
    create_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simular sem alterar nada",
    )

    # test
    subparsers.add_parser(
        "test",
        help="Testar conectividade com todas as instâncias",
    )

    # sync
    sync_parser = subparsers.add_parser(
        "sync",
        help="Sincronizar configuração dos slaves ao master",
    )

    sync_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simular sem alterar nada",
    )

    # slave add
    slave_add_parser = subparsers.add_parser(
        "slave add",
        help="Adicionar um novo slave",
    )

    slave_add_parser.add_argument(
        "name",
        help="Nome do slave (ex: rs004)",
    )

    slave_add_parser.add_argument(
        "host",
        help="Host do slave para pool.py (ex: localhost:20132)",
    )

    slave_add_parser.add_argument(
        "--docker-host",
        help="Host Docker para o master (ex: 9router-slave-004:20132)",
        default="",
    )

    # slave delete
    slave_delete_parser = subparsers.add_parser(
        "slave delete",
        help="Remover um slave",
    )

    slave_delete_parser.add_argument(
        "name",
        help="Nome do slave",
    )

    slave_delete_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simular sem alterar nada",
    )

    # backup
    backup_parser = subparsers.add_parser(
        "backup",
        help="Fazer backup da configuração do master",
    )

    backup_parser.add_argument(
        "--output",
        help="Arquivo de saída (padrão: backup-YYYYMMDD-HHMMSS.json)",
    )

    # scale
    scale_parser = subparsers.add_parser(
        "scale",
        help="Escalar pool para N slaves",
    )
    scale_parser.add_argument(
        "num_slaves",
        type=int,
        help="Número de slaves (ex: 6)",
    )
    scale_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simular sem alterar nada",
    )
    scale_parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Não executar sync após criar slaves",
    )

    # clean
    clean_parser = subparsers.add_parser(
        "clean",
        help="Limpar tudo: containers, dados, configs",
    )
    clean_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simular sem alterar nada",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    config = load_config()

    if args.command == "list":
        list_pool(config)

    elif args.command == "create":
        create_pool(config, dry_run=args.dry_run)

    elif args.command == "test":
        test_pool(config)

    elif args.command == "sync":
        sync_pool(config, dry_run=args.dry_run)

    elif args.command == "slave add":
        slave_add(config, args.name, args.host, docker_host=args.docker_host)

    elif args.command == "slave delete":
        slave_delete(
            config,
            args.name,
            dry_run=args.dry_run,
        )

    elif args.command == "backup":
        backup_pool(config, output=args.output)

    elif args.command == "scale":
        scale_pool(
            config,
            args.num_slaves,
            dry_run=args.dry_run,
            no_sync=args.no_sync,
        )

    elif args.command == "clean":
        clean_pool(
            config,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
