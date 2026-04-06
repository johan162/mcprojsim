
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
