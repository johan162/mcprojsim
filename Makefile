# Makefile for MCProjSim project
# The structure for the Makefile is built on separating timestamp dependencies and command targets
# Each command target may depend on one or more timestamp files that encapsulate the logic for when
# to re-run certain tasks based on file changes.

.PHONY: help dev install clean-venv reinstall run test test-short test-param test-html lint format typecheck migrate init-db check \
pre-commit clean maintainer-clean docs pdf pdf-sprint-planning pdf-pandoc gen-examples docs-serve docs-container-build docs-container-start docs-container-stop docs-container-restart docs-container-status docs-container-logs build container-build container-build-corporate container-build-public container-up container-down container-logs \
container-restart container-shell container-clean container-clean-container-volumes container-clean-images \
container-volume-info container-rebuild ghcr-login ghcr-logout ghcr-push ghcr-clean pull-all


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
DOCS_CONTAINER_SCRIPT := ./scripts/docs-contctl.sh

# Server configuration
SERVER_HOST := 0.0.0.0
# SERVER_PORT := 8000
DOCS_PORT := 8100

# Project settings
PROJECT := mcprojsim
APP_NAME := MCProjSim
PYPI_NAME := mcprojsim
VERSION := $(shell grep '^version' pyproject.toml | head -1 | cut -d'"' -f2)
CONTAINER_NAME := $(PROJECT)

# User guide PDF output path
USER_GUIDE_PDF := mcprojsim_user_guide-v$(VERSION).pdf
USER_GUIDE_PANDOC_PDF := user_guide_pandoc.pdf
USER_GUIDE_DIST_DIR := .build/user-guide
USER_GUIDE_TEMPLATE := docs/user_guide/report_template.tex
USER_GUIDE_CONCAT_MD := $(USER_GUIDE_DIST_DIR)/user_guide_concat.md
USER_GUIDE_BODY_TEX := $(USER_GUIDE_DIST_DIR)/user_guide_body.tex
USER_GUIDE_TEX := $(USER_GUIDE_DIST_DIR)/user_guide_report.tex
USER_GUIDE_PDF_BUILT := $(USER_GUIDE_DIST_DIR)/user_guide_report.pdf

# Doc files for User Guide PDF generation
USER_GUIDE_DOCS := \
	docs/user_guide/getting_started.md \
	docs/user_guide/introduction.md \
	docs/user_guide/your_first_project.md  \
	docs/user_guide/uncertainty_factors.md  \
	docs/user_guide/task_estimation.md  \
	docs/user_guide/risks.md  \
	docs/user_guide/project_files.md  \
	docs/user_guide/constrained.md  \
	docs/user_guide/running_simulations.md  \
	docs/user_guide/interpreting_results.md  \
	docs/user_guide/mcp-server.md \
	docs/examples.md

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
DOC_FILES := mkdocs.yml $(shell find $(DOCS_DIR) -name '*.md' -o -name '*.yml' -o -name '*.yaml')
MISC_FILES := pyproject.toml README.md mypy.ini .flake8
LOCK_FILE := poetry.lock
DOCKER_SRC_FILES := Dockerfile docker-compose.yml

# Timestamp files
STAMP_DIR := .makefile-stamps
$(shell mkdir -p $(STAMP_DIR))

CONTAINER_STAMP := $(STAMP_DIR)/container-stamp
DOC_STAMP := $(STAMP_DIR)/docs-stamp
FORMAT_STAMP := $(STAMP_DIR)/format-stamp
LINT_STAMP := $(STAMP_DIR)/lint-stamp
TYPECHECK_STAMP := $(STAMP_DIR)/typecheck-stamp
INSTALL_STAMP := $(STAMP_DIR)/install-stamp
TEST_STAMP := $(STAMP_DIR)/test-stamp
GHCR_LOGIN_STAMP := $(STAMP_DIR)/ghcr-login-stamp

# Build package files
DIST_DIR := dist

# Generic builddir for interim build artifacts (e.g. for PDF generation)
BUILD_DIR := .build

# Design ideas PDF output path
DESIGN_IDEAS_DIR := design-ideas
SPRINT_PLANNING_MD := $(DESIGN_IDEAS_DIR)/sprint-based-planning.md
SPRINT_PLANNING_PDF := $(DESIGN_IDEAS_DIR)/sprint-based-planning.pdf
SPRINT_PLANNING_DIST_DIR := $(BUILD_DIR)/design-ideas/sprint-based-planning
SPRINT_PLANNING_TEMPLATE := $(DESIGN_IDEAS_DIR)/report_template.tex
SPRINT_PLANNING_PANDOC_FILTER := scripts/pandoc_sprint_planning_table_widths.lua
SPRINT_PLANNING_BODY_TEX := $(SPRINT_PLANNING_DIST_DIR)/sprint-based-planning_body.tex
SPRINT_PLANNING_TEX := $(SPRINT_PLANNING_DIST_DIR)/sprint-based-planning_report.tex
SPRINT_PLANNING_PDF_BUILT := $(SPRINT_PLANNING_DIST_DIR)/sprint-based-planning_report.pdf

# Remove any hypen in PyPi specifi version number for wheel filename compliance
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
		echo -e "$(GREEN)✓ All tests passed with required coverage$(NC)"; \
	else \
		echo -e "$(RED)✗ Error: Tests failed or coverage below ${COVERAGE}%$(NC)"; \
		exit 1; \
	fi

$(FORMAT_STAMP): $(SRC_FILES) $(TEST_FILES)
	@echo -e "$(DARKYELLOW)- Running code formatter...$(NC)"
	@poetry run black --check $(SRC_DIR) $(TEST_DIR) -q
	@touch $(FORMAT_STAMP)
	@echo -e "$(GREEN)✓ Format target runs successfully$(NC)"

$(CONTAINER_STAMP): $(SRC_FILES) $(TEST_FILES) $(DOCKER_SRC_FILES) $(MISC_FILES) $(INSTALL_STAMP) | container-engine-check
	@echo -e "$(DARKYELLOW)- Building container image...$(NC)"
	@$(CONTAINER_COMPOSE_CMD) build
	@$(CONTAINER_CMD) tag oneselect-backend:latest oneselect-backend:$(VERSION)
	@touch $(CONTAINER_STAMP)
	@echo -e "$(GREEN)✓ Container image built and tagged as oneselect-backend:$(VERSION)$(NC)"

$(DOC_STAMP): $(DOC_FILES)
	@echo -e "$(DARKYELLOW)- Building documentation...$(NC)"
	@if poetry run mkdocs build -q; then \
		touch $(DOC_STAMP); \
		echo -e "$(GREEN)✓ Documentation built successfully$(NC)"; \
	else \
		echo -e "$(RED)✗ Error: Documentation build failed$(NC)"; \
		exit 1; \
	fi

$(LINT_STAMP): $(SRC_FILES) $(TEST_FILES)
	@echo -e "$(DARKYELLOW)- Running linter...$(NC)"
	@poetry run flake8 $(SRC_DIR) $(TEST_DIR)
# Run pyright as an additional linting step if available
	@if command -v pyright >/dev/null 2>&1; then \
		echo -e "$(DARKYELLOW)- Running pyright for additional linting...$(NC)"; \
		if poetry run pyright $(SRC_DIR) $(TEST_DIR); then \
			echo -e "$(GREEN)✓ Pyright linting passed$(NC)"; \
		else \
			echo -e "$(RED)✗ Error: Pyright linting failed$(NC)"; \
			exit 1; \
		fi \
	else \
		echo -e "$(YELLOW)⚠️  Warning: pyright not found, skipping pyright linting. Install with 'npm install -g pyright' for enhanced linting.$(NC)"; \
	fi
	@touch $(LINT_STAMP)
	@echo -e "$(GREEN)✓ Lint run successfully$(NC)"

$(TYPECHECK_STAMP): $(SRC_FILES) $(TEST_FILES)
	@echo -e "$(DARKYELLOW)- Running type checker...$(NC)"
	@poetry run mypy src/ tests/ --strict
	@touch $(TYPECHECK_STAMP)
	@echo -e "$(GREEN)✓ Typecheck target runs successfully$(NC)"

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
	@$(call print_section,Testing,test|test-short|test-param|test-html)
	@$(call print_section,Database,migrate|init-db)
	@$(call print_section,Build & Documentation,build|docs|pdf|pdf-sprint-planning|pdf-pandoc|gen-examples|docs-serve|docs-container-build|docs-container-start|docs-container-stop|docs-container-restart|docs-container-status|docs-container-logs|docs-deploy)
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
test: $(INSTALL_STAMP) $(TEST_STAMP) ## Run tests in parallel, terminal coverage report
	@:

test-short: $(INSTALL_STAMP) ## Run tests in parallel with minimal output, no coverage
	@echo -e "$(DARKYELLOW)- Starting short test without coverage...$(NC)"	
	@poetry run pytest -n auto -q --no-cov

test-html: $(INSTALL_STAMP) ## Run tests in parallel, HTML & XML coverage report
	@echo -e "$(DARKYELLOW)- Starting parallel test coverage...$(NC)"
	@poetry run pytest -q -n auto --cov=src/mcprojsime --cov-report=xml --cov-report=html --cov-fail-under=${COVERAGE}
	@echo -e "$(GREEN)✓ Test coverage report generated in \"coverage.xml\" and \"htmlcov/index.html\"$(NC)"

# ============================================================================================
# Code Quality Targets
# ============================================================================================
check: format lint typecheck ## Run all code quality checks
	@:

lint: $(LINT_STAMP) ## Run linting checks with flake8
	@:

format: $(FORMAT_STAMP) ## Format code with black
	@:

typecheck: $(TYPECHECK_STAMP) ## Run strict type checking with mypy
	@:

pre-commit: $(INSTALL_STAMP) ## Run pre-commit checks (format, lint, typecheck)
	@echo -e "$(DARKYELLOW)Running pre-commit checks...$(NC)"
	@$(MAKE) check
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
	@rm -rf $(USER_GUIDE_DIST_DIR)
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
# Documentation Targets
# ============================================================================================
docs: $(DOC_STAMP) ## Build the project documentation with MkDocs
	@:

gen-examples: $(EXAMPLES_OUTPUT) ## Regenerate docs/examples.md from template
	@:

$(EXAMPLES_OUTPUT): $(EXAMPLES_TEMPLATE) $(EXAMPLES_GENERATOR) $(EXAMPLE_FILES) $(INSTALL_STAMP)
	@echo -e "$(DARKYELLOW)- Generating examples documentation from template...$(NC)"
	@bash $(EXAMPLES_GENERATOR)

## Target that updates the version number in the LaTeX template for the user guide PDF generation
update-version: ## Update the version number in the LaTeX template for the user guide PDF generation
	@echo -e "$(DARKYELLOW)- Updating version number in LaTeX template...$(NC)"
	@sed -i.bak -E 's/\\texttt{mcprojsim}, v[0-9.]+/\\texttt{mcprojsim}, v$(VERSION)/g' $(USER_GUIDE_TEMPLATE)
	@if grep -q "\\\texttt{mcprojsim}, v$(VERSION)" $(USER_GUIDE_TEMPLATE); then \
		echo -e "$(GREEN)✓ Version number updated successfully in LaTeX template$(NC)"; \
	else \
		echo -e "$(RED)✗ Error: Failed to update version number in LaTeX template$(NC)"; \
		exit 1; \
	fi
	@rm -f $(USER_GUIDE_TEMPLATE).bak
	

pdf: $(USER_GUIDE_PDF)  ## Build the user guide PDF
	@:

$(USER_GUIDE_PDF): $(USER_GUIDE_DOCS) $(USER_GUIDE_TEMPLATE) | update-version  ## Build user guide via custom LaTeX report template + pdflatex
	@echo -e "$(DARKYELLOW)- Building user guide PDF via LaTeX report pipeline...$(NC)"
	@mkdir -p $(USER_GUIDE_DIST_DIR)
	@echo -e "$(DARKYELLOW)  - Concatenating markdown sources...$(NC)"
	@cat $(USER_GUIDE_DOCS) > $(USER_GUIDE_CONCAT_MD)
	@echo -e "$(DARKYELLOW)  - Converting concatenated markdown to LaTeX body...$(NC)"
	@pandoc --from=markdown --to=latex --top-level-division=chapter --syntax-highlighting=none $(USER_GUIDE_CONCAT_MD) -o $(USER_GUIDE_BODY_TEX)
	@sed -i.bak 's/\\def\\LTcaptype{none}/\\def\\LTcaptype{table}/g' $(USER_GUIDE_BODY_TEX)
	@rm -f $(USER_GUIDE_BODY_TEX).bak
	@echo -e "$(DARKYELLOW)  - Injecting body into handcrafted LaTeX template...$(NC)"
	@awk -v body="$(USER_GUIDE_BODY_TEX)" '\
		/%%__USER_GUIDE_CONTENT__%%/ { while ((getline line < body) > 0) print line; close(body); inserted=1; next } \
		{ print } \
		END { if (!inserted) { print "Template placeholder %%__USER_GUIDE_CONTENT__%% not found" > "/dev/stderr"; exit 2 } }' \
		$(USER_GUIDE_TEMPLATE) > $(USER_GUIDE_TEX)
	@echo -e "$(DARKYELLOW)  - Compiling PDF with xelatex (2 passes for references/TOC)...$(NC)"
	@xelatex -interaction=nonstopmode -halt-on-error -output-directory $(USER_GUIDE_DIST_DIR) $(USER_GUIDE_TEX) >/dev/null
	@xelatex -interaction=nonstopmode -halt-on-error -output-directory $(USER_GUIDE_DIST_DIR) $(USER_GUIDE_TEX) >/dev/null
	@cp $(USER_GUIDE_PDF_BUILT) $(USER_GUIDE_PDF)
	@echo -e "$(GREEN)✓ User guide PDF built: $(USER_GUIDE_PDF)$(NC)"

pdf-sprint-planning: $(SPRINT_PLANNING_PDF) ## Build the sprint-based planning design PDF
	@:

$(SPRINT_PLANNING_PDF): $(SPRINT_PLANNING_MD) $(SPRINT_PLANNING_TEMPLATE) $(SPRINT_PLANNING_PANDOC_FILTER)
	@echo -e "$(DARKYELLOW)- Building sprint-based planning PDF via LaTeX report pipeline...$(NC)"
	@mkdir -p $(SPRINT_PLANNING_DIST_DIR)
	@echo -e "$(DARKYELLOW)  - Converting markdown source to LaTeX body...$(NC)"
	@pandoc --from=markdown --to=latex --top-level-division=chapter --syntax-highlighting=none --lua-filter=$(SPRINT_PLANNING_PANDOC_FILTER) $(SPRINT_PLANNING_MD) -o $(SPRINT_PLANNING_BODY_TEX)
	@sed -i.bak 's/\\def\\LTcaptype{none}/\\def\\LTcaptype{table}/g' $(SPRINT_PLANNING_BODY_TEX)
	@rm -f $(SPRINT_PLANNING_BODY_TEX).bak
	@echo -e "$(DARKYELLOW)  - Injecting body into design-ideas LaTeX template...$(NC)"
	@awk -v body="$(SPRINT_PLANNING_BODY_TEX)" '\
		/%%__DESIGN_CONTENT__%%/ { while ((getline line < body) > 0) print line; close(body); inserted=1; next } \
		{ print } \
		END { if (!inserted) { print "Template placeholder %%__DESIGN_CONTENT__%% not found" > "/dev/stderr"; exit 2 } }' \
		$(SPRINT_PLANNING_TEMPLATE) > $(SPRINT_PLANNING_TEX)
	@echo -e "$(DARKYELLOW)  - Compiling PDF with xelatex (2 passes for references/TOC)...$(NC)"
	@xelatex -interaction=nonstopmode -halt-on-error -output-directory $(SPRINT_PLANNING_DIST_DIR) $(SPRINT_PLANNING_TEX) >/dev/null
	@xelatex -interaction=nonstopmode -halt-on-error -output-directory $(SPRINT_PLANNING_DIST_DIR) $(SPRINT_PLANNING_TEX) >/dev/null
	@cp $(SPRINT_PLANNING_PDF_BUILT) $(SPRINT_PLANNING_PDF)
	@rm -f $(SPRINT_PLANNING_DIST_DIR)/*.aux $(SPRINT_PLANNING_DIST_DIR)/*.log $(SPRINT_PLANNING_DIST_DIR)/*.fls $(SPRINT_PLANNING_DIST_DIR)/*.fdb_latexmk 2>/dev/null || true
	@echo -e "$(GREEN)✓ Sprint-based planning PDF built: $(SPRINT_PLANNING_PDF)$(NC)"

pdf-pandoc: $(USER_GUIDE_PANDOC_PDF) ## Build fallback user guide PDF directly with Pandoc
	@:

$(USER_GUIDE_PANDOC_PDF): $(USER_GUIDE_DOCS)
	@echo -e "$(DARKYELLOW)- Building fallback user guide PDF directly with Pandoc...$(NC)"
	@pandoc --pdf-engine=xelatex -V mainfont="Arial Unicode MS" -V monofont="DejaVu Sans Mono" \
		-V geometry:top=2cm,left=2.5cm,right=1.8cm,bottom=1.5cm \
		$(USER_GUIDE_DOCS) -o $(USER_GUIDE_PANDOC_PDF)

docs-serve: docs ## Serve the project documentation locally with MkDocs
	@echo -e "$(BLUE)Serving documentation on http://localhost:$(DOCS_PORT)$(NC)"
	@poetry run mkdocs serve -a localhost:$(DOCS_PORT)

container-engine-check:
	@if [ "$(NO_CONTAINER_ENGINE)" = "yes" ]; then \
        echo -e "$(YELLOW)⚠️  Warning: No container engine detected. Skipping container operation. Please start Podman or Docker.$(NC)"; \
        exit 1; \
    fi

docs-container-build: | container-engine-check ## Build the containerized documentation image
	@MCPROJSIM_DOCS_PORT=$(DOCS_PORT) $(DOCS_CONTAINER_SCRIPT) build

docs-container-start: | container-engine-check ## Start the containerized documentation server
	@MCPROJSIM_DOCS_PORT=$(DOCS_PORT) $(DOCS_CONTAINER_SCRIPT) start

docs-container-stop: | container-engine-check ## Stop the containerized documentation server
	@MCPROJSIM_DOCS_PORT=$(DOCS_PORT) $(DOCS_CONTAINER_SCRIPT) stop

docs-container-restart: | container-engine-check ## Restart the containerized documentation server
	@MCPROJSIM_DOCS_PORT=$(DOCS_PORT) $(DOCS_CONTAINER_SCRIPT) restart

docs-container-status: | container-engine-check ## Show status for the containerized documentation server
	@MCPROJSIM_DOCS_PORT=$(DOCS_PORT) $(DOCS_CONTAINER_SCRIPT) status

docs-container-logs: | container-engine-check ## Show logs for the containerized documentation server
	@MCPROJSIM_DOCS_PORT=$(DOCS_PORT) $(DOCS_CONTAINER_SCRIPT) logs --follow

docs-deploy: ## Build and deploy documentation to GitHub Pages
	@echo -e "$(DARKYELLOW)- Deploying documentation to GitHub Pages...$(NC)"
	@if poetry run mkdocs gh-deploy --force; then \
		echo -e "$(GREEN)✓ Documentation deployed successfully$(NC)"; \
	else \
		echo -e "$(RED)✗ Error: Documentation deployment failed$(NC)"; \
		exit 1; \
	fi

# ============================================================================================
# Container Management with Podman/Docker Targets
# ============================================================================================
# container-build: $(CONTAINER_STAMP) container-build-public ## Build the container image for the application and tag it with the current version
# 	@:

container-up: $(CONTAINER_STAMP)  | container-engine-check ## Start the container in detached mode
	@echo -e "$(DARKYELLOW)- Starting containers...$(NC)"
	@$(CONTAINER_COMPOSE_CMD) up -d
	@echo -e "$(GREEN)✓ Containers started$(NC)"

container-down: | container-engine-check ## Stop and remove the running container
	@echo -e "$(DARKYELLOW)- Stopping containers...$(NC)"
	@$(CONTAINER_COMPOSE_CMD) down
	@echo -e "$(GREEN)✓ Containers stopped$(NC)"

container-logs: | container-engine-check ## Follow the logs of the running container
	@$(CONTAINER_COMPOSE_CMD) logs -f

container-restart: $(CONTAINER_STAMP) | container-engine-check ## Restart the running container
	@echo -e "$(DARKYELLOW)- Restarting containers...$(NC)"
	@$(CONTAINER_COMPOSE_CMD) restart
	@echo -e "$(GREEN)✓ Containers restarted$(NC)"

container-shell: $(CONTAINER_STAMP) | container-engine-check ## Open an interactive shell inside the running container
	@$(CONTAINER_COMPOSE_CMD) exec $(SERVICE_NAME) /bin/shz

container-clean: container-clean-container-volumes container-clean-images ## Clean up all containers and images

container-clean-container-volumes: | container-engine-check ## Remove all containers, volumes and prune the system
	@echo -e "$(DARKYELLOW)- Cleaning up containers and volumes...$(NC)"
	@$(CONTAINER_COMPOSE_CMD) down -v
	@$(CONTAINER_CMD) system prune -f
	@echo -e "$(GREEN)✓ Containers and volumes removed$(NC)"

container-clean-images: container-down | container-engine-check ## Remove all oneselect container images
	@echo -e "$(DARKYELLOW)- Removing all oneselect images...$(NC)"
	@$(CONTAINER_CMD) rmi -f $$($(CONTAINER_CMD) images --filter "reference=oneselect*" -q) 2>/dev/null || true
	@rm -f $(CONTAINER_STAMP)
	@echo -e "$(GREEN)✓ Images removed$(NC)"

container-volume-info: | container-engine-check ## Inspect the container volume used for persistent data storage
	@echo -e "$(DARKYELLOW)- Listing container volumes...$(NC)"
	@$(CONTAINER_CMD) volume ls
	@$(CONTAINER_CMD) volume inspect $(PROJECT)_oneselect-data

container-rebuild: | container-engine-check ## Rebuild container from scratch with auto-detection
	@echo -e "$(DARKYELLOW)- Rebuilding container from scratch...$(NC)"
	@$(MAKE) container-down || true
	@rm -f $(CONTAINER_STAMP)
	@$(MAKE) container-build-auto
	@echo -e "$(GREEN)✓ Container rebuilt$(NC)"

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


### End of Makefile

