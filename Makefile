# Define variáveis buscando direto do seu Git local
GIT_NAME := $(shell git config user.name 2>/dev/null || echo "Claude Agent")
GIT_EMAIL := $(shell git config user.email 2>/dev/null || echo "claude-agent@local.internal")

NINEROUTER_COMPOSE := scripts/9router/docker-compose.yaml

.PHONY: up down run code logs clean build build-base scan-secrets scan-secrets-ci 9router-up 9router-down 9router-logs lint install-pre-commit

# Constrói a imagem base compartilhada
build-base:
	@echo "Construindo imagem base..."
	docker compose build --no-cache base 2>/dev/null || \
	docker build -t ai-memory-base:latest ./scripts/base

# Constrói todas as imagens
build: build-base
	@echo "Construindo imagens dos agentes..."
	docker compose build claude-code opencode

# Inicia o servidor de memória em background
up:
	@echo "Iniciando o servidor ai-memory..."
	docker compose up -d ai-memory

# Para todos os serviços
down:
	docker compose down

# Abre o Claude Code instantaneamente com um único comando
cc:
	@echo "Iniciando Claude Code com o usuário Git: $(GIT_NAME)"
	@GIT_AUTHOR_NAME="$(GIT_NAME)" \
	GIT_AUTHOR_EMAIL="$(GIT_EMAIL)" \
	GIT_COMMITTER_NAME="$(GIT_NAME)" \
	GIT_COMMITTER_EMAIL="$(GIT_EMAIL)" \
	docker compose run --rm claude-code

# Abre o OpenCode instantaneamente com um único comando
code:
	@echo "Iniciando OpenCode com o usuário Git: $(GIT_NAME)"
	@GIT_AUTHOR_NAME="$(GIT_NAME)" \
	GIT_AUTHOR_EMAIL="$(GIT_EMAIL)" \
	GIT_COMMITTER_NAME="$(GIT_NAME)" \
	GIT_COMMITTER_EMAIL="$(GIT_EMAIL)" \
	docker compose run --rm opencode

# Mostra os logs do servidor de memória
logs:
	docker compose logs -f ai-memory

# Remove os volumes e limpa o ambiente Docker
clean:
	docker compose down -v

# Rebuild completo (base + agents)
rebuild: clean build
	@echo "Rebuild completo finalizado"

# ============================
# 9Router — Gateway IA Gratuito
# ============================

# Inicia 9Router (master + 3 slaves)
9router-up:
	@echo "Iniciando 9Router (master + 3 slaves)..."
	docker compose -f $(NINEROUTER_COMPOSE) up -d

# Para 9Router
9router-down:
	@echo "Parando 9Router..."
	docker compose -f $(NINEROUTER_COMPOSE) down

# Logs do 9Router
9router-logs:
	docker compose -f $(NINEROUTER_COMPOSE) logs -f

# ============================
# Security: Gitleaks
# ============================

# Escaneia segredos no repo (usa .gitleaks.toml)
scan-secrets:
	@echo "🔍 Escaneando segredos com gitleaks..."
	@docker run --rm -v $(PWD):/workspace -w /workspace \
		zricethezav/gitleaks:latest detect \
		--source /workspace \
		--config /workspace/.gitleaks.toml \
		--verbose \
		--redact

# Escaneia segredos (modo CI - exit code 1 se achar)
scan-secrets-ci:
	@echo "🔍 Escaneando segredos (modo CI)..."
	@docker run --rm -v $(PWD):/workspace -w /workspace \
		zricethezav/gitleaks:latest detect \
		--source /workspace \
		--config /workspace/.gitleaks.toml \
		--no-banner \
		--redact \
		--exit-code 1

# ============================
# Lint & Pre-commit
# ============================

# Instala pre-commit hooks (yaml lint + gitleaks)
install-pre-commit:
	@echo "Instalando pre-commit hooks..."
	@pip install pre-commit 2>/dev/null || pip3 install pre-commit
	pre-commit install
	@echo "✅ Hooks instalados: check-yaml + gitleaks"

# Roda lint (yaml validation + secrets scan)
lint:
	@echo "🔍 Rodando pre-commit (yaml + gitleaks)..."
	pre-commit run --all-files

# Pre-commit hook helper (fallback manual sem pre-commit)
install-gitleaks-hook:
	@echo "Instalando pre-commit hook para gitleaks..."
	@echo '#!/bin/bash\ndocker run --rm -v $(git rev-parse --show-toplevel):/workspace -w /workspace \
		zricethezav/gitleaks:latest detect \
		--source /workspace \
		--config /workspace/.gitleaks.toml \
		--no-banner \
		--redact \
		--exit-code 1' > .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit
	@echo "✅ Hook instalado em .git/hooks/pre-commit"
