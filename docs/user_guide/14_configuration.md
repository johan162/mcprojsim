# Configuration

This page documents the application configuration file used by `mcprojsim`.

The configuration file controls:

- uncertainty multipliers,
- symbolic estimate mappings such as T-shirt sizes and Story Points,
- default simulation settings,
- output and reporting defaults,
- staffing-analysis behavior.

## Configuration file format

The configuration file is currently loaded as **YAML**.

Typical usage:

```bash
mcprojsim simulate project.yaml --config config.yaml
```

You can also load it directly from Python:

```python
from mcprojsim import SimulationEngine
from mcprojsim.config import Config

config = Config.load_from_file("config.yaml")
engine = SimulationEngine(iterations=10000, config=config)
```

## How configuration loading works

When `mcprojsim` loads a configuration file, it does **not** replace the built-in defaults wholesale. Instead, it:

1. starts from the built-in default configuration,
2. reads your YAML file,
3. recursively merges your values into those defaults,
4. validates the merged result against the `Config` model.

This means you can override only the values you care about.

For example, if you define only `t_shirt_sizes.story.M`, the built-in mappings for the remaining sizes and categories remain available.

## Top-level configuration structure

The current configuration schema supports these top-level keys:

- `uncertainty_factors`
- `t_shirt_sizes`
- `t_shirt_size_default_category`
- `t_shirt_size_unit`
- `story_points`
- `story_point_unit`
- `simulation`
- `lognormal`
- `output`
- `staffing`
- `constrained_scheduling`
- `sprint_defaults`

## Full example

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

t_shirt_size_default_category: "story"

t_shirt_size_unit: "hours"
```

```yaml
story_points:
  1:
    low: 0.5
    expected: 1
    high: 3
  5:
    low: 3
    expected: 5
    high: 8
  8:
    low: 5
    expected: 8
    high: 15

story_point_unit: "days"

simulation:
  default_iterations: 10000
  random_seed: 42
  max_stored_critical_paths: 20

lognormal:
  high_percentile: 95

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
```

```yaml
constrained_scheduling:
  sickness_prob: 0.0
  assignment_mode: greedy_single_pass
  pass1_iterations: 1000

sprint_defaults:
  planning_confidence_level: 0.8
  removed_work_treatment: churn_only
  velocity_model: empirical
  volatility_disruption_probability: 0.0
  volatility_disruption_multiplier_low: 1.0
  volatility_disruption_multiplier_expected: 1.0
  volatility_disruption_multiplier_high: 1.0
  spillover_model: table
  spillover_size_reference_points: 5.0
  spillover_size_brackets:
    - max_points: 2.0
      probability: 0.05
    - max_points: 5.0
      probability: 0.12
    - max_points: 8.0
      probability: 0.25
    - max_points: null
      probability: 0.40
  spillover_consumed_fraction_alpha: 3.25
  spillover_consumed_fraction_beta: 1.75
  spillover_logistic_slope: 1.9
  spillover_logistic_intercept: -1.9924301646902063
  sickness:
    enabled: false
    probability_per_person_per_week: 0.058
    duration_log_mu: 0.693
    duration_log_sigma: 0.75
```

## Uncertainty factors

Uncertainty factors are multipliers applied to base task estimates. A value of `1.0` is the baseline. Values below `1.0` make work faster; values above `1.0` make work slower.

The built-in configuration defines these factor names:

- `team_experience`
- `requirements_maturity`
- `technical_complexity`
- `team_distribution`
- `integration_complexity`

### Defaults

#### Team experience

- **high (`0.90`)**: experienced team, about 10% faster than baseline
- **medium (`1.0`)**: baseline
- **low (`1.30`)**: inexperienced team, about 30% slower than baseline

#### Requirements maturity

- **high (`1.0`)**: stable, well-defined requirements
- **medium (`1.15`)**: moderate ambiguity
- **low (`1.40`)**: substantial ambiguity and likely change

#### Technical complexity

- **low (`1.0`)**: straightforward technology or architecture
- **medium (`1.20`)**: moderate complexity
- **high (`1.50`)**: difficult or novel technology

#### Team distribution

- **colocated (`1.0`)**: team in one place
- **distributed (`1.25`)**: coordination and communication slow delivery

#### Integration complexity

- **low (`1.0`)**: little external integration
- **medium (`1.15`)**: moderate integration effort
- **high (`1.35`)**: many integration points or fragile dependencies

### Notes

- The configuration model accepts nested dictionaries here.
- The current project-file model uses the built-in factor names listed above.
- Extra factor names in the configuration file are not useful unless the source model and simulation logic also reference them.

## Symbolic estimate mappings

`mcprojsim` supports two symbolic estimate systems:

- `t_shirt_size`
- `story_points`

Tasks using those symbolic forms are resolved through the active configuration.

If you override only part of either mapping table, the remaining built-in defaults stay available.

### T-shirt sizes

Tasks may use `t_shirt_size` instead of explicit `low` / `expected` / `high` values.

Canonical configuration shape:

```yaml
t_shirt_sizes:
  story:
    XS: {low: 3, expected: 5, high: 15}
    M: {low: 40, expected: 60, high: 120}
  bug:
    M: {low: 3, expected: 8, high: 24}
  epic:
    M: {low: 200, expected: 480, high: 1200}

t_shirt_size_default_category: story
```

Project-file values can be:

- bare size: `M` (resolved via `t_shirt_size_default_category`)
- qualified size: `epic.M`
- long-form aliases: `Medium`, `Epic.Large`

Built-in category keys:

- `bug`
- `story`
- `epic`
- `business`
- `initiative`

Built-in size keys (per category):

- `XS`
- `S`
- `M`
- `L`
- `XL`
- `XXL`

Built-in `story` defaults:

| Size | `low` | `expected` | `high` |
|---|---:|---:|---:|
| `XS` | 3 | 5 | 15 |
| `S` | 5 | 16 | 40 |
| `M` | 40 | 60 | 120 |
| `L` | 160 | 240 | 500 |
| `XL` | 320 | 400 | 750 |
| `XXL` | 400 | 500 | 1200 |

Canonical override example:

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

t_shirt_size_default_category: story
```

Backward compatibility:

- legacy flat maps under `t_shirt_sizes` are accepted and migrated to `t_shirt_sizes.<default_category>`
- transitional alias key `t_shirt_size_categories` is accepted as input
- defining both `t_shirt_sizes` and `t_shirt_size_categories` in one file is rejected

### `t_shirt_size_default_category`

This field controls how bare T-shirt size tokens are resolved when the project file uses values like `M` instead of qualified values like `story.M` or `epic.M`.

Default: `story`

That means:

- `t_shirt_size: M` resolves to `story.M` unless you override the default category,
- legacy flat `t_shirt_sizes` maps are migrated into `t_shirt_sizes.<default_category>` during config loading,
- changing this value changes both bare-token resolution and the target category used for legacy flat-map normalization.

Example:

```yaml
t_shirt_sizes:
  story:
    M: {low: 40, expected: 60, high: 120}
  epic:
    M: {low: 120, expected: 240, high: 400}

t_shirt_size_default_category: story
```

With that configuration, project-file `t_shirt_size: M` resolves to `story.M`.

## Shifted log-normal configuration

When an estimate uses `distribution: "lognormal"`, `mcprojsim` fits a **shifted**
log-normal from the already familiar `low`, `expected`, and `high` fields:

- `low` is treated as the hard shift/minimum,
- `expected` is treated as the mode,
- `high` is treated as a chosen percentile of the distribution.

That percentile is configured here:

```yaml
lognormal:
  high_percentile: 95
```

Allowed values are:

- `70`
- `75`
- `80`
- `85`
- `90`
- `95`
- `99`

The default is `95`, meaning the `high` value is interpreted as the P95 point of
the shifted log-normal distribution.

### `t_shirt_size_unit`

This field controls the unit used for all values in `t_shirt_sizes`.

Supported values:

- `"hours"`
- `"days"`
- `"weeks"`

Default: `"hours"`

Example:

```yaml
t_shirt_size_unit: "days"
```

### Story Points

Tasks may also use `story_points` for agile-style relative sizing.

Built-in point values:

- `1`
- `2`
- `3`
- `5`
- `8`
- `13`
- `21`

Built-in defaults:

| Points | `low` | `expected` | `high` |
|---|---:|---:|---:|
| `1` | 0.5 | 1 | 3 |
| `2` | 1 | 2 | 4 |
| `3` | 1.5 | 3 | 5 |
| `5` | 3 | 5 | 8 |
| `8` | 5 | 8 | 15 |
| `13` | 8 | 13 | 21 |
| `21` | 13 | 21 | 34 |

Example override:

```yaml
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

### `story_point_unit`

This field controls the unit used for all values in `story_points`.

Supported values:

- `"hours"`
- `"days"`
- `"weeks"`

Default: `"days"`

### Important note

Story Point and T-shirt-size estimates in the **project file** must **not** include their own `unit` field. The unit comes from the configuration via `story_point_unit` and `t_shirt_size_unit`.

See [Task Estimation](05_task_estimation.md#t-shirt-size-estimates) and [Task Estimation](05_task_estimation.md#story-point-estimates) for more guidance.

## Simulation settings

The `simulation` section controls default run behavior.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `default_iterations` | integer | `10000` | Default number of Monte Carlo iterations |
| `random_seed` | integer or `null` | `null` | Seed for reproducible runs |
| `max_stored_critical_paths` | integer | `20` | Number of full critical path sequences retained in memory |

Example:

```yaml
simulation:
  default_iterations: 20000
  random_seed: 42
  max_stored_critical_paths: 50
```

### Critical path reporting

The simulator can retain full critical path sequences, not just task-level criticality.

- `simulation.max_stored_critical_paths` controls how many of the most common full paths are retained in the results object.
- `output.critical_path_report_limit` controls how many of those stored paths are shown in CLI summaries and exports by default.

Example:

```yaml
simulation:
  default_iterations: 10000
  random_seed: null
  max_stored_critical_paths: 50

output:
  formats: ["json", "html"]
  include_histogram: true
  number_bins: 50
  critical_path_report_limit: 3
```

With that configuration, the simulation stores up to 50 unique full critical path sequences and shows the top 3 in the CLI, JSON, CSV, and HTML outputs.

You can still override the report count from the CLI:

```bash
mcprojsim simulate project.yaml --config config.yaml --critical-paths 5
```

That affects reporting only. Storage remains controlled by `simulation.max_stored_critical_paths`.

## Output settings

The `output` section controls reporting and export defaults.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `formats` | list of strings | `["json", "csv", "html"]` | Default export formats |
| `include_histogram` | boolean | `true` | Include histogram data where supported |
| `number_bins` | integer | `50` | Number of bins used for histograms in JSON, CSV, and HTML exports |
| `critical_path_report_limit` | integer | `2` | Number of stored full critical paths shown by default |

### Histogram bins

The `number_bins` setting controls the granularity of duration distribution charts in exported reports. Higher bin counts produce finer-grained histograms with narrower bars, while lower counts produce coarser histograms with wider bars.

- **Typical range**: 20–100 bins
- **Default**: 50 bins
- **CLI override**: Use `--number-bins N` to override the config file setting for a single run

The histogram data is included in:
- HTML reports (visual distribution chart)
- JSON exports (histogram array)
- CSV exports (histogram table)

**Configuration example:**

```yaml
output:
  formats: ["json", "html"]
  include_histogram: true
  number_bins: 80
  critical_path_report_limit: 5
```

**CLI override example:**

```bash
# Use 100 bins for this run, regardless of the config file
mcprojsim simulate project.yaml --number-bins 100 -f json,html
```

When `--number-bins` is specified on the command line, it overrides the value in the config file for that simulation run only.

## Staffing settings

The `staffing` section controls the staffing analysis shown in CLI output and exports.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `effort_percentile` | integer (optional) | omitted | Use a specific effort percentile such as P80 instead of the mean |
| `min_individual_productivity` | float | `0.25` | Lower bound on per-person productivity after communication overhead |
| `experience_profiles` | mapping | built-in defaults | Named team profiles used for staffing recommendations |

### `effort_percentile`

When `effort_percentile` is omitted, staffing uses mean total effort and mean elapsed time.

When it is set, staffing uses the matching percentile for both:

- total effort, and
- elapsed time / critical-path basis.

For example, `80` means the staffing recommendation is based on P80 effort and P80 elapsed time.

This is useful when you want conservative staffing guidance rather than a mean-based plan.

### `min_individual_productivity`

The staffing model assumes each additional person introduces communication overhead. Raw per-person productivity declines with team size and is then floored by `min_individual_productivity`.

Conceptually:

$$
P(n) = \max(P_{min}, 1 - c(n - 1))
$$

where:

- $n$ is team size,
- $c$ is the profile's `communication_overhead`,
- $P_{min}$ is `min_individual_productivity`.

This prevents the model from predicting unrealistically close-to-zero productivity for very large teams.

Lower values penalize oversized teams more aggressively. Higher values produce a softer diminishing-returns curve.

### `experience_profiles`

Each named profile contains:

| Field | Type | Meaning |
|---|---|---|
| `productivity_factor` | float | Base multiplier for that team's effectiveness |
| `communication_overhead` | float | Per-person overhead penalty as team size grows |

Built-in profiles:

| Profile | `productivity_factor` | `communication_overhead` |
|---|---:|---:|
| `senior` | 1.00 | 0.04 |
| `mixed` | 0.85 | 0.06 |
| `junior` | 0.65 | 0.08 |

Example:

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

## Sprint planning defaults

The `sprint_defaults` section provides company-wide defaults for sprint-planning simulations. These values are used when the project file does not set the corresponding `project.sprint_planning` field and no CLI flag overrides it.

Several of these settings change simulation behavior directly, not just reporting:

- `planning_confidence_level` changes which percentile the sprint plan targets,
- `velocity_model` changes how sprint capacity is sampled,
- `removed_work_treatment` changes whether removed work is modeled as churn only or as actual backlog reduction,
- `volatility_disruption_*` settings control whether disruption multipliers are sampled,
- `spillover_*` settings control how often work spills over and how much remains,
- `sprint_defaults.sickness.*` affects sprint sickness modeling and also constrained-scheduling sickness duration.

### Field reference

| Field | Type | Default | Allowed values | Effect |
|---|---|---|---|---|
| `planning_confidence_level` | float | `0.8` | `0 < value < 1` | Target confidence used when planning sprint outcomes |
| `removed_work_treatment` | string | `churn_only` | `churn_only`, `reduce_backlog` | Controls whether removed work is treated as churn only or also reduces backlog |
| `velocity_model` | string | `empirical` | `empirical`, `neg_binomial` | Controls how historical capacity is sampled |
| `volatility_disruption_probability` | float | `0.0` | `0 <= value <= 1` | Probability that disruption multipliers apply |
| `volatility_disruption_multiplier_low` | float | `1.0` | `value >= 0` | Low bound for sampled disruption multiplier |
| `volatility_disruption_multiplier_expected` | float | `1.0` | `value >= 0` | Expected disruption multiplier |
| `volatility_disruption_multiplier_high` | float | `1.0` | `value >= 0` | High bound for sampled disruption multiplier |
| `spillover_model` | string | `table` | `table`, `logistic` | Controls how spillover probability is modeled |
| `spillover_size_reference_points` | float | `5.0` | `value > 0` | Reference size used by spillover probability models |
| `spillover_size_brackets` | list | built-in table | bracket list | Size-to-probability table used when `spillover_model: table` |
| `spillover_consumed_fraction_alpha` | float | `3.25` | `value > 0` | Beta-shape parameter controlling typical consumed fraction |
| `spillover_consumed_fraction_beta` | float | `1.75` | `value > 0` | Beta-shape parameter controlling typical remaining spillover |
| `spillover_logistic_slope` | float | `1.9` | `value > 0` | Slope of the logistic spillover probability curve |
| `spillover_logistic_intercept` | float | `-1.9924301646902063` | any float | Intercept of the logistic spillover probability curve |
| `sickness.enabled` | boolean | `false` | `true`, `false` | Enables sprint sickness modeling |
| `sickness.probability_per_person_per_week` | float | `0.058` | `0 < value < 1` | Weekly sickness probability per team member |
| `sickness.duration_log_mu` | float | `0.693` | any float | Log-normal sickness duration location parameter |
| `sickness.duration_log_sigma` | float | `0.75` | `value > 0` | Log-normal sickness duration scale parameter |

### Notes on behavioral impact

- `velocity_model: empirical` re-samples directly from historical data; `neg_binomial` fits a negative binomial model to historical throughput.
- `removed_work_treatment: churn_only` treats removed work as diagnostic churn; `reduce_backlog` allows removed work to reduce remaining backlog.
- `spillover_model: table` uses the configured size brackets directly; `logistic` uses `spillover_logistic_slope`, `spillover_logistic_intercept`, and `spillover_size_reference_points`.
- The `volatility_disruption_multiplier_*` values define the sampled disruption range when `volatility_disruption_probability` is non-zero.

## Viewing current configuration

```bash
# Show effective configuration (built-in defaults, or auto-loaded user config)
mcprojsim config

# Show configuration from a specific file
mcprojsim config --config config.yaml

# Generate a default configuration file at ~/.mcprojsim/config.yaml
mcprojsim config --generate
```

When no `--config` is given, `mcprojsim` automatically loads
`~/.mcprojsim/config.yaml` if it exists. Use `--generate` to produce a
starter config file at that location that you can then customise.

The `config` output includes the most relevant effective settings, including:

- default iteration count,
- random seed,
- max stored critical paths,
- output histogram settings,
- critical path report limit,
- staffing settings,
- sprint defaults.

!!! note "Derived lognormal parameters in config output"
    For each T-shirt size and story point value, `mcprojsim config` also shows computed `lognormal params` (`mu`, `sigma`, `z-score`). These are derived from the configured `low`/`expected`/`high` values and are displayed for verification purposes only. They are not configurable fields — changing the underlying size values automatically recomputes them.

## Sprint planning precedence

Sprint-planning values are resolved in this order (highest to lowest priority):

1. CLI flags
2. Project `sprint_planning` fields
3. Global `sprint_defaults`
4. Built-in defaults

This lets you keep company-wide defaults in `sprint_defaults`, set project-specific behavior in the project file, and still override per run with CLI flags.

For sprint-planning field details and examples, see [Sprint planning](09_sprint_planning.md).

## Constrained scheduling defaults

The `constrained_scheduling` section controls defaults for resource-constrained scheduling runs.

These settings affect scheduling behavior directly:

- `sickness_prob` supplies the per-resource sickness fallback when the project file omits `resources[*].sickness_prob`,
- `assignment_mode` selects single-pass greedy scheduling or two-pass criticality-aware scheduling,
- `pass1_iterations` controls how much pass-1 sampling is used to rank tasks when two-pass scheduling is active.

### Field reference

| Field | Type | Default | Allowed values | Effect |
|---|---|---|---|---|
| `sickness_prob` | float | `0.0` | `0 <= value <= 1` | Fallback per-resource sickness probability |
| `assignment_mode` | string | `greedy_single_pass` | `greedy_single_pass`, `criticality_two_pass` | Selects constrained scheduling strategy |
| `pass1_iterations` | integer | `1000` | `value > 0` | Number of pass-1 iterations used to compute criticality ranking in two-pass mode |

### `sickness_prob`

`constrained_scheduling.sickness_prob` sets the default sickness probability for resources in constrained scheduling when a resource does not specify `sickness_prob` in the project file.

Precedence:

1. `resources[*].sickness_prob` in project file
2. `constrained_scheduling.sickness_prob` in config
3. built-in default `0.0`

Example:

```yaml
constrained_scheduling:
  sickness_prob: 0.03
```

If you omit this key, resources without `sickness_prob` still behave as `0.0`.

### `assignment_mode`

This field controls how tasks are prioritized when resource constraints are active.

- `greedy_single_pass`: the default. Tasks are dispatched in deterministic greedy order.
- `criticality_two_pass`: the simulator first runs a baseline pass to estimate task criticality, then re-runs the schedule using those criticality rankings as priority.

Two-pass mode affects the simulation itself, not just the output. The final results use pass-2 statistics, and the simulator includes a traceability block describing the delta between pass 1 and pass 2.

Example:

```yaml
constrained_scheduling:
  assignment_mode: criticality_two_pass
  pass1_iterations: 1500
```

### `pass1_iterations`

This field matters only when `assignment_mode: criticality_two_pass`.

- It controls how many iterations are used in pass 1 to estimate criticality indices.
- If it is larger than total simulation iterations, the simulator caps it to the total iteration count.
- Very low values can produce noisy criticality rankings.

As a practical rule, use enough pass-1 iterations to get stable rankings before relying on two-pass deltas for decision-making.

## Sickness duration defaults

The keys under `sprint_defaults.sickness` now serve two related purposes:

- sprint-planning sickness modeling,
- resource-constrained scheduler sickness duration modeling.

Specifically:

- `probability_per_person_per_week` is used by sprint planning,
- `enabled` turns sprint sickness simulation on or off,
- `duration_log_mu` and `duration_log_sigma` define the shared log-normal duration model for sickness episodes,
- per-resource `sickness_prob` still belongs in the project file because it is resource-specific.

Example:

```yaml
sprint_defaults:
  sickness:
    enabled: false
    probability_per_person_per_week: 0.058
    duration_log_mu: 0.693
    duration_log_sigma: 0.75
```

If you raise `duration_log_mu` or `duration_log_sigma`, constrained schedules with non-zero `resources[*].sickness_prob` will tend to experience longer sickness-driven absences.

## Sprint default logistic spillover parameters

The global keys `sprint_defaults.spillover_logistic_slope` and `sprint_defaults.spillover_logistic_intercept` control the logistic spillover probability curve used when project spillover model is `logistic`.

The planner computes probability in log-space from planning story points:

$$
z = \max\!\left(\frac{x}{r}, 10^{-6}\right),\quad
\ell = s \cdot \ln(z) + b,\quad
p = \frac{1}{1 + e^{-\ell}}
$$

where:

- $x$ = item planning story points
- $r$ = `spillover_size_reference_points`
- $s$ = `spillover_logistic_slope`
- $b$ = `spillover_logistic_intercept`

At the reference size ($x=r$), baseline probability is:

$$
p(x=r) = \frac{1}{1 + e^{-b}}
$$

For full spillover workflow details (including Beta-sampled consumed fraction and carryover construction), see [Sprint planning](09_sprint_planning.md#item-spillover).

`sprint_defaults.spillover_consumed_fraction_alpha` and `sprint_defaults.spillover_consumed_fraction_beta` are the Beta-distribution shape parameters for the consumed fraction during spillover events. Their expected consumed fraction is:

$$
\mathbb{E}[f] = \frac{\alpha}{\alpha + \beta}
$$

Increasing `alpha` raises typical consumed fraction; increasing `beta` lowers it.

## Validation rules

The configuration model validates these constraints directly:

- `t_shirt_size_unit` must be one of `hours`, `days`, or `weeks`,
- `story_point_unit` must be one of `hours`, `days`, or `weeks`,
- `t_shirt_sizes` accepts either a nested `<category>: <size>: {low, expected, high}` map or a legacy flat size map,
- if `t_shirt_size_categories` is used as a transitional alias, it cannot appear together with `t_shirt_sizes`,
- T-shirt size tokens in config must normalize to one of `XS`, `S`, `M`, `L`, `XL`, or `XXL`,
- all configured estimate ranges require positive `low`, `expected`, and `high`,
- `lognormal.high_percentile` must be one of `70`, `75`, `80`, `85`, `90`, `95`, or `99`,
- `simulation.default_iterations` must be greater than 0,
- `simulation.max_stored_critical_paths` must be greater than 0,
- `output.formats` must be non-empty and may contain only `json`, `csv`, and `html`,
- `output.number_bins` must be greater than 0,
- `output.critical_path_report_limit` must be greater than 0,
- `staffing.effort_percentile`, when set, must be between 1 and 99,
- `staffing.min_individual_productivity` must be greater than 0 and at most 1,
- `experience_profiles[*].productivity_factor` must be greater than 0,
- `experience_profiles[*].communication_overhead` must be between 0 and 1,
- `constrained_scheduling.sickness_prob` must be between 0 and 1.
- `constrained_scheduling.pass1_iterations` must be greater than 0,
- `sprint_defaults.planning_confidence_level` must be between 0 and 1,
- `sprint_defaults.removed_work_treatment` must be either `churn_only` or `reduce_backlog`,
- `sprint_defaults.velocity_model` must be either `empirical` or `neg_binomial`,
- `sprint_defaults.volatility_disruption_probability` must be between 0 and 1,
- `sprint_defaults.volatility_disruption_multiplier_low`, `volatility_disruption_multiplier_expected`, and `volatility_disruption_multiplier_high` must be greater than or equal to 0,
- `sprint_defaults.spillover_model` must be either `table` or `logistic`,
- `sprint_defaults.spillover_size_reference_points` must be greater than 0,
- `sprint_defaults.spillover_consumed_fraction_alpha` and `sprint_defaults.spillover_consumed_fraction_beta` must be greater than 0,
- `sprint_defaults.spillover_logistic_slope` must be greater than 0,
- `sprint_defaults.sickness.probability_per_person_per_week` must be greater than 0 and less than 1,
- `sprint_defaults.sickness.duration_log_sigma` must be greater than 0.

## Related settings in the project file

Some important settings are **not** part of `config.yaml`. They belong in the project file instead.

For example, `probability_red_threshold` and `probability_green_threshold` are project-level fields stored in the simulation results and available for programmatic use:

```yaml
project:
  name: "My Project"
  start_date: "2025-01-01"
  probability_red_threshold: 0.50
  probability_green_threshold: 0.90
```

Default values:

- `probability_red_threshold`: `0.50`
- `probability_green_threshold`: `0.90`

!!! note
    These thresholds are stored in simulation results and exported in JSON output, but they do **not** control the colour of the HTML thermometer chart. The thermometer uses a fixed gradient from dark orange at 50 % to dark green at 99 %, computed solely from the probability value of each segment.

## Calibrating configuration values

To calibrate the configuration for your organisation:

1. collect historical estimate-versus-actual data,
2. derive realistic uncertainty multipliers,
3. adjust symbolic estimate mappings to match your team's sizing habits,
4. tune staffing profiles to reflect your real communication overhead,
5. iterate over several completed projects.

Examples:

- if experienced teams historically finish at about 85% of baseline effort, set `team_experience.high: 0.85`,
- if distributed teams typically take about 30% longer, set `team_distribution.distributed: 1.30`,
- if your team uses Story Point 8 for bigger work than the defaults assume, widen the `story_points.8` range.

