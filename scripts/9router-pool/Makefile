COMPOSE := docker compose --env-file ../../.env
BUILD := docker compose build --no-cache

.PHONY: up down logs clean

up:
	$(COMPOSE) up -d  --remove-orphans

build:
	$(BUILD)

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

clean:
	$(COMPOSE) down -v
