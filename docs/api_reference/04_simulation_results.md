
# Simulation Results Models

## Overview

`mcprojsim.models.simulation` holds the output models produced by `SimulationEngine` after a Monte Carlo run. `SimulationResults` stores numpy arrays of per-iteration elapsed project durations alongside aggregated statistics, per-task metrics, and critical-path data. A key design distinction is that `durations` represents *elapsed* project time (critical-path length), while `effort_durations` represents *total person-effort* (the sum of all task durations per iteration) — these differ whenever tasks run in parallel.

**When to use this module:** Access it directly when reading simulation output, computing custom percentiles, querying critical-path sequences, or serialising results to JSON/CSV via `to_dict()`.

| Capability | Description |
|---|---|
| Elapsed duration percentiles | `percentile(p)` queries `durations` (critical-path hours) at any percentile |
| Total effort percentiles | `effort_percentile(p)` queries `effort_durations` (person-hours) at any percentile |
| Critical-path task frequency | `get_critical_path()` returns each task's criticality index (0–1) across iterations |
| Full path sequences | `get_critical_path_sequences()` returns ordered `CriticalPathRecord` objects by frequency |
| Delivery date projection | `delivery_date(hours)` adds working days to `start_date`, skipping weekends |
| Serialisation | `to_dict()` converts the full result to a nested plain dictionary for export |

**Background: Elapsed duration vs. total effort** — Monte Carlo simulation samples each task's duration stochastically. The *elapsed* project duration is the critical-path length (tasks that cannot run in parallel). *Total effort* is the arithmetic sum of all task durations and represents person-hours of work. When tasks run in parallel, elapsed < total effort; keeping both arrays enables accurate both schedule and staffing estimates.

**Imports:**
```python
from mcprojsim.models.simulation import SimulationResults, CriticalPathRecord, TwoPassDelta
```

---

## `CriticalPathRecord`

Represents one aggregated critical-path sequence across all simulation iterations.

| Field | Type | Description |
|-------|------|-------------|
| `path` | `tuple[str, ...]` | Ordered sequence of task IDs forming the critical path |
| `count` | `int` | Number of iterations this exact path was observed |
| `frequency` | `float` | Fraction of all iterations (0.0–1.0) this path appeared |

**Method:** `format_path() -> str` — Returns the path as a human-readable arrow-separated string (e.g. `"task_a -> task_b -> task_c"`).

---

## `TwoPassDelta`

Traceability payload produced when the `criticality_two_pass` scheduling mode is active. Stores pass-1 baseline statistics, pass-2 full-run statistics, and the deltas between them.

**Pass metadata:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `False` | Whether two-pass scheduling was active |
| `pass1_iterations` | `int` | `0` | Number of pass-1 (baseline) iterations run |
| `pass2_iterations` | `int` | `0` | Number of pass-2 (priority-ranked) iterations run |
| `ranking_method` | `str` | `"criticality_index"` | Method used to rank tasks between passes |
| `task_criticality_index` | `dict[str, float]` | `{}` | Per-task criticality index computed in pass-1 |

**Pass-1 aggregate statistics:**

| Field | Type | Default |
|-------|------|---------|
| `pass1_mean_hours` | `float` | `0.0` |
| `pass1_p50_hours` | `float` | `0.0` |
| `pass1_p80_hours` | `float` | `0.0` |
| `pass1_p90_hours` | `float` | `0.0` |
| `pass1_p95_hours` | `float` | `0.0` |
| `pass1_resource_wait_hours` | `float` | `0.0` |
| `pass1_resource_utilization` | `float` | `0.0` |
| `pass1_calendar_delay_hours` | `float` | `0.0` |

**Pass-2 aggregate statistics** (same shape; prefix `pass2_`):
`pass2_mean_hours`, `pass2_p50_hours`, `pass2_p80_hours`, `pass2_p90_hours`, `pass2_p95_hours`, `pass2_resource_wait_hours`, `pass2_resource_utilization`, `pass2_calendar_delay_hours`

**Deltas (pass-2 minus pass-1; negative = improvement)**:
`delta_mean_hours`, `delta_p50_hours`, `delta_p80_hours`, `delta_p90_hours`, `delta_p95_hours`, `delta_resource_wait_hours`, `delta_resource_utilization`, `delta_calendar_delay_hours`

**Method:** `to_dict() -> dict[str, Any]` — Serialize the traceability payload to a nested dictionary.

---

## `SimulationResults`

Holds the complete output of a Monte Carlo simulation run, including all percentiles, critical path analysis, risk summaries, resource diagnostics, and per-task metrics.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `project_name` | `str` | required | Name of the project that was simulated |
| `iterations` | `int` | required | Number of iterations run |
| `durations` | `np.ndarray` | required | Per-iteration elapsed project duration in hours (the main simulation output array) |
| `task_durations` | `dict[str, np.ndarray]` | `{}` | Per-task duration arrays (task ID → per-iteration values) |
| `critical_path_frequency` | `dict[str, int]` | `{}` | Raw count of iterations each task appeared on the critical path |
| `critical_path_sequences` | `list[CriticalPathRecord]` | `[]` | Full ordered critical-path sequences in descending frequency order |
| `random_seed` | `int \| None` | `None` | Seed used for reproducibility |
| `probability_red_threshold` | `float` | `0.5` | Probability below which delivery is shown as red |
| `probability_green_threshold` | `float` | `0.9` | Probability above which delivery is shown as green |
| `hours_per_day` | `float` | `8.0` | Working hours per calendar day |
| `start_date` | `date \| None` | `None` | Project start date (for delivery date calculations) |
| `sensitivity` | `dict[str, float]` | `{}` | Per-task Spearman rank correlation with total duration |
| `task_slack` | `dict[str, float]` | `{}` | Mean schedule slack per task (hours) across all iterations |
| `max_parallel_tasks` | `int` | `0` | Peak parallel task count observed across all iterations |
| `schedule_mode` | `str` | `"dependency_only"` | `"dependency_only"` or `"constrained"` |
| `resource_constraints_active` | `bool` | `False` | Whether resource-constrained scheduling was used |
| `resource_wait_time_hours` | `float` | `0.0` | Total wait time caused by resource unavailability |
| `resource_utilization` | `float` | `0.0` | Average resource utilization (0.0–1.0) |
| `calendar_delay_time_hours` | `float` | `0.0` | Hours lost to calendar constraints (weekends, holidays) |
| `risk_impacts` | `dict[str, np.ndarray]` | `{}` | Per-task risk impact arrays (task ID → per-iteration impact in hours) |
| `project_risk_impacts` | `np.ndarray` | `[]` | Per-iteration project-level risk impacts in hours |
| `effort_durations` | `np.ndarray` | `[]` | Per-iteration total person-effort (sum of all task durations); differs from `durations` which is elapsed time |
| `two_pass_trace` | `TwoPassDelta \| None` | `None` | Traceability data when two-pass scheduling was used |
| `mean` | `float` | `0.0` | Mean elapsed project duration (hours) |
| `median` | `float` | `0.0` | Median elapsed project duration (hours) |
| `std_dev` | `float` | `0.0` | Standard deviation of elapsed duration |
| `min_duration` | `float` | `0.0` | Minimum observed elapsed duration |
| `max_duration` | `float` | `0.0` | Maximum observed elapsed duration |
| `skewness` | `float` | `0.0` | Skewness of the duration distribution |
| `kurtosis` | `float` | `0.0` | Excess kurtosis of the duration distribution |
| `percentiles` | `dict[int, float]` | `{}` | Pre-computed elapsed duration percentiles (hours) |
| `effort_percentiles` | `dict[int, float]` | `{}` | Pre-computed total effort percentiles (person-hours) |

> **Elapsed duration vs. total effort:** `durations` and `mean`/`percentiles` represent the *elapsed* project timeline (critical-path time, accounting for parallelism). `effort_durations` and `effort_percentiles` represent the total *person-hours* of work across all tasks — this will always be ≥ the elapsed duration when tasks run in parallel.

**Key methods:**

- **`calculate_statistics() -> None`** — Populate `mean`, `median`, `std_dev`, `min_duration`, `max_duration`, `skewness`, and `kurtosis` from `durations`. Called automatically by `SimulationEngine` after the run.
- **`percentile(p: int) -> float`** — Get elapsed duration for a specific percentile
- **`effort_percentile(p: int) -> float`** — Get total effort for a specific percentile (falls back to `total_effort_hours()` when per-iteration effort data is unavailable)
- **`probability_of_completion(target_hours: float) -> float`** — Calculate probability of finishing within a target duration
- **`hours_to_working_days(hours: float) -> int`** — Convert hours to working days (ceiling rounding)
- **`delivery_date(effort_hours: float) -> date | None`** — Convert elapsed duration to a calendar date (skips weekends; returns `None` if `start_date` is unset)
- **`get_critical_path() -> dict[str, float]`** — Per-task criticality index (0.0–1.0, frequency on critical path), derived from `critical_path_frequency`
- **`get_critical_path_sequences(top_n: int | None = None) -> list[CriticalPathRecord]`** — Most frequent full paths (up to `top_n`)
- **`get_most_frequent_critical_path() -> CriticalPathRecord | None`** — Single most common critical path
- **`get_histogram_data(bins: int = 50) -> tuple[np.ndarray, np.ndarray]`** — Bin edges and counts for distribution visualization
- **`get_risk_impact_summary() -> dict[str, dict[str, float]]`** — Per-task risk triggering and impact statistics (`mean_impact`, `trigger_rate`, `mean_when_triggered`)
- **`total_effort_hours() -> float`** — Sum of per-task mean durations (total person-hours)
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

