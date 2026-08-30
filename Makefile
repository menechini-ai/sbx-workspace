# Define variáveis buscando direto do seu Git local
GIT_NAME := $(shell git config user.name 2>/dev/null || echo "Claude Agent")
GIT_EMAIL := $(shell git config user.email 2>/dev/null || echo "claude-agent@local.internal")

.PHONY: up down run code logs clean build build-base scan-secrets scan-secrets-ci

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
run:
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

# Pre-commit hook helper
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
