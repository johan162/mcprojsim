# Resource and Calendar Constrained Scheduling

This chapter shows how to model and run **resource- and calendar-constrained** simulations in `mcprojsim`, starting from a simple project and building up to a full-featured example.

Constrained scheduling is activated automatically when a project file contains a top-level `resources` section.

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

---

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
    estimate: { min: 8, most_likely: 16, max: 24 }

  - id: "task_002"
    name: "Implementation"
    estimate: { min: 40, most_likely: 64, max: 96 }
    dependencies: ["task_001"]
```

Run:

```bash
mcprojsim simulate baseline.yaml --seed 42 --table
```

You should see `Schedule Mode: dependency_only`.

---

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

---

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
    estimate: { min: 8, most_likely: 16, max: 24 }

  - id: "task_002"
    name: "Implementation"
    estimate: { min: 40, most_likely: 64, max: 96 }
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
    estimate: { min: 8, most_likely: 16, max: 24 }
    resources: ["alice"]

  - id: "task_002"
    name: "Implementation"
    estimate: { min: 40, most_likely: 64, max: 96 }
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

---

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
    estimate: { min: 8, most_likely: 16, max: 24 }
  - id: "task_002"
    name: "Implementation"
    estimate: { min: 40, most_likely: 64, max: 96 }
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

---

## Example 4: Add sickness and planned absence

Sickness is configured per resource via `sickness_prob` (0.0 to 1.0), and explicit days off are set with `planned_absence`.

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
    `sickness_prob` is currently configured in the **project file** (per resource), not in the global config file.

---

## Example 5: Add task-level resource constraints

Use task fields to control assignment behavior:

- `resources`: restrict eligible resources by name,
- `max_resources`: cap parallel resources assigned to a task,
- `min_experience_level`: minimum allowed experience (`1`, `2`, `3`).

```yaml
tasks:
  - id: "task_003"
    name: "Data migration"
    estimate: { min: 24, most_likely: 40, max: 64 }
    dependencies: ["task_002"]
    resources: ["alice"]
    max_resources: 1
    min_experience_level: 3

  - id: "task_004"
    name: "System testing"
    estimate: { min: 16, most_likely: 24, max: 40 }
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

---

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
    estimate: { min: 16, most_likely: 24, max: 40 }
    uncertainty_factors:
      team_experience: medium
      technical_complexity: medium

  - id: "task_002"
    name: "Core implementation"
    estimate: { min: 80, most_likely: 120, max: 180 }
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
    estimate: { min: 40, most_likely: 64, max: 96 }
    dependencies: ["task_002"]
    resources: ["alice"]
    max_resources: 1
    min_experience_level: 3

  - id: "task_004"
    name: "Verification and rollout"
    estimate: { min: 24, most_likely: 40, max: 64 }
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

---

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

---

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

---

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

Use config files for simulation/reporting defaults (for example output settings and uncertainty multipliers). They do **not** replace per-resource sickness settings in the project file.

Example:

```yaml
simulation:
  default_iterations: 30000

output:
  critical_path_report_limit: 5
  histogram_bins: 80

staffing:
  effort_percentile: 80
```

---

## Related chapters

- [Project Files](project_files.md) for full schema reference
- [Running Simulations](running_simulations.md) for command reference
- [Interpreting Results](interpreting_results.md) for diagnostics interpretation
