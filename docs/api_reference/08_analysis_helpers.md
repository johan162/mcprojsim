
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

