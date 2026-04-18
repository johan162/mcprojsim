
# Core API

## Overview

`SimulationEngine` is the central entry point for running Monte Carlo simulations in mcprojsim. It samples task durations (triangular or lognormal), evaluates risks, delegates scheduling to `TaskScheduler`, and aggregates thousands of iterations into a `SimulationResults` object containing duration arrays, percentiles, and critical-path data. The scheduler supports two modes: a fast dependency-only topological sort, and a resource-calendar-constrained mode with optional two-pass criticality prioritisation.

**When to use this module:** Use it whenever you want to run a simulation programmatically — whether from a parsed YAML project or one built in code.

| Capability | Description |
|---|---|
| Monte Carlo sampling | Runs `iterations` independent samples via triangular or shifted-lognormal distributions |
| Dependency scheduling | Topological ordering of tasks respecting `depends_on` chains |
| Resource-constrained scheduling | Assigns named resources with availability, calendars, and experience modifiers |
| Two-pass criticality mode | Pass 1 builds criticality indices with greedy dispatch; Pass 2 replays with criticality-prioritised assignment |
| Risk evaluation | Applies project and task-level risks (percentage or absolute) per iteration |
| Reproducibility | Flows all randomness through a seeded `numpy.random.RandomState` |

**Background: Monte Carlo project simulation** — Each iteration independently samples every task duration and risk event, then schedules tasks to compute a total elapsed project duration. Repeating this thousands of times yields a distribution from which percentiles (P50, P80, P95, etc.) and critical-path frequencies are derived.

**Imports:**
```python
from mcprojsim import SimulationEngine
from mcprojsim.simulation.engine import SimulationCancelled
from mcprojsim.models.simulation import SimulationResults
```

## `SimulationEngine`

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

**Constructor parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `iterations` | `int` | `10000` | Number of Monte Carlo iterations to run. |
| `random_seed` | `int \| None` | `None` | Random seed for reproducible sampling. |
| `config` | `Config \| None` | `None` | Configuration for uncertainty multipliers, T-shirt mappings, and story-point mappings. Uses `Config.get_default()` when omitted. |
| `show_progress` | `bool` | `True` | Print progress updates during long runs. |
| `two_pass` | `bool` | `False` | Enable criticality-two-pass scheduling. Only has effect when resource-constrained scheduling is active. Overrides `config.constrained_scheduling.assignment_mode`. |
| `pass1_iterations` | `int \| None` | `None` | Number of pass-1 iterations for criticality ranking. Overrides `config.constrained_scheduling.pass1_iterations` when provided. Capped to `iterations`. |
| `progress_callback` | `Callable[[int, int], None] \| None` | `None` | Optional callback invoked with `(completed_iterations, total_iterations)` during the run. When provided, stdout progress output is suppressed regardless of the `show_progress` flag. Sequential runs report at the built-in 10 % buckets; parallel runs report as chunks complete, so callback frequency can be higher. See [Example 7](./11_api_examples.md#example-7-progress-callback-and-cancellation) for usage. |
| `workers` | `int` | `1` | Number of worker processes for parallel simulation. `1` uses the sequential path (default and recommended for library/MCP callers). Values > 1 distribute iterations across a short-lived `ProcessPoolExecutor` using the `spawn` start method. The engine falls back to the sequential path when `iterations < 500` or `len(project.tasks) < 5`. |

**Key methods:**

- `run(project: Project) -> SimulationResults` — Run the Monte Carlo simulation and return aggregated results. When two-pass mode is active and resource constraints are present, the engine first runs `pass1_iterations` with greedy scheduling to build criticality indices, then reruns the full simulation with criticality-prioritised dispatch. Raises `SimulationCancelled` if `cancel()` was called before or during the run.
- `cancel() -> None` — Request cancellation of a running simulation. The engine checks an internal flag at the top of each iteration; when set, the current `run()` call raises `SimulationCancelled`. This method is thread-safe: call it from any thread to stop a simulation running in another.

## `SimulationCancelled`

Exception raised when a running simulation is cancelled via `SimulationEngine.cancel()`.

```python
from mcprojsim.simulation.engine import SimulationCancelled
```

`SimulationCancelled` is a plain `Exception` subclass with no additional attributes. Catch it to distinguish user-initiated cancellation from other errors:

```python
try:
    results = engine.run(project)
except SimulationCancelled:
    print("Simulation was cancelled by the user.")
```

## `SimulationResults`

Holds the output of a simulation run, including durations, summary statistics, percentiles, and critical-path frequency data.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `project_name` | `str` | Name of the simulated project. |
| `iterations` | `int` | Number of iterations used. |
| `random_seed` | `int \| None` | Seed that was used, or `None`. |
| `hours_per_day` | `float` | Working hours per day (used for day conversions). |
| `start_date` | `date \| None` | Project start date, if provided. |
| `durations` | `np.ndarray` | Per-iteration elapsed project durations in hours. |
| `task_durations` | `dict[str, np.ndarray]` | Per-iteration sampled duration arrays keyed by task ID. |
| `effort_durations` | `np.ndarray` | Per-iteration total person-effort in hours (sum across all tasks). |
| `mean` | `float` | Mean elapsed duration in hours. |
| `median` | `float` | Median elapsed duration in hours. |
| `std_dev` | `float` | Standard deviation of elapsed durations. |
| `min_duration` | `float` | Minimum elapsed duration observed. |
| `max_duration` | `float` | Maximum elapsed duration observed. |
| `skewness` | `float` | Skewness of the duration distribution. |
| `kurtosis` | `float` | Excess kurtosis of the duration distribution. |
| `percentiles` | `dict[int, float]` | Cached elapsed-duration percentiles (populated on demand). |
| `effort_percentiles` | `dict[int, float]` | Cached effort percentiles (populated on demand). |
| `sensitivity` | `dict[str, float]` | Per-task Spearman rank correlations with total elapsed duration. |
| `task_slack` | `dict[str, float]` | Mean schedule slack per task in hours. |
| `max_parallel_tasks` | `int` | Peak parallel task count observed across all iterations. |
| `schedule_mode` | `str` | `"dependency_only"` or `"resource_constrained"`. |
| `resource_constraints_active` | `bool` | Whether resource-constrained scheduling was used. |
| `resource_wait_time_hours` | `float` | Mean hours tasks waited for a resource slot. |
| `resource_utilization` | `float` | Average resource utilization (0.0–1.0). |
| `calendar_delay_time_hours` | `float` | Mean hours lost to calendar constraints. |
| `two_pass_trace` | `TwoPassDelta \| None` | Pass-1 vs pass-2 comparison payload; `None` unless two-pass mode was active. |

**Methods:**

- `calculate_statistics()` — Compute and cache mean, median, std\_dev, min, max, skewness, and kurtosis from the `durations` array.
- `percentile(p: int) -> float` — Elapsed-duration value at percentile *p*.
- `effort_percentile(p: int) -> float` — Total person-effort value at percentile *p*.
- `get_critical_path() -> dict[str, float]` — Per-task criticality index (fraction of iterations in which the task was on the critical path).
- `get_critical_path_sequences(top_n: int | None = None) -> list[CriticalPathRecord]` — Ordered full critical-path sequences by frequency.
- `get_most_frequent_critical_path() -> CriticalPathRecord | None` — Single most frequent full path sequence.
- `get_histogram_data(bins: int = 50) -> tuple[np.ndarray, np.ndarray]` — Returns `(bin_edges, counts)` for visualisation.
- `probability_of_completion(target_hours: float) -> float` — Fraction of iterations that completed within the given hours.
- `total_effort_hours() -> float` — Sum of per-task mean durations (total person-hours regardless of parallelism).
- `hours_to_working_days(hours: float) -> int` — Convert hours to working days (ceiling).
- `delivery_date(effort_hours: float) -> date | None` — Project delivery date by adding working days to `start_date`; `None` if no start date.
- `get_risk_impact_summary() -> dict[str, dict[str, float]]` — Per-task risk impact statistics (`mean_impact`, `trigger_rate`, `mean_when_triggered`).
- `to_dict() -> dict[str, Any]` — Serialise results to a plain dictionary.

```python
print(f"Mean: {results.mean:.2f}")
print(f"Median: {results.median:.2f}")
print(f"P80: {results.percentile(80):.2f}")

criticality = results.get_critical_path()
for task_id, value in criticality.items():
    print(task_id, value)
```

## `CriticalPathRecord`

Aggregated full critical path sequence information.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `path` | `tuple[str, ...]` | Ordered task IDs forming the path. |
| `count` | `int` | Number of iterations this exact path appeared. |
| `frequency` | `float` | Fraction of total iterations (0.0–1.0). |

**Methods:**

- `format_path() -> str` — returns `"task_a -> task_b -> task_c"`

## `TwoPassDelta`

Traceability payload for two-pass constrained scheduling. Populated in `SimulationResults.two_pass_trace` when `two_pass=True`.

Import path:

```python
from mcprojsim.models.simulation import TwoPassDelta
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | `bool` | Whether two-pass scheduling was active. |
| `pass1_iterations` | `int` | Number of iterations run in pass 1. |
| `pass2_iterations` | `int` | Number of iterations run in pass 2. |
| `ranking_method` | `str` | Criticality ranking method used (e.g. `"criticality_index"`). |
| `pass1_mean_hours` | `float` | Pass-1 mean elapsed duration in hours. |
| `pass1_p50_hours` / `pass1_p80_hours` / `pass1_p90_hours` / `pass1_p95_hours` | `float` | Pass-1 percentile durations. |
| `pass1_resource_wait_hours` | `float` | Pass-1 mean resource wait time. |
| `pass1_resource_utilization` | `float` | Pass-1 mean resource utilization. |
| `pass1_calendar_delay_hours` | `float` | Pass-1 mean calendar delay. |
| `pass2_*` | `float` | Same fields for pass 2 (full run). |
| `delta_*` | `float` | Pass-2 minus pass-1 delta (negative = improvement). |
| `task_criticality_index` | `dict[str, float]` | Per-task criticality index from pass 1. |

**Methods:**

- `to_dict() -> dict[str, Any]` — Serialise the trace payload to a plain dictionary.

## `SprintSimulationEngine`

Entry point for sprint-planning Monte Carlo simulation.

Import path:

```python
from mcprojsim.planning.sprint_engine import SprintSimulationEngine
```

**Constructor parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `iterations` | `int` | `10000` | Number of Monte Carlo iterations. |
| `random_seed` | `int \| None` | `None` | Random seed for reproducible sampling. |

**Key method:**

- `run(project: Project) -> SprintPlanningResults` — Run the sprint-planning simulation. Raises `ValueError` if `project.sprint_planning` is not enabled.

## `SprintPlanningResults`

Result model for sprint-planning simulations.

Import path:

```python
from mcprojsim.models.sprint_simulation import SprintPlanningResults
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `project_name` | `str` | Name of the simulated project. |
| `iterations` | `int` | Number of iterations used. |
| `random_seed` | `int \| None` | Seed that was used, or `None`. |
| `sprint_counts` | `np.ndarray` | Per-iteration sprint-count samples. |
| `sprint_length_weeks` | `int` | Duration of each sprint in weeks. |
| `mean` | `float` | Mean total sprint count to completion. |
| `median` | `float` | Median sprint count. |
| `std_dev` | `float` | Standard deviation of sprint counts. |
| `min_sprints` | `float` | Minimum sprint count observed. |
| `max_sprints` | `float` | Maximum sprint count observed. |
| `percentiles` | `dict[int, float]` | Sprint count per percentile (populated on demand). |
| `date_percentiles` | `dict[int, date \| None]` | Calendar dates per percentile (populated on demand). |
| `planned_commitment_guidance` | `float` | Recommended capacity units per sprint. |
| `historical_diagnostics` | `dict` | Statistics derived from historical velocity data (when provided). |
| `disruption_statistics` | `dict` | Disruption event statistics. |
| `carryover_statistics` | `dict` | Carryover (incomplete work) statistics. |
| `spillover_statistics` | `dict` | Task spillover statistics. |
| `burnup_percentiles` | `list[dict]` | Per-sprint cumulative work by percentile. |

**Methods:**

- `percentile(p: int) -> float` — Total sprint count at percentile *p*.
- `date_percentile(p: int) -> date | None` — Calendar date for a sprint-count percentile.
- `delivery_date_for_sprints(sprint_count: float) -> date | None` — Convert a sprint count to a projected delivery date.
- `to_dict() -> dict[str, Any]` — Serialise results to a plain dictionary.

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
    print(f"Historical velocity: mean {hist.get('series_statistics', {}).get('completed_units', {}).get('mean', 0):.1f}")
    print(f"Historical observations: {hist.get('observation_count', 0)}")
```
