# Project files

This chapter is the authoritative reference for the project definition file format used by `mcprojsim`. It documents every supported field, explains the motivation for each feature, and includes examples for every accepted syntax form.

For the formal EBNF grammar that precisely defines what is syntactically valid, see the [Formal Grammar Specification](../grammar.md). This reference uses human-readable prose and worked examples; the grammar is the machine-precise complement.

The parser layer is intentionally simple:

- `.yaml` and `.yml` files are loaded with the YAML parser,
- `.toml` files are loaded with the TOML parser,
- both are then validated against the same `Project` model.

Because of that design, the logical schema is the same regardless of whether you write the file in YAML or TOML.

## Quick reference for new users

The table below summarises every top-level section. The two mandatory sections — `project` and `tasks` — are enough to run your first simulation. Everything else is optional and can be added incrementally.

| Section | Required | Activates |
|---|---|---|
| `project` | **Yes** | Project name, start date, and reporting settings |
| `tasks` | **Yes** | The work items to simulate |
| `project_risks` | No | Cross-cutting risks applied to the whole project |
| `resources` | No | Resource-constrained scheduling (replaces unlimited-workforce mode) |
| `calendars` | No | Custom working hours, holidays, non-standard weeks |
| `sprint_planning` | No | Sprint-based forecasting from historical velocity data |

Inside each task, the only truly required field beyond `id` and `name` is `estimate`. The minimal estimate is a numeric range:

```yaml
estimate:
  low: 1
  expected: 3
  high: 8
```

T-shirt sizes and story points are shorthand alternatives — they map to numeric ranges via the configuration file:

```yaml
estimate:
  t_shirt_size: "M"          # resolved from config, no unit needed
```

```yaml
estimate:
  story_points: 5            # resolved from config, no unit needed
```

For a complete worked example see the [Full YAML example](#full-yaml-example) at the end of this chapter.

## Creating project files

There are three ways to create a project file:

| Method | Best for |
|--------|----------|
| **Write YAML or TOML by hand** | Full control over every field |
| **`mcprojsim generate`** | Quick creation from a natural language description |
| **MCP server** | AI-assisted generation through an MCP client |

The `generate` command converts a plain-text project description into a valid YAML file without requiring any AI service — it runs locally using a built-in pattern-based parser.

### Using `mcprojsim generate`

Write a description in a text file (e.g., `description.txt`):

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
```

Generate the YAML project file:

```bash
mcprojsim generate description.txt -o project.yaml
```

See [Running Simulations — `mcprojsim generate`](running_simulations.md#mcprojsim-generate) for the full command reference and all options. The [MCP Server](mcp-server.md) page covers the complete input format and more examples.

!!! note
    The `generate` command creates a minimal but valid project file. After generating, you can manually add uncertainty factors, risks, resources, and other fields documented in this chapter.

## Supported file formats

The validator and CLI currently recognize these project file extensions:

- `.yaml`
- `.yml`
- `.toml`

Any other extension is rejected as an unsupported file format.

## Top-level structure

At the highest level, a project file may contain the following sections:

- `project` — required
- `tasks` — required
- `project_risks` — optional
- `resources` — optional. When present, constrained scheduling is activated.
- `calendars` — optional. Used by constrained scheduling when resources reference calendars.
- `sprint_planning` — optional. Activates sprint-based simulation mode.

If `project.team_size` is greater than zero, default resources are generated up to that size (after validating explicit resources), which also makes scheduling resource-constrained.

The smallest valid project file therefore looks like this:

```yaml
project:
  name: "My Project"
  start_date: "2026-03-01"

tasks:
  - id: "task_001"
    name: "First task"
    estimate:
      low: 1
      expected: 2
      high: 3
```

### Top-level YAML skeleton

```yaml
project:
  ...

tasks:
  - ...
  - ...

project_risks:
  - ...

resources:
  - ...

calendars:
  - ...
```

### Top-level TOML skeleton

```toml
[project]
# ...

[[tasks]]
# ...

[[project_risks]]
# ...

[[resources]]
# ...

[[calendars]]
# ...
```

## Formal section order

The parser does not require a specific order for top-level sections, but this is the clearest and most conventional order:

1. `project`
2. `project_risks`
3. `tasks`
4. `resources`
5. `calendars`
6. `sprint_planning`

That is also the order used in most examples and in this reference.

## The `project` section

The `project` section is required. It contains project-level metadata and reporting settings.

Every simulation starts here: the `name` and `start_date` are the two fields the engine cannot work without. Everything else in this section controls how results are interpreted and displayed — which confidence percentiles appear in the output, what colour thresholds mark a date as red or green, and what distribution model is used by default across all tasks. You set these once at project level and every task inherits them automatically, which keeps individual task definitions short.

### Supported fields

| Field | Required | Type | Default | Notes |
|---|---|---|---|---|
| `name` | Yes | string | — | Project display name |
| `description` | No | string | `null` | Optional descriptive text |
| `start_date` | Yes | ISO date string | — | Must parse as `YYYY-MM-DD` |
| `currency` | No | string | `"USD"` | Stored as metadata |
| `confidence_levels` | No | list of integers | `[10, 25, 50, 75, 80, 85, 90, 95, 99]` | Controls reported percentiles |
| `hours_per_day` | No | float | `8.0` | Hours in a working day; used for day/week conversion |
| `distribution` | No | `"triangular"` or `"lognormal"` | `"triangular"` | Default estimate distribution for tasks that do not specify one |
| `team_size` | No | integer | `null` | If > `0`, target total resources after validation (may auto-create defaults) |
| `probability_red_threshold` | No | float | `0.50` | Must be between `0.0` and `1.0` |
| `probability_green_threshold` | No | float | `0.90` | Must be between `0.0` and `1.0` |

### Required constraints

The implementation currently enforces these rules for `project`:

- `start_date` must be a valid ISO-format date string or a date object,
- `probability_red_threshold` must be less than `probability_green_threshold`,
- both thresholds must be in the range `0.0` to `1.0`,
- `distribution`, if provided, must be either `triangular` or `lognormal`,
- if provided, `team_size` must be `>= 0`,
- if `team_size > 0` and explicit `resources` are fewer, default resources are added up to `team_size`,
- if explicit `resources` exceed `team_size`, validation fails.

### YAML example

```yaml
project:
  name: "Customer Portal Redesign"
  description: "Next-generation customer portal with enhanced features"
  start_date: "2025-11-01"
  currency: "USD"
  distribution: "triangular"
  confidence_levels: [10, 25, 50, 75, 80, 85, 90, 95, 99]
  probability_red_threshold: 0.50
  probability_green_threshold: 0.90
```

### TOML example

```toml
[project]
name = "Customer Portal Redesign"
description = "Next-generation customer portal with enhanced features"
start_date = "2025-11-01"
currency = "USD"
distribution = "triangular"
confidence_levels = [10, 25, 50, 75, 80, 85, 90, 95, 99]
probability_red_threshold = 0.50
probability_green_threshold = 0.90
```

## The `tasks` section

The `tasks` section is required and must contain at least one task.

A **task** is any unit of schedulable work. You give each task an estimate of its duration, list its dependencies (other tasks that must complete before it can start), and optionally add uncertainty factors, resource requirements, and task-level risks. The simulation samples every task's duration in every iteration and sequences them according to the dependency graph — or, when resources are present, according to resource availability too. The more accurately each task is described, the more representative the resulting uncertainty distribution will be.

Each task is validated as a `Task` object with the following fields.

### Supported task fields

| Field | Required | Type | Default | Notes |
|---|---|---|---|---|
| `id` | Yes | string | — | Must be unique across all tasks |
| `name` | Yes | string | — | Human-readable task name |
| `description` | No | string | `null` | Optional task description |
| `estimate` | Yes | object | — | One of the supported estimate syntaxes |
| `dependencies` | No | list of strings | `[]` | Each entry must match another task `id` |
| `uncertainty_factors` | No | object | defaults applied | Recognized factor fields described below |
| `resources` | No | list of strings | `[]` | Task-level resource names |
| `max_resources` | No | integer | `1` | Max number of resources that may be assigned concurrently |
| `min_experience_level` | No | integer | `1` | Minimum resource experience allowed (`1`, `2`, `3`) |
| `planning_story_points` | No | integer > 0 | `null` | Story point size used for sprint planning; overrides `estimate.story_points` when set |
| `priority` | No | integer | `null` | Scheduling priority hint used in some sprint-planning modes |
| `spillover_probability_override` | No | float 0.0–1.0 | `null` | Per-task override for the probability that incomplete work spills into the next sprint |
| `risks` | No | list of risk objects | `[]` | Task-level probabilistic risks |

### Minimal task example

```yaml
tasks:
  - id: "task_001"
    name: "Design database schema"
    estimate:
      low: 3
      expected: 5
      high: 8
```

### TOML task example

```toml
[[tasks]]
id = "task_001"
name = "Design database schema"

[tasks.estimate]
min = 3
expected = 5
max = 8
```

## The `estimate` section

Every task must define an `estimate` object. The estimate is the engine's primary input: it describes the uncertain duration of a task (or, in sprint planning mode, its size in story points or tasks) so the simulator can draw a different sample in each Monte Carlo iteration.

Choosing the right estimate style matters for accuracy:

- **Triangular** is the simplest and most common choice. It matches the way team members typically think — "at best X, most likely Y, at worst Z" — and is well suited to tasks with a finite worst case.
- **Log-normal** is appropriate for tasks where extreme over-runs are more likely than a symmetric range suggests — for example, research-heavy work, integration tasks with unknown third-party behaviour, or anything where "two to three times longer than expected" is a realistic tail scenario.
- **T-shirt sizes** are useful when teams do not have enough information to produce numeric estimates, or when they want to use a consistent sizing vocabulary across many tasks without converting each size into hours by hand.
- **Story points** are the standard agile unit and are mapped to numeric ranges through the configuration file, with a default mapping included out of the box.

The implementation supports four estimate styles:

1. triangular estimate,
2. log-normal estimate,
3. T-shirt-size estimate,
4. Story Point estimate.

The `distribution` field defaults to `triangular` when omitted. Setting it at task level overrides the project-level default for that task only — useful when most tasks warrant a triangular estimate but a few specific tasks benefit from a log-normal tail model.

For the formal grammar of all estimate forms see [Formal Grammar — `<estimate_spec>`](../grammar.md#project-file-grammar).

### Field name aliases

The model accepts both long-form and short-form names for the three range fields:

| Canonical name | Accepted alias |
|---|---|
| `low` | `min` |
| `expected` | `most_likely` |
| `high` | `max` |

Both forms are valid in YAML and TOML. Examples in this chapter use both; they are equivalent.

### 1. Triangular estimate

This is the default and most common form.

#### Supported fields

| Field | Required | Type | Default |
|---|---|---|---|
| `distribution` | No | `"triangular"` or `"lognormal"` | `null` (inherits project default) |
| `min` | Yes for triangular | number ≥ 0 | `null` |
| `expected` | Yes | number > 0 | `null` |
| `max` | Yes for triangular | number ≥ 0 | `null` |
| `unit` | No | `"hours"`, `"days"`, or `"weeks"` | `"hours"` |

#### Validation rules

For a triangular estimate:

- `expected` must be present,
- `min` must be present,
- `max` must be present,
- `low <= expected <= high`.
- `unit` must be one of `"hours"`, `"days"`, or `"weeks"` if specified.

#### YAML example

```yaml
estimate:
  low: 3
  expected: 5
  high: 10
  unit: "days"
```

#### TOML example

```toml
[tasks.estimate]
min = 3
expected = 5
max = 10
unit = "days"
```

### 2. Log-normal estimate

The implementation also supports **shifted** log-normal estimates. In this mode
you still provide `low`, `expected`, and `high`, but they are interpreted
differently:

- `low` is the hard shift / minimum,
- `expected` is the mode,
- `high` is interpreted as the configured percentile (P95 by default; see `lognormal.high_percentile` in the configuration file).

#### Supported fields

| Field | Required | Type | Notes |
|---|---|---|---|
| `distribution` | Yes | `"lognormal"` | Must be set explicitly |
| `low` | Yes | number ≥ 0 | Required |
| `expected` | Yes | number > 0 | Required |
| `high` | Yes | number ≥ 0 | Required |
| `unit` | No | `"hours"`, `"days"`, or `"weeks"` | `"hours"` |

#### Validation rules

For a log-normal estimate:

- `distribution` must be `lognormal`,
- `low` must be present,
- `expected` must be present,
- `high` must be present,
- `low < expected < high`,
- `unit` must be one of `"hours"`, `"days"`, or `"weeks"` if specified.

#### YAML example

```yaml
estimate:
  distribution: "lognormal"
  low: 3
  expected: 8
  high: 20
  unit: "days"
```

#### TOML example

```toml
[tasks.estimate]
distribution = "lognormal"
low = 3
expected = 8
high = 20
unit = "days"
```

### 3. T-shirt-size estimate

This form lets the task refer to a symbolic size token.

Supported token forms:

- bare size: `M`
- qualified category/size: `epic.M`
- long-form size alias: `Medium`, `Epic.Large`
- full long-form aliases: `EXTRA_SMALL`, `SMALL`, `MEDIUM`, `LARGE`, `EXTRA_LARGE`, `EXTRA_EXTRA_LARGE`

For the complete token grammar see [Formal Grammar — `<tshirt_size>`](../grammar.md#project-file-grammar).

#### Supported fields

| Field | Required | Type | Default |
|---|---|---|---|
| `t_shirt_size` | Yes | string | — |
| `distribution` | No | enum | Defaults to `triangular` |

#### Validation behavior

When `t_shirt_size` is present:

- the `TaskEstimate` validator accepts the estimate immediately,
- explicit `min`, `expected`, and `max` are not required,
- **`unit` must not be specified** — the unit comes from the configuration file's `t_shirt_size_unit` setting (default: `"hours"`),
- the simulation engine resolves the size to actual `min`, `expected`, and `max` values from the active configuration,
- if `distribution` is omitted, the task inherits the project-level default distribution.

If the chosen size does not exist in the active configuration, simulation raises an error.

#### YAML example

```yaml
estimate:
  t_shirt_size: "M"
```

```yaml
estimate:
  t_shirt_size: "epic.M"
```

#### TOML example

```toml
[tasks.estimate]
t_shirt_size = "M"
```

#### Important precedence note

As implemented today, if `t_shirt_size` is present together with explicit numeric estimate fields, the T-shirt-size path takes precedence during validation and resolution.

In other words, this is technically accepted by the model:

```yaml
estimate:
  t_shirt_size: "M"
  low: 1
  expected: 2
  high: 3
```

But it should be treated as ambiguous and avoided in real project files. If you use `t_shirt_size`, prefer to omit the explicit numeric range fields.

### 4. Story Point estimate

This form lets a task use agile-style relative sizing while still simulating an effort range.

#### Supported fields

| Field | Required | Type | Default |
|---|---|---|---|
| `story_points` | Yes | integer | — |
| `distribution` | No | enum | Defaults to `triangular` |

#### Validation behavior

When `story_points` is present:

- the value must currently be one of `1`, `2`, `3`, `5`, `8`, `13`, or `21`,
- **`unit` must not be specified** — the unit comes from the configuration file's `story_point_unit` setting (default: `"days"`),
- the simulation engine resolves the Story Point value to actual `min`, `expected`, and `max` values from the active configuration.

If the chosen Story Point value does not exist in the active configuration, simulation raises an error.

#### YAML example

```yaml
estimate:
  story_points: 5
```

#### TOML example

```toml
[tasks.estimate]
story_points = 5
```

### Symbolic estimate mappings in configuration

Both `t_shirt_size` and `story_points` are symbolic estimate forms. They are converted to numeric ranges by the active configuration, using the unit specified by `t_shirt_size_unit` (default: `"hours"`) and `story_point_unit` (default: `"days"`) respectively. All values are then converted to hours internally.

Built-in defaults exist for both styles, and a custom configuration file may override all or only some of those mappings.

#### Example configuration

```yaml
t_shirt_sizes:
  story:
    M:
      low: 45
      expected: 65
      high: 130
  epic:
    M:
      low: 240
      expected: 520
      high: 1400

t_shirt_size_default_category: epic

story_points:
  5:
    low: 4
    expected: 6
    high: 9
  8:
    low: 6
    expected: 9
    high: 16
```

If a custom configuration overrides only some T-shirt sizes or Story Point values, the remaining built-in defaults stay available.

## The `dependencies` field

`dependencies` is a list of task IDs that must complete before the current task can start.

Dependencies drive the critical-path analysis and scheduling. When the dependency graph is shallow (few dependencies), many tasks can run in parallel, and the project duration is limited mainly by the longest single task. When the graph is deep (long chains of dependent tasks), the critical path grows and the overall schedule becomes more sensitive to individual task delays. Expressing dependencies accurately is therefore important: underspecifying them produces over-optimistic forecasts; overspecifying them produces unnecessarily conservative ones.

### Supported syntax

```yaml
dependencies: []
dependencies: ["task_001"]
dependencies: ["task_001", "task_002", "task_003"]
```

### Validation rules

The project validator enforces that:

- every dependency ID must match an existing task ID,
- task IDs must be unique,
- no circular dependency may exist,
- at least one task must exist overall.

### Example

```yaml
tasks:
  - id: "task_001"
    name: "Backend design"
    estimate:
      low: 2
      expected: 4
      high: 6

  - id: "task_002"
    name: "API implementation"
    estimate:
      low: 5
      expected: 8
      high: 12
    dependencies: ["task_001"]
```

## The `uncertainty_factors` field

At task level, `uncertainty_factors` is modeled as a structured object with a fixed set of recognized fields.

Uncertainty factors apply a multiplier to a task's sampled duration before it enters the schedule. They let you express qualitative risk signals — "the team is junior", "the requirements are immature", "this task integrates with multiple external systems" — without converting those signals into numeric estimates by hand. The multipliers for each factor level are defined in the configuration file; the project file simply assigns a level to each factor.

All five factors are **optional** and each defaults to its baseline level, so you only need to specify factors where a task deviates from a typical baseline. Omitting `uncertainty_factors` entirely applies the full set of baseline defaults.

### Recognized fields

| Field | Default | Valid values |
|---|---|---|
| `team_experience` | `"medium"` | `"high"`, `"medium"`, `"low"` |
| `requirements_maturity` | `"medium"` | `"high"`, `"medium"`, `"low"` |
| `technical_complexity` | `"medium"` | `"low"`, `"medium"`, `"high"` |
| `team_distribution` | `"colocated"` | `"colocated"`, `"distributed"` |
| `integration_complexity` | `"medium"` | `"low"`, `"medium"`, `"high"` |

### YAML example

```yaml
uncertainty_factors:
  team_experience: "high"
  requirements_maturity: "medium"
  technical_complexity: "high"
  team_distribution: "distributed"
  integration_complexity: "medium"
```

### TOML example

```toml
[tasks.uncertainty_factors]
team_experience = "high"
requirements_maturity = "medium"
technical_complexity = "high"
team_distribution = "distributed"
integration_complexity = "medium"
```

### Important implementation note

Only the five fields above are represented by the current project model and used by the simulation engine.

If you add other names under `uncertainty_factors`, they are not part of the supported project-file reference and should not be relied on as active inputs.

The numeric multiplier that each level applies (e.g. `"high"` for `team_experience` → `0.90×`) is defined in the configuration file. See [The `uncertainty_factors` section](#the-uncertainty_factors-section) later in this chapter for the built-in defaults and how to override them.

## The `resources` field inside a task

Each task may list resource names as strings:

```yaml
resources: ["backend_dev", "database_admin"]
```

Task-level `resources` is typed as a list of strings in the current model.

### Resource assignment rule with `max_resources`

When `resources` lists multiple names, the scheduler may still assign fewer resources:

- assignment at task start is capped by `max_resources` (default `1`),
- scheduler applies an automatic practical cap:
  - `granularity_cap = max(1, floor(task_effort_hours / 16.0))`
  - `coordination_cap = 3`
  - `practical_cap = min(granularity_cap, coordination_cap)`
- effective start-time assignment is:
  - `min(max_resources, practical_cap, eligible_available_resources_now)`.

This avoids unrealistic over-assignment on short tasks while still permitting
parallelization on larger tasks.

Important behavior for schema users:

- assignment happens at task start only,
- assigned resources remain fixed for the task execution,
- no mid-task reassignment/swapping is performed.

Also, if you explicitly list resource names and set `min_experience_level`, each named resource must meet that minimum or validation fails.

## The `risks` field inside a task

Each task may have zero or more task-level risks.

A **risk** models a discrete event that may or may not occur during the task. In each Monte Carlo iteration, the engine draws a Bernoulli sample for each risk using its `probability`. When the risk fires, the `impact` is added to the task's sampled duration. This cleanly separates planned estimation uncertainty (captured by the estimate range) from identified discrete risks (captured here). It lets you quantify the schedule impact of a risk without baking it unconditionally into the estimate.

Task-level risks are appropriate for events that affect only one task — for example, "the third-party API may introduce a breaking change during this task" at probability 0.15. For events that could affect the whole project — for example, "key stakeholder may request a scope change" — use `project_risks` instead.

For the complete risk grammar see [Formal Grammar — `<risk_properties>`](../grammar.md#project-file-grammar).

### Task-level risk object fields

| Field | Required | Type | Notes |
|---|---|---|---|
| `id` | Yes | string | Risk identifier |
| `name` | Yes | string | Display name |
| `probability` | Yes | float | Must be between `0.0` and `1.0` |
| `impact` | Yes | number or object | See below |
| `description` | No | string | Optional |

### Risk impact syntax

The `impact` field can be specified in two ways but is normally specified as as structured object. The two ways to specify risk impact are: 

#### 1. Structured impact object (recommended)

This may be either of type `"absolute"` or type `"percentage"` and is the 
clearest way to specify a risk as it is unambigous. A unit can only be specified if the type `"absolute"` since the percentage is applied to the already specified unit for the simulation result either for the task or the overall effort for the project. The following example makes it clear:

```yaml
risks:
  - id: "risk_001"
    name: "Architecture rework"
    probability: 0.20
    impact:
      type: "absolute"
      value: 5
      unit: "days"
risks:
  - id: "risk_002"
    name: "Approval delay"
    probability: 0.10
    impact:
      type: "percentage"
      value: 15
```

In the first case `risk_001` the risk adds 5 working days (`=hours_per_day*5`). Unit can be one of `"hours"`, `"days"` or `"weeks"`.

#### 2. Short form

This is interpreted as an absolute time penalty in hours and is supplied as a "quick-and-dirty" way to specify a risk impact. However, we strongly recommend that the full structured object way is used!

```yaml
risks:
  - id: "risk_001"
    name: "Integration issues"
    probability: 0.25
    impact: 3  # Interpretated as an absolute impact in hours
```

**Caution:**

```
  ✅ Correct:
  risks:
    - id: "risk_001"
      name: "Delay"
      probability: 0.2
      impact:
        type: "absolute"
        value: 3
        unit: "days"
  
  ❌ Wrong:
  risks:
    - id: "risk_001"
      name: "Delay"
      probability: 0.2
      impact: 3
      unit: "days"  ← unit goes inside impact, not outside
  ```


### Validation rules for risks

The model enforces:

- `probability` must be between `0.0` and `1.0`,
- `impact.value` must be greater than `0` when object syntax is used,
- numeric impacts are converted to floats,
- structured impacts must use `type: "absolute"` or `type: "percentage"`.
- a unit only makes sense for `"absolute"`type of impact

## The `project_risks` section

`project_risks` has exactly the same syntax as task-level `risks`, but it appears at top level and applies to the project as a whole.

When a project-level risk fires in a Monte Carlo iteration, its impact is added to the total elapsed project duration (on top of the scheduled task chain). Use `project_risks` for cross-cutting uncertainties — late design freezes, vendor delays, or regulatory response times — that cannot be cleanly attributed to a single task.

### Example

```yaml
project_risks:
  - id: "proj_risk_001"
    name: "Requirements change"
    probability: 0.30
    impact:
      type: "absolute"
      value: 10
      unit: "days"
    description: "Late business scope change"
```

**Note:** Be careful if you add an impact type of percentage as a top level risk as it is added as a multiplicative percentage to the overall simulated effort.

## The top-level `resources` section

Adding a `resources` section switches the scheduler from **dependency-only** mode to **resource-constrained** mode. In dependency-only mode the scheduler assumes unlimited workforce and sequences tasks purely by dependencies. In resource-constrained mode each task can only start when both its dependencies are satisfied *and* a suitable resource is available. This produces longer but more realistic schedules whenever the team is genuinely the bottleneck.

If you prefer not to enumerate individual resources, you can instead set `project.team_size` to a number of default resources to generate automatically.

Each `resources` entry supports the following fields:

### Supported fields

| Field | Required | Type | Default | Constraints |
|---|---|---|---|---|
| `name` | No | string | auto-generated | Unique across all resolved resource names |
| `id` | No | string | `null` | Legacy fallback for `name`; still accepted |
| `experience_level` | No | integer | `2` | Must be `1`, `2`, or `3` |
| `productivity_level` | No | float | `1.0` | 0.1 to 2.0 |
| `sickness_prob` | No | float | `0.0` | 0.0 to 1.0 |
| `planned_absence` | No | list of dates | `[]` | ISO `YYYY-MM-DD` format |
| `calendar` | No | string | `"default"` | Must match a calendar `id` if calendars are defined |
| `availability` | No | float | `1.0` | Must be in (0, 1] |

!!! note
    If `name` is omitted, the engine auto-generates a unique name (`resource_001`, `resource_002`, …). The legacy `id` field is still accepted and used as a fallback for `name`.

### YAML example

```yaml
resources:
  - name: "backend_dev"
    experience_level: 3
    productivity_level: 1.1
    sickness_prob: 0.05
    planned_absence:
      - "2026-07-01"
      - "2026-07-02"
  - experience_level: 2
    productivity_level: 0.9
    sickness_prob: 0.08
```

## The top-level `calendars` section

Calendars control when resources are available. Without a calendar definition, the scheduler uses an 8-hour / 5-day working week. Defining a calendar lets you model public holidays, reduced-hour days, or non-standard working weeks. Each resource can reference a specific calendar by name; resources that do not specify one fall back to the `default` calendar.

Each `calendars` entry supports the following fields:

| Field | Required | Type | Default | Notes |
|---|---|---|---|---|
| `id` | No | string | `"default"` | Must be unique across all calendars |
| `work_hours_per_day` | No | float > 0 | `8.0` | Number of working hours in a day |
| `work_days` | No | list of integers | `[1, 2, 3, 4, 5]` | Days of the week; 1 = Monday, 7 = Sunday |
| `holidays` | No | list of ISO dates | `[]` | Dates in `YYYY-MM-DD` format |

### YAML example

```yaml
calendars:
  - id: "standard"
    work_hours_per_day: 8
    work_days: [1, 2, 3, 4, 5]
    holidays:
      - "2026-12-25"
      - "2026-12-26"
```

## The `sprint_planning` section

The optional `sprint_planning` section activates sprint-based simulation mode. When present and `enabled: true`, the engine models work as a sequence of fixed-length sprints rather than a single elapsed duration. Each sprint draws a velocity from the historical distribution, places as many backlog items as will fit, and carries the rest forward to the next sprint. The output is a distribution over the number of sprints (and hence calendar weeks) needed to complete the backlog, rather than a raw elapsed-hours distribution.

Use sprint planning when the team works in fixed-length iterations and tracks velocity \u2014 whether measured in story points or tasks completed per sprint. The historical sprint data you provide is the primary input: the simulator fits a velocity distribution to it and samples from that distribution in each Monte Carlo iteration.

!!! note
    Sprint planning requires at least two usable historical sprint entries (entries with a positive delivery signal). The `capacity_mode` field controls whether the unit of delivery is story points or task counts, and **must be consistent** across all history entries and task backlogs.

For a comprehensive walkthrough of sprint planning features, configuration options, and interpretation of results, see [Sprint Planning](sprint_planning.md).

### Top-level sprint planning fields

| Field | Required | Type | Default | Notes |
|---|---|---|---|---|
| `enabled` | No | boolean | `false` | When `false`, the section is parsed but not simulated |
| `sprint_length_weeks` | Yes | integer > 0 | \u2014 | Duration of each sprint in calendar weeks |
| `capacity_mode` | Yes | `story_points` \| `tasks` | \u2014 | Unit family for all velocity and backlog measurements |
| `planning_confidence_level` | No | float (0, 1) | `0.80` | Percentile of the sprint count distribution reported |
| `velocity_model` | No | `empirical` \| `neg_binomial` | `empirical` | Distribution fitted to historical velocity observations |
| `removed_work_treatment` | No | `churn_only` \| `reduce_backlog` | `churn_only` | How removed sprint items affect the net backlog |
| `history` | No | list or external descriptor | `[]` | Historical sprint data; see below |
| `future_sprint_overrides` | No | list | `[]` | Forward-looking capacity adjustments |
| `volatility_overlay` | No | object | disabled | Sprint-level disruption model |
| `spillover` | No | object | disabled | Task-level spillover model |
| `sickness` | No | object | disabled | Per-person sickness model |

#### `velocity_model` values

| Value | Meaning |
|---|---|
| `empirical` | Resample directly from observed historical velocities |
| `neg_binomial` | Fit a negative-binomial distribution to history and sample from that |

#### `removed_work_treatment` values

| Value | Meaning |
|---|---|
| `churn_only` | Removed items are treated as pure churn with no net effect on remaining backlog |
| `reduce_backlog` | Removed items reduce the total backlog to be completed |

### Minimal example

```yaml
sprint_planning:
  enabled: true
  sprint_length_weeks: 2
  capacity_mode: story_points
  history:
    - sprint_id: "SPR-001"
      completed_story_points: 10
      spillover_story_points: 1
    - sprint_id: "SPR-002"
      completed_story_points: 9
      spillover_story_points: 2
    - sprint_id: "SPR-003"
      completed_story_points: 11
```

For a `tasks`-based project, replace `completed_story_points` with `completed_tasks` and set `capacity_mode: tasks`.

### Sprint history

Historical sprint data is the empirical foundation of the sprint planning simulation. Rather than asking you to specify a single velocity, `mcprojsim` fits a probability distribution to your team's observed sprint outcomes and samples from that distribution in each Monte Carlo iteration. The result is a forecast of "how many sprints will this backlog require?" expressed as a confidence interval, not a single number.

#### Why history matters

Two sprints of history give the simulator just enough to estimate the spread of the velocity distribution. More history reduces sampling uncertainty and produces tighter, more reliable confidence intervals. A minimum of two usable entries — entries where the delivery signal (completed points or tasks) is greater than zero — is required when `enabled: true`.

The velocity the simulator works with is not simply `completed_story_points`. For each historical sprint it computes the **effective velocity** as:

```
effective_velocity = completed + spillover - added + removed  (treatment-dependent)
```

This means `spillover_story_points`, `added_story_points`, and `removed_story_points` all influence the distribution the simulator samples from. The more accurately you record them, the more representative the velocity distribution will be.

#### Unit-family consistency

All history entries in a project file must belong to the same unit family as `capacity_mode`. You cannot mix `completed_story_points` entries with `completed_tasks` entries in a single `history` list.

#### Inline history format

Each `history` list entry represents one completed sprint. Fields marked *Conditional* are required only for the chosen `capacity_mode`.

| Field | Required | Type | Default | Notes |
|---|---|---|---|---|
| `sprint_id` | Yes | string | — | Unique string identifier for the sprint; must be non-empty |
| `sprint_length_weeks` | No | integer > 0 | inherits top-level `sprint_length_weeks` | Override sprint length for this individual entry |
| `completed_story_points` | Conditional | float ≥ 0 | — | Completed capacity; required when `capacity_mode: story_points` |
| `completed_tasks` | Conditional | integer ≥ 0 | — | Completed capacity; required when `capacity_mode: tasks` |
| `spillover_story_points` | No | float ≥ 0 | `0` | Story points that carried over from the previous sprint into this one |
| `spillover_tasks` | No | integer ≥ 0 | `0` | Tasks that carried over from the previous sprint into this one |
| `added_story_points` | No | float ≥ 0 | `0` | Story points added to the sprint backlog mid-sprint |
| `added_tasks` | No | integer ≥ 0 | `0` | Tasks added to the sprint backlog mid-sprint |
| `removed_story_points` | No | float ≥ 0 | `0` | Story points removed from the sprint backlog mid-sprint |
| `removed_tasks` | No | integer ≥ 0 | `0` | Tasks removed from the sprint backlog mid-sprint |
| `holiday_factor` | No | float > 0 | `1.0` | Capacity reduction from public holidays; `0.8` means 20% reduction |
| `end_date` | No | ISO date string | `null` | Date the sprint ended; used for timeline charts and calendar alignment |
| `team_size` | No | integer ≥ 0 | `null` | Actual team headcount during this sprint |
| `notes` | No | string | `null` | Free-text annotation; not used by the simulator |

!!! note
    Story-point and task-count fields are mutually exclusive within a single entry. Do not mix `completed_story_points` with `spillover_tasks`, `added_tasks`, or `removed_tasks` in the same entry, or vice versa. The validator will reject it.

#### Story-point mode example

```yaml
sprint_planning:
  enabled: true
  sprint_length_weeks: 2
  capacity_mode: story_points
  history:
    - sprint_id: "SPR-001"
      completed_story_points: 34
      spillover_story_points: 2
    - sprint_id: "SPR-002"
      completed_story_points: 28
      spillover_story_points: 4
      added_story_points: 3
    - sprint_id: "SPR-003"
      completed_story_points: 31
      removed_story_points: 2
      holiday_factor: 0.9
      end_date: "2026-03-14"
      notes: "Public holiday reduced capacity"
```

#### Task-count mode example

```yaml
sprint_planning:
  enabled: true
  sprint_length_weeks: 1
  capacity_mode: tasks
  history:
    - sprint_id: "WK-01"
      completed_tasks: 7
      spillover_tasks: 1
    - sprint_id: "WK-02"
      completed_tasks: 6
      spillover_tasks: 2
      added_tasks: 1
    - sprint_id: "WK-03"
      completed_tasks: 8
```

#### External history format

For teams that maintain sprint data in a separate file, `mcprojsim` can load history from an external JSON or CSV source instead of an inline list:

```yaml
sprint_planning:
  enabled: true
  sprint_length_weeks: 2
  capacity_mode: story_points
  history:
    format: json
    path: "sprint_planning_history.json"
```

Supported formats:

| Value | Description |
|---|---|
| `json` | A JSON file containing either a top-level array of sprint objects, or an object with a `sprints` key whose value is that array |
| `csv` | A CSV file with a header row; column names must match the field names in the table above |

The external file must use the same field names as the inline entries. See [Sprint Planning](sprint_planning.md) for complete JSON and CSV shape examples.

### `future_sprint_overrides`

Forward-looking sprint overrides let you express known capacity variations in upcoming sprints \u2014 for example, a holiday week that will reduce capacity by 20%, or a sprint where the team is larger.

Each override must identify its target sprint via at least one of `sprint_number` or `start_date`.

| Field | Required | Type | Default | Notes |
|---|---|---|---|---|
| `sprint_number` | Conditional | integer > 0 | `null` | 1-based sprint number relative to the start of simulation |
| `start_date` | Conditional | date string | `null` | ISO date of the sprint start |
| `holiday_factor` | No | float > 0 | `1.0` | Capacity scaling due to holidays |
| `capacity_multiplier` | No | float > 0 | `1.0` | Additional scaling factor (e.g. `0.5` for a half-team sprint) |
| `notes` | No | string | `null` | Annotation |

The effective capacity for an overridden sprint is `holiday_factor \u00d7 capacity_multiplier` of the baseline.

```yaml
future_sprint_overrides:
  - sprint_number: 3
    holiday_factor: 0.8
    notes: "Easter week"
  - start_date: "2026-06-15"
    capacity_multiplier: 0.5
    notes: "Half the team at off-site"
```

### Task fields used by sprint planning

When `sprint_planning` is active, three additional task fields become relevant:

| Field | Type | `capacity_mode` | Notes |
|---|---|---|---|
| `planning_story_points` | integer > 0 | `story_points` | Story point size for sprint planning; overrides `estimate.story_points` when set |
| `priority` | integer | both | Scheduling priority hint; lower values are allocated to sprints first |
| `spillover_probability_override` | float 0.0\u20131.0 | both | Per-task spillover probability, overrides the model default |

### Configuration interaction

The `sprint_defaults` section in the configuration file supplies default values for every `sprint_planning` parameter. Any value set directly in the project file's `sprint_planning` section overrides the corresponding config default. This means you can tune velocity models, sickness parameters, and spillover behaviour once in a shared config file and override only sprint-specific values in each project file.

\newpage 

## Full YAML example

The following example demonstrates every currently recognized project-file section in one file.

```yaml
project:
  name: "Reference Example"
  description: "Comprehensive project file example"
  start_date: "2026-04-01"
  currency: "USD"
  confidence_levels: [50, 75, 80, 90, 95]
  probability_red_threshold: 0.45
  probability_green_threshold: 0.90

project_risks:
  - id: "proj_risk_001"
    name: "Late stakeholder change"
    probability: 0.20
    impact:
      type: "absolute"
      value: 4
      unit: "days"

tasks:
  - id: "task_001"
    name: "Design"
    description: "Design the feature set"
    estimate:
      low: 2
      expected: 4
      high: 7
      unit: "days"
    dependencies: []
    uncertainty_factors:
      team_experience: "high"
      requirements_maturity: "medium"
    resources: ["designer"]
    risks:
      - id: "task_risk_001"
        name: "Clarification delay"
        probability: 0.15
        impact: 1.5
```

```yaml
  - id: "task_002"
    name: "Implementation"
    estimate:
      distribution: "lognormal"
      low: 3
      expected: 8
      high: 20
      unit: "days"
    dependencies: ["task_001"]
    uncertainty_factors:
      team_experience: "medium"
      technical_complexity: "high"
      team_distribution: "distributed"
    resources: ["backend_dev", "frontend_dev"]

  - id: "task_003"
    name: "Deployment"
    estimate:
      t_shirt_size: "S"
    dependencies: ["task_002"]

resources:
  - name: "designer"
  - name: "backend_dev"
  - name: "frontend_dev"

calendars:
  - id: "standard"
    work_days: [1, 2, 3, 4, 5]
    holidays:
      - "2026-12-25"
```
\newpage

## Full TOML example

The same logical content can be written in TOML. The most important syntax difference is that repeated entries such as tasks and risks use array-of-table syntax.

```toml
[project]
name = "Reference Example"
description = "Comprehensive project file example"
start_date = "2026-04-01"
currency = "USD"
confidence_levels = [50, 75, 80, 90, 95]
probability_red_threshold = 0.45
probability_green_threshold = 0.90

[[project_risks]]
id = "proj_risk_001"
name = "Late stakeholder change"
probability = 0.20

[project_risks.impact]
type = "absolute"
value = 4
unit = "days"

[[tasks]]
id = "task_001"
name = "Design"
description = "Design the feature set"
dependencies = []
resources = ["designer"]

[tasks.estimate]
min = 2
expected = 4
max = 7
unit = "days"

[tasks.uncertainty_factors]
team_experience = "high"
requirements_maturity = "medium"

[[tasks.risks]]
id = "task_risk_001"
name = "Clarification delay"
probability = 0.15
impact = 1.5

[[tasks]]
id = "task_002"
name = "Implementation"
dependencies = ["task_001"]
resources = ["backend_dev", "frontend_dev"]

[tasks.estimate]
distribution = "lognormal"
low = 3
expected = 8
high = 20
unit = "days"

[tasks.uncertainty_factors]
team_experience = "medium"
technical_complexity = "high"
team_distribution = "distributed"
```

```toml
[[tasks]]
id = "task_003"
name = "Deployment"
dependencies = ["task_002"]

[tasks.estimate]
t_shirt_size = "S"

[[resources]]
name = "designer"

[[resources]]
name = "backend_dev"

[[resources]]
name = "frontend_dev"

[[calendars]]
id = "standard"
work_days = [1, 2, 3, 4, 5]
holidays = ["2026-12-25"]
```

## Configuration file reference

The project file defines the work being simulated. The configuration file defines how `mcprojsim` interprets uncertainty, symbolic estimates, reporting defaults, and staffing analysis.

Use a configuration file when you want to:

- change uncertainty multipliers,
- override T-shirt size mappings,
- override Story Point mappings,
- set simulation and report defaults,
- tune staffing analysis behavior.

Unlike project files, the configuration file is currently loaded as YAML.

### How configuration loading works

When you pass `--config config.yaml`, the loader:

1. starts from the built-in default configuration,
2. reads your YAML file,
3. merges your values into the defaults recursively,
4. validates the result against the `Config` model.

That means you can override only the values you care about. For example, if you provide only `t_shirt_sizes.M`, the built-in definitions for `XS`, `S`, `L`, `XL`, and `XXL` remain available.

### Top-level configuration structure

The current configuration schema supports these top-level sections:

- `uncertainty_factors`
- `t_shirt_sizes`
- `t_shirt_size_unit`
- `t_shirt_size_default_category`
- `story_points`
- `story_point_unit`
- `lognormal`
- `simulation`
- `output`
- `staffing`
- `constrained_scheduling`
- `sprint_defaults`

### Minimal configuration example

```yaml
simulation:
  default_iterations: 5000

staffing:
  effort_percentile: 80
```

### Full configuration skeleton

```yaml
uncertainty_factors:
  team_experience:
    high: 0.90
    medium: 1.0
    low: 1.30
  requirements_maturity:
    high: 1.0
    medium: 1.15
    low: 1.40
  technical_complexity:
    low: 1.0
    medium: 1.20
    high: 1.50
  team_distribution:
    colocated: 1.0
    distributed: 1.25
  integration_complexity:
    low: 1.0
    medium: 1.15
    high: 1.35
t_shirt_sizes:
  story:
    XS:
      low: 3
      expected: 5
      high: 15
    M:
      low: 40
      expected: 60
      high: 120
  epic:
    M:
      low: 200
      expected: 480
      high: 1200
t_shirt_size_unit: "hours"
t_shirt_size_default_category: "epic"
story_points:
  1:
    low: 0.5
    expected: 1
    high: 3
  5:
    low: 3
    expected: 5
    high: 8
```

```yaml
story_point_unit: "days"

lognormal:
  high_percentile: 95

simulation:
  default_iterations: 10000
  random_seed: null
  max_stored_critical_paths: 20

output:
  formats: ["json", "csv", "html"]
  include_histogram: true
  number_bins: 50
  critical_path_report_limit: 2

staffing:
  min_individual_productivity: 0.25
  experience_profiles:
    senior:
      productivity_factor: 1.0
      communication_overhead: 0.04
    mixed:
      productivity_factor: 0.85
      communication_overhead: 0.06
    junior:
      productivity_factor: 0.65
      communication_overhead: 0.08
constrained_scheduling:
  assignment_mode: "greedy_single_pass"
  pass1_iterations: 1000
  sickness_prob: 0.0

sprint_defaults:
  planning_confidence_level: 0.80
  velocity_model: "empirical"
  removed_work_treatment: "churn_only"
```

## The `uncertainty_factors` section

This section maps uncertainty factor names to per-level multipliers.

### YAML structure

```yaml
uncertainty_factors:
  factor_name:
    level_name: 1.0
    another_level: 1.0
```

### Supported fields

| Field | Required | Type | Default | Notes |
|---|---|---|---|---|
| factor name | No | mapping | built-in defaults | Outer keys are factor names |
| level name | No | float | none at the schema level | Inner keys depend on the factor, for example `high`, `medium`, `low`, `colocated`, or `distributed` |

### Built-in level names by factor

| Factor | Built-in level names |
|---|---|
| `team_experience` | `high`, `medium`, `low` |
| `requirements_maturity` | `high`, `medium`, `low` |
| `technical_complexity` | `low`, `medium`, `high` |
| `team_distribution` | `colocated`, `distributed` |
| `integration_complexity` | `low`, `medium`, `high` |

### Built-in factor names

The default configuration defines these factor names:

- `team_experience`
- `requirements_maturity`
- `technical_complexity`
- `team_distribution`
- `integration_complexity`

These are also the names used by the current project-file model under `tasks[].uncertainty_factors`.

### Built-in defaults

| Factor | High / low-side values | Medium / baseline |
|---|---|---|
| `team_experience` | `high: 0.90`, `low: 1.30` | `medium: 1.0` |
| `requirements_maturity` | `high: 1.0`, `low: 1.40` | `medium: 1.15` |
| `technical_complexity` | `low: 1.0`, `high: 1.50` | `medium: 1.20` |
| `team_distribution` | `colocated: 1.0`, `distributed: 1.25` | not applicable |
| `integration_complexity` | `low: 1.0`, `high: 1.35` | `medium: 1.15` |

!!! note
    The configuration model can parse arbitrary nested dictionaries here, but the current project-file schema only exposes the recognized uncertainty-factor names listed above. Extra factor names in the config file are not useful unless the source model and simulation logic also reference them.

## The `t_shirt_sizes` section

This section maps symbolic T-shirt sizes to numeric effort ranges by category. The typical structure looks like this:

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

### Supported fields for each category/size entry

| Field | Required | Type | Default | Constraints |
|---|---|---|---|---|
| `low` | Yes when that size is defined | float | — | `> 0` |
| `expected` | Yes | float | — | `> 0` |
| `high` | Yes | float | — | `> 0` |

### Built-in category keys

- `bug`
- `story`
- `epic`
- `business`
- `initiative`

### Built-in size keys (per category)

- `XS`
- `S`
- `M`
- `L`
- `XL`
- `XXL`

### Built-in `story` defaults

| Size | `low` | `expected` | `high` |
|---|---:|---:|---:|
| `XS` | 3 | 5 | 15 |
| `S` | 5 | 16 | 40 |
| `M` | 40 | 60 | 120 |
| `L` | 160 | 240 | 500 |
| `XL` | 320 | 400 | 750 |
| `XXL` | 400 | 500 | 1200 |

### Example override

```yaml
t_shirt_sizes:
  story:
    M:
      low: 45
      expected: 65
      high: 130

t_shirt_size_default_category: epic
```

With this override, only `story.M` changes. Other built-in categories and sizes remain available.

## The `t_shirt_size_unit` field

This field controls the unit used for all values in `t_shirt_sizes`.

### Supported values

- `"hours"`
- `"days"`
- `"weeks"`

### Default

`"hours"`

### Example

```yaml
t_shirt_size_unit: "days"
```

If a task uses `estimate.t_shirt_size: "M"`, the simulator resolves it through `t_shirt_size_default_category`. A qualified value like `estimate.t_shirt_size: "epic.M"` resolves directly to that category.

## The `story_points` section

This section maps Story Point values to numeric effort ranges.

### Supported fields for each point value

| Field | Required | Type | Default | Constraints |
|---|---|---|---|---|
| `low` | Yes when that point value is defined | float | — | `> 0` |
| `expected` | Yes | float | — | `> 0` |
| `high` | Yes | float | — | `> 0` |

### Built-in point values

- `1`
- `2`
- `3`
- `5`
- `8`
- `13`
- `21`

### Built-in defaults

| Points | `low` | `expected` | `high` |
|---|---:|---:|---:|
| `1` | 0.5 | 1 | 3 |
| `2` | 1 | 2 | 4 |
| `3` | 1.5 | 3 | 5 |
| `5` | 3 | 5 | 8 |
| `8` | 5 | 8 | 15 |
| `13` | 8 | 13 | 21 |
| `21` | 13 | 21 | 34 |

### Example override

```yaml
story_points:
  8:
    low: 6
    expected: 9
    high: 16
```

## The `story_point_unit` field

This field controls the unit used for all values in `story_points`.

### Supported values

- `"hours"`
- `"days"`
- `"weeks"`

### Default

`"days"`

## The `lognormal` section

This section controls how the simulation interprets log-normal estimates.

### Supported fields

| Field | Required | Type | Default | Constraints | Notes |
|---|---|---|---|---|---|
| `high_percentile` | No | integer | `95` | one of `70`, `75`, `80`, `85`, `90`, `95`, `99` | The percentile that `high` is treated as in a log-normal estimate |

### Example

```yaml
lognormal:
  high_percentile: 90
```

When a task uses `distribution: lognormal`, the `high` value is fitted as this percentile of the resulting distribution. A lower value makes the tail shorter; a higher value widens it.

## The `simulation` section

This section controls default simulation behavior.

### Supported fields

| Field | Required | Type | Default | Constraints | Notes |
|---|---|---|---|---|---|
| `default_iterations` | No | integer | `10000` | `> 0` | Used by commands that rely on config defaults |
| `random_seed` | No | integer or `null` | `null` | none | Set for reproducible runs |
| `max_stored_critical_paths` | No | integer | `20` | `> 0` | Number of full critical path sequences retained in results |

### Example

```yaml
simulation:
  default_iterations: 20000
  random_seed: 42
  max_stored_critical_paths: 50
```

## The `output` section

This section controls reporting and export defaults.

### Supported fields

| Field | Required | Type | Default | Constraints | Notes |
|---|---|---|---|---|---|
| `formats` | No | list of strings | `["json", "csv", "html"]` | each entry must be `json`, `csv`, or `html`; list must not be empty | Default export formats for config-driven workflows |
| `include_histogram` | No | boolean | `true` | — | Whether histogram data should be included where supported |
| `number_bins` | No | integer | `50` | `> 0` | Number of bins for histogram generation |
| `critical_path_report_limit` | No | integer | `2` | `> 0` | Number of stored full critical paths shown in reports by default |

### Example

```yaml
output:
  formats: ["json", "html"]
  include_histogram: true
  number_bins: 80
  critical_path_report_limit: 5
```

## The `staffing` section

This section controls the staffing analysis added to CLI output and exports.

### Supported fields

| Field | Required | Type | Default | Constraints | Notes |
|---|---|---|---|---|---|
| `effort_percentile` | No | integer | omitted | `1..99` when set | Uses that effort percentile instead of the mean for staffing calculations |
| `min_individual_productivity` | No | float | `0.25` | `> 0`, `<= 1` | Lower bound on each person's productivity after communication overhead is applied |
| `experience_profiles` | No | mapping | built-in defaults | profile values validated individually | Defines named team profiles |

When `effort_percentile` is omitted, staffing uses the mean total effort and mean elapsed time. When it is set, staffing uses the matching percentile for both effort and elapsed time, for example P80 effort with P80 elapsed time.

### How `min_individual_productivity` affects team-size efficiency

The staffing model assumes that each additional person creates some communication overhead. For a team of size $n$, the model first calculates a raw per-person productivity:

$$
P_{raw}(n) = 1 - c(n - 1)
$$

where $c$ is the `communication_overhead` for the selected experience profile.

That raw value is then floored by `min_individual_productivity`:

$$
P(n) = \max(P_{min}, P_{raw}(n))
$$

where $P_{min}$ is `min_individual_productivity`.

This means `min_individual_productivity` is not a bonus. It is a safety floor. It prevents the model from predicting that people become almost useless, or literally zero-productivity, as team size increases.

The model then converts per-person productivity into total effective capacity:

$$
E(n) = n \cdot P(n) \cdot f
$$

where $f$ is the profile's `productivity_factor`.

Calendar duration for that team size is then:

$$
T(n) = \max\left(T_{cp}, \frac{W}{E(n)}\right)
$$

where:

- $T_{cp}$ is the critical-path elapsed time,
- $W$ is the total effort in person-hours,
- $E(n)$ is the effective capacity of the team.

Finally, the **Efficiency** shown in the staffing table is calculated relative to the fastest team size found for that profile:

$$
  \text{Efficiency}(n) = \frac{T_{min}}{T(n)}
$$

So `min_individual_productivity` affects efficiency indirectly:

- if the floor is **lower**, very large teams lose more effective capacity as communication overhead grows,
- if the floor is **higher**, large teams retain more capacity and the efficiency drop-off on the right side of the staffing table is less severe,
- if the project is already near the critical-path floor, changing this value may have little visible effect, because no team can compress the schedule below $T_{cp}$ anyway.

### Practical interpretation

- **Small team sizes**: `min_individual_productivity` usually does nothing, because raw productivity is still above the floor.
- **Medium team sizes**: the value may begin to matter if communication overhead becomes significant.
- **Large team sizes**: this setting determines how harshly the model penalises oversized teams.

For example, with `communication_overhead: 0.06`, raw individual productivity is:

- 1 person: $1.00$
- 3 people: $1 - 0.06 \cdot 2 = 0.88$
- 8 people: $1 - 0.06 \cdot 7 = 0.58$
- 15 people: $1 - 0.06 \cdot 14 = 0.16$

If `min_individual_productivity` is `0.25`, the 15-person team is floored to $0.25$ instead of dropping to $0.16$. That keeps the team from looking unrealistically ineffective, while still showing diminishing returns.

In practice:

- use a **lower** value when you want the model to penalise oversized teams more aggressively,
- use a **higher** value when you believe communication overhead is real but should not collapse individual output too sharply,
- keep in mind that this value mainly shapes the **right-hand side** of the efficiency curve, where teams are larger than the optimal size.

### The `experience_profiles` subsection

Each profile name maps to an object with these fields:

| Field | Required | Type | Default | Constraints |
|---|---|---|---|---|
| `productivity_factor` | Yes when that profile is defined | float | — | `> 0` |
| `communication_overhead` | Yes when that profile is defined | float | — | `0..1` |

### Built-in profile defaults

| Profile | `productivity_factor` | `communication_overhead` |
|---|---:|---:|
| `senior` | 1.00 | 0.04 |
| `mixed` | 0.85 | 0.06 |
| `junior` | 0.65 | 0.08 |

### Example

```yaml
staffing:
  effort_percentile: 80
  min_individual_productivity: 0.30
  experience_profiles:
    senior:
      productivity_factor: 1.0
      communication_overhead: 0.03
    contractor:
      productivity_factor: 0.75
      communication_overhead: 0.05
```

### Configuration validation summary

The current configuration model validates these rules directly:

- `t_shirt_size_unit` must be one of `hours`, `days`, or `weeks`,
- `story_point_unit` must be one of `hours`, `days`, or `weeks`,
- `lognormal.high_percentile` must be one of `70`, `75`, `80`, `85`, `90`, `95`, `99`,
- all configured estimate ranges require positive `min`, `expected`, and `max`,
- `output.formats` must be a non-empty list; each entry must be `json`, `csv`, or `html`,
- `simulation.default_iterations` must be greater than 0,
- `simulation.max_stored_critical_paths` must be greater than 0,
- `output.number_bins` must be greater than 0,
- `output.critical_path_report_limit` must be greater than 0,
- `staffing.effort_percentile`, when set, must be between 1 and 99,
- `staffing.min_individual_productivity` must be greater than 0 and at most 1,
- `experience_profiles[*].productivity_factor` must be greater than 0,
- `experience_profiles[*].communication_overhead` must be between 0 and 1.

### Recommended authoring style for configuration files

- override only the values you need,
- keep symbolic estimate mappings consistent with your team's estimation conventions,
- set `random_seed` only when you want reproducible runs,
- use `effort_percentile` when staffing recommendations should be conservative,
- add custom experience profiles only when they correspond to real planning scenarios.

## Validation summary

The current implementation validates the following rules directly:

- file extension must be `.yaml`, `.yml`, or `.toml`,
- `project` must be present,
- `tasks` must be present,
- there must be at least one task,
- task IDs must be unique,
- all dependencies must point to existing tasks,
- task dependencies must not be circular,
- `start_date` must parse as an ISO date,
- probability thresholds must be in range and ordered correctly,
- triangular estimates must satisfy `low <= expected <= high`,
- log-normal estimates must include `low`, `expected`, and `high`, and must satisfy `low < expected < high`,
- risks must have probabilities in `0.0..1.0`,
- structured risk impacts must use positive values.

## Notes on undocumented keys

This reference documents the supported keys that are explicitly modeled by the current source code.

Keys outside these structures are not part of the formal project-file reference. In the current implementation, undeclared keys are not a reliable extension mechanism and should not be used to represent important semantics unless and until the source model explicitly supports them.

## Recommended authoring style

Although multiple forms are accepted, the clearest project files usually follow these practices:

- keep the `project` section concise and metadata-focused,
- use triangular estimates unless log-normal or T-shirt sizing is clearly justified,
- use task IDs that are stable and machine-friendly,
- keep dependency lists explicit,
- use only the recognized uncertainty-factor names,
- use structured risk impacts when you need `percentage` or explicit units,
- treat `resources` and `calendars` as advanced sections whose detailed internal schema may evolve.

If you want to see the reference syntax used in practice, compare this chapter with `examples/sample_project.yaml`, `examples/tshirt_walkthrough_project.yaml`, `examples/story_points_walkthrough_project.yaml`, and `examples/project_with_custom_thresholds.yaml`.

\newpage
