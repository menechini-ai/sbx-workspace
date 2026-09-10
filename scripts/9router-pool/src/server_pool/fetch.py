"""Fetch opencode free models and test thinking capability."""

from __future__ import annotations

import re
from typing import Any

import requests as req

from .config import save_config
from .console import error, info, success, title, warning


def fetch_opencode_free_models() -> dict[str, list[str]]:
    """Busca modelos free do opencode via suggested-models e testa thinking."""

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
