# Aura Hub Project Makefile
# =========================
# Usage: make <target>

.DEFAULT_GOAL := help

PYTHON       ?= python
PIP          ?= $(PYTHON) -m pip
DOCKER       ?= docker compose
FRONTEND_DIR ?= frontend

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------
.PHONY: help

help: ## Show available commands
	@echo Aura Hub Project - Available Commands
	@echo =====================================
	@echo.
	@echo Setup:
	@echo   make install               Install Python dependencies
	@echo.
	@echo Docker:
	@echo   make docker-build          Build Docker images
	@echo   make docker-build-no-cache Build Docker images without cache
	@echo   make docker-up             Build and start all services
	@echo   make docker-down           Stop all services
	@echo   make docker-rebuild        Rebuild all services without cache
	@echo   make docker-logs           Follow service logs
	@echo   make docker-ps             Show service status
	@echo   make docker-clean          Delete containers and persisted volumes
	@echo.
	@echo Maintenance:
	@echo   make bootstrap             Initialize SQLite and Qdrant
	@echo   make clean                 Remove cache and build artifacts

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
.PHONY: install

install: ## Install Python dependencies
	$(PIP) install -r requirements.txt

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------
.PHONY: docker-build docker-build-no-cache docker-up docker-down
.PHONY: docker-rebuild docker-logs docker-ps docker-clean

docker-build: ## Build Docker images
	$(DOCKER) build

docker-build-no-cache: ## Build Docker images without cache
	$(DOCKER) build --no-cache

docker-up: ## Build and start all services
	$(DOCKER) up -d --build

docker-down: ## Stop all services without deleting volumes
	$(DOCKER) down --remove-orphans

docker-rebuild: ## Rebuild all images without cache
	$(DOCKER) down --remove-orphans
	$(DOCKER) build --no-cache
	$(DOCKER) up -d --force-recreate

docker-logs: ## Follow Docker Compose logs
	$(DOCKER) logs -f

docker-ps: ## Show Docker Compose service status
	$(DOCKER) ps

docker-clean: ## Delete containers, networks, and persisted volumes
	@echo WARNING: This command deletes SQLite and Qdrant persisted data.
	$(DOCKER) down -v --remove-orphans

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
.PHONY: bootstrap

bootstrap: ## Initialize database tables and Qdrant collection
	$(PYTHON) scripts/bootstrap.py

# ---------------------------------------------------------------------------
# Clean
# ---------------------------------------------------------------------------
.PHONY: clean clean-pyc clean-test clean-frontend

clean-pyc: ## Remove Python bytecode and cache directories
	$(PYTHON) -c "from pathlib import Path; import shutil; [shutil.rmtree(p, ignore_errors=True) for p in Path('.').rglob('__pycache__')]; [p.unlink(missing_ok=True) for p in Path('.').rglob('*.pyc')]; [p.unlink(missing_ok=True) for p in Path('.').rglob('*.pyo')]"

clean-test: ## Remove test and quality-tool artifacts
	$(PYTHON) -c "from pathlib import Path; import shutil; [shutil.rmtree(Path(p), ignore_errors=True) for p in ['.pytest_cache', '.mypy_cache', '.ruff_cache', 'htmlcov']]; Path('.coverage').unlink(missing_ok=True)"

clean-frontend: ## Remove Next.js build artifacts
	$(PYTHON) -c "from pathlib import Path; import shutil; shutil.rmtree(Path('$(FRONTEND_DIR)') / '.next', ignore_errors=True)"

clean: clean-pyc clean-test clean-frontend ## Remove cache and build artifacts
