.DEFAULT_GOAL := help
.PHONY: help install lint format typecheck quality fixtures test all

# Colors for output
YELLOW := \033[33m
GREEN := \033[32m
BLUE := \033[34m
RED := \033[31m
RESET := \033[0m

help: ## Show this help message
	@echo "$(BLUE)BalatroBot Development Makefile$(RESET)"
	@echo ""
	@echo "$(YELLOW)Available targets:$(RESET)"
	@printf "  $(GREEN)%-18s$(RESET) %s\n" "help" "Show this help message"
	@printf "  $(GREEN)%-18s$(RESET) %s\n" "install" "Install balatrobot and all dependencies (including dev)"
	@printf "  $(GREEN)%-18s$(RESET) %s\n" "lint" "Run ruff linter (check only)"
	@printf "  $(GREEN)%-18s$(RESET) %s\n" "format" "Run ruff and mdformat formatters"
	@printf "  $(GREEN)%-18s$(RESET) %s\n" "typecheck" "Run type checker"
	@printf "  $(GREEN)%-18s$(RESET) %s\n" "quality" "Run all code quality checks"
	@printf "  $(GREEN)%-18s$(RESET) %s\n" "fixtures" "Generate fixtures"
	@printf "  $(GREEN)%-18s$(RESET) %s\n" "test" "Run all tests"
	@printf "  $(GREEN)%-18s$(RESET) %s\n" "all" "Run all code quality checks and tests"

install: ## Install balatrobot and all dependencies (including dev)
	@echo "$(YELLOW)Installing all dependencies...$(RESET)"
	uv sync --group dev --group test

lint: ## Run ruff linter (check only)
	@echo "$(YELLOW)Running ruff linter...$(RESET)"
	ruff check --fix --select I .
	ruff check --fix .

format: ## Run ruff and mdformat formatters
	@echo "$(YELLOW)Running ruff formatter...$(RESET)"
	ruff check --select I --fix .
	ruff format .
	@echo "$(YELLOW)Running mdformat formatter...$(RESET)"
	mdformat ./docs README.md CLAUDE.md
	@if command -v stylua >/dev/null 2>&1; then \
		echo "$(YELLOW)Running stylua formatter...$(RESET)"; \
		stylua src/lua; \
	else \
		echo "$(BLUE)Skipping stylua formatter (stylua not found)$(RESET)"; \
	fi

typecheck: ## Run type checker
	@echo "$(YELLOW)Running Python type checker...$(RESET)"
	@ty check
	@if command -v lua-language-server >/dev/null 2>&1 && [ -f .luarc.json ]; then \
		echo "$(YELLOW)Running Lua type checker...$(RESET)"; \
		lua-language-server --check balatrobot.lua src/lua --configpath="$(CURDIR)/.luarc.json" 2>/dev/null; \
	else \
		echo "$(BLUE)Skipping Lua type checker (lua-language-server not found or .luarc.json missing)$(RESET)"; \
	fi

quality: lint typecheck format ## Run all code quality checks
	@echo "$(GREEN)✓ All checks completed$(RESET)"

fixtures: ## Generate fixtures
	@echo "$(YELLOW)Starting Balatro...$(RESET)"
	balatrobot --fast --debug
	@echo "$(YELLOW)Generating all fixtures...$(RESET)"
	python tests/fixtures/generate.py

test: ## Run all tests
	@echo "$(YELLOW)Running tests/cli...$(RESET)"
	pytest tests/cli
	@echo "$(YELLOW)Running tests/lua...$(RESET)"
	pytest -n 6 tests/lua

all: lint format typecheck test ## Run all code quality checks and tests
	@echo "$(GREEN)✓ All checks completed$(RESET)"
