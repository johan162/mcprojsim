# 'mcprojsim` -  New User Learning Journey Report 1

> **Context**: This report documents findings from a systematic walkthrough of the
> mcprojsim documentation as a new (but technical) user, following the Quick Start
> Guide and then every page in the User Guide in the order defined by `mkdocs.yml`.
> For each topic, experimental YAML files were created, simulations run, and output
> compared against the documentation's claims. All experiment files are in
> `new_user/learning01/`.

## Scope
I followed the documentation as a new but technical user in this order:

1. Quick Start (`docs/quickstart.md`)
2. User Guide order from `mkdocs.yml`:
   - Getting Started
   - Introduction
   - Your first project
   - Uncertainty Factors
   - Task Estimation
   - Project Risks
   - Project Files
   - Sprint Planning
   - Resource and Calendar Constrained Scheduling
   - Multi-Phase (Two-Pass) Simulation
   - Running Simulations
   - Interpreting Results
   - Configuration
   - Monetary Cost Estimation
   - Natural Language Input
   - MCP Server
   - Examples

For each topic I created a topic file in `new_user/*.yaml` and captured command output in `new_user/*_output.txt`.

## Artifacts Produced
Created experiment inputs and outputs for all guide topics:

- `new_user/quickstart.yaml` + `new_user/quickstart_output.txt`
- `new_user/getting_started.yaml` + `new_user/getting_started_output.txt`
- `new_user/introduction.yaml` + `new_user/introduction_output.txt`
- `new_user/your_first_project.yaml` + `new_user/your_first_project_output.txt`
- `new_user/uncertainty_factors.yaml` + `new_user/uncertainty_factors_output.txt`
- `new_user/task_estimation.yaml` + `new_user/task_estimation_output.txt`
- `new_user/risks.yaml` + `new_user/risks_output.txt`
- `new_user/project_files.yaml` + `new_user/project_files.toml` + `new_user/project_files_output.txt`
- `new_user/sprint_planning.yaml` + `new_user/sprint_planning_output.txt`
- `new_user/constrained.yaml` + `new_user/constrained_output.txt`
- `new_user/multi_phase_simulation.yaml` + `new_user/multi_phase_simulation_output.txt`
- `new_user/running_simulations.yaml` + `new_user/running_simulations_output.txt`
- `new_user/interpreting_results.yaml` + `new_user/interpreting_results_output.txt`
- `new_user/configuration_project.yaml` + `new_user/configuration.yaml` + `new_user/configuration_output.txt`
- `new_user/cost_handling.yaml` + `new_user/cost_handling_output.txt`
- `new_user/nl_processing_input.txt` + `new_user/nl_processing.yaml` + `new_user/nl_processing_output.txt`
- `new_user/mcp_server.yaml` + `new_user/mcp_server_output.txt`
- `new_user/examples.yaml` + `new_user/examples_output.txt`

## What Was Hard To Understand

### 1) Estimate schema differences are easy to confuse
I initially tried lognormal with `min/max/confidence` and hit validation errors. The accepted structure in project tasks is `low/expected/high` plus `distribution: lognormal`.

Why this is confusing:
- The same docs ecosystem includes both `low/expected/high` and other shape conventions (for different features/modes).
- A new user can mix those mental models.

Suggested improvement:
- Add an explicit "Common mistake" callout in task-estimation docs:
  - "For task-level lognormal estimates, do NOT use `min/max/confidence`; use `low/expected/high` + `distribution: lognormal`."

### 2) Risk impact syntax needs a stronger quick-reference warning
I initially wrote task/project risks with a top-level `unit` next to numeric `impact` and got schema errors.

Why this is confusing:
- Numeric `impact` looks unitless unless the user knows the implicit behavior.
- Structured impact object with `type/value/unit` is more explicit but easy to miss.

Suggested improvement:
- In risks docs, add a compact "Do this / not this" snippet immediately under the first example.

### 3) Config keys and CLI flags use different names for histogram bins
I initially used `output.number_bins` in config (from CLI mental model `--number-bins`) and got validation errors. The config key is `output.histogram_bins`.

Why this is confusing:
- Similar concept, two names.

Suggested improvement:
- Add a short mapping table in configuration docs:
  - CLI `--number-bins` -> config `output.histogram_bins`.

### 4) Constrained scheduling results can look "too large" at first glance
Dependency-only examples gave much shorter timelines than constrained runs (resource/calendar constrained). As a new user, this feels like "something is wrong" before learning why.

Why this is confusing:
- The jump is large and surprising.
- New users often expect only modest increases.

Suggested improvement:
- Put a first-class "Why constrained can be much longer" box near the beginning of the constrained chapter with a tiny before/after numeric example.

### 5) Staffing recommendation can look counterintuitive
Several runs recommended 1 person even with multiple tasks. New users may read that as a bug.

Why this is confusing:
- Users often assume more tasks always imply larger team recommendations.
- The output is technically correct but interpretation requires understanding serial critical paths and overhead.

Suggested improvement:
- In interpreting-results chapter, add one worked micro-example showing a serial chain where team size >1 hurts schedule.

## Potential Documentation Gaps vs Observed Functionality

### Gap A: MCP verification command behavior
The MCP chapter recommends checking `mcprojsim-mcp --help`. In practice, this appears to behave like a long-running process in this environment rather than a quick help exit.

Observed workaround that did work:
- `from mcprojsim.mcp_server import main` import check
- Followed by normal CLI workflow for generated YAML

Recommendation:
- Document a non-blocking verification path first (import check), and explicitly note whether `mcprojsim-mcp` is a server command that may run continuously.

### Gap B: New-user validation troubleshooting needs one centralized section
Across chapters, schema mistakes are common and educational, but there is no single "Top 10 validation errors" section.

Recommendation:
- Add one shared troubleshooting page and link to it from Quick Start, Project Files, Risks, Task Estimation, and Configuration.

### Gap C: Quick Start could preview expected runtime/log patterns
Quick Start output is comprehensive, but first-time users may not know which lines are "success criteria" vs informational.

Recommendation:
- Add a compact "You are successful if you see:" block:
  - `Project file is valid`
  - `Simulation Results`
  - `No export formats specified...` (expected unless `-f` used)

## Suggested Improvements (Prioritized)

1. Add "Common mistakes" callouts in:
   - task estimation (lognormal field confusion)
   - risks (numeric vs structured impact)
   - configuration (CLI-to-config key mapping)
2. Add a dedicated validation troubleshooting page with exact error-message-to-fix patterns.
3. Add an early constrained-scheduling intuition box with explicit before/after example.
4. Expand staffing interpretation with a serial-chain example where recommended team size is 1.
5. Clarify MCP verification commands to avoid potentially blocking checks.
6. In Quick Start, add a short "what output to expect" checklist.

## Positive Notes

- The overall learning progression is strong and feature-complete.
- The chapter ordering in `mkdocs.yml` is sensible from baseline to advanced topics.
- CLI outputs are rich and practically useful, especially `--table` mode.
- Natural-language generation workflow is very usable (`generate` -> `validate` -> `simulate`).

## Final Assessment
The docs are strong for breadth and practical command coverage, but the learning curve would improve significantly with sharper guardrails around schema pitfalls and a few interpretation aids for counterintuitive outputs (constrained duration jumps and staffing recommendations). A small set of targeted clarifications would remove most first-user friction.
