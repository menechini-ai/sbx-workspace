COMPOSE := docker compose --env-file ../../.env
AI_MEMORY_VOLUME ?= ../../Vault/ai-memory:/data

.PHONY: up down logs clean

up:
	AI_MEMORY_VOLUME=$(AI_MEMORY_VOLUME) $(COMPOSE) up -d  --remove-orphans

down:
	AI_MEMORY_VOLUME=$(AI_MEMORY_VOLUME) $(COMPOSE) down

logs:
	AI_MEMORY_VOLUME=$(AI_MEMORY_VOLUME) $(COMPOSE) logs -f

clean:
	AI_MEMORY_VOLUME=$(AI_MEMORY_VOLUME) $(COMPOSE) down -v
