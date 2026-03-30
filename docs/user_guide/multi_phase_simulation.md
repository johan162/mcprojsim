# Multi-Phase (Two-Pass) Simulation

**Multi-phase simulation** is an advanced scheduling strategy for resource-constrained
projects. When several tasks compete for the same limited pool of resources, the order
in which they are dispatched to those resources can materially affect the projected
completion date.

The standard scheduler uses a simple greedy policy: when multiple tasks become ready at
the same moment it picks them in deterministic ID order. This works well when resources
are abundant or contention is low.  When resources are scarce and some tasks are strongly
critical, a smarter ordering—one that dispatches the most critical tasks first—can
reduce the median project duration and, more importantly, reduce tail-risk at the P80–
P95 percentiles.

Two-pass simulation solves this problem with two consecutive simulation runs.

!!! info "Only active with resource-constrained scheduling"
    Two-pass mode requires at least one named `resource` in your project file.
    If no resources are defined the engine falls back to the standard single-pass mode
    automatically.

---

## How It Works

```
Pass 1 (baseline)          Pass 2 (priority-ordered)
───────────────────        ─────────────────────────
Greedy dispatch            Criticality-ranked dispatch
N = pass1_iterations       N = iterations (full run)

┌──────────┐               ┌──────────────────────────┐
│ Sample   │               │ Replay pass-1 durations  │  ← paired replay
│ durations│               │ (first pass1_iterations) │
└────┬─────┘               │ Sample fresh for the     │
     │                     │ remaining iterations     │
     ▼                     └───────────┬──────────────┘
┌──────────────┐                       │
│ Build        │                       ▼
│ criticality  │          ┌─────────────────────────┐
│ index CI(t)  │          │ Sort ready tasks by     │
│ per task     │─────────▶│ descending CI → earlier │
└──────────────┘          │ dispatch of critical    │
                          │ tasks                   │
                          └──────────┬──────────────┘
                                     │
                                     ▼
                          ┌─────────────────────────┐
                          │ TwoPassDelta:           │
                          │  pass-1 stats           │
                          │  pass-2 stats           │
                          │  Δ = pass-2 − pass-1    │
                          │  CI per task            │
                          └─────────────────────────┘
```

**Pass 1 — criticality baseline**  
The engine runs `pass1_iterations` iterations using the standard greedy policy.
Every iteration, it records which tasks appear on the critical path.  The
_criticality index_ of each task is the fraction of pass-1 iterations in which
it was critical (range 0 → 1).  Task durations are also cached for paired replay.

**Pass 2 — priority-ordered run**  
The engine runs the full `--iterations` run again.  Whenever two or more tasks
become ready at the same moment and there is a resource to claim, they are sorted
by _descending criticality index_ before dispatch.  This ensures that pass-1
identified bottleneck tasks get resources first.

For the first `pass1_iterations` iterations, the exact same sampled durations
from pass-1 are replayed (paired replay).  This makes the comparison between
pass-1 and pass-2 apples-to-apples: any difference in project duration is
caused solely by the change in dispatch policy, not by different duration samples.

**TwoPassDelta traceability**  
The results include a `two_pass_traceability` block in all output formats
(console, JSON, CSV, HTML) with per-pass statistics and Δ values.

---

## Basic Example

### Project file

For this example we will use the provided `examples/contention.yaml` file with three tasks sharing one senior developer
and a separate junior developer:

```yaml
project:
  name: "contention-demo"
  start_date: "2025-03-01"
  hours_per_day: 8
  confidence_levels: [50, 80, 90, 95]

tasks:
  - id: "A1"
    name: "Spec review"
    estimate: { low: 9, expected: 10, high: 12 }
    resources: ["dev-senior"]

  - id: "A2"
    name: "Core implementation"
    estimate: { low: 13, expected: 15, high: 18 }
    dependencies: ["A1"]
    resources: ["dev-senior"]

  - id: "A3"
    name: "Code review"
    estimate: { low: 9, expected: 10, high: 12 }
    dependencies: ["A2"]
    resources: ["dev-senior"]

  - id: "B1"
    name: "Documentation"
    estimate: { low: 18, expected: 20, high: 24 }
    resources: ["dev-senior"]          # competes for dev-senior!

  - id: "B2"
    name: "User testing"
    estimate: { low: 9, expected: 10, high: 12 }
    dependencies: ["B1"]
    resources: ["dev-junior"]

  - id: "C1"
    name: "Integration"
    estimate: { low: 4, expected: 5, high: 7 }
    dependencies: ["A3", "B2"]
    resources: ["dev-junior"]

  - id: "C2"
    name: "Release"
    estimate: { low: 7, expected: 8, high: 10 }
    dependencies: ["C1"]
    resources: ["dev-junior"]

resources:
  - name: "dev-senior"
    experience_level: 3

  - name: "dev-junior"
    experience_level: 1
```

### Single-pass run

```
mcprojsim % mcprojsim simulate examples/contention.yaml -n 1000 -t --seed 1234
```

Output excerpt:

```
=== Simulation Results ===

Calendar Time Statistical Summary:
┌──────────────────────────┬────────────────────────────────┐
│ Metric                   │ Value                          │
├──────────────────────────┼────────────────────────────────┤
│ Mean                     │ 567.49 hours (71 working days) │
│ Median (P50)             │ 559.94 hours                   │
│ Std Dev                  │ 13.64 hours                    │
└──────────────────────────┴────────────────────────────────┘

Calendar Time Confidence Intervals:
┌──────────────┬─────────┬────────────────┬────────────┐
│ Percentile   │   Hours │   Working Days │ Date       │
├──────────────┼─────────┼────────────────┼────────────┤
│ P50          │  559.94 │             70 │ 2025-06-06 │
│ P80          │  578.91 │             73 │ 2025-06-11 │
│ P90          │  580.6  │             73 │ 2025-06-11 │
│ P95          │  581.68 │             73 │ 2025-06-11 │
└──────────────┴─────────┴────────────────┴────────────┘
```

### Two-pass run

Add the `--two-pass` flag:

```
mcprojsim % mcprojsim simulate examples/contention.yaml -n 1000 --two-pass --pass1-iterations 500 -t --seed 1234
```

Output excerpt:

```
Pass 1: computing criticality indices
Progress: 100.0% (500/500)
Pass 2: priority-ordered scheduling
Progress: 100.0% (1000/1000)

=== Simulation Results ===

Calendar Time Statistical Summary:
┌──────────────────────────┬────────────────────────────────┐
│ Metric                   │ Value                          │
├──────────────────────────┼────────────────────────────────┤
│ Mean                     │ 470.91 hours (59 working days) │
│ Median (P50)             │ 463.49 hours                   │
│ Std Dev                  │ 13.28 hours                    │
└──────────────────────────┴────────────────────────────────┘

Calendar Time Confidence Intervals:
┌──────────────┬─────────┬────────────────┬────────────┐
│ Percentile   │   Hours │   Working Days │ Date       │
├──────────────┼─────────┼────────────────┼────────────┤
│ P50          │  463.49 │             58 │ 2025-05-21 │
│ P80          │  482.47 │             61 │ 2025-05-26 │
│ P90          │  484.08 │             61 │ 2025-05-26 │
│ P95          │  485.34 │             61 │ 2025-05-26 │
└──────────────┴─────────┴────────────────┴────────────┘

Two-Pass Scheduling Traceability:
┌──────────┬────────────────────┬─────────────────────┬─────────┐
│ Metric   │ Pass-1 iter: 500   │ Pass-2 iter: 1000   │ Delta   │
├──────────┼────────────────────┼─────────────────────┼─────────┤
│ Mean     │ 567.4h             │ 470.9h              │ -96.5h  │
│ P80      │ 578.9h             │ 482.5h              │ -96.4h  │
│ P95      │ 582.0h             │ 485.3h              │ -96.6h  │
└──────────┴────────────────────┴─────────────────────┴─────────┘

Resource wait delta: -121.1h
```

The two-pass run reduces the mean project duration from **~520 h to ~423 h** (~12 working
days) purely by prioritising the tasks that pass-1 identified as critical
bottlenecks.

---

## When Is Two-Pass Useful?

Two-pass simulation is most valuable when **all of the following** are true:

| Condition | Why it matters |
|---|---|
| Named resources are defined in the project file | Without resources, dispatch order has no effect |
| At least two tasks compete for the same resource | No contention → dispatch order is irrelevant |
| Some tasks have much higher criticality than others | Uniform criticality → reordering has little effect |
| The project has more than ~5–10 tasks | Very small projects often have no slack to reorder |

**Typical use-cases**

* Software delivery teams where one or two senior engineers are on the critical path
  and also reviewed by junior work items
* Infrastructure projects where a specialist (network architect, DBA) is a shared
  bottleneck across multiple workstreams
* Hardware/software co-design where a scarce test bench is contended between parallel
  integration streams
* Any project where you suspect the default greedy schedule is sub-optimal

**When two-pass has little effect**

If every task has its own dedicated resource (no contention), the delta will be close
to zero.  Example with `abundant-resources.yaml` (each task on its own resource):

```
Two-Pass Scheduling Traceability:
  Pass-1 iterations: 300 | Pass-2 iterations: 500
  Mean: 189.6h (pass-1) → 189.2h (pass-2) [delta -0.3h]
  P80:  194.7h (pass-1) → 194.6h (pass-2) [delta -0.1h]
  P95:  197.1h (pass-1) → 196.8h (pass-2) [delta -0.3h]
  Resource wait delta: +0.0h
```

The near-zero delta confirms that two-pass adds no distortion when resources are
not a bottleneck.

---

## Configuration Reference

### CLI flags

| Flag | Default | Description |
|---|---|---|
| `--two-pass` | off | Enable two-pass mode for this run |
| `--pass1-iterations N` | 1 000 | Pass-1 iteration budget for criticality ranking |

Both flags are accepted by the `simulate` command.  `--pass1-iterations` requires
`--two-pass` to have any effect.

```bash
# Basic two-pass run
mcprojsim simulate project.yaml --two-pass

# Fine-tuned: pass-1 with 2 000 iterations, pass-2 with 10 000
mcprojsim simulate project.yaml --two-pass --pass1-iterations 2000 -n 10000

# Export all formats
mcprojsim simulate project.yaml --two-pass -n 5000 -f json,csv,html -o report
```

### Configuration file

You can set the assignment mode globally in your `~/.mcprojsim/configuration.yaml` or
any config file passed with `--config`:

```yaml
constrained_scheduling:
  assignment_mode: criticality_two_pass   # default: greedy_single_pass
  pass1_iterations: 1000                  # default: 1000
```

With this config, every `simulate` invocation uses two-pass mode automatically for
projects that have resources, with no need for the `--two-pass` flag.

---

## More Complex Example: Developer Allocation

Consider a project with three workstreams all sharing a DevOps engineer for
deployment tasks:

```yaml
project:
  name: "multi-stream-release"
  start_date: "2025-06-01"
  hours_per_day: 8
  confidence_levels: [50, 80, 90, 95]

tasks:
  # --- Stream A: Backend ---
  - id: "backend-dev"
    name: "Backend development"
    estimate: { low: 60, expected: 80, high: 120 }
    resources: ["backend-dev-1"]

  - id: "backend-deploy"
    name: "Backend deployment"
    estimate: { low: 8, expected: 12, high: 16 }
    dependencies: ["backend-dev"]
    resources: ["devops"]              # shared bottleneck

  # --- Stream B: Frontend ---
  - id: "frontend-dev"
    name: "Frontend development"
    estimate: { low: 40, expected: 60, high: 90 }
    resources: ["frontend-dev-1"]

  - id: "frontend-deploy"
    name: "Frontend deployment"
    estimate: { low: 6, expected: 8, high: 12 }
    dependencies: ["frontend-dev"]
    resources: ["devops"]              # shared bottleneck

  # --- Stream C: Mobile ---
  - id: "mobile-dev"
    name: "Mobile development"
    estimate: { low: 80, expected: 100, high: 140 }
    resources: ["mobile-dev-1"]

  - id: "mobile-deploy"
    name: "Mobile deployment"
    estimate: { low: 8, expected: 10, high: 14 }
    dependencies: ["mobile-dev"]
    resources: ["devops"]              # shared bottleneck

  # --- Integration ---
  - id: "smoke-test"
    name: "Smoke test all streams"
    estimate: { low: 8, expected: 12, high: 20 }
    dependencies: ["backend-deploy", "frontend-deploy", "mobile-deploy"]
    resources: ["qa-1"]

  - id: "release"
    name: "Production release"
    estimate: { low: 4, expected: 6, high: 10 }
    dependencies: ["smoke-test"]
    resources: ["devops"]

resources:
  - name: "backend-dev-1"
    experience_level: 3

  - name: "frontend-dev-1"
    experience_level: 2

  - name: "mobile-dev-1"
    experience_level: 2

  - name: "devops"
    experience_level: 3

  - name: "qa-1"
    experience_level: 2
```

Run with two-pass to discover which deployment stream should be prioritised:

```bash
mcprojsim simulate multi-stream.yaml --two-pass --pass1-iterations 2000 \
  -n 10000 -t -f json,html -o multi-stream-report
```

The TwoPassDelta block in the JSON output will show which stream's deploy task
had the highest criticality index in pass-1, and how much the end-to-end schedule
improved once pass-2 gave that stream's DevOps slot priority.

---

## Output Formats

### Console (`-t` table mode)

A **Two-Pass Scheduling Traceability** table is printed after the constrained
diagnostics when `--two-pass` is active.  The table shows pass-1, pass-2, and
Δ values for Mean, P80, P95, and resource wait time.

### JSON export (`-f json`)

The `two_pass_traceability` key is always present.  It is `null` for single-pass
runs and an object for two-pass runs:

```json
{
  "two_pass_traceability": {
    "enabled": true,
    "pass1_iterations": 500,
    "pass2_iterations": 1000,
    "ranking_method": "criticality_index",
    "pass1": {
      "mean_hours": 519.9,
      "p50_hours": 519.8,
      "p80_hours": 530.6,
      "p90_hours": 532.7,
      "p95_hours": 533.0,
      "resource_wait_hours": 212.2,
      "resource_utilization": 0.87,
      "calendar_delay_hours": 0.0
    },
    "pass2": {
      "mean_hours": 422.8,
      "p50_hours": 422.3,
      "p80_hours": 434.3,
      "p90_hours": 436.4,
      "p95_hours": 437.1,
      "resource_wait_hours": 90.2,
      "resource_utilization": 0.91,
      "calendar_delay_hours": 0.0
    },
    "delta": {
      "mean_hours": -97.0,
      "p50_hours": -97.5,
      "p80_hours": -96.3,
      "p90_hours": -96.3,
      "p95_hours": -95.9,
      "resource_wait_hours": -122.0,
      "resource_utilization": 0.04,
      "calendar_delay_hours": 0.0
    },
    "task_criticality_index": {
      "A1": 0.0,
      "A2": 0.0,
      "A3": 0.0,
      "B1": 1.0,
      "B2": 1.0,
      "C1": 1.0,
      "C2": 1.0
    }
  }
}
```

### CSV export (`-f csv`)

A **Two-Pass Scheduling Traceability** section is appended after the constrained
diagnostics block, followed by a **Task Criticality Index (pass-1)** section that
lists each task's CI value.

### HTML export (`-f html`)

The HTML report gains a **Two-Pass Scheduling Traceability** table with pass-1,
pass-2, and Δ columns for each key metric, followed by a collapsible **Task
Criticality Index (Pass 1)** table.

---

## Choosing `pass1_iterations`

Pass-1 is used only to rank tasks; it does not directly affect the final results.
A few practical guidelines:

| Scenario | Recommended `pass1_iterations` |
|---|---|
| Quick exploratory run | 200–500 |
| Standard analysis | 500–2 000 (default 1 000) |
| Rigorous / publication-quality | 2 000–5 000 |
| Noisy project with many tasks | 5 000+ |

The default of **1 000** is a good balance between ranking stability and
computational cost for most projects.  If you reduce `pass1_iterations` below
100 the engine logs a warning that the criticality indices may be noisy.

`pass1_iterations` is automatically capped to `--iterations` if it is larger.

---

## Interpreting the Delta

The delta values tell you the **effect of smarter dispatch** on each reported
metric, holding all other inputs constant:

| Delta sign | Meaning |
|---|---|
| Negative (e.g. `-97 h`) | Pass-2 schedule is shorter → good, the reordering helped |
| Near zero | No contention, or all tasks equally critical → reordering made no difference |
| Positive | Unusual; could indicate that the pass-1 ranking was noisy (increase `pass1_iterations`) |

A large negative delta on mean/P80 combined with a large negative delta on
resource wait time is strong evidence that the project suffers from avoidable
resource contention, and that assigning more resources or restructuring task
ownership would reduce schedule risk.
