
# Configuration

## Overview

`Config` is the single source of truth for all default values in mcprojsim — uncertainty multipliers, T-shirt-size and story-point mappings, output settings, staffing profiles, constrained-scheduling parameters, and sprint-planning defaults. `Config.load_from_file()` merges YAML overrides onto the built-in defaults rather than replacing the whole structure, so you only need to specify the fields you want to change. Use this module whenever you need to customise simulation behaviour programmatically or inspect the defaults your project file inherits.

**When to use this module:** Customise T-shirt sizes, story-point ranges, uncertainty factors, constrained-scheduling assignment mode, or output format settings without modifying the project YAML.

| Capability | Description |
|---|---|
| T-shirt size mappings | Configurable low/expected/high hour ranges per size label, organised by category |
| Story-point mappings | Configurable low/expected/high day ranges per point value |
| Uncertainty factor multipliers | Per-factor, per-level multipliers (e.g. `team_experience: high → 0.90`) applied during simulation |
| Sub-config classes | `SimulationConfig`, `LognormalConfig`, `OutputConfig`, `StaffingConfig`, `ConstrainedSchedulingConfig`, `SprintDefaultsConfig` |
| Merge-onto-defaults loading | `Config.load_from_file()` deep-merges a YAML file onto built-in defaults |
| Programmatic defaults | `Config.get_default()` returns a fully populated instance with no file required |

**Imports:**
```python
from mcprojsim.config import Config
```

## `Config`

Application-wide configuration for simulation settings, output formatting, uncertainty-factor multipliers, T-shirt-size mappings, story-point mappings, staffing recommendations, and sprint-planning defaults.

**Top-level fields:**

| Field | Type | Description |
|-------|------|-------------|
| `uncertainty_factors` | `dict[str, dict[str, float]]` | Multipliers for uncertainty factors |
| `t_shirt_sizes` | `dict[str, dict[str, TShirtSizeConfig]]` | T-shirt size mappings by category |
| `t_shirt_size_default_category` | `str` | Default category for bare T-shirt sizes (default: `"epic"`) |
| `t_shirt_size_unit` | `EffortUnit` | Unit for T-shirt size estimates (default: `HOURS`) |
| `story_points` | `dict[int, StoryPointConfig]` | Story point mappings |
| `story_point_unit` | `EffortUnit` | Unit for story point estimates (default: `DAYS`) |
| `simulation` | `SimulationConfig` | Simulation defaults |
| `lognormal` | `LogNormalConfig` | Log-normal distribution settings |
| `output` | `OutputConfig` | Output and export settings |
| `staffing` | `StaffingConfig` | Staffing analysis configuration |
| `constrained_scheduling` | `ConstrainedSchedulingConfig` | Resource-constrained scheduling settings |
| `sprint_defaults` | `SprintDefaultsConfig` | Sprint planning defaults |

**Key methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `Config.load_from_file` | `(config_path: Path \| str) -> Config` | Load configuration from a YAML file, merging overrides onto built-in defaults. |
| `Config.get_default` | `() -> Config` | Return a `Config` instance populated with built-in defaults. |
| `get_uncertainty_multiplier` | `(factor_name: str, level: str) -> float` | Look up a multiplier for a named uncertainty factor and level. |
| `get_t_shirt_size` | `(size: str) -> TShirtSizeConfig \| None` | Resolve a T-shirt size label. Returns `None` on unrecognised input. |
| `resolve_t_shirt_size` | `(size: str) -> TShirtSizeConfig` | Resolve a T-shirt size label. Raises `ValueError` on unrecognised input. |
| `get_t_shirt_categories` | `() -> list[str]` | List all configured T-shirt size categories. |
| `get_story_point` | `(points: int) -> StoryPointConfig \| None` | Resolve a story point value. Returns `None` if not configured. |
| `get_lognormal_high_z_value` | `() -> float` | Return the Z-score corresponding to `lognormal.high_percentile`. |

**Example: Working with Configuration**

```python
from mcprojsim.config import Config

# Load custom config
config = Config.load_from_file("config.yaml")

# Or use defaults
config = Config.get_default()

# Query uncertainty factors
team_multiplier = config.get_uncertainty_multiplier("team_experience", "high")
print(f"High-experience multiplier: {team_multiplier}")

# Query T-shirt sizes
size_config = config.get_t_shirt_size("M")
if size_config:
    print(f"M estimate: {size_config.low}-{size_config.expected}-{size_config.high} hours")

# Query story points
sp = config.get_story_point(5)
if sp:
    print(f"5 story points: {sp.low}-{sp.expected}-{sp.high} hours")

# List T-shirt categories
categories = config.get_t_shirt_categories()
print(f"Available categories: {', '.join(categories)}")

# Access output settings
print(f"Default histogram bins: {config.output.number_bins}")
print(f"Critical path limit: {config.output.critical_path_report_limit}")
```

## Config Sub-Models

### `TShirtSizeConfig` / `StoryPointConfig`

Both inherit from `EstimateRangeConfig` and contain:

| Field | Type | Description |
|-------|------|-------------|
| `low` | `float` | Optimistic estimate |
| `expected` | `float` | Best estimate |
| `high` | `float` | Pessimistic estimate |

Returned by `config.get_t_shirt_size()` and `config.get_story_point()`.

### `ExperienceProfileConfig`

Productivity and overhead parameters for an experience profile.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `productivity_factor` | `float` | `1.0` | Effective output multiplier |
| `communication_overhead` | `float` | `0.06` | Fraction of capacity lost to coordination (0.0–1.0) |

Used inside `StaffingConfig.experience_profiles`.

### `OutputConfig`

Settings for simulation output and export behavior.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `formats` | `list[str]` | `["json", "csv", "html"]` | Default export formats |
| `include_histogram` | `bool` | `True` | Include histogram data in exports |
| `number_bins` | `int` | `50` | Number of bins for histogram charts |
| `critical_path_report_limit` | `int` | `2` | Max critical path sequences to show |

**Histogram binning note:** The `number_bins` setting is used by all exporters when generating distribution charts in JSON, CSV, and HTML reports. You can also override this per-run via the `--number-bins` CLI flag.

### `SimulationConfig`

Defaults for simulation runs.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `default_iterations` | `int` | `10000` | Default Monte Carlo iteration count |
| `random_seed` | `int \| None` | `None` | Default random seed |
| `max_stored_critical_paths` | `int` | `20` | Maximum distinct critical paths to track |

### `LogNormalConfig`

Shifted log-normal interpretation settings.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `high_percentile` | `int` | `95` | The percentile the "high" estimate maps to. Allowed values: `70`, `75`, `80`, `85`, `90`, `95`, `99`. |

### `StaffingConfig`

Configuration for staffing recommendations.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `effort_percentile` | `int \| None` | `None` | Percentile to base staffing on (e.g., `80` for P80). When `None`, mean effort is used. |
| `min_individual_productivity` | `float` | `0.25` | Floor for individual productivity after communication overhead. |
| `experience_profiles` | `dict[str, ExperienceProfileConfig]` | `"senior"`, `"mixed"`, `"junior"` | Named team experience profiles. |

**Example:**

```python
# Use P80 effort for staffing (more conservative)
config = Config.get_default()
config.staffing.effort_percentile = 80

engine = SimulationEngine(iterations=10000, config=config)
results = engine.run(project)
```

### `ConstrainedSchedulingConfig`

Settings for resource-constrained scheduling.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sickness_prob` | `float` | `0.0` | Default per-resource sickness probability when not specified on the resource. |
| `assignment_mode` | `ConstrainedSchedulingAssignmentMode` | `"greedy_single_pass"` | Scheduling dispatch policy. `"greedy_single_pass"` uses deterministic ID-order greedy dispatch; `"criticality_two_pass"` runs a criticality-ranking pass first. |
| `pass1_iterations` | `int` | `1000` | Iteration count for the criticality-ranking pass when using `"criticality_two_pass"`. |

### `SprintDefaultsConfig`

Company-wide defaults for sprint-planning behavior.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `planning_confidence_level` | `float` | `0.80` | Default confidence for commitment guidance. |
| `removed_work_treatment` | `"churn_only" \| "reduce_backlog"` | `"churn_only"` | How removed work is accounted for in velocity. |
| `velocity_model` | `"empirical" \| "neg_binomial"` | `"empirical"` | Velocity sampling model. |
| `volatility_disruption_probability` | `float` | `0.0` | Default disruption probability per sprint. |
| `volatility_disruption_multiplier_low` | `float` | `1.0` | Low-end disruption multiplier. |
| `volatility_disruption_multiplier_expected` | `float` | `1.0` | Expected disruption multiplier. |
| `volatility_disruption_multiplier_high` | `float` | `1.0` | High-end disruption multiplier. |
| `spillover_model` | `"table" \| "logistic"` | `"table"` | Spillover estimation model. |
| `spillover_size_reference_points` | `float` | `5.0` | Reference sprint size for the spillover table. |
| `spillover_size_brackets` | `list[dict[str, float \| None]]` | See defaults | Bracket definitions for the table-based spillover model. |
| `spillover_consumed_fraction_alpha` | `float` | `3.25` | Beta distribution alpha for consumed-fraction sampling. |
| `spillover_consumed_fraction_beta` | `float` | `1.75` | Beta distribution beta for consumed-fraction sampling. |
| `spillover_logistic_slope` | `float` | `1.9` | Slope for the logistic spillover model. |
| `spillover_logistic_intercept` | `float` | `~-1.99` | Intercept for the logistic spillover model. |
| `sickness` | `SprintSicknessDefaultsConfig` | See below | Company-wide sprint sickness defaults. |

### `SprintSicknessDefaultsConfig`

Company-wide defaults for sprint sickness modelling. Nested inside `SprintDefaultsConfig.sickness`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `False` | Whether sickness is modelled by default in sprint simulations. |
| `probability_per_person_per_week` | `float` | `0.058` | Probability that a team member falls sick in any given week. |
| `duration_log_mu` | `float` | `0.693` | Log-mean of the log-normal sickness duration distribution. |
| `duration_log_sigma` | `float` | `0.75` | Log-standard-deviation of the sickness duration distribution. |
