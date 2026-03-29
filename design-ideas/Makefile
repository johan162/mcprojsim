# Makefile for Design Documentation in MCProjSim project

.PHONY: pdf-design help clean

# Makefile itself as a dependency to ensure it is re-evaluated when changed
# NOTE: This requires GNU Make 4.3+ and MacOS ships with vGNU Make 3.81 due to licensing issues
# and then this line will be silently ignored.´unless you have upgrade make via brew or similar.	
.EXTRA_PREREQS := $(firstword $(MAKEFILE_LIST))

# Make behavior
.DEFAULT_GOAL := pdf-design

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
RESET := $(NC)

# Formatting
BOLD := \033[1m
UNDERLINE := \033[4m

# ============================================================================================
# Variable configurations
# ============================================================================================

# Build dir
BUILD_DIR := .build
BUILD_DESIGN_DIR := $(BUILD_DIR)/design-ideas
SCRIPTS_DIR := ../scripts
DESIGN_IDEAS_DIR := .

# Generic Latex template to use for all design documents - 
# it will have a placeholder for content injection and some basic styling, 
# but the content will be generated from the respective markdown files 
# for each design document
DESIGN_LATEX_TEMPLATE := $(DESIGN_IDEAS_DIR)/design_template.tex

# Sprint planning design document specific variables
SPRINT_PLANNING_BASENAME := $(DESIGN_IDEAS_DIR)/sprint-based-planning
SPRINT_PLANNING_MD := $(DESIGN_IDEAS_DIR)/$(SPRINT_PLANNING_BASENAME).md
SPRINT_PLANNING_PDF := $(DESIGN_IDEAS_DIR)/$(SPRINT_PLANNING_BASENAME).pdf
SPRINT_PLANNING_DIST_DIR := $(BUILD_DESIGN_DIR)/$(SPRINT_PLANNING_BASENAME)
SPRINT_PLANNING_PANDOC_FILTER := $(SCRIPTS_DIR)/pandoc_sprint_planning_table_widths.lua
SPRINT_PLANNING_BODY_TEX := $(SPRINT_PLANNING_DIST_DIR)/$(SPRINT_PLANNING_BASENAME)_body.tex
SPRINT_PLANNING_TEX := $(SPRINT_PLANNING_DIST_DIR)/$(SPRINT_PLANNING_BASENAME)_report.tex
SPRINT_PLANNING_PDF_BUILT := $(SPRINT_PLANNING_DIST_DIR)/$(SPRINT_PLANNING_BASENAME)_report.pdf
SPRINT_PLANNING_PANDOC_OPTS := --lua-filter=$(SPRINT_PLANNING_PANDOC_FILTER)
SPRINT_PLANNING_EXTRA_DEPS := $(SPRINT_PLANNING_PANDOC_FILTER)

# T-shirt category design document specific variables
TSHIRT_CATEGORY_BASENAME := $(DESIGN_IDEAS_DIR)/tshirt-categories
TSHIRT_CATEGORY_MD := $(DESIGN_IDEAS_DIR)/$(TSHIRT_CATEGORY_BASENAME).md
TSHIRT_CATEGORY_PDF := $(DESIGN_IDEAS_DIR)/$(TSHIRT_CATEGORY_BASENAME).pdf
TSHIRT_CATEGORY_DIST_DIR := $(BUILD_DESIGN_DIR)/$(TSHIRT_CATEGORY_BASENAME)
TSHIRT_CATEGORY_BODY_TEX := $(TSHIRT_CATEGORY_DIST_DIR)/$(TSHIRT_CATEGORY_BASENAME)_body.tex
TSHIRT_CATEGORY_TEX := $(TSHIRT_CATEGORY_DIST_DIR)/$(TSHIRT_CATEGORY_BASENAME)_report.tex
TSHIRT_CATEGORY_PDF_BUILT := $(TSHIRT_CATEGORY_DIST_DIR)/$(TSHIRT_CATEGORY_BASENAME)_report.pdf
TSHIRT_CATEGORY_PANDOC_OPTS :=
TSHIRT_CATEGORY_EXTRA_DEPS :=

# Multi-phased simulaton design document specific variables
MULTIPHASE_SIM_BASENAME := $(DESIGN_IDEAS_DIR)/multiphase-simulation
MULTIPHASE_SIM_MD := $(DESIGN_IDEAS_DIR)/$(MULTIPHASE_SIM_BASENAME).md
MULTIPHASE_SIM_PDF := $(DESIGN_IDEAS_DIR)/$(MULTIPHASE_SIM_BASENAME).pdf
MULTIPHASE_SIM_DIST_DIR := $(BUILD_DESIGN_DIR)/$(MULTIPHASE_SIM_BASENAME)
MULTIPHASE_SIM_BODY_TEX := $(MULTIPHASE_SIM_DIST_DIR)/$(MULTIPHASE_SIM_BASENAME)_body.tex
MULTIPHASE_SIM_TEX := $(MULTIPHASE_SIM_DIST_DIR)/$(MULTIPHASE_SIM_BASENAME)_report.tex
MULTIPHASE_SIM_PDF_BUILT := $(MULTIPHASE_SIM_DIST_DIR)/$(MULTIPHASE_SIM_BASENAME)_report.pdf
MULTIPHASE_SIM_PANDOC_OPTS :=
MULTIPHASE_SIM_EXTRA_DEPS :=

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

# ============================================================================================
# Makefile Macro for PDF generation from markdown design documents
# This macro defines the rules for generating a PDF from a markdown file using a LaTeX template.
# It takes care of the following steps:
# 1. Convert the markdown file to a LaTeX body using pandoc.
# 2. Inject the generated LaTeX body into the provided LaTeX template at the placeholder.
# 3. Extract the version number and title from the markdown file and replace the corresponding placeholders in the LaTeX template.
# 4. Compile the final LaTeX file to generate the PDF.
# Arguments: 1. A prefix for the variables related to the specific design document (e.g., SPRINT_PLANNING)
#            2. A human-readable name for the design document (used in output messages)
# Note: This macro assumes that the markdown file has a specific format where the version number is on the 
# first line in the format "Version: x.y.z" and the title is the first level 1 heading (e.g., "# Title").
# The generated PDF will be placed in the specified distribution directory and named according to the provided variables.
# ============================================================================================
define DESIGN_DOC_PDF_RULE
$$($1_PDF): $$($1_MD) $$(DESIGN_LATEX_TEMPLATE) $$($1_EXTRA_DEPS) | $$(BUILD_DIR)
	@echo -e "\n$$(DARKYELLOW)- Building $2 PDF via LaTeX report pipeline...$$(NC)"
	@mkdir -p $$($1_DIST_DIR)
	@pandoc --from=markdown --to=latex --top-level-division=chapter --syntax-highlighting=none $$($1_PANDOC_OPTS) $$($1_MD) -o $$($1_BODY_TEX)
	@sed -i.bak 's/\\def\\LTcaptype{none}/\\def\\LTcaptype{table}/g' $$($1_BODY_TEX)
	@rm -f $$($1_BODY_TEX).bak
	@awk -v body="$$($1_BODY_TEX)" '\
		/%%__DESIGN_CONTENT__%%/ { while ((getline line < body) > 0) print line; close(body); inserted=1; next } \
		{ print } \
		END { if (!inserted) { print "Template placeholder %%__DESIGN_CONTENT__%% not found" > "/dev/stderr"; exit 2 } }' \
		$$(DESIGN_LATEX_TEMPLATE) > $$($1_TEX)
	@VERSION_FROM_MD=$$$$(head -n 1 $$($1_MD) | sed -E 's/^Version:[[:space:]]*//'); \
	if [ -z "$$$$VERSION_FROM_MD" ]; then \
		echo -e "$$(RED)✗ Error: Could not extract Version from first line of $$($1_MD)$$(NC)"; \
		exit 1; \
	fi; \
	TITLE_FROM_MD=$$$$(grep -m 1 '^# ' $$($1_MD) | sed -E 's/^#[[:space:]]+//'); \
	if [ -z "$$$$TITLE_FROM_MD" ]; then \
		echo -e "$$(RED)✗ Error: Could not extract title from $$($1_MD)$$(NC)"; \
		exit 1; \
	fi; \
	sed -i.bak -E "s/\{\{VERSION\}\}/Version: $$$$VERSION_FROM_MD/g" $$($1_TEX); \
	sed -i.bak -E "s/\{\{TITLE\}\}/$$$$TITLE_FROM_MD/g" $$($1_TEX); \
	if ! grep -q "Version: $$$$VERSION_FROM_MD" $$($1_TEX); then \
		echo -e "$$(RED)✗ Error: Failed to update version number in LaTeX template from markdown source$$(NC)"; \
		exit 1; \
	fi; \
	if ! grep -q "$$$$TITLE_FROM_MD" $$($1_TEX); then \
		echo -e "$$(RED)✗ Error: Failed to update title in LaTeX template from markdown source$$(NC)"; \
		exit 1; \
	fi; \
	rm -f $$($1_TEX).bak; \
	xelatex -interaction=nonstopmode -halt-on-error -output-directory $$($1_DIST_DIR) $$($1_TEX) >/dev/null; \
	xelatex -interaction=nonstopmode -halt-on-error -output-directory $$($1_DIST_DIR) $$($1_TEX) >/dev/null; \
	cp $$($1_PDF_BUILT) $$($1_BASENAME)-$$$$VERSION_FROM_MD.pdf; \
	rm -rf $$($1_DIST_DIR); \
	echo -e "$$(GREEN)✓ Version: $$$$VERSION_FROM_MD of \"$2\" PDF built: $$(DARKGRAY)$$($1_BASENAME)-$$$$VERSION_FROM_MD.pdf$$(NC)"
endef

help: ## Show this help message
	@echo -e "$(DARKYELLOW)OneSelect - Makefile Targets$(NC)"
	@$(call print_section,Build & Documentation,build|pdf-design)
	@echo ""

$(BUILD_DIR):
	@mkdir -p $(BUILD_DIR)

clean: ## Clean all generated files
	@rm -rf $(BUILD_DIR) $(SPRINT_PLANNING_BASENAME)-*.pdf $(TSHIRT_CATEGORY_BASENAME)-*.pdf $(MULTIPHASE_SIM_BASENAME)-*.pdf
	@echo -e "$(GREEN)✓ Cleaned all generated files$(NC)"

pdf-design: $(SPRINT_PLANNING_PDF) $(TSHIRT_CATEGORY_PDF) $(MULTIPHASE_SIM_PDF) ## Build all the PDF versions of the design documents
	@:


$(eval $(call DESIGN_DOC_PDF_RULE,SPRINT_PLANNING,sprint-based planning))
$(eval $(call DESIGN_DOC_PDF_RULE,TSHIRT_CATEGORY,t-shirt category))
$(eval $(call DESIGN_DOC_PDF_RULE,MULTIPHASE_SIM,multi-phase simulation))

