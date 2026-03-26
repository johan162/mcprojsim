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
=== Simulation Results ===

Project Overview:
Project: Website Refresh
Hours per Day: 8.0
Max Parallel Tasks: 1
Schedule Mode: dependency_only

Calendar Time Statistical Summary:
Mean: 126.93 hours (16 working days)
Median (P50): 125.74 hours
Std Dev: 17.68 hours
Minimum: 78.43 hours
Maximum: 184.27 hours
Coefficient of Variation: 0.1393
Skewness: 0.2267
Excess Kurtosis: -0.4206

Project Effort Statistical Summary:
Mean: 126.93 person-hours (16 person-days)
Median (P50): 125.74 person-hours
Std Dev: 17.68 person-hours
Minimum: 78.43 person-hours
Maximum: 184.27 person-hours
Coefficient of Variation: 0.1393
Skewness: 0.2267
Excess Kurtosis: -0.4206

Calendar Time Confidence Intervals:
  P50: 125.74 hours (16 working days)  (2026-04-23)
  P80: 142.59 hours (18 working days)  (2026-04-27)
  P90: 151.18 hours (19 working days)  (2026-04-28)
```

Key observations: two sequential tasks, no parallelism (`Max Parallel Tasks: 1`), `dependency_only` scheduling.

See `examples/quickstart_example.yaml` in the repository.



## T-Shirt Sizing

For quick estimation using relative sizes (`XS`, `S`, `M`, `L`, `XL`, `XXL`) with category-aware calibration. Bare values like `M` resolve via the configured default category, and qualified values like `epic.M` resolve directly. T-shirt mappings are configurable via the [configuration file](user_guide/task_estimation.md#t-shirt-size-estimates).

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
=== Simulation Results ===

Project Overview:
Project: Mobile App Development
Hours per Day: 8.0
Max Parallel Tasks: 2
Schedule Mode: dependency_only

Calendar Time Statistical Summary:
Mean: 3491.26 hours (437 working days)
Median (P50): 3422.83 hours
Std Dev: 578.05 hours
Minimum: 2189.84 hours
Maximum: 6092.89 hours
Coefficient of Variation: 0.1656
Skewness: 0.5892
Excess Kurtosis: 0.1221

Project Effort Statistical Summary:
Mean: 3476.64 person-hours (435 person-days)
Median (P50): 3419.67 person-hours
Std Dev: 508.01 person-hours
Minimum: 2284.80 person-hours
Maximum: 5287.37 person-hours
Coefficient of Variation: 0.1461
Skewness: 0.4073
Excess Kurtosis: -0.4388

Calendar Time Confidence Intervals:
  P10: 2791.21 hours (349 working days)  (2027-03-04)
  P50: 3422.83 hours (428 working days)  (2027-06-23)
  P75: 3869.17 hours (484 working days)  (2027-09-09)
  P80: 3981.40 hours (498 working days)  (2027-09-29)
  P85: 4103.10 hours (513 working days)  (2027-10-20)
  P90: 4273.10 hours (535 working days)  (2027-11-19)
  P95: 4516.80 hours (565 working days)  (2027-12-31)
  P99: 5055.58 hours (632 working days)  (2028-04-04)
```

Key observations: two independent starting tasks yield `Max Parallel Tasks: 2`. The wide P10–P99 spread (349–632 working days) reflects uncertainty in symbolic sizing for large effort items.

Note: T-shirt size and story point estimates must **not** include a `unit` field in the project file. The unit is controlled by the configuration.

See `examples/tshirt_sizing_project.yaml` in the repository.



## Story Points

For agile-style relative estimation using calibrated story point mappings. Default mappings are configurable via the [configuration file](user_guide/task_estimation.md#story-point-estimates).

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
=== Simulation Results ===

Project Overview:
┌────────────────────┬───────────────────┐
│ Field              │ Value             │
├────────────────────┼───────────────────┤
│ Project            │ Tiny Landing Page │
│ Hours per Day      │ 8.0               │
│ Max Parallel Tasks │ 1                 │
│ Schedule Mode      │ dependency_only   │
└────────────────────┴───────────────────┘

Calendar Time Statistical Summary:
┌──────────────────────────┬────────────────────────────────┐
│ Metric                   │ Value                          │
├──────────────────────────┼────────────────────────────────┤
│ Mean                     │ 109.90 hours (14 working days) │
│ Median (P50)             │ 109.21 hours                   │
│ Std Dev                  │ 15.97 hours                    │
│ Minimum                  │ 64.96 hours                    │
│ Maximum                  │ 167.85 hours                   │
│ Coefficient of Variation │ 0.1453                         │
│ Skewness                 │ 0.1731                         │
│ Excess Kurtosis          │ -0.2637                        │
└──────────────────────────┴────────────────────────────────┘

Project Effort Statistical Summary:
┌──────────────────────────┬──────────────────────────────────────┐
│ Metric                   │ Value                                │
├──────────────────────────┼──────────────────────────────────────┤
│ Mean                     │ 109.90 person-hours (14 person-days) │
│ Median (P50)             │ 109.21 person-hours                  │
│ Std Dev                  │ 15.97 person-hours                   │
│ Minimum                  │ 64.96 person-hours                   │
│ Maximum                  │ 167.85 person-hours                  │
│ Coefficient of Variation │ 0.1453                               │
│ Skewness                 │ 0.1731                               │
│ Excess Kurtosis          │ -0.2637                              │
└──────────────────────────┴──────────────────────────────────────┘

Calendar Time Confidence Intervals:
┌──────────────┬─────────┬────────────────┬────────────┐
│ Percentile   │   Hours │   Working Days │ Date       │
├──────────────┼─────────┼────────────────┼────────────┤
│ P50          │  109.21 │             14 │ 2026-03-19 │
│ P80          │  123.81 │             16 │ 2026-03-23 │
│ P90          │  131.03 │             17 │ 2026-03-24 │
└──────────────┴─────────┴────────────────┴────────────┘
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
=== Simulation Results ===

Project Overview:
Project: Customer Portal Redesign
Hours per Day: 8.0
Max Parallel Tasks: 2
Schedule Mode: dependency_only

Calendar Time Statistical Summary:
Mean: 580.89 hours (73 working days)
Median (P50): 574.73 hours
Std Dev: 78.46 hours
Minimum: 365.50 hours
Maximum: 924.02 hours
Coefficient of Variation: 0.1351
Skewness: 0.4798
Excess Kurtosis: 0.1518

Project Effort Statistical Summary:
Mean: 686.35 person-hours (86 person-days)
Median (P50): 684.08 person-hours
Std Dev: 61.54 person-hours
Minimum: 487.94 person-hours
Maximum: 902.14 person-hours
Coefficient of Variation: 0.0897
Skewness: 0.1210
Excess Kurtosis: -0.1140

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
=== Simulation Results ===

Project Overview:
Project: Team Size Demo
Hours per Day: 8.0
Max Parallel Tasks: 1
Schedule Mode: resource_constrained

Calendar Time Statistical Summary:
Mean: 538.33 hours (68 working days)
Median (P50): 530.25 hours
Std Dev: 80.28 hours
Minimum: 337.16 hours
Maximum: 793.05 hours
Coefficient of Variation: 0.1491
Skewness: 0.1334
Excess Kurtosis: -0.3907

Project Effort Statistical Summary:
Mean: 131.12 person-hours (17 person-days)
Median (P50): 130.25 person-hours
Std Dev: 18.79 person-hours
Minimum: 81.16 person-hours
Maximum: 185.05 person-hours
Coefficient of Variation: 0.1433
Skewness: 0.1250
Excess Kurtosis: -0.5403

Calendar Time Confidence Intervals:
  P25: 485.56 hours (61 working days)  (2026-06-25)
  P50: 530.25 hours (67 working days)  (2026-07-03)
  P75: 624.72 hours (79 working days)  (2026-07-21)
  P80: 627.91 hours (79 working days)  (2026-07-21)
  P85: 648.18 hours (82 working days)  (2026-07-24)
  P90: 652.93 hours (82 working days)  (2026-07-24)
  P95: 675.08 hours (85 working days)  (2026-07-29)
  P99: 701.04 hours (88 working days)  (2026-08-03)
```

Compare with the same project **without** `team_size` (dependency-only mode):

```bash
mcprojsim simulate examples/team_size_demo_base.yaml --minimal --seed 42
```

```text
=== Simulation Results ===

Project Overview:
Project: Team Size Demo
Hours per Day: 8.0
Max Parallel Tasks: 1
Schedule Mode: dependency_only

Calendar Time Statistical Summary:
Mean: 131.18 hours (17 working days)
Median (P50): 130.38 hours
Std Dev: 18.95 hours
Minimum: 78.42 hours
Maximum: 184.91 hours
Coefficient of Variation: 0.1445
Skewness: 0.1120
Excess Kurtosis: -0.5163

Project Effort Statistical Summary:
Mean: 131.18 person-hours (17 person-days)
Median (P50): 130.38 person-hours
Std Dev: 18.95 person-hours
Minimum: 78.42 person-hours
Maximum: 184.91 person-hours
Coefficient of Variation: 0.1445
Skewness: 0.1120
Excess Kurtosis: -0.5163

Calendar Time Confidence Intervals:
  P25: 117.83 hours (15 working days)  (2026-04-22)
  P50: 130.38 hours (17 working days)  (2026-04-24)
  P75: 144.63 hours (19 working days)  (2026-04-28)
  P80: 148.37 hours (19 working days)  (2026-04-28)
  P85: 152.21 hours (20 working days)  (2026-04-29)
  P90: 156.96 hours (20 working days)  (2026-04-29)
  P95: 163.60 hours (21 working days)  (2026-04-30)
  P99: 172.95 hours (22 working days)  (2026-05-01)
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
=== Simulation Results ===

Project Overview:
Project: Onboarding Portal
Hours per Day: 8.0
Max Parallel Tasks: 1
Schedule Mode: resource_constrained

Calendar Time Statistical Summary:
Mean: 622.35 hours (78 working days)
Median (P50): 630.16 hours
Std Dev: 82.72 hours
Minimum: 387.98 hours
Maximum: 890.12 hours
Coefficient of Variation: 0.1329
Skewness: 0.0753
Excess Kurtosis: 0.4830

Project Effort Statistical Summary:
Mean: 174.90 person-hours (22 person-days)
Median (P50): 175.84 person-hours
Std Dev: 20.43 person-hours
Minimum: 120.72 person-hours
Maximum: 225.55 person-hours
Coefficient of Variation: 0.1168
Skewness: 0.0826
Excess Kurtosis: -0.2307

Calendar Time Confidence Intervals:
  P50: 630.16 hours (79 working days)  (2026-07-21)
  P80: 676.83 hours (85 working days)  (2026-07-29)
  P90: 703.75 hours (88 working days)  (2026-08-03)
  P95: 726.73 hours (91 working days)  (2026-08-06)
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
=== Simulation Results ===

Project Overview:
Project: Rework Web Interface
Hours per Day: 8.0
Max Parallel Tasks: 1
Schedule Mode: dependency_only

Calendar Time Statistical Summary:
Mean: 1670.31 hours (209 working days)
Median (P50): 1654.52 hours
Std Dev: 210.88 hours
Minimum: 1169.56 hours
Maximum: 2433.52 hours
Coefficient of Variation: 0.1263
Skewness: 0.3511
Excess Kurtosis: -0.2986

Project Effort Statistical Summary:
Mean: 1670.31 person-hours (209 person-days)
Median (P50): 1654.52 person-hours
Std Dev: 210.88 person-hours
Minimum: 1169.56 person-hours
Maximum: 2433.52 person-hours
Coefficient of Variation: 0.1263
Skewness: 0.3511
Excess Kurtosis: -0.2986

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
mcprojsim generate examples/nl_constrained_example.txt -o .build/gen-examples/nl_constrained_project.yaml
mcprojsim simulate .build/gen-examples/nl_constrained_project.yaml --minimal --seed 42 --iterations 200
```

```text
=== Simulation Results ===

Project Overview:
Project: Platform Migration
Hours per Day: 8.0
Max Parallel Tasks: 1
Schedule Mode: resource_constrained

Calendar Time Statistical Summary:
Mean: 1256.09 hours (158 working days)
Median (P50): 1264.41 hours
Std Dev: 132.44 hours
Minimum: 962.44 hours
Maximum: 1657.45 hours
Coefficient of Variation: 0.1054
Skewness: 0.2059
Excess Kurtosis: -0.1495

Project Effort Statistical Summary:
Mean: 411.37 person-hours (52 person-days)
Median (P50): 410.01 person-hours
Std Dev: 40.80 person-hours
Minimum: 321.07 person-hours
Maximum: 509.50 person-hours
Coefficient of Variation: 0.0992
Skewness: 0.0893
Excess Kurtosis: -0.6046

Calendar Time Confidence Intervals:
  P50: 1264.41 hours (159 working days)  (2026-12-10)
  P80: 1348.09 hours (169 working days)  (2026-12-24)
  P90: 1440.65 hours (181 working days)  (2027-01-11)
  P95: 1466.63 hours (184 working days)  (2027-01-14)
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
      removed_story_points: 1```

```bash
mcprojsim simulate examples/sprint_planning_minimal.yaml --minimal --seed 42
```

```text
=== Simulation Results ===

Project Overview:
Project: Sprint Planning Minimal
Hours per Day: 8.0
Max Parallel Tasks: 5
Schedule Mode: dependency_only

Calendar Time Statistical Summary:
Mean: 118.89 hours (15 working days)
Median (P50): 115.18 hours
Std Dev: 26.00 hours
Minimum: 65.66 hours
Maximum: 189.74 hours
Coefficient of Variation: 0.2186
Skewness: 0.4313
Excess Kurtosis: -0.5763

Project Effort Statistical Summary:
Mean: 334.08 person-hours (42 person-days)
Median (P50): 332.47 person-hours
Std Dev: 34.77 person-hours
Minimum: 232.35 person-hours
Maximum: 460.47 person-hours
Coefficient of Variation: 0.1041
Skewness: 0.2056
Excess Kurtosis: -0.1693

Calendar Time Confidence Intervals:
  P50: 115.18 hours (15 working days)  (2026-05-25)
  P80: 142.80 hours (18 working days)  (2026-05-28)
  P90: 156.82 hours (20 working days)  (2026-06-01)

Sprint Planning Summary:
Sprint Length: 2 weeks
Planning Confidence Level: 80%
Removed Work Treatment: RemovedWorkTreatment.CHURN_ONLY
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
      removed_story_points: 1```

```bash
mcprojsim simulate examples/sprint_planning_advanced.yaml --minimal --table --seed 42 --iterations 200
```

```text
=== Simulation Results ===

Project Overview:
┌────────────────────┬──────────────────────────┐
│ Field              │ Value                    │
├────────────────────┼──────────────────────────┤
│ Project            │ Sprint Planning Advanced │
│ Hours per Day      │ 8.0                      │
│ Max Parallel Tasks │ 6                        │
│ Schedule Mode      │ dependency_only          │
└────────────────────┴──────────────────────────┘

Calendar Time Statistical Summary:
┌──────────────────────────┬────────────────────────────────┐
│ Metric                   │ Value                          │
├──────────────────────────┼────────────────────────────────┤
│ Mean                     │ 136.97 hours (18 working days) │
│ Median (P50)             │ 136.38 hours                   │
│ Std Dev                  │ 23.09 hours                    │
│ Minimum                  │ 84.80 hours                    │
│ Maximum                  │ 188.66 hours                   │
│ Coefficient of Variation │ 0.1686                         │
│ Skewness                 │ 0.0783                         │
│ Excess Kurtosis          │ -0.8139                        │
└──────────────────────────┴────────────────────────────────┘

Project Effort Statistical Summary:
┌──────────────────────────┬──────────────────────────────────────┐
│ Metric                   │ Value                                │
├──────────────────────────┼──────────────────────────────────────┤
│ Mean                     │ 455.70 person-hours (57 person-days) │
│ Median (P50)             │ 456.26 person-hours                  │
│ Std Dev                  │ 43.32 person-hours                   │
│ Minimum                  │ 361.20 person-hours                  │
│ Maximum                  │ 586.08 person-hours                  │
│ Coefficient of Variation │ 0.0951                               │
│ Skewness                 │ 0.0635                               │
│ Excess Kurtosis          │ -0.2823                              │
└──────────────────────────┴──────────────────────────────────────┘

Calendar Time Confidence Intervals:
┌──────────────┬─────────┬────────────────┬────────────┐
│ Percentile   │   Hours │   Working Days │ Date       │
├──────────────┼─────────┼────────────────┼────────────┤
│ P50          │  136.38 │             18 │ 2026-05-28 │
│ P80          │  158.59 │             20 │ 2026-06-01 │
│ P90          │  169.52 │             22 │ 2026-06-03 │
└──────────────┴─────────┴────────────────┴────────────┘

Sprint Planning Summary:
┌───────────────────────────────┬─────────────────────────────────────┐
│ Field                         │ Value                               │
├───────────────────────────────┼─────────────────────────────────────┤
│ Sprint Length                 │ 2 weeks                             │
│ Planning Confidence Level     │ 85%                                 │
│ Removed Work Treatment        │ RemovedWorkTreatment.REDUCE_BACKLOG │
│ Velocity Model                │ empirical                           │
│ Planned Commitment Guidance   │ 7.13                                │
│ Historical Sampling Mode      │ matching_cadence                    │
│ Historical Observations       │ 4                                   │
│ Carryover Mean                │ 2.10                                │
│ Aggregate Spillover Rate      │ 0.1981                              │
│ Observed Disruption Frequency │ 0.7250                              │
└───────────────────────────────┴─────────────────────────────────────┘

Sprint Count Statistical Summary:
┌──────────────────────────┬───────────────┐
│ Metric                   │ Value         │
├──────────────────────────┼───────────────┤
│ Mean                     │ 4.93 sprints  │
│ Median (P50)             │ 4.00 sprints  │
│ Std Dev                  │ 1.63 sprints  │
│ Minimum                  │ 3.00 sprints  │
│ Maximum                  │ 18.00 sprints │
│ Coefficient of Variation │ 0.3305        │
└──────────────────────────┴───────────────┘

Sprint Count Confidence Intervals:
┌──────────────┬───────────┬───────────────────────────┐
│ Percentile   │ Sprints   │ Projected Delivery Date   │
├──────────────┼───────────┼───────────────────────────┤
│ P50          │ 4.00      │ 2026-06-15                │
│ P80          │ 5.00      │ 2026-06-29                │
│ P90          │ 7.00      │ 2026-07-27                │
└──────────────┴───────────┴───────────────────────────┘
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
      removed_tasks: 1```

```bash
mcprojsim simulate examples/sprint_planning_tasks.yaml --minimal --seed 42
```

```text
=== Simulation Results ===

Project Overview:
Project: Sprint Planning Tasks Mode
Hours per Day: 8.0
Max Parallel Tasks: 6
Schedule Mode: dependency_only

Calendar Time Statistical Summary:
Mean: 11.16 hours (2 working days)
Median (P50): 11.21 hours
Std Dev: 0.73 hours
Minimum: 8.49 hours
Maximum: 12.67 hours
Coefficient of Variation: 0.0656
Skewness: -0.3072
Excess Kurtosis: -0.4514

Project Effort Statistical Summary:
Mean: 57.12 person-hours (8 person-days)
Median (P50): 57.11 person-hours
Std Dev: 3.15 person-hours
Minimum: 44.41 person-hours
Maximum: 68.77 person-hours
Coefficient of Variation: 0.0551
Skewness: -0.0057
Excess Kurtosis: -0.0762

Calendar Time Confidence Intervals:
  P50: 11.21 hours (2 working days)  (2026-05-06)
  P80: 11.84 hours (2 working days)  (2026-05-06)
  P90: 12.11 hours (2 working days)  (2026-05-06)

Sprint Planning Summary:
Sprint Length: 1 weeks
Planning Confidence Level: 80%
Removed Work Treatment: RemovedWorkTreatment.CHURN_ONLY
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
    path: sprint_planning_history.json```

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
high = 8```

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
- Scope added: 1 points```

```bash
mcprojsim generate examples/sprint_planning_nl.txt -o .build/gen-examples/sprint_planning_nl.yaml
mcprojsim simulate .build/gen-examples/sprint_planning_nl.yaml --minimal --seed 42
```

```text
=== Simulation Results ===

Project Overview:
Project: Sprint Planning from Text
Hours per Day: 8.0
Max Parallel Tasks: 3
Schedule Mode: dependency_only

Calendar Time Statistical Summary:
Mean: 118.50 hours (15 working days)
Median (P50): 115.22 hours
Std Dev: 26.19 hours
Minimum: 63.87 hours
Maximum: 188.52 hours
Coefficient of Variation: 0.2210
Skewness: 0.4093
Excess Kurtosis: -0.5588

Project Effort Statistical Summary:
Mean: 226.21 person-hours (29 person-days)
Median (P50): 223.89 person-hours
Std Dev: 30.93 person-hours
Minimum: 143.14 person-hours
Maximum: 338.00 person-hours
Coefficient of Variation: 0.1368
Skewness: 0.2634
Excess Kurtosis: -0.3135

Calendar Time Confidence Intervals:
  P50: 115.22 hours (15 working days)  (2026-05-25)
  P80: 142.26 hours (18 working days)  (2026-05-28)
  P90: 156.49 hours (20 working days)  (2026-06-01)
  P95: 166.67 hours (21 working days)  (2026-06-02)

Sprint Planning Summary:
Sprint Length: 2 weeks
Planning Confidence Level: 80%
Removed Work Treatment: RemovedWorkTreatment.CHURN_ONLY
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
