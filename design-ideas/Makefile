# Makefile for Design Documentation inMCProjSim project

.PHONY: pdf-design help

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
SCRIPTS_DIR := ../scripts
DESIGN_IDEAS_DIR := .

# Generic Latex template to use for all design documents - 
# it will have a placeholder for content injection and some basic styling, 
# but the content will be generated from the respective markdown files 
# for each design document
DESIGN_LATEX_TEMPLATE := $(DESIGN_IDEAS_DIR)/design_template.tex

# Sprint planning design document specific variables
SPRINT_PLANNING_MD := $(DESIGN_IDEAS_DIR)/sprint-based-planning.md
SPRINT_PLANNING_PDF := $(DESIGN_IDEAS_DIR)/sprint-based-planning.pdf
SPRINT_PLANNING_DIST_DIR := $(BUILD_DIR)/design-ideas/sprint-planning
SPRINT_PLANNING_PANDOC_FILTER := $(SCRIPTS_DIR)/pandoc_sprint_planning_table_widths.lua
SPRINT_PLANNING_BODY_TEX := $(SPRINT_PLANNING_DIST_DIR)/sprint-based-planning_body.tex
SPRINT_PLANNING_TEX := $(SPRINT_PLANNING_DIST_DIR)/sprint-based-planning_report.tex
SPRINT_PLANNING_PDF_BUILT := $(SPRINT_PLANNING_DIST_DIR)/sprint-based-planning_report.pdf

# T-shirt category design document specific variables
TSHIRT_CATEGORY_MD := $(DESIGN_IDEAS_DIR)/tshirt-categories.md
TSHIRT_CATEGORY_PDF := $(DESIGN_IDEAS_DIR)/tshirt-categories.pdf
TSHIRT_CATEGORY_DIST_DIR := $(BUILD_DIR)/design-ideas/tshirt-categories
TSHIRT_CATEGORY_BODY_TEX := $(TSHIRT_CATEGORY_DIST_DIR)/tshirt-categories_body.tex
TSHIRT_CATEGORY_TEX := $(TSHIRT_CATEGORY_DIST_DIR)/tshirt-categories_report.tex
TSHIRT_CATEGORY_PDF_BUILT := $(TSHIRT_CATEGORY_DIST_DIR)/tshirt-categories_report.pdf

# Multi-phased simulaton design document specific variables
MULTIPHASE_SIM_MD := $(DESIGN_IDEAS_DIR)/multiphase-simulation.md
MULTIPHASE_SIM_PDF := $(DESIGN_IDEAS_DIR)/multiphase-simulation.pdf
MULTIPHASE_SIM_DIST_DIR := $(BUILD_DIR)/design-ideas/multiphase-simulation
MULTIPHASE_SIM_BODY_TEX := $(MULTIPHASE_SIM_DIST_DIR)/multiphase-simulation_body.tex
MULTIPHASE_SIM_TEX := $(MULTIPHASE_SIM_DIST_DIR)/multiphase-simulation_report.tex
MULTIPHASE_SIM_PDF_BUILT := $(MULTIPHASE_SIM_DIST_DIR)/multiphase-simulation_report.pdf

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
	@$(call print_section,Build & Documentation,build|pdf-design)
	@echo ""

$(BUILD_DIR):
	@mkdir -p $(BUILD_DIR)

clean: ## Clean all generated files
	@rm -rf $(BUILD_DIR) $(SPRINT_PLANNING_PDF) $(TSHIRT_CATEGORY_PDF) $(MULTIPHASE_SIM_PDF)
	@echo -e "$(GREEN)✓ Cleaned all generated files$(NC)"

pdf-design: $(SPRINT_PLANNING_PDF) $(TSHIRT_CATEGORY_PDF) $(MULTIPHASE_SIM_PDF) ## Build all the PDF versions of the design documents
	@:

$(SPRINT_PLANNING_PDF): $(SPRINT_PLANNING_MD) $(DESIGN_LATEX_TEMPLATE) $(SPRINT_PLANNING_PANDOC_FILTER) | $(BUILD_DIR)
	@echo -e "$(DARKYELLOW)- Building sprint-based planning PDF via LaTeX report pipeline...$(NC)"
	@mkdir -p $(SPRINT_PLANNING_DIST_DIR)
#	@echo -e "$(DARKYELLOW)  - Converting markdown source to LaTeX body...$(NC)"
	@pandoc --from=markdown --to=latex --top-level-division=chapter --syntax-highlighting=none --lua-filter=$(SPRINT_PLANNING_PANDOC_FILTER) $(SPRINT_PLANNING_MD) -o $(SPRINT_PLANNING_BODY_TEX)
	@sed -i.bak 's/\\def\\LTcaptype{none}/\\def\\LTcaptype{table}/g' $(SPRINT_PLANNING_BODY_TEX)
	@rm -f $(SPRINT_PLANNING_BODY_TEX).bak
#	@echo -e "$(DARKYELLOW)  - Injecting body into design-ideas LaTeX template...$(NC)"
	@awk -v body="$(SPRINT_PLANNING_BODY_TEX)" '\
		/%%__DESIGN_CONTENT__%%/ { while ((getline line < body) > 0) print line; close(body); inserted=1; next } \
		{ print } \
		END { if (!inserted) { print "Template placeholder %%__DESIGN_CONTENT__%% not found" > "/dev/stderr"; exit 2 } }' \
		$(DESIGN_LATEX_TEMPLATE) > $(SPRINT_PLANNING_TEX)
# Read the version from the first line of the markdown file (assuming it is in the format: "Version: x.y.z") 
# and replace the version placeholder "{{VERSION}}" in the LaTeX template	
	@VERSION_FROM_MD=$$(head -n 1 $(SPRINT_PLANNING_MD) | sed -E 's/Version:\s*([0-9.]+)/\1/'); \
	sed -i.bak -E "s/\{\{VERSION\}\}/$$VERSION_FROM_MD/g" $(SPRINT_PLANNING_TEX); \
	if grep -q "$$VERSION_FROM_MD" $(SPRINT_PLANNING_TEX); then \
		echo -e "$(GREEN)✓ Version number updated successfully in LaTeX template from markdown source$(NC)"; \
	else \
		echo -e "$(RED)✗ Error: Failed to update version number in LaTeX template from markdown source$(NC)"; \
		exit 1; \
	fi; 
# Use the first heading in the markdown file as the title and replace the "{{TITLE}}" placeholder in the LaTeX template
	@TITLE_FROM_MD=$$(grep -m 1 '^# ' $(SPRINT_PLANNING_MD) | sed -E 's/#\s*(.+)/\1/'); \
	sed -i.bak -E "s/\{\{TITLE\}\}/$$TITLE_FROM_MD/g" $(SPRINT_PLANNING_TEX); \
	if grep -q "$$TITLE_FROM_MD" $(SPRINT_PLANNING_TEX); then \
		echo -e "$(GREEN)✓ Title updated successfully in LaTeX template from markdown source$(NC)"; \
	else \
		echo -e "$(RED)✗ Error: Failed to update title in LaTeX template from markdown source$(NC)"; \
		exit 1; \
	fi
	@rm -f $(SPRINT_PLANNING_TEX).bak		
#	@echo -e "$(DARKYELLOW)  - Compiling PDF with xelatex (2 passes for references/TOC)...$(NC)"
	@xelatex -interaction=nonstopmode -halt-on-error -output-directory $(SPRINT_PLANNING_DIST_DIR) $(SPRINT_PLANNING_TEX) >/dev/null
	@xelatex -interaction=nonstopmode -halt-on-error -output-directory $(SPRINT_PLANNING_DIST_DIR) $(SPRINT_PLANNING_TEX) >/dev/null
	@cp $(SPRINT_PLANNING_PDF_BUILT) $(SPRINT_PLANNING_PDF)
	@rm -rf $(SPRINT_PLANNING_DIST_DIR) 
	@echo -e "$(GREEN)✓ Sprint-based planning PDF built: $(DARKYELLOW)$(SPRINT_PLANNING_PDF)$(NC)"


$(TSHIRT_CATEGORY_PDF): $(TSHIRT_CATEGORY_MD) $(DESIGN_LATEX_TEMPLATE) | $(BUILD_DIR)
	@echo -e "\n$(DARKYELLOW)- Building t-shirt category PDF via LaTeX report pipeline...$(NC)"
	@mkdir -p $(TSHIRT_CATEGORY_DIST_DIR)
#	@echo -e "$(DARKYELLOW)  - Converting markdown source to LaTeX body...$(NC)"
	@pandoc --from=markdown --to=latex --top-level-division=chapter --syntax-highlighting=none $(TSHIRT_CATEGORY_MD) -o $(TSHIRT_CATEGORY_BODY_TEX)
	@sed -i.bak 's/\\def\\LTcaptype{none}/\\def\\LTcaptype{table}/g' $(TSHIRT_CATEGORY_BODY_TEX)
	@rm -f $(TSHIRT_CATEGORY_BODY_TEX).bak
#	@echo -e "$(DARKYELLOW)  - Injecting body into design-ideas LaTeX template...$(NC)"
	@awk -v body="$(TSHIRT_CATEGORY_BODY_TEX)" '\
		/%%__DESIGN_CONTENT__%%/ { while ((getline line < body) > 0) print line; close(body); inserted=1; next } \
		{ print } \
		END { if (!inserted) { print "Template placeholder %%__DESIGN_CONTENT__%% not found" > "/dev/stderr"; exit 2 } }' \
		$(DESIGN_LATEX_TEMPLATE) > $(TSHIRT_CATEGORY_TEX)
# Read the version from the first line of the markdown file (assuming it is in the format: "Version: x.y.z") 
# and replace the version placeholder "{{VERSION}}" in the LaTeX template	
	@VERSION_FROM_MD=$$(head -n 1 $(TSHIRT_CATEGORY_MD) | sed -E 's/Version:\s*([0-9.]+)/\1/'); \
	sed -i.bak -E "s/\{\{VERSION\}\}/$$VERSION_FROM_MD/g" $(TSHIRT_CATEGORY_TEX); \
	if grep -q "$$VERSION_FROM_MD" $(TSHIRT_CATEGORY_TEX); then \
		echo -e "$(GREEN)✓ Version number updated successfully in LaTeX template from markdown source$(NC)"; \
	else \
		echo -e "$(RED)✗ Error: Failed to update version number in LaTeX template from markdown source$(NC)"; \
		exit 1; \
	fi; 
# Use the first heading in the markdown file as the title and replace the "{{TITLE}}" placeholder in the LaTeX template
	@TITLE_FROM_MD=$$(grep -m 1 '^# ' $(TSHIRT_CATEGORY_MD) | sed -E 's/#\s*(.+)/\1/'); \
	sed -i.bak -E "s/\{\{TITLE\}\}/$$TITLE_FROM_MD/g" $(TSHIRT_CATEGORY_TEX); \
	if grep -q "$$TITLE_FROM_MD" $(TSHIRT_CATEGORY_TEX); then \
		echo -e "$(GREEN)✓ Title updated successfully in LaTeX template from markdown source$(NC)"; \
	else \
		echo -e "$(RED)✗ Error: Failed to update title in LaTeX template from markdown source$(NC)"; \
		exit 1; \
	fi
	@rm -f $(TSHIRT_CATEGORY_TEX).bak
#	@echo -e "$(DARKYELLOW)  - Compiling PDF with xelatex (2 passes for references/TOC)...$(NC)"
	@xelatex -interaction=nonstopmode -halt-on-error -output-directory $(TSHIRT_CATEGORY_DIST_DIR) $(TSHIRT_CATEGORY_TEX) >/dev/null
	@xelatex -interaction=nonstopmode -halt-on-error -output-directory $(TSHIRT_CATEGORY_DIST_DIR) $(TSHIRT_CATEGORY_TEX) >/dev/null
	@cp $(TSHIRT_CATEGORY_PDF_BUILT) $(TSHIRT_CATEGORY_PDF)
	@rm -rf $(TSHIRT_CATEGORY_DIST_DIR)
	@echo -e "$(GREEN)✓ T-shirt category PDF built: $(DARKYELLOW)$(TSHIRT_CATEGORY_PDF)$(NC)"


$(MULTIPHASE_SIM_PDF): $(MULTIPHASE_SIM_MD) $(DESIGN_LATEX_TEMPLATE) | $(BUILD_DIR)
	@echo -e "\n$(DARKYELLOW)- Building Multi-phase simulation PDF via LaTeX report pipeline...$(NC)"
	@mkdir -p $(MULTIPHASE_SIM_DIST_DIR)
#	@echo -e "$(DARKYELLOW)  - Converting markdown source to LaTeX body...$(NC)"
	@pandoc --from=markdown --to=latex --top-level-division=chapter --syntax-highlighting=none $(MULTIPHASE_SIM_MD) -o $(MULTIPHASE_SIM_BODY_TEX)
	@sed -i.bak 's/\\def\\LTcaptype{none}/\\def\\LTcaptype{table}/g' $(MULTIPHASE_SIM_BODY_TEX)
	@rm -f $(MULTIPHASE_SIM_BODY_TEX).bak
#	@echo -e "$(DARKYELLOW)  - Injecting body into design-ideas LaTeX template...$(NC)"
	@awk -v body="$(MULTIPHASE_SIM_BODY_TEX)" '\
		/%%__DESIGN_CONTENT__%%/ { while ((getline line < body) > 0) print line; close(body); inserted=1; next } \
		{ print } \
		END { if (!inserted) { print "Template placeholder %%__DESIGN_CONTENT__%% not found" > "/dev/stderr"; exit 2 } }' \
		$(DESIGN_LATEX_TEMPLATE) > $(MULTIPHASE_SIM_TEX)
# Read the version from the first line of the markdown file (assuming it is in the format: "Version: x.y.z") 
# and replace the version placeholder "{{VERSION}}" in the LaTeX template	
	@VERSION_FROM_MD=$$(head -n 1 $(MULTIPHASE_SIM_MD) | sed -E 's/Version:\s*([0-9.]+)/\1/'); \
	sed -i.bak -E "s/\{\{VERSION\}\}/$$VERSION_FROM_MD/g" $(MULTIPHASE_SIM_TEX); \
	if grep -q "$$VERSION_FROM_MD" $(MULTIPHASE_SIM_TEX); then \
		echo -e "$(GREEN)✓ Version number updated successfully in LaTeX template from markdown source$(NC)"; \
	else \
		echo -e "$(RED)✗ Error: Failed to update version number in LaTeX template from markdown source$(NC)"; \
		exit 1; \
	fi; 
# Use the first heading in the markdown file as the title and replace the "{{TITLE}}" placeholder in the LaTeX template
	@TITLE_FROM_MD=$$(grep -m 1 '^# ' $(MULTIPHASE_SIM_MD) | sed -E 's/#\s*(.+)/\1/'); \
	sed -i.bak -E "s/\{\{TITLE\}\}/$$TITLE_FROM_MD/g" $(MULTIPHASE_SIM_TEX); \
	if grep -q "$$TITLE_FROM_MD" $(MULTIPHASE_SIM_TEX); then \
		echo -e "$(GREEN)✓ Title updated successfully in LaTeX template from markdown source$(NC)"; \
	else \
		echo -e "$(RED)✗ Error: Failed to update title in LaTeX template from markdown source$(NC)"; \
		exit 1; \
	fi
	@rm -f $(MULTIPHASE_SIM_TEX).bak
#	@echo -e "$(DARKYELLOW)  - Compiling PDF with xelatex (2 passes for references/TOC)...$(NC)"
	@xelatex -interaction=nonstopmode -halt-on-error -output-directory $(MULTIPHASE_SIM_DIST_DIR) $(MULTIPHASE_SIM_TEX) >/dev/null
	@xelatex -interaction=nonstopmode -halt-on-error -output-directory $(MULTIPHASE_SIM_DIST_DIR) $(MULTIPHASE_SIM_TEX) >/dev/null
	@cp $(MULTIPHASE_SIM_PDF_BUILT) $(MULTIPHASE_SIM_PDF)
	@rm -rf $(MULTIPHASE_SIM_DIST_DIR)
	@echo -e "$(GREEN)✓ Multiphase simulation PDF built: $(DARKYELLOW)$(MULTIPHASE_SIM_PDF)$(NC)"

