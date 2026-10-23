.DEFAULT_GOAL := help

RUNTIME_DIR := /tmp/docpilot-dev
FRONTEND_URL := http://127.0.0.1:5173
API_URL := http://127.0.0.1:8000

.PHONY: help install frontend-install test test-fast compile check \
        up down restart dev stop status logs api-logs frontend-logs \
        docker-logs ps migrate migration run db-shell llm-up llm-down

help: ## Show available commands
	@grep -E '^[a-zA-Z0-9_-]+:.*## ' $(MAKEFILE_LIST) | \
		sed 's/:.*## / - /'

install: ## Install backend and frontend dependencies
	uv sync --locked
	npm ci --prefix frontend

frontend-install: ## Install frontend dependencies
	npm ci --prefix frontend

test: ## Run the full test suite
	uv run pytest -q --assert=plain

test-fast: ## Run chat tests
	uv run pytest -q --assert=plain tests/test_chat.py

compile: ## Check Python syntax
	@find backend tests -type f -name '*.py' -print0 | \
		xargs -0 -r uv run python -m py_compile

check: compile test ## Run syntax checks and tests

up: ## Start all Docker Compose services
	docker compose up -d

down: ## Stop and remove Compose containers (keeps named volumes)
	docker compose down

restart: ## Restart Compose services
	docker compose restart

dev: ## Start database, LLM, backend, frontend, and open browser
	@set -eu; \
	mkdir -p "$(RUNTIME_DIR)"; \
	test -x frontend/node_modules/.bin/vite || { \
		echo "Frontend dependencies missing. Run: make install"; exit 1; \
	}; \
	echo "=== Starting PostgreSQL ==="; \
	docker compose up -d postgres; \
	echo "=== Waiting for PostgreSQL ==="; \
	i=0; \
	until docker compose exec -T postgres pg_isready -U docpilot -d docpilot >/dev/null 2>&1; do \
		i=$$((i + 1)); \
		if [ $$i -ge 30 ]; then \
			echo "PostgreSQL did not become ready. Check: docker compose logs postgres"; exit 1; \
		fi; \
		sleep 2; \
	done; \
	echo "PostgreSQL is ready."; \
	echo "=== Starting optional LLM container ==="; \
	if docker compose up -d llama-server; then \
		echo "LLM container start requested; model readiness may take longer."; \
	else \
		echo "WARNING: LLM container could not start. Check: docker compose logs llama-server"; \
	fi; \
	echo "=== Starting backend ==="; \
	if ! { test -f "$(RUNTIME_DIR)/backend.pid" && kill -0 "$$(cat "$(RUNTIME_DIR)/backend.pid")" 2>/dev/null; }; then \
		rm -f "$(RUNTIME_DIR)/backend.pid"; \
		nohup sh -c 'exec env CUDA_VISIBLE_DEVICES= uv run uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload' \
			>"$(RUNTIME_DIR)/backend.log" 2>&1 </dev/null & \
		echo $$! > "$(RUNTIME_DIR)/backend.pid"; \
	fi; \
	echo "=== Starting frontend ==="; \
	if ! { test -f "$(RUNTIME_DIR)/frontend.pid" && kill -0 "$$(cat "$(RUNTIME_DIR)/frontend.pid")" 2>/dev/null; }; then \
		rm -f "$(RUNTIME_DIR)/frontend.pid"; \
		nohup sh -c 'cd frontend && exec ./node_modules/.bin/vite --host 127.0.0.1 --port 5173 --strictPort' \
			>"$(RUNTIME_DIR)/frontend.log" 2>&1 </dev/null & \
		echo $$! > "$(RUNTIME_DIR)/frontend.pid"; \
	fi; \
	echo "=== Waiting for backend and frontend ==="; \
	i=0; \
	until curl -fsS "$(API_URL)/health" >/dev/null 2>&1 && curl -fsS "$(FRONTEND_URL)" >/dev/null 2>&1; do \
		i=$$((i + 1)); \
		if [ $$i -ge 30 ]; then \
			echo "A service did not become ready. Inspect with: make logs"; \
			tail -n 30 "$(RUNTIME_DIR)/backend.log" "$(RUNTIME_DIR)/frontend.log" 2>/dev/null || true; \
			exit 1; \
		fi; \
		sleep 2; \
	done; \
	echo ""; \
	echo "DocPilot services are responding."; \
	echo "Frontend: $(FRONTEND_URL)"; \
	echo "Backend:  $(API_URL)"; \
	echo "API docs: $(API_URL)/docs"; \
	echo ""; \
	if command -v wslview >/dev/null 2>&1; then \
		wslview "$(FRONTEND_URL)" || true; \
	elif command -v cmd.exe >/dev/null 2>&1; then \
		cmd.exe /C start "" "$(FRONTEND_URL)" >/dev/null 2>&1 || true; \
	elif command -v xdg-open >/dev/null 2>&1; then \
		xdg-open "$(FRONTEND_URL)" >/dev/null 2>&1 || true; \
	else \
		echo "Open $(FRONTEND_URL) in your browser."; \
	fi

stop: ## Stop backend, frontend, and Compose services
	@for service in backend frontend; do \
		pidfile="$(RUNTIME_DIR)/$$service.pid"; \
		if test -f "$$pidfile"; then \
			pid=$$(cat "$$pidfile"); \
			if kill -0 "$$pid" 2>/dev/null; then \
				echo "Stopping $$service (PID $$pid)"; \
				kill "$$pid" 2>/dev/null || true; \
			fi; \
			rm -f "$$pidfile"; \
		fi; \
	done
	@docker compose stop

status: ## Show container and application status
	@docker compose ps
	@echo ""
	@for service in backend frontend; do \
		pidfile="$(RUNTIME_DIR)/$$service.pid"; \
		if test -f "$$pidfile" && kill -0 "$$(cat "$$pidfile")" 2>/dev/null; then \
			echo "$$service: running (PID $$(cat "$$pidfile"))"; \
		else \
			echo "$$service: not running"; \
		fi; \
	done
	@echo ""
	@curl -fsS "$(API_URL)/health" || true
	@echo ""

logs: ## Follow backend and frontend logs
	@mkdir -p "$(RUNTIME_DIR)"
	@touch "$(RUNTIME_DIR)/backend.log" "$(RUNTIME_DIR)/frontend.log"
	tail -n 100 -f "$(RUNTIME_DIR)/backend.log" "$(RUNTIME_DIR)/frontend.log"

api-logs: ## Follow backend logs
	@mkdir -p "$(RUNTIME_DIR)"
	@touch "$(RUNTIME_DIR)/backend.log"
	tail -n 100 -f "$(RUNTIME_DIR)/backend.log"

frontend-logs: ## Follow frontend logs
	@mkdir -p "$(RUNTIME_DIR)"
	@touch "$(RUNTIME_DIR)/frontend.log"
	tail -n 100 -f "$(RUNTIME_DIR)/frontend.log"

docker-logs: ## Follow Docker Compose logs
	docker compose logs -f

ps: ## Show Docker Compose status
	docker compose ps

llm-up: ## Start the LLM container
	docker compose up -d llama-server

llm-down: ## Stop the LLM container
	docker compose stop llama-server

migrate: ## Apply database migrations
	uv run alembic upgrade head

migration: ## Create a migration (usage: make migration MSG="description")
	@test -n "$(MSG)" || (echo 'Usage: make migration MSG="describe the change"'; exit 1)
	uv run alembic revision --autogenerate -m "$(MSG)"

run: ## Run backend in the foreground
	uv run uvicorn app.main:app --app-dir backend --reload

db-shell: ## Open PostgreSQL shell
	docker compose exec postgres psql -U docpilot -d docpilot
