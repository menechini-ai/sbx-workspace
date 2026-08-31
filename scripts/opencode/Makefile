COMPOSE := docker compose --env-file ../../.env
GIT_NAME := $(shell git config user.name 2>/dev/null || echo "Agent")
GIT_EMAIL := $(shell git config user.email 2>/dev/null || echo "agent@local")

.PHONY: up down run logs clean

up:
	$(COMPOSE) up -d

run:
	@echo "Iniciando OpenCode..."
	@GIT_AUTHOR_NAME="$(GIT_NAME)" \
	GIT_AUTHOR_EMAIL="$(GIT_EMAIL)" \
	GIT_COMMITTER_NAME="$(GIT_NAME)" \
	GIT_COMMITTER_EMAIL="$(GIT_EMAIL)" \
	$(COMPOSE) run --rm opencode

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

clean:
	$(COMPOSE) down -v
