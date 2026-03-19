.PHONY: help install quickstart lint lint-fix format format-check test test-be test-fe test-cov build ci clean

BACKEND  := backend
FRONTEND := frontend
VENV     := $(BACKEND)/.venv/bin
VENV_REL := .venv/bin

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ── Install ──────────────────────────────────────────────────────────

install: ## Install all dependencies (backend + frontend)
	cd $(BACKEND) && python3 -m venv .venv && $(VENV)/pip install -r requirements.txt
	cd $(FRONTEND) && yarn install

# ── Quick Start ──────────────────────────────────────────────────────

quickstart: ## One-command dev setup: env, deps, infra, backend + frontend
	@echo "==> Copying .env.example → .env (if missing)"
	@test -f .env || cp .env.example .env
	@echo "==> Installing dependencies"
	@$(MAKE) install
	@echo "==> Starting MongoDB and Redis via Docker"
	@docker compose up -d mongodb redis 2>/dev/null || echo "Docker unavailable — start MongoDB and Redis manually"
	@echo "==> Waiting for MongoDB..."
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		mongosh --eval "db.runCommand({ping:1})" --quiet 2>/dev/null && break || sleep 2; \
	done
	@echo ""
	@echo "✓ Ready! Start the servers in two terminals:"
	@echo "  Terminal 1:  cd backend && source .venv/bin/activate && uvicorn app.main:app --reload"
	@echo "  Terminal 2:  cd frontend && yarn dev"
	@echo ""
	@echo "  App:     http://localhost:5173"
	@echo "  API:     http://localhost:8000"
	@echo "  Swagger: http://localhost:8000/docs"
	@echo ""
	@echo "Note: S3/MinIO is optional (files stored locally in backend/media/)."
	@echo "      Redis is optional (notifications disabled if unavailable)."
	@echo "      Google OAuth credentials are required — see .env for setup instructions."

# ── Lint ─────────────────────────────────────────────────────────────

lint: ## Run linters (ruff + eslint + prettier check)
	$(VENV)/ruff check $(BACKEND)/app $(BACKEND)/tests
	cd $(FRONTEND) && yarn run check

lint-fix: ## Auto-fix lint issues
	$(VENV)/ruff check $(BACKEND)/app $(BACKEND)/tests --fix
	cd $(FRONTEND) && yarn run lint:fix

# ── Format ───────────────────────────────────────────────────────────

format: ## Format all code (ruff + prettier)
	$(VENV)/ruff format $(BACKEND)/app $(BACKEND)/tests
	cd $(FRONTEND) && yarn run format

format-check: ## Check formatting without changes
	$(VENV)/ruff format --check $(BACKEND)/app $(BACKEND)/tests
	cd $(FRONTEND) && yarn run format:check

# ── Test ─────────────────────────────────────────────────────────────

test: test-be test-fe ## Run all tests

test-be: ## Run backend tests
	cd $(BACKEND) && $(VENV_REL)/python -m pytest

test-fe: ## Run frontend tests
	cd $(FRONTEND) && yarn test

test-cov: ## Run all tests with coverage
	cd $(BACKEND) && $(VENV_REL)/python -m pytest --cov=app --cov-report=term-missing
	cd $(FRONTEND) && yarn run test:coverage

# ── Build ────────────────────────────────────────────────────────────

build: ## Build frontend for production
	cd $(FRONTEND) && yarn build

# ── CI ───────────────────────────────────────────────────────────────

ci: lint format-check test build ## Full CI pipeline: lint + format-check + test + build

# ── Clean ────────────────────────────────────────────────────────────

clean: ## Remove build artifacts
	rm -rf $(FRONTEND)/dist $(FRONTEND)/coverage
	find $(BACKEND) -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
