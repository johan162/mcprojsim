# Sprint-Based Planning for `mcprojsim`: Research and Design Proposal

## Executive Summary

`mcprojsim` already produces two important distributions per simulation run: elapsed project duration and total effort. It does that by sampling task uncertainty, applying multiplicative uncertainty factors and additive risks, then scheduling the resulting task durations through dependency-only or resource-constrained scheduling. A sprint-planning mode should therefore be added **alongside** the current engine, not as a replacement for it.

The most suitable approach is an **empirical Monte Carlo sprint forecast** driven by historical team sprint outcomes, with two capacity modes: **story points per sprint** and **tasks/items per sprint**.[^4][^5][^6] Story-point mode is appropriate when the team already plans and measures in points; task-throughput mode is appropriate only when work items are right-sized and reasonably homogeneous, which is exactly the condition emphasized in throughput-driven sprint planning guidance.[^5]

The best way is to make a **dependency-aware sprint simulator** that repeatedly samples sprint capacity from historical data, but with each historical sprint treated as a joint outcome containing **completed work, spill-over work, mid-sprint added work, and mid-sprint removed work**. The simulator should pull a subset of ready tasks into each sprint, model scope added during the sprint, model work explicitly removed from the sprint after planning, carry unfinished work out of the sprint, and stop when all project tasks are complete. The output should be a distribution of **sprints-to-done** (P50/P80/P90), plus date projections, burn-up style percentile bands, commitment guidance for how much planned work to load into future sprints, and volatility diagnostics such as standard deviation and coefficient of variation, reusing the same style of summary statistics already used elsewhere in the product.

The strongest design choice is to make the sprint-capacity model **empirical first** (bootstrap/resampling historical sprint outcomes) rather than parametric first (fit a Normal/Lognormal model to velocity). Scrum and agile forecasting guidance consistently emphasizes using observed variation instead of collapsing data to a single average, and the current product direction already aligns well with Monte Carlo-style sampling of uncertain work.[^4][^6]

## Query Type

This is a **technical deep-dive / architecture proposal**: it asks how to add a new sprint-based forecasting mode to an existing Monte Carlo project simulation system, how to ground it in agile delivery practice, and how to represent uncertainty and volatility in a statistically sound way.[^4]

## Current `mcprojsim` Architecture and Why It Matters

The current simulation engine runs many iterations and, in each one, resolves symbolic estimates, samples a task duration distribution, applies multiplicative uncertainty factors, applies risk impacts, and then schedules the resulting task durations to produce project duration statistics. This means the system is already designed around **repeated stochastic simulation**, so sprint planning should plug into the same style of computation rather than introducing a deterministic planning subsystem.

The engine also stores a per-iteration **effort distribution** by summing all task durations, separately from elapsed duration. That is important because sprint planning is conceptually closer to **capacity vs. backlog consumption** than to critical-path elapsed time; the product already distinguishes those two ideas.

`SimulationResults` already exposes mean, median, standard deviation, skewness, kurtosis, percentile lookup, and dictionary/export support for simulated outputs. That suggests the cleanest extension is to add a parallel result surface for sprint forecasts, rather than trying to coerce sprint metrics into the existing `durations` array.

The staffing analyzer further reinforces that today’s model is fundamentally **effort + capacity => calendar time**, with team-size effects and communication overhead applied after simulation. Sprint planning is a different abstraction: it assumes a fixed sprint cadence and an empirically observed team delivery capacity per sprint, then asks how many sprint buckets are required to finish a backlog.[^4]

Finally, the current program already models dependencies, resource availability, holidays, planned absences, sickness, and practical caps on parallelism. A sprint-planning mode should respect task dependencies and can optionally adjust sampled sprint capacity for known future calendar effects.

## Architecture Overview

```text
Current model
-------------
Task estimates -> sample task durations -> apply uncertainty/risks
               -> schedule tasks by deps/resources/calendars
               -> elapsed-duration distribution + effort distribution

Recommended sprint model
------------------------
Project tasks + sprint config + historical sprint outcomes
             -> build ready queue from dependencies
             -> sample {completed, spill-over, added, removed} profile for Sprint 1
             -> pull ready tasks/items into Sprint 1
             -> inject unplanned added work, remove de-scoped work, and carry over unfinished work
             -> update dependencies / remaining backlog
             -> repeat until all tasks complete
             -> sprint-count distribution + sprint-date distribution
```

## External Research: What Agile Practice Suggests

The Scrum Guide defines Sprints as fixed-length events of one month or less, and the entire framework is explicitly empirical: teams inspect outcomes and adapt based on what actually happened.[^12] That supports a sprint-planning feature whose primary inputs are **historical sprint outcomes** and a **fixed sprint length**.

Atlassian’s velocity guidance describes sprint velocity as the amount of work a Scrum team completes in a sprint, usually in story points, and it explicitly says velocity should be based on **fully completed stories**, averaged across multiple sprints, while also noting that team size, experience, story complexity, and holidays affect it and that velocity is team-specific.[^13] That validates story-point-based sprint capacity as one supported mode, but it also highlights a key limitation: a simple average is not enough when capacity varies materially from sprint to sprint, when items spill out of the sprint, or when urgent work is added after sprint start.[^13]

Scrum.org’s Monte Carlo forecasting article makes the crucial statistical point: using a single average burn rate discards variation, while Monte Carlo forecasting keeps the observed spread and yields a **range** of likely outcomes rather than a falsely precise point forecast.[^4] That is directly aligned with `mcprojsim`’s Monte Carlo philosophy and is the best argument against implementing sprint planning as “remaining backlog / average velocity”.[^4]

Scrum.org’s throughput-driven sprint planning article argues for using **throughput** (completed items per unit time) rather than story points when teams manage similarly sized work items, and it ties that to a Service Level Expectation (SLE) that helps determine whether items are “right-sized” for the workflow.[^5] This is the best support for a second capacity mode based on **tasks/items per sprint**, but it also implies a design constraint: item-throughput forecasting only works well when tasks are small enough and similarly sized enough to behave like comparable work items.[^5]

The LeadingEDJE agile forecasting write-up reinforces the same pattern: flow metrics and Monte Carlo simulation should be used to answer either “how many items by date?” or “when will this amount of work finish?”, using historical throughput or cycle-time data instead of deterministic plans.[^6] That maps almost exactly to the user request for “distribution of how many sprints it takes to complete the total effort to certain percentile.”[^6]

## Compared Approaches

| Approach | How it works | Strengths | Weaknesses | Verdict |
|---|---|---|---|---|
| Average velocity / average throughput | Divide remaining backlog by mean points-per-sprint or tasks-per-sprint | Very simple, easy to explain | Throws away variation; produces brittle point forecasts; weak under volatility[^4][^13] | Do **not** use as primary forecast |
| Parametric capacity distribution | Fit a Normal/ Lognormal /Gamma/ Negative-Binomial model to capacity, then sample | Compact, smooth, supports extrapolation | Risk of fitting the wrong shape; fragile with small sample sizes; harder to explain to users[^4] | Optional advanced mode |
| Empirical Monte Carlo resampling | Sample future sprint outcomes from observed historical sprint outcomes | Preserves real observed variation and churn coupling; easy to explain; aligned with the product’s Monte Carlo direction[^4][^6] | Needs enough history; can inherit historical regime bias | **Recommended default** |
| Throughput + SLE flow forecasting | Forecast completed items using throughput and right-sized items | Works well for item flow; no story points required[^5][^6] | Only valid if items are small and comparable; weaker for uneven task sizes | Recommended for task-count mode |
| Dependency-aware sprint simulation | Resample capacity, but also only pull dependency-ready tasks into each sprint | Matches project-task structure; yields subset-of-tasks-per-sprint plan | More implementation work; needs priority policy | **Recommended core simulator** |

## Recommended Product Design

### 1. Add sprint planning as a distinct planning mode

Add a new top-level project section such as `sprint_planning`, rather than overloading the current `project` or `simulation` sections. The existing engine is duration-based and the new feature is capacity/burn-up based, so the separation should be explicit in the schema and outputs.

Suggested shape:

```yaml
project:
  name: "Example"
  start_date: "2026-04-06"

sprint_planning:
  enabled: true
  sprint_length_weeks: 2
  capacity_mode: "story_points"   # or "tasks"
  removed_work_treatment: "churn_only"   # or "reduce_backlog"
  future_sprint_overrides:
    - sprint_number: 4
      holiday_factor: 0.8
      notes: "Public holiday sprint"
  history:
    - sprint_length_weeks: 2
      completed_story_points: 23
      spillover_story_points: 5
      added_story_points: 3
      removed_story_points: 2
    - sprint_length_weeks: 2
      completed_story_points: 19
      spillover_story_points: 8
      added_story_points: 6
      removed_story_points: 1
    - sprint_length_weeks: 2
      completed_story_points: 26
      spillover_story_points: 2
      added_story_points: 1
      removed_story_points: 0
  uncertainty_mode: "empirical"
  volatility_overlay:
    enabled: true
    disruption_probability: 0.10
    disruption_multiplier_low: 0.5
    disruption_multiplier_expected: 0.8
    disruption_multiplier_high: 1.0
```

The system should support sprint length adjustable in whole weeks and capacity configurable either as tasks-per-sprint or story-points-per-sprint, so those need to be first-class config choices.[^12][^13]

The extended historical fields for sprint churn should be optional in the input schema so teams can start with only completed work and then progressively add richer data. When omitted, `spillover_*`, `added_*`, and `removed_*` should default to `0` for that history row. This preserves backward compatibility for partially observed historical data while still rewarding teams that capture more detailed sprint outcomes.

More generally, every field in a historical sprint row should be omittable and should fall back to a neutral, non-impacting default. This makes it possible to use partially observed historical data without forcing teams to backfill every sprint attribute before they can benefit from the model.

Future calendar adjustments should also be explicitly configurable rather than only described conceptually. The cleanest approach is to allow a `future_sprint_overrides` list in `SprintPlanningSpec`, where each override targets a known future sprint and applies a `holiday_factor` or equivalent capacity multiplier for that specific sprint. This closes the gap between historical interpretation and forward prediction.

### Example complete project file

The following example shows a project file that includes all currently proposed historical sprint data points:

```yaml
project:
  name: "Payments Platform Refresh"
  start_date: "2026-04-06"

simulation:
  iterations: 10000
  random_seed: 42

sprint_planning:
  enabled: true
  sprint_length_weeks: 2
  capacity_mode: "story_points"
  planning_confidence_level: 0.80
  removed_work_treatment: "churn_only"
  uncertainty_mode: "empirical"
  future_sprint_overrides:
    - sprint_number: 3
      holiday_factor: 0.8
      notes: "Spring public holiday"
  history:
    - end_date: "2026-01-16"
      sprint_length_weeks: 2
      completed_story_points: 21
      spillover_story_points: 5
      added_story_points: 3
      removed_story_points: 1
      team_size: 5
      holiday_factor: 1.0
      notes: "Normal sprint"
    - end_date: "2026-01-30"
      sprint_length_weeks: 2
      completed_story_points: 18
      spillover_story_points: 7
      added_story_points: 6
      removed_story_points: 2
      team_size: 5
      holiday_factor: 0.9
      notes: "Production incident interrupted planned work"
    - end_date: "2026-02-13"
      sprint_length_weeks: 2
      completed_story_points: 24
      spillover_story_points: 2
      added_story_points: 1
      removed_story_points: 0
      team_size: 5
      holiday_factor: 1.0
      notes: "Low churn sprint"

  volatility_overlay:
    enabled: true
    disruption_probability: 0.10
    disruption_multiplier_low: 0.5
    disruption_multiplier_expected: 0.8
    disruption_multiplier_high: 1.0

  spillover:
    enabled: true
    model: "table"
    size_reference_points: 5
    size_brackets:
      - max_points: 2
        probability: 0.05
      - max_points: 5
        probability: 0.12
      - max_points: 8
        probability: 0.25
      - max_points: null
        probability: 0.40
    consumed_fraction_alpha: 3.25
    consumed_fraction_beta: 1.75

tasks:
  - id: "discovery"
    name: "Discovery and architecture"
    planning_story_points: 5

  - id: "schema"
    name: "Schema updates"
    planning_story_points: 8
    dependencies: ["discovery"]

  - id: "api"
    name: "API implementation"
    planning_story_points: 8
    dependencies: ["schema"]

  - id: "ui"
    name: "UI integration"
    planning_story_points: 5
    dependencies: ["api"]

  - id: "rollout"
    name: "Rollout and validation"
    planning_story_points: 3
    dependencies: ["ui"]
```

Field omission note:

- Any historical sprint field may be omitted.
- If `sprint_length_weeks` is omitted in a history row, it should default to the parent `sprint_planning.sprint_length_weeks`.
- If `completed_*`, `spillover_*`, `added_*`, or `removed_*` is not present in a history row, it should be treated as `0` for that row.
- If `removed_work_treatment` is omitted, it should default to `churn_only`.
- If `planning_confidence_level` is omitted, it should default to the documented project default, proposed here as `0.80`.
- If `future_sprint_overrides` is omitted, no explicit future sprint adjustments should be applied.
- If `holiday_factor` is omitted, it should default to `1.0`, meaning the sprint is treated as having normal available working time.
- If `end_date`, `team_size`, or `notes` is omitted, it should default to a null/ignored value and should not affect the forecast.

Example sparse historical row with omitted fields:

```yaml
history:
  - completed_story_points: 20
```

This sparse row should be interpreted as if it had been written as:

```yaml
history:
  - sprint_length_weeks: 2          # inherited from sprint_planning.sprint_length_weeks
    completed_story_points: 20
    spillover_story_points: 0
    added_story_points: 0
    removed_story_points: 0
    holiday_factor: 1.0
    end_date: null
    team_size: null
    notes: null
```

  Minimum usable-history note:

  - Sparse rows are allowed for convenience, but the simulation should only run when the history contains at least two usable observations with positive delivery signal after defaulting and normalization.
  - A practical MVP rule is to require at least two historical rows where normalized `completed_* > 0` or where attempted delivery signal (`completed_* + spillover_*`) is positive.

### What `holiday_factor` means

`holiday_factor` is an optional per-history-row capacity scaling value that describes how much effective working time was available in that sprint relative to a normal sprint.

Recommended interpretation:

- `holiday_factor = 1.0`: normal sprint capacity, with no holiday-related reduction;
- `holiday_factor < 1.0`: reduced effective capacity because of public holidays, planned shutdowns, company events, or similar non-working time;
- `holiday_factor > 1.0`: unusually high effective capacity, which should be allowed but should normally be rare and used cautiously.

Examples:

- `holiday_factor = 0.9` means the sprint had about 90% of the normal working availability;
- `holiday_factor = 0.75` means the sprint had materially reduced working time and should not be treated as directly comparable to a full-capacity sprint.

### Purpose of `holiday_factor`

The purpose of `holiday_factor` is to separate **calendar-driven capacity reduction** from **planning instability**.

Without this field, a sprint with lower completion due to holidays can look statistically similar to a sprint with lower completion due to poor planning, excessive spill-over, or large amounts of urgent added work. That would pollute the historical learning signal. `holiday_factor` allows the model to recognize that some lower-output sprints were constrained by reduced availability rather than by estimation error or delivery volatility.

This makes the historical data cleaner in three ways:

1. it reduces the risk of underestimating normal sprint capacity because holiday-affected sprints are mixed in without adjustment;
2. it reduces the risk of overstating spill-over or churn as the explanation for low completion when the real cause was less available working time;
3. it gives the forecast a better basis for adjusting specific future sprints that are already known to have reduced working availability.

### How `holiday_factor` should affect planning and prediction

`holiday_factor` should affect the model as a **capacity normalizer and forward-sprint adjustment**, not as churn.

For historical rows, the cleanest use is to normalize **delivery-side capacity signals** back to a nominal full-capacity basis before comparing or resampling them:

```text
normalized_completed_i = completed_units_i / max(holiday_factor_i, epsilon)
normalized_spillover_i = spillover_units_i / max(holiday_factor_i, epsilon)
normalized_added_i = added_units_i
normalized_removed_i = removed_units_i
```

This keeps a holiday-shortened sprint from being interpreted as evidence that the team normally completes less work. Added and removed scope should remain raw churn signals, because they describe priority change and replanning rather than available working time.

For future sprints, the same factor should be applied in the forward direction when a known future sprint has reduced availability:

```text
effective_future_capacity_t = sampled_nominal_capacity_t * override_holiday_factor_t
```

where `override_holiday_factor_t` comes from a matching `future_sprint_overrides` entry when one is present, and otherwise defaults to `1.0`.

This affects planning and prediction in three specific places:

1. **Sprint planning:** recommended planned load for a future sprint should be reduced when that sprint has a known `holiday_factor < 1.0`.
2. **Completion-date forecasting:** projected completion dates should move later when one or more future sprints are known to have reduced availability.
3. **Historical interpretation:** low-output historical sprints with reduced availability should be discounted as evidence of delivery instability.

In practical terms, `holiday_factor` should influence the forecast differently from the other historical fields:

- `spillover_*`, `added_*`, and `removed_*` describe sprint churn and planning instability;
- `holiday_factor` describes the amount of working time available to the team.

Those are not the same phenomenon and should not be merged statistically.

### 2. Support two planning units, but keep them separate

**Story-point mode** should use observed historical **completed story points**, **spill-over story points**, **added story points**, and **removed story points** per sprint, and should consume backlog in story points.[^13] This is appropriate when the team already estimates backlog items in story points.

**Task mode** should use observed historical **completed tasks/items**, **spill-over tasks/items**, **added tasks/items**, and **removed tasks/items** per sprint, and should consume backlog in units of task-count.[^5] This is appropriate only when the project tasks represent right-sized backlog items rather than large epics; otherwise the forecast will be misleading because one “task” may be far larger than another.[^5]

The current estimate model already supports multiple sizing styles, but that does **not** mean hours-based task estimates can safely be converted into story points, because story points are a relative team-specific measure rather than a time unit.[^13] Therefore:

- if `capacity_mode == "story_points"`, require each planned item to expose planning points explicitly, or require a separate `planning_story_points` field if the task’s duration estimate is not already story-point based;
- if `capacity_mode == "tasks"`, count each eligible task as one item, but warn when item sizes are obviously heterogeneous.

### 3. Use a dependency-aware sprint pull simulator

The model is based on working on a subset of tasks from the project in each sprint. The right way to express that in this design is to build a **SprintPlanner** that mirrors the product’s existing scheduling approach at a sprint level: it should maintain a ready queue of dependency-satisfied tasks and select from that queue sprint by sprint.

Recommended per-iteration algorithm:

1. Build the initial ready queue from tasks whose dependencies are already satisfied.
2. Sample the sprint outcome profile for Sprint `n`, including completed-capacity, added-work, removed-work, and churn behavior.
3. Pull ready tasks in priority order until the usable sprint capacity would be exceeded.
4. Inject sampled added work and remove sampled de-scoped work according to the configured interpretation.
5. Mark finished tasks complete at sprint end and carry forward unfinished work.
6. Unlock newly ready tasks.
7. Repeat until all tasks are done.
8. Record the number of sprints and the sprint-end date.

This produces a true distribution of **sprints-to-done**, rather than merely dividing a scalar backlog by scalar capacity.[^4][^6]

### 4. Make empirical resampling the default uncertainty model

The default sprint-capacity generator should be **empirical bootstrap/resampling** from observed historical sprint outcomes, because that preserves actual volatility and avoids assuming a distribution shape the team may not have.[^4][^6]

For example:

- in story-point mode, resample from historical quadruples of completed story points, spill-over story points, added story points, and removed story points per sprint;
- in task mode, resample from historical quadruples of completed tasks, spill-over tasks, added tasks, and removed tasks per sprint.

If the user changes `sprint_length_weeks`, normalize history to **weekly outcome rates** first, then resample at the weekly level and aggregate to the configured sprint length. This keeps “whole weeks” meaningful and makes 1-week, 2-week, and 3-week sprint scenarios comparable.[^12]

Recommended normalization:

```text
weekly_completed_i = completed_units_i / sprint_length_weeks_i
weekly_spillover_i = spillover_units_i / sprint_length_weeks_i
weekly_added_i = added_units_i / sprint_length_weeks_i
weekly_removed_i = removed_units_i / sprint_length_weeks_i
simulated_sprint_outcome(L weeks) = sum(sampled weekly_completed_1..L,
                                        sampled weekly_spillover_1..L,
                                        sampled weekly_added_1..L,
                                        sampled weekly_removed_1..L)
```

This is statistically cleaner than pretending that historical 2-week sprint capacity can be reused unchanged for a future 3-week sprint.

### 5. Treat spill-over, scope-addition, and scope-removal as first-class historical signals

Historical sprint learning should not be limited to what was completed. Each historical row should be treated as a **joint outcome vector**:

```text
historical_sprint_i = (completed_units_i, spillover_units_i, added_units_i, removed_units_i)
```

where:

- `completed_units_i` is the work fully finished inside sprint `i`;
- `spillover_units_i` is the work still carried out of sprint `i` at sprint end because it did not land;
- `added_units_i` is the work added after sprint start because higher-priority demand interrupted the original plan;
- `removed_units_i` is the work explicitly de-scoped from sprint `i` after sprint start, either because priorities changed or because the plan proved unrealistic.

The most statistically sound default is to resample these vectors **jointly**, not as four independent series. Joint bootstrap preserves the observed correlation structure between healthy sprints, high-churn sprints, and unstable sprints. If the team historically sees that urgent scope additions and de-scoping tend to coincide with more spill-over and lower completion, the simulator should preserve that relationship rather than averaging it away.

Two derived measures should then be computed from the same history:

```text
spillover_ratio_i = spillover_units_i / max(completed_units_i + spillover_units_i, epsilon)
scope_addition_ratio_i = added_units_i / max(completed_units_i + added_units_i, epsilon)
scope_removal_ratio_i = removed_units_i / max(completed_units_i + spillover_units_i + removed_units_i, epsilon)
```

These are the most useful normalized measures of planning instability:

- `spillover_ratio` measures how much of the attempted sprint scope failed to land;
- `scope_addition_ratio` measures how much of the sprint demand arrived after planning was supposedly complete;
- `scope_removal_ratio` measures how much planned sprint scope had to be taken back out after sprint start.

Those historical signals should be used in two different ways:

1. **Completion-date forecasting:** added work should be treated as stochastic scope growth, removed work should be treated as stochastic scope shrinkage, and spill-over should calibrate how much of the sprint plan actually lands versus carries forward.
2. **Planned-load guidance:** future sprint commitments should be lower than raw historical completion whenever the historical data shows frequent scope additions, heavy spill-over, or repeated de-scoping of planned work.

Historical removed work needs a slightly more careful interpretation than historical added work. Added work nearly always represents genuine extra demand that consumed capacity or expanded backlog. Removed work can mean one of two things:

1. the team legitimately discovered that some planned work should no longer be done at all; or
2. the team used removal as a planning escape hatch to avoid reporting spill-over.

The model should therefore use removed work in **two** ways:

- as a measure of **planning churn**, because frequent removals mean the sprint plan was unstable;
- as an optional source of **backlog shrinkage**, but only when the user intends historical removals to represent genuine descoping rather than reclassification.

The cleanest design is to add an optional interpretation flag at the planning-spec level, for example `removed_work_treatment: "churn_only" | "reduce_backlog"`, defaulting to `"churn_only"`. That keeps the forecast conservative unless the user explicitly states that removed work should be modeled as real reduction in remaining project scope.

The simplest commitment rule that makes good use of the available data is:

```text
recommended_planned_commitment(q)
  = max(0,
        Q50(completed_units)
        * (1 - Qq(spillover_ratio))
        * (1 - Qq(scope_removal_ratio))
        - Qq(added_units))
```

for a chosen planning confidence level `q` such as 0.80. This rule is deliberately conservative: it starts with typical delivered capacity, discounts it by a high-percentile spill-over rate, discounts again for the historical tendency to remove planned work after sprint start, and then reserves explicit room for likely mid-sprint scope additions.

For completion-date forecasting, the simulator should instead use the richer sprint recursion:

```text
remaining_backlog_(t+1) = remaining_backlog_t - delivered_units_t + added_units_t - removed_units_t_effective
```

where `delivered_units_t` is produced by the dependency-aware planner after applying sampled capacity and sampled spill-over behavior, and `removed_units_t_effective` is either `0` in `churn_only` mode or the sampled removed work in `reduce_backlog` mode. This is the better place to use the new data for forecast dates, because it models backlog growth, backlog shrinkage, and sprint instability directly instead of collapsing them into one average burn rate.

### 6. Add an explicit volatility layer, but keep it optional

Historical resampling already captures ordinary variation, but the user also asked for “some measurement of the uncertainty in the sprint capacity and potential volatility.” The best design is to distinguish:

- **uncertainty** = the spread already visible in historical sprint outcomes;
- **volatility** = exogenous future shocks that may reduce capacity beyond the normal observed range.

The current engine already uses multiplicative uncertainty factors on task duration. A sprint mode can use the same design pattern, but it should apply it specifically to the **deliverable-capacity component** of the sampled sprint outcome rather than to every historical variable indiscriminately:

```text
effective_deliverable_capacity = sampled_completed_capacity * sampled_volatility_multiplier
```

where the multiplier defaults to `1.0` when no extra volatility model is enabled.

In the MVP design, the volatility overlay should affect the forecast as follows:

- it scales deliverable capacity for the sprint;
- it does **not** directly rescale sampled `added_units` or `removed_units`, because those are scope-churn signals rather than capacity signals;
- it does **not** directly overwrite sampled spill-over history, because spill-over should primarily emerge from reduced effective delivery capacity and the task-level spill-over model.

That boundary keeps the statistical model coherent: calendar and disruption effects reduce what the team can deliver, while churn variables continue to represent changing scope and replanning behavior.

Recommended volatility options:

1. **Empirical only (default)**: no extra layer; use history as-is.
2. **Empirical + disruption overlay**: with probability `p_disruption`, multiply sprint capacity by a sampled factor below 1.
3. **Scenario-driven overrides**: allow planned PTO/known holidays/future events to reduce specific future sprints.

This preserves a simple mental model for users while still allowing “normal” capacity variation and “shock” variation to be reported separately.
### 7. Model task-level execution uncertainty and spill-over

The capacity-volatility layer in section 6 captures sprint-team-wide capacity variation. A second, independent source of uncertainty is **task-level execution overrun**: a task is selected into a sprint, consumes capacity during the sprint, but is not completed by sprint end. It therefore contributes zero to delivered throughput while still consuming some or all of the sprint's capacity budget for that item.

This is distinct from the case in which a task simply does not fit into remaining capacity and is deferred to a later sprint without being started. Execution spill-over means the task *starts*, runs over its planned size, and carries unfinished work into the next sprint.

**Why spill-over probability should be size-dependent**

Empirically, smaller tasks are more predictable: their actual effort stays close to their estimate, so they either finish cleanly within the sprint or are held back. Larger tasks have higher uncertainty in absolute terms, so even when planned-vs-actual ratios are similar, a larger task has more absolute room to overrun. The design should therefore treat spill-over probability as a monotonically increasing function of a task's planned effort, so an 8 SP task has a materially higher probability of spilling over than a 3 SP task.

A practical model is a logistic function of planned size:

```text
P(spillover | planned_points = s) = 1 / (1 + exp(-(a * log(s / ref_size) + b)))
```

where `ref_size` is a reference task size (e.g. 5 SP), `a` controls the steepness of the increase with size, and `b` shifts the overall base rate. A simpler piecewise-linear approximation is also acceptable if user-facing calibration is preferred over a continuous curve:

| Planned size (SP) | Default spill-over probability |
|---|---|
| ≤ 2 | 0.05 |
| 3–5 | 0.12 |
| 6–8 | 0.25 |
| > 8 | 0.40 |

Both forms should be overridable via config; the table-based form is the recommended default for explainability.

**How overrun effort is modeled**

When a spill-over event is triggered for a task, the sprint consumes only a sampled fraction of the task's planned effort during the current sprint. The remaining effort carries forward as a reduced-size "remainder task" that re-enters the ready queue for the next sprint (retaining all original dependencies, now satisfied):

```text
fraction_consumed ~ Beta(alpha_consumed, beta_consumed)  # default: mean ≈ 0.65
remaining_effort  = planned_effort * (1 - fraction_consumed)
```

The default Beta distribution should have `alpha_consumed = 3.25`, `beta_consumed = 1.75`, giving a mean consumed fraction of roughly 0.65 (most of the work is done, but the task still does not land). This parameterisation also captures the occasional case where a task was barely started before it was recognized as too large to finish, by assigning some probability to low consumed fractions.

**Capacity accounting**

During the sprint, the consumed fraction of the spilled task is charged against sprint capacity just like a completed task. The net effect is:

- sprint capacity is partially or fully exhausted by the spilled task;
- no throughput credit is awarded for that sprint;
- the remainder task enters the next sprint's ready pool;
- diagnostics should record carry-over load per iteration so the aggregate spill-over distribution can be reported.

**Config shape**

```yaml
sprint_planning:
  spillover:
    enabled: true
    model: "table"           # "table" | "logistic"
    size_reference_points: 5
    # table mode: one entry per size bracket
    size_brackets:
      - max_points: 2
        probability: 0.05
      - max_points: 5
        probability: 0.12
      - max_points: 8
        probability: 0.25
      - max_points: null    # unbounded
        probability: 0.40
    consumed_fraction_alpha: 3.25
    consumed_fraction_beta: 1.75
```
## Measuring Uncertainty and Volatility

The project already reports standard deviation and coefficient of variation (CV) for simulated duration outputs. The sprint feature should report analogous metrics for historical and simulated sprint capacity, spill-over, and scope churn:

- mean capacity,
- median capacity,
- standard deviation,
- coefficient of variation (`std_dev / mean`),
- P10 / P50 / P90 capacity,
- mean spill-over units,
- spill-over ratio percentiles,
- mean added units,
- scope-addition ratio percentiles,
- mean removed units,
- scope-removal ratio percentiles,
- correlation between completed, spill-over, added, and removed units,
- downside deviation (optional),
- disruption frequency (if volatility overlay is enabled).

These should be shown both for:

1. the **input historical sprint-outcome series**, and
2. the **simulated sprints-to-done output**.

Good user-facing diagnostics would include:

- “historical story-point capacity: mean 21.4, CV 0.18”;
- “historical spill-over ratio: P50 0.12, P80 0.24”;
- “historical added scope: mean 3.1 SP, CV 0.44”;
- “historical removed scope: mean 1.4 SP, P80 ratio 0.09”;
- “recommended planned load at P80 confidence: 15 SP”;
- “P80 completion: 6 sprints”;
- “10% modeled probability of disrupted sprint, median disruption multiplier 0.72”.

## How to Handle Adjustable Sprint Lengths

Sprints are fixed-length events in Scrum, but the chosen fixed length can differ between teams or scenarios.[^12] The safest implementation is:

1. allow a configured `sprint_length_weeks` as a whole number;
2. normalize historical sprint outcomes to weekly rates;
3. aggregate sampled weekly rates back into sprint capacity for the chosen sprint length.

If enough history exists for multiple sprint lengths, a more advanced option is to segment history by sprint length and prefer same-length history before falling back to normalized weekly pooling. That would preserve cadence-specific effects while still supporting scenario analysis.

For delivery-date projection, map sprint counts to dates using sprint boundaries rather than working-day accumulation. However, known calendar effects can still be folded in by scaling future sprint capacity by the ratio of available workdays in that sprint versus nominal workdays.

## How to Treat Partial Work and Carry-Over

There are two distinct ways a task can fail to land in a sprint; they require different modeling treatments.

**Type 1: Capacity-driven deferral.** The task was not pulled into the sprint because there was insufficient remaining capacity to start it. No effort is consumed and no capacity is charged; the task simply waits in the ready queue. This is the case addressed by non-preemptive whole-item pull: if the next ready task does not fit in remaining sprint capacity, it is deferred unchanged.

**Type 2: Execution-driven spill-over.** The task was pulled into the sprint, effort was expended against it, but the work was not completed by sprint end. This is a separate phenomenon: capacity is partially or fully consumed, yet no throughput credit is awarded. The task carries its remaining effort into the next sprint as a reduced-size item.

Atlassian's velocity guidance says only **fully completed** stories count toward sprint velocity.[^13] Both types of carry-over are consistent with that rule: deferred tasks contribute zero to velocity with zero capacity cost; spilled tasks contribute zero to velocity but do carry a capacity cost.

The default for this feature should be **non-preemptive whole-item pull with execution-driven spill-over modeled separately** (see section 7):

- a task that does not fit in remaining capacity is left for a future sprint (Type 1: no capacity consumed);
- a task that is pulled but triggers a spill-over event consumes a sampled fraction of sprint capacity and carries its remaining effort forward as a new, smaller task (Type 2);
- completed tasks are credited to throughput normally.

The two mechanisms combine naturally in the per-iteration algorithm:

1. For each ready task in pull order, if capacity remains for the full task, pull it and check for spill-over using the size-dependent probability model.
2. If a spill-over event fires, charge the consumed fraction, mark the remainder for the next sprint, and continue pulling other tasks with any remaining capacity.
3. If capacity would be exhausted before starting the full task, defer it without charging capacity.
4. At sprint end, compute delivered throughput from fully completed tasks only.

Diagnostics should record, per iteration, both the number of deferred tasks and the total remaining effort from spill-over events, so the aggregate carry-over distribution can be distinguished from capacity-driven deferral in reports.[^13]

Historical spill-over, scope-addition, and scope-removal data should also shape how much work is intentionally loaded into the sprint in the first place. A planner that ignores these measures will systematically overcommit whenever the team has a history of churn or incomplete landings. The output should therefore include both:

- a **completion forecast** for the full backlog, and
- a **recommended planned-load range** for the next sprint, derived from the historical outcome vectors and the chosen planning confidence level.

## Data Model Recommendation

### New project-file structures

Recommended new models:

- `SprintPlanningSpec`
- `SprintHistoryEntry`
- `FutureSprintOverrideSpec`
- `SprintVolatilitySpec`
- `SprintSpilloverSpec`
- `SprintCarryoverRecord`
- `SprintPlanningResults`

Suggested fields:

| Model | Fields |
|---|---|
| `SprintPlanningSpec` | `enabled`, `sprint_length_weeks`, `capacity_mode`, `history`, `uncertainty_mode`, `volatility_overlay`, `spillover_config`, `priority_mode`, `service_level_expectation_days`, `planning_confidence_level`, `removed_work_treatment`, `future_sprint_overrides` |
| `SprintHistoryEntry` | `end_date?`, `sprint_length_weeks`, `completed_tasks?`, `completed_story_points?`, `spillover_tasks?`, `spillover_story_points?`, `added_tasks?`, `added_story_points?`, `removed_tasks?`, `removed_story_points?`, `team_size?`, `holiday_factor?`, `notes?` |
| `FutureSprintOverrideSpec` | `sprint_number?`, `start_date?`, `holiday_factor?`, `capacity_multiplier?`, `notes?` |
| `SprintVolatilitySpec` | `enabled`, `disruption_probability`, `multiplier_distribution` |
| `SprintSpilloverSpec` | `enabled`, `model` (`table` or `logistic`), `size_reference_points`, `size_brackets`, `consumed_fraction_alpha`, `consumed_fraction_beta` |
| `SprintCarryoverRecord` | `sprint_number`, `task_id`, `planned_points`, `consumed_fraction`, `remaining_points` |
| `SprintPlanningResults` | `sprint_counts`, `sprint_percentiles`, `date_percentiles`, `capacity_statistics`, `spillover_statistics`, `scope_addition_statistics`, `scope_removal_statistics`, `joint_outcome_statistics`, `planned_commitment_guidance`, `burnup_percentiles`, `carryover_statistics` |

The new optional historical fields should be interpreted as follows:

- `removed_story_points` / `removed_tasks`: work explicitly taken out of the sprint after sprint start;
- `removed_work_treatment`: whether removed work only informs churn/commitment guidance or also reduces the remaining forecast backlog.
- `holiday_factor`: the fraction of normal working availability in that sprint, used to distinguish reduced calendar availability from true planning or delivery instability.
- `end_date`: optional metadata for chronological ordering, reporting, and potential later segmentation; not required for the MVP forecast math.
- `team_size`: optional metadata for diagnostics and future analysis; not used as a direct scaling input in the MVP forecast.
- `future_sprint_overrides`: optional forward-looking calendar/capacity adjustments for specific known future sprints.

All historical sprint-row fields should be optional per history row. Neutral defaults should be applied as follows:

- `sprint_length_weeks` -> inherit from `SprintPlanningSpec.sprint_length_weeks`
- `completed_*` -> `0`
- `spillover_*` -> `0`
- `added_*` -> `0`
- `removed_*` -> `0`
- `holiday_factor` -> `1.0`
- `end_date` -> `null` / ignored
- `team_size` -> `null` / ignored
- `notes` -> `null` / ignored

An implementation-oriented schema defaulting rule should be stated explicitly:

- every omitted history-row field should be normalized to its neutral default before statistical processing;
- `sprint_length_weeks` inherits from the parent sprint-planning spec when omitted in a history row;
- `completed_*`, `spillover_*`, `added_*`, and `removed_*` default to `0` per history row;
- `holiday_factor` defaults to `1.0` per history row;
- `removed_work_treatment` defaults to `churn_only` at the planning-spec level;
- `planning_confidence_level` should default to a documented value such as `0.80` if omitted.

### Task-level additions

If story-point sprint mode needs to coexist with time-based duration estimates, add a separate optional field such as `planning_story_points` on `Task`. That avoids conflating delivery forecasting units with time-estimation units.[^13]

Optional additions:

- `priority` for pull order within the ready queue,
- `epic` / `milestone` grouping for richer burn-up views,
- `sprint_sized: true/false` to gate task-throughput mode warnings,
- `spillover_probability_override: float` to allow per-task overrides of the size-bracket default when a specific task is known to carry higher execution risk.

## Recommended Internal Component Design

| Component | Responsibility | Suggested module |
|---|---|---|
| `SprintCapacitySampler` | Jointly sample per-sprint completed, spill-over, added-work, and removed-work outcomes from history and volatility config | `planning/sprint_capacity.py` |
| `SprintPlanner` | Build ready queue, pull tasks into sprint buckets, inject unplanned additions, remove de-scoped work, and advance dependencies | `planning/sprint_planner.py` |
| `SprintSimulationEngine` | Run N iterations, update backlog with added and optionally removed work, and produce sprint-count arrays | `planning/sprint_engine.py` |
| `SprintPlanningResults` | Percentiles, dates, capacity stats, churn metrics, and planned-load guidance | `models/sprint_simulation.py` |

This keeps sprint planning modular and avoids destabilizing the current duration-based simulation engine.

## Integration with Existing `mcprojsim` Concepts

### Reuse what already fits

- Reuse the existing Monte Carlo iteration pattern.
- Reuse the existing statistics and percentile reporting style.
- Reuse the existing project dependency graph and task order.
- Reuse calendar metadata to adjust future sprint capacity when desired.

### Do **not** force-fit what does not

- Do not convert hours directly into story points.[^13]
- Do not reuse critical-path elapsed duration as sprint count; sprint planning is a backlog-capacity forecast, not a path-length forecast.
- Do not assume task-count throughput is valid unless items are right-sized.[^5]

## MVP vs. Follow-On Roadmap

### MVP

1. Add `sprint_planning` project schema.
2. Support `capacity_mode = story_points | tasks`.
3. Add historical `spillover_*`, `added_*`, and `removed_*` fields to sprint history.
4. Implement empirical joint resampling of completed, spill-over, added-work, and removed-work history.
5. Implement dependency-aware sprint pulling with whole-item completion.
6. Report `P50/P80/P90 sprints`, delivery dates, recommended planned load, and historical capacity/churn stats.

### Phase 2

1. Add optional volatility/disruption overlay.
2. Add execution-driven spill-over modeling with size-dependent probability and sampled consumed-fraction carry-over (see section 7). Report per-sprint carry-over distribution alongside the main sprints-to-done percentiles.
3. Add calendar-adjusted future sprint capacity.
4. Add burn-up percentile charts by sprint.
5. Add warnings for heterogeneous task sizes in task-throughput mode.

### Phase 3

1. Add parametric capacity models as advanced options.
2. Add scenario analysis for team-size changes.
3. Add support for multiple teams / multiple sprint lanes.

## Implementation Notes

To make the proposal implementable without further design gaps, the following details should be treated as part of the MVP-level document guidance:

1. **Schema and validation behavior**

- `SprintHistoryEntry` should accept sparse historical rows where churn fields are absent.
- Validation should normalize every omitted history-row field to its neutral default before downstream statistical processing.
- Validation should reject histories that do not contain at least two usable observations with positive delivery signal after defaulting and normalization.
- Validation should reject mixed unit families within the same history series.

`end_date` and `team_size` should be treated as metadata-only fields in the MVP. They may be stored and reported, but they should not silently alter capacity calculations unless a later design explicitly introduces that behavior.

2. **Sampler behavior**

- `SprintCapacitySampler` should normalize historical rows into a canonical internal tuple:

- `SprintCapacitySampler` should normalize historical rows into a canonical internal tuple:

```text
(completed_units, spillover_units, added_units, removed_units)
```

- The sampler should apply per-row default filling before weekly normalization.
- The sampler should only holiday-normalize delivery-side quantities (`completed`, and optionally `spillover` if that interpretation is retained), while leaving `added` and `removed` as raw churn signals.
- The sampler should expose both the sampled delivered-capacity component and the sampled churn components so downstream planning logic does not have to reverse-engineer them from a single scalar.
- The sampler should also apply any matching `future_sprint_overrides` when simulating known future sprints.

3. **Planner and engine behavior**

- `SprintPlanner` should treat added work and removed work as sprint-level events distinct from task execution spill-over.
- `SprintSimulationEngine` should make the backlog update rule explicit and auditable per iteration so it is clear whether a date forecast changed because of delivery, spill-over, added scope, or removed scope.
- Volatility should reduce deliverable capacity, while churn and task-level spill-over should remain behaviorally separate mechanisms.

4. **CLI and export behavior**

- CLI summaries should surface the selected `removed_work_treatment` whenever sprint planning mode is active.
- JSON and CSV exports should include raw historical churn summaries, derived ratios, and recommended planned-load guidance in a dedicated sprint-planning section.
- Reports should clearly distinguish:
  - work completed,
  - work added,
  - work removed,
  - work spilled over,
  - and work still remaining.

These implementation notes do not change the design; they close the remaining specification gaps between the proposal and an actual implementation plan.

## Why This Is the Best-Fit Approach for `mcprojsim`

This design fits the repository because it preserves the current Monte Carlo style, keeps the existing duration/effort outputs intact, and adds a parallel forecast for sprint cadence rather than trying to reinterpret the current duration arrays. It is also well grounded in agile practice: Sprints are fixed cadence, velocity/throughput should be based on completed work, and forecasts should reflect observed variation rather than a single mean.[^4][^5][^12][^13]

Most importantly, it answers the actual user problem:

- adjustable sprint length in whole weeks,
- either tasks-per-sprint or story-points-per-sprint capacity,
- historical learning from completed work, spill-over, and scope added during the sprint,
- historical learning from work removed from the sprint after planning,
- a statistically grounded recommendation for how much planned work should be loaded into future sprints,
- explicit uncertainty and volatility handling,
- and a percentile distribution for how many sprints it takes to finish the project.[^4][^5][^6]

## Confidence Assessment

**High confidence**

- `mcprojsim` is already structurally compatible with a sprint Monte Carlo extension because it already samples work stochastically, stores per-iteration outputs, and reports percentile/statistical summaries.
- An empirical Monte Carlo sprint-capacity model is better founded than an average-velocity model, based on agile forecasting references.[^4][^6]
- A dependency-aware sprint pull planner is the right way to model “subset of tasks per sprint” in this design.

**Medium confidence**

- Weekly normalization is the best way to support adjustable sprint lengths, but it may underrepresent ceremony/batching effects if a team has only ever worked in one sprint cadence.
- Task-count throughput mode is valuable, but only if tasks are roughly right-sized; some projects in `mcprojsim` may currently define tasks at too coarse a granularity for that to be reliable.[^5]
- Historical added-work data tells us that scope churn exists, but if the project does not distinguish whether added work was also finished inside the same sprint, commitment guidance will remain conservative rather than exact.
- Historical removed-work data is useful, but its forecast meaning depends on whether removal means genuine descoping or only replanning; the default should therefore remain conservative.

**Assumptions / inferred design choices**

- I assume sprint planning is intended as an **additional** forecast view, not a replacement for the current duration/effort simulation.
- I assume “subset of tasks” means selecting whole tasks/items into sprints, not simulating arbitrary task fractions.
- I assume the product can introduce one or two new planning-specific fields on tasks if story-point sprint mode must coexist with hour-based duration estimates.

## Footnotes

[^4]: `https://www.scrum.org/resources/blog/monte-carlo-forecasting-scrum` (Scrum.org, “Monte Carlo forecasting in Scrum”)
[^5]: `https://www.scrum.org/resources/blog/throughput-driven-sprint-planning` (Scrum.org, “Throughput-Driven Sprint Planning”)
[^6]: `https://blog.leadingedje.com/post/agileforecasting/caseforit.html` (LeadingEDJE, “Agile Forecasting: Monte Carlo Simulations and Flow Metrics”)
[^12]: `https://scrumguides.org/scrum-guide.html` (The Scrum Guide, section “The Sprint”)
[^13]: `https://www.atlassian.com/agile/project-management/velocity-scrum` (Atlassian, “Velocity in Scrum”)
---

## Formal Requirements

### FR-SP-001: Sprint Planning Mode Integration
- The system SHALL support sprint-based planning as an additional, parallel planning mode that does not replace or alter the existing Monte Carlo duration/effort simulation.
- Sprint planning SHALL be enabled via a dedicated top-level `sprint_planning` section in the project definition file.
- Existing project files that omit the `sprint_planning` section SHALL remain fully valid and SHALL run in the existing simulation mode without change.

### FR-SP-002: Sprint Length Configuration
- The system SHALL allow the sprint length to be configured as a whole number of weeks.
- The sprint length SHALL be applied consistently to all sprints within a simulation run.
- Historical sprint outcome entries that use a different sprint length than the configured sprint length SHALL be normalized to a weekly outcome rate before resampling.

### FR-SP-003: Capacity Planning Units
- The system SHALL support two mutually exclusive capacity modes: `story_points` and `tasks`.
- In `story_points` mode, each task SHALL expose a planning story-point value, either via an existing story-point estimate or a separate `planning_story_points` field on the task, and sprint capacity SHALL be measured in story points.
- In `tasks` mode, each eligible task SHALL count as one unit of work, and sprint capacity SHALL be measured in completed task count.
- The system SHALL warn when `tasks` mode is used and task sizes are heterogeneous, as throughput-based forecasting is only reliable when items are roughly comparable in size.
- The system SHALL NOT silently convert hours-based duration estimates into story points.

### FR-SP-004: Historical Sprint Outcome Input
- The system SHALL accept a list of historical sprint outcome observations provided by the user in the project definition file.
- Any field in a historical sprint outcome entry MAY be omitted.
- In `story_points` mode, a history entry MAY provide `completed_story_points`, `spillover_story_points`, `added_story_points`, and `removed_story_points`.
- In `tasks` mode, a history entry MAY provide `completed_tasks`, `spillover_tasks`, `added_tasks`, and `removed_tasks`.
- When `sprint_length_weeks` is omitted from a history entry, the system SHALL default it to the parent `sprint_planning.sprint_length_weeks`.
- When `completed_*`, `spillover_*`, `added_*`, or `removed_*` fields are omitted, the system SHALL treat the missing value as `0` for that sprint.
- When `holiday_factor` is omitted, the system SHALL treat it as `1.0` for that sprint.
- When `end_date`, `team_size`, or `notes` are omitted, the system SHALL treat them as null/ignored metadata values.
- The system SHALL require at least two historical observations before running a sprint simulation.
- The system SHALL require at least two usable historical observations with positive delivery signal after defaulting and normalization before running a sprint simulation.

### FR-SP-005: Empirical Joint Outcome Resampling
- The default sprint-capacity model SHALL be empirical bootstrap resampling from the provided historical sprint outcome observations.
- The system SHALL resample completed units, spill-over units, added units, and removed units as a joint historical vector so that observed correlations between delivery, spill-over, and scope churn are preserved.
- The system SHALL support historical rows where any fields are absent by first normalizing all omitted fields to their neutral defaults before statistical processing.
- The system SHALL distinguish delivery-capacity signals from churn signals when normalizing historical data, so that holiday/calendar adjustments do not directly rescale raw added-work or removed-work observations.
- The system SHALL normalize history observations to per-week outcome rates and aggregate sampled weekly rates to match the configured sprint length, so that historical sprints of differing lengths can be used together.
- The system SHALL NOT default to using only the historical mean velocity as the sprint capacity; point-estimate forecasting SHALL NOT be the primary output.

### FR-SP-005A: Historical Spill-Over Modeling
- The system SHALL treat historical spill-over as a first-class stochastic input rather than only as explanatory metadata.
- The system SHALL derive a spill-over ratio from the historical data and use it to quantify planning instability.
- The system SHALL use historical spill-over information to reduce recommended planned sprint load and to calibrate future sprint spill-over behavior in simulation.

### FR-SP-005B: Historical Scope-Addition Modeling
- The system SHALL treat historical added work as a first-class stochastic input rather than only as explanatory metadata.
- The system SHALL use historical added-work observations to model future unplanned scope growth during simulation.
- The system SHALL use historical added-work observations to reserve part of future sprint capacity for expected urgent work that arrives after sprint start.

### FR-SP-005C: Historical Scope-Removal Modeling
- The system SHALL treat historical removed work as a first-class stochastic input rather than only as explanatory metadata.
- The system SHALL derive a scope-removal ratio from the historical data and use it to quantify planning churn.
- The system SHALL use historical removed-work observations to reduce recommended planned sprint load when frequent de-scoping indicates unstable sprint commitments.
- The system SHALL support an explicit configuration choice to treat removed work either as churn-only signal or as effective backlog reduction in forecast simulations.

### FR-SP-005D: Historical Metadata Treatment
- The system SHALL treat `end_date`, `team_size`, and `notes` as metadata-only fields in the MVP sprint forecast unless a later feature explicitly enables them as model inputs.
- Metadata-only fields MAY be preserved for reporting, ordering, filtering, or future analysis, but SHALL NOT silently change sprint-capacity calculations in the MVP design.

### FR-SP-006: Dependency-Aware Sprint Pull Simulation
- The system SHALL maintain a ready queue of tasks whose declared dependencies have been satisfied in prior sprints.
- In each simulated sprint, the system SHALL pull tasks from the ready queue in priority order until the sampled sprint capacity would be exceeded.
- The system SHALL inject sampled unplanned work into the sprint and backlog according to the historical added-work model.
- The system SHALL remove sampled de-scoped work from the sprint and optionally from the remaining backlog according to the configured removed-work treatment.
- A task that does not fit within remaining sprint capacity SHALL be deferred to a future sprint without consuming any capacity.
- After each sprint, the system SHALL unlock tasks whose dependencies are now fully satisfied and add them to the ready queue.
- The system SHALL repeat the sprint cycle until all tasks in the project backlog have been completed.
- Each simulation iteration SHALL record the total number of sprints required and the projected completion date.

### FR-SP-006A: Future Sprint Override Configuration
- The system SHALL support explicit configuration of future sprint-specific capacity overrides for known calendar or availability events.
- A future sprint override SHALL allow identifying the target sprint by at least one explicit locator such as sprint number or start date.
- A future sprint override MAY specify a `holiday_factor`, `capacity_multiplier`, or equivalent explicit availability reduction.
- When no future sprint override is configured for a sprint, the forecast SHALL assume a neutral future override of `1.0`.

### FR-SP-007: Sprint Simulation Output and Statistics
- The system SHALL run N iterations of the sprint simulation (using the same configurable iteration count as the existing Monte Carlo engine).
- The system SHALL report P50, P80, and P90 percentiles for the number of sprints required to complete the project.
- The system SHALL report projected delivery dates corresponding to each reported confidence level when a project start date is provided.
- The system SHALL report recommended planned sprint-load guidance for at least one configurable planning confidence level.
- The system SHALL report descriptive statistics for the simulated sprint-count distribution: mean, median, standard deviation, and coefficient of variation.
- The system SHALL report descriptive statistics for the input historical completed-work series, spill-over series, added-work series, and removed-work series: mean, median, standard deviation, and coefficient of variation.
- The system SHALL report spill-over ratio, scope-addition ratio, and scope-removal ratio percentiles derived from the historical sprint outcome data.

### FR-SP-008: Volatility Overlay
- The system SHALL support an optional sprint-level capacity volatility overlay that is disabled by default.
- When enabled, the system SHALL apply a multiplicative disruption factor to sampled sprint capacity with a configurable disruption probability and a configurable impact range.
- The effective sprint capacity SHALL be computed as the product of the resampled historical completed-capacity component and the sampled disruption multiplier.
- When no volatility overlay is configured, the multiplier SHALL default to 1.0, preserving the empirical-only behavior.
- The system SHALL support scenario-driven capacity overrides for individual future sprints to model known planned events such as public holidays or team unavailability.
- The volatility overlay SHALL affect deliverable sprint capacity and SHALL NOT directly rescale raw historical added-work or removed-work observations.
- The volatility overlay SHALL remain distinct from task-level spill-over and from scope-churn variables, which continue to be modeled separately.

### FR-SP-009: Task-Level Execution Spill-Over Modeling
- The system SHALL support an optional task-level spill-over model that is disabled by default.
- When enabled, each task pulled into a sprint SHALL be evaluated for execution spill-over using a size-dependent probability model.
- The probability of spill-over SHALL increase monotonically with planned task size so that larger tasks have a materially higher probability of spilling over than smaller tasks.
- The system SHALL support two spill-over probability models: a table-based piecewise model (default) and a logistic function of log task size.
- The default table-based model SHALL assign spill-over probabilities of 0.05 for tasks of 1–2 SP, 0.12 for 3–5 SP, 0.25 for 6–8 SP, and 0.40 for tasks larger than 8 SP.
- The probability brackets SHALL be configurable in the project definition file.
- Individual tasks MAY declare a `spillover_probability_override` to supersede the size-bracket default.

### FR-SP-010: Spill-Over Effort Carry-Over
- When a spill-over event is triggered for a task, the system SHALL sample the fraction of planned effort consumed during the current sprint from a Beta distribution.
- The default Beta distribution parameters SHALL yield a mean consumed fraction of approximately 0.65 (`alpha = 3.25`, `beta = 1.75`).
- The consumed fraction SHALL be charged against the current sprint's capacity budget.
- The task SHALL NOT be credited to delivered throughput in the current sprint.
- The remaining effort SHALL be re-entered into the ready queue as a reduced-size remainder task for the next sprint, retaining the original task's dependency relationships (which are already satisfied at the point of spill-over).
- The Beta distribution parameters SHALL be configurable in the project definition file.

### FR-SP-011: Carry-Over and Spill-Over Diagnostics
- The system SHALL distinguish between capacity-driven deferral (task not started, no capacity consumed) and execution-driven spill-over (task started, capacity partially consumed, not delivered) in all diagnostic output.
- The system SHALL report, per simulation run, the distribution of carry-over load across sprints, including mean and P80/P90 carry-over effort.
- The system SHALL report the aggregate spill-over rate as the fraction of task-sprint assignments that resulted in a spill-over event.

### FR-SP-012: Schema and Validation
- The system SHALL validate that `sprint_length_weeks` is a positive integer.
- The system SHALL validate that `capacity_mode` is one of the supported enumerated values.
- The system SHALL validate that at least two historical sprint outcome entries are provided before accepting the sprint planning configuration.
- The system SHALL validate that all historical `completed_*`, `spillover_*`, `added_*`, and `removed_*` values are non-negative.
- The system SHALL validate that every historical row can be normalized by applying neutral defaults to omitted fields before downstream statistical processing.
- The system SHALL validate that the history contains at least two usable observations with positive delivery signal after defaulting and normalization.
- The system SHALL validate that each history entry uses the unit family implied by `capacity_mode` and does not mix task counts with story-point values for the same simulation.
- The system SHALL validate that `planning_confidence_level`, when provided, is in the open interval `(0, 1)`.
- The system SHALL validate that `removed_work_treatment`, when provided, is one of `churn_only` or `reduce_backlog`.
- The system SHALL validate that any configured future sprint override targets a uniquely identifiable sprint and uses positive multiplier values.
- The system SHALL validate that all spill-over probability values are in the range [0.0, 1.0].
- The system SHALL validate that the Beta distribution parameters `alpha` and `beta` are both strictly positive.
- Tasks referencing `spillover_probability_override` SHALL fail validation if the value is outside [0.0, 1.0].
- When `capacity_mode` is `story_points`, the system SHALL validate that every task in the project backlog has a resolvable planning story-point value and SHALL report a validation error for any task that does not.

### FR-SP-013: Export and Reporting
- Sprint planning results SHALL be included in JSON and CSV exports when the sprint planning mode is active.
- Sprint planning results SHALL be clearly separated from the existing duration/effort simulation results in all output formats.
- CLI output SHALL indicate whether sprint planning mode was active and summarize the P50/P80/P90 sprint-count results.
- Exports SHALL include the completed-work, spill-over, added-work, and removed-work statistics for the input historical series alongside the simulated sprint-count percentiles.
- Exports SHALL include the recommended planned sprint-load guidance and the planning confidence level used to compute it.
- When the volatility overlay is enabled, exports SHALL report the disruption probability and the simulated disruption frequency observed across iterations.
- When the spill-over model is enabled, exports SHALL include the aggregate spill-over rate and the carry-over distribution summary.
- Exports SHALL include the historical spill-over ratio, scope-addition ratio, and scope-removal ratio summaries used in the forecast.
- Exports SHALL include the configured removed-work treatment used when projecting remaining backlog and completion dates.

### FR-SP-014: Internal Component Structure
- Sprint planning logic SHALL be implemented in a dedicated `planning/` module to preserve separation of concerns and avoid modifying the existing simulation engine.
- The module SHALL contain at minimum: a `SprintCapacitySampler` for resampling historical sprint outcome vectors, a `SprintPlanner` for managing the ready queue and sprint pulling, a `SprintSimulationEngine` for running N iterations, and a `SprintPlanningResults` model for holding output arrays and statistics.
- The sprint simulation engine SHALL reuse the existing project's random seed mechanism to ensure reproducible results when a seed is configured.