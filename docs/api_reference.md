# API Reference

This page documents the main Python API intended for library consumers. For installation and first steps, see the [Quickstart](quickstart.md).

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

!!! note "Internal modules"
    Modules under `mcprojsim.simulation` (distributions, scheduler, risk_evaluator) and `mcprojsim.utils` are accessible but considered internal. They may change without deprecation notice.

## Key Concepts

Before diving into the API, it helps to understand four concepts that mcprojsim distinguishes:

**Elapsed duration vs total effort.** *Elapsed duration* is the calendar time from project start to finish — what a Gantt chart shows. *Total effort* is the sum of all person-hours across every task, regardless of parallelism. A 100-hour project done by two people in parallel has ~50 hours elapsed duration but 100 hours of effort. `SimulationResults.mean` and `.percentile()` report elapsed duration; `.total_effort_hours()`, `.effort_percentile()`, and `.effort_durations` report effort.

**Dependency-only vs resource-constrained scheduling.** When a project defines no resources, the scheduler runs in *dependency-only* mode: tasks start as soon as their predecessors finish, with unlimited parallelism. When resources are defined, *constrained scheduling* activates: tasks compete for finite resource slots, potentially queuing behind other work. Check `results.schedule_mode` and `results.resource_constraints_active` to see which mode was used.

**Two-pass scheduling.** An optional extension of constrained scheduling. Pass 1 runs a smaller batch of iterations with simple greedy dispatch to rank tasks by criticality index. Pass 2 re-runs the full simulation using those ranks as scheduling priorities. Enable via `SimulationEngine(two_pass=True)` or `config.constrained_scheduling.assignment_mode = "criticality_two_pass"`. Results include a `two_pass_trace` with pass-1 vs pass-2 comparison data.

**Coordination overhead / team size.** When `project.project.team_size` is set, mcprojsim applies Brooks's Law–inspired communication overhead: larger teams lose a fraction of capacity to coordination. The staffing analyzer models this via `communication_overhead` and `min_individual_productivity` parameters per experience profile.

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

JSONExporter.export(results, "results.json", config=config, project=project)
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

Constructor parameters:

- `iterations`: Number of Monte Carlo iterations (default: 10000)
- `random_seed`: Seed for reproducible sampling
- `config`: `Config` object used for uncertainty multipliers, T-shirt mappings, and story-point mappings
- `show_progress`: Whether to print progress updates during long runs (default: `True`)
- `two_pass`: Enable criticality-two-pass scheduling (default: `False`). Only has effect when resource-constrained scheduling is active. Overrides `config.constrained_scheduling.assignment_mode`.
- `pass1_iterations`: Number of pass-1 iterations for criticality ranking. Overrides `config.constrained_scheduling.pass1_iterations` when provided. Capped to `iterations`.

Key method:

- `run(project: Project) -> SimulationResults`

### `SimulationResults`

Holds the output of a simulation run, including durations, summary statistics, percentiles, and critical-path frequency data.

Useful attributes:

- `project_name`
- `iterations`
- `random_seed`
- `hours_per_day`
- `start_date`
- `durations`
- `task_durations`
- `effort_durations` — per-iteration total person-effort array
- `mean`
- `median`
- `std_dev`
- `min_duration`
- `max_duration`
- `skewness`
- `kurtosis`
- `percentiles`
- `effort_percentiles`
- `sensitivity` — per-task Spearman rank correlations with total duration
- `task_slack` — mean schedule slack per task (hours)
- `max_parallel_tasks` — peak parallel task count
- `schedule_mode` — `"dependency_only"` or `"constrained"`
- `resource_constraints_active`
- `resource_wait_time_hours`
- `resource_utilization` — average utilization (0.0–1.0)
- `calendar_delay_time_hours`
- `two_pass_trace` — `TwoPassDelta | None`

Useful methods:

- `calculate_statistics()`
- `percentile(p: int) -> float`
- `effort_percentile(p: int) -> float`
- `get_critical_path() -> dict[str, float]`
- `get_critical_path_sequences(top_n: int | None = None) -> list[CriticalPathRecord]`
- `get_most_frequent_critical_path() -> CriticalPathRecord | None`
- `get_histogram_data(bins: int = 50) -> tuple[np.ndarray, np.ndarray]`
- `probability_of_completion(target_hours: float) -> float`
- `total_effort_hours() -> float`
- `hours_to_working_days(hours: float) -> int`
- `delivery_date(effort_hours: float) -> date | None`
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

### `CriticalPathRecord`

Aggregated full critical path sequence information.

**Fields:**

- `path`: `tuple[str, ...]` — ordered task IDs forming the path
- `count`: `int` — number of iterations this exact path appeared
- `frequency`: `float` — fraction of total iterations (0.0–1.0)

**Methods:**

- `format_path() -> str` — returns `"task_a -> task_b -> task_c"`

### `SprintSimulationEngine`

Entry point for sprint-planning Monte Carlo simulation.

Import path:

```python
from mcprojsim.planning.sprint_engine import SprintSimulationEngine
```

Constructor parameters:

- `iterations` (default: 10000)
- `random_seed`

Key method:

- `run(project: Project) -> SprintPlanningResults`

### `SprintPlanningResults`

Result model for sprint-planning simulations.

Import path:

```python
from mcprojsim.models.sprint_simulation import SprintPlanningResults
```

Useful properties:

- `project_name`: str
- `iterations`: int
- `mean`: float — mean total sprint count to completion
- `median`: float
- `std_dev`: float
- `percentiles`: dict[int, float] — sprint count per percentile
- `date_percentiles`: dict[int, date | None] — calendar dates per percentile
- `sprint_length_weeks`: float
- `planned_commitment_guidance`: float — recommended capacity units per sprint
- `historical_diagnostics`: dict — statistics from historical data (when available)
- `disruption_statistics`: dict — disruption event statistics
- `carryover_statistics`: dict — carryover (incomplete work) statistics
- `spillover_statistics`: dict — task spillover statistics
- `burnup_percentiles`: list[dict] — per-sprint cumulative work (percentiles)

Useful methods:

- **`percentile(p: int) -> float`** — total sprint count for a percentile
- **`date_percentile(p: int) -> date | None`** — calendar date for a percentile
- **`delivery_date_for_sprints(sprint_count: float) -> date | None`** — convert sprint count to calendar date
- **`to_dict() -> dict[str, Any]`** — serialize to dictionary

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

## Project Models

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
    print(f"Risk: {risk.name}, Probability: {risk.probability}")

# Check if sprint planning is configured
if project.sprint_planning and project.sprint_planning.enabled:
    print(f"Sprint length: {project.sprint_planning.sprint_length_weeks} weeks")
```

**Example: Building a Project Programmatically**

```python
from datetime import date
from mcprojsim.models.project import (
    Project, ProjectMetadata, Task, TaskEstimate, Risk,
)

project = Project(
    project=ProjectMetadata(
        name="My API Project",
        start_date=date(2026, 6, 1),
        hours_per_day=8.0,
    ),
    tasks=[
        Task(
            id="design",
            name="API Design",
            estimate=TaskEstimate(low=8, expected=16, high=32),
        ),
        Task(
            id="implement",
            name="Implementation",
            estimate=TaskEstimate(low=40, expected=80, high=160),
            dependencies=["design"],
        ),
        Task(
            id="test",
            name="Testing",
            estimate=TaskEstimate(t_shirt_size="M"),
            dependencies=["implement"],
        ),
    ],
    project_risks=[
        Risk(
            id="scope_creep",
            name="Scope Creep",
            probability=0.3,
            impact=40.0,
        ),
    ],
)
```

### `ProjectMetadata`

Stores top-level project settings and characteristics.

**Key fields:**

- `name`: str — Project name
- `description`: str | None — Optional project description
- `start_date`: date — Project start date
- `currency`: str | None — Currency for cost tracking (default: `"USD"`)
- `confidence_levels`: list[int] — Percentiles to include in reports (default: [10, 25, 50, 75, 80, 85, 90, 95, 99])
- `probability_red_threshold`: float — Probability threshold marking risk level (default: 0.5)
- `probability_green_threshold`: float — Probability threshold marking success (default: 0.9)
- `hours_per_day`: float — Working hours per day (default: 8.0)
- `distribution`: `DistributionType` — Default task duration distribution (default: `"triangular"`)
- `team_size`: int | None — Total team size (used for coordination overhead calculations and auto-generating resources)

**Example:**

```python
project = parser.parse_file("project.yaml")
meta = project.project

print(f"Project: {meta.name}")
print(f"Start: {meta.start_date}")
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
- `dependencies`: list[str] — List of task IDs this task depends on
- `uncertainty_factors`: `UncertaintyFactors | None` — Optional uncertainty adjustments
- `resources`: list[str] — Required resource names
- `max_resources`: int — Maximum number of resources that can be assigned (default: 1)
- `min_experience_level`: int — Minimum experience level required (1, 2, or 3; default: 1)
- `planning_story_points`: int | None — Story points override for sprint planning
- `priority`: int | None — Scheduling priority hint
- `spillover_probability_override`: float | None — Override for sprint spillover probability (0.0–1.0)
- `risks`: list[Risk] — Task-specific risks

**Key methods:**

- `has_dependency(task_id: str) -> bool` — Check if this task depends on another task
- `get_planning_story_points() -> int | None` — Return sprint-planning story points (falls back to `estimate.story_points`)

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

- `distribution`: `DistributionType | None` — Override the default distribution for this task
- `low`: float | None — Minimum hours (optimistic)
- `expected`: float | None — Best estimate in hours
- `high`: float | None — Maximum hours (pessimistic)
- `t_shirt_size`: str | None — Size token (e.g. `"XS"`, `"S"`, `"M"`, `"L"`, `"XL"`, `"XXL"`, or `"category.size"`)
- `story_points`: int | None — Story point value
- `unit`: `EffortUnit | None` — Effort unit (`"hours"`, `"days"`, `"weeks"`). Must not be set when using symbolic estimates (T-shirt or story points) — the unit comes from configuration.

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

- `id`: str — Unique risk identifier
- `name`: str — Human-readable risk name
- `probability`: float — Probability this risk occurs (0.0 to 1.0)
- `impact`: float | `RiskImpact` — Impact when risk happens (float is treated as hours)
- `description`: str | None — Optional description

**RiskImpact fields:**

- `type`: `ImpactType` — `"percentage"` or `"absolute"`
- `value`: float — Percentage (0–100) or absolute hours
- `unit`: `EffortUnit | None` — Unit only relevant for absolute impacts

**Risk methods:**

- `get_impact_value(base_duration: float = 0.0, hours_per_day: float = 8.0) -> float` — Calculate numeric impact in hours

**Example:**

```python
# Access project-level risks
for risk in project.project_risks:
    impact = risk.get_impact_value()
    print(f"Project risk: {risk.name}")
    print(f"  Probability: {risk.probability * 100:.0f}%")
    print(f"  Impact: {impact:.1f} hours")

# Access task-level risks
for task in project.tasks:
    for risk in task.risks:
        impact = risk.get_impact_value(base_duration=task.estimate.expected)
        print(f"Task {task.id} risk: {risk.name}")
        print(f"  Probability: {risk.probability * 100:.0f}%")
        print(f"  Impact: {impact:.1f} hours")
```

### `ResourceSpec`

Defines an individual resource (team member) that can be assigned to tasks.

**Key fields:**

- `name`: str | None — Resource name (e.g. `"Alice"`, `"Backend Developer"`). Auto-generated if omitted.
- `id`: str | None — Legacy identifier (used as fallback for `name`)
- `availability`: float — Fraction of time available (0.0–1.0, default: 1.0)
- `calendar`: str — Calendar identifier to use (default: `"default"`)
- `experience_level`: int — Skill level: 1 (junior), 2 (mid), or 3 (senior). Default: 2
- `productivity_level`: float — Productivity multiplier (0.1–2.0, default: 1.0)
- `sickness_prob`: float — Probability of absence per scheduling unit (0.0–1.0, default: 0.0)
- `planned_absence`: list[date] — Specific dates this resource is unavailable

**Example:**

```python
for resource in project.resources:
    print(f"Resource: {resource.name}")
    print(f"  Availability: {resource.availability * 100:.0f}%")
    print(f"  Experience level: {resource.experience_level}")
    print(f"  Calendar: {resource.calendar}")
    if resource.planned_absence:
        print(f"  Planned absence: {len(resource.planned_absence)} days")
```

### `CalendarSpec`

Defines a working calendar for scheduling.

**Key fields:**

- `id`: str — Calendar identifier (default: `"default"`)
- `work_hours_per_day`: float — Working hours per day (default: 8.0)
- `work_days`: list[int] — Working days of the week, where 1=Monday through 7=Sunday (default: `[1, 2, 3, 4, 5]`)
- `holidays`: list[date] — Specific non-working dates

**Example:**

```python
for calendar in project.calendars:
    print(f"Calendar: {calendar.id}")
    print(f"  Work hours/day: {calendar.work_hours_per_day}")
    print(f"  Work days: {calendar.work_days}")
    if calendar.holidays:
        print(f"  Holidays: {len(calendar.holidays)} days")
```

### `UncertaintyFactors`

Applies multipliers to adjust base task duration based on project characteristics.

**Supported fields:**

- `team_experience`: `"high"` | `"medium"` | `"low"`
- `requirements_maturity`: `"high"` | `"medium"` | `"low"`
- `technical_complexity`: `"low"` | `"medium"` | `"high"`
- `team_distribution`: `"colocated"` | `"distributed"`
- `integration_complexity`: `"low"` | `"medium"` | `"high"`

Each is optional; only specified factors affect the task estimate. The actual multiplier values are defined in `Config.uncertainty_factors`.

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

### Sprint Planning Models

These models define the sprint-planning input configuration. They are populated from the `sprint_planning:` block in a project YAML file.

#### `SprintPlanningSpec`

Top-level sprint planning configuration.

**Key fields:**

- `enabled`: bool — Whether sprint planning is active (default: `False`)
- `sprint_length_weeks`: int — Length of each sprint in weeks
- `capacity_mode`: `SprintCapacityMode` — `"story_points"` or `"tasks"`
- `history`: list[`SprintHistoryEntry`] — Historical sprint outcomes (minimum 2 usable rows required)
- `planning_confidence_level`: float — Confidence level for commitment guidance (0–1)
- `removed_work_treatment`: `RemovedWorkTreatment` — `"churn_only"` or `"reduce_backlog"`
- `future_sprint_overrides`: list[`FutureSprintOverrideSpec`] — Per-sprint capacity adjustments
- `volatility_overlay`: `SprintVolatilitySpec` — Sprint disruption model
- `spillover`: `SprintSpilloverSpec` — Task spillover model
- `velocity_model`: `SprintVelocityModel` — `"empirical"` or `"neg_binomial"`
- `sickness`: `SprintSicknessSpec` — Per-person sickness model

#### `SprintHistoryEntry`

One historical sprint outcome row.

**Key fields:**

- `sprint_id`: str — Unique identifier for this sprint
- `sprint_length_weeks`: int | None — Override sprint length (defaults to parent)
- `completed_story_points`: float | None — Story points completed (mutually exclusive with `completed_tasks`)
- `completed_tasks`: int | None — Tasks completed (mutually exclusive with `completed_story_points`)
- `spillover_story_points`: float — Unfinished story points carried over (default: 0)
- `spillover_tasks`: int — Unfinished tasks carried over (default: 0)
- `added_story_points` / `added_tasks`: float / int — Work added mid-sprint (default: 0)
- `removed_story_points` / `removed_tasks`: float / int — Work removed mid-sprint (default: 0)
- `holiday_factor`: float — Capacity adjustment for holidays (default: 1.0)
- `end_date`: date | None — Sprint end date
- `team_size`: int | None — Team size during this sprint
- `notes`: str | None — Free-text notes

#### `SprintVolatilitySpec`

Sprint-level disruption overlay (unexpected events reducing capacity).

**Key fields:**

- `enabled`: bool (default: `False`)
- `disruption_probability`: float — Probability of disruption per sprint
- `disruption_multiplier_low` / `disruption_multiplier_expected` / `disruption_multiplier_high`: float — Triangular distribution for capacity reduction

#### `SprintSpilloverSpec`

Task-level execution spillover model.

**Key fields:**

- `enabled`: bool (default: `False`)
- `model`: `SprintSpilloverModel` — `"table"` or `"logistic"`
- `size_reference_points`: float — Reference point size for scaling
- `size_brackets`: list[`SprintSpilloverBracketSpec`] — Table-model probability brackets
- `consumed_fraction_alpha` / `consumed_fraction_beta`: float — Beta distribution parameters for consumed fraction
- `logistic_slope` / `logistic_intercept`: float — Logistic model parameters

#### `SprintSicknessSpec`

Per-person sickness model for sprint capacity.

**Key fields:**

- `enabled`: bool (default: `False`)
- `team_size`: int | None — Override team size for sickness calculations
- `probability_per_person_per_week`: float — Sickness probability
- `duration_log_mu` / `duration_log_sigma`: float — Log-normal parameters for sickness duration

### Enums

The following enums are part of the model API:

- `DistributionType` — `"triangular"` or `"lognormal"`
- `ImpactType` — `"percentage"` or `"absolute"`
- `EffortUnit` — `"hours"`, `"days"`, or `"weeks"`
- `SprintCapacityMode` — `"story_points"` or `"tasks"`
- `SprintVelocityModel` — `"empirical"` or `"neg_binomial"`
- `SprintSpilloverModel` — `"table"` or `"logistic"`
- `RemovedWorkTreatment` — `"churn_only"` or `"reduce_backlog"`
- `ConstrainedSchedulingAssignmentMode` — `"greedy_single_pass"` or `"criticality_two_pass"`

## Simulation Results Models

### `SimulationResults`

Holds the complete output of a Monte Carlo simulation run, including all percentiles, critical path analysis, risk summaries, resource diagnostics, and per-task metrics.

**Key properties:**

- `project_name`: str — Name of the project that was simulated
- `iterations`: int — Number of iterations run
- `random_seed`: int | None — Seed used for reproducibility
- `hours_per_day`: float — Hours per calendar day
- `start_date`: date | None — Project start date (for delivery date calculations)
- `schedule_mode`: str — `"dependency_only"` or `"constrained"`
- `resource_constraints_active`: bool — Whether resource-constrained scheduling was used
- `mean`: float — Mean project duration (hours)
- `median`: float — Median project duration (hours)
- `std_dev`: float — Standard deviation of duration
- `min_duration`: float — Minimum observed duration
- `max_duration`: float — Maximum observed duration
- `skewness`: float — Skewness of the distribution
- `kurtosis`: float — Excess kurtosis of the distribution
- `percentiles`: dict[int, float] — Per-percentile duration (hours)
- `effort_percentiles`: dict[int, float] — Per-percentile total effort (person-hours)
- `effort_durations`: np.ndarray — Per-iteration total effort (project-wide)
- `sensitivity`: dict[str, float] — Per-task Spearman rank correlation with total duration
- `task_slack`: dict[str, float] — Mean schedule slack per task (hours)
- `max_parallel_tasks`: int — Peak parallel task count
- `resource_wait_time_hours`: float — Total wait time caused by resource unavailability
- `resource_utilization`: float — Average resource utilization (0.0–1.0)
- `calendar_delay_time_hours`: float — Hours lost to calendar constraints (weekends, holidays)
- `two_pass_trace`: `TwoPassDelta | None` — Traceability data when two-pass scheduling was enabled

**Key methods:**

- **`percentile(p: int) -> float`** — Get calendar duration for a specific percentile
- **`effort_percentile(p: int) -> float`** — Get total effort for a specific percentile
- **`probability_of_completion(target_hours: float) -> float`** — Calculate probability of finishing within a target duration
- **`hours_to_working_days(hours: float) -> int`** — Convert hours to working days (ceiling rounding)
- **`delivery_date(effort_hours: float) -> date | None`** — Convert project duration to a calendar date (skips weekends)
- **`get_critical_path() -> dict[str, float]`** — Per-task criticality index (0.0–1.0, frequency on critical path)
- **`get_critical_path_sequences(top_n: int | None = None) -> list[CriticalPathRecord]`** — Most frequent full paths (up to `top_n`)
- **`get_most_frequent_critical_path() -> CriticalPathRecord | None`** — Single most common critical path
- **`get_histogram_data(bins: int = 50) -> tuple[np.ndarray, np.ndarray]`** — Bin edges and counts for distribution visualization
- **`get_risk_impact_summary() -> dict[str, dict[str, float]]`** — Per-task risk triggering and impact statistics
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

## Exporters

All exporters support histogram data, critical-path output, sprint-planning results, and historic-base data (when available). The histogram bin count defaults to 50 but is controlled by `config.output.histogram_bins`.

### `JSONExporter`

Exports comprehensive results including all percentiles, statistics, histogram data, critical paths, risk summaries, and sprint-planning data to JSON.

**Method:**

- `export(results: SimulationResults, output_path: Path | str, config: Config | None = None, critical_path_limit: int | None = None, sprint_results: SprintPlanningResults | None = None, project: Project | None = None, include_historic_base: bool = False) -> None`

**Parameters:**

- `results` — Simulation results object
- `output_path` — File path for JSON output
- `config` — Active configuration (used for histogram bin count and other settings)
- `critical_path_limit` — Override number of critical paths to include (default from config)
- `sprint_results` — Sprint planning results (optional)
- `project` — Original project definition (optional; enables richer output)
- `include_historic_base` — Include historic baseline data if available

**Example:**

```python
from mcprojsim.exporters import JSONExporter

JSONExporter.export(
    results,
    "results.json",
    config=config,
    project=project,
    critical_path_limit=5,
    sprint_results=sprint_results,
)
```

### `CSVExporter`

Exports results as a CSV table format: metrics, percentiles, critical paths, histogram data, risk impact, resource diagnostics, and sprint data.

**Method:**

- `export(results: SimulationResults, output_path: Path | str, config: Config | None = None, critical_path_limit: int | None = None, sprint_results: SprintPlanningResults | None = None) -> None`

**Example:**

```python
from mcprojsim.exporters import CSVExporter

CSVExporter.export(results, "results.csv", config=config)
```

### `HTMLExporter`

Exports a formatted, interactive HTML report with thermometers, percentile tables, charts (using matplotlib), critical-path analysis, staffing recommendations, and sprint-planning traceability.

**Method:**

- `export(results: SimulationResults, output_path: Path | str, project: Project | None = None, config: Config | None = None, critical_path_limit: int | None = None, sprint_results: SprintPlanningResults | None = None, include_historic_base: bool = False) -> None`

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

These specialized analysis modules provide focused statistical, sensitivity, and staffing analysis capabilities beyond what `SimulationResults` provides directly.

### `StatisticalAnalyzer`

Convenience helpers for descriptive statistics on duration arrays.

Import:

```python
from mcprojsim.analysis.statistics import StatisticalAnalyzer
```

**Methods:**

- **`calculate_statistics(durations: np.ndarray) -> dict[str, float]`** — Returns mean, median, std_dev, min, max, coefficient of variation, skewness, excess kurtosis
- **`calculate_percentiles(durations: np.ndarray, percentiles: list[int]) -> dict[int, float]`** — Compute specific percentiles
- **`confidence_interval(durations: np.ndarray, confidence: float = 0.95) -> tuple[float, float]`** — Return lower/upper bounds for a confidence interval

### `SensitivityAnalyzer`

Analyzes which tasks have the strongest correlation with total project duration (Spearman rank correlation).

Import:

```python
from mcprojsim.analysis.sensitivity import SensitivityAnalyzer
```

**Methods:**

- **`calculate_correlations(results: SimulationResults) -> dict[str, float]`** — Per-task correlation with total duration
- **`get_top_contributors(results: SimulationResults, n: int = 10) -> list[tuple[str, float]]`** — Top N tasks by sensitivity

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

- **`get_criticality_index(results: SimulationResults) -> dict[str, float]`** — Same as `results.get_critical_path()`
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

**`StaffingRow` fields:**

- `profile`: str — Experience level name
- `team_size`: int — Candidate team size
- `individual_productivity`: float — Per-person productivity after overhead
- `effective_capacity`: float — Total effective team capacity
- `calendar_hours`: float — Total hours of calendar time needed
- `calendar_working_days`: int — Calendar days needed
- `delivery_date`: date | None — Projected delivery date
- `efficiency`: float — Effective capacity vs nominal team size

**`StaffingRecommendation` fields:**

- `profile`: str — Experience level name (e.g., `"senior"`, `"mixed"`, `"junior"`)
- `recommended_team_size`: int — Primary recommendation
- `total_effort_hours`: float — Total effort basis
- `critical_path_hours`: float — Critical path duration
- `calendar_working_days`: int — Calendar days needed
- `delivery_date`: date | None — Scheduled completion
- `efficiency`: float — Effective capacity vs nominal team size
- `parallelism_ratio`: float — Ratio of total effort to critical-path duration
- `effort_basis`: str — Effort basis label (`"mean"` or a percentile label such as `"p80"`)

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

- **`validate_file(file_path: str | Path) -> tuple[bool, str]`** — Returns (is_valid, error_message). Auto-selects parser based on file extension.

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

- **`setup_logging(level: str = "INFO") -> logging.Logger`** — Returns configured logger with specified level (`"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`, `"CRITICAL"`)

**Example:**

```python
logger = setup_logging(level="INFO")
# Library logging now routes to this logger
```

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

- `ParsedProject` — extracted project-level data (`name`, `start_date`, `description`, `hours_per_day`, `tasks`, `confidence_levels`, `resources`, `calendars`, `sprint_planning`)
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

### Example 2: Resource-Constrained and Two-Pass Scheduling

This example shows how to enable resource-constrained scheduling and two-pass mode:

```python
from datetime import date
from mcprojsim import SimulationEngine
from mcprojsim.config import Config
from mcprojsim.models.project import (
    Project, ProjectMetadata, Task, TaskEstimate,
    ResourceSpec, CalendarSpec,
)

# Define resources and calendars
project = Project(
    project=ProjectMetadata(
        name="Constrained Project",
        start_date=date(2026, 6, 1),
    ),
    tasks=[
        Task(
            id="task_a",
            name="Backend work",
            estimate=TaskEstimate(low=20, expected=40, high=80),
            resources=["dev_team"],
        ),
        Task(
            id="task_b",
            name="Frontend work",
            estimate=TaskEstimate(low=16, expected=32, high=64),
            resources=["dev_team"],
        ),
        Task(
            id="task_c",
            name="Integration",
            estimate=TaskEstimate(low=8, expected=16, high=32),
            dependencies=["task_a", "task_b"],
            resources=["dev_team"],
        ),
    ],
    resources=[
        ResourceSpec(name="dev_team", availability=1.0, experience_level=3),
        ResourceSpec(name="dev_team", availability=0.8, experience_level=2),
    ],
    calendars=[
        CalendarSpec(
            id="default",
            work_hours_per_day=8.0,
            work_days=[1, 2, 3, 4, 5],
            holidays=[date(2026, 7, 4)],
        ),
    ],
)

config = Config.get_default()

# Run with two-pass scheduling for better resource prioritization
engine = SimulationEngine(
    iterations=10000,
    random_seed=42,
    config=config,
    two_pass=True,
    pass1_iterations=2000,
)
results = engine.run(project)

print(f"Schedule mode: {results.schedule_mode}")
print(f"Resource utilization: {results.resource_utilization*100:.1f}%")
print(f"Resource wait time: {results.resource_wait_time_hours:.1f} hours")

if results.two_pass_trace and results.two_pass_trace.enabled:
    delta = results.two_pass_trace
    print(f"Two-pass P50 improvement: {delta.delta_p50_hours:+.1f} hours")
```

### Example 3: Dashboard Integration

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

### Example 4: Sprint Planning with Forecast

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

### Example 5: Batch Processing Multiple Projects

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

### Example 6: Configuration-Driven Customization

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
