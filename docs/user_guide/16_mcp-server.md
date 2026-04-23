# MCP Server & NL Input

Writing a full YAML project file by hand is straightforward once you know the format, but it takes time — especially when you are in an early planning session and just want to sketch out tasks quickly. The `mcprojsim` **MCP server** bridges that gap. It lets an AI assistant (such as Claude, GitHub Copilot, or any MCP-compatible client) convert a rough, natural-language project description into a syntactically correct project specification file that `mcprojsim` can simulate immediately.

This chapter explains what the MCP server is, how to install and configure it, how the natural language parser works, and how to get the best results from it.



## What is the MCP server?

The **Model Context Protocol (MCP)** is an open standard that lets AI assistants call external tools in a structured way. The mcprojsim MCP server exposes the following tools grouped by input type and action:

| Command class | Tool | Purpose |
|------|------|--------|
| NL -> YAML generation | `generate_project_file` | Convert natural language project description into a valid mcprojsim YAML file |
| NL validation | `validate_project_description` | Lightweight parser-level checks on the description |
| NL strict validation | `validate_generated_project_yaml` | Full parser/model validation of generated YAML using runtime defaults and overrides |
| NL simulation | `simulate_project` | Generate YAML from description and run simulation in one step |
| YAML strict validation | `validate_project_yaml` | Validate existing YAML directly (no NL regeneration) |
| YAML simulation | `simulate_project_yaml` | Simulate directly from existing YAML with runtime options |
| YAML update/transform | `update_project_yaml` | Apply NL update instructions to existing YAML (optionally replace tasks) |

When an MCP client connects to the server, the AI assistant can invoke these tools on your behalf. You can now work in either direction:

- describe in natural language and generate/simulate immediately,
- or keep an existing YAML project as the source of truth and validate/simulate/update it directly.



## Prerequisites and installation

The MCP server has one additional dependency beyond the core `mcprojsim` package: the `mcp` Python library. It is declared as an optional dependency group so it does not affect users who do not need the server.

## Ways to install the server

There are two main ways to install the server

1. [Recommended] Ask your assistant to download and install the server from GitHub

2. Download the project, setup the development environment and build the server locally your self.

## Ask your assistant

Use the following example prompt to get your assistant to install `mcprojsim`:

```txt
Download and install the latest mcprojsim MCP server from GitHub Releases. Follow the README.md for installation instructions.
```

Depending on which assistant you use (e.g. `copilot-cli`, `claude-desktop`, ...) and you general instructions you might get different questions to approve various file-operations in order to
setup the server.


## Download project and install manually

### Step 1: Install mcprojsim with MCP support

If you already have the project checked out and use Poetry you can install it with:

```bash
poetry install --with mcp
```

This installs the `mcp` package alongside the existing dependencies. The `--with mcp` flag pulls in only the MCP group without affecting other optional groups like `docs` or `dev`.

### Step 2: Verify the installation

!!! warning "mcprojsim-mcp does not accept --help"
    `mcprojsim-mcp` is a **long-running server process**. When started from a terminal it
    immediately begins listening for MCP protocol messages over stdio. It does not
    accept `--help` or any command-line flags — running `mcprojsim-mcp --help` will
    appear to hang, because the process is waiting for a client. Press `Ctrl+C` to exit.

To verify that the entry point and all MCP dependencies are correctly installed, use the Python import check instead:

```python
from mcprojsim.mcp_server import main
print("MCP server installed correctly")
```

If this import succeeds without an `ImportError`, the MCP dependencies are correctly installed. You can also run this as a one-liner from the terminal:

```bash
python -c "from mcprojsim.mcp_server import main; print('OK')"
```

With Poetry:

```bash
poetry run python -c "from mcprojsim.mcp_server import main; print('OK')"
```

A successful run prints `OK` and exits immediately. Any `ImportError` or `ModuleNotFoundError` means the `mcp` dependency group was not installed — re-run `poetry install --with mcp` to fix it.

### Step 3: Configure your MCP client

Every MCP client has its own configuration format. Below are examples for common clients.

**Claude Desktop** — edit `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mcprojsim": {
      "command": "mcprojsim-mcp"
    }
  }
}
```

**VS Code (GitHub Copilot)** — add to your `.vscode/mcp.json` or user settings:

```json
{
  "servers": {
    "mcprojsim": {
      "command": "mcprojsim-mcp"
    }
  }
}
```

!!! note
    If you installed `mcprojsim` inside a Poetry virtual environment, you may need to specify the full path to the entry point. You can find it with `poetry run which mcprojsim-mcp`.


## A basic example of a prompt that uses the MCP Server

After restarting the assistant (needed to load the new MCP Server) ask for a simple project simulation:

```txt
Simulate a project that starts 2025-05-01 and has two M-size tasks that depends on each-other. Show the result for all complete date percentiles in a table.
```

An example output would be

```txt
● Here are the simulation results for the two-task project (sequential M→M, starting 2025-05-01):

  ┌────────────┬───────┬──────────────┬───────────────┐
  │ Percentile │ Hours │ Working Days │ Delivery Date │
  ├────────────┼───────┼──────────────┼───────────────┤
  │ P50        │ 230.8 │ 29           │ 2025-06-11    │
  ├────────────┼───────┼──────────────┼───────────────┤
  │ P80        │ 265.3 │ 34           │ 2025-06-18    │
  ├────────────┼───────┼──────────────┼───────────────┤
  │ P90        │ 283.4 │ 36           │ 2025-06-20    │
  ├────────────┼───────┼──────────────┼───────────────┤
  │ P95        │ 298.7 │ 38           │ 2025-06-24    │
  └────────────┴───────┴──────────────┴───────────────┘

  Key stats: Mean ~233h (30 days) · Std dev ~38h · 
  Both tasks are on the critical path 100% of the time.
```

You can then continue to explore more of the statistics with another prompt

```txt
Show the summary statistics for this simulation in a table.
```

which could result in something simlar to this table:

```txt
● From the previous simulation results:

  ┌──────────────────────────┬────────────────────────────────┐
  │ Statistic                │ Value                          │
  ├──────────────────────────┼────────────────────────────────┤
  │ Mean                     │ 232.64 hours (30 working days) │
  ├──────────────────────────┼────────────────────────────────┤
  │ Median (P50)             │ 230.82 hours (29 working days) │
  ├──────────────────────────┼────────────────────────────────┤
  │ Std Dev                  │ 37.97 hours                    │
  ├──────────────────────────┼────────────────────────────────┤
  │ Coefficient of Variation │ 0.1632                         │
  ├──────────────────────────┼────────────────────────────────┤
  │ Skewness                 │ 0.2703                         │
  ├──────────────────────────┼────────────────────────────────┤
  │ Excess Kurtosis          │ -0.3336                        │
  ├──────────────────────────┼────────────────────────────────┤
  │ Iterations               │ 10,000                         │
  ├──────────────────────────┼────────────────────────────────┤
  │ Hours per Day            │ 8.0                            │
  └──────────────────────────┴────────────────────────────────┘
```


## Workflow overview

There are now four practical workflows depending on whether you start from natural language or existing YAML.

### Two-step workflow: generate then simulate

```text
 ┌──────────────────┐     ┌──────────────┐     ┌───────────────┐     ┌────────────────┐
 │ 1. Write a rough │────▶│ 2. AI calls  │────▶│ 3. Review the │────▶│ 4. Run the     │
 │    description   │     │    MCP tool  │     │    YAML output│     │    simulation  │
 └──────────────────┘     └──────────────┘     └───────────────┘     └────────────────┘
```

1. **Write a description.** Open your MCP client (e.g., Claude Desktop) and describe the project in natural language. You do not need to worry about YAML syntax or exact field names — the parser handles that.

2. **The AI calls `generate_project_file`.** The assistant invokes the MCP tool with your description as input. The natural language parser extracts project metadata, tasks, sizes, dependencies, and estimates.

3. **Review the generated YAML.** The tool returns a complete YAML file. Review it for correctness — the parser captures structure faithfully, but you may want to add risks, uncertainty factors, or adjust task names.

4. **Run the simulation.** Save the YAML to a file and simulate:

```bash
mcprojsim simulate my_project.yaml --iterations 10000 --seed 42
```

### One-step workflow: describe and simulate directly

If you want results immediately without reviewing the YAML first, ask the assistant to simulate directly:

> "Simulate this project with 10000 iterations and seed 42:
> Project name: API Migration
> Start date: 2026-07-01
> Task 1: Design — Size: M
> Task 2: Build — Depends on Task 1 — Size: XL"

The assistant calls `simulate_project`, which generates the YAML internally and runs the simulation in a single step. The response includes both the generated YAML and the full simulation results (statistics, confidence intervals, delivery dates, critical paths).

### YAML-first workflow: validate/simulate existing project files

If your team already stores project YAML in version control, you can use YAML-native MCP tools directly:

- `validate_project_yaml` for strict validation
- `simulate_project_yaml` to run simulation with runtime options

This avoids re-generating the project from natural language when you only need execution or checks.

### YAML update workflow: apply natural-language change requests

Use `update_project_yaml` when you already have a project file and want the assistant to apply changes from natural-language instructions (for example, update sprint settings, change project metadata, or replace tasks).

This is useful for iterative planning sessions where the YAML evolves over time.

#### `simulate_project` parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `description` | string | required | Natural language project description |
| `iterations` | integer | 10000 | Number of Monte Carlo iterations |
| `seed` | integer | none | Random seed for reproducible results |
| `config_yaml` | string | none | Custom configuration YAML content (as a string) |
| `velocity_model` | string | none | Sprint velocity override: `empirical` or `neg_binomial` |
| `no_sickness` | boolean | `false` | Disable sprint sickness modeling for this run |
| `two_pass` | boolean | `false` | Enable criticality two-pass constrained scheduling |
| `pass1_iterations` | integer | none | Pass-1 iteration override when `two_pass` is enabled |
| `critical_paths_limit` | integer | none | Override number of full critical paths shown in output |

The `config_yaml` parameter lets you pass custom T-shirt size mappings, uncertainty factor values, or simulation settings inline without needing a separate file. Runtime options such as `velocity_model`, `no_sickness`, and `two_pass` mirror the corresponding CLI behavior.

#### `simulate_project_yaml` parameters

`simulate_project_yaml` accepts the same runtime simulation options as `simulate_project`, but takes `project_yaml` instead of `description`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `project_yaml` | string | required | Existing mcprojsim YAML project content |
| `iterations` | integer | 10000 | Number of Monte Carlo iterations |
| `seed` | integer | none | Random seed for reproducible results |
| `config_yaml` | string | none | Custom configuration YAML content (as a string) |
| `velocity_model` | string | none | Sprint velocity override: `empirical` or `neg_binomial` |
| `no_sickness` | boolean | `false` | Disable sprint sickness modeling for this run |
| `two_pass` | boolean | `false` | Enable criticality two-pass constrained scheduling |
| `pass1_iterations` | integer | none | Pass-1 iteration override when `two_pass` is enabled |
| `critical_paths_limit` | integer | none | Override number of full critical paths shown in output |

#### Validation tools: when to use which

| Tool | Input | Validation depth |
|------|-------|------------------|
| `validate_project_description` | NL description | Parser-level warnings and obvious issues |
| `validate_generated_project_yaml` | NL description | Full parser/model validation on generated YAML |
| `validate_project_yaml` | Existing YAML | Full parser/model validation on provided YAML |

`validate_project_description` is fast and useful during drafting. Use `validate_generated_project_yaml` or `validate_project_yaml` when you want strict behavior equivalent to normal YAML parsing and simulation setup.

#### `validate_generated_project_yaml` parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `description` | string | required | Natural language project description |
| `config_yaml` | string | none | Custom configuration YAML content (as a string) |
| `velocity_model` | string | none | Sprint velocity override: `empirical` or `neg_binomial` |
| `no_sickness` | boolean | `false` | Disable sprint sickness modeling for this validation |

#### `validate_project_yaml` parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `project_yaml` | string | required | Existing mcprojsim YAML project content |
| `config_yaml` | string | none | Custom configuration YAML content (as a string) |
| `velocity_model` | string | none | Sprint velocity override: `empirical` or `neg_binomial` |
| `no_sickness` | boolean | `false` | Disable sprint sickness modeling for this validation |

#### `update_project_yaml` parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `existing_yaml` | string | required | Existing mcprojsim project YAML content to update |
| `update_description` | string | required | Semi-structured NL instructions describing the changes to apply |
| `replace_tasks` | boolean | `false` | When `true`, replaces all existing tasks with tasks parsed from the update description. When `false` (default), existing tasks are preserved and only project metadata, sprint planning, resources, and calendars are updated |

## Translating NL intent to simulation options

One of the biggest benefits of MCP is that assistants can map user intent to runtime options.

### Example 1: Sprint velocity override

User intent:

```txt
Simulate this backlog using negative binomial velocity modeling.
```

Assistant maps to MCP call:

- `simulate_project(..., velocity_model="neg_binomial")`

### Example 2: Disable sickness for a scenario

User intent:

```txt
Run the same sprint simulation but ignore sickness effects.
```

Assistant maps to MCP call:

- `simulate_project(..., no_sickness=true)`

### Example 3: Constrained scheduling with two-pass

User intent:

```txt
Use two-pass constrained scheduling with 2000 pass-1 iterations.
```

Assistant maps to MCP call:

- `simulate_project(..., two_pass=true, pass1_iterations=2000)`

### Example 4: Existing YAML, no NL regeneration

User intent:

```txt
Validate and simulate this existing project YAML with seed 42.
```

Assistant maps to MCP calls:

- `validate_project_yaml(project_yaml=...)`
- `simulate_project_yaml(project_yaml=..., seed=42)`

### Example 5: Apply update instructions to an existing YAML

User intent:

```txt
Update this project: change start date, add sprint planning history, keep existing tasks.
```

Assistant maps to MCP call:

- `update_project_yaml(existing_yaml=..., update_description=..., replace_tasks=false)`

If the user says to replace tasks entirely, the assistant can set `replace_tasks=true`.

You can also ask the assistant to validate first:

> "Validate this project description before generating the file."

The assistant will call `validate_project_description` and report any warnings (missing estimates, undefined dependencies) before you commit to generating the file.



## Natural language input format

The parser is intentionally tolerant of formatting variations. It understands semi-structured text that follows a simple pattern: project metadata at the top, then numbered tasks with bullet-point attributes. It also accepts plain numbered lists, bullet lists, and inline properties — see [Natural Language Input](15_nl_processing.md) for the comprehensive reference.

The parser also supports sprint-planning phrasing, including sprint history and future sprint capacity override sections.

### Project-level fields

| Field | Pattern | Example |
|-------|---------|---------|
| Project name | `Project name:` or `Project:` | `Project name: API Migration` |
| Start date | `Start date:` followed by `YYYY-MM-DD` | `Start date: 2026-07-01` |
| Description | `Description:` | `Description: Migrate legacy REST API to GraphQL` |
| Hours per day | `Hours per day:` | `Hours per day: 6` |
| Confidence levels | `Confidence levels:` | `Confidence levels: 50, 80, 90, 95` |

All project-level fields are optional. If omitted, sensible defaults are used (project name defaults to "Untitled Project", confidence levels default to 50, 80, 90, 95).

### Task definitions

Tasks are introduced with a header line (`Task N:`) followed by bullet points. The task number determines the generated task ID (`task_001`, `task_002`, etc.).

Each bullet can contain one of the following:

| Attribute | Patterns recognized | Example |
|-----------|---------------------|---------|
| **Task name** | Any unrecognized bullet (first one becomes the name) | `- Design the new login flow` |
| **T-shirt size** | `Size: M`, `Size M`, `Size. XL` | `- Size: L` |
| **Story points** | `Story points: 5`, `Points: 8` | `- Story points: 13` |
| **Explicit estimate** | `Estimate: min/likely/max [unit]` | `- Estimate: 3/5/10 days` |
| **Dependencies** | `Depends on Task N`, `Depends on Task 1, Task 3` | `- Depends on Task 2` |
| **Description** | Second unrecognized bullet | `- Involves database migration` |

### Sprint-planning definitions (NL)

The NL parser can extract sprint planning information from sections such as:

- `Sprint planning:`
- `Sprint history SPR-001:`
- `Future sprint override 4:`

Supported sprint-planning bullets include:

| Attribute | Patterns recognized | Example |
|-----------|---------------------|---------|
| Sprint length | `Sprint length: 2`, `2-week sprints` | `- Sprint length: 2` |
| Capacity mode | `Capacity mode: story points`, `Capacity mode: tasks` | `- Capacity mode: story points` |
| Planning confidence | `Planning confidence level: 80%` | `- Planning confidence level: 80%` |
| Removed work treatment | `Removed work treatment: churn only` / `reduce backlog` | `- Removed work treatment: churn only` |
| Velocity model | `Velocity model: empirical` / `negative binomial` | `- Velocity model: negative binomial` |
| Sprint history completed | `Done: 20 points`, `Delivered: 9 tasks` | `- Done: 20 points` |
| Sprint history spillover | `Carryover: 3 points`, `Rolled over: 2 tasks` | `- Carryover: 3 points` |
| Sprint history added/removed | `Scope added: 2 points`, `Scope removed: 1 points` | `- Scope added: 2 points` |
| Holiday factor | `Holiday factor: 90%` | `- Holiday factor: 90%` |
| Future override locator | `Future sprint override 4`, `start date: 2026-07-01` | `Future sprint override 4:` |
| Future override multiplier | `Holiday factor: 80%`, `Capacity multiplier: 0.9` | `- Capacity multiplier: 0.9` |
| Sprint sickness toggles | `Sickness: enabled`, `No sickness` | `- Sickness: enabled` |

### T-shirt size aliases

The parser normalizes a variety of size labels to standard sizes:

| Input | Normalized to |
|-------|---------------|
| `XS`, `Extra Small` | `XS` |
| `S`, `Small` | `S` |
| `M`, `Medium`, `Med` | `M` |
| `L`, `Large` | `L` |
| `XL`, `Extra Large` | `XL` |
| `XXL`, `Extra Extra Large`, `2XL` | `XXL` |

Size matching is case-insensitive: `size: medium`, `Size: MEDIUM`, and `Size Medium` all resolve to `M`.



## Examples

The following examples show different levels of detail and formatting styles, all of which the parser handles correctly.

### Example 1: Minimal description with T-shirt sizes

The simplest useful input — just a project name, a start date, and tasks with sizes:

```text
Project name: Website Redesign
Start date: 2026-04-15
Task 1:
- Gather requirements
- Size: S
Task 2:
- Create wireframes
- Depends on Task 1
- Size: M
Task 3:
- Build frontend
- Depends on Task 2
- Size: XL
Task 4:
- QA and launch
- Depends on Task 3
- Size: M
```

Generated YAML:

```yaml
project:
  name: "Website Redesign"
  start_date: "2026-04-15"
  confidence_levels: [50, 80, 90, 95]

tasks:
  - id: "task_001"
    name: "Gather requirements"
    estimate:
      t_shirt_size: "S"
    dependencies: []

  - id: "task_002"
    name: "Create wireframes"
    estimate:
      t_shirt_size: "M"
    dependencies: ["task_001"]

  - id: "task_003"
    name: "Build frontend"
    estimate:
      t_shirt_size: "XL"
    dependencies: ["task_002"]

  - id: "task_004"
    name: "QA and launch"
    estimate:
      t_shirt_size: "M"
    dependencies: ["task_003"]
```

\newpage

### Example 2: Story points with multiple dependencies

Using story points and tasks with fan-in dependencies:

```text
Project: Mobile App v2
Start date: 2026-09-01
Task 1:
- API design
- Story points: 5
Task 2:
- iOS development
- Depends on Task 1
- Story points: 13
Task 3:
- Android development
- Depends on Task 1
- Story points: 13
Task 4:
- Integration testing
- Depends on Task 2, Task 3
- Story points: 8
```

Generated YAML:

```yaml
project:
  name: "Mobile App v2"
  start_date: "2026-09-01"
  confidence_levels: [50, 80, 90, 95]

tasks:
  - id: "task_001"
    name: "API design"
    estimate:
      story_points: 5
    dependencies: []

  - id: "task_002"
    name: "iOS development"
    estimate:
      story_points: 13
    dependencies: ["task_001"]

  - id: "task_003"
    name: "Android development"
    estimate:
      story_points: 13
    dependencies: ["task_001"]

  - id: "task_004"
    name: "Integration testing"
    estimate:
      story_points: 8
    dependencies: ["task_002", "task_003"]
```

\newpage

### Example 3: Explicit estimates with different units

When your team prefers numeric ranges over symbolic sizes:

```text
Project name: Database Migration
Start date: 2026-05-01
Hours per day: 7
Task 1:
- Schema analysis
- Estimate: 2/3/5 days
Task 2:
- Write migration scripts
- Depends on Task 1
- Estimate: 5/8/15 days
Task 3:
- Data validation
- Depends on Task 2
- Estimate: 8/16/32 hours
Task 4:
- Production cutover
- Depends on Task 3
- Estimate: 1/2/3 days
```

Generated YAML:

```yaml
project:
  name: "Database Migration"
  start_date: "2026-05-01"
  hours_per_day: 7
  confidence_levels: [50, 80, 90, 95]

tasks:
  - id: "task_001"
    name: "Schema analysis"
    estimate:
      low: 2
      expected: 3
      high: 5
      unit: "days"
    dependencies: []

  - id: "task_002"
    name: "Write migration scripts"
    estimate:
      low: 5
      expected: 8
      high: 15
      unit: "days"
    dependencies: ["task_001"]

  - id: "task_003"
    name: "Data validation"
    estimate:
      low: 8
      expected: 16
      high: 32
      unit: "hours"
    dependencies: ["task_002"]

  - id: "task_004"
    name: "Production cutover"
    estimate:
      low: 1
      expected: 2
      high: 3
      unit: "days"
    dependencies: ["task_003"]
```

\newpage

### Example 4: Sloppy formatting (typos, inconsistent punctuation)

The parser is designed to handle real-world input with minor typos and formatting inconsistencies. All of the following variations parse correctly:

```text
Project name: Rework Web Interface
Start date: 2026-06-02
Task 1:
- Analyse existing UI
- Size: M
Task 2:
- Refine requirements
- Depends on Task1
- Size XL
Task 3:
- Design solution
- Depends on Task 2
- Size. XL
```

Notice:
- `Depends on Task1` — no space between "Task" and "1" (still works)
- `Size XL` — no colon after "Size" (still works)
- `Size. XL` — period instead of colon (still works)

The parser normalizes all of these to the correct output.

### Example 5: Inline task names and descriptions

You can put the task name directly on the header line, and add a description bullet:

```text
Project: Platform Upgrade
Start date: 2026-08-01
Task 1: Upgrade framework
- Update all packages to latest versions
- Size: L
Task 2: Fix breaking changes
- Address deprecated APIs and removed features
- Depends on Task 1
- Size: XL
Task 3: Regression testing
- Depends on Task 2
- Size: M
```

Generated YAML:

```yaml
project:
  name: "Platform Upgrade"
  start_date: "2026-08-01"
  confidence_levels: [50, 80, 90, 95]

tasks:
  - id: "task_001"
    name: "Upgrade framework"
    description: "Update all packages to latest versions"
    estimate:
      t_shirt_size: "L"
    dependencies: []

  - id: "task_002"
    name: "Fix breaking changes"
    description: "Address deprecated APIs and removed features"
    estimate:
      t_shirt_size: "XL"
    dependencies: ["task_001"]

  - id: "task_003"
    name: "Regression testing"
    estimate:
      t_shirt_size: "M"
    dependencies: ["task_002"]
```

### Example 6: Verbose size labels

Teams unfamiliar with T-shirt abbreviations can use full words:

```text
Project: Sprint 12
Start date: 2026-03-15
Task 1:
- Bug triage
- Size: Extra Small
Task 2:
- Feature implementation
- Depends on Task 1
- Size: Extra Large
Task 3:
- Documentation
- Size: Small
```

`Extra Small` becomes `XS`, `Extra Large` becomes `XL`, and `Small` becomes `S` in the generated YAML.

### Example 7: Auto-detected lists with inline properties

You don't need `Task N:` headers at all. Plain numbered lists, bullet lists, and bracket-numbered lists are automatically detected as tasks. Sizes, estimates, and dependencies can appear inline on the same line:

```text
Project name: Mobile App MVP
Start date: 2026-06-01

- Discovery and requirements (S)
- UX wireframes (M)
  Depends on Task 1
- Backend API, probably an XL
  Depends on Task 2
- iOS frontend (XL)
  Depends on Task 3
- QA and bug fixes, likely an L
  Depends on Task 4
- App store submission (S)
  Depends on Task 5
```

The parser auto-numbers the bullet items (1, 2, 3, …), extracts parenthesized sizes like `(S)` and `(M)`, and recognizes fuzzy phrasing like `probably an XL` and `likely an L`. Indented continuation lines are parsed as task properties.

Numbered lists also work — and preserve the original numbering:

```text
Project name: Data Pipeline Rebuild
Start date: 2026-07-01

[1] Audit existing ETL jobs [S]
[2] Design new pipeline architecture [M] depends on Task 1
[3] Implement ingestion layer 3–5 days depends on Task 2
[4] Build transformation engine [XL] depends on Task 3
```

See [Natural Language Input](15_nl_processing.md) for the full range of supported list formats and inline properties.



## Using the parser from the command line

You do not need an MCP client or an AI service to use the natural language parser. The `mcprojsim generate` command runs the same parser directly from the terminal:

```bash
mcprojsim generate description.txt -o my_project.yaml
```

See [Running Simulations — `mcprojsim generate`](12_running_simulations.md#mcprojsim-generate) for the full command reference and all options.

## Using the MCP tools directly from Python

While the MCP server is the primary way to use the parser through an AI assistant, you can also call the parser directly from Python code:

```python
from mcprojsim.nl_parser import NLProjectParser

description = """
Project name: My Project
Start date: 2026-01-15
Task 1:
- Design phase
- Size: M
Task 2:
- Implementation
- Depends on Task 1
- Size: XL
"""

parser = NLProjectParser()

# Parse and generate YAML in one step
yaml_output = parser.parse_and_generate(description)
print(yaml_output)

# Or parse first, inspect, then generate
project = parser.parse(description)
print(f"Project: {project.name}")
print(f"Tasks: {len(project.tasks)}")
for task in project.tasks:
    print(f"  Task {task.number}: {task.name} ({task.t_shirt_size})")

yaml_output = parser.to_yaml(project)

# Save to file
with open("my_project.yaml", "w") as f:
    f.write(yaml_output)
```



## Tips & tricks

### Start simple, then enrich

The parser generates a minimal but valid project file. After generating the initial YAML, you can manually add:

- **Uncertainty factors** (`team_experience`, `requirements_maturity`, etc.)
- **Task-level risks** (e.g., "API complexity higher than expected")
- **Project-level risks** (e.g., "Key team member leaves")
- **Custom confidence levels** or threshold overrides

This two-step workflow — generate the skeleton, then enrich — is often faster than writing everything from scratch.

### Use the validation tool first

Before generating a file, ask your AI assistant to validate the description. This catches common problems early:

> "Validate this project description for me."

The `validate_project_description` tool will flag:

- Missing project name or start date
- Tasks without any estimate
- Dependencies referencing non-existent tasks

### Be consistent with task numbering

When using `Task N:` headers, the parser uses these numbers to resolve dependencies. If you write `Task 1`, `Task 2`, `Task 5` (skipping 3 and 4), the parser will still work — but a dependency like `Depends on Task 3` will not resolve to anything.

When using auto-detected lists (plain numbered or bullets), the same numbering rules apply. Bullet lists are auto-numbered starting from 1.

### Mix estimation methods across tasks

Different tasks can use different estimation methods within the same project. For example:

```text
Task 1:
- Well-understood work
- Estimate: 3/5/8 days
Task 2:
- Vaguely scoped work
- Size: XL
Task 3:
- Agile team estimate
- Story points: 8
```

The parser handles this correctly, and `mcprojsim` will resolve each estimate type using the appropriate configuration mapping.

### Use a configuration file for T-shirt sizes and story points

The generated YAML uses symbolic estimates (`t_shirt_size: "M"` or `story_points: 5`). These are resolved to numeric ranges at simulation time using a configuration file. If you want custom mappings, create a `config.yaml`:

```yaml
t_shirt_sizes:
  story:
    M:
      low: 40
      expected: 60
      high: 120
  epic:
    M:
      low: 200
      expected: 480
      high: 1200

t_shirt_size_default_category: epic
```

Then run the simulation with:

```bash
mcprojsim simulate my_project.yaml --config config.yaml
```

See [Configuration](14_configuration.md) for full details on customizing the mappings.

### Generating files for quick "what-if" scenarios

The MCP server is particularly useful for rapid scenario comparison. You can ask your AI assistant:

> "Generate a project file with 5 tasks, all size M, in a chain of dependencies — then a second version where tasks 2 and 3 run in parallel."

Compare the simulation results side by side to see how parallelism affects the schedule distribution.

### Handling the generated YAML output

When the AI assistant returns the generated YAML, you can:

1. **Copy it into a file** and run `mcprojsim validate` to double-check.
2. **Ask the assistant to save it** if your MCP client supports file operations.
3. **Pipe it into the simulation** if you prefer a scripted workflow:

```bash
echo '<paste YAML here>' > project.yaml && mcprojsim simulate project.yaml
```

### Known limitations

The natural language parser is a pattern-based parser, not a full natural language understanding system. Keep these points in mind:

- **Uncertainty factors** are not extracted from natural language input. Add them to the YAML file after generation.
- **Resource definitions** and **calendar constraints** are supported, but only through recognized semi-structured patterns (not arbitrary prose).
- **Project-level risks** are not extracted from the description. Add them manually.
- The parser expects either **numbered task headers** (`Task 1:`, `Task 2:`) or **auto-detected lists** (plain numbered, bullet, or bracket lists). The two modes cannot be mixed in the same description. See [Natural Language Input](15_nl_processing.md) for details.
- **Circular dependencies** are not detected by the parser — they will be caught when you load the file with `mcprojsim validate`.
- Advanced structures such as full volatility-overlay and spillover calibration blocks are still best edited directly in YAML after generation.

\newpage
