<!-- AUTO-GENERATED FILE — DO NOT EDIT -->
<!-- Source: docs/examples_template.md -->
<!-- Regenerate with: make gen-examples -->

# Examples

- [Examples](#examples)
  - [Basic Project with Explicit Estimates](#basic-project-with-explicit-estimates)
  - [T-Shirt Sizing](#t-shirt-sizing)
  - [Story Points](#story-points)
  - [Complex Project with Risks](#complex-project-with-risks)
  - [Log-Normal Distribution](#log-normal-distribution)
  - [Constrained Scheduling with `team_size`](#constrained-scheduling-with-team_size)
  - [Constrained Scheduling with Explicit Resources and Calendars](#constrained-scheduling-with-explicit-resources-and-calendars)
  - [Natural Language Project Generation](#natural-language-project-generation)
    - [Basic text input (dependency-only)](#basic-text-input-dependency-only)
    - [Text input with resources and calendars (constrained)](#text-input-with-resources-and-calendars-constrained)
  - [Sprint Planning](#sprint-planning)
    - [Minimal story-point forecast](#minimal-story-point-forecast)
    - [Advanced sprint forecast](#advanced-sprint-forecast)
    - [Tasks mode and external history](#tasks-mode-and-external-history)
  - [Running Examples](#running-examples)
    - [Common CLI options](#common-cli-options)
    - [Additional example files](#additional-example-files)


This page provides practical examples of project definitions, progressing from simple to complex. Each example includes real simulation output. For complete specification details, see the [Formal Grammar](grammar.md).

All outputs below were generated with `--minimal --seed 42` for reproducibility. Use `--seed` to get identical results on your machine.



## Basic Project with Explicit Estimates

A simple project with two sequential tasks using three-point (min / most likely / max) estimates. This is the simplest useful project definition.

```yaml
project:
  name: "Website Refresh"
  description: "Small example project"
  start_date: "2026-04-01"
  confidence_levels: [50, 80, 90]

tasks:
  - id: "task_001"
    name: "Design updates"
    estimate:
      low: 2
      expected: 3
      high: 5
      unit: "days"

  - id: "task_002"
    name: "Frontend changes"
    estimate:
      low: 4
      expected: 6
      high: 10
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
mcprojsim v0.15.0
Run: 2026-04-25

Project Overview:
  Project: Website Refresh
  Start Date: 2026-04-01
  Number of Tasks: 2
  Effective Default Distribution: triangular
  T-Shirt Category Used: story
  Hours per Day: 8.0
  Max Parallel Tasks: 1
  Schedule Mode: dependency_only

Calendar Time Statistical Summary:
  Mean: 90.65 hours (12 working days)
  Median (P50): 89.68 hours
  Std Dev: 12.97 hours
  Minimum: 55.92 hours
  Maximum: 131.62 hours

Project Effort Statistical Summary:
  Mean: 90.65 person-hours (12 person-days)
  Median (P50): 89.68 person-hours
  Std Dev: 12.97 person-hours
  Minimum: 55.92 person-hours
  Maximum: 131.62 person-hours

Calendar Time Confidence Intervals:
  P50: 89.68 hours (12 working days)  (2026-04-17)
  P80: 102.25 hours (13 working days)  (2026-04-20)
  P90: 108.53 hours (14 working days)  (2026-04-21)
```

Key observations: two sequential tasks, no parallelism (`Max Parallel Tasks: 1`), `dependency_only` scheduling.

See `examples/quickstart_example.yaml` in the repository.



## T-Shirt Sizing

For quick estimation using relative sizes (`XS`, `S`, `M`, `L`, `XL`, `XXL`). T-shirt sizes map to default effort ranges that are configurable via the [configuration file](user_guide/05_task_estimation.md#t-shirt-size-estimates).

```yaml
project:
  name: "Mobile App Development"
  description: "Example project using T-shirt sizing for effort estimates"
  start_date: "2025-11-01"
  confidence_levels: [10, 50, 75, 80, 85, 90, 95, 99]
  probability_red_threshold: 0.50
  probability_green_threshold: 0.90

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
    uncertainty_factors:
      team_experience: "medium"
      technical_complexity: "medium"

  - id: "api_development"
    name: "REST API Development"
    estimate:
      t_shirt_size: "XL"
    dependencies: ["setup_backend"]
    uncertainty_factors:
      team_experience: "medium"
      technical_complexity: "high"
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
    uncertainty_factors:
      team_experience: "low"
      technical_complexity: "high"

  - id: "integration_testing"
    name: "Integration Testing"
    estimate:
      t_shirt_size: "M"
    dependencies: ["mobile_app_dev"]
    uncertainty_factors:
      requirements_maturity: "high"

  - id: "deployment"
    name: "Deployment and Go-Live"
    estimate:
      t_shirt_size: "S"
    dependencies: ["integration_testing"]
    uncertainty_factors:
      integration_complexity: "medium"

project_risks:
  - id: "team_change"
    name: "Key team member leaves"
    probability: 0.15
    impact:
      type: "percentage"
      value: 20
```

```bash
mcprojsim simulate examples/tshirt_sizing_project.yaml --minimal --seed 42
```

```text
mcprojsim v0.15.0
Run: 2026-04-25

Project Overview:
  Project: Mobile App Development
  Start Date: 2025-11-01
  Number of Tasks: 6
  Effective Default Distribution: triangular
  T-Shirt Category Used: story
  Hours per Day: 8.0
  Max Parallel Tasks: 2
  Schedule Mode: dependency_only

Calendar Time Statistical Summary:
  Mean: 2635.93 hours (330 working days)
  Median (P50): 2584.12 hours
  Std Dev: 436.95 hours
  Minimum: 1653.07 hours
  Maximum: 4602.84 hours

Project Effort Statistical Summary:
  Mean: 2622.12 person-hours (328 person-days)
  Median (P50): 2578.96 person-hours
  Std Dev: 384.08 person-hours
  Minimum: 1721.88 person-hours
  Maximum: 3990.15 person-hours

Calendar Time Confidence Intervals:
  P10: 2107.45 hours (264 working days)  (2026-11-05)
  P50: 2584.12 hours (324 working days)  (2027-01-28)
  P75: 2921.42 hours (366 working days)  (2027-03-29)
  P80: 3006.12 hours (376 working days)  (2027-04-12)
  P85: 3099.16 hours (388 working days)  (2027-04-28)
  P90: 3227.73 hours (404 working days)  (2027-05-20)
  P95: 3411.59 hours (427 working days)  (2027-06-22)
  P99: 3818.90 hours (478 working days)  (2027-09-01)
```

Key observations: two independent starting tasks yield `Max Parallel Tasks: 2`. The wide P10–P99 spread (938–1590 working days) reflects the inherent uncertainty of T-shirt sizing for large effort items.

Note: T-shirt size and story point estimates must **not** include a `unit` field in the project file. The unit is controlled by the configuration.

See `examples/tshirt_sizing_project.yaml` in the repository.



## Story Points

For agile-style relative estimation using calibrated story point mappings. Default mappings are configurable via the [configuration file](user_guide/05_task_estimation.md#story-point-estimates).

```yaml
project:
  name: "Tiny Landing Page"
  description: "Story Point sizing example"
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
mcprojsim simulate examples/story_points_walkthrough_project.yaml --minimal --table --seed 42
```

```text
mcprojsim v0.15.0
Run: 2026-04-25

Project Overview:
┌────────────────────────────────┬───────────────────────────────────┐
│ Field                          │ Value                             │
├────────────────────────────────┼───────────────────────────────────┤
│ Project                        │ Tiny Landing Page                 │
│ Start Date                     │ 2026-03-01                        │
│ Number of Tasks                │ 3                                 │
│ Effective Default Distribution │ triangular                        │
│ T-Shirt Category Used          │ story                             │
│ Hours per Day                  │ 8.0                               │
│ Max Parallel Tasks             │ 1                                 │
│ Schedule Mode                  │ dependency_only                   │
└────────────────────────────────┴───────────────────────────────────┘

Calendar Time Statistical Summary:
┌──────────────┬─────────────────────────────────────────────────────┐
│ Metric       │ Value                                               │
├──────────────┼─────────────────────────────────────────────────────┤
│ Mean         │ 79.98 hours (10 working days)                       │
│ Median (P50) │ 79.44 hours                                         │
│ Std Dev      │ 11.65 hours                                         │
│ Minimum      │ 47.31 hours                                         │
│ Maximum      │ 121.18 hours                                        │
└──────────────┴─────────────────────────────────────────────────────┘

Project Effort Statistical Summary:
┌──────────────┬─────────────────────────────────────────────────────┐
│ Metric       │ Value                                               │
├──────────────┼─────────────────────────────────────────────────────┤
│ Mean         │ 79.98 person-hours (10 person-days)                 │
│ Median (P50) │ 79.44 person-hours                                  │
│ Std Dev      │ 11.65 person-hours                                  │
│ Minimum      │ 47.31 person-hours                                  │
│ Maximum      │ 121.18 person-hours                                 │
└──────────────┴─────────────────────────────────────────────────────┘

Calendar Time Confidence Intervals:
┌──────────────┬─────────┬────────────────┬──────────────────────────┐
│ Percentile   │   Hours │   Working Days │ Date                     │
├──────────────┼─────────┼────────────────┼──────────────────────────┤
│ P50          │   79.44 │             10 │ 2026-03-13               │
│ P80          │   90.19 │             12 │ 2026-03-17               │
│ P90          │   95.57 │             12 │ 2026-03-17               │
└──────────────┴─────────┴────────────────┴──────────────────────────┘
```

Key observations: small project with low uncertainty — the CV is only 0.15 and P50 to P90 spans just 3 working days.

See `examples/story_points_walkthrough_project.yaml` in the repository.



## Complex Project with Risks

A realistic project with 8 tasks, complex dependencies, uncertainty factors, and both task-level and project-level risks.

```yaml
project:
  name: "Customer Portal Redesign"
  description: "Next-generation customer portal with enhanced features"
  start_date: "2025-11-01"
  confidence_levels: [25, 50, 75, 80, 85, 90, 95, 99]
  # Probability thresholds for thermometer visualization
  probability_red_threshold: 0.50    # Below 50% shown as red (high risk)
  probability_green_threshold: 0.90  # Above 90% shown as green (low risk)

project_risks:
  - id: "risk_001"
    name: "Key developer leaves"
    probability: 0.15
    impact:
      type: "percentage"
      value: 20
    description: "Risk of losing senior developer mid-project"
  
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
    description: "Design normalized schema for customer data"
    estimate:
      low: 3
      expected: 5
      high: 10
      unit: "days"
    dependencies: []
    uncertainty_factors:
      team_experience: "high"
      requirements_maturity: "medium"
      technical_complexity: "low"
      team_distribution: "colocated"
      integration_complexity: "low"
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
    description: "Implement RESTful API endpoints"
    estimate:
      low: 5
      expected: 8
      high: 15
      unit: "days"
    dependencies: ["task_001"]
    uncertainty_factors:
      team_experience: "medium"
      requirements_maturity: "high"
      technical_complexity: "medium"
      team_distribution: "colocated"
      integration_complexity: "medium"
    risks: []

  - id: "task_003"
    name: "Frontend React components"
    description: "Build reusable React components for UI"
    estimate:
      low: 7
      expected: 10
      high: 18
      unit: "days"
    dependencies: []
    uncertainty_factors:
      team_experience: "high"
      requirements_maturity: "medium"
      technical_complexity: "medium"
      team_distribution: "colocated"
      integration_complexity: "low"
    risks:
      - id: "task_risk_002"
        name: "Browser compatibility issues"
        probability: 0.25
        impact:
          type: "absolute"
          value: 3
          unit: "days"

  - id: "task_004"
    name: "Authentication & Authorization"
    description: "Implement OAuth2 and role-based access control"
    estimate:
      low: 4
      expected: 6
      high: 12
      unit: "days"
    dependencies: ["task_002"]
    uncertainty_factors:
      team_experience: "medium"
      requirements_maturity: "high"
      technical_complexity: "high"
      team_distribution: "colocated"
      integration_complexity: "high"
    risks:
      - id: "task_risk_003"
        name: "Security audit findings"
        probability: 0.30
        impact:
          type: "absolute"
          value: 5
          unit: "days"

  - id: "task_005"
    name: "Integration testing"
    description: "End-to-end integration tests"
    estimate:
      low: 3
      expected: 5
      high: 8
      unit: "days"
    dependencies: ["task_002", "task_003", "task_004"]
    uncertainty_factors:
      team_experience: "high"
      requirements_maturity: "high"
      technical_complexity: "medium"
      team_distribution: "colocated"
      integration_complexity: "high"
    risks: []

  - id: "task_006"
    name: "Performance optimization"
    description: "Optimize API and frontend performance"
    estimate:
      low: 2
      expected: 4
      high: 7
      unit: "days"
    dependencies: ["task_005"]
    uncertainty_factors:
      team_experience: "medium"
      requirements_maturity: "medium"
      technical_complexity: "high"
      team_distribution: "colocated"
      integration_complexity: "medium"
    risks:
      - id: "task_risk_004"
        name: "Performance targets not met"
        probability: 0.35
        impact:
          type: "absolute"
          value: 4
          unit: "days"

  - id: "task_007"
    name: "Documentation"
    description: "API documentation and user guides"
    estimate:
      low: 2
      expected: 3
      high: 5
      unit: "days"
    dependencies: ["task_002", "task_003"]
    uncertainty_factors:
      team_experience: "high"
      requirements_maturity: "high"
      technical_complexity: "low"
      team_distribution: "colocated"
      integration_complexity: "low"
    risks: []

  - id: "task_008"
    name: "Deployment & DevOps"
    description: "Setup CI/CD pipeline and production deployment"
    estimate:
      low: 3
      expected: 5
      high: 9
      unit: "days"
    dependencies: ["task_006"]
    uncertainty_factors:
      team_experience: "medium"
      requirements_maturity: "medium"
      technical_complexity: "medium"
      team_distribution: "distributed"
      integration_complexity: "high"
    risks:
      - id: "task_risk_005"
        name: "Infrastructure issues"
        probability: 0.20
        impact:
          type: "absolute"
          value: 3
          unit: "days"
```

```bash
mcprojsim simulate examples/sample_project.yaml --minimal --seed 42
```

```text
mcprojsim v0.15.0
Run: 2026-04-25

Project Overview:
  Project: Customer Portal Redesign
  Start Date: 2025-11-01
  Number of Tasks: 8
  Effective Default Distribution: triangular
  T-Shirt Category Used: story
  Hours per Day: 8.0
  Max Parallel Tasks: 2
  Schedule Mode: dependency_only

Calendar Time Statistical Summary:
  Mean: 580.89 hours (73 working days)
  Median (P50): 574.73 hours
  Std Dev: 78.46 hours
  Minimum: 365.50 hours
  Maximum: 924.02 hours

Project Effort Statistical Summary:
  Mean: 686.35 person-hours (86 person-days)
  Median (P50): 684.08 person-hours
  Std Dev: 61.54 person-hours
  Minimum: 487.94 person-hours
  Maximum: 902.14 person-hours

Calendar Time Confidence Intervals:
  P25: 524.00 hours (66 working days)  (2026-02-02)
  P50: 574.73 hours (72 working days)  (2026-02-10)
  P75: 629.98 hours (79 working days)  (2026-02-19)
  P80: 645.37 hours (81 working days)  (2026-02-23)
  P85: 663.34 hours (83 working days)  (2026-02-25)
  P90: 685.64 hours (86 working days)  (2026-03-02)
  P95: 722.71 hours (91 working days)  (2026-03-09)
  P99: 789.05 hours (99 working days)  (2026-03-19)
```

Key observations:

- Effort and calendar time differ (`86 person-days` effort vs `73 working days` calendar) because some tasks run in parallel.
- The positive skewness (0.48) shows a right-skewed distribution — risks and uncertainty create a longer tail toward delays.

See `examples/sample_project.yaml` in the repository.



## Log-Normal Distribution

For tasks where extreme overruns are more probable than a triangular distribution predicts:

```yaml
tasks:
  - id: "research"
    name: "Research new technology"
    estimate:
      distribution: "lognormal"
      low: 2
      expected: 5
      high: 14
      unit: "days"
    dependencies: []
```

The shifted log-normal distribution produces a heavier right tail, making it
suitable for research, exploration, or tasks with high uncertainty about upper
bounds.



## Constrained Scheduling with `team_size`

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
    estimate: { low: 8, expected: 16, high: 24 }
  - id: "task_002"
    name: "Task 2"
    estimate: { low: 40, expected: 64, high: 96 }
    dependencies: ["task_001"]
```

```bash
mcprojsim simulate examples/team_size_demo_with_team_size.yaml --minimal --seed 42
```

```text
mcprojsim v0.15.0
Run: 2026-04-25

Project Overview:
  Project: Team Size Demo
  Start Date: 2026-04-01
  Number of Tasks: 2
  Effective Default Distribution: triangular
  T-Shirt Category Used: story
  Hours per Day: 8.0
  Max Parallel Tasks: 1
  Schedule Mode: resource_constrained

Calendar Time Statistical Summary:
  Mean: 335.59 hours (42 working days)
  Median (P50): 338.16 hours
  Std Dev: 46.63 hours
  Minimum: 196.00 hours
  Maximum: 486.77 hours

Project Effort Statistical Summary:
  Mean: 82.69 person-hours (11 person-days)
  Median (P50): 82.16 person-hours
  Std Dev: 11.85 person-hours
  Minimum: 52.00 person-hours
  Maximum: 118.77 person-hours

Calendar Time Confidence Intervals:
  P10: 291.31 hours (37 working days)  (2026-05-22)
  P25: 314.03 hours (40 working days)  (2026-05-27)
  P50: 338.16 hours (43 working days)  (2026-06-01)
  P75: 363.12 hours (46 working days)  (2026-06-04)
  P80: 365.33 hours (46 working days)  (2026-06-04)
  P85: 384.05 hours (49 working days)  (2026-06-09)
  P90: 386.92 hours (49 working days)  (2026-06-09)
  P95: 390.98 hours (49 working days)  (2026-06-09)
  P99: 461.04 hours (58 working days)  (2026-06-22)
```

Compare with the same project **without** `team_size` (dependency-only mode):

```bash
mcprojsim simulate examples/team_size_demo_base.yaml --minimal --seed 42
```

```text
mcprojsim v0.15.0
Run: 2026-04-25

Project Overview:
  Project: Team Size Demo
  Start Date: 2026-04-01
  Number of Tasks: 2
  Effective Default Distribution: triangular
  T-Shirt Category Used: story
  Hours per Day: 8.0
  Max Parallel Tasks: 1
  Schedule Mode: dependency_only

Calendar Time Statistical Summary:
  Mean: 82.66 hours (11 working days)
  Median (P50): 82.16 hours
  Std Dev: 11.94 hours
  Minimum: 49.42 hours
  Maximum: 116.52 hours

Project Effort Statistical Summary:
  Mean: 82.66 person-hours (11 person-days)
  Median (P50): 82.16 person-hours
  Std Dev: 11.94 person-hours
  Minimum: 49.42 person-hours
  Maximum: 116.52 person-hours

Calendar Time Confidence Intervals:
  P10: 66.98 hours (9 working days)  (2026-04-14)
  P25: 74.24 hours (10 working days)  (2026-04-15)
  P50: 82.16 hours (11 working days)  (2026-04-16)
  P75: 91.13 hours (12 working days)  (2026-04-17)
  P80: 93.49 hours (12 working days)  (2026-04-17)
  P85: 95.91 hours (12 working days)  (2026-04-17)
  P90: 98.90 hours (13 working days)  (2026-04-20)
  P95: 103.09 hours (13 working days)  (2026-04-20)
  P99: 108.98 hours (14 working days)  (2026-04-21)
```

Key observations:

- Adding `team_size` switches from `dependency_only` to `resource_constrained`.
- Calendar time increases significantly (P50: 17 → 67 working days) because resources are assigned one at a time by default (`max_resources: 1`), and working calendars now account for weekends and non-working hours.
- Effort remains the same — only elapsed calendar time changes.

See `examples/team_size_demo_base.yaml` and `examples/team_size_demo_with_team_size.yaml` in the repository.



## Constrained Scheduling with Explicit Resources and Calendars

For full control, define resources with individual skill levels, productivity, sickness probability, and planned absences. Attach resources to named calendars with custom work patterns.

```yaml
project:
  name: "Onboarding Portal"
  description: "Constrained scheduling example with explicit resources and calendars"
  start_date: "2026-04-01"
  hours_per_day: 8
  confidence_levels: [50, 80, 90, 95]

tasks:
  - id: "task_001"
    name: "Requirements"
    estimate: { low: 8, expected: 16, high: 24 }

  - id: "task_002"
    name: "Implementation"
    estimate: { low: 40, expected: 64, high: 96 }
    dependencies: ["task_001"]
    resources: ["alice", "bob"]
    max_resources: 2
    min_experience_level: 2

  - id: "task_003"
    name: "Testing"
    estimate: { low: 16, expected: 24, high: 40 }
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
mcprojsim simulate examples/constrained_portal.yaml --minimal --seed 42 --iterations 200
```

```text
mcprojsim v0.15.0
Run: 2026-04-25

Project Overview:
  Project: Onboarding Portal
  Start Date: 2026-04-01
  Number of Tasks: 3
  Effective Default Distribution: triangular
  T-Shirt Category Used: story
  Hours per Day: 8.0
  Max Parallel Tasks: 1
  Schedule Mode: resource_constrained

Calendar Time Statistical Summary:
  Mean: 377.05 hours (48 working days)
  Median (P50): 363.68 hours
  Std Dev: 50.00 hours
  Minimum: 288.97 hours
  Maximum: 531.94 hours

Project Effort Statistical Summary:
  Mean: 108.80 person-hours (14 person-days)
  Median (P50): 108.03 person-hours
  Std Dev: 12.31 person-hours
  Minimum: 74.53 person-hours
  Maximum: 137.90 person-hours

Calendar Time Confidence Intervals:
  P50: 363.68 hours (46 working days)  (2026-06-04)
  P80: 391.05 hours (49 working days)  (2026-06-09)
  P90: 462.23 hours (58 working days)  (2026-06-22)
  P95: 482.20 hours (61 working days)  (2026-06-25)
```

Key observations:

- `resources` on `task_002` restricts it to only `alice` and `bob`.
- `max_resources: 2` allows both to work in parallel on that task.
- `min_experience_level: 2` filters out any resource below that skill tier.
- `sickness_prob` introduces stochastic sick days that vary across iterations.
- `planned_absence` blocks specific dates deterministically.
- Bob's `part_time` calendar (6 hours/day, Mon–Thu) reduces his available capacity.
- Calendar time (78 working days) is much larger than effort (22 person-days) due to calendar constraints, weekends, holidays, and sickness.

For a full constrained walkthrough with incremental complexity, see the [Constrained Scheduling Guide](user_guide/10_constrained.md).



## Natural Language Project Generation

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
- Depends on Task1
- Size XL
Task 3:
- Design solution
- Depends on Task 2
- Size. XL
```

```bash
mcprojsim generate examples/nl_example.txt -o .build/gen-examples/nl_project.yaml
mcprojsim simulate .build/gen-examples/nl_project.yaml --minimal --seed 42
```

```text
mcprojsim v0.15.0
Run: 2026-04-25

Project Overview:
  Project: Rework Web Interface
  Start Date: 2026-06-02
  Number of Tasks: 3
  Effective Default Distribution: triangular
  T-Shirt Category Used: story
  Hours per Day: 8.0
  Max Parallel Tasks: 1
  Schedule Mode: dependency_only

Calendar Time Statistical Summary:
  Mean: 1052.49 hours (132 working days)
  Median (P50): 1042.54 hours
  Std Dev: 132.88 hours
  Minimum: 736.96 hours
  Maximum: 1533.41 hours

Project Effort Statistical Summary:
  Mean: 1052.49 person-hours (132 person-days)
  Median (P50): 1042.54 person-hours
  Std Dev: 132.88 person-hours
  Minimum: 736.96 person-hours
  Maximum: 1533.41 person-hours

Calendar Time Confidence Intervals:
  P50: 1042.54 hours (131 working days)  (2026-12-02)
  P80: 1167.75 hours (146 working days)  (2026-12-23)
  P90: 1233.46 hours (155 working days)  (2027-01-05)
  P95: 1285.85 hours (161 working days)  (2027-01-13)
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
mcprojsim generate examples/nl_constrained_example.txt -o .build/gen-examples/nl_constrained_project.yaml
mcprojsim simulate .build/gen-examples/nl_constrained_project.yaml --minimal --seed 42 --iterations 200
```

```text
mcprojsim v0.15.0
Run: 2026-04-25

Project Overview:
  Project: Platform Migration
  Start Date: 2026-05-01
  Number of Tasks: 4
  Effective Default Distribution: triangular
  T-Shirt Category Used: story
  Hours per Day: 8.0
  Max Parallel Tasks: 1
  Schedule Mode: resource_constrained

Calendar Time Statistical Summary:
  Mean: 840.04 hours (106 working days)
  Median (P50): 819.88 hours
  Std Dev: 90.25 hours
  Minimum: 630.72 hours
  Maximum: 1272.02 hours

Project Effort Statistical Summary:
  Mean: 264.61 person-hours (34 person-days)
  Median (P50): 263.89 person-hours
  Std Dev: 24.51 person-hours
  Minimum: 206.48 person-hours
  Maximum: 326.63 person-hours

Calendar Time Confidence Intervals:
  P50: 819.88 hours (103 working days)  (2026-09-23)
  P80: 918.51 hours (115 working days)  (2026-10-09)
  P90: 942.87 hours (118 working days)  (2026-10-14)
  P95: 991.48 hours (124 working days)  (2026-10-22)
```

The generated YAML includes full `resources:` and `calendars:` sections. Use `--validate-only` to check your description before generating:

```bash
mcprojsim generate examples/nl_constrained_example.txt --validate-only
```

```text
✓ Valid: 'Platform Migration' with 4 task(s)
```

See `examples/nl_example.txt` and `examples/nl_constrained_example.txt` in the repository.



## Sprint Planning

Sprint-planning examples combine the normal task simulation with a sprint-based forecast built from historical sprint results.

### Minimal story-point forecast

```yaml
project:
  name: "Sprint Planning Minimal"
  start_date: "2026-05-04"
  confidence_levels: [50, 80, 90]

tasks:
  - id: "task_001"
    name: "Foundation"
    estimate:
      story_points: 3
  - id: "task_002"
    name: "Backend API"
    estimate:
      story_points: 5
  - id: "task_003"
    name: "Frontend"
    estimate:
      story_points: 8
  - id: "task_004"
    name: "Integration"
    estimate:
      story_points: 5
  - id: "task_005"
    name: "Release prep"
    estimate:
      story_points: 3

sprint_planning:
  enabled: true
  sprint_length_weeks: 2
  capacity_mode: story_points
  planning_confidence_level: 0.8
  history:
    - sprint_id: "SPR-001"
      completed_story_points: 10
      spillover_story_points: 1
    - sprint_id: "SPR-002"
      completed_story_points: 9
      spillover_story_points: 2
      added_story_points: 1
    - sprint_id: "SPR-003"
      completed_story_points: 11
      spillover_story_points: 1
      removed_story_points: 1
```

```bash
mcprojsim simulate examples/sprint_planning_minimal.yaml --minimal --seed 42
```

```text
mcprojsim v0.15.0
Run: 2026-04-25

Project Overview:
  Project: Sprint Planning Minimal
  Start Date: 2026-05-04
  Number of Tasks: 5
  Effective Default Distribution: triangular
  T-Shirt Category Used: story
  Hours per Day: 8.0
  Max Parallel Tasks: 5
  Schedule Mode: dependency_only

Calendar Time Statistical Summary:
  Mean: 74.92 hours (10 working days)
  Median (P50): 72.58 hours
  Std Dev: 16.38 hours
  Minimum: 41.37 hours
  Maximum: 119.56 hours

Project Effort Statistical Summary:
  Mean: 210.51 person-hours (27 person-days)
  Median (P50): 209.49 person-hours
  Std Dev: 21.91 person-hours
  Minimum: 146.41 person-hours
  Maximum: 290.15 person-hours

Calendar Time Confidence Intervals:
  P50: 72.58 hours (10 working days)  (2026-05-18)
  P80: 89.98 hours (12 working days)  (2026-05-20)
  P90: 98.82 hours (13 working days)  (2026-05-21)

Sprint Planning Summary:
Sprint Length: 2 weeks
Planning Confidence Level: 80%
Removed Work Treatment: churn_only
Velocity Model: empirical
Planned Commitment Guidance: 7.55
Historical Sampling Mode: matching_cadence
Historical Observations: 3
Carryover Mean: 0.00
Aggregate Spillover Rate: 0.0000
Observed Disruption Frequency: 0.0000

Sprint Count Statistical Summary:
Mean: 3.00 sprints
Median (P50): 3.00 sprints
Std Dev: 0.00 sprints
Minimum: 3.00 sprints
Maximum: 3.00 sprints
Coefficient of Variation: 0.0000

Sprint Count Confidence Intervals:
  P50: 3 sprints  (2026-06-01)
  P80: 3 sprints  (2026-06-01)
  P90: 3 sprints  (2026-06-01)
```

Key observations:

- Uses `story_points` as the sprint-capacity unit.
- Three historical sprint rows are enough to start forecasting.
- The sprint summary shows commitment guidance and sprint-count percentiles alongside the regular project forecast.

### Advanced sprint forecast

```yaml
project:
  name: "Sprint Planning Advanced"
  start_date: "2026-05-04"
  confidence_levels: [50, 80, 90]

tasks:
  - id: "task_001"
    name: "Discovery"
    estimate:
      story_points: 3
  - id: "task_002"
    name: "Core API"
    estimate:
      story_points: 8
  - id: "task_003"
    name: "UI flow"
    estimate:
      story_points: 5
  - id: "task_004"
    name: "Reporting"
    estimate:
      story_points: 8
    spillover_probability_override: 0.55
  - id: "task_005"
    name: "Hardening"
    estimate:
      story_points: 5
  - id: "task_006"
    name: "Rollout"
    estimate:
      story_points: 3

sprint_planning:
  enabled: true
  sprint_length_weeks: 2
  capacity_mode: story_points
  planning_confidence_level: 0.85
  removed_work_treatment: reduce_backlog
  future_sprint_overrides:
    - sprint_number: 2
      capacity_multiplier: 0.7
      notes: "Shared release sprint"
    - start_date: "2026-06-29"
      holiday_factor: 0.8
      notes: "Summer vacation period"
  volatility_overlay:
    enabled: true
    disruption_probability: 0.25
    disruption_multiplier_low: 0.6
    disruption_multiplier_expected: 0.8
    disruption_multiplier_high: 1.0
  spillover:
    enabled: true
    model: logistic
    size_reference_points: 5
    consumed_fraction_alpha: 3.25
    consumed_fraction_beta: 1.75
  history:
    - sprint_id: "SPR-001"
      completed_story_points: 12
      spillover_story_points: 1
      added_story_points: 1
    - sprint_id: "SPR-002"
      completed_story_points: 10
      spillover_story_points: 3
      added_story_points: 2
      removed_story_points: 1
      holiday_factor: 0.9
    - sprint_id: "SPR-003"
      completed_story_points: 11
      spillover_story_points: 2
    - sprint_id: "SPR-004"
      completed_story_points: 13
      spillover_story_points: 1
      removed_story_points: 1
```

```bash
mcprojsim simulate examples/sprint_planning_advanced.yaml --minimal --table --seed 42 --iterations 200
```

```text
mcprojsim v0.15.0
Run: 2026-04-25

Project Overview:
┌────────────────────────────────┬───────────────────────────────────┐
│ Field                          │ Value                             │
├────────────────────────────────┼───────────────────────────────────┤
│ Project                        │ Sprint Planning Advanced          │
│ Start Date                     │ 2026-05-04                        │
│ Number of Tasks                │ 6                                 │
│ Effective Default Distribution │ triangular                        │
│ T-Shirt Category Used          │ story                             │
│ Hours per Day                  │ 8.0                               │
│ Max Parallel Tasks             │ 6                                 │
│ Schedule Mode                  │ dependency_only                   │
└────────────────────────────────┴───────────────────────────────────┘

Calendar Time Statistical Summary:
┌──────────────┬─────────────────────────────────────────────────────┐
│ Metric       │ Value                                               │
├──────────────┼─────────────────────────────────────────────────────┤
│ Mean         │ 86.31 hours (11 working days)                       │
│ Median (P50) │ 85.93 hours                                         │
│ Std Dev      │ 14.55 hours                                         │
│ Minimum      │ 53.43 hours                                         │
│ Maximum      │ 118.88 hours                                        │
└──────────────┴─────────────────────────────────────────────────────┘

Project Effort Statistical Summary:
┌──────────────┬─────────────────────────────────────────────────────┐
│ Metric       │ Value                                               │
├──────────────┼─────────────────────────────────────────────────────┤
│ Mean         │ 287.15 person-hours (36 person-days)                │
│ Median (P50) │ 287.50 person-hours                                 │
│ Std Dev      │ 27.30 person-hours                                  │
│ Minimum      │ 227.60 person-hours                                 │
│ Maximum      │ 369.30 person-hours                                 │
└──────────────┴─────────────────────────────────────────────────────┘

Calendar Time Confidence Intervals:
┌──────────────┬─────────┬────────────────┬──────────────────────────┐
│ Percentile   │   Hours │   Working Days │ Date                     │
├──────────────┼─────────┼────────────────┼──────────────────────────┤
│ P50          │   85.93 │             11 │ 2026-05-19               │
│ P80          │   99.93 │             13 │ 2026-05-21               │
│ P90          │  106.82 │             14 │ 2026-05-22               │
└──────────────┴─────────┴────────────────┴──────────────────────────┘

Sprint Planning Summary:
┌───────────────────────────────┬────────────────────────────────────┐
│ Field                         │ Value                              │
├───────────────────────────────┼────────────────────────────────────┤
│ Sprint Length                 │ 2 weeks                            │
│ Planning Confidence Level     │ 85%                                │
│ Removed Work Treatment        │ reduce_backlog                     │
│ Velocity Model                │ empirical                          │
│ Planned Commitment Guidance   │ 7.13                               │
│ Historical Sampling Mode      │ matching_cadence                   │
│ Historical Observations       │ 4                                  │
│ Carryover Mean                │ 2.10                               │
│ Aggregate Spillover Rate      │ 0.1981                             │
│ Observed Disruption Frequency │ 0.7250                             │
└───────────────────────────────┴────────────────────────────────────┘

Sprint Count Statistical Summary:
┌──────────────────────────┬─────────────────────────────────────────┐
│ Metric                   │ Value                                   │
├──────────────────────────┼─────────────────────────────────────────┤
│ Mean                     │ 4.93 sprints                            │
│ Median (P50)             │ 4.00 sprints                            │
│ Std Dev                  │ 1.63 sprints                            │
│ Minimum                  │ 3.00 sprints                            │
│ Maximum                  │ 18.00 sprints                           │
│ Coefficient of Variation │ 0.3305                                  │
└──────────────────────────┴─────────────────────────────────────────┘

Sprint Count Confidence Intervals:
┌──────────────┬───────────┬─────────────────────────────────────────┐
│ Percentile   │ Sprints   │ Projected Delivery Date                 │
├──────────────┼───────────┼─────────────────────────────────────────┤
│ P50          │ 4.00      │ 2026-06-15                              │
│ P80          │ 5.00      │ 2026-06-29                              │
│ P90          │ 7.00      │ 2026-07-27                              │
└──────────────┴───────────┴─────────────────────────────────────────┘
```

Key observations:

- `future_sprint_overrides` model known upcoming capacity reductions.
- `volatility_overlay` adds random sprint-level disruption.
- `spillover` plus `spillover_probability_override` let larger items partially carry into later sprints.

### Tasks mode and external history

Tasks mode is useful for service or maintenance backlogs where items are intentionally kept to similar size.

```yaml
project:
  name: "Sprint Planning Tasks Mode"
  start_date: "2026-05-04"
  confidence_levels: [50, 80, 90]

tasks:
  - id: "task_001"
    name: "Bug fix A"
    estimate:
      low: 4
      expected: 6
      high: 8
  - id: "task_002"
    name: "Bug fix B"
    estimate:
      low: 4
      expected: 6
      high: 8
  - id: "task_003"
    name: "Bug fix C"
    estimate:
      low: 4
      expected: 6
      high: 8
  - id: "task_004"
    name: "Bug fix D"
    estimate:
      low: 4
      expected: 6
      high: 8
  - id: "task_005"
    name: "Bug fix E"
    estimate:
      low: 4
      expected: 6
      high: 8
  - id: "task_006"
    name: "Bug fix F"
    estimate:
      low: 4
      expected: 6
      high: 8

sprint_planning:
  enabled: true
  sprint_length_weeks: 1
  capacity_mode: tasks
  planning_confidence_level: 0.8
  history:
    - sprint_id: "SPR-001"
      completed_tasks: 4
      spillover_tasks: 1
    - sprint_id: "SPR-002"
      completed_tasks: 5
      spillover_tasks: 0
      added_tasks: 1
    - sprint_id: "SPR-003"
      completed_tasks: 4
      spillover_tasks: 1
      removed_tasks: 1
```

```bash
mcprojsim simulate examples/sprint_planning_tasks.yaml --minimal --seed 42
```

```text
mcprojsim v0.15.0
Run: 2026-04-25

Project Overview:
  Project: Sprint Planning Tasks Mode
  Start Date: 2026-05-04
  Number of Tasks: 6
  Effective Default Distribution: triangular
  T-Shirt Category Used: story
  Hours per Day: 8.0
  Max Parallel Tasks: 6
  Schedule Mode: dependency_only

Calendar Time Statistical Summary:
  Mean: 7.03 hours (1 working days)
  Median (P50): 7.06 hours
  Std Dev: 0.46 hours
  Minimum: 5.35 hours
  Maximum: 7.99 hours

Project Effort Statistical Summary:
  Mean: 35.99 person-hours (5 person-days)
  Median (P50): 35.98 person-hours
  Std Dev: 1.98 person-hours
  Minimum: 27.99 person-hours
  Maximum: 43.33 person-hours

Calendar Time Confidence Intervals:
  P50: 7.06 hours (1 working days)  (2026-05-05)
  P80: 7.46 hours (1 working days)  (2026-05-05)
  P90: 7.63 hours (1 working days)  (2026-05-05)

Sprint Planning Summary:
Sprint Length: 1 weeks
Planning Confidence Level: 80%
Removed Work Treatment: churn_only
Velocity Model: empirical
Planned Commitment Guidance: 2.28
Historical Sampling Mode: matching_cadence
Historical Observations: 3
Carryover Mean: 0.00
Aggregate Spillover Rate: 0.0000
Observed Disruption Frequency: 0.0000

Sprint Count Statistical Summary:
Mean: 2.00 sprints
Median (P50): 2.00 sprints
Std Dev: 0.00 sprints
Minimum: 2.00 sprints
Maximum: 2.00 sprints
Coefficient of Variation: 0.0000

Sprint Count Confidence Intervals:
  P50: 2 sprints  (2026-05-11)
  P80: 2 sprints  (2026-05-11)
  P90: 2 sprints  (2026-05-11)
```

The same sprint-planning workflow can load history from external data files:

```yaml
project:
  name: "Sprint Planning External JSON"
  start_date: "2026-05-04"
  confidence_levels: [50, 80, 90]

tasks:
  - id: "task_001"
    name: "Foundation"
    estimate:
      story_points: 3
  - id: "task_002"
    name: "API"
    estimate:
      story_points: 5
  - id: "task_003"
    name: "UI"
    estimate:
      story_points: 8
  - id: "task_004"
    name: "Release"
    estimate:
      story_points: 3

sprint_planning:
  enabled: true
  sprint_length_weeks: 2
  capacity_mode: story_points
  history:
    format: json
    path: sprint_planning_history.json
```

```json
{
  "metricDefinitions": {
    "committed_StoryPoints": "Sum of story points for issues present at sprint start; issues added during the sprint are excluded.",
    "completed_StoryPoints": "Sum of story points for issues completed during the sprint.",
    "addedIntraSprint_StoryPoints": "Sum of story points for issues added during the sprint.",
    "removedInSprint_StoryPoints": "Sum of story points removed from the sprint during execution.",
    "spilledOver_StoryPoints": "Sum of story points not completed at sprint close."
  },
  "sprints": [
    {
      "sprintUniqueID": "2026:Q1 Sprint 1",
      "startDate": "2026-01-06T09:00:00.000+01:00",
      "endDate": "2026-01-20",
      "metrics": {
        "committed_StoryPoints": 95.0,
        "completed_StoryPoints": 78.0,
        "addedIntraSprint_StoryPoints": 12.0,
        "removedInSprint_StoryPoints": 6.0,
        "spilledOver_StoryPoints": 11.0
      }
    },
    {
      "sprintUniqueID": "2026:Q1 Sprint 2",
      "endDate": "2026-02-03",
      "metrics": {
        "committed_StoryPoints": 88.0,
        "completed_StoryPoints": 82.0
      }
    },
    {
      "sprintUniqueID": "2026:Q1 Sprint 3",
      "metrics": {
        "committed_StoryPoints": 91.0,
        "completed_StoryPoints": 85.0,
        "spilledOver_StoryPoints": 4.0
      }
    }
  ]
}
```

```toml
[project]
name = "Sprint Planning External CSV"
start_date = "2026-05-04"
confidence_levels = [50, 80, 90]

[sprint_planning]
enabled = true
sprint_length_weeks = 1
capacity_mode = "story_points"

[sprint_planning.history]
format = "csv"
path = "sprint_planning_history.csv"

[[tasks]]
id = "task_001"
name = "Support ticket A"
planning_story_points = 3

[tasks.estimate]
low = 4
expected = 6
high = 8

[[tasks]]
id = "task_002"
name = "Support ticket B"
planning_story_points = 3

[tasks.estimate]
low = 4
expected = 6
high = 8

[[tasks]]
id = "task_003"
name = "Support ticket C"
planning_story_points = 3

[tasks.estimate]
low = 4
expected = 6
high = 8

[[tasks]]
id = "task_004"
name = "Support ticket D"
planning_story_points = 3

[tasks.estimate]
low = 4
expected = 6
high = 8

[[tasks]]
id = "task_005"
name = "Support ticket E"
planning_story_points = 3

[tasks.estimate]
low = 4
expected = 6
high = 8
```

```
sprintUniqueID,committed_StoryPoints,completed_StoryPoints,addedIntraSprint_StoryPoints,removedInSprint_StoryPoints,spilledOver_StoryPoints,startDate,endDate
2026:Q2 Sprint 1,32,28,4,2,2,2026-05-04T09:00:00.000+02:00,2026-05-11T09:00:00.000+02:00
2026:Q2 Sprint 2,30,29,3,1,1,2026-05-11T09:00:00.000+02:00,2026-05-18T09:00:00.000+02:00
```

Natural-language input also supports sprint-planning sections:

```text
Project: Sprint Planning from Text
Start date: 2026-05-04
Task 1:
- Discovery
- Story points: 3
Task 2:
- API implementation
- Story points: 5
Task 3:
- Frontend integration
- Story points: 8
Sprint planning:
- Sprint length: 2
- Capacity mode: story points
- Planning confidence level: 80%
Sprint history SPR-001:
- Done: 10 points
- Carryover: 1 points
Sprint history SPR-002:
- Done: 9 points
- Carryover: 2 points
- Scope added: 1 points
```

```bash
mcprojsim generate examples/sprint_planning_nl.txt -o .build/gen-examples/sprint_planning_nl.yaml
mcprojsim simulate .build/gen-examples/sprint_planning_nl.yaml --minimal --seed 42
```

```text
mcprojsim v0.15.0
Run: 2026-04-25

Project Overview:
  Project: Sprint Planning from Text
  Start Date: 2026-05-04
  Number of Tasks: 3
  Effective Default Distribution: triangular
  T-Shirt Category Used: story
  Hours per Day: 8.0
  Max Parallel Tasks: 3
  Schedule Mode: dependency_only

Calendar Time Statistical Summary:
  Mean: 74.67 hours (10 working days)
  Median (P50): 72.60 hours
  Std Dev: 16.50 hours
  Minimum: 40.24 hours
  Maximum: 118.79 hours

Project Effort Statistical Summary:
  Mean: 142.54 person-hours (18 person-days)
  Median (P50): 141.08 person-hours
  Std Dev: 19.49 person-hours
  Minimum: 90.20 person-hours
  Maximum: 212.98 person-hours

Calendar Time Confidence Intervals:
  P50: 72.60 hours (10 working days)  (2026-05-18)
  P80: 89.64 hours (12 working days)  (2026-05-20)
  P90: 98.61 hours (13 working days)  (2026-05-21)
  P95: 105.02 hours (14 working days)  (2026-05-22)

Sprint Planning Summary:
Sprint Length: 2 weeks
Planning Confidence Level: 80%
Removed Work Treatment: churn_only
Velocity Model: empirical
Planned Commitment Guidance: 7.15
Historical Sampling Mode: matching_cadence
Historical Observations: 2
Carryover Mean: 0.00
Aggregate Spillover Rate: 0.0000
Observed Disruption Frequency: 0.0000

Sprint Count Statistical Summary:
Mean: 2.00 sprints
Median (P50): 2.00 sprints
Std Dev: 0.00 sprints
Minimum: 2.00 sprints
Maximum: 2.00 sprints
Coefficient of Variation: 0.0000

Sprint Count Confidence Intervals:
  P50: 2 sprints  (2026-05-18)
  P80: 2 sprints  (2026-05-18)
  P90: 2 sprints  (2026-05-18)
```



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
| `sprint_planning_minimal.yaml` | Minimal story-point sprint forecast |
| `sprint_planning_advanced.yaml` | Advanced sprint forecast with spillover, volatility, and overrides |
| `sprint_planning_tasks.yaml` | Throughput-style sprint planning in `tasks` mode |
| `sprint_planning_external_json.yaml` | YAML project loading external JSON sprint history |
| `sprint_planning_external_csv.toml` | TOML project loading external CSV sprint history |
| `sprint_planning_nl.txt` | Natural-language sprint planning input |
| `nl_example.txt` | Natural language input (basic) |
| `nl_constrained_example.txt` | Natural language input with resources |
| `sample_config.yaml` | Custom configuration file |
