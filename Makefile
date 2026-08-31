SERVICES := ai-memory claude-code opencode 9router

.PHONY: up down logs clean build cc code $(SERVICES)

# Targets vazios para Make não reclamar com: make down ai-memory
ai-memory:; @true
claude-code:; @true
opencode:; @true
9router:; @true

# make up SERVICE=ai-memory / make up cc / make up code
up:
	@if [ -z "$(filter $(SERVICES),$(SERVICE))" ]; then \
		echo "Uso: make up SERVICE=<servico>"; \
		echo "Servicos: $(SERVICES)"; \
		echo "Atalhos: make cc (=claude-code), make code (=opencode)"; \
		exit 1; \
	fi
	cd scripts/$(SERVICE) && make up

# Atalhos
cc:
	cd scripts/claude-code && make up

code:
	cd scripts/opencode && make up

# make down SERVICE=ai-memory | make down (todos)
down:
	@if [ -n "$(filter $(SERVICES),$(SERVICE))" ]; then \
		cd scripts/$(SERVICE) && make down; \
	else \
		for svc in $(SERVICES); do \
			echo "Parando $$svc..."; \
			cd scripts/$$svc && make down && cd ../..; \
		done; \
	fi

# make logs SERVICE=ai-memory
logs:
	@if [ -z "$(filter $(SERVICES),$(SERVICE))" ]; then \
		echo "Uso: make logs SERVICE=<servico>"; \
		echo "Servicos: $(SERVICES)"; \
		exit 1; \
	fi
	cd scripts/$(SERVICE) && make logs

# make clean SERVICE=ai-memory | make clean (todos)
clean:
	@if [ -n "$(filter $(SERVICES),$(SERVICE))" ]; then \
		cd scripts/$(SERVICE) && make clean; \
	else \
		for svc in $(SERVICES); do \
			echo "Limpando $$svc..."; \
			cd scripts/$$svc && make clean && cd ../..; \
		done; \
	fi

# make build
build:
	docker compose -f scripts/claude-code/docker-compose.yaml build
	docker compose -f scripts/opencode/docker-compose.yaml build
