# Monte Carlo Project Simulator (mcprojsim) — Requirements & Implementation Specification

> **Purpose**: This document specifies the complete functional and non-functional requirements
> for `mcprojsim`, a Monte Carlo simulation tool for software project schedule, effort, and
> cost estimation. It is written with sufficient detail that a competent engineering team
> could recreate the system from scratch in any programming language.

---

## 1. Introduction

### 1.1 Purpose

mcprojsim uses Monte Carlo simulation to produce probabilistic schedule, effort, and cost
estimates for software projects. Given a set of tasks with uncertain duration estimates,
dependency relationships, optional resource constraints, risk events, and cost parameters,
the tool runs thousands of simulated project executions and reports statistical distributions
of outcomes.

### 1.2 Scope

The system provides:
- **Schedule estimation**: Elapsed calendar-time project duration with confidence intervals
- **Effort estimation**: Total person-hours of work (independent of parallelism)
- **Cost estimation**: Labor + fixed + risk-triggered monetary costs with budget confidence
- **Sprint planning**: Monte Carlo forecasting of sprint count to completion
- **Sensitivity analysis**: Which tasks drive schedule uncertainty
- **Critical path analysis**: Which task chains are most frequently schedule-critical
- **Staffing analysis**: Optimal team size recommendations using Brooks's Law model
- **Resource-constrained scheduling**: Calendar-aware scheduling with sickness and absence
- **Multiple input modes**: YAML project files, TOML, natural language descriptions, MCP server

### 1.3 Key Design Principles

1. **Reproducibility**: Given the same seed, produce identical results
2. **Configuration over code**: All tuning parameters externalized to config
3. **Progressive complexity**: Simple projects need only tasks; advanced features are opt-in
4. **Separation of concerns**: Parsing → Modeling → Simulation → Analysis → Export
5. **Strict validation**: Catch errors early with location-aware error messages

---

## 2. Functional Requirements

### 2.1 Core Simulation (FR-001 through FR-025)

#### FR-001: Project File Parsing
The system SHALL parse project specifications from YAML and TOML formats. The parser
SHALL produce location-aware error messages including line numbers for validation failures.

**Implementation notes:**
- YAML parser tracks line numbers using a custom loader that annotates each node
- Unknown/unrecognized fields cause validation errors (strict mode)
- Field aliases are supported in the Pydantic model layer (e.g., `min` → `low`, `max` → `high`,
  `most_likely` → `expected`) but the YAML parser itself does not perform alias mapping;
  aliases only work when data passes through Pydantic model construction

#### FR-002: Three-Point Estimation
The system SHALL accept three-point estimates (low, expected, high) for each task and
sample durations from either a triangular or shifted log-normal distribution.

**Triangular distribution:**
- Direct sampling: `numpy.random.triangular(low, expected, high)`
- Requires: `low <= expected <= high`

**Shifted log-normal distribution:**
- Model: `actual_duration = low + exp(Normal(μ, σ²))`
- Parameter derivation from three-point input:
  ```
  shifted_mode = expected - low
  shifted_high = high - low
  log_ratio = ln(shifted_high) - ln(shifted_mode)
  σ = (-z + √(z² + 4 × log_ratio)) / 2
  μ = ln(shifted_mode) + σ²
  ```
  Where `z` = configured high-percentile z-score (default: 1.6449 for 95th percentile)
- Requires strict inequality: `low < expected < high` (degenerate distributions rejected)
- The `high` value is interpreted as the configured percentile (default 95th), not the maximum

**Gotcha**: The z-score is configurable via `config.lognormal.high_percentile` (allowed values:
70, 75, 80, 85, 90, 95, 99). Changing this significantly affects the shape of sampled distributions.
The z-score is computed as `NormalDist().inv_cdf(high_percentile / 100)`.

#### FR-003: Monte Carlo Execution
The system SHALL execute N iterations (default 10,000) of the simulation, each iteration
independently sampling task durations, evaluating risks, and scheduling tasks.

**Per-iteration flow:**
1. For each task: sample base duration → convert units to hours → apply uncertainty multipliers
2. Evaluate task-level risks (both time impact and cost impact)
3. Schedule all tasks respecting dependencies (and optionally resource constraints)
4. Compute project end time = max(all task end times)
5. Evaluate project-level risks and add their impact to project duration
6. Record: project duration, effort (sum of all task durations), per-task durations,
   risk impacts, schedule slack, critical path, costs

#### FR-004: Risk Modeling
The system SHALL support risks at both task and project levels. Each risk has:
- `probability` [0.0, 1.0]: Chance of occurring per iteration
- `impact`: Time impact in hours (absolute) or percentage of base duration
- `cost_impact` (optional): Monetary impact when triggered (can be negative for savings)

**Impact types:**
- `absolute`: Fixed hours added (with optional unit conversion from days/weeks)
- `percentage`: Fraction of the task's adjusted duration (e.g., 0.20 = 20% increase)

**Evaluation order:**
- Task-level risks are evaluated and added to task duration BEFORE scheduling
- Project-level risks are evaluated and added to project duration AFTER scheduling
- Both time and cost impacts share the same probability roll (a triggered risk applies both)

#### FR-005: Uncertainty Factors
The system SHALL support multiplicative uncertainty factors applied to each task's sampled
duration. Five factor dimensions are supported:

| Factor | Levels | Default Multipliers |
|--------|--------|-------------------|
| team_experience | high, medium, low | 0.90, 1.00, 1.30 |
| requirements_maturity | high, medium, low | 1.00, 1.15, 1.40 |
| technical_complexity | low, medium, high | 1.00, 1.20, 1.50 |
| team_distribution | colocated, distributed | 1.00, 1.25 |
| integration_complexity | low, medium, high | 1.00, 1.15, 1.35 |

**Application**: All applicable factors are multiplied together into a single compound
multiplier, then applied to the sampled duration:
```
final_duration = sampled_duration × hours_multiplier × Π(uncertainty_factors)
```

**Project-level uncertainty factors**: Can be set at the project level and are inherited by
all tasks that don't override them individually.

#### FR-006: Dependency Resolution
The system SHALL resolve task dependencies using topological sorting (Kahn's algorithm)
and reject projects with circular dependencies.

**Scheduling rule**: A task cannot start until ALL its predecessors have completed.
In dependency-only mode: `start_time = max(end_time of all predecessors)`

#### FR-007: Critical Path Analysis
The system SHALL identify critical paths through the task dependency network.

**Two forms of critical path data:**
1. **Per-task criticality frequency**: For each task, count how many iterations it appeared
   on at least one critical path. Express as `criticality_index = count / iterations` (0.0–1.0).
2. **Full path sequences**: Track complete ordered task chains that form critical paths.
   Multiple terminal tasks finishing at the same time produce multiple branches per iteration.

**Stored data:**
- `critical_path_frequency: Dict[task_id → count]`
- `critical_path_sequences: List[CriticalPathRecord]` with path tuple, count, and frequency

**Report limit**: Config `output.critical_path_report_limit` (default 2) controls how many
distinct path sequences are shown in output. The simulation stores up to
`simulation.max_stored_critical_paths` (default 20) unique sequences.

#### FR-008: Statistical Analysis
The system SHALL compute and report:
- Mean, median, standard deviation, variance, min, max, range
- Coefficient of variation (std_dev / mean)
- Skewness (scipy.stats.skew)
- Kurtosis (scipy.stats.kurtosis, excess kurtosis)
- Percentiles at configurable confidence levels (default: 50, 80, 90, 95)
- Histogram with configurable bin count (default: 50 bins)

#### FR-009: Sensitivity Analysis
The system SHALL compute Spearman rank correlation between each task's per-iteration
duration and the overall project duration.

**Algorithm:**
```python
for each task_id:
    correlation = scipy.stats.spearmanr(task_durations[task_id], project_durations).correlation
    # Handle constant arrays (zero variance) by returning 0.0
```

**Output**: Tasks ranked by absolute correlation value. Higher |r| indicates the task's
duration variability drives more of the project schedule uncertainty.

#### FR-010: Configuration System
The system SHALL load configuration from:
1. Built-in defaults (hardcoded in Config class)
2. Auto-loaded user config at `~/.mcprojsim/config.yaml` (if exists)
3. Explicit `--config` flag on CLI (overrides auto-loaded)
4. In-project YAML fields (project-level settings override config for that run)

**Merge semantics**: Config files are MERGED onto defaults (deep merge), not replaced
wholesale. Only specified keys are overridden.

**Gotcha**: The auto-load path is `~/.mcprojsim/config.yaml` (not `configuration.yaml`).
The `--config` flag accepts any path. The `config show --generate` command outputs a
template to the default path.

#### FR-011: Progress Reporting
The system SHALL report simulation progress for long-running simulations.
A progress callback mechanism is available for integration with UI frameworks.

#### FR-012: Export Formats
The system SHALL export results in JSON, CSV, and HTML formats.
See Section 10 for detailed format specifications.

#### FR-013: Input Validation
The system SHALL validate all input before simulation and report all errors with
sufficient context (line numbers, field paths) for the user to locate and fix issues.
See Section 11 for complete validation rules.

#### FR-014: Symbolic Estimation — Story Points
The system SHALL accept story point estimates as an alternative to three-point numeric
estimates. Story points are mapped to three-point hour ranges via configuration.

**Default mappings** (unit: days):
| Points | Low | Expected | High |
|--------|-----|----------|------|
| 1 | 0.5 | 1 | 3 |
| 2 | 1 | 2 | 4 |
| 3 | 1.5 | 3 | 5 |
| 5 | 3 | 5 | 8 |
| 8 | 5 | 8 | 15 |
| 13 | 8 | 13 | 21 |
| 21 | 13 | 21 | 34 |

**Rule**: Tasks with `story_points` MUST NOT also specify `unit` — the unit comes from
`config.story_point_unit` (default: days).

#### FR-015: Symbolic Estimation — T-shirt Sizes
The system SHALL accept T-shirt size estimates (XS, S, M, L, XL, XXL) with support
for multiple size categories.

**Categories** (5 built-in):
- `story` (default): Standard development tasks (hours scale)
- `bug`: Bug fixes (smaller scale)
- `epic`: Large feature groupings (hundreds of hours)
- `business`: Business initiatives (thousands of hours)
- `initiative`: Portfolio-level initiatives (tens of thousands of hours)

**Size format**: Either plain (`M`) or qualified (`epic.L`). Plain sizes use the project's
`t_shirt_size_default_category` (default: `story`).

**Rule**: Tasks with `t_shirt_size` MUST NOT also specify `unit` — the unit comes from
`config.t_shirt_size_unit` (default: hours).

**Gotcha**: The token format is validated as alphabetic characters only (plus dashes/spaces
within tokens). Numeric characters in size names are rejected.

#### FR-016: Delivery Date Calculation
The system SHALL compute projected delivery dates from start_date by converting hours
to working days (skipping weekends: Saturday and Sunday).

**Formula:**
```
delivery_date = start_date + ceil(hours / hours_per_day) working days
```
Weekend days are skipped in the count.

#### FR-017: Schedule Slack (Total Float)
The system SHALL compute and report the mean total float (slack) for each task across
all iterations. Slack is calculated as:
```
slack = latest_possible_start - earliest_start
```
Where latest_possible_start is the latest a task could start without delaying the project end.

Tasks with zero or near-zero slack are marked "Critical" in output.

#### FR-018: Full Critical Path Sequences
See FR-007 above. The system tracks complete path sequences (ordered task ID tuples)
and reports their frequency of occurrence.

#### FR-019: Risk Impact Reporting
The system SHALL report per-task risk statistics:
- `mean_impact`: Average time impact across all iterations (including zero for non-triggered)
- `trigger_rate`: Fraction of iterations where the risk was triggered
- `mean_when_triggered`: Average impact in iterations where it DID trigger

#### FR-020: Distribution Shape Statistics
The system SHALL compute skewness and kurtosis of the project duration distribution.
These indicate whether the distribution is right-skewed (common for software projects)
and whether it has heavy tails.

#### FR-021: Staffing Analysis
The system SHALL provide team size recommendations using a Brooks's Law communication
overhead model.

**Individual Productivity formula:**
```
IP(n) = max(min_individual_productivity, 1.0 - communication_overhead × (n - 1))
```

**Effective Capacity formula:**
```
E(n) = n × IP(n) × productivity_factor
```

**Calendar Duration formula:**
```
T(n) = max(critical_path_hours, total_effort / E(n))
```

**Experience profiles** (configurable):
| Profile | productivity_factor | communication_overhead |
|---------|--------------------|-----------------------|
| senior | 1.0 | 0.04 |
| mixed | 0.85 | 0.06 |
| junior | 0.65 | 0.08 |

**Recommendation algorithm**: For each profile, evaluate team sizes 1 to max_parallel_tasks.
Find the first team size where adding one more person would increase calendar duration
(diminishing returns). That size is the recommendation.

**Effort basis**: By default uses mean effort. If `config.staffing.effort_percentile` is set,
uses that percentile of effort distribution instead.

#### FR-022: Natural Language Parsing
The system SHALL accept semi-structured natural language project descriptions and
generate valid YAML project specifications from them.

**Supported input elements:**
- Project metadata: `Project name:`, `Start date:`, `Hours per day:`, `Description:`
- Tasks: `Task N:` headers or auto-detected numbered/bulleted lists
- Estimates: T-shirt sizes, story points, three-point (`3/5/10 days`), prose ("about a week")
- Dependencies: `Depends on Task N`, `depends on the DB work` (fuzzy name matching)
- Resources: `Resource N: Name` with Experience, Productivity, Availability, Calendar, etc.
- Calendars: `Calendar: id` with Work hours, Work days, Holidays
- Sprint planning: `Sprint planning:` section with sprint length, history entries

**Fuzzy duration mapping** (prose → T-shirt sizes):
- XS: "a few hours", "couple of hours"
- S: "a day or two", "couple of days", "half a day"
- M: "about a week", "5 working days"
- L: "a few weeks", "several weeks"
- XL: "a month", "four weeks"
- XXL: "a few months", "several months", "a quarter"

**Gotcha**: Cannot mix `Task N:` headers and auto-detected plain lists in the same input.
Task names may get trailing `()` from empty parentheses in input — a known parser artifact.

#### FR-023: YAML Project File Generation
The system SHALL generate syntactically valid YAML project files from natural language
descriptions (FR-022) and from the `generate` CLI command.

The generated YAML must pass `mcprojsim validate` without errors.

#### FR-024: MCP Server
The system SHALL expose simulation functionality via a Model Context Protocol (MCP)
server using stdio transport.

**Exposed tools** (7 total):
1. `generate_project_file(description) → yaml_string`
2. `validate_project_description(description) → validation_report`
3. `validate_generated_project_yaml(description, config_yaml?, velocity_model?, no_sickness?) → report + yaml`
4. `validate_project_yaml(project_yaml, config_yaml?, velocity_model?, no_sickness?) → report`
5. `simulate_project(description, iterations?, seed?, config_yaml?, velocity_model?, no_sickness?, two_pass?, pass1_iterations?, critical_paths_limit?, target_budget?) → results`
6. `simulate_project_yaml(project_yaml, <same options as above>) → results`
7. `update_project_yaml(existing_yaml, update_description, replace_tasks?) → updated_yaml`

**Architecture**: FastMCP-based, runs as long-lived process on stdin/stdout.
The MCP dependency is optional (`poetry install --with mcp`).

**Gotcha**: The MCP server does NOT accept `--help` or any command-line flags.
Running it directly will hang waiting for MCP protocol messages on stdin.

#### FR-025: Project YAML Update
The system SHALL support updating existing YAML project files from natural language
instructions without requiring full re-specification.

**Behavior:**
- `replace_tasks=False` (default): Preserves existing tasks; updates metadata/sprint/resources/calendars only
- `replace_tasks=True`: Replaces entire task list with newly parsed tasks

---

### 2.2 Cost Estimation (FR-045 through FR-054)

#### FR-045: Cost Model Activation
The system SHALL activate cost estimation when ANY of the following conditions are met:
- `project.default_hourly_rate > 0`
- Any resource has `hourly_rate` set (even to 0)
- Any task has `fixed_cost` set
- Any risk (task-level or project-level) has `cost_impact` set

When cost estimation is inactive, all cost-related output fields are None/omitted.

#### FR-046: Labor Cost Calculation
The system SHALL compute labor cost per task as:
```
task_labor_cost = task_duration_hours × effective_hourly_rate
```

**Rate resolution:**
- In constrained mode (resources assigned): Uses mean of assigned resources' hourly_rates;
  falls back to project `default_hourly_rate` for resources without explicit rates
- In dependency-only mode: Always uses project `default_hourly_rate`

**Gotcha**: Multi-resource tasks use the MEAN of assigned rates, assuming equal effort split.
This is a simplifying assumption documented as "Phase 1"; per-resource contributed-hours
tracking is not yet implemented.

#### FR-047: Fixed Cost
The system SHALL support per-task fixed costs that are added regardless of duration.
Fixed costs may be negative (representing credits or subsidies).

#### FR-048: Risk Cost Impact
The system SHALL support monetary `cost_impact` on risks. When a risk triggers (based on
its probability roll), both time impact AND cost impact are applied in the same iteration.
Cost impacts may be negative.

#### FR-049: Overhead Rate
The system SHALL apply a fractional overhead rate to labor costs ONLY:
```
overhead = total_labor_cost × overhead_rate
```
Fixed costs and risk cost impacts are NOT subject to overhead markup.

**Total project cost per iteration:**
```
total_cost = total_labor + total_fixed + total_risk_cost + (total_labor × overhead_rate)
```

#### FR-050: Budget Confidence Analysis
When `--target-budget` is specified, the system SHALL report:
1. Probability of staying within budget: `P(cost ≤ target)`
2. 95% confidence interval on that probability (Wilson score for small tails, normal approx otherwise)
3. Budget required for P50, P80, P90 confidence levels
4. Joint probability of meeting BOTH schedule AND budget targets (if applicable)

#### FR-051: Cost Statistics
The system SHALL compute and report cost distribution statistics (mean, std_dev, percentiles)
in the same manner as duration statistics.

#### FR-052: Cost Sensitivity Analysis
The system SHALL compute correlation between per-task costs and total project cost,
identifying which tasks drive cost uncertainty.

#### FR-053: Secondary Currencies
The system SHALL support display of cost results in up to 5 secondary currencies.

**Fields:**
- `secondary_currencies`: List of ISO 4217 codes (max 5)
- `fx_rates`: Manual exchange rate overrides (target_currency → rate)
- `fx_conversion_cost`: Bank spread fraction [0, 0.50]
- `fx_overhead_rate`: Hedging/admin overhead [0, 1.0]

**Note**: Automatic FX rate fetching is not implemented. Rates must be provided manually
via `fx_rates` or display will use the raw primary-currency amounts.

#### FR-054: Per-Task Cost Reporting
The system SHALL report per-task cost statistics: mean, std_dev, min, max, and
percentage of total project cost.

---

### 2.3 Resource & Calendar Constrained Scheduling (FR-026 through FR-044)

#### FR-026: Team Resource Model
The system SHALL support explicit resource definitions with:
- `name`: Unique identifier
- `availability`: Fraction of full-time [0, 1.0]
- `calendar`: Reference to a calendar definition
- `experience_level`: Integer {1, 2, 3}
- `productivity_level`: Float [0.1, 2.0] (multiplier on work output)
- `sickness_prob`: Per-day probability of starting a sickness episode [0, 1.0]
- `planned_absence`: List of specific dates when unavailable
- `hourly_rate`: Optional monetary rate for cost calculation

#### FR-027: Implicit Team via team_size
If `project.team_size > 0` and fewer explicit resources are defined, the system SHALL
auto-generate default resources to reach the specified team_size.

**Rules:**
- If explicit resources > team_size: validation error
- If explicit resources < team_size: append generic resources with default attributes
- Auto-generated resources use the "default" calendar

#### FR-028: Resource Productivity
The system SHALL apply `productivity_level` as a divisor on effective work rate:
```
effective_hours_per_calendar_hour = availability × productivity_level
```
Higher productivity = task completes faster.

#### FR-029: Calendar Definitions
The system SHALL support calendar specifications with:
- `id`: Unique identifier (default: "default")
- `work_hours_per_day`: Hours of productive work per calendar day (default: 8.0)
- `work_days`: List of working weekdays as integers 1–7 (1=Monday, 7=Sunday; default: [1,2,3,4,5])
- `holidays`: List of specific dates that are non-working

#### FR-030: Sickness Simulation
The system SHALL stochastically simulate sickness absence for each resource.

**Algorithm:**
1. Estimate project horizon: `max(30, ceil(total_effort / (hours_per_day × total_capacity)) + 60)` days
2. For each resource, for each working day in the horizon:
   - Roll `random() < sickness_prob`
   - If sick: sample duration from LogNormal(μ, σ), mark consecutive days as absent
   - Skip ahead by sickness duration
3. Sickness days are excluded from resource availability windows

**Sickness probability precedence:**
1. Per-resource `sickness_prob` field (explicit in YAML)
2. Config `constrained_scheduling.sickness_prob` (global fallback)

**Duration distribution**: LogNormal with configurable μ and σ (from config or sprint sickness defaults)

#### FR-031: Resource Assignment Strategy
The system SHALL assign resources to tasks using a greedy event-driven algorithm.

**Single-pass (default):**
- Ready tasks sorted by ascending task_id (lexicographic, deterministic)
- For each ready task: find eligible free resources meeting experience requirements
- Eligible resources sorted alphabetically by name
- Assign first `min(max_resources, practical_cap)` eligible resources

**Practical auto-cap formula:**
```python
granularity_cap = max(1, floor(effort_hours / MIN_EFFORT_PER_ASSIGNEE_HOURS))
practical_cap = max(1, min(MAX_ASSIGNEES_PER_TASK, granularity_cap))
```
Where `MIN_EFFORT_PER_ASSIGNEE_HOURS = 16.0` and `MAX_ASSIGNEES_PER_TASK = 3`.

This prevents unrealistic compression (e.g., a 5-hour task split among 3 people).

#### FR-032: Calendar-Aware Duration Computation
Once resources are assigned to a task, the system SHALL compute task end time by
integrating effort over calendar availability windows:

```
For each availability window of assigned resources:
    producible_hours = capacity_per_hour × window_duration
    remaining_effort -= producible_hours
    If remaining_effort <= 0: task ends within this window
Track total calendar_delay (non-work periods within task span)
```

#### FR-033: Task Eligibility and Experience
A resource is eligible for a task if:
1. The resource is listed in the task's `resources` field (or task has no explicit resource list)
2. `resource.experience_level >= task.min_experience_level`

`min_experience_level` accepts values {1, 2, 3}.

#### FR-034: Two-Pass Criticality Scheduling
The system SHALL support a two-pass scheduling mode (`--two-pass` flag or
`config.constrained_scheduling.assignment_mode = "criticality_two_pass"`).

**Pass 1**: Run N iterations (configurable, default 1000) with default greedy single-pass.
Build per-task criticality index from critical path frequency.

**Pass 2**: Re-run with task priority ordering:
- Ready tasks sorted by `(-criticality_index, task_id)` — higher criticality scheduled first
- First `pass1_iterations` iterations replay cached durations deterministically
- Remaining iterations sample fresh

**Traceability output:**
- Pass-1 aggregate stats (mean, P50, P80, P90, P95)
- Pass-2 aggregate stats (same)
- Deltas (negative = improvement from prioritization)
- Per-task criticality index from Pass-1

**Gotcha**: Using `--two-pass` without named resources silently falls back to single-pass
with no warning. This is because two-pass only meaningfully affects resource-constrained
scheduling where assignment order matters.

#### FR-035: Scheduling Mode Selection
The scheduler mode is selected per the project's resource configuration:
- `dependency_only`: When no resources exist (no explicit resources, team_size=0 or unset)
- `resource_constrained`: When resources exist (explicitly defined or generated from team_size)

#### FR-036: Resource Wait Time Tracking
The system SHALL track time between when a task's dependencies are satisfied and when
resources actually become available to start it.

#### FR-037: Resource Utilization Tracking
The system SHALL track overall resource utilization:
```
utilization = total_effort_hours / total_available_capacity_hours (capped at 1.0)
```

#### FR-038: Calendar Delay Tracking
The system SHALL track total non-work time within the project span (weekends, holidays,
sickness days that fall between a task's dependency-ready time and completion).

#### FR-039: Dependency-Only Scheduling Algorithm
When no resources exist:
```
for task_id in topological_order:
    start_time = max(end_time of all predecessors, or 0.0 if none)
    end_time = start_time + duration
    schedule[task_id] = (start, end)
```
Pure dependency-chain parallelism: tasks without mutual dependencies can overlap in time.

#### FR-040: Resource-Constrained Scheduling Algorithm
**Event-driven greedy loop:**
```
while remaining_tasks:
    1. Release completed tasks at current_time
    2. Find ready tasks (all dependencies satisfied)
    3. Sort ready tasks (by task_id or by criticality priority)
    4. For each ready task:
       - Find eligible free resources
       - Compute practical_cap (FR-031)
       - Assign resources, compute end_time via calendar integration (FR-032)
       - Add to active list
    5. If no task could start: advance current_time to earliest active task completion
```

#### FR-041: Planned Absence
The system SHALL respect per-resource `planned_absence` dates. On those dates,
the resource is unavailable for work assignment (treated identically to sickness days
for scheduling purposes).

#### FR-042: Effort vs Duration Distinction
The system SHALL maintain and report two independent metrics:
- **Project Duration** (calendar time): `max(task_end_times)` — elapsed time from start to finish
- **Project Effort** (person-hours): `sum(all task durations)` — total work regardless of parallelism

In dependency-only mode these may be similar. In resource-constrained mode, duration is
typically much longer than effort would suggest due to resource bottlenecks.

#### FR-043: Constrained Scheduling Validation
The system SHALL validate resource-constraint configurations:
- All task resource references must point to existing resources
- Resource calendars must reference existing calendar definitions
- Experience requirements must be satisfiable (at least one eligible resource exists)

#### FR-044: Constrained Scheduling Diagnostics
The system SHALL report per-iteration diagnostics:
- Mean resource wait time (hours)
- Mean resource utilization (0–1)
- Mean calendar delay (hours)

---

### 2.4 Sprint Planning (FR-055 through FR-070)

#### FR-055: Sprint Planning Model
The system SHALL support Monte Carlo sprint forecasting as an optional overlay on top
of standard duration simulation.

**Core concept**: Given historical sprint velocity data and a remaining backlog,
simulate how many sprints are needed to complete all named tasks (and optional
aggregate backlog), producing a probabilistic sprint count distribution.

#### FR-056: Sprint History Input
The system SHALL accept sprint history entries with:
- `sprint_id`: Unique identifier (required)
- `sprint_length_weeks`: Duration (inherits from global sprint_length_weeks if omitted)
- Delivery signal: EXACTLY ONE of `completed_story_points` or `completed_tasks`
- `spillover_story_points` / `spillover_tasks`: Incomplete work carried over (default: 0)
- `added_story_points` / `added_tasks`: Scope added mid-sprint (default: 0)
- `removed_story_points` / `removed_tasks`: Scope removed (default: 0)
- `holiday_factor`: Capacity multiplier for reduced-capacity sprints (default: 1.0, gt 0)
- `end_date`: Optional sprint boundary date
- `team_size`: Optional team size tracking
- `notes`: Optional context

**Validation rules:**
- Minimum 2 entries with positive delivery signal required
- Cannot mix story-point and task-count fields in the same entry
- Entry field family must match `capacity_mode` (story_points vs tasks)
- sprint_id values must be unique

**Normalization**: Completed and spillover values are divided by `holiday_factor` to
normalize for reduced-capacity sprints. Added and removed are NOT normalized.

#### FR-057: Velocity Models
The system SHALL support two velocity sampling models:

**Empirical (default):**
- Resamples from historical completed-units observations
- Prefers sprints with matching `sprint_length_weeks`
- Falls back to weekly-rate normalization if no matching cadence exists
  (breaks history into per-week rates, samples N weeks, aggregates)

**Negative Binomial:**
- Fits NB distribution parameters using method of moments:
  ```
  μ = mean(completed_units)
  k = μ² / (variance - μ)    # dispersion parameter
  If variance ≤ mean: k = ∞ (Poisson fallback)
  ```
- Samples from NB(k, p) where p = k / (k + μ)
- Spillover, added, and removed units still resampled empirically
- Records diagnostic params (mu, k, overdispersed flag)

#### FR-058: Sprint Simulation Algorithm
Each iteration of the sprint simulation:
```
while (named_tasks_remaining OR aggregate_backlog > threshold):
    1. Sample velocity (completed_units) from chosen model
    2. Sample spillover, added, removed from historical distributions
    3. Apply multipliers: volatility × future_override × sickness
    4. Pull ready tasks greedily (by priority, then task_id) until capacity exhausted
       - If spillover enabled: may partially complete task (Beta-sampled fraction)
       - Track carryover (remainder items) and spillover events
    5. Update aggregate backlog: +added, -removed (if REDUCE_BACKLOG mode)
    6. Deliver synthetic backlog units if remaining capacity exists
    7. Track burnup (cumulative delivered)
    8. Check convergence (error at 10,000 sprints)
```

**Task ordering**: Tasks pulled by ascending priority (if set), then ascending task_id.
Dependency DAG is respected — only dependency-ready tasks are available.

#### FR-059: Removed Work Treatment
Two modes for handling removed scope:
- `churn_only` (default): Removed work is a diagnostic signal only; does not reduce forecast backlog
- `reduce_backlog`: Removed work directly reduces the remaining aggregate backlog projection

#### FR-060: Spillover Model
The system SHALL optionally model partial task completion (spillover) within sprints.

**Table model** (default):
- Size brackets map task size (in planning story points) to spillover probability
- Default brackets: [{max_points: 2, prob: 0.05}, {max_points: 5, prob: 0.12},
  {max_points: 8, prob: 0.25}, {max_points: None, prob: 0.40}]
- When spillover occurs: consumed fraction sampled from Beta(α, β) distribution
  (default α=3.25, β=1.75 — right-skewed, most work completed)

**Logistic model** (alternative):
- Spillover probability = sigmoid(slope × normalized_size + intercept)
- Same consumed fraction model

#### FR-061: Sprint Sickness Model
The system SHALL optionally model team-member sickness within sprint planning.

**Per-sprint sickness multiplier:**
1. For each week in sprint: Binomial(team_size, prob_per_person_per_week) → sick count
2. For each sick event: sample duration from LogNormal(μ, σ), cap at remaining sprint days
3. Total lost_days capped at total person-days
4. Multiplier = max(0, 1 - lost_days / total_person_days)

Applied to completed_units after volatility and future overrides.

#### FR-062: Volatility/Disruption Overlay
The system SHALL optionally apply a stochastic disruption event per sprint:
- `disruption_probability`: Chance of disruption per sprint
- If triggered: sample multiplier from Triangular(low, expected, high)
- Applied as: `completed_units × disruption_multiplier`

#### FR-063: Future Sprint Overrides
The system SHALL support explicit capacity adjustments for known upcoming sprints:
- Matched by `sprint_number` OR `start_date` (OR logic — first match wins)
- Each override provides `holiday_factor` and/or `capacity_multiplier`
- Effective multiplier = holiday_factor × capacity_multiplier

#### FR-064: Sprint Planning Results
The system SHALL produce:
- Sprint count distribution (array of per-iteration counts)
- Statistics: mean, median, std_dev, min, max, percentiles
- Date percentiles: sprint count mapped to calendar delivery dates
- Historical diagnostics: sampling mode, velocity model, observation count
- Series statistics: mean/median/std_dev/min/max/CV for completed, spillover, added, removed
- Ratio statistics: spillover_ratio, scope_addition_ratio, scope_removal_ratio
- Correlations between historical metrics
- Planned commitment guidance (heuristic capacity recommendation)
- Carryover statistics (peak remainder units across sprints)
- Spillover statistics (aggregate spillover rate)
- Disruption statistics (configured probability, observed frequency)
- Burnup percentiles (cumulative delivered at P50/P80/P90 per sprint number)
- Future sprint override transparency (which overrides were applied)

#### FR-065: Planned Commitment Guidance
The system SHALL compute a heuristic sprint commitment recommendation:
```
removal_ratio = removed / (completed + spillover + removed)
guidance = median(completed) × (1 - Pq(spillover_ratio)) × (1 - Pq(removal_ratio)) - Pq(added)
```
Where Pq = percentile at q = confidence_level × 100.

#### FR-066: Sprint Capacity Mode
Two capacity modes determine the unit system:
- `story_points`: Tasks have planning_story_points; velocity measured in points
- `tasks`: Tasks counted as unit-each; velocity measured in task count

#### FR-067: Sprint Burnup Tracking
The system SHALL track cumulative delivered units at percentiles (P50, P80, P90) per
sprint number across all iterations, producing a burnup forecast chart dataset.

#### FR-068: Sprint Planning Confidence Level
The system SHALL use a configurable confidence level (default 0.80) for:
- Commitment guidance percentile calculations
- Sprint count confidence intervals
- Burnup forecast reporting

#### FR-069: Sprint History Correlation Analysis
The system SHALL compute Pearson correlations between historical metrics
(e.g., completed|spillover, completed|added) and include in diagnostics output.

#### FR-070: Sprint Convergence Safety
The system SHALL raise a ValueError if any iteration exceeds 10,000 sprints.
This prevents infinite loops from misconfigured projects where tasks can never complete
(e.g., circular dependency that slipped past validation, or unreachable tasks).

---

### 2.5 Distribution Selection (FR-071)

#### FR-071: Per-Project and Per-Task Distribution
The system SHALL support selecting distribution type at both project and task level:
- `project.distribution`: Default distribution for all tasks (triangular or lognormal)
- `task.estimate.distribution`: Override for specific tasks

When unspecified at task level, the project default applies.
When unspecified at project level, triangular is the default.

---

## 3. Non-Functional Requirements

### NFR-001: Performance
- 10,000 iterations on a 20-task project SHALL complete within 10 seconds
- Memory usage SHALL scale linearly with iterations × tasks
- NumPy vectorization SHALL be used for bulk random sampling where possible

### NFR-002: Code Quality
- Strict type annotations throughout source code (Python 3.13+ typing features)
- Pydantic v2 for all data models with comprehensive validators
- Black formatting, flake8 linting, strict mypy type checking
- Pre-commit hooks for automated quality checks

### NFR-003: Test Coverage
- Minimum 80% line coverage (enforced by CI)
- Integration tests for CLI commands (using Click's CliRunner)
- MCP tests use `pytest.importorskip("mcp")` since MCP is an optional dependency
- Parametrized tests for distribution sampling, scheduling modes, cost calculations
- Reproducibility tests: same seed → identical results

### NFR-004: Documentation
- MkDocs with Material theme
- Sequentially numbered user guide chapters (01–16)
- Grammar reference for YAML project file format
- API reference via mkdocstrings
- Examples directory with sample project files

### NFR-005: Maintainability
- Clear separation: parsers (with line tracking) → Pydantic models (validation) → engine (simulation) → analysis (post-processing) → exporters (output)
- Config as single source of truth for all defaults and tuning parameters
- No hardcoded magic numbers in simulation logic

### NFR-006: Portability
- **Python 3.13+** required (uses modern typing features including `type` statements)
- Dependencies: NumPy, SciPy, Pandas, PyYAML, Pydantic v2, Click 8+, Matplotlib
- Optional: FastMCP (for MCP server), tomli/tomli-w (for TOML support)
- Runs on macOS, Linux, Windows

**Gotcha**: The original specification said "Python 3.9+" but the implementation uses
Python 3.13+ features throughout. This is a hard requirement.

### NFR-007: Reproducibility
- All randomness flows through `numpy.random.RandomState(seed)`
- Given same seed + same input + same config → bit-identical results
- The random state is passed through all sampling functions (no global random state)

### NFR-008: Extensibility
- New distribution types can be added to DistributionSampler
- New export formats can be added as ExporterBase subclasses
- New uncertainty factor dimensions can be added via config (no code changes)
- New T-shirt size categories can be added via config

### NFR-009: Usability
- CLI with helpful error messages and `--help` on all commands
- Validation errors include file path, line number, and field context
- HTML reports with embedded charts (no external dependencies to view)
- Progressive complexity: minimal projects need only `project:` + `tasks:` sections

### NFR-010: Logging
- Standard Python logging with configurable levels
- `--verbose` flag enables detailed output during simulation
- `--quiet` suppresses all output except errors and final results

---

## 4. Input File Format Specification

### 4.1 Project YAML Structure

#### 4.1.1 Minimal Valid Project
```yaml
project:
  name: "My Project"
  start_date: "2026-01-15"

tasks:
  - id: "task_001"
    name: "First task"
    estimate:
      low: 3
      expected: 5
      high: 10
```

#### 4.1.2 Complete Project Structure
```yaml
project:
  name: "Complete Example"
  description: "Full-featured project specification"
  start_date: "2026-01-15"
  hours_per_day: 8.0
  distribution: "lognormal"          # Default distribution for all tasks
  team_size: 4                       # Auto-generate resources if needed
  t_shirt_size_default_category: "story"
  confidence_levels: [50, 80, 90, 95]
  probability_red_threshold: 0.6
  probability_green_threshold: 0.8
  # Cost fields
  currency: "EUR"
  default_hourly_rate: 85.0
  overhead_rate: 0.15
  secondary_currencies: ["USD", "SEK"]
  fx_rates:
    USD: 1.08
    SEK: 11.50
  fx_conversion_cost: 0.005
  fx_overhead_rate: 0.02
  # Project-level uncertainty defaults
  uncertainty_factors:
    team_experience: "medium"
    requirements_maturity: "medium"
    technical_complexity: "medium"
    team_distribution: "colocated"
    integration_complexity: "low"

project_risks:
  - id: "risk_001"
    name: "Key person leaves"
    probability: 0.15
    impact:
      type: "percentage"
      value: 0.25
    cost_impact: 50000

tasks:
  - id: "task_001"
    name: "Database schema design"
    description: "Design normalized schema"
    estimate:
      low: 3
      expected: 5
      high: 10
      unit: "days"
      distribution: "lognormal"   # Task-level override
    dependencies: []
    priority: 1
    planning_story_points: 8
    fixed_cost: 5000
    uncertainty_factors:
      team_experience: "high"
      technical_complexity: "low"
    resources: ["alice", "bob"]
    max_resources: 2
    min_experience_level: 2
    risks:
      - id: "task_risk_001"
        name: "Schema migration issues"
        probability: 0.20
        impact: 16              # hours (plain numbers are hours)
        cost_impact: 2000

  - id: "task_002"
    name: "API implementation"
    estimate:
      t_shirt_size: "L"        # Uses story category by default
    dependencies: ["task_001"]
    resources: ["alice"]

  - id: "task_003"
    name: "Bug fix sprint"
    estimate:
      t_shirt_size: "bug.M"    # Qualified with category
    dependencies: []

  - id: "task_004"
    name: "Feature work"
    estimate:
      story_points: 8          # Maps to config story_point ranges
    dependencies: ["task_001"]

resources:
  - name: "alice"
    availability: 1.0
    calendar: "standard"
    experience_level: 3
    productivity_level: 1.1
    hourly_rate: 95.0
    sickness_prob: 0.02
    planned_absence:
      - "2026-02-14"
      - "2026-03-01"

  - name: "bob"
    availability: 0.8
    calendar: "standard"
    experience_level: 2
    productivity_level: 1.0
    hourly_rate: 75.0

calendars:
  - id: "standard"
    work_hours_per_day: 8.0
    work_days: [1, 2, 3, 4, 5]
    holidays:
      - "2026-01-01"
      - "2026-12-25"

sprint_planning:
  enabled: true
  sprint_length_weeks: 2
  capacity_mode: "story_points"
  velocity_model: "empirical"
  planning_confidence_level: 0.80
  removed_work_treatment: "churn_only"
  sickness:
    enabled: true
    team_size: 4
    probability_per_person_per_week: 0.058
    duration_log_mu: 0.693
    duration_log_sigma: 0.75
  volatility_overlay:
    enabled: true
    disruption_probability: 0.10
    disruption_multiplier_low: 0.5
    disruption_multiplier_expected: 0.7
    disruption_multiplier_high: 0.9
  spillover:
    enabled: true
    model: "table"
    size_reference_points: 5.0
    size_brackets:
      - max_points: 2.0
        probability: 0.05
      - max_points: 5.0
        probability: 0.12
      - max_points: 8.0
        probability: 0.25
      - max_points: null
        probability: 0.40
    consumed_fraction_alpha: 3.25
    consumed_fraction_beta: 1.75
  future_sprint_overrides:
    - sprint_number: 3
      holiday_factor: 0.6
      notes: "Christmas sprint"
    - start_date: "2026-04-01"
      capacity_multiplier: 0.8
      notes: "Team member on leave"
  history:
    - sprint_id: "S1"
      completed_story_points: 21
      spillover_story_points: 3
      added_story_points: 5
      removed_story_points: 2
    - sprint_id: "S2"
      completed_story_points: 25
      spillover_story_points: 1
      added_story_points: 3
    - sprint_id: "S3"
      sprint_length_weeks: 3
      completed_story_points: 35
      spillover_story_points: 5
      holiday_factor: 0.8
      end_date: "2025-12-20"
      team_size: 4
      notes: "Holiday sprint"
```

#### 4.1.3 Unit Conversion
All durations are internally converted to hours using:
- `hours_per_day` (from project metadata, default 8.0) for days → hours
- `hours_per_day × 5` for weeks → hours (5 working days per week)
- The constant `STANDARD_HOURS_PER_DAY = 8.0` is used for unit conversions in the engine,
  decoupled from the project's display `hours_per_day` setting

**Gotcha**: `STANDARD_HOURS_PER_DAY` (used for risk percentage calculations and output
conversions) is always 8.0 regardless of the project's `hours_per_day` setting.

#### 4.1.4 Field Aliases
The following field aliases are accepted by the Pydantic model layer:
- `estimate.min` → `estimate.low`
- `estimate.max` → `estimate.high`
- `estimate.most_likely` → `estimate.expected`
- Resource `id` → Resource `name` (legacy fallback)

**Gotcha**: Aliases work at the Pydantic model construction level. The YAML parser
enforces strict field names and will reject unknown fields. Therefore, aliases only
work reliably when data flows directly through model constructors (as in tests or API use).
In YAML files, prefer the canonical field names.

---

### 4.2 Configuration File (config.yaml)

The configuration file controls all default values and tuning parameters.
A complete template can be generated with `mcprojsim config show --generate`.

```yaml
# Uncertainty factor multipliers
uncertainty_factors:
  team_experience:
    high: 0.90
    medium: 1.0
    low: 1.30
  requirements_maturity:
    high: 1.0
    medium: 1.15
    low: 1.40
  technical_complexity:
    low: 1.0
    medium: 1.20
    high: 1.50
  team_distribution:
    colocated: 1.0
    distributed: 1.25
  integration_complexity:
    low: 1.0
    medium: 1.15
    high: 1.35

# T-shirt size mappings (5 categories × 6 sizes)
t_shirt_sizes:
  story:
    XS: {low: 3, expected: 5, high: 15}
    S: {low: 5, expected: 16, high: 40}
    M: {low: 40, expected: 60, high: 120}
    L: {low: 160, expected: 240, high: 500}
    XL: {low: 320, expected: 400, high: 750}
    XXL: {low: 400, expected: 500, high: 1200}
  bug:
    XS: {low: 0.5, expected: 1, high: 4}
    S: {low: 1, expected: 3, high: 10}
    M: {low: 3, expected: 8, high: 24}
    L: {low: 8, expected: 20, high: 60}
    XL: {low: 20, expected: 40, high: 100}
    XXL: {low: 40, expected: 80, high: 200}
  epic:
    XS: {low: 20, expected: 40, high: 60}
    S: {low: 60, expected: 120, high: 170}
    M: {low: 120, expected: 240, high: 400}
    L: {low: 290, expected: 480, high: 700}
    XL: {low: 600, expected: 1000, high: 1500}
    XXL: {low: 1200, expected: 2000, high: 3200}
  business:
    XS: {low: 400, expected: 800, high: 2000}
    S: {low: 800, expected: 2000, high: 5000}
    M: {low: 2000, expected: 4000, high: 10000}
    L: {low: 4000, expected: 8000, high: 20000}
    XL: {low: 8000, expected: 16000, high: 40000}
    XXL: {low: 16000, expected: 32000, high: 80000}
  initiative:
    XS: {low: 2000, expected: 4000, high: 10000}
    S: {low: 4000, expected: 10000, high: 25000}
    M: {low: 10000, expected: 20000, high: 50000}
    L: {low: 20000, expected: 40000, high: 100000}
    XL: {low: 40000, expected: 80000, high: 200000}
    XXL: {low: 80000, expected: 160000, high: 400000}

t_shirt_size_default_category: "story"
t_shirt_size_unit: "hours"   # Unit for t-shirt size ranges

# Story point mappings
story_points:
  1: {low: 0.5, expected: 1, high: 3}
  2: {low: 1, expected: 2, high: 4}
  3: {low: 1.5, expected: 3, high: 5}
  5: {low: 3, expected: 5, high: 8}
  8: {low: 5, expected: 8, high: 15}
  13: {low: 8, expected: 13, high: 21}
  21: {low: 13, expected: 21, high: 34}

story_point_unit: "days"     # Unit for story point ranges

# Lognormal distribution configuration
lognormal:
  high_percentile: 95        # Allowed: 70, 75, 80, 85, 90, 95, 99

# Simulation defaults
simulation:
  default_iterations: 10000
  random_seed: null
  max_stored_critical_paths: 20

# Output formatting
output:
  formats: ["json", "csv", "html"]
  include_histogram: true
  number_bins: 50
  critical_path_report_limit: 2

# Staffing analysis
staffing:
  effort_percentile: null    # null = use mean; 1-99 = use that percentile
  min_individual_productivity: 0.25
  experience_profiles:
    senior:
      productivity_factor: 1.0
      communication_overhead: 0.04
    mixed:
      productivity_factor: 0.85
      communication_overhead: 0.06
    junior:
      productivity_factor: 0.65
      communication_overhead: 0.08

# Constrained scheduling
constrained_scheduling:
  sickness_prob: 0.0
  assignment_mode: "greedy_single_pass"  # or "criticality_two_pass"
  pass1_iterations: 1000

# Sprint planning defaults
sprint_defaults:
  planning_confidence_level: 0.80
  removed_work_treatment: "churn_only"
  velocity_model: "empirical"
  volatility_disruption_probability: 0.0
  volatility_disruption_multiplier_low: 1.0
  volatility_disruption_multiplier_expected: 1.0
  volatility_disruption_multiplier_high: 1.0
  spillover_model: "table"
  spillover_size_reference_points: 5.0
  spillover_size_brackets:
    - {max_points: 2.0, probability: 0.05}
    - {max_points: 5.0, probability: 0.12}
    - {max_points: 8.0, probability: 0.25}
    - {max_points: null, probability: 0.40}
  spillover_consumed_fraction_alpha: 3.25
  spillover_consumed_fraction_beta: 1.75
  spillover_logistic_slope: 1.9
  spillover_logistic_intercept: -1.9924301646902063
  sickness:
    enabled: false
    probability_per_person_per_week: 0.058
    duration_log_mu: 0.693
    duration_log_sigma: 0.75

# Cost defaults
cost:
  default_hourly_rate: null
  overhead_rate: 0.0
  currency: "EUR"
  include_in_output: true
```

---

## 5. System Architecture

### 5.1 Module Structure

```
src/mcprojsim/
├── __init__.py              # Version resolution (fallback to pyproject.toml)
├── cli.py                   # Click-based CLI (simulate, validate, generate, config)
├── config.py                # Config class with all defaults and validation
├── nl_parser.py             # Natural language → project data parser
├── mcp_server.py            # FastMCP server (optional dependency)
├── models/
│   ├── __init__.py          # Public model exports
│   ├── project.py           # Project, Task, Risk, Resource, Calendar, SprintPlanning models
│   ├── simulation.py        # SimulationResults with NumPy arrays
│   └── sprint_simulation.py # SprintPlanningResults model
├── parsers/
│   ├── __init__.py
│   ├── yaml_parser.py       # YAML parser with line tracking
│   ├── toml_parser.py       # TOML parser
│   └── error_reporting.py   # Location-aware error formatting
├── simulation/
│   ├── __init__.py
│   ├── engine.py            # SimulationEngine (MC loop, two-pass, cost)
│   ├── distributions.py     # DistributionSampler (triangular, lognormal)
│   ├── scheduler.py         # TaskScheduler (dependency-only + resource-constrained)
│   └── risk_evaluator.py    # RiskEvaluator (probability + impact calculation)
├── analysis/
│   ├── __init__.py
│   ├── statistics.py        # Statistical computations (percentiles, CI)
│   ├── sensitivity.py       # Spearman rank correlation
│   ├── critical_path.py     # Path sequence tracking and reporting
│   └── staffing.py          # Brooks's Law team size optimization
├── planning/
│   ├── __init__.py
│   ├── sprint_engine.py     # SprintSimulationEngine
│   └── sprint_planner.py    # SprintPlanner (task pull, backlog ledger)
└── exporters/
    ├── __init__.py
    ├── json_exporter.py     # JSON output
    ├── csv_exporter.py      # CSV output
    └── html_exporter.py     # HTML with Matplotlib PNG charts

tests/
├── test_models.py           # Pydantic model validation
├── test_parsers.py          # Parser correctness
├── test_simulation.py       # Engine, scheduler, distributions
├── test_analysis.py         # Statistics, sensitivity, critical path
├── test_cli.py              # CLI integration (CliRunner)
├── test_cli_output.py       # Output format verification
├── test_sprint_planning.py  # Sprint simulation
├── test_staffing.py         # Staffing analysis
├── test_cost.py             # Cost calculation
├── test_mcp.py              # MCP server tools (importorskip)
├── test_nl_parser.py        # NL parser
└── fixtures/                # Sample YAML/TOML files
```

### 5.2 Data Flow

```
Input (YAML/TOML/NL) → Parser → Pydantic Models (validated) → SimulationEngine
                                                                    ↓
                                                              DistributionSampler
                                                              RiskEvaluator
                                                              TaskScheduler
                                                                    ↓
                                                           SimulationResults
                                                                    ↓
                                                    Analysis (stats, sensitivity, paths)
                                                                    ↓
                                                    Exporters (JSON, CSV, HTML)
```

### 5.3 Key Design Decisions

1. **Pydantic v2 for validation**: All data models use Pydantic v2 with `model_validator`
   decorators for complex cross-field validation. This catches errors at construction time.

2. **NumPy RandomState per engine**: Each SimulationEngine instance holds its own
   `numpy.random.RandomState` initialized from the seed. No global random state is used.

3. **Config merge strategy**: User config files are deep-merged onto defaults. Only
   specified keys are overridden; unspecified keys retain their defaults.

4. **Strict parser + flexible models**: The YAML parser rejects unknown fields (catching
   typos early). The Pydantic models accept field aliases (for programmatic API use).

5. **Optional MCP dependency**: The `mcp_server.py` module uses `FastMCP` which is in
   an optional dependency group. Tests use `pytest.importorskip("mcp")`.

6. **Version resolution**: `__init__.py` tries `importlib.metadata.version("mcprojsim")`;
   falls back to reading version from `pyproject.toml` for source checkouts.

---

## 6. Algorithms

### 6.1 Monte Carlo Simulation Loop (Complete)

```python
def run_simulation(project, config, iterations, seed):
    rng = numpy.random.RandomState(seed)
    sampler = DistributionSampler(rng, config)
    risk_eval = RiskEvaluator(rng)
    scheduler = TaskScheduler(project, config)
    
    results = empty_arrays(iterations)
    
    for i in range(iterations):
        task_durations = {}
        task_costs = {}
        
        for task in project.tasks:
            # 1. Sample base duration
            base = sampler.sample(task.estimate, project.distribution)
            
            # 2. Convert units to hours
            hours_multiplied = base * unit_to_hours_factor(task.estimate.unit)
            
            # 3. Apply uncertainty factors (compound multiplier)
            uncertainty_mult = product_of_applicable_factors(task, config)
            adjusted = hours_multiplied * uncertainty_mult
            
            # 4. Evaluate task-level risks
            risk_time_impact, risk_cost_impact = risk_eval.evaluate(task.risks, adjusted)
            final_duration = adjusted + risk_time_impact
            
            task_durations[task.id] = final_duration
            # Cost: labor + fixed + risk
            task_costs[task.id] = compute_task_cost(final_duration, task, project)
        
        # 5. Schedule tasks
        schedule, diagnostics = scheduler.schedule(task_durations, rng)
        
        # 6. Project end time
        project_duration = max(schedule[tid]["end"] for tid in schedule)
        
        # 7. Project-level risks
        proj_risk_time, proj_risk_cost = risk_eval.evaluate(project.project_risks, project_duration)
        project_duration += proj_risk_time
        
        # 8. Store results
        results.durations[i] = project_duration
        results.effort[i] = sum(task_durations.values())
        # ... critical path, slack, costs, etc.
    
    return results
```

### 6.2 Shifted Log-Normal Fitting

```python
def fit_shifted_lognormal(low, expected, high, z):
    """
    Fit μ and σ for model: X = low + exp(Normal(μ, σ²))
    
    Interpretation:
      - low = minimum (shift)
      - expected = mode of the shifted distribution
      - high = z-th percentile of the shifted distribution
      - z = inverse CDF of the high percentile (e.g., 1.6449 for 95%)
    """
    shifted_mode = expected - low
    shifted_high = high - low
    log_ratio = log(shifted_high) - log(shifted_mode)
    
    sigma = (-z + sqrt(z*z + 4 * log_ratio)) / 2
    mu = log(shifted_mode) + sigma * sigma
    
    return mu, sigma
```

**Sampling**: `result = low + rng.lognormal(mu, sigma)`

### 6.3 Dependency-Only Scheduling

```python
def schedule_dependency_only(task_durations, topological_order, dependencies):
    schedule = {}
    for task_id in topological_order:
        start = max((schedule[dep]["end"] for dep in dependencies[task_id]), default=0.0)
        end = start + task_durations[task_id]
        schedule[task_id] = {"start": start, "end": end, "duration": task_durations[task_id]}
    return schedule
```

### 6.4 Resource-Constrained Scheduling (Event-Driven Greedy)

```python
def schedule_resource_constrained(task_durations, project, rng, task_priority=None):
    # Initialize resource states with calendars and sickness
    sickness_absence = generate_sickness(project.resources, rng, horizon)
    resource_states = build_availability(project.resources, project.calendars, sickness_absence)
    
    remaining = set(all_task_ids)
    active = []  # (end_time, task_id, assigned_resources)
    schedule = {}
    current_time = 0.0
    
    while remaining:
        # Release completed tasks
        for entry in active:
            if entry.end_time <= current_time + 1e-9:
                free_resources(entry.assigned)
                active.remove(entry)
        
        # Find dependency-ready tasks
        ready = [tid for tid in remaining if all_deps_satisfied(tid, schedule)]
        
        # Sort by priority
        if task_priority:
            ready.sort(key=lambda tid: (-task_priority.get(tid, 0.0), tid))
        else:
            ready.sort()  # Ascending task_id
        
        started_any = False
        for task_id in ready:
            eligible = find_eligible_free_resources(task_id, project)
            if not eligible:
                continue
            
            cap = practical_resource_cap(task_durations[task_id])
            assigned = eligible[:cap]
            
            # Find when resources are actually available
            actual_start = find_next_available_time(assigned, current_time)
            
            # Integrate effort over calendar windows
            end_time = compute_end_with_calendars(task_durations[task_id], assigned, actual_start)
            
            schedule[task_id] = {"start": actual_start, "end": end_time, ...}
            active.append((end_time, task_id, assigned))
            remaining.remove(task_id)
            started_any = True
        
        if not started_any and active:
            current_time = min(entry.end_time for entry in active)
    
    return schedule, diagnostics
```

### 6.5 Two-Pass Criticality Scheduling

```python
def run_two_pass(project, config, iterations, seed):
    # Pass 1: Greedy baseline
    pass1_iters = config.constrained_scheduling.pass1_iterations
    pass1_results = run_single_pass(project, config, pass1_iters, seed, priority=None)
    
    # Compute criticality index
    task_ci = {}
    for task_id, count in pass1_results.critical_path_frequency.items():
        task_ci[task_id] = count / pass1_iters
    
    # Pass 2: Priority-ordered, replay cached durations for first pass1_iters
    pass2_results = run_single_pass(project, config, iterations, seed,
                                     priority=task_ci,
                                     cached_durations=pass1_results.duration_cache)
    
    # Compute deltas
    trace = TwoPassDelta(pass1_stats, pass2_stats, task_ci)
    pass2_results.two_pass_trace = trace
    
    return pass2_results
```

### 6.6 Staffing Analysis

```python
def recommend_staffing(results, config, project):
    total_effort = results.total_effort_hours()  # or percentile-based
    critical_path_hours = results.percentile(50)  # median project duration
    max_parallel = results.max_parallel_tasks
    
    recommendations = {}
    for profile_name, profile in config.staffing.experience_profiles.items():
        best_size = 1
        best_duration = float('inf')
        
        for n in range(1, max_parallel + 1):
            ip = max(config.staffing.min_individual_productivity,
                     1.0 - profile.communication_overhead * (n - 1))
            effective_cap = n * ip * profile.productivity_factor
            duration = max(critical_path_hours, total_effort / effective_cap)
            
            if duration < best_duration:
                best_duration = duration
                best_size = n
            elif duration > best_duration:
                break  # Diminishing returns
        
        recommendations[profile_name] = StaffingRecommendation(
            team_size=best_size, calendar_hours=best_duration, ...)
    
    return recommendations
```

### 6.7 Critical Path Tracing

For each iteration, after scheduling:
```python
def trace_critical_paths(schedule, dependencies, project_end):
    # Find terminal tasks (tasks whose end == project_end)
    terminals = [tid for tid in schedule if abs(schedule[tid]["end"] - project_end) < 1e-9]
    
    paths = []
    for terminal in terminals:
        path = trace_backwards(terminal, schedule, dependencies)
        paths.append(tuple(path))
    
    return paths

def trace_backwards(task_id, schedule, dependencies):
    """Trace critical predecessors backwards from a terminal task."""
    path = [task_id]
    current = task_id
    while True:
        predecessors = dependencies[current]
        if not predecessors:
            break
        # Find predecessor whose end == current's start (tight coupling)
        critical_pred = max(predecessors, key=lambda p: schedule[p]["end"])
        if abs(schedule[critical_pred]["end"] - schedule[current]["start"]) < 1e-9:
            path.insert(0, critical_pred)
            current = critical_pred
        else:
            break
    return path
```

### 6.8 Sensitivity Analysis (Spearman Rank Correlation)

```python
def compute_sensitivity(task_durations_per_iteration, project_durations):
    """
    task_durations_per_iteration: Dict[task_id → np.ndarray of per-iteration durations]
    project_durations: np.ndarray of per-iteration total project durations
    """
    correlations = {}
    for task_id, task_durs in task_durations_per_iteration.items():
        if np.std(task_durs) < 1e-10:  # Constant array
            correlations[task_id] = 0.0
        else:
            r, _ = scipy.stats.spearmanr(task_durs, project_durations)
            correlations[task_id] = r
    return correlations
```

### 6.9 Sprint Velocity Sampling (Empirical)

```python
def sample_empirical_velocity(history, sprint_length_weeks, rng):
    # Find sprints with matching cadence
    matching = [h for h in history if h.sprint_length_weeks == sprint_length_weeks]
    
    if matching:
        # Direct resample from matching sprints
        idx = rng.randint(len(matching))
        return matching[idx].completed_units
    else:
        # Weekly fallback: normalize all to per-week rates, sample N weeks
        weekly_rates = [h.completed_units / h.sprint_length_weeks for h in history]
        total = sum(weekly_rates[rng.randint(len(weekly_rates))] for _ in range(sprint_length_weeks))
        return total
```

### 6.10 Sprint Spillover Model (Table)

```python
def sample_spillover(task, config, rng):
    """Determine if task spills over and how much is consumed."""
    points = task.get_planning_story_points()
    if points is None:
        return False, 1.0  # No spillover possible without size info
    
    # Find bracket
    normalized = points / config.spillover_size_reference_points
    probability = 0.0
    for bracket in config.size_brackets:
        if bracket.max_points is None or normalized <= bracket.max_points:
            probability = bracket.probability
            break
    
    # Roll for spillover
    if rng.random() >= probability:
        return False, 1.0  # Completed whole
    
    # Sample consumed fraction from Beta distribution
    consumed = rng.beta(config.consumed_fraction_alpha, config.consumed_fraction_beta)
    return True, consumed
```

---

## 7. CLI Interface Specification

### 7.1 Commands

#### `mcprojsim simulate`
Run Monte Carlo simulation on a project file.

**Arguments:**
- `PROJECT_FILE` (required): Path to YAML or TOML project file

**Options:**
| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--iterations, -n` | int | 10000 | Number of MC iterations |
| `--seed, -s` | int | None | Random seed for reproducibility |
| `--config, --config-file, -c` | path | auto-load | Config YAML path |
| `--output, -o` | path | None | Output file base path (without extension) |
| `--output-format, -f` | str | "json,csv,html" | Comma-separated export formats |
| `--verbose, -v` | flag | False | Detailed informational messages |
| `--quiet, -q` | count | 0 | `-q` suppresses details; `-qq` suppresses all normal output |
| `--table, -t` | flag | False | Format tabular output as ASCII tables |
| `--minimal, -m` | flag | False | Condensed output (version + summaries only) |
| `--minheader` | flag | False | Minimal two-line header |
| `--noheader` | flag | False | Suppress header block entirely |
| `--two-pass` | flag | False | Enable criticality two-pass scheduling |
| `--pass1-iterations` | int | 1000 | Iterations for pass-1 (if --two-pass) |
| `--critical-paths` | int | from config | Max path sequences to report |
| `--target-budget` | float | None | Budget target for confidence analysis |
| `--target-date` | date | None | Target completion date (YYYY-MM-DD) |
| `--velocity-model` | str | None | Override sprint velocity model |
| `--no-sickness` | flag | False | Disable sickness modeling |
| `--staffing` | flag | False | Show full staffing analysis table |
| `--tshirt-category` | str | None | Override default T-shirt size category |
| `--include-historic-base` | flag | False | Include historic base in HTML/JSON |
| `--number-bins` | int | from config | Number of histogram bins |
| `--full-cost-detail` | flag | False | Include per-iteration task costs in JSON |
| `--no-fx` | flag | False | Disable exchange rate fetches |
| `--progress, -p` | flag | False | Show progress bar during simulation |
| `--simtime, -S` | flag | False | Show elapsed time and peak memory |
| `--workers` | int/str | 1 | Worker processes (positive int or "auto") |

#### `mcprojsim validate`
Validate a project file without running simulation.

**Arguments:**
- `PROJECT_FILE` (required): Path to YAML or TOML file

**Options:**
- `--config, --config-file, -c`: Config YAML path
- `--verbose, -v`: Show full validation details

#### `mcprojsim generate`
Generate a YAML project file from natural language description.

**Arguments:**
- `INPUT_FILE` (required): Plain-text project description file

**Options:**
- `--output, -o`: Output YAML file path (default: stdout)
- `--validate-only`: Only validate description, don't generate YAML
- `--verbose, -v`: Show detailed messages

#### `mcprojsim config`
Show and manage configuration settings.

**Options:**
- `--config, --config-file, -c`: Config file path
- `--generate`: Write default config template to `~/.mcprojsim/config.yaml`
- `--list, --show`: List current configuration settings (default behavior)

### 7.2 Output Formatting Modes

The CLI supports multiple output verbosity and formatting combinations:

| Mode | Trigger | Behavior |
|------|---------|----------|
| Full (default) | no flags | All sections, full header, full detail |
| Verbose | `--verbose` | Adds uncertainty factor tables, series stats, correlations |
| Quiet level 1 | `-q` | Suppress detailed sections, keep summaries |
| Quiet level 2 | `-qq` | Suppress all normal output except errors |
| Minimal | `--minimal` | Version + project overview + confidence intervals only |
| Table | `--table` | ASCII table formatting (via `tabulate`, minimum width 70) |

Header control: `--minheader` (two-line separator) or `--noheader` (no header at all).

---

## 8. Output Format Specifications

### 8.1 JSON Output
Complete nested dictionary containing:
- `project`: metadata (name, start_date, num_tasks, distribution, t_shirt_category)
- `simulation`: parameters (iterations, seed, hours_per_day, schedule_mode)
- `statistics`: duration stats (mean, median, std_dev, min, max, CV, skewness, kurtosis)
- `confidence_intervals`: percentiles with hours, working days, delivery dates
- `effort_confidence_intervals`: effort percentiles (person-hours, person-days)
- `critical_path`: task criticality index
- `critical_path_sequences`: ranked path records with frequency
- `sensitivity`: Spearman correlations per task
- `schedule_slack`: mean float per task
- `risk_impact`: per-task risk statistics
- `histogram`: bin_edges and counts arrays
- `staffing`: recommendations + full table
- `cost` (if active): statistics, percentiles, task costs, sensitivity, budget analysis
- `sprint_planning` (if active): full sprint results
- `constrained_diagnostics` (if active): wait time, utilization, calendar delay
- `two_pass_trace` (if active): pass-1/pass-2 stats and deltas

### 8.2 CSV Output
Two-column format (Metric, Value) with section headers. Same data as JSON in flat tabular form.

### 8.3 HTML Output
Self-contained HTML report with:
- **Charts**: Matplotlib-generated PNG images embedded as base64 data URIs
- **Thermometer bars**: Colored probability gauges (red/yellow/green thresholds)
- **Tables**: Statistical summaries, confidence intervals, staffing, critical paths
- **Sections**: Simulation parameters, duration stats, effort stats, cost analysis,
  budget confidence, histograms (duration + effort + cost), sensitivity tornado chart,
  schedule slack, risk impact, constrained diagnostics, two-pass traceability,
  critical path sequences, staffing analysis, sprint burnup forecast

**Chart technology**: Matplotlib renders to PNG in memory; base64-encoded inline.
No JavaScript or external dependencies required to view the HTML report.

---

## 9. Validation Rules (Complete)

### 9.1 Project-Level
1. `project.name` must be non-empty string
2. `project.start_date` must be valid ISO 8601 date
3. `probability_red_threshold` < `probability_green_threshold`
4. `secondary_currencies` max 5 entries, each 3 uppercase letters
5. `hours_per_day` > 0
6. `overhead_rate` in [0, 3.0]
7. `fx_conversion_cost` in [0, 0.50]
8. `fx_overhead_rate` in [0, 1.0]

### 9.2 Task-Level
1. All task IDs must be unique
2. At least one task must be defined
3. All dependency references must point to existing task IDs
4. No circular dependencies (detected via DFS)
5. For explicit estimates: `low <= expected <= high`, `expected > 0`
6. For lognormal distribution: strict `low < expected < high`
7. `t_shirt_size` and `story_points` are mutually exclusive
8. Tasks with `t_shirt_size` or `story_points` MUST NOT specify `unit`
9. T-shirt size format: alphabetic tokens, optional `category.size` qualification
10. `max_resources` >= 1
11. `min_experience_level` in {1, 2, 3}
12. Task resource references must point to existing resources
13. At least one eligible resource must exist for each task's experience requirement

### 9.3 Risk-Level
1. `probability` in [0.0, 1.0]
2. Impact value > 0 (for RiskImpact objects)
3. `risk.id` must be non-empty

### 9.4 Resource-Level
1. Resource names must be unique (after normalization)
2. `availability` in (0.0, 1.0]
3. `experience_level` in {1, 2, 3}
4. `productivity_level` in [0.1, 2.0]
5. `sickness_prob` in [0.0, 1.0]
6. Resource calendar must reference an existing calendar
7. `hourly_rate` >= 0 (if specified)

### 9.5 Calendar-Level
1. Calendar IDs must be unique
2. `work_hours_per_day` > 0
3. Each `work_days` entry in {1, 2, 3, 4, 5, 6, 7}

### 9.6 Sprint Planning
1. `sprint_length_weeks` > 0
2. Exactly ONE of `completed_story_points` or `completed_tasks` per history entry
3. Field family must match `capacity_mode`
4. Minimum 2 usable history entries (positive delivery signal)
5. `sprint_id` values unique across history
6. `planning_confidence_level` in (0, 1)
7. Spillover size brackets in ascending order, last must be unbounded
8. If spillover enabled: all tasks must have resolvable `planning_story_points`
9. Future sprint overrides: at least one of `sprint_number` or `start_date` required
10. Future sprint dates must align to sprint boundaries

### 9.7 Cross-Cutting
1. If `team_size` > 0 and explicit resources > team_size: error
2. If `capacity_mode = "story_points"`: all tasks must have resolvable planning_story_points
3. Unknown/unrecognized YAML fields: rejected with line-number error

---

## 10. Implementation Gotchas and Pitfalls

This section documents non-obvious behaviors and mistakes encountered during implementation.
Any re-implementation should anticipate these issues.

### 10.1 Field Alias Mismatch
**Problem**: Pydantic field aliases (`min` → `low`, `max` → `high`) work at model
construction time but NOT in the YAML parser's strict field checking. Users writing
`min:` in YAML get "unknown field" errors even though the model would accept it.

**Resolution**: Document canonical field names clearly. Aliases exist for programmatic API
compatibility only.

### 10.2 Enum str() vs .value
**Problem**: Python's `str(SomeEnum.MEMBER)` includes the class name (e.g.,
`"RemovedWorkTreatment.churn_only"`). Using `.value` gives the clean string `"churn_only"`.

**Affected areas**: Any place enum values are displayed to users or written to output files
must use `.value`, not `str()`.

### 10.3 Click Flag Naming
**Problem**: Click's `@click.option("--config", "--config-file", "-c", "config_file", ...)`
syntax requires an explicit parameter name string (`"config_file"`) when the primary flag
name (`--config`) would collide with the Python function parameter name and cause a
TypeError.

**Resolution**: Always specify the explicit Python parameter name as a positional string
after all flag aliases.

### 10.4 Config Auto-Load Path
**Problem**: The auto-load config path is `~/.mcprojsim/config.yaml`. Early documentation
incorrectly referenced `configuration.yaml`.

**Rule**: The same path is used for both `config show --generate` (writes template) and
auto-load on startup.

### 10.5 Silent Two-Pass Fallback
**Problem**: Specifying `--two-pass` without named resources silently falls back to
single-pass with no warning, even in `--verbose` mode.

**Why**: Two-pass only affects resource assignment ORDER. Without resources, there's nothing
to reorder. But users may expect an error or warning.

### 10.6 STANDARD_HOURS_PER_DAY vs hours_per_day
**Problem**: Two different "hours per day" values exist:
- `STANDARD_HOURS_PER_DAY = 8.0` (constant, used for engine calculations and unit conversions)
- `project.hours_per_day` (configurable, used for OUTPUT display — working days calculation)

Risk percentage calculations, for example, always use 8.0 regardless of project setting.

### 10.7 Stale Output Concerns
**Problem**: HTML/JSON/CSV output is generated once after simulation. If the user changes
the project file and re-runs, old output files may still exist alongside new ones.

**Resolution**: Output files include timestamps. CLI overwrites same-named files.

### 10.8 Critical Path with Multiple Terminals
**Problem**: If multiple terminal tasks finish at exactly the same project end time,
ALL are traced as critical path origins. One iteration can produce multiple path branches.

**Impact**: Critical path sequence counts can sum to more than the number of iterations.
The frequency/criticality index per task remains valid (capped at 1.0).

### 10.9 Sprint Convergence Loop
**Problem**: Misconfigured sprint planning (e.g., tasks with unmet dependencies that
can never become ready) can cause infinite simulation loops.

**Protection**: Hard limit at 10,000 sprints per iteration raises ValueError.

### 10.10 Lognormal Degenerate Cases
**Problem**: If `low == expected` or `expected == high`, the lognormal fit produces
`sigma = 0` or invalid parameters.

**Validation**: Lognormal requires STRICT inequality `low < expected < high`.
The validator rejects degenerate cases at parse time.

### 10.11 Config Merge vs Replace
**Problem**: Early implementations replaced the entire config structure when a user config
file was loaded, losing all defaults for unspecified sections.

**Resolution**: Deep merge strategy — only keys present in the user config file are
overridden. All other keys retain their built-in defaults.

### 10.12 Resource Productivity vs Availability
**Problem**: Both `availability` and `productivity_level` affect effective work rate,
but they're distinct concepts:
- `availability`: Fraction of time allocated to this project (e.g., 0.5 = half-time)
- `productivity_level`: Individual efficiency multiplier (e.g., 1.1 = 10% above average)

Both multiply together for effective capacity:
`effective_rate = availability × productivity_level × work_hours_per_day`

### 10.13 Calendar Delay Interpretation
**Problem**: Users see large "calendar delay" with zero "resource wait time" and are confused.

**Explanation**: Calendar delay accumulates ALL non-work time (weekends, holidays, sickness)
that falls within the project span, regardless of whether resources were actually waiting.
Resource wait time only measures the gap between dependency satisfaction and resource
availability.

### 10.14 T-shirt Size Token Validation
**Problem**: T-shirt size values like `"3XL"` or `"M1"` are rejected because the validator
requires purely alphabetic tokens (with optional dashes/dots for category qualification).

**Allowed formats**: `XS`, `S`, `M`, `L`, `XL`, `XXL`, `story.M`, `bug.S`, `epic-L`

### 10.15 Sprint Planning Story Points Requirement
**Problem**: When `capacity_mode = "story_points"` and spillover is enabled, ALL tasks
must have resolvable `planning_story_points`. This means either:
- Task has explicit `planning_story_points` field, OR
- Task estimate uses `story_points` (falls back to that value)

Tasks with only T-shirt sizes or explicit estimates will cause a validation error.

---

## 11. Technology Stack

### 11.1 Core Dependencies
- **Python**: 3.13+ (uses modern typing features)
- **NumPy**: 1.24+ (random sampling, array operations)
- **SciPy**: 1.10+ (statistics: spearmanr, skew, kurtosis, NormalDist)
- **Pandas**: 2.0+ (data manipulation in exporters)
- **PyYAML**: 6.0+ (YAML parsing with custom loader)
- **Pydantic**: 2.0+ (data validation, settings management)
- **Click**: 8.0+ (CLI framework)
- **Matplotlib**: 3.7+ (chart rendering for HTML export)

### 11.2 Optional Dependencies
- **FastMCP**: MCP server implementation (stdio transport)
- **tomli / tomli-w**: TOML parsing/writing

### 11.3 Development Dependencies
- **pytest**: 7.0+ (testing)
- **pytest-cov**: 4.0+ (coverage)
- **pytest-xdist**: parallel test execution (`-n auto`)
- **black**: 23.0+ (formatting)
- **mypy**: 1.0+ (strict type checking)
- **flake8**: 6.0+ (linting)
- **Poetry**: package management (with `poetry.toml` for in-project virtualenvs)

### 11.4 Documentation Dependencies
- **MkDocs**: 1.5+ (site generator)
- **mkdocs-material**: 9.0+ (Material theme)
- **mkdocstrings**: 0.22+ (API documentation)

---

## 12. Implementation Plan

This plan is ordered by dependencies between components. Each phase produces testable,
independently verifiable deliverables.

### Phase 1: Foundation
**Goal**: Minimal working simulation with triangular distribution.

1. **Project models** (Pydantic v2): Project, ProjectMetadata, Task, TaskEstimate, Risk
2. **YAML parser** with line-number tracking and strict field validation
3. **Distribution sampler**: Triangular distribution
4. **Dependency resolver**: Topological sort (Kahn's algorithm)
5. **Simulation engine**: Basic MC loop (sample → schedule → aggregate)
6. **Dependency-only scheduler**: Earliest-start-time algorithm
7. **Risk evaluator**: Probability roll + absolute/percentage impact
8. **Basic statistics**: Mean, median, percentiles
9. **JSON exporter**: Serialize results
10. **CLI**: `simulate` and `validate` commands

**Verification**: Run 10,000 iterations on a 5-task project, verify deterministic with seed.

### Phase 2: Analysis & Reporting
**Goal**: Full statistical analysis and rich output.

1. **Sensitivity analysis**: Spearman rank correlation
2. **Critical path analysis**: Per-task frequency + full path sequences
3. **Schedule slack** computation
4. **Histogram** generation
5. **CSV exporter**
6. **HTML exporter** with Matplotlib charts
7. **Uncertainty factors**: Compound multiplier system
8. **Configuration system**: Config class with all defaults, merge strategy, auto-load

**Verification**: Sensitivity correlations match expected patterns (long tasks on critical path → high r).

### Phase 3: Symbolic Estimation
**Goal**: Support T-shirt sizes and story points.

1. **T-shirt size mappings**: 5 categories × 6 sizes, config-driven
2. **Story point mappings**: 7 point values, config-driven
3. **Category qualification**: `category.size` format parsing
4. **Mutual exclusion validation**: t_shirt_size XOR story_points XOR explicit
5. **Unit inference**: Symbolic estimates derive unit from config, reject explicit unit

**Verification**: T-shirt "M" produces duration in expected range. Mixing t_shirt + unit → error.

### Phase 4: Lognormal Distribution
**Goal**: Alternative distribution with shifted log-normal fitting.

1. **Fit algorithm**: μ, σ derivation from three-point + z-score
2. **Configurable high percentile**: 70–99 with z-score lookup
3. **Validation**: Strict inequality requirement for lognormal
4. **Per-task distribution override**: Task-level overrides project default

**Verification**: Lognormal samples are right-skewed with mode ≈ expected.

### Phase 5: Resource-Constrained Scheduling
**Goal**: Calendar-aware scheduling with resource pools.

1. **Resource model**: Name, availability, calendar, experience, productivity
2. **Calendar model**: Work hours, work days, holidays
3. **Resource assignment**: Greedy, experience-filtered, auto-capped
4. **Calendar integration**: Effort-over-time accumulation
5. **Sickness simulation**: Stochastic per-resource absence
6. **Planned absence**: Fixed dates
7. **team_size** auto-generation
8. **Scheduling diagnostics**: Wait time, utilization, calendar delay

**Verification**: Resource-constrained schedule is always >= dependency-only schedule.

### Phase 6: Two-Pass Scheduling
**Goal**: Criticality-prioritized resource assignment.

1. **Pass-1 infrastructure**: Criticality index computation
2. **Duration cache**: Store per-iteration durations for deterministic replay
3. **Pass-2 priority ordering**: (-criticality, task_id) sort
4. **Traceability output**: Pass-1/Pass-2 deltas

**Verification**: Pass-2 P90 ≤ Pass-1 P90 (or equal) on typical projects.

### Phase 7: Cost Estimation
**Goal**: Full monetary cost modeling.

1. **Cost activation logic**: Detect when cost calculation is needed
2. **Rate resolution**: Per-resource rates, project default, mean for multi-resource
3. **Fixed costs and risk cost impacts**
4. **Overhead calculation**: Labor-only markup
5. **Budget confidence analysis**: P(cost ≤ target), Wilson CI, budget-for-confidence
6. **Secondary currencies**: FX rates display
7. **Cost sensitivity**: Correlation analysis
8. **Cost output**: JSON/CSV/HTML integration

**Verification**: Total cost = sum(task_labor) + sum(fixed) + sum(risk_cost) + overhead_on_labor.

### Phase 8: Sprint Planning
**Goal**: Monte Carlo sprint forecasting.

1. **Sprint planning model**: All SprintPlanningSpec fields
2. **History normalization**: holiday_factor adjustment
3. **Velocity sampling**: Empirical (matching + weekly fallback)
4. **Sprint simulation loop**: Pull tasks, track backlog, convergence check
5. **Spillover model**: Table + logistic + Beta consumed fraction
6. **Sickness in sprints**: Per-person binomial + lognormal duration
7. **Disruption overlay**: Stochastic capacity reduction
8. **Future sprint overrides**: Capacity multiplier matching
9. **Negative binomial velocity model**: Method-of-moments fitting
10. **Burnup tracking**: Cumulative percentile computation
11. **Sprint results**: Full diagnostics output

**Verification**: Sprint count decreases with higher velocity history.

### Phase 9: Natural Language & MCP
**Goal**: NL input and MCP protocol support.

1. **NL parser**: Task extraction, fuzzy matching, prose estimate recognition
2. **YAML generator**: NL → valid YAML
3. **Generate CLI command**
4. **MCP server**: FastMCP with all 7 tools
5. **Update tool**: Merge NL changes into existing YAML

**Verification**: Generated YAML passes `validate`. Round-trip NL → YAML → simulate works.

### Phase 10: Staffing Analysis & Polish
**Goal**: Team size optimization and final output polish.

1. **Staffing algorithm**: Brooks's Law model with profiles
2. **Staffing recommendations**: Find optimal per profile
3. **Staffing table**: Full grid in output
4. **HTML thermometer charts**: Probability visualization
5. **Effort vs duration distinction**: Separate tracking and reporting
6. **TOML parser**: Alternative input format
7. **Distribution shape stats**: Skewness, kurtosis
8. **Documentation**: Complete user guide, grammar reference

**Verification**: Recommended team size produces minimum calendar duration for each profile.

---

## 13. Future Enhancements (Out of Scope)

1. Correlation between task durations (currently assumes independence)
2. Resource leveling optimization (currently greedy, not globally optimal)
3. Multi-project portfolio analysis
4. Integration with Jira/Azure DevOps for history import
5. Real-time progress tracking vs. baseline
6. Machine learning for improved estimate calibration
7. Web-based UI (design document exists at `design-ideas/ui-design.md`)
8. Weather/external factor modeling
9. Per-resource contributed-hours tracking for multi-resource cost allocation
10. Automatic FX rate fetching (currently manual rates only)
11. PERT distribution as alternative to triangular/lognormal

---

## 14. References

- *Software Estimation: Demystifying the Black Art* by Steve McConnell
- *The Mythical Man-Month* by Frederick Brooks
- *How to Measure Anything in Cybersecurity Risk* by Douglas Hubbard
- NIST Guide for Risk Analysis
- PMI PMBOK Guide (7th Edition)
- Monte Carlo methods in project management (PMI white papers)
- Brooks's Law: communication overhead = n(n-1)/2 (simplified to linear per-person model)

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-10-23 | Initial | Initial specification |
| 2.0 | 2025-07-21 | Review | Complete rewrite: added cost, sprint planning, NL/MCP, staffing, gotchas, implementation plan. Updated all sections to match actual v0.15.0 implementation. |



**End of Specification**
