Version: 0.1.0

Date: 2026-04-09

Status: Design and Research Proposal

# Monetary Cost Estimation

## Executive Summary

`mcprojsim` currently produces two core distributions per simulation run: **elapsed project duration** and **total effort** (person-hours). Both are sampled stochastically across Monte Carlo iterations, giving users percentile-based delivery forecasts. However, there is no mechanism to translate effort into **monetary cost**, which is one of the most common project-planning questions: *how much will this cost, and what is the range of likely spend?*

This document proposes adding optional monetary cost estimation to `mcprojsim` with these design goals:

1. **Works without resources.** Projects that define no explicit resources should still get cost estimates by applying a project-level default hourly rate to sampled effort.
2. **Works with resources.** Projects that define named resources should support per-resource hourly rates, so cost reflects the actual mix of people assigned.
3. **Supports fixed costs.** Tasks and risks should optionally carry fixed monetary impacts (e.g., licence fees, infrastructure costs) that are independent of effort.
4. **Produces cost distributions.** Cost should be a first-class simulated quantity with the same statistical treatment as duration: mean, percentiles, sensitivity, and histogram.
5. **Remains fully optional.** Projects that do not specify any cost inputs should see zero change in behavior or output.

The recommended approach is to compute cost **per iteration inside the existing simulation loop** by multiplying sampled task durations by the applicable hourly rate, adding fixed costs and risk-triggered cost impacts, and aggregating the results into a `CostResults` surface that mirrors the existing duration statistics.

## Problem Statement

Project stakeholders routinely ask three questions:

1. **When will it be done?** — answered today by duration percentiles.
2. **How much effort will it take?** — answered today by effort percentiles.
3. **How much will it cost?** — not answered today.

Cost estimation is inherently uncertain for the same reasons duration is: task effort varies, risks trigger unpredictably, and resource mix shifts. A Monte Carlo cost model should therefore produce a **cost distribution**, not a single number, and it should correlate naturally with the duration distribution because both derive from the same sampled task durations.

## Current State in mcprojsim

Relevant existing capabilities:

1. **Per-iteration task durations** are already sampled and stored (`task_durations_all`), giving effort in hours per task per iteration.
2. **Effort durations** are already aggregated per iteration as the sum of all task durations (`effort_durations` array in `SimulationResults`).
3. **Resource assignment** is tracked during constrained scheduling — the scheduler knows which resource works on which task.
4. **Risk impacts** are evaluated per iteration and stored (`risk_impacts`, `project_risk_impacts`), currently measured in hours.
5. **Staffing analysis** already models team-size effects and communication overhead, producing total effort hours — a natural input for cost conversion.
6. **Config defaults** provide a central place for default values that can be overridden per project.

What is missing:

- No hourly rate on resources or projects.
- No fixed-cost field on tasks or risks.
- No cost-specific risk impact type.
- No cost aggregation in the simulation loop.
- No cost statistics in results or exports.

## Key Terms Used in This Proposal

- **Hourly rate**: monetary cost per person-hour of effort, the primary unit linking effort to cost.
- **Blended rate**: a single default hourly rate applied when individual resource rates are not specified.
- **Fixed cost**: a monetary amount attached to a task or risk that is independent of effort duration (e.g., a licence fee, a hardware purchase).
- **Cost impact**: a risk impact expressed in monetary units, triggered probabilistically alongside (or instead of) time impacts.
- **Cost distribution**: the per-iteration array of total project cost, analogous to `durations` and `effort_durations`.
- **Overhead rate**: a percentage markup applied on top of labor cost to account for management, infrastructure, tooling, and other indirect costs.

## Compared Approaches

| Approach | How it works | Strengths | Weaknesses | Verdict |
|---|---|---|---|---|
| **A. Post-hoc multiplication** | Multiply `effort_durations` by a single rate after simulation | Zero engine changes; trivial to implement | Cannot model per-resource rates, fixed costs, or cost-specific risks; loses per-task cost breakdown | Insufficient as a standalone solution |
| **B. Per-iteration cost accumulation in the engine** | Compute cost per task per iteration inside the simulation loop using task duration × applicable rate, plus fixed costs and risk cost impacts | Full cost distribution with correct correlation to duration; supports per-resource rates; enables cost sensitivity analysis | Requires model, engine, and exporter changes | **Recommended** |
| **C. Separate cost simulation pass** | Run a second Monte Carlo pass that samples cost parameters independently | Could model cost uncertainty separately from effort uncertainty | Breaks the natural correlation between effort and cost; doubles runtime; conceptually wrong (cost is derived from effort, not independent) | Rejected |
| **D. Deterministic cost model** | Compute cost from mean effort × rate, no distribution | Simple | Defeats the purpose of Monte Carlo; gives false precision | Rejected |

**Recommendation: Approach B** — per-iteration cost accumulation. This produces statistically correct cost distributions that are naturally correlated with duration, supports the full range of cost inputs (rates, fixed costs, risk impacts), and integrates cleanly with existing analysis and export infrastructure.

## Recommended Design

### 1. Model Changes

#### 1.1 Project-Level Cost Defaults

Add optional cost fields to `ProjectMetadata`:

```yaml
project:
  name: "My Project"
  start_date: "2026-01-15"
  default_hourly_rate: 150.00    # blended rate when no resource rates are given
  overhead_rate: 0.20            # 20% markup on labor cost (optional, default 0)
  currency: "USD"                # display label only, no conversion logic
```

All three fields are optional. If `default_hourly_rate` is not set and no resource rates exist, cost estimation is skipped entirely — existing behavior is preserved.

#### 1.2 Resource-Level Rates

Add an optional `hourly_rate` field to `ResourceSpec`:

```yaml
resources:
  - name: alice
    experience_level: 3
    availability: 1.0
    hourly_rate: 180.00

  - name: bob
    experience_level: 2
    availability: 0.8
    hourly_rate: 120.00
```

When a resource has an `hourly_rate`, that rate is used for any task the resource is assigned to. When a resource does not have an `hourly_rate`, the project-level `default_hourly_rate` is used as a fallback.

#### 1.3 Task-Level Fixed Costs

Add an optional `fixed_cost` field to `Task`:

```yaml
tasks:
  - id: infra-setup
    name: "Provision Cloud Infrastructure"
    estimate:
      expected: 8
      low: 4
      high: 16
      unit: hours
    fixed_cost: 5000.00   # one-time cost regardless of effort
```

Fixed costs are added once per iteration when the task is scheduled, independent of its sampled duration.

#### 1.4 Risk Cost Impacts

Extend `RiskImpact` to support a monetary impact type:

```yaml
risks:
  - id: vendor-delay
    name: "Third-Party Vendor Delay"
    probability: 0.25
    impact:
      type: absolute
      value: 2
      unit: days
    cost_impact: 15000.00   # monetary impact when risk triggers
```

A risk can have both a time `impact` and a `cost_impact`. They trigger together (same probability roll). This avoids complicating the existing impact model while supporting the common case where a risk has both schedule and budget consequences.

### 2. Config Changes

Add a `cost` section to the config structure with sensible defaults:

```yaml
cost:
  default_hourly_rate: null        # no default — cost disabled unless set
  overhead_rate: 0.0
  currency: "USD"
  include_in_output: true          # when cost data exists, include in reports
```

Project-level values override config-level values, following the existing merge pattern.

### 3. Simulation Engine Changes

#### 3.1 Per-Iteration Cost Computation

Inside the existing iteration loop, after task durations are sampled and scheduled:

```
for each iteration:
    total_cost = 0
    for each task:
        # Labor cost
        rate = resource_rate(task) or project.default_hourly_rate
        labor_cost = task_duration_hours[task] * rate

        # Fixed cost
        labor_cost += task.fixed_cost (if any)

        task_costs[task][iteration] = labor_cost
        total_cost += labor_cost

    # Risk cost impacts (project-level risks)
    for each triggered project_risk:
        total_cost += risk.cost_impact (if any)

    # Overhead
    labor_total = sum of all task labor costs
    total_cost += labor_total * project.overhead_rate

    cost_durations[iteration] = total_cost
```

**Rate resolution for resource-constrained mode:**

When the scheduler assigns specific resources to tasks, use the assigned resource's `hourly_rate`. If a task has multiple assignees in an iteration, the cost is the sum of each assignee's rate × their contributed hours (the scheduler already tracks this split internally via resource allocation).

**Rate resolution for dependency-only mode (no resources):**

Use `project.default_hourly_rate` for all tasks. If the project defines a `team_size`, the effort is already parallelized in the duration model; cost is based on total effort hours (sum of individual task durations), not elapsed duration, so parallelism does not double-count.

#### 3.2 Risk Cost Evaluation

Extend `RiskEvaluator` to return both the time impact (existing) and the cost impact (new) from a single probability roll per risk per iteration. This preserves the correlation between time overruns and cost overruns.

### 4. Results Model Changes

Add cost arrays to `SimulationResults`:

```python
# Cost tracking (None when cost estimation is not active)
cost_durations: Optional[np.ndarray] = None      # per-iteration total project cost
task_costs: Optional[Dict[str, np.ndarray]] = None  # per-task cost arrays
cost_percentiles: Optional[Dict[int, float]] = None  # P10, P25, P50, P75, P90
cost_mean: Optional[float] = None
cost_std_dev: Optional[float] = None
cost_sensitivity: Optional[Dict[str, float]] = None  # Spearman: task cost vs project cost
```

All fields are `Optional` and default to `None`, preserving backward compatibility. Cost statistics are only populated when at least one cost input is present in the project.

### 5. Analysis Changes

#### 5.1 Cost Statistics

Extend `StatisticalAnalyzer` (or add a thin `CostAnalyzer`) to compute mean, median, standard deviation, skewness, kurtosis, and percentiles over the `cost_durations` array — same treatment as duration statistics.

#### 5.2 Cost Sensitivity

Run Spearman rank correlation between per-task cost arrays and total project cost, producing a cost tornado chart. This tells users which tasks are the biggest cost drivers, which may differ from the biggest schedule drivers (e.g., a short task done by an expensive contractor).

#### 5.3 Cost-Duration Correlation

Report the Pearson correlation between `cost_durations` and `durations`. In most projects this will be very high (>0.9), but it can diverge when resource rates vary significantly or when fixed costs dominate.

### 6. Export Changes

#### 6.1 JSON Exporter

Add a `cost` section to the output when cost data is present:

```json
{
  "cost": {
    "currency": "USD",
    "mean": 245000,
    "std_dev": 38000,
    "percentiles": {
      "10": 198000,
      "25": 220000,
      "50": 242000,
      "75": 268000,
      "90": 298000
    },
    "overhead_rate": 0.20,
    "task_costs": {
      "task-1": { "mean": 45000, "p50": 43000, "p90": 62000 },
      "task-2": { "mean": 120000, "p50": 115000, "p90": 155000 }
    },
    "sensitivity": {
      "task-2": 0.82,
      "task-1": 0.45
    }
  }
}
```

#### 6.2 CSV Exporter

Add `cost` column to the per-iteration output, and a `task_cost_mean` / `task_cost_p90` column set in the per-task summary.

#### 6.3 HTML Exporter

- Add a **Cost Summary** card alongside the existing Duration Summary, showing cost mean/P50/P80/P90 with the currency label.
- Add a **Cost Histogram** showing the cost distribution.
- Add a **Cost Tornado Chart** for cost sensitivity (which tasks drive cost variance).
- In the existing task table, add a **Mean Cost** column when cost data is present.

### 7. CLI and MCP Changes

No new commands are needed. The existing `simulate` command and MCP `simulate_project` / `simulate_project_yaml` tools automatically pick up cost data from the project definition and include cost results in output.

The `generate` command and MCP `generate_project_file` tool should accept cost-related natural-language inputs (e.g., "Alice costs $180/hour", "infrastructure fixed cost $5000") and emit the corresponding YAML fields.

### 8. Parser Changes

#### 8.1 YAML Parser

Parse the new optional fields: `default_hourly_rate`, `overhead_rate`, `currency` on project metadata; `hourly_rate` on resources; `fixed_cost` on tasks; `cost_impact` on risks. Validation errors should use the existing location-aware error reporting.

#### 8.2 NL Parser

Recognize cost-related patterns in natural-language input:

- "hourly rate: $150" or "rate: 150/hour" → `default_hourly_rate`
- "Alice costs $180/hour" → resource `hourly_rate`
- "fixed cost: $5000" or "one-time cost $5000" → task `fixed_cost`
- "overhead: 20%" → `overhead_rate`

### 9. Sprint Planning Integration

For sprint-based planning mode, cost estimation follows the same principle: each sprint's cost is the sum of task costs for tasks completed (or partially completed) in that sprint. The sprint results model would gain optional `cost_per_sprint` and `cumulative_cost_percentiles` arrays, enabling burn-up style cost projections alongside work-item burn-up.

This is a natural follow-on but not required for the initial implementation.

## Design Decisions and Rationale

### Why effort-based costing (not duration-based)?

Cost should be proportional to **effort** (person-hours worked), not **elapsed duration** (calendar time). If two developers work 40 hours each over a 1-week elapsed period, the cost is 80 hours × rate, not 40 hours × rate. The existing `effort_durations` array already captures this distinction; cost extends it.

### Why a single probability roll for time and cost risk impacts?

Risks that cause schedule delays usually also cause cost increases. Using a single random draw per risk per iteration preserves this correlation. A risk that triggers in iteration #42 adds both its time impact and its cost impact in that same iteration. This produces realistic joint (duration, cost) distributions.

### Why overhead as a percentage rather than a fixed amount?

Overhead costs (management time, office space, tooling) typically scale with project size and effort. A percentage markup is the simplest model that captures this scaling. Projects with known fixed overhead can model it as a task with `fixed_cost` and zero effort instead.

### Why Optional[...] = None rather than a separate CostResults class?

Keeping cost fields on `SimulationResults` (as optional) avoids a parallel results hierarchy and keeps exporters simple — they check `if results.cost_durations is not None` and include the section. This matches how `effort_durations` and scheduling diagnostics are already handled.

## Worked Example

### Project Without Resources

```yaml
project:
  name: "API Rewrite"
  start_date: "2026-05-01"
  default_hourly_rate: 150
  overhead_rate: 0.15
  currency: "EUR"

tasks:
  - id: design
    name: "API Design"
    estimate: { low: 20, expected: 40, high: 80, unit: hours }

  - id: implement
    name: "Implementation"
    estimate: { low: 80, expected: 160, high: 300, unit: hours }
    dependencies: [design]
    fixed_cost: 2000   # cloud sandbox environment

  - id: testing
    name: "Integration Testing"
    estimate: { low: 30, expected: 60, high: 120, unit: hours }
    dependencies: [implement]
    risks:
      - id: flaky-deps
        name: "Flaky External Dependencies"
        probability: 0.3
        impact: { type: absolute, value: 20, unit: hours }
        cost_impact: 3000   # emergency vendor support
```

**Per iteration (example):**

| Task | Sampled Hours | Rate | Labor Cost | Fixed Cost | Risk Cost | Task Total |
|------|--------------|------|------------|------------|-----------|------------|
| design | 45 | €150 | €6,750 | — | — | €6,750 |
| implement | 180 | €150 | €27,000 | €2,000 | — | €29,000 |
| testing | 70 | €150 | €10,500 | — | €3,000 (triggered) | €13,500 |
| **Subtotal** | | | **€44,250** | **€2,000** | **€3,000** | **€49,250** |
| **Overhead (15%)** | | | | | | **€6,637** |
| **Iteration Total** | | | | | | **€55,887** |

Over 10,000 iterations this produces a cost distribution, e.g.:

- P50: €52,000
- P80: €68,000
- P90: €78,000

### Project With Resources

```yaml
project:
  name: "Mobile App"
  start_date: "2026-06-01"
  overhead_rate: 0.10
  currency: "USD"

resources:
  - name: alice
    experience_level: 3
    hourly_rate: 200
  - name: bob
    experience_level: 2
    hourly_rate: 130
  - name: carol
    experience_level: 1
    hourly_rate: 90

tasks:
  - id: design
    name: "UX Design"
    estimate: { low: 30, expected: 50, high: 90, unit: hours }
    resources: [alice]

  - id: backend
    name: "Backend Development"
    estimate: { low: 100, expected: 200, high: 400, unit: hours }
    dependencies: [design]
    resources: [alice, bob]
    max_resources: 2
```

In each iteration, the scheduler assigns alice and bob to `backend` and tracks how many hours each contributes. If alice works 90 hours and bob works 110 hours, the labor cost for that iteration is (90 × $200) + (110 × $130) = $32,300.

## Implementation Considerations

### Phased Rollout

**Phase 1 — Core cost model:**
- Model fields (`default_hourly_rate`, `hourly_rate`, `fixed_cost`, `cost_impact`, `overhead_rate`, `currency`)
- Engine cost accumulation per iteration
- Cost statistics in `SimulationResults`
- JSON and CSV export of cost data
- YAML parser support for new fields
- NL parser support for cost patterns

**Phase 2 — Analysis and visualization:**
- Cost sensitivity analysis (tornado chart)
- Cost-duration correlation reporting
- HTML exporter cost summary, histogram, and tornado chart
- Cost breakdown by task in HTML report

**Phase 3 — Budget confidence analysis:**
- `probability_within_budget(target_budget)` method on `SimulationResults`
- `budget_confidence_interval` with normal-approximation CI (Wilson fallback for extremes)
- `budget_for_confidence(p)` quantile lookup
- `joint_probability(target_hours, target_budget)` for joint duration-cost analysis
- `--target-budget` CLI option and MCP parameter
- JSON `budget_analysis` section in export
- HTML budget confidence card, CDF chart, and joint scatter plot

**Phase 4 — Advanced features:**
- Sprint planning cost integration (cost burn-up curves)
- Time-varying rates (e.g., contractor rate changes after month 3)
- Cost risk register (risks with only cost impact, no time impact)

### Backward Compatibility

All cost fields are optional with `None` or `0` defaults. Existing projects, configs, CLI commands, and MCP tools continue to work unchanged. Cost sections appear in output only when cost data is present.

### Testing Strategy

- **Unit tests**: Model validation for cost fields (valid rates, non-negative fixed costs, currency string).
- **Engine tests**: Verify per-iteration cost computation matches manual calculation for a small project with known seed.
- **Integration tests**: End-to-end simulation with cost inputs, verify cost percentiles in JSON output.
- **Regression tests**: Existing test suite must pass unchanged — no cost output when no cost inputs.

### Risks

| Risk | Mitigation |
|------|------------|
| Cost fields clutter the model for users who don't need them | All optional; not shown in output when absent |
| Per-resource rate resolution adds complexity to dependency-only mode | In dependency-only mode, always use `default_hourly_rate`; resource rates only apply in resource-constrained mode where assignment is tracked |
| Overhead model is too simplistic for some organizations | Phase 3 can add per-category overhead; percentage markup covers the common case |

## Budget Confidence Analysis — Detailed Design

### Motivation

Duration-based planning already answers "what is the probability we finish by date *D*?" via `probability_of_completion(target_hours)`. The budget analogue asks: **given a budget of *B* monetary units, what is the probability the project's total cost stays at or below *B*?**

This is the single most actionable cost metric for stakeholders. It turns a cost distribution into a decision tool: *"There is a 72% chance we stay within the €500k budget"* or *"To reach 90% confidence, the budget needs to be €620k."*

### Mathematical Foundation

#### The Empirical CDF Estimator

The cost distribution is produced by the Monte Carlo simulation as an array of *N* i.i.d. cost samples:

$$C_1, C_2, \ldots, C_N$$

where each $C_i$ is the total project cost computed in iteration $i$. The **empirical cumulative distribution function** (ECDF) is:

$$\hat{F}_N(b) = \frac{1}{N} \sum_{i=1}^{N} \mathbf{1}(C_i \le b)$$

where $\mathbf{1}(\cdot)$ is the indicator function. This is the natural non-parametric estimator of the true CDF $F(b) = P(C \le b)$.

For a given budget target *B*, the **probability of staying within budget** is:

$$P(\text{within budget}) = \hat{F}_N(B) = \frac{|\{i : C_i \le B\}|}{N}$$

This is identical in form to the existing `probability_of_completion`:

```python
# Existing duration method
def probability_of_completion(self, target_hours: float) -> float:
    return float(np.mean(self.durations <= target_hours))

# Analogous cost method
def probability_within_budget(self, target_budget: float) -> float:
    return float(np.mean(self.cost_durations <= target_budget))
```

#### Confidence Interval on the Probability Estimate

The ECDF estimator $\hat{F}_N(b)$ is itself a random variable (it depends on the Monte Carlo sample). Its sampling uncertainty is characterized by the **Dvoretzky–Kiefer–Wolfowitz (DKW) inequality**, which gives a distribution-free confidence band:

$$P\!\left(\sup_b \left|\hat{F}_N(b) - F(b)\right| > \varepsilon\right) \le 2e^{-2N\varepsilon^2}$$

For a pointwise $(1-\alpha)$ confidence interval at a specific budget *B*, the normal approximation to the binomial proportion gives:

$$\hat{p} \pm z_{\alpha/2} \sqrt{\frac{\hat{p}(1-\hat{p})}{N}}$$

where $\hat{p} = \hat{F}_N(B)$ and $z_{\alpha/2}$ is the standard normal quantile.

| *N* (iterations) | Max half-width at $\hat{p}=0.5$, 95% CI | Interpretation |
|---|---|---|
| 1,000 | ±3.1% | Rough screening |
| 10,000 | ±1.0% | Standard precision (mcprojsim default) |
| 100,000 | ±0.31% | High precision |

At the default 10,000 iterations, the budget probability estimate is accurate to approximately ±1 percentage point at 95% confidence — adequate for project decision-making.

#### The Inverse Problem: Budget Required for Target Confidence

The complementary question is: *"What budget do I need to reach *p*% confidence?"* This is the **quantile function** (inverse CDF):

$$B_p = \hat{F}_N^{-1}(p) = \inf\{b : \hat{F}_N(b) \ge p\}$$

In practice, this is computed as the *p*-th percentile of the cost sample array, which `numpy.percentile` already provides. This is the same computation used for duration percentiles.

For example, "the budget required for 80% confidence" is `np.percentile(cost_durations, 80)`.

#### Joint Duration-Cost Confidence Region (Optional Extension)

Stakeholders sometimes need to answer: *"What is the probability we finish by date D **and** stay within budget B?"* This is the joint probability:

$$P(T \le D \text{ and } C \le B) = \frac{1}{N} \sum_{i=1}^{N} \mathbf{1}(T_i \le D) \cdot \mathbf{1}(C_i \le B)$$

where $T_i$ and $C_i$ are the duration and cost from the same iteration *i*. Because both are computed from the same sampled task durations, their correlation is naturally preserved — this is a key advantage of per-iteration cost accumulation (Approach B from the main design).

Note that the joint probability is **not** the product of the marginal probabilities unless duration and cost are independent (which they are not):

$$P(T \le D \text{ and } C \le B) \ne P(T \le D) \cdot P(C \le B)$$

The per-iteration pairing is essential for correct joint estimation.

### API Design

#### Model: `SimulationResults` Methods

```python
def probability_within_budget(self, target_budget: float) -> float:
    """Calculate the probability of total project cost staying within budget.

    Args:
        target_budget: Budget threshold in project currency units.

    Returns:
        Probability (0.0 to 1.0) of staying within the target budget.

    Raises:
        ValueError: If cost estimation is not active (cost_durations is None).
    """
    if self.cost_durations is None:
        raise ValueError(
            "Cost estimation is not active. "
            "Set default_hourly_rate or resource hourly_rate to enable cost tracking."
        )
    return float(np.mean(self.cost_durations <= target_budget))

def budget_confidence_interval(
    self,
    target_budget: float,
    confidence_level: float = 0.95,
) -> tuple[float, float, float]:
    """Return point estimate and confidence interval for budget probability.

    Uses the normal approximation to the binomial proportion.

    Args:
        target_budget: Budget threshold in project currency units.
        confidence_level: Confidence level for the interval (default 0.95).

    Returns:
        Tuple of (point_estimate, lower_bound, upper_bound) where all
        values are probabilities in [0.0, 1.0].
    """
    if self.cost_durations is None:
        raise ValueError("Cost estimation is not active.")
    p_hat = float(np.mean(self.cost_durations <= target_budget))
    n = len(self.cost_durations)
    z = float(scipy.stats.norm.ppf((1 + confidence_level) / 2))
    half_width = z * math.sqrt(p_hat * (1 - p_hat) / n)
    return (p_hat, max(0.0, p_hat - half_width), min(1.0, p_hat + half_width))
```

```python
def budget_for_confidence(self, confidence: float) -> float:
    """Return the minimum budget required to reach a target confidence level.

    This is the inverse CDF (quantile function) of the cost distribution.

    Args:
        confidence: Desired probability of staying within budget (0.0 to 1.0).

    Returns:
        Budget amount in project currency units.
    """
    if self.cost_durations is None:
        raise ValueError("Cost estimation is not active.")
    return float(np.percentile(self.cost_durations, confidence * 100))

def joint_probability(
    self, target_hours: float, target_budget: float
) -> float:
    """Probability of finishing by target_hours AND staying within budget.

    Args:
        target_hours: Duration threshold in hours.
        target_budget: Budget threshold in currency units.

    Returns:
        Joint probability (0.0 to 1.0).
    """
    if self.cost_durations is None:
        raise ValueError("Cost estimation is not active.")
    return float(
        np.mean(
            (self.durations <= target_hours)
            & (self.cost_durations <= target_budget)
        )
    )
```

#### CLI Integration

Extend the existing `--target-date` pattern with a `--target-budget` option on the `simulate` command:

```
mcprojsim simulate project.yaml --target-budget 500000
```

Output:

```
Probability of staying within budget (€500,000): 72.3% (95% CI: 71.4%–73.2%)
Budget required for 80% confidence: €548,200
Budget required for 90% confidence: €621,400
```

When both `--target-date` and `--target-budget` are provided, also report the joint probability:

```
Probability of completing by 2026-09-01 AND staying within €500,000: 65.1%
```

#### MCP Integration

Add an optional `target_budget` parameter to the `simulate_project` and `simulate_project_yaml` MCP tools. When provided, the results summary includes the budget probability, confidence interval, and the budgets required for P50/P80/P90 confidence levels.

#### JSON Export

When a `target_budget` is set, add a `budget_analysis` section to the JSON output:

```json
{
  "budget_analysis": {
    "target_budget": 500000,
    "currency": "EUR",
    "probability_within_budget": 0.723,
    "confidence_interval_95": [0.714, 0.732],
    "budget_for_p50": 462000,
    "budget_for_p80": 548200,
    "budget_for_p90": 621400,
    "joint_analysis": {
      "target_hours": 960,
      "target_budget": 500000,
      "joint_probability": 0.651,
      "marginal_duration_probability": 0.81,
      "marginal_budget_probability": 0.723
    }
  }
}
```

The `joint_analysis` section is only present when both a target date/hours and target budget are specified.

#### HTML Export

Add a **Budget Confidence** card to the HTML report:

1. **Budget probability gauge**: A visual indicator showing the probability of staying within the target budget (similar to a speedometer or progress bar with color zones: green >80%, amber 60–80%, red <60%).
2. **Budget percentile table**: Rows for P50, P80, P90, P95 showing the budget amount at each confidence level.
3. **Cost CDF chart**: An S-curve plotting budget amount (x-axis) against cumulative probability (y-axis), with the target budget marked as a vertical line and the corresponding probability marked as a horizontal line. This gives stakeholders an intuitive visual of the full cost risk profile.
4. **Joint confidence scatter** (optional): A 2D scatter or contour plot of (duration, cost) pairs from the simulation, with the target budget and target date drawn as threshold lines, and the four quadrants labeled (on-time & on-budget, on-time & over-budget, late & on-budget, late & over-budget) with their respective probabilities.

### Worked Example

Consider the "API Rewrite" project from the earlier example, with 10,000 iterations producing a cost distribution. A stakeholder asks: *"We have a €500k budget — will we make it?"*

**Step 1 — Point estimate:**

$$P(C \le 500{,}000) = \frac{|\{i : C_i \le 500{,}000\}|}{10{,}000} = \frac{7{,}230}{10{,}000} = 0.723$$

*"72.3% probability of staying within the €500k budget."*

**Step 2 — Confidence interval (95%):**

$$\hat{p} = 0.723,\quad z_{0.025} = 1.96,\quad \text{half-width} = 1.96 \sqrt{\frac{0.723 \times 0.277}{10{,}000}} = 0.0088$$

$$CI = [0.714,\ 0.732]$$

*"We are 95% confident the true probability is between 71.4% and 73.2%."*

**Step 3 — Budget for target confidence:**

$$B_{0.80} = \hat{F}^{-1}(0.80) = \text{np.percentile}(\mathbf{C}, 80) = 548{,}200$$

$$B_{0.90} = \hat{F}^{-1}(0.90) = \text{np.percentile}(\mathbf{C}, 90) = 621{,}400$$

*"To reach 80% confidence, budget €548k. To reach 90% confidence, budget €621k."*

**Step 4 — Joint analysis (if target date September 1, 2026 is also set):**

$$P(T \le 960 \text{ and } C \le 500{,}000) = \frac{|\{i : T_i \le 960 \text{ and } C_i \le 500{,}000\}|}{10{,}000} = 0.651$$

*"65.1% probability of finishing on time AND within budget."*

Note: the marginal probabilities are $P(T \le 960) = 0.81$ and $P(C \le 500{,}000) = 0.723$, whose product is $0.586$ — less than the joint $0.651$, because duration and cost are positively correlated (iterations where tasks take longer also cost more, so the "bad" outcomes tend to cluster together, leaving more probability mass in the "both good" quadrant than independence would predict).

### Implementation Considerations

**Computational cost:** Zero additional simulation iterations are required. Budget analysis is a pure post-processing step over the existing `cost_durations` array. The ECDF lookup, percentile computation, and confidence interval are all O(N) or O(N log N) operations on the already-stored array.

**Numerical edge cases:**
- When $\hat{p} = 0$ or $\hat{p} = 1$, the normal approximation confidence interval degenerates. Use the Wilson score interval or Clopper-Pearson exact interval as a fallback when $\hat{p} \cdot N < 5$ or $(1-\hat{p}) \cdot N < 5$.
- When `cost_durations` is `None`, all budget methods raise `ValueError` with a message guiding the user to enable cost estimation.

**Interpolation for quantiles:** `numpy.percentile` uses linear interpolation between order statistics by default. This is consistent with how duration percentiles are already computed in mcprojsim and is appropriate for the sample sizes used (≥1,000 iterations).

**Currency formatting:** Budget amounts in CLI and HTML output should be formatted with the project's `currency` label and locale-appropriate thousand separators. The currency field is display-only — no exchange-rate logic.

## Future Work

- **Earned value metrics**: Planned Value, Earned Value, and Cost Performance Index computed from sprint-level cost data.
- **Multi-currency support**: Resources in different currencies with exchange-rate conversion.
- **Rate uncertainty**: Model hourly rates as distributions rather than point values (e.g., contractor rate negotiation range).
- **Cost breakdown structure**: Hierarchical cost categories (labor, infrastructure, licensing, overhead) with separate distributions.
- **Budget-at-risk (BaR)**: The monetary amount at risk at a given confidence level, analogous to Value-at-Risk in finance: $\text{BaR}_\alpha = \hat{F}^{-1}(\alpha) - \hat{F}^{-1}(0.50)$, representing the additional contingency reserve above the median cost needed to achieve $\alpha$-level confidence.
