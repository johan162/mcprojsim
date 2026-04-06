
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

