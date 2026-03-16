# Examples

- [Examples](#examples)
  - [1. Basic Project with Explicit Estimates](#1-basic-project-with-explicit-estimates)
  - [2. T-Shirt Sizing](#2-t-shirt-sizing)
  - [3. Story Points](#3-story-points)
  - [4. Complex Project with Risks](#4-complex-project-with-risks)
  - [5. Log-Normal Distribution](#5-log-normal-distribution)
  - [6. Constrained Scheduling with `team_size`](#6-constrained-scheduling-with-team_size)
  - [7. Constrained Scheduling with Explicit Resources and Calendars](#7-constrained-scheduling-with-explicit-resources-and-calendars)
  - [8. Natural Language Project Generation](#8-natural-language-project-generation)
    - [Basic text input (dependency-only)](#basic-text-input-dependency-only)
    - [Text input with resources and calendars (constrained)](#text-input-with-resources-and-calendars-constrained)
  - [Running Examples](#running-examples)
    - [Common CLI options](#common-cli-options)
    - [Additional example files](#additional-example-files)


This page provides practical examples of project definitions, progressing from simple to complex. Each example includes real simulation output. For complete specification details, see the [Formal Grammar](grammar.md).

All outputs below were generated with `--minimal --seed 42` for reproducibility. Use `--seed` to get identical results on your machine.

---

## 1. Basic Project with Explicit Estimates

A simple project with two sequential tasks using three-point (min / most likely / max) estimates. This is the simplest useful project definition.

```yaml
project:
  name: "Website Refresh"
  start_date: "2026-04-01"
  confidence_levels: [50, 80, 90]

tasks:
  - id: "task_001"
    name: "Design updates"
    estimate:
      min: 2
      most_likely: 3
      max: 5
      unit: "days"

  - id: "task_002"
    name: "Frontend changes"
    estimate:
      min: 4
      most_likely: 6
      max: 10
      unit: "days"
    dependencies: ["task_001"]
    uncertainty_factors:
      team_experience: "medium"
      technical_complexity: "medium"
```

```bash
mcprojsim simulate examples/quickstart_example.yaml --minimal --seed 42
```

```text
Project Overview:
Project: Website Refresh
Hours per Day: 8.0
Max Parallel Tasks: 1
Schedule Mode: dependency_only

Calendar Time Statistical Summary:
Mean: 126.93 hours (16 working days)
Median (P50): 125.74 hours
Std Dev: 17.68 hours
Coefficient of Variation: 0.1393

Calendar Time Confidence Intervals:
  P50: 125.74 hours (16 working days)  (2026-04-23)
  P80: 142.59 hours (18 working days)  (2026-04-27)
  P90: 151.18 hours (19 working days)  (2026-04-28)
```

Key observations: two sequential tasks, no parallelism (`Max Parallel Tasks: 1`), `dependency_only` scheduling.

See `examples/quickstart_example.yaml` in the repository.

---

## 2. T-Shirt Sizing

For quick estimation using relative sizes (`XS`, `S`, `M`, `L`, `XL`, `XXL`). T-shirt sizes map to default effort ranges that are configurable via the [configuration file](user_guide/task_estimation.md#t-shirt-size-estimates).

```yaml
project:
  name: "Mobile App Development"
  start_date: "2025-11-01"
  confidence_levels: [10, 50, 75, 80, 85, 90, 95, 99]

tasks:
  - id: "design_ui"
    name: "UI/UX Design"
    estimate:
      t_shirt_size: "M"
    dependencies: []
    uncertainty_factors:
      team_experience: "high"
      requirements_maturity: "high"

  - id: "setup_backend"
    name: "Backend Infrastructure Setup"
    estimate:
      t_shirt_size: "L"
    dependencies: []

  - id: "api_development"
    name: "REST API Development"
    estimate:
      t_shirt_size: "XL"
    dependencies: ["setup_backend"]
    risks:
      - id: "api_complexity"
        name: "API complexity higher than expected"
        probability: 0.30
        impact:
          type: "absolute"
          value: 5
          unit: "hours"

  - id: "mobile_app_dev"
    name: "Mobile App Development"
    estimate:
      t_shirt_size: "XXL"
    dependencies: ["design_ui", "api_development"]

  - id: "integration_testing"
    name: "Integration Testing"
    estimate:
      t_shirt_size: "M"
    dependencies: ["mobile_app_dev"]
```

```bash
mcprojsim simulate examples/tshirt_sizing_project.yaml --minimal --seed 42
```

```text
Project Overview:
Project: Mobile App Development
Hours per Day: 8.0
Max Parallel Tasks: 2
Schedule Mode: dependency_only

Calendar Time Statistical Summary:
Mean: 3491.26 hours (437 working days)
Median (P50): 3422.83 hours
Std Dev: 578.05 hours
Coefficient of Variation: 0.1656

Calendar Time Confidence Intervals:
  P10: 2791.21 hours (349 working days)  (2027-03-04)
  P50: 3422.83 hours (428 working days)  (2027-06-23)
  P90: 4273.10 hours (535 working days)  (2027-11-19)
  P99: 5055.58 hours (632 working days)  (2028-04-04)
```

Key observations: two independent starting tasks yield `Max Parallel Tasks: 2`. The wide P10–P99 spread (349–632 working days) reflects the inherent uncertainty of T-shirt sizing for large effort items.

Note: T-shirt size and story point estimates must **not** include a `unit` field in the project file. The unit is controlled by the configuration.

See `examples/tshirt_sizing_project.yaml` in the repository.

---

## 3. Story Points

For agile-style relative estimation using calibrated story point mappings. Default mappings are configurable via the [configuration file](user_guide/task_estimation.md#story-point-estimates).

```yaml
project:
  name: "Tiny Landing Page"
  start_date: "2026-03-01"
  confidence_levels: [50, 80, 90]

tasks:
  - id: "task_001"
    name: "Design page"
    estimate:
      story_points: 2
    dependencies: []
    uncertainty_factors:
      team_experience: "high"
      requirements_maturity: "high"

  - id: "task_002"
    name: "Build page"
    estimate:
      story_points: 5
    dependencies: ["task_001"]
    uncertainty_factors:
      team_experience: "medium"
      technical_complexity: "medium"

  - id: "task_003"
    name: "Deploy page"
    estimate:
      story_points: 1
    dependencies: ["task_002"]
```

```bash
mcprojsim simulate examples/story_points_walkthrough_project.yaml --minimal --seed 42
```

```text
Project Overview:
Project: Tiny Landing Page
Hours per Day: 8.0
Max Parallel Tasks: 1
Schedule Mode: dependency_only

Calendar Time Statistical Summary:
Mean: 109.90 hours (14 working days)
Median (P50): 109.21 hours
Std Dev: 15.97 hours
Coefficient of Variation: 0.1453

Calendar Time Confidence Intervals:
  P50: 109.21 hours (14 working days)  (2026-03-19)
  P80: 123.81 hours (16 working days)  (2026-03-23)
  P90: 131.03 hours (17 working days)  (2026-03-24)
```

Key observations: small project with low uncertainty — the CV is only 0.15 and P50 to P90 spans just 3 working days.

See `examples/story_points_walkthrough_project.yaml` in the repository.

---

## 4. Complex Project with Risks

A realistic project with 8 tasks, complex dependencies, uncertainty factors, and both task-level and project-level risks.

```yaml
project:
  name: "Customer Portal Redesign"
  start_date: "2025-11-01"
  confidence_levels: [25, 50, 75, 80, 85, 90, 95, 99]
  probability_red_threshold: 0.50
  probability_green_threshold: 0.90

project_risks:
  - id: "risk_001"
    name: "Key developer leaves"
    probability: 0.15
    impact:
      type: "percentage"
      value: 20
  - id: "risk_002"
    name: "Requirements change"
    probability: 0.30
    impact:
      type: "absolute"
      value: 10
      unit: "days"

tasks:
  - id: "task_001"
    name: "Database schema design"
    estimate:
      min: 3
      most_likely: 5
      max: 10
      unit: "days"
    dependencies: []
    uncertainty_factors:
      team_experience: "high"
      requirements_maturity: "medium"
      technical_complexity: "low"
    risks:
      - id: "task_risk_001"
        name: "Schema migration issues"
        probability: 0.20
        impact:
          type: "absolute"
          value: 2
          unit: "days"

  - id: "task_002"
    name: "API endpoint implementation"
    estimate: { min: 5, most_likely: 8, max: 15, unit: "days" }
    dependencies: ["task_001"]

  - id: "task_003"
    name: "Frontend React components"
    estimate: { min: 7, most_likely: 10, max: 18, unit: "days" }
    dependencies: []
    risks:
      - id: "task_risk_002"
        name: "Browser compatibility issues"
        probability: 0.25
        impact: { type: "absolute", value: 3, unit: "days" }

  - id: "task_004"
    name: "Authentication & Authorization"
    estimate: { min: 4, most_likely: 6, max: 12, unit: "days" }
    dependencies: ["task_002"]

  - id: "task_005"
    name: "Integration testing"
    estimate: { min: 3, most_likely: 5, max: 8, unit: "days" }
    dependencies: ["task_002", "task_003", "task_004"]

  - id: "task_006"
    name: "Performance optimization"
    estimate: { min: 2, most_likely: 4, max: 7, unit: "days" }
    dependencies: ["task_005"]

  - id: "task_007"
    name: "Documentation"
    estimate: { min: 2, most_likely: 3, max: 5, unit: "days" }
    dependencies: ["task_002", "task_003"]

  - id: "task_008"
    name: "Deployment & DevOps"
    estimate: { min: 3, most_likely: 5, max: 9, unit: "days" }
    dependencies: ["task_006"]
```

```bash
mcprojsim simulate examples/sample_project.yaml --minimal --seed 42
```

```text
Project Overview:
Project: Customer Portal Redesign
Hours per Day: 8.0
Max Parallel Tasks: 2
Schedule Mode: dependency_only

Calendar Time Statistical Summary:
Mean: 580.89 hours (73 working days)
Median (P50): 574.73 hours
Std Dev: 78.46 hours
Coefficient of Variation: 0.1351

Calendar Time Confidence Intervals:
  P25: 524.00 hours (66 working days)  (2026-02-02)
  P50: 574.73 hours (72 working days)  (2026-02-10)
  P75: 629.98 hours (79 working days)  (2026-02-19)
  P80: 645.37 hours (81 working days)  (2026-02-23)
  P90: 685.64 hours (86 working days)  (2026-03-02)
  P95: 722.71 hours (91 working days)  (2026-03-09)
  P99: 789.05 hours (99 working days)  (2026-03-19)
```

Key observations:

- Effort and calendar time differ (`86 person-days` effort vs `73 working days` calendar) because some tasks run in parallel.
- The positive skewness (0.48) shows a right-skewed distribution — risks and uncertainty create a longer tail toward delays.

See `examples/sample_project.yaml` in the repository.

---

## 5. Log-Normal Distribution

For tasks where extreme overruns are more probable than a triangular distribution predicts:

```yaml
tasks:
  - id: "research"
    name: "Research new technology"
    estimate:
      distribution: "lognormal"
      most_likely: 5
      standard_deviation: 2
      unit: "days"
    dependencies: []
```

The log-normal distribution produces a heavier right tail, making it suitable for research, exploration, or tasks with high uncertainty about upper bounds.

---

## 6. Constrained Scheduling with `team_size`

The simplest way to activate resource-constrained scheduling: add `team_size` to the project metadata. This auto-generates default resources.

```yaml
project:
  name: "Team Size Demo"
  start_date: "2026-04-01"
  hours_per_day: 8
  team_size: 10

tasks:
  - id: "task_001"
    name: "Task 1"
    estimate: { min: 8, most_likely: 16, max: 24 }
  - id: "task_002"
    name: "Task 2"
    estimate: { min: 40, most_likely: 64, max: 96 }
    dependencies: ["task_001"]
```

```bash
mcprojsim simulate examples/team_size_demo_with_team_size.yaml --minimal --seed 42
```

```text
Project Overview:
Project: Team Size Demo
Hours per Day: 8.0
Max Parallel Tasks: 1
Schedule Mode: resource_constrained

Calendar Time Statistical Summary:
Mean: 538.18 hours (68 working days)
Median (P50): 530.38 hours
Std Dev: 80.88 hours
Coefficient of Variation: 0.1503

Calendar Time Confidence Intervals:
  P25: 485.83 hours (61 working days)  (2026-06-25)
  P50: 530.38 hours (67 working days)  (2026-07-03)
  P80: 628.37 hours (79 working days)  (2026-07-21)
  P90: 652.96 hours (82 working days)  (2026-07-24)
  P95: 675.60 hours (85 working days)  (2026-07-29)
  P99: 700.95 hours (88 working days)  (2026-08-03)
```

Compare with the same project **without** `team_size` (dependency-only mode):

```bash
mcprojsim simulate examples/team_size_demo_base.yaml --minimal --seed 42
```

```text
Schedule Mode: dependency_only

Calendar Time Confidence Intervals:
  P50: 130.38 hours (17 working days)  (2026-04-24)
  P90: 156.96 hours (20 working days)  (2026-04-29)
```

Key observations:

- Adding `team_size` switches from `dependency_only` to `resource_constrained`.
- Calendar time increases significantly (P50: 17 → 67 working days) because resources are assigned one at a time by default (`max_resources: 1`), and working calendars now account for weekends and non-working hours.
- Effort remains the same — only elapsed calendar time changes.

See `examples/team_size_demo_base.yaml` and `examples/team_size_demo_with_team_size.yaml` in the repository.

---

## 7. Constrained Scheduling with Explicit Resources and Calendars

For full control, define resources with individual skill levels, productivity, sickness probability, and planned absences. Attach resources to named calendars with custom work patterns.

```yaml
project:
  name: "Onboarding Portal"
  start_date: "2026-04-01"
  hours_per_day: 8
  confidence_levels: [50, 80, 90, 95]

tasks:
  - id: "task_001"
    name: "Requirements"
    estimate: { min: 8, most_likely: 16, max: 24 }

  - id: "task_002"
    name: "Implementation"
    estimate: { min: 40, most_likely: 64, max: 96 }
    dependencies: ["task_001"]
    resources: ["alice", "bob"]
    max_resources: 2
    min_experience_level: 2

  - id: "task_003"
    name: "Testing"
    estimate: { min: 16, most_likely: 24, max: 40 }
    dependencies: ["task_002"]

resources:
  - name: "alice"
    experience_level: 3
    productivity_level: 1.1
    sickness_prob: 0.02
    planned_absence: ["2026-04-22"]

  - name: "bob"
    calendar: "part_time"
    experience_level: 2
    productivity_level: 0.9
    availability: 0.8
    sickness_prob: 0.04

calendars:
  - id: "default"
    work_hours_per_day: 8
    work_days: [1, 2, 3, 4, 5]
    holidays: ["2026-04-10"]

  - id: "part_time"
    work_hours_per_day: 6
    work_days: [1, 2, 3, 4]
```

```bash
mcprojsim simulate constrained_portal.yaml --minimal --seed 42 --iterations 200
```

```text
Project Overview:
Project: Onboarding Portal
Hours per Day: 8.0
Max Parallel Tasks: 1
Schedule Mode: resource_constrained

Calendar Time Statistical Summary:
Mean: 614.18 hours (77 working days)
Median (P50): 628.42 hours
Std Dev: 96.21 hours
Coefficient of Variation: 0.1567

Project Effort Statistical Summary:
Mean: 174.56 person-hours (22 person-days)

Calendar Time Confidence Intervals:
  P50: 628.42 hours (79 working days)  (2026-07-21)
  P80: 678.38 hours (85 working days)  (2026-07-29)
  P90: 722.36 hours (91 working days)  (2026-08-06)
  P95: 794.07 hours (100 working days)  (2026-08-19)
```

Key observations:

- `resources` on `task_002` restricts it to only `alice` and `bob`.
- `max_resources: 2` allows both to work in parallel on that task.
- `min_experience_level: 2` filters out any resource below that skill tier.
- `sickness_prob` introduces stochastic sick days that vary across iterations.
- `planned_absence` blocks specific dates deterministically.
- Bob's `part_time` calendar (6 hours/day, Mon–Thu) reduces his available capacity.
- Calendar time (77 working days) is much larger than effort (22 person-days) due to calendar constraints, weekends, holidays, and sickness.

For a full constrained walkthrough with incremental complexity, see the [Constrained Scheduling Guide](user_guide/constrained.md).

---

## 8. Natural Language Project Generation

The `generate` command converts plain-text project descriptions into valid YAML project files. This lets you sketch a project quickly and iterate.

### Basic text input (dependency-only)

```text
Project name: Rework Web Interface
Start date: 2026-06-02
Task 1:
- Analyse existing UI
- Size: M
Task 2:
- Refine requirements
- Depends on Task 1
- Size XL
Task 3:
- Design solution
- Depends on Task 2
- Size. XL
```

```bash
mcprojsim generate examples/nl_example.txt -o project.yaml
mcprojsim simulate project.yaml --minimal --seed 42
```

```text
Project Overview:
Project: Rework Web Interface
Hours per Day: 8.0
Max Parallel Tasks: 1
Schedule Mode: dependency_only

Calendar Time Confidence Intervals:
  P50: 1654.52 hours (207 working days)  (2027-03-18)
  P80: 1853.22 hours (232 working days)  (2027-04-22)
  P90: 1957.49 hours (245 working days)  (2027-05-11)
  P95: 2040.64 hours (256 working days)  (2027-05-26)
```

### Text input with resources and calendars (constrained)

The `generate` command also supports resource definitions, calendar definitions, and task-level resource constraints:

```text
Project name: Platform Migration
Start date: 2026-05-01
Hours per day: 8

Resource 1: Alice
- Experience: 3
- Productivity: 1.1
- Sickness: 0.02
- Absence: 2026-05-15

Resource 2: Bob
- Experience: 2
- Productivity: 1.0
- Availability: 0.8
- Sickness: 0.03

Resource 3: Carol
- Experience: 2
- Calendar: part_time
- Availability: 0.75
- Productivity: 0.9
- Sickness: 0.04
- Absence: 2026-06-01, 2026-06-02

Calendar: default
- Work hours: 8
- Work days: 1, 2, 3, 4, 5
- Holidays: 2026-05-25

Calendar: part_time
- Work hours: 6
- Work days: 1, 2, 3, 4

Task 1: Architecture design
- Estimate: 16/24/40 hours
- Min experience: 2

Task 2: Core implementation
- Estimate: 80/120/180 hours
- Depends on Task 1
- Resources: Alice, Bob, Carol
- Max resources: 2
- Min experience: 2

Task 3: Data migration
- Estimate: 40/64/96 hours
- Depends on Task 2
- Resources: Alice
- Min experience: 3

Task 4: Verification and rollout
- Estimate: 24/40/64 hours
- Depends on Task 3
- Resources: Alice, Bob, Carol
- Max resources: 2
```

```bash
mcprojsim generate examples/nl_constrained_example.txt -o project.yaml
mcprojsim simulate project.yaml --minimal --seed 42 --iterations 200
```

```text
Project Overview:
Project: Platform Migration
Hours per Day: 8.0
Max Parallel Tasks: 1
Schedule Mode: resource_constrained

Calendar Time Statistical Summary:
Mean: 1276.23 hours (160 working days)
Median (P50): 1276.72 hours
Std Dev: 128.72 hours
Coefficient of Variation: 0.1009

Calendar Time Confidence Intervals:
  P50: 1276.72 hours (160 working days)  (2026-12-11)
  P80: 1351.55 hours (169 working days)  (2026-12-24)
  P90: 1442.32 hours (181 working days)  (2027-01-11)
  P95: 1472.32 hours (185 working days)  (2027-01-15)
```

The generated YAML includes full `resources:` and `calendars:` sections. Use `--validate-only` to check your description before generating:

```bash
mcprojsim generate examples/nl_constrained_example.txt --validate-only
```

```text
✓ Valid: 'Platform Migration' with 4 task(s)
```

See `examples/nl_example.txt` and `examples/nl_constrained_example.txt` in the repository.

---

## Running Examples

### Common CLI options

```bash
# Basic simulation
mcprojsim simulate examples/quickstart_example.yaml

# Minimal output for quick overview
mcprojsim simulate examples/sample_project.yaml --minimal

# Reproducible results with a seed
mcprojsim simulate examples/sample_project.yaml --seed 42

# More iterations for higher accuracy
mcprojsim simulate examples/sample_project.yaml --iterations 50000

# With custom config (uncertainty factors, output settings)
mcprojsim simulate examples/sample_project.yaml \
  --config examples/sample_config.yaml

# Tabular output format
mcprojsim simulate examples/sample_project.yaml --table

# Check probability of hitting a target date
mcprojsim simulate examples/sample_project.yaml \
  --target-date 2026-03-15

# Show top 5 critical path sequences
mcprojsim simulate examples/sample_project.yaml \
  --critical-paths 5

# Export to multiple formats
mcprojsim simulate examples/sample_project.yaml \
  -f json,csv,html -o results/portal
```

### Additional example files

| File | Demonstrates |
|---|---|
| `quickstart_example.yaml` | Basic explicit estimates |
| `tshirt_sizing_project.yaml` | T-shirt size estimation with risks |
| `story_points_walkthrough_project.yaml` | Story point estimation |
| `sample_project.yaml` | Complex project with risks and dependencies |
| `project_with_custom_thresholds.yaml` | Custom probability thresholds |
| `team_size_demo_base.yaml` | Dependency-only baseline |
| `team_size_demo_with_team_size.yaml` | `team_size` constrained scheduling |
| `resource_cap_small_task.yaml` | Auto-capping on short tasks |
| `resource_cap_large_task.yaml` | Global coordination cap on large tasks |
| `nl_example.txt` | Natural language input (basic) |
| `nl_constrained_example.txt` | Natural language input with resources |
| `sample_config.yaml` | Custom configuration file |
