# Interpreting Results

After running a simulation, `mcprojsim` produces a set of statistics, percentiles, critical path data, and optionally an HTML report with a histogram and thermometer chart. This chapter explains what those outputs mean and how to use them for practical decision-making.

---

## The output at a glance

A typical CLI run (using `examples/sample_project.yaml`) produces output like this:

```
mcprojsim, version 0.3.0
Progress: 100.0% (10000/10000)

=== Simulation Results ===
Project: Customer Portal Redesign
Hours per Day: 8.0
Mean: 578.47 hours (73 working days)
Median (P50): 571.84 hours
Std Dev: 78.27 hours
Coefficient of Variation: 0.1353
Skewness: 0.4865
Excess Kurtosis: 0.2469

Confidence Intervals:
  P25: 522.75 hours (66 working days)  (2026-02-02)
  P50: 571.84 hours (72 working days)  (2026-02-10)
  P75: 627.77 hours (79 working days)  (2026-02-19)
  P80: 642.81 hours (81 working days)  (2026-02-23)
  P85: 660.11 hours (83 working days)  (2026-02-25)
  P90: 682.94 hours (86 working days)  (2026-03-02)
  P95: 715.57 hours (90 working days)  (2026-03-06)
  P99: 790.61 hours (99 working days)  (2026-03-19)

Sensitivity Analysis (top contributors):
  task_004: +0.4322
  task_008: +0.3244
  task_002: +0.3110
  task_006: +0.2730
  task_001: +0.1760
  task_005: +0.1658
  task_007: +0.0062
  task_003: -0.0049

Schedule Slack:
  task_008: 0.00 hours (Critical)
  task_006: 0.00 hours (Critical)
  task_005: 0.00 hours (Critical)
  task_004: 0.00 hours (Critical)
  task_001: 0.00 hours (Critical)
  task_002: 0.00 hours (Critical)
  task_003: 165.16 hours (165.2h buffer)
  task_007: 355.57 hours (355.6h buffer)

Risk Impact Analysis:
  task_001: mean=3.18h, triggers=19.9%, mean_when_triggered=16.00h
  task_003: mean=5.84h, triggers=24.3%, mean_when_triggered=24.00h
  task_004: mean=11.74h, triggers=29.3%, mean_when_triggered=40.00h
  task_006: mean=11.13h, triggers=34.8%, mean_when_triggered=32.00h
  task_008: mean=4.89h, triggers=20.4%, mean_when_triggered=24.00h

Most Frequent Critical Paths:
  1. task_001 -> task_002 -> task_004 -> task_005 -> task_006 -> task_008
     (10000/10000, 100.0%)

No export formats specified. Use -f to export results to files.
```

Every number here comes from simulating your project thousands of times with different random samples. The results describe the *distribution* of outcomes, not a single prediction.

The sections below explain each part of this output in detail.

---

## Understanding percentiles

Percentiles are the most actionable part of the output. Each percentile answers the question: *"How many hours (or days) would be enough to finish the project X% of the time?"*

| Percentile | Practical meaning |
|-----------|-------------------|
| **P50** | The median — half the simulated outcomes finished faster, half slower. This is an aggressive target; you have a coin-flip chance of meeting it. |
| **P75** | Three out of four simulations finished by this point. A reasonable internal planning target for teams comfortable with some risk. |
| **P80** | Four out of five simulations finished here. Often used as the default commitment for internal stakeholders. |
| **P90** | Nine out of ten simulations finished. A common choice for external commitments and contractual deadlines. |
| **P95** | Only 1 in 20 simulations exceeded this. A conservative target suitable for high-stakes commitments where a miss is costly. |
| **P99** | Virtually worst-case. Useful for capacity planning or budget ceilings, but not a realistic daily target. |

### Choosing the right percentile

There is no universally correct percentile. The right choice depends on the cost of being late versus the cost of over-committing:

- **Low-stakes internal milestone**: P75–P80 is usually sufficient. If you slip, you adjust.
- **Customer-facing deadline**: P85–P90 gives a meaningful safety margin without excessive padding.
- **Contractual commitment with penalties**: P90–P95 is appropriate when the consequence of a miss is significant.
- **Budget ceiling or worst-case planning**: P95–P99 helps answer "what's the most this could possibly cost?"

A useful rule of thumb: commit externally at the P85–P90 level, plan internally at P50, and track the gap between them. If the gap is large, your project has high uncertainty — which is itself valuable information.

### Working days and delivery dates

Each percentile also shows working days (hours ÷ hours_per_day, rounded up) and a projected delivery date that counts forward from `start_date`, skipping weekends. These are calculated from the hours figure — they are not separate estimates.

---

## The thermometer chart

The HTML report includes a thermometer — a vertical colour-coded bar showing effort at probability levels from 50% to 99%. It provides a quick visual: green zones are highly likely to succeed, orange zones are risky.

- **Dark orange → yellow** (50%–70%): aggressive targets. You are more likely than not to miss these.
- **Yellow → light green** (75%–85%): moderate confidence. Reasonable for internal targets.
- **Green → dark green** (90%–99%): high confidence. Suitable for external commitments.

The colour thresholds are configurable via `probability_red_threshold` and `probability_green_threshold` in the project file.

---

## Mean vs. median

The **mean** (average) and **median** (P50) are often close, but they diverge when the distribution is skewed — which it almost always is in software projects, because tasks tend to overrun more than they finish early.

- When **mean > median**, the distribution has a right tail (some iterations produced long durations pulling the average up). This is normal.
- A large gap between mean and median signals high asymmetry. It suggests a few bad-case scenarios are contributing disproportionately to the average.

For planning, the **median** is generally more useful than the mean. The mean can be distorted by outliers, while the median always represents the 50th-percentile outcome.

---

## Standard deviation and coefficient of variation

The **standard deviation** measures the spread of outcomes in hours. By itself, the number is hard to interpret — 50 hours of spread means something different for a 100-hour project than for a 1000-hour one.

The **coefficient of variation** (CV) normalises the spread so that you can compare uncertainty across projects of different sizes.

### Definition

$$
\text{CV} = \frac{\sigma}{\mu}
$$

where $\sigma$ is the standard deviation and $\mu$ is the mean project duration.

### Interpretation

| CV | Interpretation |
|----|----------------|
| < 0.15 | Low uncertainty — estimates are tight and risks are well-contained |
| 0.15–0.30 | Moderate uncertainty — typical for well-scoped projects with some unknowns |
| 0.30–0.50 | High uncertainty — wide estimate ranges or significant risk exposure |
| > 0.50 | Very high uncertainty — the project timeline is essentially unpredictable at this stage |

In the sample output, `CV = 0.1353` indicates low uncertainty: the spread of outcomes is about 13.5% of the mean.

### What to watch out for

- **CV increasing across re-estimates**: If the CV grows as you refine estimates, new information is revealing wider uncertainty than originally assumed. This is healthy — it means the model is becoming more honest.
- **Very low CV (< 0.05)**: Suspiciously tight. Check whether estimate ranges are artificially narrow (e.g., `min` and `max` almost equal) or whether risks have been omitted.
- **CV > 0.50**: The schedule is so uncertain that committing to any specific date is risky. Consider breaking the project into phases and re-estimating each one.

### Practical use

A high CV is not necessarily bad — it is *honest*. It tells you that the inputs contain wide estimate ranges, high-probability risks, or both. Narrowing the CV means improving the inputs: tightening estimates, reducing risk exposure, or breaking large tasks into better-understood pieces. Use the CV to compare uncertainty across different project proposals: a project with CV 0.40 carries much more schedule risk than one with CV 0.15, regardless of their absolute durations.

---

## Skewness

Skewness measures how asymmetric the distribution of project durations is. In software projects, distributions almost always skew right: there are more ways for things to go wrong than to go better than planned.

### Definition

$$
\text{Skewness} = \frac{1}{n} \sum_{i=1}^{n} \left( \frac{x_i - \mu}{\sigma} \right)^3
$$

A positive value means the distribution has a longer right tail (late finishes are further from the median than early finishes). A negative value means the opposite. Zero means perfect symmetry.

### Interpretation

| Skewness | Meaning |
|----------|--------|
| ≈ 0 | Roughly symmetric — early and late outcomes are about equally spread around the median |
| 0.1–0.5 | Mild right skew — a slight tendency toward late outcomes, which is typical |
| 0.5–1.0 | Moderate right skew — the mean is noticeably higher than the median; a few bad scenarios are pulling the average up |
| > 1.0 | Strong right skew — significant tail risk; worst-case outcomes are much worse than typical outcomes |

In the sample output, `Skewness = 0.4865` indicates moderate right skew: some iterations hit notably longer durations than the median, but the effect is not extreme.

### What to watch out for

- **Skewness > 1.0**: The project has significant tail risk. The mean is a poor planning target — use the median (P50) instead, and pay close attention to P90/P95.
- **Negative skewness**: Unusual in project estimation. It may indicate that `max` estimates are too conservative relative to `min`, or that uncertainty factors are compressing durations at the high end.
- **Skewness combined with high CV**: When both are high, the project has both wide variance and a long tail. This is a red flag for external commitments.

### Practical use

When skewness is positive, the mean overstates a "typical" outcome. Prefer the median for internal planning. The gap between mean and median quantifies how much the tail is pulling the average: a gap of 10+ hours suggests meaningful tail risk that should be communicated to stakeholders.

---

## Excess kurtosis

Excess kurtosis describes the "tailedness" of the distribution — whether extreme outcomes (very early or very late finishes) are more or less likely than a normal distribution would predict.

### Definition

$$
\text{Excess Kurtosis} = \frac{1}{n} \sum_{i=1}^{n} \left( \frac{x_i - \mu}{\sigma} \right)^4 - 3
$$

The $-3$ subtracts the kurtosis of a normal distribution, so that a normal distribution has excess kurtosis of zero.

### Interpretation

| Excess kurtosis | Meaning |
|-----------------|--------|
| ≈ 0 | Tail behaviour similar to a normal distribution |
| > 0 (leptokurtic) | Heavier tails — extreme outcomes are more frequent than normal. Surprises (both good and bad) happen more often |
| < 0 (platykurtic) | Lighter tails — outcomes are more concentrated around the mean. Fewer surprises |

In the sample output, `Excess Kurtosis = 0.2469` is slightly positive, meaning the tails are marginally heavier than a normal distribution — a small number of iterations produced notably long (or short) durations.

### What to watch out for

- **Kurtosis > 2**: Heavy tails. The P95 and P99 values may be much higher than P90 suggests. Check the high percentiles carefully before making commitments at those levels.
- **Kurtosis < −1**: Very light tails. This may indicate that estimate ranges are too narrow or that the model lacks risks that could cause extreme outcomes.
- **Kurtosis combined with high skewness**: When both are high and positive, the distribution has a fat right tail — rare but severe overruns are plausible.

### Practical use

Excess kurtosis guides how much buffer to add between your planning target and your worst-case commitment. When kurtosis is high, the gap between P90 and P99 is larger than usual, so committing at P90 leaves more residual risk than it would for a normal-tailed distribution. Conversely, negative kurtosis means outcomes are bunched together and P90 commitments are safer than they might first appear.

---

## Sensitivity analysis

The sensitivity analysis section ranks tasks by how strongly their duration influences the total project duration. It answers the question: *"Which task's estimate uncertainty matters most to the overall schedule?"*

### Definition

Sensitivity is measured using Spearman's rank correlation coefficient ($\rho$) between each task's sampled durations and the project's total duration across all iterations:

$$
\rho = 1 - \frac{6 \sum d_i^2}{n(n^2 - 1)}
$$

where $d_i$ is the difference between the rank of the task duration and the rank of the project duration in iteration $i$, and $n$ is the number of iterations.

The sign indicates the direction of the relationship. A positive value (the norm) means that when this task takes longer, the project takes longer. The magnitude (0 to 1) indicates the strength.

### Interpretation

| Correlation | Meaning |
|-------------|--------|
| > +0.5 | Strong positive driver — this task's variance is a major contributor to project variance |
| +0.2 to +0.5 | Moderate driver — contributes meaningfully to schedule uncertainty |
| −0.1 to +0.2 | Weak or negligible — the task has little influence on overall duration |
| < −0.1 | Inverse relationship — unusual and worth investigating (possibly a non-critical task that shares resources) |

In the sample output, `task_004: +0.4322` is the strongest driver, meaning its duration variance contributes the most to the spread of project outcomes. Tasks near zero (like `task_007: +0.0062`) have essentially no influence — even large changes to their estimates would not move the project schedule.

### What to watch out for

- **Several tasks above +0.3**: Schedule uncertainty is spread across multiple tasks. Reducing variance on any single task has limited effect — you need to address several.
- **One dominant task (> +0.7)**: This task essentially controls the schedule. Focus estimation refinement and risk mitigation there first.
- **Negative correlations**: Usually means the task is on a non-critical branch. When it runs long, a different branch becomes critical, and the total project time may stay the same or even decrease (rare).

### Practical use

Use sensitivity to prioritise where to invest in better estimates. Spending a day refining the estimate for a +0.45 task reduces overall schedule uncertainty far more than refining a +0.02 task. In the HTML report, the sensitivity analysis appears as a tornado chart for visual comparison.

---

## Schedule slack

Schedule slack (also called total float) shows how much each task can be delayed without delaying the overall project. It is calculated using a backward-pass Critical Path Method (CPM) and then averaged across all Monte Carlo iterations.

### Definition

For each task, the total float is:

$$
\text{Slack} = LS - ES
$$

where $LS$ is the latest start time (computed via the backward pass from the project end) and $ES$ is the earliest start time (from the forward pass). The value reported is the mean slack across all simulation iterations.

### Interpretation

- **0.00 hours (Critical)**: The task is on the critical path in most or all iterations. Any delay to this task delays the project.
- **Positive slack (buffer)**: The task can overrun by up to this many hours without affecting the project delivery date. The larger the buffer, the less you need to worry about this task.

In the sample output, `task_003` has 165.16 hours of slack and `task_007` has 355.57 hours — these tasks could each overrun significantly without moving the project deadline. Meanwhile, six tasks show zero slack, confirming they are consistently on the critical path.

### What to watch out for

- **All tasks showing zero slack**: The project is a single serial chain with no parallelism. Any task delay equals a project delay. Consider restructuring dependencies to create parallel paths.
- **Very small slack (< 8 hours / 1 day)**: The task is *almost* critical. It appears on the critical path in some iterations. Treat it with similar urgency to zero-slack tasks.
- **Slack changing across runs**: If the same task has very different slack with different seeds, the critical path is unstable — the project has competing bottleneck paths, and which one dominates depends on which sampled durations happen to be long.

### Practical use

Slack tells you where you have scheduling flexibility. Tasks with large buffers are safe to deprioritise, start later, or assign to less experienced team members. Tasks with zero slack are where delays are most costly — prioritise them in resource allocation, assign your strongest people, and mitigate their risks first.

---

## Risk impact analysis

The risk impact analysis section shows how much each task's risks contribute to the schedule across all simulation iterations. This goes beyond listing risks in the project file — it shows what actually happened during the simulation.

### Reported metrics

For each task that has risks defined, three values are reported:

| Metric | Definition |
|--------|------------|
| **mean** | Average risk impact across all iterations (in hours), including iterations where the risk did not trigger: $\text{mean} = \frac{1}{n} \sum_{i=1}^{n} \text{impact}_i$ |
| **triggers** | Trigger rate — the fraction of iterations where at least one risk on this task fired: $\text{triggers} = \frac{\text{count}(\text{impact} > 0)}{n}$ |
| **mean_when_triggered** | Average impact in only the iterations where a risk actually fired: $\text{mean\_when\_triggered} = \frac{\sum_{i : \text{impact}_i > 0} \text{impact}_i}{\text{count}(\text{impact} > 0)}$ |

### Interpretation

In the sample output:

```
task_004: mean=11.74h, triggers=29.3%, mean_when_triggered=40.00h
```

This means: in 29.3% of the 10,000 iterations, at least one of `task_004`'s risks fired. When they did, they added an average of 40 hours. Across *all* iterations (including the 70.7% where nothing happened), the average impact was 11.74 hours.

The gap between `mean` and `mean_when_triggered` reveals whether a risk is a frequent nuisance or a rare catastrophe:

- **High trigger rate, low impact when triggered**: A frequent but manageable disruption. The overall mean is close to `mean_when_triggered`.
- **Low trigger rate, high impact when triggered**: A "black swan" event. The overall mean looks low, but when it hits, it hits hard. These deserve contingency planning.

### What to watch out for

- **High trigger rate (> 50%)**: The risk is more likely than not. Consider whether it should be modelled as part of the base estimate rather than as a risk.
- **Large `mean_when_triggered` on a critical-path task**: This combination has the highest potential to blow the schedule. If `task_004` is critical (zero slack) and adds 40 hours when its risk fires, that is a full working week added to the project almost a third of the time.
- **Tasks with no risk output**: These tasks have no risks defined. If they have high sensitivity scores, consider whether risks were overlooked.

### Practical use

Combine risk impact analysis with sensitivity and slack to decide where to act:

1. If a task has **high sensitivity + zero slack + high trigger rate** → top priority for risk mitigation.
2. If a task has **high `mean_when_triggered` but low trigger rate** → have a contingency plan ready, but don't rearrange the whole schedule for it.
3. If a task has **large slack** → its risks are mostly absorbed by the buffer. Monitor, but don't prioritise.

---

## Critical path analysis

### What is the critical path?

The critical path is the longest chain of dependent tasks that determines when the project finishes. If any task on the critical path takes longer, the whole project takes longer. Tasks *not* on the critical path have slack — they can overrun without affecting the delivery date, up to a point.

### Why Monte Carlo gives multiple critical paths

In a deterministic schedule there is one critical path. In a Monte Carlo simulation, each iteration samples different task durations, so the critical path can shift. A task that is critical in one iteration may have slack in another.

`mcprojsim` tracks this across all iterations and reports:

1. **Criticality index** per task — the fraction of iterations where that task appeared on a critical path. A criticality of 0.85 means the task was critical in 85% of simulations.

2. **Most frequent critical path sequences** — the full path (e.g., *A → C → E*) and how often it occurred.

### How to use criticality

- **Criticality > 0.7**: This task is almost always on the critical path. It is a bottleneck. Focus risk mitigation, staffing, and management attention here.
- **Criticality 0.3–0.7**: Sometimes critical, sometimes not. Worth monitoring, but not the primary bottleneck.
- **Criticality < 0.3**: Rarely critical. This task has significant slack in most scenarios.

If multiple tasks share high criticality, the project has several competing bottleneck paths. That actually *reduces* schedule risk compared to a single dominant path, because no one task controls the outcome.

---

## Combining the analyses

The real power of these metrics comes from reading them together. Here is a decision framework:

| Situation | Action |
|-----------|--------|
| High sensitivity + zero slack + high risk trigger rate | **Top priority.** This task drives the schedule, sits on the critical path, and frequently gets hit by risk events. Invest in mitigation, tighter estimates, or splitting the task. |
| High sensitivity + zero slack + low risk trigger rate | **Monitor closely.** The task drives the schedule through estimate variance, not risk. Focus on refining the estimate range. |
| High sensitivity + large slack | **Unusual.** The task's duration varies a lot but it isn't critical. Investigate whether dependencies are correctly modelled. |
| Low sensitivity + zero slack | The task is on the critical path but doesn't contribute much variance. It is a stable bottleneck — duration is predictable but the path still runs through it. |
| Low sensitivity + large slack | **Low priority.** This task has both predictable duration and scheduling flexibility. |

---

## Reducing volatility

If the spread between P50 and P90 is uncomfortably wide, consider:

- **Splitting large tasks**: A single task with `min: 5, max: 40` contributes more variance than two tasks with `min: 3, max: 20` each, especially when they are on different dependency paths.
- **Tightening estimate ranges**: If subject-matter experts can narrow the gap between `min` and `max` after investigation, uncertainty drops directly.
- **Mitigating high-impact risks**: Removing or reducing the probability of risks on critical tasks has the largest effect.
- **Adding parallel paths**: Restructuring dependencies so that fewer tasks are in a single sequential chain reduces the chance of cascading delays.
- **Addressing high-sensitivity tasks first**: Use the sensitivity analysis to focus effort where it matters most.

---

## Limitations of the simulation

Monte Carlo simulation is a powerful tool, but it has boundaries. Understanding them prevents over-reliance on the numbers.

### What the simulation does well

- Quantifies the *range* of plausible outcomes given uncertain inputs
- Identifies which tasks and risks contribute most to schedule uncertainty
- Provides probabilistic confidence levels instead of false-precision single-number estimates
- Handles complex dependency structures and mixed estimation methods

### What the simulation does not do

- **It does not improve bad inputs**. If your estimate ranges are systematically optimistic — if the real `max` is higher than what you entered — the simulation will be optimistic too. The output is only as good as the input.

- **It assumes task independence**. Each task's duration is sampled independently. In reality, if one task overruns because the technology is harder than expected, related tasks may also overrun. The simulation does not model these correlations.

- **It ignores resource constraints**. The scheduler respects task dependencies but does not limit parallelism by resource availability. If two independent tasks need the same developer, they run in parallel in the simulation but would be sequential in practice. This means the simulation may underestimate actual duration for resource-constrained projects.

- **It does not model learning or momentum**. Teams often speed up as they gain context, or slow down from fatigue. The simulation treats each task in isolation.

- **Risks are binary**. Each risk either fires or doesn't, at a fixed probability. In reality, risk severity exists on a spectrum and probabilities shift as the project evolves.

### Calibration matters

The most useful thing you can do over time is *calibrate*: compare the simulation's P50 and P90 with actual outcomes, and adjust your estimation habits accordingly. If your P90 is consistently exceeded, your `max` values are too low. If P50 is consistently beaten, your `min` values may be too conservative — or your uncertainty factors are inflating estimates.

---

## Quick reference

| Output | What it tells you | Primary use |
|--------|-------------------|-------------|
| P50 (median) | The 50/50 point | Internal planning baseline |
| P80–P90 | High-confidence estimates | External commitments |
| Std dev / CV | How spread out the outcomes are | Gauging overall uncertainty |
| Skewness | How asymmetric the distribution is (tail risk) | Deciding between mean and median for planning |
| Excess kurtosis | Whether extreme outcomes are more/less likely than normal | Sizing the buffer between P90 and P99 |
| Sensitivity | Which tasks drive overall schedule variance | Prioritising estimation and risk-mitigation effort |
| Schedule slack | How much buffer each task has before delaying the project | Resource allocation and task prioritisation |
| Risk impact | How often and how much each task's risks fire | Identifying high-impact risk events to mitigate |
| Criticality index | How often a task is on the critical path | Focusing management attention |
| Critical path sequences | Which chains of tasks dominate | Dependency restructuring |
| Thermometer | Visual probability-to-effort mapping | Stakeholder communication |
| Delivery dates | Calendar dates at each percentile | Scheduling and milestone setting |
