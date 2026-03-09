# Interpreting Results

After running a simulation, `mcprojsim` produces a set of statistics, percentiles, critical path data, and optionally an HTML report with a histogram and thermometer chart. This chapter explains what those outputs mean and how to use them for practical decision-making.

---

## The output at a glance

A typical CLI run produces output like this:

```
=== Simulation Results ===
Project: Customer Portal
Hours per Day: 8.0
Mean: 338.42 hours (43 working days)
Median (P50): 326.15 hours
Std Dev: 67.81 hours

Confidence Intervals:
  P50:  326.15 hours (41 working days)  (2026-04-27)
  P80:  389.20 hours (49 working days)  (2026-05-07)
  P90:  421.58 hours (53 working days)  (2026-05-13)
  P95:  448.73 hours (57 working days)  (2026-05-19)

Most Frequent Critical Paths:
  1. Backend API → Database Migration → Integration Testing (6218/10000, 62.2%)
  2. Backend API → Database Migration → Load Testing (2341/10000, 23.4%)
```

Every number here comes from simulating your project thousands of times with different random samples. The results describe the *distribution* of outcomes, not a single prediction.

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

The **coefficient of variation** (CV = std_dev ÷ mean) normalises the spread:

| CV | Interpretation |
|----|----------------|
| < 0.15 | Low uncertainty — estimates are tight and risks are well-contained |
| 0.15–0.30 | Moderate uncertainty — typical for well-scoped projects with some unknowns |
| 0.30–0.50 | High uncertainty — wide estimate ranges or significant risk exposure |
| > 0.50 | Very high uncertainty — the project timeline is essentially unpredictable at this stage |

A high CV is not necessarily bad — it is *honest*. It tells you that the inputs contain wide estimate ranges, high-probability risks, or both. Narrowing the CV means improving the inputs: tightening estimates, reducing risk exposure, or breaking large tasks into better-understood pieces.

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

## Identifying risky tasks

### Which risks cause the most volatility?

Not all risks contribute equally to schedule uncertainty. To find the ones that matter most, look for:

1. **High probability × high impact**: A risk with 30% chance and 16 hours of impact contributes more expected delay (4.8 hours) than one with 5% chance and 8 hours (0.4 hours).

2. **Risks on critical-path tasks**: A risk that fires on a task with criticality 0.90 almost certainly delays the project. The same risk on a low-criticality task may be absorbed by slack.

3. **Percentage-based project risks**: These scale with project duration. A 15% project-level risk on a 400-hour project adds 60 hours. As the project grows, these become increasingly costly.

### Reducing volatility

If the spread between P50 and P90 is uncomfortably wide, consider:

- **Splitting large tasks**: A single task with `min: 5, max: 40` contributes more variance than two tasks with `min: 3, max: 20` each, especially when they are on different dependency paths.
- **Tightening estimate ranges**: If subject-matter experts can narrow the gap between `min` and `max` after investigation, uncertainty drops directly.
- **Mitigating high-impact risks**: Removing or reducing the probability of risks on critical tasks has the largest effect.
- **Adding parallel paths**: Restructuring dependencies so that fewer tasks are in a single sequential chain reduces the chance of cascading delays.

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
| Criticality index | How often a task is on the critical path | Focusing management attention |
| Critical path sequences | Which chains of tasks dominate | Dependency restructuring |
| Thermometer | Visual probability-to-effort mapping | Stakeholder communication |
| Delivery dates | Calendar dates at each percentile | Scheduling and milestone setting |
