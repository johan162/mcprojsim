# MCP Server & Natural Language Project Input

Writing a full YAML project file by hand is straightforward once you know the format, but it takes time — especially when you are in an early planning session and just want to sketch out tasks quickly. The mcprojsim **MCP server** bridges that gap. It lets an AI assistant (such as Claude, GitHub Copilot, or any MCP-compatible client) convert a rough, natural-language project description into a syntactically correct project specification file that `mcprojsim` can simulate immediately.

This chapter explains what the MCP server is, how to install and configure it, how the natural language parser works, and how to get the best results from it.

---

## What is the MCP server?

The **Model Context Protocol (MCP)** is an open standard that lets AI assistants call external tools in a structured way. The mcprojsim MCP server exposes three tools:

| Tool | Purpose |
|------|--------|
| `generate_project_file` | Takes a natural language project description and returns a valid mcprojsim YAML project file |
| `validate_project_description` | Checks a description for problems (missing estimates, broken dependencies) without generating output |
| `simulate_project` | Generates the YAML **and** runs a Monte Carlo simulation in a single step, returning both the project file and results |

When an MCP client connects to the server, the AI assistant can invoke these tools on your behalf. You describe a project in plain language, the assistant calls `generate_project_file` or `simulate_project`, and you get back a ready-to-use result.

---

## Prerequisites and installation

The MCP server has one additional dependency beyond the core `mcprojsim` package: the `mcp` Python library. It is declared as an optional dependency group so it does not affect users who do not need the server.

### Step 1: Install mcprojsim with MCP support

If you already have the project checked out and use Poetry:

```bash
poetry install --with mcp
```

This installs the `mcp` package alongside the existing dependencies. The `--with mcp` flag pulls in only the MCP group without affecting other optional groups like `docs` or `dev`.

### Step 2: Verify the installation

After installation, the `mcprojsim-mcp` entry point should be available:

```bash
mcprojsim-mcp --help
```

You can also verify from Python:

```python
from mcprojsim.mcp_server import main
```

If this import succeeds without an `ImportError`, the MCP dependencies are correctly installed.

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

---

## Workflow overview

There are two workflows depending on whether you want to review the YAML before simulating or go directly to results.

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

#### `simulate_project` parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `description` | string | required | Natural language project description |
| `iterations` | integer | 10000 | Number of Monte Carlo iterations |
| `seed` | integer | none | Random seed for reproducible results |
| `config_yaml` | string | none | Custom configuration YAML content (as a string) |

The `config_yaml` parameter lets you pass custom T-shirt size mappings, uncertainty factor values, or simulation settings inline without needing a separate file.

You can also ask the assistant to validate first:

> "Validate this project description before generating the file."

The assistant will call `validate_project_description` and report any warnings (missing estimates, undefined dependencies) before you commit to generating the file.

---

## Natural language input format

The parser is intentionally tolerant of formatting variations. It understands semi-structured text that follows a simple pattern: project metadata at the top, then numbered tasks with bullet-point attributes.

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

---

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
      min: 2
      most_likely: 3
      max: 5
      unit: "days"
    dependencies: []

  - id: "task_002"
    name: "Write migration scripts"
    estimate:
      min: 5
      most_likely: 8
      max: 15
      unit: "days"
    dependencies: ["task_001"]

  - id: "task_003"
    name: "Data validation"
    estimate:
      min: 8
      most_likely: 16
      max: 32
      unit: "hours"
    dependencies: ["task_002"]

  - id: "task_004"
    name: "Production cutover"
    estimate:
      min: 1
      most_likely: 2
      max: 3
      unit: "days"
    dependencies: ["task_003"]
```

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

---

## Using the parser from the command line

You do not need an MCP client or an AI service to use the natural language parser. The `mcprojsim generate` command runs the same parser directly from the terminal:

```bash
mcprojsim generate description.txt -o my_project.yaml
```

See [Running Simulations — `mcprojsim generate`](running_simulations.md#mcprojsim-generate) for the full command reference and all options.

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

---

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

Tasks must be numbered with `Task N:` headers. The parser uses these numbers to resolve dependencies. If you write `Task 1`, `Task 2`, `Task 5` (skipping 3 and 4), the parser will still work — but a dependency like `Depends on Task 3` will not resolve to anything.

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
  M:
    min: 3
    most_likely: 5
    max: 8
```

Then run the simulation with:

```bash
mcprojsim simulate my_project.yaml --config config.yaml
```

See [Configuration](../configuration.md) for full details on customizing the mappings.

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

- **Task-level risks** and **uncertainty factors** cannot be specified in the natural language input. Add them to the YAML file after generation.
- **Resource definitions** and **calendar constraints** are not supported in the NL input.
- **Project-level risks** are not extracted from the description. Add them manually.
- The parser expects **numbered task headers** (`Task 1:`, `Task 2:`). Free-form task lists without numbers are not recognized.
- **Circular dependencies** are not detected by the parser — they will be caught when you load the file with `mcprojsim validate`.
