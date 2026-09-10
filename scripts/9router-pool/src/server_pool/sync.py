"""Synchronization logic for 9Router pool."""

from __future__ import annotations

import time
from typing import Any

from .console import C, error, info, success, title, warning
from .models import (
    Instance,
    RouterClient,
    master_instance,
    slave_instances,
    wait_for_instance,
)


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
