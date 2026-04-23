# Makefile for MCProjSim project
# The structure for the Makefile is built on separating timestamp dependencies and command targets
# Each command target may depend on one or more timestamp files that encapsulate the logic for when
# to re-run certain tasks based on file changes.

.PHONY: help dev install clean-venv reinstall run test test-short test-param test-html test-probabilistic \
test-probabilistic-full lint format typecheck migrate init-db check \
pre-commit clean maintainer-clean docs pdf pdf-sprint-planning pdf-pandoc gen-examples \
figs docs-serve docs-container-build docs-container-start docs-container-stop docs-container-restart \
docs-container-status docs-container-logs build container-build container-build-corporate container-build-public \
container-up container-down container-logs \
container-restart container-shell container-clean container-clean-container-volumes container-clean-images \
container-volume-info container-rebuild ghcr-login ghcr-logout ghcr-push ghcr-clean pull-all \
 black flake8 mypy pyright _check figs

# Makefile itself as a dependency to ensure it is re-evaluated when changed
# NOTE: This requires GNU Make 4.3+ and MacOS ships with vGNU Make 3.81 due to licensing issues
# and then this line will be silently ignored.´unless you have upgrade make via brew or similar.	
.EXTRA_PREREQS := $(firstword $(MAKEFILE_LIST))

# Make behavior
.DEFAULT_GOAL := help

# Get full path to bash
SHELL := $(shell which bash)

# Delete target files on error to prevent stale timestamps
.DELETE_ON_ERROR:

# Use a single shell for each target to allow multi-line commands and better error handling
.ONESHELL:

# Colors for output
BLACK := \033[0;30m
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[1;33m
BLUE := \033[0;34m
MAGENTA := \033[0;35m
CYAN := \033[0;36m
WHITE := \033[1;37m

# Variations
DARKGRAY := \033[1;30m
BRIGHTRED := \033[1;31m
BRIGHTGREEN := \033[1;32m
DARKYELLOW := \033[0;33m
BRIGHTBLUE := \033[1;34m
BRIGHTMAGENTA := \033[1;35m
BRIGHTCYAN := \033[1;36m
LIGHTGRAY := \033[0;37m
NC := \033[0m # No Color

# Formatting
BOLD := \033[1m
UNDERLINE := \033[4m

# Proxy file for build (if needed)
PROXY_CA_FILE := CA_proxy_fw_all.pem

# ============================================================================================
# Tool availability checks
# ============================================================================================

POETRY := $(shell command -v poetry 2>/dev/null)
PODMAN := $(shell command -v podman 2>/dev/null)
PODMAN_COMPOSE := $(shell command -v podman-compose 2>/dev/null)
DOCKER := $(shell command -v docker 2>/dev/null)
DOCKER_COMPOSE := $(shell command -v docker-compose 2>/dev/null)

ifeq ($(POETRY),)
    $(error poetry not found. MacOS Install with: pip install poetry)
endif

# If both podman and docker are missing, raise an error
ifeq ($(PODMAN),)
    ifeq ($(DOCKER),)
        $(error Neither podman nor docker found. Please install one of them.)
    endif
endif

ifeq ($(PODMAN_COMPOSE),)
    ifeq ($(DOCKER_COMPOSE),)
        $(error Neither podman-compose nor docker-compose found. Please install one of them.)
    endif
endif

# Check which container engine is running and set the appropriate tool
PODMAN_RUNNING := $(shell podman info >/dev/null 2>&1 && echo "yes" || echo "no")
DOCKER_RUNNING := $(shell docker info >/dev/null 2>&1 && echo "yes" || echo "no")
NO_CONTAINER_ENGINE := $(shell if [ "$(PODMAN_RUNNING)" = "no" ] && [ "$(DOCKER_RUNNING)" = "no" ]; then echo "yes"; else echo "no"; fi)

ifeq ($(PODMAN_RUNNING),yes)
    CONTAINER_CMD := ${PODMAN}
    CONTAINER_COMPOSE_CMD := ${PODMAN_COMPOSE}
    $(info Using Podman as the container engine)
else ifeq ($(DOCKER_RUNNING),yes)
    CONTAINER_CMD := ${DOCKER}
    CONTAINER_COMPOSE_CMD := ${DOCKER_COMPOSE}
    $(info Using Docker as the container engine)
else
    $(info **WARNING** Neither Podman nor Docker engine is running. Please start one of them to use container-related targets.)
endif

# Check if we're behind a proxy (detect proxy environment variables and CA cert)
PROXY_DETECTED := no
ifneq ($(HTTP_PROXY)$(HTTPS_PROXY)$(http_proxy)$(https_proxy),)
    PROXY_DETECTED := yes
endif
ifeq ($(shell [ -f ${PROXY_CA_FILE} ] && [ -s ${PROXY_CA_FILE} ] && echo "yes"),yes)
    PROXY_DETECTED := yes
endif

ifeq ($(PROXY_DETECTED),yes)
    $(info Proxy environment detected - will use proxy CA certificate for container builds)
    DEFAULT_CONTAINER_BUILD := container-build-proxy
else
    $(info No proxy detected - will use standard container build)
    DEFAULT_CONTAINER_BUILD := container-build-standard
endif

# ============================================================================================
# Variable configurations
# ============================================================================================

# Directories
SRC_DIR := src
TEST_DIR := tests
DOCS_DIR := docs
DIST_DIR := dist
BUILD_DIR := .build

# Project settings
PROJECT := mcprojsim
APP_NAME := MCProjSim
PYPI_NAME := $(PROJECT)
VERSION := $(shell grep '^version' pyproject.toml | head -1 | cut -d'"' -f2)

# Container related settings
CONTAINER_NAME := $(PROJECT)

# Example generation
EXAMPLES_TEMPLATE := docs/examples_template.md
EXAMPLES_GENERATOR := scripts/gen-examples.sh
EXAMPLES_OUTPUT := docs/examples.md
EXAMPLE_FILES := $(wildcard examples/*.yaml) $(wildcard examples/*.txt)

# Minimum coverage percentage required
COVERAGE := 80

# Source and Test Files
SRC_FILES := $(shell find $(SRC_DIR) -name '*.py')
TEST_FILES := $(shell find $(TEST_DIR) -name 'test_*.py')
MISC_FILES := pyproject.toml README.md mypy.ini .flake8
LOCK_FILE := poetry.lock
DOCKER_SRC_FILES := Dockerfile docker-compose.yml

# Timestamp files
STAMP_DIR := .makefile-stamps
$(shell mkdir -p $(STAMP_DIR))

CONTAINER_STAMP := $(STAMP_DIR)/container-stamp
FORMAT_STAMP := $(STAMP_DIR)/format-stamp
LINT_STAMP := $(STAMP_DIR)/lint-stamp
PYRIGHT_STAMP := $(STAMP_DIR)/pyright-stamp
TYPECHECK_STAMP := $(STAMP_DIR)/typecheck-stamp
INSTALL_STAMP := $(STAMP_DIR)/install-stamp
TEST_STAMP := $(STAMP_DIR)/test-stamp
TEST_ALL_STAMP := $(STAMP_DIR)/test-all-stamp
GHCR_LOGIN_STAMP := $(STAMP_DIR)/ghcr-login-stamp

# Remove any hypen in PyPi specific version number for wheel filename compliance
PYPI_VERSION := $(shell echo $(VERSION) | tr -d '-')
BUILD_WHEEL := $(DIST_DIR)/$(PYPI_NAME)-$(PYPI_VERSION)-py3-none-any.whl
BUILD_SDIST := $(DIST_DIR)/$(PYPI_NAME)-$(PYPI_VERSION).tar.gz

# ================================================================================================
# Timestamp dependencies
# ================================================================================================
$(TEST_STAMP): $(SRC_FILES) $(TEST_FILES)
	@echo -e "$(DARKYELLOW)- Running tests in parallel with coverage check...$(NC)"
	@if poetry run pytest -n auto --cov=app --cov-report= --cov-report=xml --cov-fail-under=${COVERAGE} -s -q; then \
		touch $(TEST_STAMP); \
		echo -e "$(GREEN)✓ All non-heavy tests passed with required coverage$(NC)"; \
	else \
		echo -e "$(RED)✗ Error: Tests failed or coverage below ${COVERAGE}%$(NC)"; \
		exit 1; \
	fi

$(TEST_ALL_STAMP): $(SRC_FILES) $(TEST_FILES)
	@echo -e "$(DARKYELLOW)- Running tests in parallel with coverage check...$(NC)"
	@if poetry run pytest -m "heavy or not heavy" -n auto --cov=app --cov-report= --cov-report=xml --cov-fail-under=${COVERAGE} -s -q; then \
		touch $(TEST_ALL_STAMP); \
		echo -e "$(GREEN)✓ All tests (including heavy) passed with required coverage$(NC)"; \
	else \
		echo -e "$(RED)✗ Error: Tests failed or coverage below ${COVERAGE}%$(NC)"; \
		exit 1; \
	fi

$(FORMAT_STAMP): $(SRC_FILES) $(TEST_FILES)
	@echo -e "$(DARKYELLOW)- Running code formatter...$(NC)"
	@if poetry run black --check $(SRC_DIR) $(TEST_DIR) -q; then \
		touch $(FORMAT_STAMP); \
		echo -e "$(GREEN)✓ Format target runs successfully$(NC)"; \
	else \
		rm -f $(FORMAT_STAMP); \
		echo -e "$(RED)✗ Error: Black formatting check failed. Run 'poetry run black $(SRC_DIR) $(TEST_DIR)' to fix.$(NC)"; \
		exit 1; \
	fi

$(LINT_STAMP): $(SRC_FILES) $(TEST_FILES)
	@echo -e "$(DARKYELLOW)- Running linter...$(NC)"
	@if poetry run flake8 $(SRC_DIR) $(TEST_DIR); then \
		echo -e "$(GREEN)✓ Flake8 linting passed$(NC)"; \
	else \
		echo -e "$(RED)✗ Error: Flake8 linting failed$(NC)"; \
		exit 1; \
	fi
	@touch $(LINT_STAMP)
	@echo -e "$(GREEN)✓ Flake8 lint run successfully$(NC)"


$(PYRIGHT_STAMP): $(SRC_FILES) $(TEST_FILES)
	@if poetry run pyright --version >/dev/null 2>&1; then \
		echo -e "$(DARKYELLOW)- Running pyright for additional linting...$(NC)"; \
		if poetry run pyright --level error $(SRC_DIR) $(TEST_DIR); then \
			echo -e "$(GREEN)✓ Pyright linting passed$(NC)"; \
		else \
			echo -e "$(RED)✗ Error: Pyright linting failed$(NC)"; \
			exit 1; \
		fi \
	else \
		echo -e "$(YELLOW)⚠️  Warning: pyright not found, skipping pyright linting. Install with 'poetry install --with dev' for enhanced linting.$(NC)"; \
	fi
	@touch $(PYRIGHT_STAMP)
	@echo -e "$(GREEN)✓ Pyright lint run successfully$(NC)"

$(TYPECHECK_STAMP): $(SRC_FILES) $(TEST_FILES)
	@echo -e "$(DARKYELLOW)- Running type checker...$(NC)"
	@if poetry run mypy src/ tests/ --strict; then \
		echo -e "$(GREEN)✓ Mypy type checking passed$(NC)"; \
	else \
		echo -e "$(RED)✗ Error: Mypy type checking failed$(NC)"; \
		exit 1; \
	fi
	@touch $(TYPECHECK_STAMP)

$(INSTALL_STAMP): pyproject.toml $(LOCK_FILE)
	@echo -e "$(DARKYELLOW)- Installing dependencies...$(NC)"
	@poetry config virtualenvs.in-project true  ## make sure venv is created in project dir
	@poetry install
	@cp .env.example .env 2>/dev/null || true  ## copy example env if .env does not exist
	@sleep 1  ## ensure timestamp difference
	@touch $(INSTALL_STAMP)
	@echo -e "$(GREEN)✓ Project dependencies installed$(NC)"

$(BUILD_WHEEL) $(BUILD_SDIST): $(SRC_FILES) $(TEST_FILES) $(MISC_FILES)
	@echo -e "$(DARKYELLOW)- Building project packages...$(NC)"
	@if poetry build; then \
		echo -e "$(GREEN)✓ Packages built successfully$(NC)"; \
	else \
		echo -e "$(RED)✗ Error: Package build failed$(NC)"; \
		exit 1; \
	fi
	@echo -e "$(DARKYELLOW)- Verifying packages with twine...$(NC)"
	@if poetry run twine check dist/*; then \
		echo -e "$(GREEN)✓ 📦 Package verification passed$(NC)"; \
	else \
		echo -e "$(RED)✗ Error: Package verification failed$(NC)"; \
		exit 1; \
	fi

$(LOCK_FILE): pyproject.toml  ## Ensure poetry.lock is up to date if dependencies change
	@echo -e "$(DARKYELLOW)- Regenerating lock file to ensure consistency...$(NC)"
	@poetry lock
	@touch $(LOCK_FILE)

$(DB_FILE): ## Setup the database if it does not exist
	@if [ ! -f $(DB_FILE) ]; then \
		$(MAKE) migrate; \
		$(MAKE) init-db; \
	fi

$(GHCR_LOGIN_STAMP): 
	@if [ -z "$(GHCR_TOKEN)" ]; then \
		echo -e "$(RED)✗ Error: GHCR_TOKEN environment variable is not se. Please set GHCR_TOKEN with a valid GitHub Personal Access Token.$(NC)"; \
		exit 1; \
	fi
	@if [ -f $(GHCR_LOGIN_STAMP) ] && [ $$(find $(GHCR_LOGIN_STAMP) -mmin -120) ]; then \
		echo -e "$(GREEN)✓ Already logged in to GHCR recently.$(NC)"; \
		exit 0; \
	else \
		echo -e "$(DARKYELLOW)- Logging in to GitHub Container Registry...$(NC)"; \
		if $(CONTAINER_CMD) login ghcr.io -u $(GITHUB_USER) -p $(GHCR_TOKEN) >/dev/null 2>&1; then \
			echo -e "$(GREEN)✓ Login to GitHub successful!$(NC)"; \
			touch $(GHCR_LOGIN_STAMP) ; \
		else \
			echo -e "$(RED)✗ Login failed. Please check your GHCR_TOKEN.$(NC)"; \
			rm -f $(GHCR_LOGIN_STAMP); \
			exit 1; \
		fi \
	fi	

# ============================================================================================
# Help Target
# ============================================================================================

# Defines a function to print a section of the help message.
# Arg 1: Section title
# Arg 2: A pipe-separated list of targets for the section
define print_section
	@echo ""
	@echo -e "$(BRIGHTCYAN)$1:$(NC)"
	@grep -E '^($(2)):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-22s$(NC) %s\n", $$1, $$2}' | sort
endef

help: ## Show this help message
	@echo -e "$(DARKYELLOW)OneSelect - Makefile Targets$(NC)"
	@$(call print_section,Project Setup & Development,dev|install|reinstall|run)
	@$(call print_section,Code Quality,check|lint|format|typecheck|pre-commit)
	@$(call print_section,Testing,test|test-short|test-param|test-html|test-probabilistic|test-probabilistic-full)
	@$(call print_section,Database,migrate|init-db)
	@$(call print_section,Build & Documentation,build)
	@$(call print_section,Container Management,container-build|container-build-corporate|container-build-public|container-up|container-down|container-logs|container-restart|container-shell|container-rebuild|container-volume-info|container-clean)
	@$(call print_section,Cleanup,clean|clean-venv|maintainer-clean)
	@$(call print_section,GitHub Container Registry,ghcr-login|ghcr-logout|ghcr-push)
	@$(call print_section,Git Operations,pull-all)
	@echo ""

# ============================================================================================
# Development Environment Targets
# ============================================================================================
dev: $(INSTALL_STAMP) $(DB_FILE) ## Setup complete development environment
	@echo -e "$(GREEN)✓ Development environment ready!$(NC)"
	@echo -e "$(YELLOW)- TIP! $(BLUE)Run 'make test' to verify, 'make run' to start the server, or 'make container-up' for containerized deployment$(NC)"

install: $(INSTALL_STAMP) ## Install project dependencies and setup virtual environment
	@:

reinstall: clean-venv clean install ## Reinstall the project from scratch
	@echo -e "$(GREEN)✓ Project reinstalled successfully$(NC)"

# =============================================================================================
# Testing Targets
# The targets: test-short, test-param, and test-html will always be run on invocation.
# Plain test target wilkl ony be run when needed (source- or test-file changes)
# =============================================================================================
test: $(TEST_STAMP) ## Run tests in parallel, terminal coverage report
	@:

test-all: $(TEST_ALL_STAMP) ## Run all tests (including heavy) in parallel, terminal coverage report
	@:

test-short: ## Run tests in parallel with minimal output, no coverage
	@echo -e "$(DARKYELLOW)- Starting short test without coverage...$(NC)"	
	@poetry run pytest -n auto -q --no-cov

test-html: ## Run tests in parallel, HTML & XML coverage report
	@echo -e "$(DARKYELLOW)- Starting parallel test coverage...$(NC)"
	@poetry run pytest -q -n auto --cov=src/$(PROJECT) --cov-report=xml --cov-report=html --cov-fail-under=${COVERAGE}
	@echo -e "$(GREEN)✓ Test coverage report generated in \"coverage.xml\" and \"htmlcov/index.html\"$(NC)"

test-probabilistic: ## Run probabilistic simulation verification tests (CI suite, ~3 min)
	@echo -e "$(DARKYELLOW)- Running probabilistic verification tests (CI suite)...$(NC)"
	@if poetry run pytest -n auto -m "probabilistic" --no-cov -v -x; then \
		echo -e "$(GREEN)✓ Probabilistic verification tests passed$(NC)"; \
	else \
		echo -e "$(RED)✗ Error: Probabilistic verification tests failed$(NC)"; \
		exit 1; \
	fi

test-probabilistic-full: ## Run full probabilistic verification suite (slow, ~40 min)
	@echo -e "$(DARKYELLOW)- Running full probabilistic verification suite...$(NC)"
	@if poetry run pytest -n auto -m "probabilistic or probabilistic_full" --no-cov -v; then \
		echo -e "$(GREEN)✓ Full probabilistic verification suite passed$(NC)"; \
	else \
		echo -e "$(RED)✗ Error: Full probabilistic verification suite failed$(NC)"; \
		exit 1; \
	fi

# ============================================================================================
# Code Quality Targets
# ============================================================================================
check:
	$(MAKE) -j 4 _check

_check: format lint pyright typecheck ## Run all code quality checks
	@:

lint flake8: $(LINT_STAMP) ## Run linting checks with flake8
	@: 

pyright: $(PYRIGHT_STAMP) ## Run additional linting checks with pyright
	@:

format black: $(FORMAT_STAMP) ## Format code with black
	@:

typecheck mypy: $(TYPECHECK_STAMP) ## Run strict type checking with mypy
	@:

pre-commit: $(INSTALL_STAMP) ## Run pre-commit checks (format, lint, typecheck, pyright)
	@echo -e "$(DARKYELLOW)Running pre-commit checks...$(NC)"
	@$(MAKE) -j 4 check
	@$(MAKE) test-short
	@echo -e "$(GREEN)✓ All pre-commit checks passed$(NC)"

# ============================================================================================
# Build Package Targets
# ============================================================================================
build: $(INSTALL_STAMP) check test docs $(BUILD_WHEEL) $(BUILD_SDIST) ## Build the project packages
	@:

# ============================================================================================
# Cleanup Targets
# ============================================================================================
really-clean: ## Perform a deep clean including virtual environment, containers, database files, and all build artifacts
	@echo -e "$(DARKYELLOW)- Performing really deep clean...$(NC)"
	@$(MAKE) clean-venv
	-@$(MAKE) container-clean 2>/dev/null || true
	-@$(MAKE) clean 2>/dev/null || true
	@echo -e "$(GREEN)✓ Deep clean completed$(NC)"

clean-venv: ## Remove the virtual environment
	@echo -e "$(DARKYELLOW)- Removing virtual environment...$(NC)"
	@rm -rf .venv ${INSTALL_STAMP}
	@echo -e "$(GREEN)✓ Virtual environment removed$(NC)"

clean: ## Clean up build artifacts, caches, and timestamp files. Keep the .venv intact.
	@echo -e "$(DARKYELLOW)- Cleaning build artifacts and caches...$(NC)"
	@rm -rf .pytest_cache
	@rm -rf $(DIST_DIR)
	@rm -rf $(BUILD_DIR)
	@rm -rf .coverage coverage.xml
	@rm -rf htmlcov
	@rm -rf site
	@rm -rf $(USER_GUIDE_BUILD_DIR)
	@rm -rf .mypy_cache
	@rm -rf $(STAMP_DIR)
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@echo -e "$(GREEN)✓ Clean completed$(NC)"

maintainer-clean: ## Perform a thorough cleanup including virtual environment, containers and database files
	@echo -e "$(DARKYELLOW)- Performing deep clean...$(NC)"
	@$(MAKE) clean-venv
	@$(MAKE) clean
	-@$(MAKE) container-clean 2>/dev/null
	@rm -rf .env
	@echo -e "$(GREEN)✓ Deep clean completed$(NC)"


# ============================================================================================
# Container Management Targets
# IS only responsible for building and managing the mcprojsim command line tool container image 
# and not the documentation container
# ============================================================================================

container-engine-check:
	@if [ "$(NO_CONTAINER_ENGINE)" = "yes" ]; then \
        echo -e "$(YELLOW)⚠️  Warning: No container engine detected. Skipping container operation. Please start Podman or Docker.$(NC)"; \
        exit 1; \
    fi

# Alias for backwards compatibility and convenience
container-build: container-build-auto  | container-engine-check ## Build container (auto-detects proxy environment)
	@:

# Auto-detect and build with appropriate configuration
container-build-auto: | container-engine-check ## Automatically detect proxy and build with appropriate configuration
	@echo -e "$(DARKYELLOW)- Auto-detecting build environment...$(NC)"
	@$(MAKE) $(DEFAULT_CONTAINER_BUILD)

# Build with proxy CA certificate (for internal/proxy environments)
container-build-proxy: | container-engine-check ## Build container image with proxy CA certificate for proxy environments
	@echo -e "$(DARKYELLOW)- Building container image with proxy CA support...$(NC)"
	@if [ ! -s $(PROXY_CA_FILE) ]; then \
		echo -e "$(RED)✗ Error: $(PROXY_CA_FILE) not found$(NC)"; \
		echo -e "$(YELLOW)  Copy your proxy CA certificate to the project root as $(PROXY_CA_FILE)$(NC)"; \
		exit 1; \
	fi
	@$(CONTAINER_CMD) build --build-arg USE_PROXY_CA=true --secret id=proxy_ca,src=$(PROXY_CA_FILE) -t $(CONTAINER_NAME):latest -t $(CONTAINER_NAME):$(VERSION) .
	@touch $(CONTAINER_STAMP)
	@echo -e "$(GREEN)✓ Container image built with proxy CA support$(NC)"

# Build public/standard version (no proxy CA)
container-build-standard: | container-engine-check ## Build container image without proxy CA (for public/standard deployments)
	@echo -e "$(DARKYELLOW)- Building public container image (no proxy CA)...$(NC)"
	@$(CONTAINER_CMD) build --build-arg USE_PROXY_CA=false -t $(CONTAINER_NAME):latest -t $(CONTAINER_NAME):$(VERSION) .
	@touch $(CONTAINER_STAMP)
	@echo -e "$(GREEN)✓ Public container image built$(NC)"


# ============================================================================================
# GitHub Container Registry Targets
# ============================================================================================
ghcr-login: $(GHCR_LOGIN_STAMP) ## Login to GitHub Container Registry via Podman/Docker
	@:

ghcr-push: $(GHCR_LOGIN_STAMP) $(CONTAINER_STAMP)  ## Push container image to GitHub Container Registry
	@if [ -z "$(GITHUB_USER)" ]; then \
        echo -e "$(RED)✗ Error: GITHUB_USER environment variable is not set."; \
        echo -e "  Please set GITHUB_USER as an environment variable or add as argument: make container-push GITHUB_USER=\"XXXXX\"$(NC)"; \
        exit 1; \
	fi
	@echo -e "$(DARKYELLOW)- Checking if image version $(VERSION) already exists on GHCR...$(NC)"
	@if $($(CONTAINER_CMD)) manifest inspect ghcr.io/$(GITHUB_USER)/$(CONTAINER_NAME):$(VERSION) >/dev/null 2>&1; then \
        echo -e "$(YELLOW)⚠️  Warning: Image $(CONTAINER_NAME):$(VERSION) already exists in the registry. Skipping push.$(NC)"; \
        exit 1; \
    fi
	@echo -e "$(DARKYELLOW)- Pushing image $(CONTAINER_NAME):$(VERSION) and tagging as latest to GitHub Container Registry...$(NC)"
	@$(CONTAINER_CMD) tag $(CONTAINER_NAME):$(VERSION) ghcr.io/$(GITHUB_USER)/$(CONTAINER_NAME):$(VERSION)
	@$(CONTAINER_CMD) tag $(CONTAINER_NAME):$(VERSION) ghcr.io/$(GITHUB_USER)/$(CONTAINER_NAME):latest
	@if $(CONTAINER_CMD) push ghcr.io/$(GITHUB_USER)/$(CONTAINER_NAME):$(VERSION) && $(CONTAINER_CMD) push ghcr.io/$(GITHUB_USER)/$(CONTAINER_NAME):latest; then \
        echo -e "$(GREEN)✓ Image pushed successfully.$(NC)"; \
	else \
        echo -e "$(RED)✗ Error: Failed to push image to GHCR.$(NC)"; \
        exit 1; \
    fi

ghcr-logout: ## Logout from GitHub Container Registry
	@if [ ! -f $(GHCR_LOGIN_STAMP) ]; then \
		echo -e "$(YELLOW)⚠️  Warning: Not logged in to GHCR. Skipping logout.$(NC)"; \
		exit 1; \
	fi
	@echo -e "$(DARKYELLOW)- Logging out from GitHub Container Registry...$(NC)"
	@$(CONTAINER_CMD) logout ghcr.io
	@rm -f $(GHCR_LOGIN_STAMP)
	@echo -e "$(GREEN)✓ Logged out from GHCR$(NC)"

ghcr-clean: ghcr-logout container-clean-images ## Clean up GHCR login and local images
	@:

# ============================================================================================
# Git Operations Targets
# ============================================================================================
pull-all: ## Pull all local branches that exist on origin
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo -e "$(RED)✗ Error: Working directory is not clean. Please commit or stash your changes before pulling.$(NC)"; \
		exit 1; \
	fi
	@echo -e "$(DARKYELLOW)- Fetching latest from origin...$(NC)"
	@git fetch --prune origin
	@current_branch=$$(git rev-parse --abbrev-ref HEAD); \
	for branch in $$(git branch --format='%(refname:short)'); do \
		if git show-ref --verify --quiet refs/remotes/origin/$$branch; then \
			echo -e "$(BLUE)  Pulling $$branch...$(NC)"; \
			git checkout $$branch && git pull origin $$branch || echo -e "$(RED)  ✗ Failed to pull $$branch$(NC)"; \
		else \
			echo -e "$(YELLOW)  ⚠ Skipping $$branch (not on origin)$(NC)"; \
		fi; \
	done; \
	git checkout $$current_branch
	@echo -e "$(GREEN)✓ All branches pulled$(NC)"

# ============================================================================================
# Create PDFs of design documentation for distribution
# Calls the default target od the Makefile in `desig-ides/`
# ============================================================================================
pdf-design: ## Create a PDF of the design documentation for distribution
	@echo -e "$(DARKYELLOW)- Building design documentation PDFs...$(NC)"
	@$(MAKE) -C design-ideas >/dev/null 
	@echo -e "$(GREEN)✓ Design documentation PDFs created in design-docs/dist/$(NC)"
	
docs: ## Build the documentation site with MkDoc
	@$(MAKE) -C $(DOCS_DIR)

pdfs: ## Build the documentation site with MkDoc
	@$(MAKE) -j 4 -C $(DOCS_DIR) pdf-docs pdf-api-ref

docs-serve: ## Serve the documentation site locally with live reload
	@$(MAKE) -C $(DOCS_DIR) serve

# ============================================================================================
# Render PNG figures from HTML source
# ============================================================================================
FIG_SOURCES := $(wildcard assets/fig-*.html)
FIG_TARGETS := $(patsubst assets/fig-%.html,assets/fig-%.png,$(FIG_SOURCES))

 $(info FIG_SOURCES: $(FIG_SOURCES))
 $(info FIG_TARGETS: $(FIG_TARGETS))

figs: ## Render PNG figures from HTML source
	@./scripts/mkfigs.sh -s assets -o assets

### End of Makefile

