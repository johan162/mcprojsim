# Risks

This chapter explains how `mcprojsim` models schedule variation due to **risks**. (The other source of schedule variation comes from **uncertainty factors** — see [Uncertainty Factors](uncertainty_factors.md).) Both influence the simulated project duration, but they represent fundamentally different ideas and are handled differently by the simulation engine.

**Risks** are discrete events that may or may not happen. A failed security audit, the departure of a key developer, or a sudden change in requirements are all risks. Each risk has a probability of occurring and an impact if it does.



## How Risks Affect the Simulation

During each Monte Carlo iteration, every risk is independently evaluated. The simulator draws a random number and compares it to the risk's probability. If the risk triggers, its impact is added to the relevant duration. If it does not trigger, no penalty is applied.

Because risks are evaluated independently in each iteration, the overall project duration distribution naturally reflects the combined likelihood of various risk combinations. Some iterations will have no risks trigger at all. Others will see several risks fire simultaneously. Over thousands of iterations, the statistical summary captures the full range of possibilities.

### The Order of Operations

For each iteration, the simulation processes each task as follows:

1. **Sample the base duration** from the task's estimate distribution (triangular or log-normal).
2. **Apply uncertainty factor multipliers** to produce an adjusted duration.
3. **Evaluate task-level risks** against the adjusted duration; any triggered risk adds its impact.
4. **Schedule tasks** respecting dependency constraints.
5. **Evaluate project-level risks** against the overall project duration; any triggered risk adds its impact to the total.

This order matters. Uncertainty factors scale the base estimate before risks are evaluated. A percentage-based task risk therefore acts on the already-adjusted duration, not on the raw sampled value. Project-level risks are applied after scheduling, so they affect the final project completion time but do not change which tasks appear on the critical path for that iteration.



## Risk Definitions

Every risk in `mcprojsim` has four key properties:

| Property      | Required | Description                                                                 |
|---------------|----------|-----------------------------------------------------------------------------|
| `id`          | Yes      | A unique identifier for the risk (e.g., `"risk_001"`)                      |
| `name`        | Yes      | A human-readable label                                                     |
| `probability` | Yes      | The likelihood of the risk occurring, between `0.0` and `1.0`              |
| `impact`      | Yes      | The time penalty if the risk triggers (absolute value or structured object) |
| `description` | No       | An optional free-text explanation                                          |

### Specifying Impact

Risk impact can be expressed in two ways:

**Simple absolute impact** — a single number representing hours of effort. When `impact` is given as a plain number without a `type`, it is always treated as an absolute value in hours:

```yaml
risks:
  - id: "task_risk_001"
    name: "Schema migration issues"
    probability: 0.20
    impact: 2
```

If this risk triggers, it adds exactly 2 hours to the task duration. There is no percentage interpretation; a plain number is always an absolute time penalty in hours.

**Structured impact** — an object with explicit type, value, and optional unit. This form is required when you want percentage-based impact; there is no way to get percentage behavior without specifying `type: "percentage"` explicitly:

```yaml
risks:
  - id: "risk_001"
    name: "Key developer leaves"
    probability: 0.15
    impact:
      type: "percentage"
      value: 20
```

If this risk triggers, it adds 20% of the current duration. The percentage is calculated against the base duration passed to the risk evaluator — for task-level risks, this is the uncertainty-adjusted task duration; for project-level risks, it is the scheduled project duration.

```yaml
risks:
  - id: "risk_002"
    name: "Requirements change"
    probability: 0.30
    impact:
      type: "absolute"
      value: 10
      unit: "days"
```

The structured form with `type: "absolute"` behaves the same as the simple numeric form but is more explicit. When a `unit` is specified (e.g., `"days"`), the value is converted to hours using the project's `hours_per_day` setting.

### Summary of Impact Types

| Form                          | Meaning                                                   |
|-------------------------------|-----------------------------------------------------------|
| `impact: 5`                   | Adds 5 hours if triggered                                 |
| `impact: { type: "absolute", value: 5 }` | Adds 5 hours if triggered (explicit form)     |
| `impact: { type: "absolute", value: 2, unit: "days" }` | Adds 2 days (converted to hours) if triggered |
| `impact: { type: "percentage", value: 20 }` | Adds 20% of current duration if triggered |



## Task-Level Risks

Task-level risks represent events tied to a specific piece of work. They are defined inside the `risks` list of a task and are evaluated once per iteration for that task.

### When to Use Task-Level Risks

Use task-level risks for events that are specific to one task or activity. Typical examples include:

- Schema migration problems during a database redesign
- Browser compatibility issues in frontend development
- Security audit findings requiring rework on an authentication task
- Performance targets not being met during an optimization phase
- Infrastructure provisioning failures for a deployment task

### Cumulative Evaluation

If a task defines multiple risks, each risk is evaluated independently. When more than one risk triggers in the same iteration, their impacts are cumulative — they are simply added together.

For example, if a task has two risks:

```yaml
risks:
  - id: "risk_a"
    name: "Data format issues"
    probability: 0.25
    impact: 3
  - id: "risk_b"
    name: "Vendor API downtime"
    probability: 0.10
    impact: 5
```

In a given iteration, neither, one, or both may trigger. If both trigger, the task receives an additional 8 days on top of its adjusted duration.

### Full Task Example with Risks

```yaml
tasks:
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
        impact: 5
```

In each iteration, the simulator:

1. Samples a base duration between 4 and 12 days (most likely around 6).
2. Multiplies by the combined uncertainty factor (in this case the product of multipliers for medium experience, high requirements maturity, high technical complexity, colocated distribution, and high integration complexity).
3. Evaluates the "Security audit findings" risk: with 30% probability, adds 5 days.
4. Uses the resulting value as the task duration for scheduling.



## Project-Level Risks

Project-level risks represent events that affect the project as a whole rather than any single task. They are defined in the top-level `project_risks` list and are evaluated once per iteration after the schedule has been computed.

### When to Use Project-Level Risks

Use project-level risks for events whose impact is not easily attributed to one task:

- Loss of a key team member mid-project
- Major requirements changes that affect multiple work streams
- Organizational restructuring or budget reductions
- Regulatory or compliance surprises
- Vendor contract delays

### Percentage vs. Absolute Impact

Project-level risks are particularly well suited to percentage-based impact, because the absolute impact of losing a developer or changing requirements is often proportional to the project size.

```yaml
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
```

In this example, if the first risk triggers in an iteration where the scheduled project duration is 60 days, it adds 12 days (20% of 60). The second risk, if triggered, always adds a flat 10 days regardless of project length.

### How Project-Level Risks Interact with the Critical Path

Project-level risks are applied after the schedule is computed. This means they increase the final project duration but do not change which tasks are identified as being on the critical path for that iteration. The critical path is determined purely by task durations, uncertainty factors, task-level risks, and dependency structure.



## Combining Risks at Both Levels

A realistic project model often uses both task-level and project-level risks. There is no conflict between them — they operate at different stages of the simulation pipeline.

### Complete Project Example with Both Risk Types

```yaml
project:
  name: "Payment Gateway Integration"
  description: "Integrate new payment provider into existing platform"
  start_date: "2026-05-01"
  confidence_levels: [50, 80, 90, 95]

project_risks:
  - id: "proj_risk_001"
    name: "Vendor API contract delay"
    probability: 0.20
    impact:
      type: "absolute"
      value: 15
      unit: "days"
    description: "Payment provider delays final API specification delivery"

  - id: "proj_risk_002"
    name: "Compliance review extends timeline"
    probability: 0.25
    impact:
      type: "percentage"
      value: 15
    description: "PCI-DSS compliance review reveals additional work"

tasks:
  - id: "pay_001"
    name: "API client library"
    description: "Build client library for vendor payment API"
    estimate:
      low: 5
      expected: 8
      high: 14
      unit: "days"
    dependencies: []
    risks:
      - id: "pay_risk_001"
        name: "Incomplete vendor documentation"
        probability: 0.35
        impact: 4

  - id: "pay_002"
    name: "Transaction processing engine"
    description: "Core payment transaction handling logic"
    estimate:
      low: 8
      expected: 12
      high: 20
      unit: "days"
    dependencies: ["pay_001"]
    risks:
      - id: "pay_risk_002"
        name: "Edge cases in currency conversion"
        probability: 0.20
        impact: 3
      - id: "pay_risk_003"
        name: "Retry logic complexity"
        probability: 0.15
        impact: 2

  - id: "pay_003"
    name: "Integration testing with sandbox"
    description: "End-to-end testing against vendor sandbox environment"
    estimate:
      low: 3
      expected: 5
      high: 10
      unit: "days"
    dependencies: ["pay_002"]
    risks:
      - id: "pay_risk_004"
        name: "Sandbox environment instability"
        probability: 0.40
        impact: 3

  - id: "pay_004"
    name: "Security hardening"
    description: "Encryption, tokenization, and audit logging"
    estimate:
      low: 4
      expected: 6
      high: 10
      unit: "days"
    dependencies: ["pay_002"]
    risks:
      - id: "pay_risk_005"
        name: "Penetration test findings"
        probability: 0.25
        impact:
          type: "percentage"
          value: 30
```

In this project, each iteration might unfold differently. In one run the vendor documentation risk triggers on `pay_001`, adding 4 days. In another, the compliance review project risk fires, stretching the total duration by 15%. The Monte Carlo process captures all these possibilities and summarizes them statistically.



## Tasks Without Risks

Not every task needs risks. Many tasks have uncertainty captured sufficiently by their estimate range and uncertainty factors alone. If a task has no meaningful discrete risk events, simply omit the `risks` field or set it to an empty list:

```yaml
tasks:
  - id: "task_007"
    name: "Documentation"
    estimate:
      low: 2
      expected: 3
      high: 5
      unit: "days"
    dependencies: ["task_002", "task_003"]
    risks: []
```



## Practical Tips for Defining Risks

- **Be specific.** A risk named "something goes wrong" is not actionable. Prefer names like "Security audit findings" or "Vendor API downtime".
- **Calibrate probability honestly.** A probability of `0.50` means you expect the event to happen roughly half the time. If you are unsure, `0.20` to `0.30` is a reasonable starting range for events that are plausible but not expected.
- **Do not double-count.** If a condition is already captured by an uncertainty factor (e.g., high technical complexity), do not also add a risk for the same effect. Risks are for events; uncertainty factors are for conditions.
- **Use percentage impact for scale-dependent events.** If a risk tends to hurt larger tasks more than smaller ones, percentage-based impact is a better fit.
- **Use absolute impact for fixed-cost events.** If a risk has a known cost regardless of the task size (e.g., a mandatory 3-day wait for an external review), absolute impact is appropriate.
- **Keep risk lists manageable.** Most tasks should have zero to three risks. If a task has many risks, consider whether some of them are better captured as uncertainty factors or whether the task should be broken into smaller pieces.



## Examples

The following two examples demonstrate the same small project defined with and without uncertainty factors and risks. Comparing them illustrates the effect these mechanisms have on simulation input.

### Example 1: Project Without Uncertainty Factors or Risks

This project relies solely on the estimate ranges to model uncertainty. No uncertainty factors are specified (defaults will apply), and no risks are defined.

```yaml
project:
  name: "Internal Dashboard"
  description: "Build an internal reporting dashboard"
  start_date: "2026-06-01"
  confidence_levels: [50, 80, 90]

tasks:
  - id: "dash_001"
    name: "Data model design"
    estimate:
      low: 2
      expected: 4
      high: 7
      unit: "days"
    dependencies: []

  - id: "dash_002"
    name: "Backend API"
    estimate:
      low: 5
      expected: 8
      high: 14
      unit: "days"
    dependencies: ["dash_001"]

  - id: "dash_003"
    name: "Frontend charts"
    estimate:
      low: 4
      expected: 6
      high: 11
      unit: "days"
    dependencies: ["dash_001"]

  - id: "dash_004"
    name: "Integration and deployment"
    estimate:
      low: 2
      expected: 3
      high: 6
      unit: "days"
    dependencies: ["dash_002", "dash_003"]
```

In this project, the only source of variation across iterations is the random sampling from each task's triangular distribution. The simulation will produce a distribution of project durations shaped entirely by the estimate ranges and the dependency structure.

### Example 2: Same Project With Uncertainty Factors and Risks

The same project, enriched with [uncertainty factors](uncertainty_factors.md) and risks to capture additional real-world conditions.

```yaml
project:
  name: "Internal Dashboard"
  description: "Build an internal reporting dashboard"
  start_date: "2026-06-01"
  confidence_levels: [50, 80, 90]

project_risks:
  - id: "proj_risk_001"
    name: "Stakeholder changes reporting requirements"
    probability: 0.25
    impact:
      type: "percentage"
      value: 15
    description: "New metrics requested after development starts"

  - id: "proj_risk_002"
    name: "Data warehouse migration overlap"
    probability: 0.10
    impact:
      type: "absolute"
      value: 8
      unit: "days"
    description: "Data source temporarily unavailable during warehouse migration"

tasks:
  - id: "dash_001"
    name: "Data model design"
    estimate:
      low: 2
      expected: 4
      high: 7
      unit: "days"
    dependencies: []
    uncertainty_factors:
      team_experience: "high"
      requirements_maturity: "low"
      technical_complexity: "low"
    risks:
      - id: "dash_risk_001"
        name: "Source data schema undocumented"
        probability: 0.30
        impact: 3

  - id: "dash_002"
    name: "Backend API"
    estimate:
      low: 5
      expected: 8
      high: 14
      unit: "days"
    dependencies: ["dash_001"]
    uncertainty_factors:
      team_experience: "medium"
      requirements_maturity: "medium"
      technical_complexity: "medium"
      integration_complexity: "high"
    risks:
      - id: "dash_risk_002"
        name: "Unexpected data volume"
        probability: 0.20
        impact: 4

  - id: "dash_003"
    name: "Frontend charts"
    estimate:
      low: 4
      expected: 6
      high: 11
      unit: "days"
    dependencies: ["dash_001"]
    uncertainty_factors:
      team_experience: "low"
      technical_complexity: "medium"
    risks:
      - id: "dash_risk_003"
        name: "Chart library limitations"
        probability: 0.15
        impact: 2

  - id: "dash_004"
    name: "Integration and deployment"
    estimate:
      low: 2
      expected: 3
      high: 6
      unit: "days"
    dependencies: ["dash_002", "dash_003"]
    uncertainty_factors:
      team_experience: "medium"
      team_distribution: "distributed"
      integration_complexity: "high"
    risks:
      - id: "dash_risk_004"
        name: "Staging environment unavailable"
        probability: 0.20
        impact: 2
```

Compared to Example 1, this version will produce a wider and generally longer distribution of project durations. The uncertainty factors shift task durations systematically (for instance, the low team experience on `dash_003` multiplies that task's sampled duration by 1.30), and the risks introduce discrete jumps when they trigger. The two project-level risks add further spread to the overall distribution.



## Summary

| Concept                | What It Models                              | When It Applies         | How It Affects Duration           |
|------------------------|---------------------------------------------|-------------------------|-----------------------------------|
| **Task-level risk**    | A discrete event tied to one task           | Per task, per iteration  | Adds time to that task            |
| **Project-level risk** | A discrete event affecting the whole project| Per project, per iteration| Adds time to total project duration|

- Risks are **additive**: triggered risks add time to the duration.
- Task-level risks are evaluated **after** uncertainty factors are applied, so percentage-based task risks act on the adjusted duration.
- Project-level risks are evaluated **after** the schedule is computed, so they do not affect critical path membership.


\newpage

