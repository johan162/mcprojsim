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

For example, if you define only `t_shirt_sizes.M`, the built-in mappings for `XS`, `S`, `L`, `XL`, and `XXL` remain available.

## Top-level configuration structure

The current configuration schema supports these top-level keys:

- `uncertainty_factors`
- `t_shirt_sizes`
- `t_shirt_size_unit`
- `story_points`
- `story_point_unit`
- `simulation`
- `output`
- `staffing`

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
  XS:
    low: 0.5
    expected: 1
    high: 2
  M:
    low: 3
    expected: 5
    high: 8

t_shirt_size_unit: "hours"

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

output:
  formats: ["json", "csv", "html"]
  include_histogram: true
  histogram_bins: 50
  critical_path_report_limit: 2

staffing:
  effort_percentile: null
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

Tasks may use `t_shirt_size` instead of explicit `min` / `expected` / `max` values.

Built-in size keys:

- `XS`
- `S`
- `M`
- `L`
- `XL`
- `XXL`

Built-in defaults:

| Size | `min` | `expected` | `max` |
|---|---:|---:|---:|
| `XS` | 0.5 | 1 | 2 |
| `S` | 1 | 2 | 4 |
| `M` | 3 | 5 | 8 |
| `L` | 5 | 8 | 13 |
| `XL` | 8 | 13 | 21 |
| `XXL` | 13 | 21 | 34 |

Example override:

```yaml
t_shirt_sizes:
  M:
    low: 4
    expected: 6
    high: 9
```

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

| Points | `min` | `expected` | `max` |
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

See [Task Estimation](user_guide/task_estimation.md#t-shirt-size-estimates) and [Task Estimation](user_guide/task_estimation.md#story-point-estimates) for more guidance.

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
  histogram_bins: 50
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
| `histogram_bins` | integer | `50` | Number of bins used for histograms |
| `critical_path_report_limit` | integer | `2` | Number of stored full critical paths shown by default |

Example:

```yaml
output:
  formats: ["json", "html"]
  include_histogram: true
  histogram_bins: 80
  critical_path_report_limit: 5
```

## Staffing settings

The `staffing` section controls the staffing analysis shown in CLI output and exports.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `effort_percentile` | integer or `null` | `null` | Use a specific effort percentile such as P80 instead of the mean |
| `min_individual_productivity` | float | `0.25` | Lower bound on per-person productivity after communication overhead |
| `experience_profiles` | mapping | built-in defaults | Named team profiles used for staffing recommendations |

### `effort_percentile`

When `effort_percentile` is `null`, staffing uses mean total effort and mean elapsed time.

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

## Viewing current configuration

```bash
mcprojsim config show
mcprojsim config show --config-file config.yaml
```

The `config show` output includes the most relevant effective settings, including:

- default iteration count,
- random seed,
- max stored critical paths,
- output histogram settings,
- critical path report limit,
- staffing settings.

## Validation rules

The configuration model validates these constraints directly:

- `t_shirt_size_unit` must be one of `hours`, `days`, or `weeks`,
- `story_point_unit` must be one of `hours`, `days`, or `weeks`,
- all configured estimate ranges require positive `min`, `expected`, and `max`,
- `simulation.default_iterations` must be greater than 0,
- `simulation.max_stored_critical_paths` must be greater than 0,
- `output.histogram_bins` must be greater than 0,
- `output.critical_path_report_limit` must be greater than 0,
- `staffing.effort_percentile`, when set, must be between 1 and 99,
- `staffing.min_individual_productivity` must be greater than 0 and at most 1,
- `experience_profiles[*].productivity_factor` must be greater than 0,
- `experience_profiles[*].communication_overhead` must be between 0 and 1.

## Related settings in the project file

Some important reporting and visualization settings are **not** part of `config.yaml`. They belong in the project file instead.

For example, the HTML thermometer visualization uses these project-level settings:

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

These thresholds control how probabilities are colored in the HTML report:

- below the red threshold: high risk,
- above the green threshold: low risk,
- between them: intermediate risk.

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
