"""Synchronization logic for 9Router standalone."""

from __future__ import annotations

import time
from typing import Any

from .console import C, error, info, success, title, warning
from .models import (
    Instance,
    RouterClient,
    standalone_instance,
    wait_for_instance,
)


def validate_models_for_combo(
    client: RouterClient,
    models: list[str],
) -> tuple[list[str], list[str]]:
    """Valida cada modelo antes de adicionar ao combo.

    Verifica:
    1. Model é free (contém "-free" no ID)
    2. Model está ativo (responde sem erro)

    Returns:
        (valid_models, invalid_models)
    """
    info(f"Validando {len(models)} modelos para combo...")

    valid = []
    invalid = []

    for model_id in models:
        # 1. Verificar se é free
        if "-free" not in model_id.lower():
            warning(f"  ✗ {model_id} → não é FREE (sem '-free' no ID)")
            invalid.append(model_id)
            continue

        # 2. Testar se está ativo (health check via test provider ou API)
        try:
            # Tentar fazer um request simples para verificar se o modelo responde
            # Usar a API key existente para testar
            keys = client.get_api_keys()
            if not keys:
                warning(f"  ⚠ {model_id} → sem API key para testar")
                valid.append(model_id)  # Assume válido se não pode testar
                continue

            api_key = keys[0].get("key", "")

            # Test request
            test_response = client.session.post(
                f"{client.instance.base_url}/v1/responses",
                json={
                    "model": model_id,
                    "input": "Hi",
                    "max_output_tokens": 100,
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )

            if test_response.status_code == 429:
                warning(f"  ⚠ {model_id} → rate limit, assume válido")
                valid.append(model_id)
            elif test_response.status_code == 404:
                warning(f"  ✗ {model_id} → não encontrado (404)")
                invalid.append(model_id)
            elif test_response.status_code >= 500:
                warning(f"  ✗ {model_id} → erro servidor ({test_response.status_code})")
                invalid.append(model_id)
            elif test_response.status_code == 200:
                # Verificar se resposta contém erro
                try:
                    resp_data = test_response.json()
                    if resp_data.get("type") == "error":
                        error_msg = resp_data.get("error", {}).get("message", "erro desconhecido")
                        warning(f"  ✗ {model_id} → erro: {error_msg[:60]}")
                        invalid.append(model_id)
                    else:
                        info(f"  ✓ {model_id} → ATIVO + FREE")
                        valid.append(model_id)
                except Exception:
                    info(f"  ✓ {model_id} → ATIVO + FREE (sem JSON)")
                    valid.append(model_id)
            else:
                warning(f"  ⚠ {model_id} → status {test_response.status_code}, assume válido")
                valid.append(model_id)

        except Exception as exc:
            warning(f"  ✗ {model_id} → exceção: {str(exc)[:60]}")
            invalid.append(model_id)

    info(f"Validação: {len(valid)} válidos, {len(invalid)} inválidos")
    return valid, invalid


def configure_instance(
    instance: Instance,
    defaults: dict[str, Any],
    dry_run: bool = False,
    validate_models: bool = True,
) -> str | None:
    """Configure standalone instance and return API key for reference."""

    title(
        f"INSTANCE {instance.name} → {instance.host}"
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

    client = RouterClient(instance)

    # Health check antes do login
    wait_for_instance(instance, max_attempts=15, delay=3)

    if not client.login():
        error(
            f"{instance.name}: login falhou"
        )
        return None

    success(
        f"{instance.name}: login OK"
    )

    # ------------------------------------------------------------------------
    # CONFIGURAR PROXY POOL (Tor) via API do 9Router
    # ------------------------------------------------------------------------

    proxy_cfg = defaults.get("proxy", {})
    proxy_name = proxy_cfg.get("name", "tor-proxy")
    proxy_url = proxy_cfg.get("url", "socks5://sbx-tor:9050")
    proxy_type = proxy_cfg.get("type", "socks5")
    proxy_no_proxy = proxy_cfg.get("noProxy", "localhost,127.0.0.1")

    try:
        existing_pools = client.get_proxy_pools()
        already_ok = any(
            p.get("name") == proxy_name and p.get("proxyUrl") == proxy_url
            for p in existing_pools
        )
        if already_ok:
            info(
                f"{instance.name}: proxy pool '{proxy_name}' já configurado"
            )
        else:
            try:
                client.create_proxy_pool(
                    name=proxy_name,
                    proxy_url=proxy_url,
                    pool_type=proxy_type,
                    no_proxy=proxy_no_proxy,
                )
                success(
                    f"{instance.name}: proxy pool '{proxy_name}' criado "
                    f"(→ {proxy_url})"
                )
            except Exception as exc:
                warning(
                    f"{instance.name}: erro ao criar proxy pool "
                    f"'{proxy_name}': {exc}"
                )
    except Exception as exc:
        warning(
            f"{instance.name}: proxy pools indisponíveis: {exc}"
        )

    # ------------------------------------------------------------------------
    # REMOVER API KEY EXISTENTE "standalone-key"
    # ------------------------------------------------------------------------

    existing_keys = client.get_api_keys()

    for key in existing_keys:
        if key.get("name") == "standalone-key":
            try:
                client.delete_api_key(key["id"])
                info(
                    f"{instance.name}: API key 'standalone-key' removida"
                )
            except Exception as exc:
                warning(
                    f"{instance.name}: erro ao remover API key: {exc}"
                )

    # ------------------------------------------------------------------------
    # CRIAR NOVA API KEY "standalone-key"
    # ------------------------------------------------------------------------

    api_key = ""

    try:
        key_data = client.create_api_key(name="standalone-key")
        api_key = key_data.get("key", "")
        success(
            f"{instance.name}: API key criada"
        )
    except Exception as exc:
        error(
            f"{instance.name}: erro ao criar API key: {exc}"
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
                    f"{instance.name}: combo '{combo_name}' removido"
                )
            except Exception as exc:
                warning(
                    f"{instance.name}: erro ao remover combo '{combo_name}': {exc}"
                )

    # ------------------------------------------------------------------------
    # HEALTH CHECK ANTES DE CRIAR COMBOS
    # ------------------------------------------------------------------------

    info(f"{instance.name}: verificando saúde...")

    try:
        r = client.session.get(
            f"{client.instance.base_url}/api/combos",
            timeout=client.timeout,
        )
        r.raise_for_status()
        success(f"{instance.name}: saudável")
    except Exception as exc:
        error(f"{instance.name}: não saudável: {exc}")
        return None

    # ------------------------------------------------------------------------
    # CRIAR COMBOS DO DEFAULTS (com validação de modelos)
    # ------------------------------------------------------------------------

    for combo_config in combos:

        combo_name = combo_config["name"]
        combo_models = combo_config.get("models", [])

        if validate_models and combo_models:
            # Validar modelos antes de criar o combo
            valid_models, invalid_models = validate_models_for_combo(
                client, combo_models
            )

            if invalid_models:
                warning(
                    f"{instance.name}: {len(invalid_models)} modelos inválidos removidos do combo '{combo_name}'"
                )
                for m in invalid_models:
                    warning(f"    removido: {m}")

            if not valid_models:
                error(
                    f"{instance.name}: combo '{combo_name}' sem modelos válidos, pulando"
                )
                continue

            combo_models = valid_models

        try:
            client.create_combo(
                name=combo_name,
                models=combo_models,
            )

            success(
                f"{instance.name}: combo '{combo_name}' criado com {len(combo_models)} modelos"
            )

        except Exception as exc:
            error(
                f"{instance.name}: erro ao criar combo '{combo_name}': {exc}"
            )

    # ------------------------------------------------------------------------
    # VERIFICAR COMBOS CRIADOS
    # ------------------------------------------------------------------------

    combos_criados = client.get_combos()
    nomes_esperados = {c["name"] for c in combos}
    nomes_criados = {c["name"] for c in combos_criados}

    if nomes_esperados == nomes_criados:
        success(
            f"{instance.name}: todos os {len(nomes_criados)} combos verificados"
        )
    else:
        faltando = nomes_esperados - nomes_criados
        if faltando:
            error(
                f"{instance.name}: combos faltando: {faltando}"
            )

    # ------------------------------------------------------------------------
    # REMOVER CUSTOM MODELS EXISTENTES (não criar novos no standalone)
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

        if not in_any_combo and pa == "oc":
            try:
                client.delete_custom_model(pa, mid)
                info(
                    f"{instance.name}: custom model '{pa}/{mid}' removido"
                )
            except Exception:
                pass

    success(
        f"{instance.name}: configuração aplicada"
    )

    return api_key


def sync_instance(
    config: dict[str, Any],
    dry_run: bool = False,
    skip_health_check: bool = True,
    validate_models: bool = True,
) -> None:

    instance = standalone_instance(config)

    defaults = config["defaults"]

    title(f"9ROUTER STANDALONE SYNC — {instance.host}")

    print(
        f"Models: {len(defaults.get('models', []))}"
    )

    print(
        f"Combos: {len(defaults.get('combos', []))}"
    )

    print(
        f"Publish: {defaults.get('publish', [])}"
    )

    if validate_models:
        info("Validação de modelos: ATIVADA")
    else:
        warning("Validação de modelos: DESATIVADA")

    if dry_run:

        title("DRY RUN")

        print(
            f"\n{C.BOLD}{instance.name}{C.END} "
            f"→ {instance.host}"
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

    # Configurar a instância
    api_key = configure_instance(
        instance,
        defaults,
        dry_run=False,
        validate_models=validate_models,
    )

    if not api_key:
        error(f"configure_instance falhou para {instance.name}")
        return

    # ------------------------------------------------------------------------
    # EXPORTAR API KEY DA INSTÂNCIA
    # ------------------------------------------------------------------------

    try:
        client = RouterClient(instance)
        if client.login():
            keys = client.get_api_keys()

            # Se não tem API key, criar uma
            if not keys:
                info("Criando API key na instância...")
                key_data = client.create_api_key(name="standalone-key")
                if key_data:
                    keys = [key_data]
                    success("API key criada na instância")

            if keys:
                default_key = keys[0].get("key", "")
                print()
                success("API Key da Instância (use nos clientes):")
                info(f"  {default_key}")
                print()
                info("Exemplo OpenCode:")
                info(f'  apiKey: "{default_key}"')
                info(f'  baseUrl: "http://{instance.host}/v1"')
            else:
                warning("Não foi possível criar API key na instância")
        else:
            warning("Login na instância falhou para exportar API key")
    except Exception as exc:
        warning(f"Erro ao exportar API key: {exc}")

    success(
        "\nSync concluído!"
    )