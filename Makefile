SERVICES := ai-memory claude-code 9router-pool tor hermes

.PHONY: up down logs clean build cc code create scale pool-clean sync test list backup setup $(SERVICES)

# Targets vazios para Make não reclamar com: make down ai-memory
ai-memory:; @true
claude-code:; @true
9router-pool:; @true
tor:; @true
hermes:; @true

ROOT := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
POOL := $(ROOT)scripts/9router-pool

# ============================================================================
# 9Router Pool — targets diretos
# ============================================================================

# make create — criar pool (1 master + 1 slave)
create:
	cd $(POOL) && make create

# make scale N=5 — escalar para N slaves
scale:
	cd $(POOL) && make scale N=$(N)

# make pool-clean — limpar pool e volumes
pool-clean:
	cd $(POOL) && make clean

# make sync — sincronizar config com master
sync:
	cd $(POOL) && make sync

# make test — testar conectividade
test:
	cd $(POOL) && make test

# make list — mostrar configuracao
list:
	cd $(POOL) && make list

# make backup — backup da config do master
backup:
	cd $(POOL) && make backup

# ============================================================================
# setup — sobe a infraestrutura (tor -> 9router-pool -> ai-memory)
# ============================================================================

# make setup — cria rede, tor, pool 9router e ai-memory
setup:
	@docker network inspect sbx-net >/dev/null 2>&1 || docker network create sbx-net
	@echo "=== [1/3] Tor ==="
	cd $(ROOT)scripts/tor && make up
	@echo "=== [2/3] 9Router Pool ==="
	cd $(ROOT)scripts/9router-pool && make create
	@echo "=== [3/3] ai-memory ==="
	cd $(ROOT)scripts/ai-memory && make up
	@echo "=== Setup completo ==="

# ============================================================================
# up / down / logs / clean (genericos)
# ============================================================================

# make up SERVICE=ai-memory | make up SERVICE=9router-pool
up:
	@if [ -z "$(filter $(SERVICES),$(SERVICE))" ]; then \
		echo "Uso: make up SERVICE=<servico>"; \
		echo "Servicos: $(SERVICES)"; \
		echo "Atalhos: make cc (=claude-code run)"; \
		exit 1; \
	fi
	@if [ "$(SERVICE)" = "9router-pool" ]; then \
		cd $(ROOT)scripts/9router-pool && make create; \
	else \
		cd $(ROOT)scripts/$(SERVICE) && make up; \
	fi

# Atalhos
cc:
	cd $(ROOT)scripts/claude-code && make up && docker exec -it claude-code claude --dangerously-skip-permissions

code:
	@echo "Use: cd scripts/claude-code && make up && docker exec -it claude-code claude"
	@echo "Ou: make cc"

# make down SERVICE=ai-memory | make down (todos)
down:
	@if [ -n "$(filter $(SERVICES),$(SERVICE))" ]; then \
		if [ "$(SERVICE)" = "9router-pool" ]; then \
			cd $(ROOT)scripts/9router-pool && make clean; \
		else \
			cd $(ROOT)scripts/$(SERVICE) && make down; \
		fi; \
	else \
		for svc in $(SERVICES); do \
			echo "Parando $$svc..."; \
			if [ "$$svc" = "9router-pool" ]; then \
				cd $(ROOT)scripts/9router-pool && make clean; \
			else \
				cd $(ROOT)scripts/$$svc && make down; \
			fi; \
		done; \
	fi

# make logs SERVICE=ai-memory
logs:
	@if [ -z "$(filter $(SERVICES),$(SERVICE))" ]; then \
		echo "Uso: make logs SERVICE=<servico>"; \
		echo "Servicos: $(SERVICES)"; \
		exit 1; \
	fi
	cd $(ROOT)scripts/$(SERVICE) && make logs

# make clean SERVICE=ai-memory | make clean (todos)
clean:
	@if [ -n "$(filter $(SERVICES),$(SERVICE))" ]; then \
		if [ "$(SERVICE)" = "9router-pool" ]; then \
			cd $(ROOT)scripts/9router-pool && make clean; \
		else \
			cd $(ROOT)scripts/$(SERVICE) && make clean; \
		fi; \
	else \
		for svc in $(SERVICES); do \
			echo "Limpando $$svc..."; \
			if [ "$$svc" = "9router-pool" ]; then \
				cd $(ROOT)scripts/9router-pool && make clean; \
			else \
				cd $(ROOT)scripts/$$svc && make clean; \
			fi; \
		done; \
	fi

# make build
build:
	docker compose -f $(ROOT)scripts/claude-code/docker-compose.yaml build