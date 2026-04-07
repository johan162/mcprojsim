
# Analysis Helpers

## Overview

The `analysis` package provides four post-processing analyzers that extract deeper insights from a completed `SimulationResults` object. `StatisticalAnalyzer` computes descriptive statistics and confidence intervals; `SensitivityAnalyzer` ranks tasks by their Spearman rank correlation with total project duration; `CriticalPathAnalyzer` surfaces task criticality indices and the most frequent end-to-end critical sequences; and `StaffingAnalyzer` recommends team sizes using a Brooks's Law–inspired communication-overhead model.

**When to use this module:** Use these analyzers when you need custom thresholds, deeper statistical breakdowns, or want to integrate simulation insights into your own tooling beyond what the CLI output provides.

| Capability | Description |
|---|---|
| Descriptive statistics | Mean, median, std dev, CV, min/max on any duration array |
| Percentile calculation | Arbitrary percentile queries on simulation output |
| Confidence intervals | Bootstrap confidence interval at configurable confidence level |
| Sensitivity ranking | Spearman rank correlation of each task's duration against total project duration |
| Critical-path analysis | Per-task criticality index (0–1) and most frequent full path sequences |
| Staffing recommendations | Team-size vs. delivery-date trade-offs across senior/mixed/junior profiles |

**Background: Spearman rank correlation** — `SensitivityAnalyzer` converts each task's sampled durations and the total project durations to ranks before computing the correlation coefficient, making it robust to non-normal distributions and outliers. A coefficient near 1.0 means that task's duration strongly drives the overall schedule.

**Background: Communication overhead** — `StaffingAnalyzer` models individual productivity as `max(min_prod, 1 − c·(n−1))`, inspired by Brooks's Law, so adding team members beyond an optimal point yields diminishing and eventually negative returns on elapsed calendar time.

**Imports:**
```python
from mcprojsim.analysis.statistics import StatisticalAnalyzer
from mcprojsim.analysis.sensitivity import SensitivityAnalyzer
from mcprojsim.analysis.critical_path import CriticalPathAnalyzer
from mcprojsim.analysis.staffing import StaffingAnalyzer
```

These specialized analysis modules provide focused statistical, sensitivity, and staffing analysis capabilities beyond what `SimulationResults` provides directly.

## `StatisticalAnalyzer`

Convenience helpers for descriptive statistics on duration arrays.

Import:

```python
from mcprojsim.analysis.statistics import StatisticalAnalyzer
```

**Methods:**

- **`calculate_statistics(durations: np.ndarray) -> dict[str, float]`** — Returns `mean`, `median`, `std_dev`, `variance`, `min`, `max`, `range`, `coefficient_of_variation`
- **`calculate_percentiles(durations: np.ndarray, percentiles: list[int]) -> dict[int, float]`** — Compute specific percentiles
- **`confidence_interval(durations: np.ndarray, confidence: float = 0.95) -> tuple[float, float]`** — Return lower/upper bounds for a confidence interval

## `SensitivityAnalyzer`

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

## `CriticalPathAnalyzer`

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

## `StaffingAnalyzer`

Provides team-size recommendations and breaks down staffing by experience profile.

Import:

```python
from mcprojsim.analysis.staffing import StaffingAnalyzer
```

**Methods:**

- **`individual_productivity(team_size: int, communication_overhead: float, min_productivity: float) -> float`** — Per-person productivity for a given team size. Returns a value in `[min_productivity, 1.0]`.
- **`effective_capacity(team_size: int, communication_overhead: float, productivity_factor: float, min_productivity: float) -> float`** — Effective person-equivalents for a sized team, accounting for communication overhead and experience-level multiplier.
- **`calendar_hours(total_effort: float, critical_path_hours: float, team_size: int, communication_overhead: float, productivity_factor: float, min_productivity: float, hours_per_day: float) -> float`** — Elapsed calendar hours for a team. Bounded below by `critical_path_hours` regardless of team size.
- **`calculate_staffing_table(results: SimulationResults, config: Config) -> list[StaffingRow]`** — Full table of `StaffingRow` objects for every team size from 1 up to the observed peak parallelism, for each experience profile.
- **`recommend_team_size(results: SimulationResults, config: Config) -> list[StaffingRecommendation]`** — One optimal `StaffingRecommendation` per experience profile (the team size with the shortest calendar duration).

**`StaffingRow` fields:**

| Field | Type | Description |
|---|---|---|
| `profile` | `str` | Experience level name |
| `team_size` | `int` | Candidate team size |
| `individual_productivity` | `float` | Per-person productivity after communication overhead |
| `effective_capacity` | `float` | Total effective team capacity in person-equivalents |
| `calendar_hours` | `float` | Elapsed calendar hours needed |
| `calendar_working_days` | `int` | Calendar working days needed |
| `delivery_date` | `date \| None` | Projected delivery date |
| `efficiency` | `float` | Calendar-time optimality: 1.0 means this team size achieves the minimum calendar duration for its profile |

**`StaffingRecommendation` fields:**

| Field | Type | Description |
|---|---|---|
| `profile` | `str` | Experience level name (e.g. `"senior"`, `"mixed"`, `"junior"`) |
| `recommended_team_size` | `int` | Optimal team size (minimum calendar duration) |
| `total_effort_hours` | `float` | Total effort basis in person-hours |
| `critical_path_hours` | `float` | Critical-path elapsed hours (lower bound on calendar time) |
| `calendar_working_days` | `int` | Calendar working days needed |
| `delivery_date` | `date \| None` | Projected delivery date |
| `efficiency` | `float` | Always `1.0` — the recommended size is by definition the calendar-optimal team for its profile |
| `parallelism_ratio` | `float` | Ratio of total effort to critical-path duration (degree of parallelism) |
| `effort_basis` | `str` | Effort basis label (`"mean"` or a percentile label such as `"P80"`) |

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

