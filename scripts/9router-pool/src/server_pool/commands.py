"""Command functions for 9Router pool management."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from .config import BASE_DIR, save_config
from .console import C, error, info, success, title, warning
from .docker import (
    create_data_directories,
    generate_docker_compose,
    generate_env,
    remove_data_directories,
    update_config_for_scale,
)
from .fetch import fetch_opencode_free_models, update_config_with_models
from .models import (
    RouterClient,
    master_instance,
    slave_instances,
    wait_for_instance,
)
from .sync import sync_pool


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
