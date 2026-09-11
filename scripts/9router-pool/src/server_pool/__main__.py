"""9Router Pool Manager - Main entry point."""

from __future__ import annotations

import argparse
import sys

from .commands import (
    backup_pool,
    clean_pool,
    create_pool,
    list_pool,
    scale_pool,
    slave_add,
    slave_delete,
    sync_pool,
    test_pool,
)
from .config import load_config


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

    sync_parser.add_argument(
        "--skip-health-check",
        action="store_true",
        help="Pular verificação de saúde dos providers (mais rápido)",
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

    # watch
    watch_parser = subparsers.add_parser(
        "watch",
        help="Monitorar saúde dos slaves e substituir automaticamente os com falha",
    )
    watch_parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Segundos entre verificações (padrão: 60)",
    )
    watch_parser.add_argument(
        "--failures",
        type=int,
        default=2,
        help="Falhas consecutivas antes de substituir o slave (padrão: 2)",
    )
    watch_parser.add_argument(
        "--fetch-interval",
        type=int,
        default=21600,
        help="Segundos entre auto-discovery de modelos (padrão: 21600 / 6h, 0 para desativar)",
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
        sync_pool(
            config,
            dry_run=args.dry_run,
            skip_health_check=args.skip_health_check,
        )

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

    elif args.command == "watch":
        from .watch import watch_pool
        watch_pool(
            config,
            interval=args.interval,
            max_failures=args.failures,
            fetch_interval=args.fetch_interval,
        )


