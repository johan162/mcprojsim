# Project files

This chapter is a reference for the project definition file format used by `mcprojsim`.

The parser layer is intentionally simple:

- `.yaml` and `.yml` files are loaded with the YAML parser,
- `.toml` files are loaded with the TOML parser,
- both are then validated against the same `Project` model.

Because of that design, the logical schema is the same regardless of whether you write the file in YAML or TOML.

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
- `resources` — optional. **Note:** Does not impact the simulation at the moment.
- `calendars` — optional, **Note:** Does not impact the simulation at the moment.

The smallest valid project file therefore looks like this:

```yaml
project:
  name: "My Project"
  start_date: "2026-03-01"

tasks:
  - id: "task_001"
    name: "First task"
    estimate:
      min: 1
      most_likely: 2
      max: 3
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

That is also the order used in most examples and in this reference.

## The `project` section

The `project` section is required. It contains project-level metadata and reporting settings.

### Supported fields

| Field | Required | Type | Default | Notes |
|---|---|---|---|---|
| `name` | Yes | string | — | Project display name |
| `description` | No | string | `null` | Optional descriptive text |
| `start_date` | Yes | ISO date string | — | Must parse as `YYYY-MM-DD` |
| `currency` | No | string | `"USD"` | Stored as metadata |
| `confidence_levels` | No | list of integers | `[25, 50, 75, 80, 85, 90, 95, 99]` | Controls reported percentiles |
| `probability_red_threshold` | No | float | `0.50` | Must be between `0.0` and `1.0` |
| `probability_green_threshold` | No | float | `0.90` | Must be between `0.0` and `1.0` |

### Required constraints

The implementation currently enforces these rules for `project`:

- `start_date` must be a valid ISO-format date string or a date object,
- `probability_red_threshold` must be less than `probability_green_threshold`,
- both thresholds must be in the range `0.0` to `1.0`.

### YAML example

```yaml
project:
  name: "Customer Portal Redesign"
  description: "Next-generation customer portal with enhanced features"
  start_date: "2025-11-01"
  currency: "USD"
  confidence_levels: [25, 50, 75, 80, 85, 90, 95, 99]
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
confidence_levels = [25, 50, 75, 80, 85, 90, 95, 99]
probability_red_threshold = 0.50
probability_green_threshold = 0.90
```

## The `tasks` section

The `tasks` section is required and must contain at least one task.

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
| `risks` | No | list of risk objects | `[]` | Task-level probabilistic risks |

### Minimal task example

```yaml
tasks:
  - id: "task_001"
    name: "Design database schema"
    estimate:
      min: 3
      most_likely: 5
      max: 8
```

### TOML task example

```toml
[[tasks]]
id = "task_001"
name = "Design database schema"

[tasks.estimate]
min = 3
most_likely = 5
max = 8
```

## The `estimate` section

Every task must define an `estimate` object.

The implementation supports four estimate styles:

1. triangular estimate,
2. log-normal estimate,
3. T-shirt-size estimate,
4. Story Point estimate.

The `distribution` field defaults to `triangular` when omitted.

### 1. Triangular estimate

This is the default and most common form.

#### Supported fields

| Field | Required | Type | Default |
|---|---|---|---|
| `distribution` | No | `"triangular"` or `"lognormal"` | `"triangular"` |
| `min` | Yes for triangular | number ≥ 0 | `null` |
| `most_likely` | Yes | number > 0 | `null` |
| `max` | Yes for triangular | number ≥ 0 | `null` |
| `unit` | No | string | `"days"` |

#### Validation rules

For a triangular estimate:

- `most_likely` must be present,
- `min` must be present,
- `max` must be present,
- `min <= most_likely <= max`.

#### YAML example

```yaml
estimate:
  min: 3
  most_likely: 5
  max: 10
  unit: "days"
```

#### TOML example

```toml
[tasks.estimate]
min = 3
most_likely = 5
max = 10
unit = "days"
```

### 2. Log-normal estimate

The implementation also supports log-normal estimates.

#### Supported fields

| Field | Required | Type | Notes |
|---|---|---|---|
| `distribution` | Yes | `"lognormal"` | Must be set explicitly |
| `most_likely` | Yes | number > 0 | Required |
| `standard_deviation` | Yes | number > 0 | Required |
| `unit` | No | string | Defaults to `"days"` |

#### Validation rules

For a log-normal estimate:

- `distribution` must be `lognormal`,
- `most_likely` must be present,
- `standard_deviation` must be present.

`min` and `max` are not required in this mode.

#### YAML example

```yaml
estimate:
  distribution: "lognormal"
  most_likely: 8
  standard_deviation: 2
  unit: "days"
```

#### TOML example

```toml
[tasks.estimate]
distribution = "lognormal"
most_likely = 8
standard_deviation = 2
unit = "days"
```

### 3. T-shirt-size estimate

This form lets the task refer to a symbolic size such as `XS`, `M`, or `XL`.

#### Supported fields

| Field | Required | Type | Default |
|---|---|---|---|
| `t_shirt_size` | Yes | string | — |
| `unit` | No | string | `"days"` |
| `distribution` | No | enum | Defaults to `triangular` |

#### Validation behavior

When `t_shirt_size` is present:

- the `TaskEstimate` validator accepts the estimate immediately,
- explicit `min`, `most_likely`, `max`, and `standard_deviation` are not required,
- the simulation engine resolves the size to actual `min`, `most_likely`, and `max` values from the active configuration.

If the chosen size does not exist in the active configuration, simulation raises an error.

#### YAML example

```yaml
estimate:
  t_shirt_size: "M"
  unit: "days"
```

#### TOML example

```toml
[tasks.estimate]
t_shirt_size = "M"
unit = "days"
```

#### Important precedence note

As implemented today, if `t_shirt_size` is present together with explicit numeric estimate fields, the T-shirt-size path takes precedence during validation and resolution.

In other words, this is technically accepted by the model:

```yaml
estimate:
  t_shirt_size: "M"
  min: 1
  most_likely: 2
  max: 3
```

But it should be treated as ambiguous and avoided in real project files. If you use `t_shirt_size`, prefer to omit the explicit numeric range fields.

### 4. Story Point estimate

This form lets a task use agile-style relative sizing while still simulating an effort range in days.

#### Supported fields

| Field | Required | Type | Default |
|---|---|---|---|
| `story_points` | Yes | integer | — |
| `unit` | No | string | `"storypoint"` |
| `distribution` | No | enum | Defaults to `triangular` |

#### Validation behavior

When `story_points` is present:

- the value must currently be one of `1`, `2`, `3`, `5`, `8`, `13`, or `21`,
- `unit` defaults to `"storypoint"` if omitted,
- the simulation engine resolves the Story Point value to actual `min`, `most_likely`, and `max` values in days from the active configuration.

If the chosen Story Point value does not exist in the active configuration, simulation raises an error.

#### YAML example

```yaml
estimate:
  story_points: 5
  unit: "storypoint"
```

#### TOML example

```toml
[tasks.estimate]
story_points = 5
unit = "storypoint"
```

### Symbolic estimate mappings in configuration

Both `t_shirt_size` and `story_points` are symbolic estimate forms. They are converted to day-based ranges by the active configuration.

Built-in defaults exist for both styles, and a custom configuration file may override all or only some of those mappings.

#### Example configuration

```yaml
t_shirt_sizes:
  M:
    min: 4
    most_likely: 6
    max: 9

story_points:
  5:
    min: 4
    most_likely: 6
    max: 9
  8:
    min: 6
    most_likely: 9
    max: 16
```

If a custom configuration overrides only some T-shirt sizes or Story Point values, the remaining built-in defaults stay available.

## The `dependencies` field

`dependencies` is a list of task IDs that must complete before the current task can start.

### Supported syntax

```yaml
dependencies: []
```

```yaml
dependencies: ["task_001"]
```

```yaml
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
      min: 2
      most_likely: 4
      max: 6

  - id: "task_002"
    name: "API implementation"
    estimate:
      min: 5
      most_likely: 8
      max: 12
    dependencies: ["task_001"]
```

## The `uncertainty_factors` field

At task level, `uncertainty_factors` is modeled as a structured object with a fixed set of recognized fields.

### Recognized fields

| Field | Default |
|---|---|
| `team_experience` | `"medium"` |
| `requirements_maturity` | `"medium"` |
| `technical_complexity` | `"medium"` |
| `team_distribution` | `"colocated"` |
| `integration_complexity` | `"medium"` |

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

## The `resources` field inside a task

Each task may list resource names as strings:

```yaml
resources: ["backend_dev", "database_admin"]
```

Task-level `resources` is typed as a list of strings in the current model.

## The `risks` field inside a task

Each task may have zero or more task-level risks.

### Task-level risk object fields

| Field | Required | Type | Notes |
|---|---|---|---|
| `id` | Yes | string | Risk identifier |
| `name` | Yes | string | Display name |
| `probability` | Yes | float | Must be between `0.0` and `1.0` |
| `impact` | Yes | number or object | See below |
| `description` | No | string | Optional |

### Risk impact syntax

The `impact` field supports two forms.

#### 1. Simple numeric impact

This is interpreted as an absolute time penalty.

```yaml
risks:
  - id: "risk_001"
    name: "Integration issues"
    probability: 0.25
    impact: 3
```

#### 2. Structured impact object

This may be either `absolute` or `percentage`.

```yaml
risks:
  - id: "risk_001"
    name: "Architecture rework"
    probability: 0.20
    impact:
      type: "absolute"
      value: 5
      unit: "days"
```

```yaml
risks:
  - id: "risk_002"
    name: "Approval delay"
    probability: 0.10
    impact:
      type: "percentage"
      value: 15
```

### Validation rules for risks

The model enforces:

- `probability` must be between `0.0` and `1.0`,
- `impact.value` must be greater than `0` when object syntax is used,
- numeric impacts are converted to floats,
- structured impacts must use `type: "absolute"` or `type: "percentage"`.

## The `project_risks` section

`project_risks` has exactly the same syntax as task-level `risks`, but it appears at top level and applies to the project as a whole.

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

## The top-level `resources` section

The top-level project model accepts a `resources` section.

### Current implementation shape

At parse time, `resources` is typed as:

```text
list[dict[str, Any]]
```

That means each resource entry must be a mapping-like object, but the current project model does not impose a stricter nested schema inside each entry.

### Example shape accepted by the current model

```yaml
resources:
  - id: "backend_dev"
    name: "Backend Developer"
    availability: 1.0
  - id: "qa_engineer"
    name: "QA Engineer"
    availability: 0.5
```

### Important note

The parser accepts this section, but the current source code does not define a strongly validated internal resource schema at the project-model level.

## The top-level `calendars` section

The top-level project model also accepts a `calendars` section.

### Current implementation shape

At parse time, `calendars` is typed as:

```text
list[dict[str, Any]]
```

As with top-level `resources`, the current project model does not define a stricter nested schema for calendar entries.

### Example shape accepted by the current model

```yaml
calendars:
  - id: "standard"
    working_days: ["monday", "tuesday", "wednesday", "thursday", "friday"]
    holidays:
      - "2026-12-25"
      - "2026-12-26"
```

### Important note

This section is accepted structurally by the project parser, but the current project model does not validate its internal keys beyond “list of objects”.

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
      min: 2
      most_likely: 4
      max: 7
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

  - id: "task_002"
    name: "Implementation"
    estimate:
      distribution: "lognormal"
      most_likely: 8
      standard_deviation: 2
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
      unit: "days"
    dependencies: ["task_002"]

resources:
  - id: "designer"
    name: "Product Designer"
  - id: "backend_dev"
    name: "Backend Developer"
  - id: "frontend_dev"
    name: "Frontend Developer"

calendars:
  - id: "standard"
    working_days: ["monday", "tuesday", "wednesday", "thursday", "friday"]
    holidays:
      - "2026-12-25"
```

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
most_likely = 4
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
most_likely = 8
standard_deviation = 2
unit = "days"

[tasks.uncertainty_factors]
team_experience = "medium"
technical_complexity = "high"
team_distribution = "distributed"

[[tasks]]
id = "task_003"
name = "Deployment"
dependencies = ["task_002"]

[tasks.estimate]
t_shirt_size = "S"
unit = "days"

[[resources]]
id = "designer"
name = "Product Designer"

[[resources]]
id = "backend_dev"
name = "Backend Developer"

[[resources]]
id = "frontend_dev"
name = "Frontend Developer"

[[calendars]]
id = "standard"
working_days = ["monday", "tuesday", "wednesday", "thursday", "friday"]
holidays = ["2026-12-25"]
```

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
- triangular estimates must satisfy `min <= most_likely <= max`,
- log-normal estimates must include `most_likely` and `standard_deviation`,
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

If you want to see the reference syntax used in practice, compare this chapter with [examples/sample_project.yaml](examples/sample_project.yaml), [examples/tshirt_walkthrough_project.yaml](examples/tshirt_walkthrough_project.yaml), [examples/story_points_walkthrough_project.yaml](examples/story_points_walkthrough_project.yaml), and [examples/project_with_custom_thresholds.yaml](examples/project_with_custom_thresholds.yaml).
