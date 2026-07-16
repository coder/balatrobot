.DEFAULT_GOAL := help
.PHONY: help install lint format typecheck quality fixtures test all

# Colors (ANSI)
YELLOW := \033[33m
GREEN  := \033[32m
BLUE   := \033[34m
RED    := \033[31m
RESET  := \033[0m

# Print helper
PRINT = printf "%b\n"

# Worker counts tuned per platform
XDIST_CLI_WORKERS ?= 2
ifndef XDIST_LUA_WORKERS
ifeq ($(BALATROBOT_PLATFORM),darwin)
  XDIST_LUA_WORKERS := 6
else ifeq ($(BALATROBOT_PLATFORM),docker)
  XDIST_LUA_WORKERS := 4
else
  XDIST_LUA_WORKERS := 2
endif
endif

help: ## Show this help message
	@$(PRINT) "$(BLUE)BalatroBot Development Makefile$(RESET)"
	@$(PRINT) ""
	@$(PRINT) "$(YELLOW)Available targets:$(RESET)"
	@printf "  $(GREEN)%-18s$(RESET) %s\n" "help"      "Show this help message"
	@printf "  $(GREEN)%-18s$(RESET) %s\n" "install"   "Install balatrobot and all dependencies (including dev)"
	@printf "  $(GREEN)%-18s$(RESET) %s\n" "lint"      "Run ruff linter (check only)"
	@printf "  $(GREEN)%-18s$(RESET) %s\n" "format"    "Run formatters (ruff, mdformat, stylua)"
	@printf "  $(GREEN)%-18s$(RESET) %s\n" "typecheck" "Run type checkers (Python and Lua)"
	@printf "  $(GREEN)%-18s$(RESET) %s\n" "quality"   "Run all code quality checks"
	@printf "  $(GREEN)%-18s$(RESET) %s\n" "fixtures"  "Generate fixtures"
	@printf "  $(GREEN)%-18s$(RESET) %s\n" "test"      "Run all tests"
	@printf "  $(GREEN)%-18s$(RESET) %s\n" "all"       "Run all code quality checks and tests"

install: ## Install balatrobot and all dependencies (including dev)
	@$(PRINT) "$(YELLOW)Installing all dependencies...$(RESET)"
	uv sync --group dev --group test

lint: ## Run ruff linter (check only)
	@$(PRINT) "$(YELLOW)Running ruff linter...$(RESET)"
	ruff check --fix --select I .
	ruff check --fix .

format: ## Run formatters (ruff, mdformat, stylua)
	@$(PRINT) "$(YELLOW)Running ruff formatter...$(RESET)"
	ruff check --select I --fix .
	ruff format .
	@$(PRINT) "$(YELLOW)Running mdformat formatter...$(RESET)"
	mdformat --number --exclude "CHANGELOG.md" --exclude ".venv/**" --exclude "vendors/**" ./docs README.md .agents/skills/balatrobot/SKILL.md
	@if command -v stylua >/dev/null 2>&1; then \
		$(PRINT) "$(YELLOW)Running stylua formatter...$(RESET)"; \
		stylua src/lua; \
	else \
		$(PRINT) "$(BLUE)Skipping stylua formatter (stylua not found)$(RESET)"; \
	fi

typecheck: ## Run type checkers (Python and Lua)
	@$(PRINT) "$(YELLOW)Running Python type checker...$(RESET)"
	@ty check
	@if command -v lua-language-server >/dev/null 2>&1 && [ -f .luarc.json ]; then \
		$(PRINT) "$(YELLOW)Running Lua type checker...$(RESET)"; \
		lua-language-server --check="$(CURDIR)" \
			--configpath="$(CURDIR)/.luarc.json" 2>/dev/null; \
	else \
		$(PRINT) "$(BLUE)Skipping Lua type checker (lua-language-server not found or .luarc.json missing)$(RESET)"; \
	fi

quality: lint typecheck format ## Run all code quality checks
	@$(PRINT) "$(GREEN)✓ All checks completed$(RESET)"

fixtures: ## Generate fixtures
	@$(PRINT) "$(YELLOW)Generating all fixtures...$(RESET)"
	python tests/fixtures/generate.py

test: ## Run all tests
	@$(PRINT) "$(YELLOW)Running tests/cli with $(XDIST_CLI_WORKERS) workers...$(RESET)"
	pytest -n $(XDIST_CLI_WORKERS) tests/cli
	@$(PRINT) "$(YELLOW)Running tests/lua with $(XDIST_LUA_WORKERS) workers...$(RESET)"
	pytest -n $(XDIST_LUA_WORKERS) tests/lua


all: lint format typecheck test ## Run all code quality checks and tests
	@$(PRINT) "$(GREEN)✓ All checks completed$(RESET)"
