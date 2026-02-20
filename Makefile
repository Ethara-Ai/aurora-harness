SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c

# Colors for output
ECHO := printf '%b\n'
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
CYAN := \033[36m
RESET := \033[0m

# Required uv version
REQUIRED_UV_VERSION := 0.8.13

.PHONY: build patch-venv format lint clean help check-uv-version

# Default target
.DEFAULT_GOAL := help


check-uv-version:
	@$(ECHO) "$(YELLOW)Checking uv version...$(RESET)"
	@UV_VERSION=$$(uv --version | cut -d' ' -f2); \
	REQUIRED_VERSION=$(REQUIRED_UV_VERSION); \
	if [ "$$(printf '%s\n' "$$REQUIRED_VERSION" "$$UV_VERSION" | sort -V | head -n1)" != "$$REQUIRED_VERSION" ]; then \
		$(ECHO) "$(RED)Error: uv version $$UV_VERSION is less than required $$REQUIRED_VERSION$(RESET)"; \
		$(ECHO) "$(YELLOW)Please update uv with: uv self update$(RESET)"; \
		exit 1; \
	fi; \
	$(ECHO) "$(GREEN)uv version $$UV_VERSION meets requirements$(RESET)"

build: check-uv-version
	@$(ECHO) "$(CYAN)Setting up OpenHands V1 development environment...$(RESET)"
	@$(ECHO) "$(YELLOW)Syncing submodules...$(RESET)"
	@git submodule update --init --recursive
	@$(ECHO) "$(YELLOW)Installing dependencies with uv sync --dev...$(RESET)"
	@uv sync --dev
	@$(ECHO) "$(GREEN)Dependencies installed successfully.$(RESET)"
	@$(ECHO) "$(YELLOW)Setting up pre-commit hooks...$(RESET)"
	@uv run pre-commit install
	@$(ECHO) "$(GREEN)Pre-commit hooks installed successfully.$(RESET)"
	@$(MAKE) patch-venv
	@$(ECHO) "$(GREEN)Build complete! Development environment is ready.$(RESET)"

patch-venv:
	@$(ECHO) "$(YELLOW)Applying venv patches for multi-swe-bench compatibility...$(RESET)"
	@SITE_PKG=$$(ls -d .venv/lib/python*/site-packages 2>/dev/null | head -1); \
	if [ -z "$$SITE_PKG" ]; then \
		$(ECHO) "$(RED)Error: .venv not found. Run 'make build' first.$(RESET)"; exit 1; \
	fi; \
	QISKIT_FILE="$$SITE_PKG/multi_swe_bench/harness/repos/python/__init__.py"; \
	if [ -f "$$QISKIT_FILE" ]; then \
		sed -i '' 's|from multi_swe_bench.harness.repos.python.qiskit import \*|from multi_swe_bench.harness.repos.python.Qiskit import *|g' "$$QISKIT_FILE"; \
		$(ECHO) "$(GREEN)  ✓ Fixed qiskit → Qiskit import case$(RESET)"; \
	else \
		$(ECHO) "$(YELLOW)  ⚠ qiskit fix: file not found, skipping$(RESET)"; \
	fi; \
	DOCKER_UTIL="$$SITE_PKG/multi_swe_bench/utils/docker_util.py"; \
	if [ -f "$$DOCKER_UTIL" ]; then \
		sed -i '' 's|docker_client = docker.from_env()|docker_client = docker.from_env(timeout=600)|g' "$$DOCKER_UTIL"; \
		$(ECHO) "$(GREEN)  ✓ Fixed Docker client timeout to 600s$(RESET)"; \
	else \
		$(ECHO) "$(YELLOW)  ⚠ docker_util fix: file not found, skipping$(RESET)"; \
	fi
	@$(ECHO) "$(GREEN)Venv patches applied successfully.$(RESET)"

format:
	@$(ECHO) "$(YELLOW)Formatting code with uv format...$(RESET)"
	@uv run ruff format
	@$(ECHO) "$(GREEN)Code formatted successfully.$(RESET)"

lint:
	@$(ECHO) "$(YELLOW)Linting code with ruff...$(RESET)"
	@uv run ruff check --fix
	@$(ECHO) "$(GREEN)Linting completed.$(RESET)"

clean:
	@$(ECHO) "$(YELLOW)Cleaning up cache files...$(RESET)"
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@rm -rf .pytest_cache .ruff_cache .mypy_cache 2>/dev/null || true
	@$(ECHO) "$(GREEN)Cache files cleaned.$(RESET)"
