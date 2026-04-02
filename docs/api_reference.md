# API Reference

This page documents the main Python API intended for library consumers.

The most stable entry points are:

- **Root package imports** from `mcprojsim` — Quick-start for common workflows
- **Data models** from `mcprojsim.models` — Project structure, tasks, risks, estimates
- **File parsers** from `mcprojsim.parsers` — Load YAML/TOML project files
- **Simulation engines** from `mcprojsim` and `mcprojsim.planning` — Run Monte Carlo simulations
- **Exporters** from `mcprojsim.exporters` — Generate JSON, CSV, and HTML reports
- **Configuration** from `mcprojsim.config` — Simulation settings, uncertainty factors, estimate mappings
- **Analysis helpers** from `mcprojsim.analysis` — Statistical, sensitivity, critical-path, and staffing analysis
- **Sprint-planning APIs** from `mcprojsim.planning` and `mcprojsim.models.sprint_simulation` — Forecast sprint-based delivery
- **Natural language parser** from `mcprojsim.nl_parser` — Convert text descriptions to project files

Internal modules under `mcprojsim.simulation` and `mcprojsim.utils` are accessible but less stable and subject to change without deprecation.

## Root Package

The root package currently exports:

- `Project`
- `Task`
- `Risk`
- `SimulationEngine`
- `__version__`

```python
from mcprojsim import Project, Task, Risk, SimulationEngine, __version__
```

Use these imports when you want the shortest path for common programmatic usage.

## Simulation Workflow

The standard schedule-simulation workflow is:

1. Load a project definition with `YAMLParser` or `TOMLParser`
2. Optionally load a `Config`
3. Run `SimulationEngine`
4. Inspect `SimulationResults`
5. Export the results if needed

```python
from mcprojsim import SimulationEngine
from mcprojsim.config import Config
from mcprojsim.parsers import YAMLParser
from mcprojsim.exporters import JSONExporter, HTMLExporter

project = YAMLParser().parse_file("project.yaml")
config = Config.load_from_file("config.yaml")

engine = SimulationEngine(
    iterations=10000,
    random_seed=42,
    config=config,
    show_progress=True,
)
results = engine.run(project)

print(results.mean)
print(results.percentile(90))
print(results.get_critical_path())

JSONExporter.export(results, "results.json")
HTMLExporter.export(results, "results.html", project=project, config=config)
```

Sprint-planning workflow (when `project.sprint_planning.enabled` is true):

1. Load a `Project`
2. Run `SprintSimulationEngine`
3. Inspect `SprintPlanningResults`

```python
from mcprojsim.parsers import YAMLParser
from mcprojsim.planning.sprint_engine import SprintSimulationEngine

project = YAMLParser().parse_file("sprint_project.yaml")
engine = SprintSimulationEngine(iterations=5000, random_seed=42)
results = engine.run(project)

print(results.mean)
print(results.percentile(90))
print(results.date_percentile(90))
```

## Core API

### `SimulationEngine`

Main entry point for Monte Carlo simulation.

```python
from mcprojsim import SimulationEngine

engine = SimulationEngine(
    iterations=10000,
    random_seed=42,
    config=config,
    show_progress=True,
)

results = engine.run(project)
```

Key constructor parameters:

- `iterations`: Number of Monte Carlo iterations
- `random_seed`: Seed for reproducible sampling
- `config`: `Config` object used for uncertainty multipliers, T-shirt mappings, and Story Point mappings
- `show_progress`: Whether to print progress updates during long runs

Key method:

- `run(project: Project) -> SimulationResults`

### `SimulationResults`

Holds the output of a simulation run, including durations, summary statistics, percentiles, and critical-path frequency data.

Useful attributes:

- `project_name`
- `iterations`
- `durations`
- `task_durations`
- `mean`
- `median`
- `std_dev`
- `min_duration`
- `max_duration`
- `percentiles`

Useful methods:

- `calculate_statistics()`
- `percentile(p: int) -> float`
- `effort_percentile(p: int) -> float`
- `get_critical_path() -> dict[str, float]`
- `get_critical_path_sequences(top_n: int | None = None) -> list[CriticalPathRecord]`
- `get_most_frequent_critical_path() -> CriticalPathRecord | None`
- `get_histogram_data(bins: int = 50)`
- `probability_of_completion(target_hours: float) -> float`
- `total_effort_hours() -> float`
- `get_risk_impact_summary() -> dict[str, dict[str, float]]`
- `to_dict() -> dict[str, Any]`

```python
print(f"Mean: {results.mean:.2f}")
print(f"Median: {results.median:.2f}")
print(f"P80: {results.percentile(80):.2f}")

criticality = results.get_critical_path()
for task_id, value in criticality.items():
    print(task_id, value)
```

### `SprintSimulationEngine`

Entry point for sprint-planning Monte Carlo simulation.

Import path:

```python
from mcprojsim.planning.sprint_engine import SprintSimulationEngine
```

Constructor parameters:

- `iterations`
- `random_seed`

Key method:

- `run(project: Project) -> SprintPlanningResults`

### `SprintPlanningResults`

Result model for sprint-planning simulations.

Import path:

```python
from mcprojsim.models.sprint_simulation import SprintPlanningResults
```

Useful methods:

- `calculate_statistics()`
- `percentile(p: int) -> float`
- `date_percentile(p: int) -> date | None`
- `delivery_date_for_sprints(sprint_count: float) -> date | None`
- `to_dict() -> dict[str, Any]`

## Project Models

The data model layer is richer than the previous version of this page suggested.

### `Project`

Represents the complete project definition with metadata, tasks, risks, resources, and calendars.

**Key fields:**

- `project`: `ProjectMetadata` — project name, start date, hours/day, etc.
- `tasks`: `list[Task]` — work items and their dependencies
- `project_risks`: `list[Risk]` — top-level project-level risks
- `resources`: `list[ResourceSpec]` — named resource pools
- `calendars`: `list[CalendarSpec]` — named calendars for holidays/exclusions
- `sprint_planning`: `SprintPlanningSpec | None` — sprint planning configuration if enabled

**Key methods:**

- `get_task_by_id(task_id: str) -> Task | None` — Retrieve a task by its ID
- `to_dict() -> dict[str, Any]` — Convert to a dictionary representation

**Example:**

```python
from mcprojsim.parsers import YAMLParser

parser = YAMLParser()
project = parser.parse_file("project.yaml")

# Access project metadata
print(f"Project name: {project.project.name}")
print(f"Start date: {project.project.start_date}")
print(f"Total tasks: {len(project.tasks)}")

# Find a specific task
task = project.get_task_by_id("backend_api")
if task:
    print(f"Task: {task.name}, Dependencies: {task.dependencies}")

# Access all risks
for risk in project.project_risks:
    print(f"Risk: {risk.description}, Probability: {risk.probability}")

# Check if sprint planning is configured
if project.sprint_planning and project.sprint_planning.enabled:
    print(f"Sprint length: {project.sprint_planning.sprint_length_weeks} weeks")
```

### `ProjectMetadata`

Stores top-level project settings and characteristics.

**Key fields:**

- `name`: str — Project name
- `description`: str | None — Optional project description
- `start_date`: date — Project start date
- `currency`: str | None — Currency for cost tracking
- `confidence_levels`: list[int] — Percentiles to include in reports (default: [10, 25, 50, 75, 80, 85, 90, 95, 99])
- `probability_red_threshold`: float | None — Probability threshold marking risk level (default: 0.5)
- `probability_green_threshold`: float | None — Probability threshold marking success (default: 0.9)
- `hours_per_day`: float | None — Working hours per day (default from config)
- `distribution`: DistributionType | None — Default task duration distribution (default: triangular)
- `team_size`: int | None — Total team size (used for coordination overhead calculations)

**Example:**

```python
project = parser.parse_file("project.yaml")
meta = project.project

print(f"Project: {meta.name}")
print(f"Start: {meta.start_date}")
print(f"Duration: {meta.duration_days} days" if hasattr(meta, 'duration_days') else "")
print(f"Tracked thresholds: {meta.confidence_levels}")
print(f"Hours/day: {meta.hours_per_day}")
if meta.team_size:
    print(f"Team size: {meta.team_size} people")
```

### `Task`

Represents a single work item in the project network.

**Key fields:**

- `id`: str — Unique task identifier
- `name`: str — Human-readable task name
- `description`: str | None — Optional task description
- `estimate`: `TaskEstimate` — Duration estimate
- `dependencies`: `list[str]` — List of task IDs this task depends on
- `uncertainty_factors`: `UncertaintyFactors | None` — Optional uncertainty adjustments
- `resources`: `list[str]` — Required resource names
- `max_resources`: int | None — Maximum number of resources that can be assigned
- `min_experience_level`: str | None — Minimum experience level required
- `planning_story_points`: int | None — Story points override for sprint planning
- `risks`: `list[Risk]` — Task-specific risks

**Key methods:**

- `has_dependency(task_id: str) -> bool` — Check if this task depends on another task

**Example:**

```python
# Iterate over all tasks
for task in project.tasks:
    print(f"Task: {task.id} - {task.name}")
    print(f"  Description: {task.description or 'N/A'}")
    print(f"  Resources: {task.resources}")
    print(f"  Depends on: {task.dependencies}")
    if task.estimate:
        print(f"  Estimate: {task.estimate.low}-{task.estimate.expected}-{task.estimate.high} hours")
    if task.risks:
        print(f"  Risks: {len(task.risks)} identified")
    print()

# Find tasks with no dependencies
root_tasks = [t for t in project.tasks if not t.dependencies]
print(f"Root tasks (no dependencies): {[t.id for t in root_tasks]}")

# Find the longest task
longest_task = max(project.tasks, key=lambda t: t.estimate.high if t.estimate else 0)
print(f"Longest task: {longest_task.id}, up to {longest_task.estimate.high} hours")
```

### `TaskEstimate`

Supports four estimation styles:

- Triangular estimates via `low`, `expected`, and `high`
- Log-normal estimates via `low`, `expected`, and `high`
- T-shirt-sized estimates via `t_shirt_size`
- Story Point estimates via `story_points`

**Key fields:**

- `distribution`: DistributionType | None — Override the default distribution for this task
- `low`: float | None — Minimum hours (optimistic)
- `expected`: float | None — Best estimate in hours
- `high`: float | None — Maximum hours (pessimistic)
- `t_shirt_size`: str | None — Size token (XS, S, M, L, XL, XXL)
- `story_points`: int | None — Story point value
- `unit`: EffortUnit | None — Effort unit (hours, days, weeks)

**Example:**

```python
for task in project.tasks:
    est = task.estimate
    
    if est.story_points:
        print(f"Task {task.id}: {est.story_points} story points")
    elif est.t_shirt_size:
        print(f"Task {task.id}: {est.t_shirt_size} T-shirt")
    else:
        print(f"Task {task.id}: {est.low}-{est.expected}-{est.high} hours")
    
    # Show the distribution type (if overridden for this task)
    if est.distribution:
        print(f"  Distribution: {est.distribution.value}")
```

### `Risk` and `RiskImpact`

Represents task-level or project-level risk.

**Risk fields:**

- `description`: str — Risk description
- `probability`: float — Probability this risk occurs (0.0 to 1.0)
- `impact`: float | RiskImpact — Impact when risk happens
- `contingency`: float | None — Optional time contingency for specific risks

**RiskImpact fields:**

- `type`: ImpactType — "percentage" or "absolute"
- `value`: float — Percentage (0–100) or absolute hours
- `unit`: EffortUnit | None — Unit only relevant for absolute impacts

**Risk methods:**

- `get_impact_value(base_duration: float = 0.0) -> float` — Calculate numeric impact in hours

**Example:**

```python
# Access project-level risks
for risk in project.project_risks:
    impact = risk.get_impact_value()
    print(f"Project risk: {risk.description}")
    print(f"  Probability: {risk.probability * 100:.0f}%")
    print(f"  Impact: {impact:.1f} hours")

# Access task-level risks
for task in project.tasks:
    for risk in task.risks:
        impact = risk.get_impact_value(base_duration=task.estimate.expected)
        print(f"Task {task.id} risk: {risk.description}")
        print(f"  Probability: {risk.probability * 100:.0f}%")
        print(f"  Impact: {impact:.1f} hours")
```

### `ResourceSpec`

Defines a named resource pool that can be assigned to tasks.

**Key fields:**

- `name`: str — Resource name (e.g., "Backend Developer", "QA")
- `capacity`: int | float — Total availability (persons or person-hours)
- `costs_per_hour`: float | None — Cost per hour (optional)

**Example:**

```python
for resource in project.resources:
    print(f"Resource: {resource.name}")
    print(f"  Capacity: {resource.capacity}")
    if resource.costs_per_hour:
        print(f"  Cost/hour: ${resource.costs_per_hour}")
```

### `CalendarSpec`

Defines a calendar for holidays, vacation, or maintenance windows.

**Key fields:**

- `name`: str — Calendar identifier
- `periods`: list of exclusion periods (vacation, holidays, etc.)

**Example:**

```python
for calendar in project.calendars:
    print(f"Calendar: {calendar.name}")
```

### `UncertaintyFactors`

Applies multipliers to adjust base task duration based on project characteristics.

**Supported fields:**

- `team_experience`: "high" | "medium" | "low"
- `requirements_maturity`: "high" | "medium" | "low"
- `technical_complexity`: "low" | "medium" | "high"
- `team_distribution`: "colocated" | "distributed"
- `integration_complexity`: "low" | "medium" | "high"

Each is optional; only specified factors affect the task estimate.

**Example:**

```python
for task in project.tasks:
    if task.uncertainty_factors:
        factors = task.uncertainty_factors
        print(f"Task {task.id} uncertainty adjustments:")
        if factors.team_experience:
            print(f"  Team experience: {factors.team_experience}")
        if factors.technical_complexity:
            print(f"  Technical complexity: {factors.technical_complexity}")
```

### Enums

The following enums are also part of the model API:

- `DistributionType` — "triangular" or "lognormal"
- `ImpactType` — "percentage" or "absolute"
- `EffortUnit` — "hours", "days", or "weeks"
- `SprintCapacityMode` — "story_points" or "tasks"
- `SprintVelocityModel` — "empirical" or "neg_binomial"
- `RemovedWorkTreatment` — "churn_only" or "reduce_backlog"

## Simulation Results Models

### `SimulationResults`

Holds the complete output of a Monte Carlo simulation run, including all percentiles, critical path analysis, risk summaries, resource diagnostics, and per-task metrics.

**Key properties:**

- `project_name`: str — Name of the project that was simulated
- `iterations`: int — Number of iterations run
- `random_seed`: int | None — Seed used for reproducibility
- `hours_per_day`: float — Hours per calendar day
- `schedule_mode`: str — "dependency_only" or "constrained"
- `resource_constraints_active`: bool — Whether resource-constrained scheduling was used
- `mean`: float — Mean project duration (hours)
- `median`: float — Median project duration (hours)
- `std_dev`: float — Standard deviation of duration
- `min_duration`: float — Minimum observed duration
- `max_duration`: float — Maximum observed duration
- `skewness`: float — Skewness of the distribution
- `kurtosis`: float — Excess kurtosis of the distribution
- `percentiles`: Dict[int, float] — Per-percentile duration (hours)
- `effort_percentiles`: Dict[int, float] — Per-percentile total effort (person-hours)
- `effort_durations`: np.ndarray — Per-iteration total effort (project-wide)
- `task_slack`: Dict[str, float] — Mean schedule slack per task (hours)
- `max_parallel_tasks`: int — Peak parallel task count
- `resource_wait_time_hours`: float — Total wait time caused by resource unavailability
- `resource_utilization`: float — Average resource utilization (0.0–1.0)
- `calendar_delay_time_hours`: float — Hours lost to calendar constraints (weekends, holidays)
- `two_pass_trace`: `TwoPassDelta | None` — Traceability data when two-pass scheduling was enabled

**Key methods:**

- **`percentile(p: int) -> float`** — Get calendar duration for a specific percentile
- **`probability_of_completion(target_hours: float) -> float`** — Calculate probability of finishing within a target duration
- **`delivery_date(effort_hours: float) -> date | None`** — Convert project duration to a calendar date
- **`get_critical_path() -> Dict[str, float]`** — Per-task criticality index (0.0–1.0, frequency on critical path)
- **`get_critical_path_sequences(limit: int) -> list[CriticalPathRecord]`** — Most frequent full paths (up to `limit`)
- **`get_most_frequent_critical_path() -> CriticalPathRecord | None`** — Single most common critical path
- **`get_histogram_data(bins: int = 50) -> Tuple[np.ndarray, np.ndarray]`** — Bin edges and counts for distribution visualization
- **`get_risk_impact_summary() -> Dict[str, Dict[str, float]]`** — Per-task risk triggering and impact statistics
- **`total_effort_hours() -> float`** — Sum of all task base estimates
- **`to_dict() -> dict[str, Any]`** — Serialize results to a dictionary

**Example: Complete Results Query**

```python
from mcprojsim.simulation import SimulationEngine
from mcprojsim.config import Config
from mcprojsim.parsers import YAMLParser

# Setup
project = YAMLParser().parse_file("project.yaml")
config = Config.get_default()
engine = SimulationEngine(iterations=10000, random_seed=42, config=config)
results = engine.run(project)

# Query duration statistics
print(f"Mean duration: {results.mean:.1f} hours ({results.mean / results.hours_per_day:.1f} days)")
print(f"Median (P50): {results.percentile(50):.1f} hours")
print(f"P80 estimate: {results.percentile(80):.1f} hours")
print(f"P95 estimate: {results.percentile(95):.1f} hours")

# Calculate success odds for a deadline
deadline_hours = 500
success_prob = results.probability_of_completion(deadline_hours)
print(f"\nProbability of completion within {deadline_hours} hours: {success_prob*100:.1f}%")

# Get a delivery date for a specific duration
delivery = results.delivery_date(results.percentile(80))
print(f"P80 delivery date: {delivery}")

# Analyze critical path
critical_tasks = results.get_critical_path()
top_critical = sorted(critical_tasks.items(), key=lambda x: x[1], reverse=True)[:5]
print("\nTop 5 critical tasks (frequency on critical path):")
for task_id, criticality in top_critical:
    print(f"  {task_id}: {criticality*100:.1f}%")

# Get most common path
most_common = results.get_most_frequent_critical_path()
if most_common:
    print(f"\nMost frequent path ({most_common.frequency*100:.1f}%): {most_common.format_path()}")

# Show histogram data (for charting)
bin_edges, counts = results.get_histogram_data(bins=40)
print(f"\nHistogram: {len(bin_edges)-1} bins, total observations: {sum(counts)}")

# Risk analysis
risk_summary = results.get_risk_impact_summary()
for task_id, stats in risk_summary.items():
    if stats['trigger_rate'] > 0.05:  # Show risks triggered in >5% of iterations
        print(f"Task {task_id}: {stats['trigger_rate']*100:.1f}% trigger rate, "
              f"mean impact {stats['mean_impact']:.1f}h")

# Resource constraints info (if applicable)
if results.resource_constraints_active:
    print(f"\nResource utilization: {results.resource_utilization*100:.1f}%")
    print(f"Average resource wait time: {results.resource_wait_time_hours:.1f} hours")
    print(f"Calendar delay time: {results.calendar_delay_time_hours:.1f} hours")

# Two-pass scheduling info (if used)
if results.two_pass_trace and results.two_pass_trace.enabled:
    print(f"\nTwo-pass scheduling used:")
    print(f"  Pass 1 iterations: {results.two_pass_trace.pass1_iterations}")
    print(f"  Pass 2 iterations: {results.two_pass_trace.pass2_iterations}")
    print(f"  P50 delta: {results.two_pass_trace.delta_p50_hours:+.1f} hours")
```

### `SprintPlanningResults`

Result model for sprint-planning simulations, bridging between project-level simulation and sprint-by-sprint forecasting.

Import path:

```python
from mcprojsim.models.sprint_simulation import SprintPlanningResults
```

**Key properties:**

- `project_name`: str — Name of the project
- `iterations`: int — Number of Monte Carlo iterations
- `mean`: float — Mean total sprint count to completion
- `median`: float — Median total sprint count
- `std_dev`: float — Standard deviation of sprint count
- `percentiles`: Dict[int, float] — Sprint count per percentile
- `date_percentiles`: Dict[int, date | None] — Calendar dates corresponding to percentiles
- `sprint_length_weeks`: float — Length of each sprint
- `planned_commitment_guidance`: float — Recommended capacity units per sprint
- `historical_diagnostics`: dict — Statistics from historical data (when available)
- `disruption_statistics`: dict — Disruption event statistics
- `carryover_statistics`: dict — Carryover (incomplete work) statistics
- `spillover_statistics`: dict — Task spillover statistics
- `burnup_percentiles`: list[dict] — Per-sprint cumulative work (percentiles)

**Key methods:**

- **`percentile(p: int) -> float`** — Total sprint count for a percentile
- **`date_percentile(p: int) -> date | None`** — Calendar date for a percentile
- **`delivery_date_for_sprints(sprint_count: float) -> date | None`** — Convert sprint count to calendar date
- **`to_dict() -> dict[str, Any]`** — Serialize to dictionary

**Example: Sprint Planning Results**

```python
from mcprojsim.planning.sprint_engine import SprintSimulationEngine

# Setup
project = YAMLParser().parse_file("sprint_project.yaml")
engine = SprintSimulationEngine(iterations=5000, random_seed=42)
results = engine.run(project)

# Sprint count distribution
print(f"Mean duration: {results.mean:.1f} sprints")
print(f"P50 duration: {results.percentile(50):.1f} sprints")
print(f"P80 duration: {results.percentile(80):.1f} sprints")

# Calendar predictions
print(f"P80 completion date: {results.date_percentile(80)}")

# Commitment guidance
print(f"Recommended sprint capacity: {results.planned_commitment_guidance:.1f} units/sprint")

# Historical diagnostics (if history was provided)
if results.historical_diagnostics:
    hist = results.historical_diagnostics
    print(f"Historical velocity: mean {hist.get('velocity_mean', 0):.1f}")
    print(f"Historical observations: {hist.get('observation_count', 0)}")
```

## Parsers

### `YAMLParser`

Parses YAML project files into `Project` objects.

Methods:

- `parse_file(file_path) -> Project`
- `parse_dict(data) -> Project`
- `validate_file(file_path) -> tuple[bool, str]`

```python
from mcprojsim.parsers import YAMLParser

parser = YAMLParser()
project = parser.parse_file("project.yaml")
is_valid, error = parser.validate_file("project.yaml")
```

### `TOMLParser`

Same interface as `YAMLParser`, but for TOML project files.

```python
from mcprojsim.parsers import TOMLParser

parser = TOMLParser()
project = parser.parse_file("project.toml")
```

## Configuration

### `Config`

Application-wide configuration for simulation settings, output formatting, uncertainty-factor multipliers, T-shirt-size mappings, story-point mappings, staffing recommendations, and sprint-planning defaults.

**Top-level fields:**

- `uncertainty_factors`: Dict[str, Dict[str, float]] — Multipliers for uncertainty factors
- `t_shirt_sizes`: Dict[str, Dict[str, TShirtSizeConfig]] — T-shirt size mappings by category
- `t_shirt_size_default_category`: str — Default category for bare T-shirt sizes
- `t_shirt_size_unit`: EffortUnit — Unit for T-shirt sizes
- `story_points`: Dict[int, StoryPointConfig] — Story point mappings
- `story_point_unit`: EffortUnit — Unit for story points
- `simulation`: `SimulationConfig` — Simulation defaults
- `lognormal`: `LognormalConfig` — Log-normal distribution settings
- `output`: `OutputConfig` — Output and export settings
- `staffing`: `StaffingConfig` — Staffing analysis configuration
- `constrained_scheduling`: `ConstrainedSchedulingConfig` — Resource-constrained settings
- `sprint_defaults`: `SprintDef aultsConfig` — Sprint planning defaults

**Key methods:**

- **`Config.load_from_file(config_path: Path | str) -> Config`** — Load from YAML config file
- **`Config.get_default() -> Config`** — Get built-in defaults
- **`get_uncertainty_multiplier(factor_name: str, level: str) -> float`** — Look up factor multiplier
- **`get_t_shirt_size(size: str) -> TShirtSizeConfig | None`** — Resolve a T-shirt size
- **`get_t_shirt_categories() -> list[str]`** — List all T-shirt categories
- **`resolve_t_shirt_size(size: str) -> TShirtSizeConfig`** — Resolve with error handling
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

### `OutputConfig`

Settings for simulation output and export behavior.

**Fields:**

- `formats`: list[str] — Default export formats ("json", "csv", "html")
- `include_histogram`: bool — Include histogram data in exports
- `histogram_bins`: int — Number of bins for histogram charts (default: 50)
- `critical_path_report_limit`: int — Max critical path sequences to show (default: 2)

**Histogram binning note:** The `histogram_bins` setting is used by all exporters when generating distribution charts in JSON, CSV, and HTML reports. You can also override this per-run via the `--number-bins` CLI flag.

### `SimulationConfig`

Defaults for simulation runs.

**Fields:**

- `default_iterations`: int — Default Monte Carlo iterations (default: 10000)
- `random_seed`: int | None — Default seed
- `max_stored_critical_paths`: int — Maximum distinct paths to track (default: 20)

### `StaffingConfig`

Configuration for staffing recommendations.

**Fields:**

- `effort_percentile`: int | None — Percentile to base staffing on (e.g., 80 for P80)
- `min_individual_productivity`: float — Minimum productivity per person
- `experience_profiles`: Dict[str, ExperienceProfileConfig] — Named team profiles

When `effort_percentile` is omitted, staffing uses mean effort. When set, it uses that percentile for both total effort and elapsed time, providing more conservative recommendations.

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

**Fields:**

- `sickness_prob`: float — Probability of resource illness
- `assignment_mode`: str — "greedy_single_pass" or "criticality_two_pass"
- `pass1_iterations`: int — Iterations for criticality ranking (two-pass only)

## Exporters

All exporters support histogram data, critical-path output, sprint-planning results, and historic-base data (when available). The histogram bin count defaults to 50 but is controlled by `config.output.histogram_bins`.

### `JSONExporter`

Exports comprehensive results including all percentiles, statistics, histogram data, critical paths, risk summaries, and sprint-planning data to JSON.

**Method:**

- `export(results: SimulationResults, output_path: Path | str, config: Config | None = None, critical_path_limit: int | None = None, sprint_results: SprintPlanningResults | None = None, include_historic_base: bool = False) -> None`

**Parameters:**

- `results` — Simulation results object
- `output_path` — File path for JSON output
- `config` — Active configuration (used for histogram bin count and other settings)
- `critical_path_limit` — Override number of critical paths to include (default from config)
- `sprint_results` — Sprint planning results (optional)
- `include_historic_base` — Include historic baseline data if available

**Example:**

```python
from mcprojsim.exporters import JSONExporter

JSONExporter.export(
    results,
    "results.json",
    config=config,
    critical_path_limit=5,
    sprint_results=sprint_results
)
```

### `CSVExporter`

Exports results as a CSV table format: metrics, percentiles, critical paths, histogram data, risk impact, resource diagnostics, and sprint data.

**Method:**

- `export(results: SimulationResults, output_path: Path | str, config: Config | None = None, critical_path_limit: int | None = None, sprint_results: SprintPlanningResults | None = None) -> None`

All parameters same as JSONExporter.

### `HTMLExporter`

Exports a formatted, interactive HTML report with thermometers, percentile tables, charts (using matplotlib), critical-path analysis, staffing recommendations, and sprint-planning traceability.

**Method:**

- `export(results: SimulationResults, output_path: Path | str, project: Project | None = None, config: Config | None = None, critical_path_limit: int | None = None, sprint_results: SprintPlanningResults | None = None, include_historic_base: bool = False) -> None`

**Additional parameters:**

- `project` — Original project definition (enables richer task-effort display and T-shirt/story-point annotations)
- Other parameters same as above

**Key features when `project` and `config` are provided:**

- T-shirt-sized tasks are rendered with the active configuration labels
- Story-point tasks show the configured hour ranges
- Task descriptions and dependencies are included
- Effort data is shown per task

**Example:**

```python
from mcprojsim.exporters import HTMLExporter

HTMLExporter.export(
    results,
    "report.html",
    project=project,
    config=config,
    critical_path_limit=10,
    sprint_results=sprint_results,
    include_historic_base=True
)
```

## Analysis Helpers

These specialized analysis modules were previously underdocumented. They provide focused statistical, sensitivity, and staffing analysis capabilities beyond what `SimulationResults` provides directly.

### `StatisticalAnalyzer`

Convenience helpers for descriptive statistics on duration arrays.

Import:

```python
from mcprojsim.analysis.statistics import StatisticalAnalyzer
```

**Methods:**

- **`calculate_statistics(durations: np.ndarray) -> Dict[str, float]`** — Returns mean, median, std_dev, min, max, coefficient of variation, skewness, excess kurtosis
- **`calculate_percentiles(durations: np.ndarray, percentiles: list[int]) -> Dict[int, float]`** — Compute specific percentiles
- **`confidence_interval(durations: np.ndarray, confidence: float = 0.95) -> Tuple[float, float]`** — Return lower/upper bounds for a confidence interval

### `SensitivityAnalyzer`

Analyzes which tasks have the strongest correlation with total project duration (Spearman rank correlation).

Import:

```python
from mcprojsim.analysis.sensitivity import SensitivityAnalyzer
```

**Methods:**

- **`calculate_correlations(results: SimulationResults) -> Dict[str, float]`** — Per-task correlation with total duration
- **`get_top_contributors(results: SimulationResults, n: int = 10) -> list[Tuple[str, float]]`** — Top N tasks by sensitivity

**Example:**

```python
analyzer = SensitivityAnalyzer()
correlations = analyzer.calculate_correlations(results)

# Show top 5 sensitive tasks
top_5 = analyzer.get_top_contributors(results, n=5)
for task_id, correlation in top_5:
    print(f"{task_id}: correlation = {correlation:.3f}")
```

### `CriticalPathAnalyzer`

Specialized analysis for critical paths and task criticality.

Import:

```python
from mcprojsim.analysis.critical_path import CriticalPathAnalyzer
```

**Methods:**

- **`get_criticality_index(results: SimulationResults) -> Dict[str, float]`** — Same as `results.get_critical_path()`
- **`get_most_critical_tasks(results: SimulationResults, threshold: float = 0.5) -> list[str]`** — Tasks appearing on critical path in >threshold of iterations
- **`get_most_frequent_paths(results: SimulationResults, top_n: int | None = None) -> list[CriticalPathRecord]`** — Most common paths (wraps `results.get_critical_path_sequences()`)

**Example:**

```python
analyzer = CriticalPathAnalyzer()

# Tasks on critical path >80% of the time
critical_tasks = analyzer.get_most_critical_tasks(results, threshold=0.8)
print(f"Always-critical tasks: {critical_tasks}")

# Most common path
paths = analyzer.get_most_frequent_paths(results, top_n=1)
if paths:
    print(f"Most common path: {paths[0].format_path()}")
```

### `StaffingAnalyzer`

Provides team-size recommendations and breaks down staffing by experience profile.

Import:

```python
from mcprojsim.analysis.staffing import StaffingAnalyzer
```

**Methods:**

- **`calculate_staffing_table(results: SimulationResults, config: Config) -> list[StaffingRow]`** — Per-profile team-size recommendations
- **`recommend_team_size(results: SimulationResults, config: Config) -> list[StaffingRecommendation]`** — Primary recommendations for each profile

**Fields in `StaffingRecommendation`:**

- `profile`: str — Experience level name (e.g., "senior", "mixed", "junior")
- `recommended_team_size`: int — Primary recommendation
- `total_effort_hours`: float — Total effort basis
- `critical_path_hours`: float — Critical path duration
- `calendar_working_days`: int — Calendar days needed
- `delivery_date`: date | None — Scheduled completion
- `efficiency`: float — Effective capacity vs nominal team size
- `effort_percentile`: int | None — Which percentile was used

**Example:**

```python
analyzer = StaffingAnalyzer()

# Get full table for all profiles
table = analyzer.calculate_staffing_table(results, config)
for row in table:
    print(f"{row.profile} team (size {row.team_size}): "
          f"{row.calendar_working_days} days, efficiency {row.efficiency*100:.1f}%")

# Get primary recommendations
recommendations = analyzer.recommend_team_size(results, config)
for rec in recommendations:
    print(f"{rec.profile}: recommend {rec.recommended_team_size} people "
          f"({rec.efficiency*100:.0f}% efficiency)")
```

## Validation Utilities

### `Validator`

Convenience utility for validating project files by extension.

Import:

```python
from mcprojsim.utils import Validator
```

**Method:**

- **`validate_file(file_path: str | Path) -> Tuple[bool, str]`** — Returns (is_valid, error_message). Auto-selects parser based on file extension.

**Example:**

```python
is_valid, error = Validator.validate_file("project.yaml")
if not is_valid:
    print(f"Validation failed: {error}")
else:
    print("Project is valid!")
```

### `setup_logging`

Configure logging verbosity and output for library usage.

Import:

```python
from mcprojsim.utils import setup_logging
```

**Method:**

- **`setup_logging(level: str = "WARNING") -> logging.Logger`** — Returns configured logger with specified level ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

**Example:**

```python
logger = setup_logging(level="INFO")
# Library logging now routes to this logger
```

## Not a Stable User-Facing API?

The following modules are currently imported in `mcprojsim.simulation` and `mcprojsim.utils`, but they are more internal and subject to change without deprecation. They are not intended for direct use by library consumers, but they are technically accessible if you want to experiment or build on top of them.

- `mcprojsim.simulation.distributions`
- `mcprojsim.simulation.scheduler`
- `mcprojsim.simulation.risk_evaluator`
- `mcprojsim.utils.logging`


## Natural Language Parser

### `NLProjectParser`

Converts semi-structured, plain-text project descriptions into valid mcprojsim YAML project files. Also available via the `mcprojsim generate` CLI command and the MCP server's `generate_project_file` tool.

```python
from mcprojsim.nl_parser import NLProjectParser

parser = NLProjectParser()
```

Methods:

- `parse(text: str) -> ParsedProject` — extract project metadata and tasks from a text description
- `to_yaml(project: ParsedProject) -> str` — render a `ParsedProject` as a valid YAML project file
- `parse_and_generate(text: str) -> str` — convenience wrapper that calls `parse` then `to_yaml`

Supported input patterns:

- `Project name: My Project`
- `Start date: 2026-04-01`
- `Task 1: Backend API` followed by bullet points
- `Size: M` or `Size XL` (T-shirt sizes)
- `Story points: 5`
- `Estimate: 3/5/10 days` (low/expected/high)
- `Depends on Task 1, Task 3`

```python
description = """
Project name: Website Redesign
Start date: 2026-06-01

Task 1: Design mockups
- Size: M

Task 2: Frontend implementation
- Size: L
- Depends on Task 1
"""

yaml_output = parser.parse_and_generate(description)
```

### Data classes

- `ParsedProject` — extracted project-level data (`name`, `start_date`, `hours_per_day`, `tasks`, `confidence_levels`)
- `ParsedTask` — extracted task data (`name`, `t_shirt_size`, `story_points`, `low_estimate`/`expected_estimate`/`high_estimate`, `dependency_refs`)
- `ParsedResource` — extracted resource data (`name`, `availability`, `experience_level`, `productivity_level`, `calendar`, `sickness_prob`, `planned_absence`)
- `ParsedCalendar` — extracted calendar data (`id`, `work_hours_per_day`, `work_days`, `holidays`)
- `ParsedSprintPlanning` — extracted sprint-planning settings (`enabled`, `sprint_length_weeks`, `capacity_mode`, `history`, ...)

---

## Complete External API Examples

### Example 1: Programmatic Simulation with Full Analysis

This example shows how an external tool can load a project, run a simulation, and perform comprehensive analysis:

```python
from mcprojsim import SimulationEngine
from mcprojsim.config import Config
from mcprojsim.parsers import YAMLParser
from mcprojsim.analysis.critical_path import CriticalPathAnalyzer
from mcprojsim.analysis.staffing import StaffingAnalyzer
from mcprojsim.analysis.sensitivity import SensitivityAnalyzer
from mcprojsim.exporters import HTMLExporter, JSONExporter

def run_comprehensive_analysis(project_file: str, output_dir: str):
    """Load, simulate, analyze, and export a complete project report."""
    
    # Step 1: Load project and configuration
    project = YAMLParser().parse_file(project_file)
    config = Config.get_default()
    
    # Step 2: Run simulation
    engine = SimulationEngine(
        iterations=10000,
        random_seed=42,
        config=config,
        show_progress=True
    )
    results = engine.run(project)
    
    # Step 3: Critical path analysis
    cp_analyzer = CriticalPathAnalyzer()
    critical_tasks = cp_analyzer.get_most_critical_tasks(results, threshold=0.7)
    print(f"Critical tasks (>70% frequency): {critical_tasks}")
    
    # Step 4: Sensitivity analysis
    sens_analyzer = SensitivityAnalyzer()
    top_risks = sens_analyzer.get_top_contributors(results, n=5)
    print("\nTop 5 sensitivity contributors:")
    for task_id, correlation in top_risks:
        print(f"  {task_id}: {correlation:.3f}")
    
    # Step 5: Staffing recommendations
    staff_analyzer = StaffingAnalyzer()
    recommendations = staff_analyzer.recommend_team_size(results, config)
    for rec in recommendations:
        print(f"Staffing ({rec.profile}): {rec.recommended_team_size} people, "
              f"{rec.calendar_working_days} days, {rec.efficiency*100:.0f}% efficiency")
    
    # Step 6: Export all formats
    base_path = f"{output_dir}/analysis"
    JSONExporter.export(results, f"{base_path}.json", config=config, project=project)
    HTMLExporter.export(results, f"{base_path}.html", project=project, config=config)
    
    return results

# Usage
results = run_comprehensive_analysis("project.yaml", "reports/")
print(f"\nSimulation complete. Mean duration: {results.mean:.0f} hours")
```

### Example 2: Dashboard Integration

This example demonstrates integrating mcprojsim into a web dashboard:

```python
from flask import Flask, request, jsonify
from mcprojsim import SimulationEngine
from mcprojsim.config import Config
from mcprojsim.models.project import Project
from pathlib import Path
import json

app = Flask(__name__)

@app.route('/api/simulate', methods=['POST'])
def simulate_project():
    """API endpoint for running simulations."""
    
    # Parse request
    data = request.json
    project_file = data.get('project_file')
    iterations = data.get('iterations', 5000)
    
    # Load and validate
    from mcprojsim.parsers import YAMLParser
    try:
        project = YAMLParser().parse_file(project_file)
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    
    # Run simulation
    config = Config.get_default()
    engine = SimulationEngine(iterations=iterations, config=config)
    results = engine.run(project)
    
    # Build response with key metrics
    return jsonify({
        'project_name': results.project_name,
        'iterations': results.iterations,
        'mean_hours': float(results.mean),
        'mean_days': float(results.mean / results.hours_per_day),
        'percentiles': {
            'p50': float(results.percentile(50)),
            'p80': float(results.percentile(80)),
            'p95': float(results.percentile(95)),
        },
        'critical_tasks': list(results.get_critical_path().keys())[:10],
        'success_at_500h': float(results.probability_of_completion(500)),
    })

@app.route('/api/config', methods=['GET'])
def get_config():
    """Return active configuration."""
    config = Config.get_default()
    return jsonify({
        't_shirt_categories': config.get_t_shirt_categories(),
        'uncertainty_factors': {
            'team_experience': ['high', 'medium', 'low'],
            'requirements_maturity': ['high', 'medium', 'low'],
        }
    })
```

### Example 3: Sprint Planning with Forecast

This example shows sprint-planning integration:

```python
from mcprojsim.parsers import YAMLParser
from mcprojsim.planning.sprint_engine import SprintSimulationEngine
from typing import List
from datetime import datetime, timedelta

def forecast_project_completion(project_file: str) -> dict:
    """Forecast sprint-by-sprint delivery timeline."""
    
    project = YAMLParser().parse_file(project_file)
    
    # Sprint planning must be enabled
    if not project.sprint_planning or not project.sprint_planning.enabled:
        raise ValueError("Sprint planning not enabled in project")
    
    # Run sprint simulation
    engine = SprintSimulationEngine(iterations=5000, random_seed=42)
    results = engine.run(project)
    
    # Build forecast
    forecast = {
        'project_name': results.project_name,
        'sprint_length_weeks': results.sprint_length_weeks,
        'forecasts': {
            'p50_sprints': results.percentile(50),
            'p80_sprints': results.percentile(80),
            'p50_date': results.date_percentile(50),
            'p80_date': results.date_percentile(80),
        },
        'guidance': {
            'recommended_capacity': results.planned_commitment_guidance,
            'historical_velocity': results.historical_diagnostics.get('velocity_mean', 0),
            'risk_level': 'low' if results.std_dev < results.mean * 0.2 else 'high',
        }
    }
    
    return forecast

# Usage
forecast = forecast_project_completion("sprint_project.yaml")
print(f"P80 completion: {forecast['forecasts']['p80_date']}")
```

### Example 4: Batch Processing Multiple Projects

This example processes multiple projects and generates a portfolio view:

```python
from pathlib import Path
from mcprojsim import SimulationEngine
from mcprojsim.config import Config
from mcprojsim.parsers import YAMLParser
import pandas as pd

def analyze_portfolio(project_dir: str) -> pd.DataFrame:
    """Run simulations for all projects in a directory and create summary."""
    
    results_list = []
    config = Config.get_default()
    
    for project_file in Path(project_dir).glob("*.yaml"):
        print(f"Processing {project_file.name}...")
        
        try:
            project = YAMLParser().parse_file(str(project_file))
            engine = SimulationEngine(iterations=5000, config=config, show_progress=False)
            results = engine.run(project)
            
            results_list.append({
                'project': project.project.name,
                'tasks': len(project.tasks),
                'mean_hours': results.mean,
                'mean_days': results.mean / results.hours_per_day,
                'p80_hours': results.percentile(80),
                'p95_hours': results.percentile(95),
                'risk_high': len([t for t in results.get_critical_path().items() 
                                 if t[1] > 0.8]),
            })
        except Exception as e:
            print(f"  Error: {e}")
    
    # Create DataFrame
    df = pd.DataFrame(results_list)
    df = df.sort_values('mean_days', ascending=False)
    
    print("\n=== Portfolio Summary ===")
    print(df.to_string(index=False))
    print(f"\nTotal projected effort: {df['mean_hours'].sum():.0f} hours")
    
    return df

# Usage
portfolio = analyze_portfolio("projects/")
```

### Example 5: Configuration-Driven Customization

This example shows how to customize the simulation via configuration:

```python
from mcprojsim.config import Config
from mcprojsim import SimulationEngine
from mcprojsim.parsers import YAMLParser
import yaml

def simulate_with_custom_config(project_file: str, config_file: str, overrides: dict):
    """Run simulation with config file + programmatic overrides."""
    
    # Load config from file
    config = Config.load_from_file(config_file)
    
    # Apply programmatic overrides
    if 'histogram_bins' in overrides:
        config.output.histogram_bins = overrides['histogram_bins']
    
    if 'iterations' in overrides:
        iterations = overrides['iterations']
    else:
        iterations = config.simulation.default_iterations
    
    if 'staffing_percentile' in overrides:
        config.staffing.effort_percentile = overrides['staffing_percentile']
    
    # Run simulation with customized config
    project = YAMLParser().parse_file(project_file)
    engine = SimulationEngine(
        iterations=iterations,
        random_seed=42,
        config=config
    )
    results = engine.run(project)
    
    return results

# Usage - override histogram bins to 100 and use P80 for staffing
results = simulate_with_custom_config(
    'project.yaml',
    'config.yaml',
    {
        'histogram_bins': 100,
        'staffing_percentile': 80,
        'iterations': 20000,
    }
)
```
