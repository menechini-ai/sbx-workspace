# 9Router Standalone Makefile

.PHONY: help list create test sync fetch backup clean watch

help:
	@echo "9Router Standalone - Comandos disponíveis:"
	@echo "  make list      - Listar configuração"
	@echo "  make create    - Criar instância standalone"
	@echo "  make test      - Testar conectividade"
	@echo "  make sync      - Sincronizar configuração"
	@echo "  make fetch     - Buscar modelos opencode free"
	@echo "  make backup    - Fazer backup"
	@echo "  make clean     - Limpar tudo"
	@echo "  make watch     - Monitorar instância (watchdog)"

list:
	python standalone.py list

create:
	python standalone.py create

test:
	python standalone.py test

sync:
	python standalone.py sync

sync-dry:
	python standalone.py sync --dry-run

fetch:
	python standalone.py fetch

backup:
	python standalone.py backup

clean:
	python standalone.py clean

clean-dry:
	python standalone.py clean --dry-run

watch:
	python standalone.py watch

watch-fast:
	python standalone.py watch --interval 60 --fetch-interval 300