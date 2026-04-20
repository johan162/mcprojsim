# Task Estimation

This chapter explains how individual tasks are estimated in `mcprojsim` and how those estimates drive the Monte Carlo simulation. Every task in a project file needs an effort estimate. That estimate is not a single fixed number — it is a structured description of plausible effort that the simulator samples from in each iteration.

The goal of this chapter is to explain all supported estimation methods, the probability distributions behind them, and how to specify each one in a project file.



## How estimation works in the simulation

In each Monte Carlo iteration, the simulator processes every task as follows:

1. **Read the estimate** from the task definition.
2. **Resolve symbolic estimates** (T-shirt sizes or story points) into numeric ranges using the configuration file.
3. **Sample a base duration** from the specified probability distribution.
4. **Apply uncertainty factors** (multiplicative adjustment).
5. **Evaluate task-level risks** (additive impact if triggered).

The result is the task's effective duration for that iteration. Over thousands of iterations, the sampled values form a distribution that captures the inherent uncertainty in the estimate.

This chapter focuses on steps 1 through 3. Uncertainty factors and risks are covered in [Uncertainty Factors](04_uncertainty_factors.md) and [Risks](06_risks.md).



## Estimation methods at a glance

`mcprojsim` supports four ways to express task effort. Each method provides the same information to the simulator — a probability distribution to sample from — but is suited to different estimation contexts.

| Method | Input | Resolved to | Best for |
|--------|-------|-------------|----------|
| **Explicit range (triangular)** | `low`, `expected`, `high` | Used directly | Teams comfortable giving numeric estimates with bounded outcomes |
| **Explicit range (log-normal)** | `low`, `expected`, `high`, `distribution: "lognormal"` | Used directly | Tasks with significant right-tail risk or open-ended uncertainty |
| **T-shirt size** | `t_shirt_size` (e.g., `"M"` or `"epic.M"`) | Looked up in config → `low`, `expected`, `high` | Early-stage or relative estimation |
| **Story points** | `story_points` (e.g., `5`) | Looked up in config → `low`, `expected`, `high` | Teams using story point estimation practices |

All four methods ultimately feed into the same simulation machinery. T-shirt sizes and story points are convenience mappings that resolve to explicit ranges before sampling begins.

## Explicit range estimates

The most direct way to estimate a task is to provide three values that describe the range of plausible effort:

| Parameter     | Meaning                                          | Required |
|---------------|--------------------------------------------------|----------|
| `low`         | The shortest plausible duration (optimistic)      | Yes      |
| `expected` | The expected duration under normal conditions     | Yes      |
| `high`         | The longest plausible duration (pessimistic)       | Yes      |
| `unit`        | The time unit: `"hours"`, `"days"`, or `"weeks"` (default: `"hours"`) | No       |

The three values must satisfy: `low` ≤ `expected` ≤ `high`.

### Basic example

```yaml
tasks:
  - id: "task_001"
    name: "Database schema design"
    estimate:
      low: 3
      expected: 5
      high: 10
      unit: "days"
```

This tells the simulator: in the best case, the task takes about 3 days; most likely it takes about 5 days; in a difficult scenario, it could take up to 10 days. Because `unit: "days"` is specified, the simulator converts these values to hours internally (using the project's `hours_per_day` setting, which defaults to 8). The simulator then samples from this range in every iteration, producing a distribution of task durations across the full simulation.

### Choosing good range values

The three values are not arbitrary guesses. They carry specific meaning:

- **`low`** is not the theoretical fastest time if everything goes perfectly. It is the shortest duration that is still realistic given the scope of work. Ask: "If things go smoothly, how fast could this realistically be done?"

- **`expected`** is the duration you would expect under normal conditions. It represents the mode — the single most probable outcome. Ask: "If I had to pick one number for this task, what would it be?"

- **`high`** is not a catastrophic worst case. It is the longest duration that is credibly possible if several things go wrong, but without extraordinary events like losing the entire team. Ask: "If this task hits significant headwinds, how long could it take?"

The spread between `low` and `high` reflects how uncertain you are. A narrow range (e.g., 4 / 5 / 6) means high confidence. A wide range (e.g., 3 / 5 / 15) means substantial uncertainty, and the simulation results will reflect that.

### Asymmetric ranges

In practice, most software tasks have more upside risk than downside opportunity. It is common for the distance between `expected` and `high` to be larger than the distance between `low` and `expected`. This naturally produces a right-skewed distribution — reflecting the reality that tasks are more likely to run over than to finish early by the same margin.

```yaml
estimate:
  low: 3
  expected: 5
  high: 15
  unit: "days"
```

Here, the best-case savings is 2 days (5 minus 3), but the worst-case overrun is 10 days (15 minus 5). This kind of asymmetry is realistic and the triangular distribution handles it naturally.

## Near-deterministic estimates

Sometimes a task has very little uncertainty — for example, a well-understood routine task with a known duration. You might be tempted to set `low`, `expected`, and `high` to the same value.

However, the triangular distribution requires `low` < `high`. Setting all three values equal will produce a validation error at sampling time. To model a near-deterministic task, use a very narrow range:

```yaml
estimate:
  low: 4.9
  expected: 5
  high: 5.1
  unit: "days"
```

This effectively produces a duration of approximately 5 days in every iteration, with negligible variation. The sampled values will be very close to 5.0 but not exactly identical, which is usually close enough for practical purposes.



## Probability distributions

The estimate range defines the inputs. The probability distribution defines how values are sampled from that range. `mcprojsim` supports two distributions.

### Triangular distribution (default)

The triangular distribution is the default and most commonly used distribution in project estimation. It is defined by three parameters — minimum, mode, and maximum — which correspond directly to the `low`, `expected`, and `high` fields in the estimate.

**Properties:**

| Property | Description |
|----------|-------------|
| Shape | Triangle-shaped probability density |
| Parameters | `low`, `expected` (mode), `high` |
| Support | Values between `low` and `high` only |
| Skewness | Determined by position of `expected` within the range |
| Implementation | `numpy.random.triangular` |

**When to use it:**

- When the team can provide three-point estimates (optimistic, likely, pessimistic)
- When you want a bounded distribution — no sampled value can fall outside the stated range
- When you want an intuitive model that is easy to explain to stakeholders
- For most software estimation tasks — this is the recommended default

**Characteristics:**

The triangular distribution concentrates probability around the `expected` value and tapers linearly toward the extremes. It guarantees that no sample will be less than `low` or greater than `high`, which can be reassuring when the team has confidence in the boundaries.

If `expected` is centered between `low` and `high`, the distribution is symmetric. If `expected` is closer to `low` (common in software estimation), the distribution is right-skewed — producing a longer tail toward the high end.

**Specification:**

The triangular distribution is the default, so you do not need to specify it explicitly. Both of the following are equivalent:

```yaml
# Implicit (triangular is the default)
estimate:
  low: 3
  expected: 5
  high: 10
  unit: "days"

# Explicit
estimate:
  distribution: "triangular"
  low: 3
  expected: 5
  high: 10
  unit: "days"
```

### Distribution precedence

The distribution used for a task is resolved in this order, from highest to lowest priority:

1. **Per-task `distribution` field** — set directly on a task's `estimate` block. Always takes precedence.
2. **Project-level `distribution` field** — set under `project:` in the project file. Acts as the default for all tasks in that project.
3. **Built-in default** — `triangular` when nothing else is specified.

This means you can set `distribution: lognormal` once at the project level and get log-normal sampling for every task without touching each individual task, while still overriding specific tasks back to `triangular` (or another distribution) where needed.

There is currently no global `--distribution` CLI override for `simulate`.

**Example — project-wide lognormal with one triangular override:**

```yaml
project:
  name: "Research Project"
  start_date: "2026-04-01"
  distribution: "lognormal"          # all tasks default to lognormal

tasks:
  - id: "task_001"
    name: "Write specification"
    estimate:                         # inherits lognormal from project
      low: 1
      expected: 3
      high: 8
      unit: "days"

  - id: "task_002"
    name: "Set up CI pipeline"
    estimate:
      distribution: "triangular"     # overrides project default for this task only
      low: 0.5
      expected: 1
      high: 2
      unit: "days"
```

### Log-normal distribution

The log-normal distribution is an alternative that produces a right-skewed,
unbounded distribution. It is useful for tasks where the upside risk (overrun)
is potentially much larger than the downside opportunity (early finish).

`mcprojsim` implements this as a **shifted log-normal** so end users can keep
working with the same `low`, `expected`, and `high` fields they already use for
triangular estimates.

**Properties:**

| Property | Description |
|----------|-------------|
| Shape | Right-skewed, long tail toward high values |
| Parameters | `low`, `expected`, `high`, plus configured percentile for `high` |
| Support | All values greater than `low` |
| Skewness | Always right-skewed; heavier tail with larger fitted sigma |
| Implementation | `numpy.random.lognormal` |

Internally the simulator defines a shifted variable:

$$Y = X - \text{low}$$

where $X$ is the actual duration and $Y$ follows a standard log-normal
distribution.

The inputs are interpreted as:

- `low`: hard minimum / shift
- `expected`: mode of $X$
- `high`: configured percentile of $X$ (P95 by default)

This gives:

$$e^{\mu - \sigma^2} = \text{expected} - \text{low}$$

and

$$e^{\mu + z_p\sigma} = \text{high} - \text{low}$$

where $z_p$ is the z-score for the configured percentile. For the default P95,
$z_p \approx 1.645$.

Subtracting the two equations yields:

$$\sigma^2 + z_p\sigma = \ln(\text{high} - \text{low}) - \ln(\text{expected} - \text{low})$$

The simulator solves that quadratic for the positive $\sigma$, then computes:

$$\mu = \ln(\text{expected} - \text{low}) + \sigma^2$$

**When to use it:**

- For tasks with significant right-tail risk — where overruns could be much larger than expected
- When you are uncertain about the upper bound — the log-normal has no maximum, which may better represent truly open-ended tasks
- For research-oriented work, prototyping, or integration tasks with high unknowns
- When historical data suggests log-normal effort patterns (this is supported by research in some software estimation contexts)

**When not to use it:**

- When you have clear, defensible bounds on the task duration — in that case, a triangular distribution is more appropriate
- When stakeholders need guarantees that the sampled value will not exceed a certain threshold - the log-normal can produce extreme outliers
- When the team is not comfortable with unbounded estimates

**Specification:**

```yaml
estimate:
  distribution: "lognormal"
  low: 2
  expected: 5
  high: 14
  unit: "days"
```

Here, 2 days is the minimum, 5 days is the most likely outcome, and 14 days is
interpreted as the configured high percentile (P95 by default). Wider gaps
between `expected` and `high` produce a heavier right tail.

### Configuring the log-normal high percentile

The `high` value for log-normal estimates is interpreted using the configuration setting `lognormal.high_percentile`.

```yaml
lognormal:
  high_percentile: 95
```

Allowed values are: `70`, `75`, `80`, `85`, `90`, `95`, `99`.

- Lower values (for example `80`) treat `high` as a less extreme percentile and produce a lighter right tail.
- Higher values (for example `99`) treat `high` as a more extreme percentile and produce a heavier right tail.

**Example: a research task with high uncertainty**

```yaml
tasks:
  - id: "prototype"
    name: "Prototype ML model"
    estimate:
      distribution: "lognormal"
      low: 4
      expected: 10
      high: 30
      unit: "days"
    dependencies: []
```

Here, the most likely duration is 10 days, but the long right tail means that in some iterations the sampled value could be 20 or 30 days — reflecting the genuine uncertainty in exploratory work.


::: pagebreak-b5  
:::

### Comparing the two distributions

| Aspect | Triangular | Log-normal |
|--------|-----------|------------|
| Bounded | Yes — samples always within [min, max] | No — no upper bound |
| Parameters | `low`, `expected`, `high` | `low`, `expected`, `high` + configured high percentile |
| Skewness | Depends on parameter placement | Always right-skewed |
| Intuition | Easy to explain to non-technical stakeholders | Requires more statistical background |
| Extreme values | Impossible beyond stated bounds | Possible — long tail |
| Recommended for | Most estimation tasks | Tasks with open-ended risk |

For most projects, the triangular distribution is the right choice. It is intuitive, bounded, and maps naturally to how teams think about estimates. The log-normal distribution is a specialized tool for tasks where the unbounded right tail better reflects reality.

### Why is log-normal a good model for software (or project) estimation?

Individual task durations are often observed to follow a log-normal distribution in empirical studies of projects and software projects in particular. 
This can be explained by noticing that task durations are influenced by many small, multiplicative factors — such as the complexity of the work, the efficiency of the team, the quality of requirements, and unforeseen issues that arise during execution. When you have a process that is influenced by many independent multiplicative factors, the resulting distribution of outcomes tends to be log-normal. This can be easily seen by observing that if an estimate can be written as 

$$X = X_0 \times F_1 \times F_2 \times ... \times F_n$$

where $X_0$ is the base estimate and $F_i$ are the multiplicative factors, then taking the logarithm gives:

$$\ln(X) = \ln(X_0) + \ln(F_1) + \ln(F_2) + ... + \ln(F_n)$$

If we assume the $\ln(F_i)$ are independent and identically distributed, then by the Central Limit Theorem, $\ln(X)$ will tend to be normally distributed, which means that $X$ is log-normally distributed.

\newpage


## T-shirt size estimates

T-shirt sizing is a relative estimation technique where tasks are classified into sizes such as `XS`, `S`, `M`, `L`, `XL`, and `XXL`, scoped by named categories (`bug`, `story`, `epic`, `business`, `initiative`). This is useful when teams need different calibration levels across planning horizons.

In `mcprojsim`, each T-shirt size is mapped to a numeric range (`low`, `expected`, `high`) inside a category in the configuration file. During simulation, a bare value like `M` resolves through `t_shirt_size_default_category` (default: `story`), while a qualified value like `epic.M` resolves directly.

### Default T-shirt size mappings

The default unit for T-shirt sizes is **hours** (configurable via `t_shirt_size_unit` in the configuration file).

The built-in default category is `story`, so a bare value like `M` resolves as `story.M` unless you change `t_shirt_size_default_category` or pass `--tshirt-category` on the CLI.

***Table: Bug - category***

| Category | Size | low (hours) | expected (hours) | high (hours) |
|---|---|---:|---:|---:|
| `bug` | `XS` | 0.5 | 1 | 4 |
| `bug` | `S` | 1 | 3 | 10 |
| `bug` | `M` | 3 | 8 | 24 |
| `bug` | `L` | 8 | 20 | 60 |
| `bug` | `XL` | 20 | 40 | 100 |
| `bug` | `XXL` | 40 | 80 | 200 |

***Table: Story - category***

| Category | Size | low (hours) | expected (hours) | high (hours) |
|---|---|---:|---:|---:|
| `story` | `XS` | 3 | 5 | 15 |
| `story` | `S` | 5 | 16 | 40 |
| `story` | `M` | 40 | 60 | 120 |
| `story` | `L` | 160 | 240 | 500 |
| `story` | `XL` | 320 | 400 | 750 |
| `story` | `XXL` | 400 | 500 | 1200 |

::: pagebreak-b5   
:::

***Table: Epic - category***

| Category | Size | low (hours) | expected (hours) | high (hours) |
|---|---|---:|---:|---:|
| `epic` | `XS` | 20 | 40 | 60 |
| `epic` | `S` | 60 | 120 | 170 |
| `epic` | `M` | 120 | 240 | 400 |
| `epic` | `L` | 290 | 480 | 700 |
| `epic` | `XL` | 600 | 1000 | 1500 |
| `epic` | `XXL` | 1200 | 2000 | 3200 |

***Table: Business/Program - category***

| Category | Size | low (hours) | expected (hours) | high (hours) |
|---|---|---:|---:|---:|
| `business` | `XS` | 400 | 800 | 2000 |
| `business` | `S` | 800 | 2000 | 5000 |
| `business` | `M` | 2000 | 4000 | 10000 |
| `business` | `L` | 4000 | 8000 | 20000 |
| `business` | `XL` | 8000 | 16000 | 40000 |
| `business` | `XXL` | 16000 | 32000 | 80000 |

***Table: Initiative - category***

| Category | Size | low (hours) | expected (hours) | high (hours) |
|---|---|---:|---:|---:|
| `initiative` | `XS` | 2000 | 4000 | 10000 |
| `initiative` | `S` | 4000 | 10000 | 25000 |
| `initiative` | `M` | 10000 | 20000 | 50000 |
| `initiative` | `L` | 20000 | 40000 | 100000 |
| `initiative` | `XL` | 40000 | 80000 | 200000 |
| `initiative` | `XXL` | 80000 | 160000 | 400000 |



These category-specific defaults let you keep the same symbolic size scale while tuning absolute magnitude for different planning scopes.

### Specifying a T-shirt size estimate

T-shirt size estimates must **not** include a `unit` field in the project file. The unit is determined by the configuration file's `t_shirt_size_unit` setting (default: `"hours"`).

```yaml
tasks:
  - id: "design_ui"
    name: "UI/UX Design"
    estimate:
      t_shirt_size: "M"
    dependencies: []
```

You can also use a qualified value:

```yaml
estimate:
  t_shirt_size: "epic.M"
```

Bare long-form aliases are accepted too, for example:

```yaml
estimate:
  t_shirt_size: "Medium"
```

With the built-in defaults, the bare `"M"` example above is equivalent to writing:

```yaml
estimate:
  low: 120
  expected: 240
  high: 400
  unit: "hours"
```

If you want story-scale values instead, either use a qualified value (`story.M`) or set `t_shirt_size_default_category: story` in your configuration.

The resolution happens automatically when the simulation runs. The resolved values are then converted to hours internally (if they are not already in hours) using the project's `hours_per_day` setting.

**Including `unit` on a T-shirt size estimate is a validation error:**

```yaml
# INVALID — will produce a validation error
estimate:
  t_shirt_size: "M"
  unit: "days"   # ERROR: T-shirt size estimates must not specify 'unit'
```

### Full example: project using T-shirt sizes

```yaml
project:
  name: "Tiny Landing Page"
  description: "T-shirt sizing example"
  start_date: "2026-03-01"
  confidence_levels: [50, 80, 90]
  hours_per_day: 8

tasks:
  - id: "task_001"
    name: "Design page"
    estimate:
      t_shirt_size: "S"
    dependencies: []
    uncertainty_factors:
      team_experience: "high"
      requirements_maturity: "high"

  - id: "task_002"
    name: "Build page"
    estimate:
      t_shirt_size: "M"
    dependencies: ["task_001"]
    uncertainty_factors:
      team_experience: "medium"
      technical_complexity: "medium"

  - id: "task_003"
    name: "Deploy page"
    estimate:
      t_shirt_size: "XS"
    dependencies: ["task_002"]
```

Note that no `unit` field appears on any task — the unit is taken from the configuration.

### Customizing T-shirt sizes in the configuration file

The default mappings can be overridden in the configuration file. This allows organizations to calibrate the sizes to match their own team velocity and task granularity. For example, a team that works in shorter cycles might define smaller ranges:

```yaml
# config.yaml
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
```

Any category/size values you define in the configuration file override those defaults while untouched categories and sizes remain available.

### Choosing the unit for T-shirt sizes

The numeric ranges in the T-shirt size mappings are interpreted in the unit specified by `t_shirt_size_unit` in the configuration file. The default is `"hours"`:

```yaml
# config.yaml — T-shirt sizes in hours (the default)
t_shirt_size_unit: "hours"

t_shirt_sizes:
  story:
    S:
      low: 1
      expected: 2
      high: 4       # 1-4 hours
    M:
      low: 3
      expected: 5
      high: 8       # 3-8 hours
    L:
      low: 5
      expected: 8
      high: 13      # 5-13 hours
```

If your team thinks about T-shirt sizes in terms of working days rather than hours, set `t_shirt_size_unit` to `"days"`. The simulator will then convert the ranges to hours using `hours_per_day`:

```yaml
# config.yaml — T-shirt sizes in days
t_shirt_size_unit: "days"

t_shirt_sizes:
  story:
    S:
      low: 0.5
      expected: 1
      high: 2       # 0.5-2 days -> 4-16 hours (at 8 hours/day)
    M:
      low: 1
      expected: 2
      high: 4       # 1-4 days -> 8-32 hours
    L:
      low: 2
      expected: 4
      high: 7       # 2-7 days -> 16-56 hours
```

The unit setting applies to **all** T-shirt sizes in the configuration. You cannot mix units across individual sizes — the `t_shirt_size_unit` value governs the entire mapping. The project file never specifies a unit for T-shirt size estimates; the unit is always determined by this configuration setting.



## Story point estimates

Story points are a common estimation unit in agile teams. In `mcprojsim`, story point values are mapped to day-based numeric ranges in the configuration file, similar to T-shirt sizes.

### Default story point mappings

The default unit for story points is **days** (configurable via `story_point_unit` in the configuration file).

| Story points | low (days) | expected (days) | high (days) |
|--------------|------------|-------------------|------------|
| 1            | 0.5        | 1                  | 3          |
| 2            | 1          | 2                  | 4          |
| 3            | 1.5        | 3                  | 5          |
| 5            | 3          | 5                  | 8          |
| 8            | 5          | 8                  | 15         |
| 13           | 8          | 13                 | 21         |
| 21           | 13         | 21                 | 34         |

The allowed values are: **1, 2, 3, 5, 8, 13, 21**. Other values are rejected during validation.

### Specifying a story point estimate

Story point estimates must **not** include a `unit` field in the project file. The unit is determined by the configuration file's `story_point_unit` setting (default: `"days"`).

```yaml
tasks:
  - id: "task_001"
    name: "Design page"
    estimate:
      story_points: 5
    dependencies: []
```

**Including `unit` on a story point estimate is a validation error:**

```yaml
# INVALID — will produce a validation error
estimate:
  story_points: 5
  unit: "days"   # ERROR: Story Point estimates must not specify 'unit'
```

### Full example: project using story points

```yaml
project:
  name: "Tiny Landing Page"
  description: "Story point estimation example"
  start_date: "2026-03-01"
  confidence_levels: [50, 80, 90]
  hours_per_day: 8

tasks:
  - id: "task_001"
    name: "Design page"
    estimate:
      story_points: 2
    dependencies: []
    uncertainty_factors:
      team_experience: "high"
      requirements_maturity: "high"
  - id: "task_002"
    name: "Build page"
    estimate:
      story_points: 5
    dependencies: ["task_001"]
    uncertainty_factors:
      team_experience: "medium"
      technical_complexity: "medium"
!!! yaml-cbreak-b5
  - id: "task_003"
    name: "Deploy page"
    estimate:
      story_points: 1
    dependencies: ["task_002"]
```

Note that no `unit` field appears on any task — the unit is taken from the configuration (`story_point_unit`, which defaults to `"days"`).

### Customizing story point mappings in the configuration file

Different teams have different velocity patterns. The configuration file lets you adjust the day-based ranges that each story point value maps to:

```yaml
# config.yaml
story_points:
  1:
    low: 0.5
    expected: 1
    high: 2.5
  2:
    low: 1
    expected: 2
    high: 3.5
  5:
    low: 3.5
    expected: 5.5
    high: 9
```

You only need to include the story point values you want to override. Any values not specified in your configuration will use the built-in defaults. Note that you can only use values from the allowed set (1, 2, 3, 5, 8, 13, 21) — the allowed values are defined in the code, not in configuration.

### Choosing the unit for story points

The numeric ranges in the story point mappings are interpreted in the unit specified by `story_point_unit` in the configuration file. The default is `"days"`:

```yaml
story_point_unit: "days"
story_points:
  1:
    low: 0.5
    expected: 1
    high: 3       # 0.5–3 days → 4–24 hours (at 8 hours/day)
  5:
    low: 3
    expected: 5
    high: 8       # 3–8 days → 24–64 hours
```

If your team calibrates story points directly in hours, set `story_point_unit` to `"hours"`:

```yaml
story_point_unit: "hours"
story_points:
  1:
    low: 1
    expected: 3
    high: 6       # 1–6 hours
  5:
    low: 8
    expected: 16
    high: 32      # 8–32 hours
```

As with T-shirt sizes, the unit setting applies to **all** story point mappings in the configuration. The project file never specifies a unit for story point estimates — the unit is always determined by `story_point_unit`.

> **Note:** The `t_shirt_size_unit` and `story_point_unit` settings are independent. It is perfectly valid to have T-shirt sizes in hours and story points in days (the defaults), or any other combination.

## Mixing estimation methods

A single project can use different estimation methods for different tasks. This is useful when some tasks are well-understood enough for explicit day estimates while others are better expressed as relative sizes.

```yaml
tasks:
  - id: "research"
    name: "Technology research"
    estimate:
      distribution: "lognormal"
      low: 3
      expected: 8
      high: 20
      unit: "days"
    dependencies: []

  - id: "design"
    name: "Architecture design"
    estimate:
      t_shirt_size: "L"
    dependencies: ["research"]
 !!! text-cbreak-b5  
  - id: "implementation"
    name: "Core implementation"
    estimate:
      low: 10
      expected: 15
      high: 25
      unit: "days"
    dependencies: ["design"]

  - id: "testing"
    name: "Integration testing"
    estimate:
      story_points: 8
    dependencies: ["implementation"]
```

All four estimation methods are combined in one project. Each task's estimate is resolved and sampled independently using the same simulation pipeline. The simulator converts all values to hours internally using the appropriate unit for each estimate method.

Implementation detail: if a symbolic estimate (`t_shirt_size` or `story_points`) is present together with explicit numeric fields (`low` / `expected` / `high`), the symbolic estimate path is used and numeric fields are effectively ignored.

Recommended authoring style: avoid mixing symbolic and explicit fields on the same task. Use exactly one method per task to keep intent unambiguous.



## The `unit` field

The `unit` field specifies the time unit for numeric estimate values. The simulator uses this field to convert all values to **hours** internally, which is the canonical unit used throughout the simulation.

### Supported values

The `unit` field accepts exactly three values:

| Value     | Meaning              | Conversion to hours                              |
|-----------|----------------------|--------------------------------------------------|
| `"hours"` | Working hours        | Used as-is (1 hour = 1 hour)                     |
| `"days"`  | Working days         | Multiplied by `hours_per_day` (default 8)        |
| `"weeks"` | Working weeks        | Multiplied by `hours_per_day × 5` (default 40)   |

Any other value is a validation error.

::: pagebreak-b5  
:::

### Defaults by estimate type

| Estimate type  | Default unit | `unit` field allowed? |
|----------------|--------------|----------------------|
| Explicit range | `"hours"`    | Yes — `"hours"`, `"days"`, or `"weeks"` |
| T-shirt size   | *(from config)* | **No** — specifying `unit` is a validation error |
| Story points   | *(from config)* | **No** — specifying `unit` is a validation error |

For explicit range estimates, the default unit is `"hours"`. If you omit the `unit` field, your numeric values are interpreted as hours.

For T-shirt sizes and story points, the unit is controlled by the configuration file (`t_shirt_size_unit` and `story_point_unit` respectively). The project file must not include a `unit` field for these estimate types.

### The `hours_per_day` setting

The project metadata supports an `hours_per_day` field (default: `8.0`) that controls how days and weeks are converted to hours:

```yaml
project:
  name: "My Project"
  start_date: "2026-03-01"
  hours_per_day: 6    # 6-hour productive work days
```

This setting affects:

- conversion of `unit: "days"` values (multiplied by `hours_per_day`)
- conversion of `unit: "weeks"` values (multiplied by `hours_per_day × 5`)
- conversion of simulation results from hours back to working days for reporting

### Unit conversion is automatic

The simulator automatically converts all estimate values to hours before simulation begins. This means you can safely mix units across tasks in the same project:

```yaml
tasks:
  - id: "quick_fix"
    estimate:
      low: 2
      expected: 4
      high: 8
      unit: "hours"    # Small task estimated in hours
 !!! text-cbreak-b5 
  - id: "major_feature"
    estimate:
      low: 2
      expected: 4
      high: 8
      unit: "days"     # Large task estimated in days
```

The simulator converts the second task's values to hours (2×8=16, 4×8=32, 8×8=64) before sampling. The two tasks are compared on a common scale.

### Simulation output

All simulation results are reported in hours. The CLI and export formats also show working days (computed as `ceil(hours / hours_per_day)`) and projected delivery dates (skipping weekends, based on `start_date`).

### Unit field for T-shirt sizes and story points

When a T-shirt size or story point estimate is resolved during simulation, the numeric values come from the configuration file. The unit for those values is also defined in the configuration:

- `t_shirt_size_unit`: defaults to `"hours"`
- `story_point_unit`: defaults to `"days"`

The resolved values are then converted to hours using the same conversion logic. This means a story point estimate of `5` with default configuration resolves to `min=3, expected=5, max=8` in days, which the simulator converts to `min=24, expected=40, max=64` in hours.



## Validation rules

`mcprojsim` validates every task estimate before the simulation runs. Understanding the validation rules helps avoid errors:

| Rule | Applies to | Error if violated |
|------|-----------|-------------------|
| `low` ≤ `expected` ≤ `high` | Triangular distribution | Yes — values must be in order |
| `low` < `high` | Triangular distribution | Yes — NumPy requires strict inequality |
| `expected` > 0 | All explicit estimates | Yes — zero or negative not allowed |
| `low` ≥ 0 | All explicit estimates | Yes — negative values not allowed |
| `low` < `expected` < `high` | Log-normal distribution | Yes — shifted fit requires a strict range |
| `low`, `expected`, `high` all provided | Log-normal distribution | Yes — all three required |
| `low`, `expected`, `high` all provided | Triangular distribution | Yes — all three required |
| Only one symbolic type | T-shirt / story point | Yes — cannot use both on one task |
| At least one estimate mode provided (`expected` or symbolic) | All tasks | Yes — estimate cannot be empty |
| Story point value in allowed set | Story points | Yes — must be 1, 2, 3, 5, 8, 13, or 21 |
| `unit` must be `"hours"`, `"days"`, or `"weeks"` | Explicit estimates | Yes — free-form strings not accepted |
| No `unit` on symbolic estimates | T-shirt / story point | Yes — unit comes from config |
| `t_shirt_size` token shape must be `<size>` or `<category>.<size>` | T-shirt size | Yes — invalid token formats fail validation |
| `t_shirt_size` category and size must exist in active config | T-shirt size | Yes — unknown category/size fails resolution |


::: pagebreak-b5 
:::

## Summary

| Estimation method | Required fields | Distribution | Good for |
|-------------------|----------------|--------------|----------|
| Explicit range (triangular) | `low`, `expected`, `high` | Triangular (bounded) | Well-understood tasks with clear bounds |
| Explicit range (log-normal) | `low`, `expected`, `high`, `distribution: "lognormal"` | Shifted log-normal | Exploratory tasks with open-ended risk |
| T-shirt size | `t_shirt_size` | Inherits project/task distribution after config lookup | Relative estimation, early planning |
| Story points | `story_points` | Inherits project/task distribution after config lookup | Agile teams using story point practices |

All methods produce the same kind of output: a sampled duration for each iteration. The choice of method depends on what information the team is comfortable providing, not on any difference in simulation behavior.

\newpage

