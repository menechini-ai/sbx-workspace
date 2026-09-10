POOL := python3 pool.py

.PHONY: list test sync create scale backup clean

# ============================================================================
# Pool Manager
# ============================================================================

list:
	$(POOL) list

test:
	$(POOL) test

sync:
	$(POOL) sync

create:
	$(POOL) create

scale:
	$(POOL) scale $(N)

backup:
	$(POOL) backup

clean:
	$(POOL) clean
	@volumes=$$(docker volume ls --filter name=9router -q 2>/dev/null); \
	if [ -n "$$volumes" ]; then \
		docker volume rm -f $$volumes; \
	fi

slave-add:
	$(POOL) slave add $(NAME) $(HOST)

slave-delete:
	$(POOL) slave delete $(NAME)
