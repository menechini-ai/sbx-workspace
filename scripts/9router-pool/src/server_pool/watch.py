"""Watchdog: monitora slaves, realiza auto-discovery de modelos e substituição com quarentena."""

from __future__ import annotations

import signal
import time
from typing import Any

from .config import load_config
from .console import error, info, success, title, warning
from .fetch import fetch_opencode_free_models, update_config_with_models
from .models import RouterClient, master_instance, slave_instances
from .sync import (
    hot_reload_master_models,
    quarantine_slave,
    replace_slave,
    unquarantine_slave,
)

MIN_SLAVES = 2


def _test_provider(
    master_client: RouterClient,
    provider_id: str,
    timeout: int = 30,
) -> tuple[bool, str]:
    """Testa um provider via master. Retorna (valid, error_msg)."""
    try:
        r = master_client.session.post(
            f"{master_client.instance.base_url}/api/providers/{provider_id}/test",
            json={},
            timeout=timeout,
        )
        r.raise_for_status()
        data = r.json()
        err_msg = data.get("error") or ""
        return data.get("valid", False), str(err_msg)
    except Exception as exc:
        return False, str(exc)


def _is_rate_limited(err: str | None) -> bool:
    if not err:
        return False
    msg = str(err).lower()
    return "429" in msg or "rate limit" in msg or "too many" in msg


def watch_pool(
    config: dict[str, Any],
    interval: int = 60,
    max_failures: int = 2,
    fetch_interval: int = 21600,
) -> None:
    """
    Loop de monitoramento contínuo e autônomo (Pool Vivo).

    - Auto-Discovery de modelos a cada fetch_interval segundos (padrão 6h / 21600s).
    - Quarentena preventiva na 1ª falha (remove do combo do master sem matar o container).
    - Replace completo (Delete+Create) na max_failures consecutiva.
    - Desfaz quarentena se o slave se recuperar.
    """
    master = master_instance(config)
    slaves = slave_instances(config)

    title("9ROUTER LIVE POOL WATCHDOG")
    info(f"Slaves: {len(slaves)} | Mínimo: {MIN_SLAVES}")
    info(f"Intervalo Health: {interval}s | Falhas para Replace: {max_failures}")
    if fetch_interval > 0:
        info(f"Auto-Discovery Modelos: a cada {fetch_interval}s ({fetch_interval // 3600}h)")
    else:
        info("Auto-Discovery Modelos: desativado")
    info("Pressione Ctrl+C para parar\n")

    if len(slaves) < MIN_SLAVES:
        warning(f"Pool tem {len(slaves)} slave(s) — abaixo do mínimo de {MIN_SLAVES}!")

    failure_counts: dict[str, int] = {s.name: 0 for s in slaves}
    quarantined: set[str] = set()
    replacing: set[str] = set()
    last_fetch_time: float = time.time()

    def _stop(sig, frame):
        print()
        info("Watchdog encerrado.")
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    while True:
        now = time.time()

        # -------------------------------------------------------------------
        # 1. AUTO-DISCOVERY & HOT-RELOAD DE MODELOS
        # -------------------------------------------------------------------
        if fetch_interval > 0 and (now - last_fetch_time >= fetch_interval):
            info("\n[watchdog] Iniciando Auto-Discovery de modelos...")
            try:
                discovered = fetch_opencode_free_models(
                    master_host=master.host,
                    master_password=master.password,
                )
                if discovered.get("thinking") or discovered.get("no_thinking"):
                    fresh_cfg = load_config()
                    update_config_with_models(fresh_cfg, discovered)
                    hot_reload_master_models(fresh_cfg)
                    success("[watchdog] Hot-Reload de novos modelos concluído!")
            except Exception as exc:
                warning(f"[watchdog] Falha no Auto-Discovery de modelos: {exc}")
            last_fetch_time = time.time()

        # -------------------------------------------------------------------
        # 2. CARREGAR CONFIG E VERIFICAR SAÚDE
        # -------------------------------------------------------------------
        try:
            fresh_config = load_config()
        except Exception:
            fresh_config = config

        master_client = RouterClient(master)
        if not master_client.login():
            warning("[watchdog] login no master falhou — tentando no próximo ciclo")
            time.sleep(interval)
            continue

        try:
            providers = master_client.get_providers()
        except Exception as exc:
            warning(f"[watchdog] erro ao listar providers: {exc}")
            time.sleep(interval)
            continue

        provider_map = {p["name"]: p for p in providers if p.get("name")}

        ts = time.strftime("%H:%M:%S")
        active_slaves = slave_instances(fresh_config)
        print(f"\n[{ts}] Verificando {len(active_slaves)} slave(s)...")

        for slave in active_slaves:
            if slave.name in replacing:
                info(f"  {slave.name}: substituindo... aguardando")
                continue

            if slave.name not in failure_counts:
                failure_counts[slave.name] = 0

            provider = provider_map.get(slave.name)

            if not provider:
                warning(f"  {slave.name}: ausente no master → +1 falha")
                failure_counts[slave.name] += 1
            else:
                valid, err = _test_provider(master_client, provider["id"], timeout=30)
                kind = "429" if _is_rate_limited(err) else "ERRO"

                if valid:
                    # Se estava em quarentena e recuperou, tira da quarentena
                    if slave.name in quarantined:
                        unquarantine_slave(fresh_config, slave.name)
                        quarantined.remove(slave.name)
                    success(f"  {slave.name}: OK")
                    failure_counts[slave.name] = 0
                else:
                    cnt = failure_counts[slave.name] + 1
                    failure_counts[slave.name] = cnt
                    warning(f"  {slave.name}: {kind} ({cnt}/{max_failures}) — {err[:80]}")

                    # 1ª Falha -> Colocar em quarentena preventiva se ainda não estiver
                    if cnt == 1 and slave.name not in quarantined:
                        if quarantine_slave(fresh_config, slave.name):
                            quarantined.add(slave.name)

            # Atingiu o limite -> Replace completo (Delete + Create)
            if failure_counts[slave.name] >= max_failures:
                current_slaves = slave_instances(fresh_config)
                active_count = len([s for s in current_slaves if s.name not in replacing])

                if active_count <= MIN_SLAVES:
                    warning(
                        f"  {slave.name}: precisa de replace mas pool tem apenas "
                        f"{active_count} slave(s) ativo(s)."
                    )

                warning(f"\n  ⚡ {slave.name}: iniciando DELETE + CREATE...")
                replacing.add(slave.name)
                failure_counts[slave.name] = 0

                ok = replace_slave(fresh_config, slave.name)

                if ok:
                    success(f"  ✓ {slave.name}: substituído com sucesso")
                    quarantined.discard(slave.name)
                else:
                    error(f"  ✗ {slave.name}: falha no replace — tentará no próximo ciclo")
                    failure_counts[slave.name] = max_failures - 1

                replacing.discard(slave.name)

        time.sleep(interval)
