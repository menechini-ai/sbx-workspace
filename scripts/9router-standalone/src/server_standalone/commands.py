"""Command functions for 9Router standalone management."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from .config import BASE_DIR, save_config
from .console import C, error, info, success, title, warning
from .docker import (
    generate_docker_compose,
    generate_env,
)
from .fetch import fetch_opencode_free_models, update_config_with_models
from .models import (
    RouterClient,
    standalone_instance,
    wait_for_instance,
)
from .sync import (
    sync_instance,
    configure_instance,
)


def list_instance(config: dict[str, Any]) -> None:

    defaults = config["defaults"]
    instance = standalone_instance(config)

    title("9ROUTER STANDALONE")

    print(
        f"Instance: {C.BOLD}{instance.host}{C.END}"
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


def test_instance(config: dict[str, Any]) -> None:

    instance = standalone_instance(config)

    title("9ROUTER STANDALONE TEST")

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

            if providers:
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

    else:
        error("login falhou")

    print()
    success("Teste concluído")


def fetch_models(config: dict[str, Any]) -> None:
    """Buscar modelos do opencode e atualizar config.json."""

    instance = standalone_instance(config)

    models = fetch_opencode_free_models(
        instance_host=instance.host,
        instance_password=instance.password,
    )
    update_config_with_models(config, models)


def create_instance(
    config: dict[str, Any],
    dry_run: bool = False,
) -> None:
    """Cria instância standalone básica."""

    title("CREATE — Criar instância standalone")

    if dry_run:
        info("[dry-run] nada será criado")
        return

    instance = standalone_instance(config)

    # 1. Gerar docker-compose.yaml e .env
    info("Gerando docker-compose.yaml...")
    compose_content = generate_docker_compose(config)
    compose_path = BASE_DIR / "docker-compose.yaml"
    with compose_path.open("w", encoding="utf-8") as f:
        f.write(compose_content)
    success("docker-compose.yaml criado")

    info("Gerando .env...")
    env_content = generate_env()
    env_path = BASE_DIR / ".env"
    with env_path.open("w", encoding="utf-8") as f:
        f.write(env_content)
    success(".env criado")

    # 2. Docker compose up
    info("Iniciando container...")
    result = subprocess.run(
        ["docker", "compose", "up", "-d", "--remove-orphans"],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        success("container iniciado")
    else:
        error(f"docker compose up falhou: {result.stderr}")
        return

    # 3. Aguardar container ficar healthy
    time.sleep(5)
    info("Aguardando container ficar healthy...")
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
            if healthy >= 1:  # apenas a instância standalone
                break
            info(f"Healthy: {healthy}/1... ({attempt + 1}/30)")
    else:
        warning("Container pode não estar totalmente pronto")

    # 4. Health check na instância via API
    wait_for_instance(instance, max_attempts=10, delay=3)

    # 5. Buscar modelos opencode free e atualizar config
    models = fetch_opencode_free_models(
        instance_host=instance.host,
        instance_password=instance.password,
    )
    update_config_with_models(config, models)

    # 6. Sync
    info("Sincronizando instância...")
    sync_instance(config, dry_run=False, validate_models=True)

    print()
    success("Instância standalone criada!")
    info(f"Porta: 20128 (standalone)")


def clean_instance(
    config: dict[str, Any],
    dry_run: bool = False,
) -> None:
    """Limpa tudo: container, dados, configs."""

    title("CLEAN — Remover tudo")

    instance = standalone_instance(config)

    info(f"Container para remover: sbx-9router-standalone")

    if dry_run:
        info("[dry-run] nada será removido")
        return

    # 1. Docker compose down (com -v remove volumes)
    info("Parando container e removendo volume...")
    subprocess.run(
        ["docker", "compose", "down", "-v"],
        cwd=BASE_DIR, capture_output=True,
    )
    success("container e volume removidos")

    # 2. Reset config.json para padrão
    info("Resetando config.json para padrão...")
    config["instance"] = {
        "name": "standalone",
        "host": "localhost:20128",
        "password": "123456",
    }
    config["defaults"] = {
        "models": [],
        "combos": [],
        "publish": [],
        "proxy": {
            "name": "tor-proxy",
            "url": "socks5://sbx-tor:9050",
            "type": "socks5",
            "noProxy": "localhost,127.0.0.1"
        }
    }
    save_config(config)
    success("config.json resetado")

    # 3. Gerar docker-compose.yaml e .env padrão
    info("Gerando docker-compose.yaml padrão...")
    compose_content = generate_docker_compose(config)
    compose_path = BASE_DIR / "docker-compose.yaml"
    with compose_path.open("w", encoding="utf-8") as f:
        f.write(compose_content)
    success("docker-compose.yaml atualizado")

    info("Gerando .env padrão...")
    env_content = generate_env()
    env_path = BASE_DIR / ".env"
    with env_path.open("w", encoding="utf-8") as f:
        f.write(env_content)
    success(".env atualizado")

    print()
    success("Standalone limpo!")


def backup_instance(
    config: dict[str, Any],
    output: str | None = None,
) -> None:

    instance = standalone_instance(config)

    title(f"BACKUP {instance.host}")

    client = RouterClient(instance)

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