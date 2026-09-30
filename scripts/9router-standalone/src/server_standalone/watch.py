"""Watchdog: monitora instância standalone, realiza auto-discovery de modelos."""

from __future__ import annotations

import signal
import time
from typing import Any

from .config import load_config
from .console import error, info, success, title, warning
from .fetch import fetch_opencode_free_models, update_config_with_models
from .models import RouterClient, standalone_instance
from .sync import configure_instance


def watch_instance(
    config: dict[str, Any],
    interval: int = 300,
    fetch_interval: int = 600,
) -> None:
    """
    Loop de monitoramento contínuo e autônomo (Standalone Vivo).

    - Auto-Discovery de modelos a cada fetch_interval segundos (padrão 10min / 600s).
    - Health check da instância a cada interval segundos.
    """
    instance = standalone_instance(config)

    title("9ROUTER STANDALONE WATCHDOG")
    info(f"Instance: {instance.name} → {instance.host}")
    info(f"Intervalo Health: {interval}s")
    if fetch_interval > 0:
        info(f"Auto-Discovery Modelos: a cada {fetch_interval}s ({fetch_interval // 60}min)")
    else:
        info("Auto-Discovery Modelos: desativado")
    info("Pressione Ctrl+C para parar\n")

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
                    instance_host=instance.host,
                    instance_password=instance.password,
                )
                if discovered.get("thinking") or discovered.get("no_thinking"):
                    fresh_cfg = load_config()
                    update_config_with_models(fresh_cfg, discovered)
                    # Reconfigurar a instância com novos modelos
                    configure_instance(standalone_instance(fresh_cfg), fresh_cfg.get("defaults", {}))
                    success("[watchdog] Hot-Reload de novos modelos concluído!")
            except Exception as exc:
                warning(f"[watchdog] Falha no Auto-Discovery de modelos: {exc}")
            last_fetch_time = time.time()

        # -------------------------------------------------------------------
        # 2. HEALTH CHECK DA INSTÂNCIA
        # -------------------------------------------------------------------
        try:
            fresh_config = load_config()
        except Exception:
            fresh_config = config

        client = RouterClient(instance)
        if not client.login():
            warning("[watchdog] login na instância falhou — tentando no próximo ciclo")
            time.sleep(interval)
            continue

        try:
            providers = client.get_providers()
        except Exception as exc:
            warning(f"[watchdog] erro ao listar providers: {exc}")
            time.sleep(interval)
            continue

        provider_map = {p["name"]: p for p in providers if p.get("name")}

        ts = time.strftime("%H:%M:%S")
        print(f"\n[{ts}] Verificando instância {instance.name}...")

        # Testar cada provider
        for provider in providers:
            provider_id = provider.get("id")
            provider_name = provider.get("name", provider_id)

            if not provider_id:
                continue

            try:
                data = client.test_provider(provider_id, timeout=90)
                valid = data.get("valid", False)
                err = data.get("error", "")

                if valid:
                    success(f"  {provider_name}: OK")
                else:
                    warning(f"  {provider_name}: FALHOU — {err[:80]}")
            except Exception as exc:
                warning(f"  {provider_name}: ERRO — {exc}")

        # Verificar combos
        try:
            combos = client.get_combos()
            info(f"  Combos ativos: {len(combos)}")
        except Exception as exc:
            warning(f"  Erro ao listar combos: {exc}")

        # Verificar custom models
        try:
            custom = client.get_custom_models()
            info(f"  Custom models: {len(custom)}")
        except Exception as exc:
            warning(f"  Erro ao listar custom models: {exc}")

        time.sleep(interval)