
## Configuration

### `Config`

Application-wide configuration for simulation settings, output formatting, uncertainty-factor multipliers, T-shirt-size mappings, story-point mappings, staffing recommendations, and sprint-planning defaults.

**Top-level fields:**

- `uncertainty_factors`: dict[str, dict[str, float]] — Multipliers for uncertainty factors
- `t_shirt_sizes`: dict[str, dict[str, TShirtSizeConfig]] — T-shirt size mappings by category
- `t_shirt_size_default_category`: str — Default category for bare T-shirt sizes
- `t_shirt_size_unit`: `EffortUnit` — Unit for T-shirt sizes
- `story_points`: dict[int, StoryPointConfig] — Story point mappings
- `story_point_unit`: `EffortUnit` — Unit for story points
- `simulation`: `SimulationConfig` — Simulation defaults
- `lognormal`: `LogNormalConfig` — Log-normal distribution settings
- `output`: `OutputConfig` — Output and export settings
- `staffing`: `StaffingConfig` — Staffing analysis configuration
- `constrained_scheduling`: `ConstrainedSchedulingConfig` — Resource-constrained settings
- `sprint_defaults`: `SprintDefaultsConfig` — Sprint planning defaults

**Key methods:**

- **`Config.load_from_file(config_path: Path | str) -> Config`** — Load from YAML config file
- **`Config.get_default() -> Config`** — Get built-in defaults
- **`get_uncertainty_multiplier(factor_name: str, level: str) -> float`** — Look up factor multiplier
- **`get_t_shirt_size(size: str) -> TShirtSizeConfig | None`** — Resolve a T-shirt size (returns `None` on invalid input)
- **`resolve_t_shirt_size(size: str) -> TShirtSizeConfig`** — Resolve a T-shirt size (raises `ValueError` on invalid input)
- **`get_t_shirt_categories() -> list[str]`** — List all T-shirt categories
- **`get_story_point(points: int) -> StoryPointConfig | None`** — Resolve story points
- **`get_lognormal_high_z_value() -> float`** — Get Z-score for log-normal estimation

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
print(f"Default histogram bins: {config.output.histogram_bins}")
print(f"Critical path limit: {config.output.critical_path_report_limit}")
```

### Config Sub-Models

#### `TShirtSizeConfig` / `StoryPointConfig`

Both inherit from `EstimateRangeConfig` and contain:

- `low`: float — Optimistic estimate
- `expected`: float — Best estimate
- `high`: float — Pessimistic estimate

Returned by `config.get_t_shirt_size()` and `config.get_story_point()`.

#### `ExperienceProfileConfig`

Productivity and overhead parameters for an experience profile.

- `productivity_factor`: float — Effective output multiplier (default: 1.0)
- `communication_overhead`: float — Fraction of capacity lost to coordination (0.0–1.0, default: 0.06)

Used inside `StaffingConfig.experience_profiles`.

#### `OutputConfig`

Settings for simulation output and export behavior.

**Fields:**

- `formats`: list[str] — Default export formats (`"json"`, `"csv"`, `"html"`)
- `include_histogram`: bool — Include histogram data in exports
- `histogram_bins`: int — Number of bins for histogram charts (default: 50)
- `critical_path_report_limit`: int — Max critical path sequences to show (default: 2)

**Histogram binning note:** The `histogram_bins` setting is used by all exporters when generating distribution charts in JSON, CSV, and HTML reports. You can also override this per-run via the `--number-bins` CLI flag.

#### `SimulationConfig`

Defaults for simulation runs.

**Fields:**

- `default_iterations`: int — Default Monte Carlo iterations (default: 10000)
- `random_seed`: int | None — Default seed
- `max_stored_critical_paths`: int — Maximum distinct paths to track (default: 20)

#### `LogNormalConfig`

Shifted log-normal interpretation settings.

**Fields:**

- `high_percentile`: int — The percentile the "high" estimate maps to (allowed: specific Z-score-mapped values)

#### `StaffingConfig`

Configuration for staffing recommendations.

**Fields:**

- `effort_percentile`: int | None — Percentile to base staffing on (e.g., 80 for P80). When `None` (default), mean effort is used.
- `min_individual_productivity`: float — Floor for individual productivity after communication overhead (default: 0.25)
- `experience_profiles`: dict[str, ExperienceProfileConfig] — Named team profiles. Default profiles: `"senior"`, `"mixed"`, `"junior"`.

**Example:**

```python
# Use P80 effort for staffing (more conservative)
config = Config.get_default()
config.staffing.effort_percentile = 80

engine = SimulationEngine(iterations=10000, config=config)
results = engine.run(project)
```

#### `ConstrainedSchedulingConfig`

Settings for resource-constrained scheduling.

**Fields:**

- `sickness_prob`: float — Default per-resource sickness probability (default: 0.0)
- `assignment_mode`: `ConstrainedSchedulingAssignmentMode` — `"greedy_single_pass"` (default) or `"criticality_two_pass"`
- `pass1_iterations`: int — Iterations for criticality ranking in two-pass mode

#### `SprintDefaultsConfig`

Company-wide defaults for sprint-planning behavior.

**Fields:**

- `planning_confidence_level`: float — Default confidence for commitment guidance
- `removed_work_treatment`: `"churn_only"` | `"reduce_backlog"`
- `velocity_model`: `"empirical"` | `"neg_binomial"`
- `volatility_disruption_probability`: float — Default disruption probability
- `volatility_disruption_multiplier_low` / `_expected` / `_high`: float — Default disruption multipliers
- `spillover_model` / `spillover_size_reference_points` / `spillover_size_brackets`: various — Default spillover settings
- `spillover_consumed_fraction_alpha` / `_beta`: float — Beta distribution defaults
- `spillover_logistic_slope` / `_intercept`: float — Logistic model defaults
- `sickness`: `SprintSicknessDefaultsConfig` — Company-wide sickness defaults

