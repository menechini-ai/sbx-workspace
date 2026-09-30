"""9Router Standalone Manager - Main entry point."""

from __future__ import annotations

import argparse
import sys

from .commands import (
    backup_instance,
    clean_instance,
    create_instance,
    fetch_models,
    list_instance,
    sync_instance,
    test_instance,
)
from .config import load_config
from .watch import watch_instance


def main() -> None:

    parser = argparse.ArgumentParser(
        description="9Router Standalone Manager"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        help="Comandos disponíveis",
    )

    # list
    subparsers.add_parser(
        "list",
        help="Listar configuração da instância",
    )

    # create
    create_parser = subparsers.add_parser(
        "create",
        help="Criar instância standalone, sobe e sincroniza",
    )
    create_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simular sem alterar nada",
    )

    # test
    subparsers.add_parser(
        "test",
        help="Testar conectividade com a instância",
    )

    # sync
    sync_parser = subparsers.add_parser(
        "sync",
        help="Sincronizar configuração da instância",
    )

    sync_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simular sem alterar nada",
    )

    sync_parser.add_argument(
        "--health-check",
        action="store_true",
        help="Executar health check dos providers após sync (desativado por padrão)",
    )

    sync_parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Pular validação de modelos antes de criar combos",
    )

    # fetch
    subparsers.add_parser(
        "fetch",
        help="Buscar modelos opencode free e atualizar config",
    )

    # backup
    backup_parser = subparsers.add_parser(
        "backup",
        help="Fazer backup da configuração da instância",
    )

    backup_parser.add_argument(
        "--output",
        help="Arquivo de saída (padrão: backup-YYYYMMDD-HHMMSS.json)",
    )

    # clean
    clean_parser = subparsers.add_parser(
        "clean",
        help="Limpar tudo: container, dados, configs",
    )
    clean_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simular sem alterar nada",
    )

    # watch
    watch_parser = subparsers.add_parser(
        "watch",
        help="Monitorar saúde da instância e auto-discovery de modelos",
    )
    watch_parser.add_argument(
        "--interval",
        type=int,
        default=180,
        help="Segundos entre verificações de saúde (padrão: 180)",
    )
    watch_parser.add_argument(
        "--fetch-interval",
        type=int,
        default=600,
        help="Segundos entre auto-discovery de modelos (padrão: 600 / 10min, 0 para desativar)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    config = load_config()

    if args.command == "list":
        list_instance(config)

    elif args.command == "create":
        create_instance(config, dry_run=args.dry_run)

    elif args.command == "test":
        test_instance(config)

    elif args.command == "sync":
        sync_instance(
            config,
            dry_run=args.dry_run,
            skip_health_check=not args.health_check,
            validate_models=not args.no_validate,
        )

    elif args.command == "fetch":
        fetch_models(config)

    elif args.command == "backup":
        backup_instance(config, output=args.output)

    elif args.command == "clean":
        clean_instance(
            config,
            dry_run=args.dry_run,
        )

    elif args.command == "watch":
        watch_instance(
            config,
            interval=args.interval,
            fetch_interval=args.fetch_interval,
        )