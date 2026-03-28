# Resource and Calendar Constrained Scheduling

This chapter shows how to model and run **resource- and calendar-constrained** simulations in `mcprojsim`, starting from a simple project and building up to a full-featured example.

Constrained scheduling is activated automatically when the validated project has resources available for assignment—either from a top-level `resources` section or from `project.team_size > 0` (which auto-generates default resources up to that size).

## What constrained scheduling changes

In dependency-only mode, tasks start as soon as dependencies are complete.

In constrained mode, task start and completion times also depend on:

- resource availability,
- resource experience and productivity,
- task-level resource requirements,
- working calendars and holidays,
- planned absences and sickness probability.

The CLI and exporters report this explicitly via:

- `Schedule Mode` (`dependency_only` or `resource_constrained`),
- constrained diagnostics (resource wait time, utilization, calendar delay contribution).



## How `team_size` affects scheduling

`team_size` and top-level `resources` interact during validation before simulation starts.

Current rules:

- `team_size` omitted or `0`: use only explicitly listed `resources`.
- `team_size > 0` and explicit resources **exceed** `team_size`: validation error.
- `team_size > 0` and explicit resources are **fewer** than `team_size`: default resources are auto-created up to `team_size`.
- no `resources` and no `team_size` (or `team_size: 0`): scheduler remains dependency-only.

### Example A: tasks only (no `team_size`)

```yaml
project:
  name: "Team Size Demo"
  start_date: "2026-04-01"
  hours_per_day: 8

tasks:
  - id: "task_001"
    name: "Task 1"
    estimate: { low: 8, expected: 16, high: 24 }
  - id: "task_002"
    name: "Task 2"
    estimate: { low: 40, expected: 64, high: 96 }
    dependencies: ["task_001"]
```

### Example B: same tasks, with `team_size`

```yaml
project:
  name: "Team Size Demo"
  start_date: "2026-04-01"
  hours_per_day: 8
  team_size: 10

tasks:
  - id: "task_001"
    name: "Task 1"
    estimate: { low: 8, expected: 16, high: 24 }
  - id: "task_002"
    name: "Task 2"
    estimate: { low: 40, expected: 64, high: 96 }
    dependencies: ["task_001"]
```

Sample output excerpt (seed `42`, `200` iterations):

```text
Schedule Mode: resource_constrained
Median (P50): 529.86 hours
```

`team_size: 10` auto-creates 10 default resources, so this run is constrained.

### Example C: explicit `resources` + `team_size` (smaller than resources)

```yaml
project:
  name: "Team Size + Resources"
  start_date: "2026-04-01"
  hours_per_day: 8
  team_size: 1

tasks:
  - id: "task_001"
    name: "Task 1"
    estimate: { low: 8, expected: 16, high: 24 }
  - id: "task_002"
    name: "Task 2"
    estimate: { low: 40, expected: 64, high: 96 }
    dependencies: ["task_001"]

resources:
  - name: "alice"
    experience_level: 3
    productivity_level: 1.0
  - name: "bob"
    experience_level: 2
    productivity_level: 0.9
```

Sample output excerpt:

```text
Error: Invalid project file format: 1 validation error for Project
  Value error, team_size is smaller than explicitly specified resources: team_size=1, resources=2
```

### Example D: explicit `resources` + `team_size` (larger than resources)

Same as Example C but with `team_size: 20`.

Sample output excerpt (same run settings):

```text
Schedule Mode: resource_constrained
Median (P50): 529.86 hours
```

`team_size: 20` is valid here: two explicit resources are kept and the remaining capacity is auto-filled with defaults.

### Interpretation and policy

- `team_size` is a capacity target when greater than zero.
- Explicit `resources` can be combined with `team_size`, but they must not exceed it.
- If explicit resources are fewer than `team_size`, generated defaults fill the gap.
- If both are omitted (or `team_size: 0` with no resources), the run is dependency-only.



## Example 1: Baseline (dependency-only)

Start with a minimal project that has dependencies but no resource section.

```yaml
project:
  name: "Onboarding Portal"
  start_date: "2026-04-01"
  hours_per_day: 8

tasks:
  - id: "task_001"
    name: "Requirements"
    estimate: { low: 8, expected: 16, high: 24 }

  - id: "task_002"
    name: "Implementation"
    estimate: { low: 40, expected: 64, high: 96 }
    dependencies: ["task_001"]
```

Run:

```bash
mcprojsim simulate baseline.yaml --seed 42 --table
```

You should see `Schedule Mode: dependency_only`.

Sample output excerpt (seed `42`, `200` iterations):

```text
Schedule Mode: dependency_only
Calendar Time Confidence Intervals:
  P50: 129.86 hours (17 working days)  (2026-04-24)
  P90: 155.97 hours (20 working days)  (2026-04-29)
  P99: 170.61 hours (22 working days)  (2026-05-01)
```



## Resource fields introduced in this chapter

Before Example 2, here is a quick reference for the `resources` fields used throughout the walkthrough.

| Field | Required | Default | What it controls |
|---|---|---|---|
| `name` | No | auto-generated (`resource_001`, ...) | Stable resource identifier used by tasks |
| `availability` | No | `1.0` | Fractional availability (for example `0.8` for 80%) |
| `experience_level` | No | `2` | Skill level (`1`, `2`, or `3`) used with `min_experience_level` |
| `productivity_level` | No | `1.0` | Relative throughput multiplier (valid range `0.1` to `2.0`) |
| `calendar` | No | `default` | Which calendar (`calendars[*].id`) the resource follows |
| `sickness_prob` | No | `0.0` | Daily sickness probability for stochastic absence |
| `planned_absence` | No | `[]` | Explicit non-working dates for that resource |


### First two fields introduced in Example 2

- `experience_level`: the resource's capability tier (`1`, `2`, `3`).
- `productivity_level`: how quickly the resource converts effort into progress relative to baseline `1.0`.

In Example 2, Alice (`3`, `1.0`) is modeled as more senior baseline-capacity, while Bob (`2`, `0.9`) is slightly less productive.


## Task fields related to resources introduced in this chapter

| Field | Required | Default | What it controls |
|---|---|---|---|
| `max_resources` | No | 1 | Maximum number of resources assigned to a task |


### `max_resources` semantics (important)

`max_resources` is an upper bound on concurrent assignees for a task, but the
scheduler also applies an automatic practical cap.

- If `resources` lists multiple names and `max_resources` is smaller than that list,
  only up to `max_resources` resources are assigned at task start.

Automatic practical cap heuristic:

- `granularity_cap = max(1, floor(task_effort_hours / 4.0))`
- `coordination_cap = 6`
- `practical_cap = min(granularity_cap, coordination_cap)`

Effective assignment count at start is:

  `min(max_resources, practical_cap, currently_available_eligible_resources)`

- If `max_resources` is omitted, the default is `1`.

Why this exists:

- It prevents unrealistic compression of small tasks (for example, assigning eight people to an ~8–24 hour task).
- It keeps behavior deterministic while limiting over-parallelization on large tasks.

Practical examples:

- Task effort `8h` → `granularity_cap = floor(8/4) = 2` → at most 2 assignees.
- Task effort `24h` → `granularity_cap = floor(24/4) = 6` → at most 6 assignees.
- Task effort `80h` → `granularity_cap = 20`, but coordination cap still limits to 6.

Why these constants were selected:

- `MIN_EFFORT_PER_ASSIGNEE_HOURS = 4.0` uses a half-day work chunk as a practical lower bound for productive splitting. It avoids pathological cases where many assignees are allocated to very small tasks.
- `MAX_ASSIGNEES_PER_TASK = 6` is a conservative coordination ceiling. It reflects diminishing returns from communication/synchronization overhead when too many people are placed on one task.
- The pair balances realism and runtime simplicity: the scheduler remains deterministic and fast while avoiding implausible near-linear speedups.

If you need stricter or looser behavior in your environment, these constants can be adjusted in the scheduler implementation and validated with scenario-specific simulations.

### Assignment timing model

Resource assignment is performed only when the task starts.

- Assigned resources remain fixed for that task run (non-preemptive execution).
- The scheduler does not swap or add resources mid-task.

### Start-now vs wait-for-more-resources behavior

Current automatic assignment is greedy:

- If at least one eligible resource is available, the task can start immediately.
- The scheduler does not delay task start to wait for additional resources that might become
  available later.

This is a deliberate trade-off for deterministic and scalable simulation on large projects.
This avoids combinatorial explosion and keeps runtime predictable for large projects. 
It is a heuristic, not globally optimal schedule optimization.




## Example 2: Add resources (single-pass automatic assignment)

Now add a top-level `resources` section. This enables constrained scheduling.

```yaml
project:
  name: "Onboarding Portal"
  start_date: "2026-04-01"
  hours_per_day: 8

tasks:
  - id: "task_001"
    name: "Requirements"
    estimate: { low: 8, expected: 16, high: 24 }

  - id: "task_002"
    name: "Implementation"
    estimate: { low: 40, expected: 64, high: 96 }
    dependencies: ["task_001"]

resources:
  - name: "alice"
    experience_level: 3
    productivity_level: 1.0

  - name: "bob"
    experience_level: 2
    productivity_level: 0.9
```

Run:

```bash
mcprojsim simulate resources-basic.yaml --seed 42 --table
```

Sample output excerpt (seed `42`, `200` iterations):

```text
Schedule Mode: resource_constrained
Calendar Time Confidence Intervals:
  P50: 529.86 hours (67 working days)  (2026-07-03)
  P90: 651.97 hours (82 working days)  (2026-07-24)
  P99: 698.61 hours (88 working days)  (2026-08-03)

Constrained Schedule Diagnostics:
  Calendar Delay Contribution: 404.16 hours
```

### How resources are used in Example 2

In this example, tasks do **not** define `tasks[*].resources`, so each ready task can use the full resource pool:

- `alice`
- `bob`

Assignment behavior in this case is:

1. A task becomes eligible only after all dependencies are finished.
2. If the task has no explicit `resources` list, the scheduler considers **all** project resources.
3. Resources already busy on other tasks are not available (a resource can only work on one task at a time).
4. The task receives up to `max_resources` resources (default is `1` if omitted).
5. If no eligible resource is free, the task waits; this contributes to `Average Resource Wait` in diagnostics.

Because `max_resources` defaults to `1`, each task in Example 2 is effectively assigned one resource at a time unless you override it on the task.

### Why `experience_level` and `productivity_level` matter here

- `experience_level` on each resource is matched against task `min_experience_level` (default task minimum is `1`).
- `productivity_level` affects effective capacity, so two resources with different productivity can produce different calendar durations even for the same effort.

### Making assignment explicit (optional)

If you want explicit control instead of automatic pooling, set `tasks[*].resources`:

```yaml
tasks:
  - id: "task_001"
    name: "Requirements"
    estimate: { low: 8, expected: 16, high: 24 }
    resources: ["alice"]

  - id: "task_002"
    name: "Implementation"
    estimate: { low: 40, expected: 64, high: 96 }
    dependencies: ["task_001"]
    resources: ["alice", "bob"]
    max_resources: 2
```

In that explicit form, only listed resources are considered for each task.

Look for:

- `Schedule Mode: resource_constrained`
- `Constrained Schedule Diagnostics`
  - Average Resource Wait (hours)
  - Effective Resource Utilization
  - Calendar Delay Contribution (hours)



## Example 3: Add working calendars

Attach resources to calendars and define working patterns.

```yaml
project:
  name: "Onboarding Portal"
  start_date: "2026-04-01"
  hours_per_day: 8

tasks:
  - id: "task_001"
    name: "Requirements"
    estimate: { low: 8, expected: 16, high: 24 }
  - id: "task_002"
    name: "Implementation"
    estimate: { low: 40, expected: 64, high: 96 }
    dependencies: ["task_001"]

resources:
  - name: "alice"
    calendar: "default"
    experience_level: 3
    productivity_level: 1.0
  - name: "bob"
    calendar: "part_time"
    experience_level: 2
    productivity_level: 0.9

calendars:
  - id: "default"
    work_hours_per_day: 8
    work_days: [1, 2, 3, 4, 5]
    holidays: ["2026-04-10"]

  - id: "part_time"
    work_hours_per_day: 6
    work_days: [1, 2, 3, 4]
    holidays: []
```

This introduces calendar-driven delays automatically (weekends, holidays, shorter days).

Sample output excerpt (seed `42`, `200` iterations):

```text
Schedule Mode: resource_constrained
Calendar Time Confidence Intervals:
  P50: 553.86 hours (70 working days)  (2026-07-08)
  P90: 675.97 hours (85 working days)  (2026-07-29)
  P99: 722.61 hours (91 working days)  (2026-08-06)

Constrained Schedule Diagnostics:
  Calendar Delay Contribution: 437.28 hours
```

Compared with Example 2, the added holiday and part-time calendar increase calendar-time percentiles and calendar-delay contribution.

### Quick comparison (Examples 1 → 3)

The table below compares calendar-time percentiles from the sample runs above (seed `42`, `200` iterations):

| Example | Schedule Mode | P50 (hours) | P90 (hours) | P99 (hours) |
|---|---|---:|---:|---:|
| Example 1 (dependency-only) | `dependency_only` | 129.86 | 155.97 | 170.61 |
| Example 2 (resources only) | `resource_constrained` | 529.86 | 651.97 | 698.61 |
| Example 3 (resources + calendars) | `resource_constrained` | 553.86 | 675.97 | 722.61 |

This progression highlights how resource constraints and then calendar constraints increase elapsed calendar time, even when effort distributions are unchanged.



## Example 4: Add sickness and planned absence

Sickness has three related configuration layers:

- `constrained_scheduling.sickness_prob` is the default per-resource sickness probability used when a resource omits `sickness_prob`,
- `resources[*].sickness_prob` controls/overrides probability for that specific resource,
- `sprint_defaults.sickness.duration_log_mu` and `sprint_defaults.sickness.duration_log_sigma` control the shared log-normal duration model used when sickness occurs.

Explicit days off are set with `planned_absence`.

```yaml
resources:
  - name: "alice"
    calendar: "default"
    experience_level: 3
    productivity_level: 1.0
    sickness_prob: 0.02
    planned_absence: ["2026-04-22"]

  - name: "bob"
    calendar: "part_time"
    experience_level: 2
    productivity_level: 0.9
    sickness_prob: 0.04
    planned_absence: ["2026-04-15", "2026-04-16"]
```

!!! note
    `resources[*].sickness_prob` is configured in the project file per resource. If omitted, constrained scheduling falls back to `constrained_scheduling.sickness_prob` from the config file. If neither is set, the effective default remains `0.0`.

### Optional config for default sickness probability

```yaml
constrained_scheduling:
  sickness_prob: 0.03
```

With this setting:

- resources with explicit `sickness_prob` keep their own value,
- resources without `sickness_prob` use `0.03`,
- omitting this config block keeps the legacy `0.0` default.

### Optional config for sickness duration

If you want the constrained scheduler to assume shorter or longer sickness episodes, add this to your config file and run with `--config`:

```yaml
sprint_defaults:
  sickness:
    duration_log_mu: 1.10
    duration_log_sigma: 0.90
```

This does not change who gets sick. It changes how long an absence tends to last once a sickness event occurs.

!!! note
    The duration parameters (`duration_log_mu` and `duration_log_sigma`) are configured once under `sprint_defaults.sickness` and apply to **both constrained scheduling and sprint planning**. This ensures consistent absence duration modeling across both forecasting modes. Sickness probabilities, however, have separate mode-specific defaults: `constrained_scheduling.sickness_prob` (constrained mode only) and `sprint_defaults.sickness.probability_per_person_per_week` (sprint planning only).



## Example 5: Add task-level resource constraints

Use task fields to control assignment behavior:

- `resources`: restrict eligible resources by name,
- `max_resources`: cap parallel resources assigned to a task,
- `min_experience_level`: minimum allowed experience (`1`, `2`, `3`).

```yaml
tasks:
  - id: "task_003"
    name: "Data migration"
    estimate: { low: 24, expected: 40, high: 64 }
    dependencies: ["task_002"]
    resources: ["alice"]
    max_resources: 1
    min_experience_level: 3

  - id: "task_004"
    name: "System testing"
    estimate: { low: 16, expected: 24, high: 40 }
    dependencies: ["task_003"]
    resources: ["alice", "bob"]
    max_resources: 2
    min_experience_level: 2
```

### Compact recap: how assignment works in Example 5

- `task_003` can only use `alice` (`resources: ["alice"]`) and is capped at one resource (`max_resources: 1`).
- `task_004` can use either `alice` or `bob`, and can run with up to two resources in parallel (`max_resources: 2`) when both are available.
- `min_experience_level` filters the eligible set before assignment (for example, tasks requiring `3` cannot use level-`2` resources).
- If fewer resources are available than requested by `max_resources`, the task starts with what is available (if at least one eligible resource exists) and continues with reduced effective capacity.

This is the first point in the walkthrough where `max_resources` is actively overridden above the default (`1`) to allow multi-resource task execution.



## Example 6: Full constrained project (final build-up)

This example combines core project fields, risks, uncertainty factors, resource constraints, calendars, absences, and sickness.

```yaml
project:
  name: "Commerce Platform Upgrade"
  description: "Backend modernization with staged rollout"
  start_date: "2026-05-04"
  confidence_levels: [50, 80, 90, 95]
  hours_per_day: 8
  probability_red_threshold: 0.5
  probability_green_threshold: 0.9

project_risks:
  - id: "risk_vendor"
    name: "Vendor API latency"
    probability: 0.2
    impact: 16
    impact_unit: "hours"

tasks:
  - id: "task_001"
    name: "Architecture design"
    estimate: { low: 16, expected: 24, high: 40 }
    uncertainty_factors:
      team_experience: medium
      technical_complexity: medium

  - id: "task_002"
    name: "Core implementation"
    estimate: { low: 80, expected: 120, high: 180 }
    dependencies: ["task_001"]
    resources: ["alice", "bob", "carol"]
    max_resources: 2
    min_experience_level: 2
    risks:
      - id: "risk_rework"
        name: "Unexpected rework"
        probability: 0.25
        impact: 24
        impact_unit: "hours"

  - id: "task_003"
    name: "Migration"
    estimate: { low: 40, expected: 64, high: 96 }
    dependencies: ["task_002"]
    resources: ["alice"]
    max_resources: 1
    min_experience_level: 3

  - id: "task_004"
    name: "Verification and rollout"
    estimate: { low: 24, expected: 40, high: 64 }
    dependencies: ["task_003"]
    resources: ["alice", "bob", "carol"]
    max_resources: 2

resources:
  - name: "alice"
    calendar: "default"
    availability: 1.0
    experience_level: 3
    productivity_level: 1.1
    sickness_prob: 0.02
    planned_absence: ["2026-05-15"]

  - name: "bob"
    calendar: "default"
    availability: 0.8
    experience_level: 2
    productivity_level: 1.0
    sickness_prob: 0.03

  - name: "carol"
    calendar: "part_time"
    availability: 0.75
    experience_level: 2
    productivity_level: 0.9
    sickness_prob: 0.04
    planned_absence: ["2026-06-01", "2026-06-02"]

calendars:
  - id: "default"
    work_hours_per_day: 8
    work_days: [1, 2, 3, 4, 5]
    holidays: ["2026-05-25"]

  - id: "part_time"
    work_hours_per_day: 6
    work_days: [1, 2, 3, 4]
    holidays: []
```

Run and export all formats:

```bash
mcprojsim validate constrained-full.yaml
mcprojsim simulate constrained-full.yaml \
  --iterations 30000 \
  --seed 42 \
  --table \
  --critical-paths 5 \
  -f json,csv,html \
  -o results/constrained-full
```



## Single-pass vs double-pass assignment

### Single-pass automatic assignment (available)

Current constrained scheduling uses deterministic single-pass assignment while respecting dependencies, resource eligibility, calendars, and absences.

You use it by defining top-level `resources` (and optionally `calendars`). No extra CLI flag is required.

### Double-pass automatic assignment (status)

A dedicated double-pass criticality-prioritized assignment mode is documented in requirements (`FR-042`) but is **not currently exposed as a CLI/config toggle** in this release.

Practical workaround today:

1. Run a baseline simulation and inspect critical-path frequency.
2. Tighten task-level resource constraints (`resources`, `max_resources`, `min_experience_level`) for the highest-criticality tasks.
3. Re-run and compare constrained diagnostics and completion percentiles.



## CLI options most relevant to constrained runs

Use these with `mcprojsim simulate`:

| Option | Why it matters for constrained scheduling |
|---|---|
| `-n`, `--iterations` | More iterations stabilize constrained diagnostics and tail percentiles |
| `-s`, `--seed` | Makes resource/sickness-driven runs reproducible |
| `-c`, `--config` | Apply custom uncertainty and output/reporting defaults |
| `--critical-paths` | Show more critical-path sequences for bottleneck analysis |
| `-t`, `--table` | Easier reading of diagnostics and interval tables |
| `-f json,csv,html` | Export constrained diagnostics to all report channels |
| `-o` | Keep scenario outputs organized for side-by-side comparison |
| `--target-date` | Evaluate on-time probability against a concrete deadline |



## Where to configure constrained behavior

### In the project file (primary for constrained scheduling)

- `resources[*].availability`
- `resources[*].productivity_level`
- `resources[*].experience_level`
- `resources[*].calendar`
- `resources[*].sickness_prob`
- `resources[*].planned_absence`
- `calendars[*].work_hours_per_day`
- `calendars[*].work_days`
- `calendars[*].holidays`
- `tasks[*].resources`
- `tasks[*].max_resources`
- `tasks[*].min_experience_level`

### In the config file (`--config`)

Use config files for simulation/reporting defaults and shared stochastic model parameters. They do **not** replace per-resource sickness probabilities in the project file, but they can now define the shared sickness-duration distribution used by constrained scheduling.

Example:

```yaml
constrained_scheduling:
  sickness_prob: 0.03

simulation:
  default_iterations: 30000

output:
  critical_path_report_limit: 5
  histogram_bins: 80

staffing:
  effort_percentile: 80

sprint_defaults:
  sickness:
    duration_log_mu: 1.10
    duration_log_sigma: 0.90
```



## Related chapters

- [Project Files](project_files.md) for full schema reference
- [Running Simulations](running_simulations.md) for command reference
- [Interpreting Results](interpreting_results.md) for diagnostics interpretation

\newpage
