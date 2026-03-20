# Sprint-Based Planning for `mcprojsim`: Research and Design Proposal

## Executive Summary

`mcprojsim` already produces two important distributions per simulation run: elapsed project duration and total effort. It does that by sampling task uncertainty, applying multiplicative uncertainty factors and additive risks, then scheduling the resulting task durations through dependency-only or resource-constrained scheduling.[^1][^2][^3] A sprint-planning mode should therefore be added **alongside** the current engine, not as a replacement for it.[^1][^3]

The most suitable approach is an **empirical Monte Carlo sprint forecast** driven by historical team capacity, with two capacity modes: **story points per sprint** and **tasks/items per sprint**.[^4][^5][^6] Story-point mode is appropriate when the team already plans and measures in points; task-throughput mode is appropriate only when work items are right-sized and reasonably homogeneous, which is exactly the condition emphasized in throughput-driven sprint planning guidance.[^5][^7]

The best way is to make a **dependency-aware sprint simulator** that repeatedly samples sprint capacity from historical data, pulls a subset of ready tasks into each sprint, and stops when all project tasks are complete.[^1][^8] The output should be a distribution of **sprints-to-done** (P50/P80/P90), plus date projections, burn-up style percentile bands, and volatility diagnostics such as standard deviation and coefficient of variation, reusing statistical conventions the project already uses for duration reporting.[^2][^3]

The strongest design choice is to make the sprint-capacity model **empirical first** (bootstrap/resampling historical sprint capacity) rather than parametric first (fit a Normal/Lognormal model to velocity). Scrum and agile forecasting guidance consistently emphasizes using observed variation instead of collapsing data to a single average, and the current codebase is already organized around Monte Carlo sampling of uncertain work.[^4][^6][^9]

## Query Type

This is a **technical deep-dive / architecture proposal**: it asks how to add a new sprint-based forecasting mode to an existing Monte Carlo project simulation system, how to ground it in agile delivery practice, and how to represent uncertainty and volatility in a statistically sound way.[^1][^4]

## Current `mcprojsim` Architecture and Why It Matters

The current simulation engine runs many iterations and, in each one, resolves symbolic estimates, samples a task duration distribution, applies multiplicative uncertainty factors, applies risk impacts, and then schedules the resulting task durations to produce project duration statistics.[^1][^8] This means the system is already designed around **repeated stochastic simulation**, so sprint planning should plug into the same style of computation rather than introducing a deterministic planning subsystem.[^1][^8]

The engine also stores a per-iteration **effort distribution** by summing all task durations, separately from elapsed duration.[^1] That is important because sprint planning is conceptually closer to **capacity vs. backlog consumption** than to critical-path elapsed time; the repository already distinguishes those two ideas.[^1][^3]

`SimulationResults` already exposes mean, median, standard deviation, skewness, kurtosis, percentile lookup, and dictionary/export support for simulated outputs.[^2] That suggests the cleanest extension is to add a parallel result surface for sprint forecasts, rather than trying to coerce sprint metrics into the existing `durations` array.[^2]

The staffing analyzer further reinforces that today’s model is fundamentally **effort + capacity => calendar time**, with team-size effects and communication overhead applied after simulation.[^3] Sprint planning is a different abstraction: it assumes a fixed sprint cadence and an empirically observed team delivery capacity per sprint, then asks how many sprint buckets are required to finish a backlog.[^3][^4]

Finally, the scheduler and constrained-scheduling documentation show that the current program already models dependencies, resource availability, holidays, planned absences, sickness, and practical caps on parallelism.[^10][^11] A sprint-planning mode should respect task dependencies and can optionally adjust sampled sprint capacity for known future calendar effects.[^10][^11]

## Architecture Overview

```text
Current model
-------------
Task estimates -> sample task durations -> apply uncertainty/risks
               -> schedule tasks by deps/resources/calendars
               -> elapsed-duration distribution + effort distribution

Recommended sprint model
------------------------
Project tasks + sprint config + historical sprint capacity
             -> build ready queue from dependencies
             -> sample sprint capacity for Sprint 1
             -> pull ready tasks/items into Sprint 1
             -> update dependencies / remaining backlog
             -> repeat until all tasks complete
             -> sprint-count distribution + sprint-date distribution
```

## External Research: What Agile Practice Suggests

The Scrum Guide defines Sprints as fixed-length events of one month or less, and the entire framework is explicitly empirical: teams inspect outcomes and adapt based on what actually happened.[^12] That supports a sprint-planning feature whose primary inputs are **historical completed work per sprint** and a **fixed sprint length**.

Atlassian’s velocity guidance describes sprint velocity as the amount of work a Scrum team completes in a sprint, usually in story points, and it explicitly says velocity should be based on **fully completed stories**, averaged across multiple sprints, while also noting that team size, experience, story complexity, and holidays affect it and that velocity is team-specific.[^13] That validates story-point-based sprint capacity as one supported mode, but it also highlights a key limitation: a simple average is not enough when capacity varies materially from sprint to sprint.[^13]

Scrum.org’s Monte Carlo forecasting article makes the crucial statistical point: using a single average burn rate discards variation, while Monte Carlo forecasting keeps the observed spread and yields a **range** of likely outcomes rather than a falsely precise point forecast.[^4] That is directly aligned with `mcprojsim`’s current Monte Carlo philosophy and is the best argument against implementing sprint planning as “remaining backlog / average velocity”.[^1][^4]

Scrum.org’s throughput-driven sprint planning article argues for using **throughput** (completed items per unit time) rather than story points when teams manage similarly sized work items, and it ties that to a Service Level Expectation (SLE) that helps determine whether items are “right-sized” for the workflow.[^5] This is the best support for a second capacity mode based on **tasks/items per sprint**, but it also implies a design constraint: item-throughput forecasting only works well when tasks are small enough and similarly sized enough to behave like comparable work items.[^5]

The LeadingEDJE agile forecasting write-up reinforces the same pattern: flow metrics and Monte Carlo simulation should be used to answer either “how many items by date?” or “when will this amount of work finish?”, using historical throughput or cycle-time data instead of deterministic plans.[^6] That maps almost exactly to the user request for “distribution of how many sprints it takes to complete the total effort to certain percentile.”[^6]

## Compared Approaches

| Approach | How it works | Strengths | Weaknesses | Verdict |
|---|---|---|---|---|
| Average velocity / average throughput | Divide remaining backlog by mean points-per-sprint or tasks-per-sprint | Very simple, easy to explain | Throws away variation; produces brittle point forecasts; weak under volatility[^4][^13] | Do **not** use as primary forecast |
| Parametric capacity distribution | Fit a Normal/Lognormal/Gamma/Negative-Binomial model to capacity, then sample | Compact, smooth, supports extrapolation | Risk of fitting the wrong shape; fragile with small sample sizes; harder to explain to users[^4] | Optional advanced mode |
| Empirical Monte Carlo resampling | Sample future sprint capacity from observed historical sprint capacities | Preserves real observed variation; easy to explain; aligned with current engine[^1][^4][^6] | Needs enough history; can inherit historical regime bias | **Recommended default** |
| Throughput + SLE flow forecasting | Forecast completed items using throughput and right-sized items | Works well for item flow; no story points required[^5][^6] | Only valid if items are small and comparable; weaker for uneven task sizes | Recommended for task-count mode |
| Dependency-aware sprint simulation | Resample capacity, but also only pull dependency-ready tasks into each sprint | Matches project-task structure; yields subset-of-tasks-per-sprint plan[^8][^10] | More implementation work; needs priority policy | **Recommended core simulator** |

## Recommended Product Design

### 1. Add sprint planning as a distinct planning mode

Add a new top-level project section such as `sprint_planning`, rather than overloading the current `project` or `simulation` sections. The existing engine is duration-based and the new feature is capacity/burn-up based, so the separation should be explicit in the schema and outputs.[^1][^2][^3]

Suggested shape:

```yaml
project:
  name: "Example"
  start_date: "2026-04-06"

sprint_planning:
  enabled: true
  sprint_length_weeks: 2
  capacity_mode: "story_points"   # or "tasks"
  history:
    - sprint_length_weeks: 2
      completed_story_points: 23
    - sprint_length_weeks: 2
      completed_story_points: 19
    - sprint_length_weeks: 2
      completed_story_points: 26
  uncertainty_mode: "empirical"
  volatility_overlay:
    enabled: true
    disruption_probability: 0.10
    disruption_multiplier_low: 0.5
    disruption_multiplier_expected: 0.8
    disruption_multiplier_high: 1.0
```

The system should support sprint length adjustable in whole weeks and capacity configurable either as tasks-per-sprint or story-points-per-sprint, so those need to be first-class config choices.[^12][^13]

### 2. Support two planning units, but keep them separate

**Story-point mode** should use observed historical **completed story points per sprint** as capacity and should consume backlog in story points.[^13] This is appropriate when the team already estimates backlog items in story points.

**Task mode** should use observed historical **completed tasks/items per sprint** as capacity and should consume backlog in units of task-count.[^5] This is appropriate only when the project tasks represent right-sized backlog items rather than large epics; otherwise the forecast will be misleading because one “task” may be far larger than another.[^5]

The repository’s current estimate model already supports explicit ranges, T-shirt sizes, and story points, and symbolic estimates are resolved before sampling.[^7][^8] But that does **not** mean hours-based task estimates can safely be converted into story points, because story points are a relative team-specific measure rather than a time unit.[^13] Therefore:

- if `capacity_mode == "story_points"`, require each planned item to expose planning points explicitly, or require a separate `planning_story_points` field if the task’s duration estimate is not already story-point based;
- if `capacity_mode == "tasks"`, count each eligible task as one item, but warn when item sizes are obviously heterogeneous.

### 3. Use a dependency-aware sprint pull simulator

The model is based on working on a subset of tasks from the project in each sprint. The right way to express that in this repository is to build a **SprintPlanner** that mirrors what `TaskScheduler` does for hour-level execution: it should maintain a ready queue of dependency-satisfied tasks and select from that queue sprint by sprint.[^8][^10]

Recommended per-iteration algorithm:

1. Build the initial ready queue from tasks whose dependencies are already satisfied.[^10]
2. Sample sprint capacity for Sprint `n`.
3. Pull ready tasks in priority order until capacity would be exceeded.
4. Mark those tasks complete at sprint end.
5. Unlock newly ready tasks.
6. Repeat until all tasks are done.
7. Record the number of sprints and the sprint-end date.

This produces a true distribution of **sprints-to-done**, rather than merely dividing a scalar backlog by scalar capacity.[^4][^6]

### 4. Make empirical resampling the default uncertainty model

The default sprint-capacity generator should be **empirical bootstrap/resampling** from observed historical capacity, because that preserves actual volatility and avoids assuming a distribution shape the team may not have.[^4][^6]

For example:

- in story-point mode, resample from historical completed story points per sprint;
- in task mode, resample from historical completed tasks per sprint.

If the user changes `sprint_length_weeks`, normalize history to a **weekly capacity rate** first, then resample at the weekly level and aggregate to the configured sprint length. This keeps “whole weeks” meaningful and makes 1-week, 2-week, and 3-week sprint scenarios comparable.[^12]

Recommended normalization:

```text
weekly_capacity_i = completed_units_i / sprint_length_weeks_i
simulated_sprint_capacity(L weeks) = sum(sampled weekly_capacity_1..L)
```

This is statistically cleaner than pretending that historical 2-week sprint capacity can be reused unchanged for a future 3-week sprint.

### 5. Add an explicit volatility layer, but keep it optional

Historical resampling already captures ordinary variation, but the user also asked for “some measurement of the uncertainty in the sprint capacity and potential volatility.” The best design is to distinguish:

- **uncertainty** = the spread already visible in historical capacity;
- **volatility** = exogenous future shocks that may reduce capacity beyond the normal observed range.

The current engine already uses multiplicative uncertainty factors on task duration.[^8] A sprint mode can use the same design pattern:

```text
effective_sprint_capacity = sampled_capacity * sampled_volatility_multiplier
```

where the multiplier defaults to `1.0` when no extra volatility model is enabled.

Recommended volatility options:

1. **Empirical only (default)**: no extra layer; use history as-is.
2. **Empirical + disruption overlay**: with probability `p_disruption`, multiply sprint capacity by a sampled factor below 1.
3. **Scenario-driven overrides**: allow planned PTO/known holidays/future events to reduce specific future sprints.

This preserves a simple mental model for users while still allowing “normal” capacity variation and “shock” variation to be reported separately.
### 6. Model task-level execution uncertainty and spill-over

The capacity-volatility layer in section 5 captures sprint-team-wide capacity variation. A second, independent source of uncertainty is **task-level execution overrun**: a task is selected into a sprint, consumes capacity during the sprint, but is not completed by sprint end. It therefore contributes zero to delivered throughput while still consuming some or all of the sprint's capacity budget for that item.

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

The project already reports standard deviation and coefficient of variation (CV) for simulated duration outputs.[^2][^9] The sprint feature should report analogous metrics for historical and simulated sprint capacity:

- mean capacity,
- median capacity,
- standard deviation,
- coefficient of variation (`std_dev / mean`),
- P10 / P50 / P90 capacity,
- downside deviation (optional),
- disruption frequency (if volatility overlay is enabled).

These should be shown both for:

1. the **input historical capacity series**, and
2. the **simulated sprints-to-done output**.

Good user-facing diagnostics would include:

- “historical story-point capacity: mean 21.4, CV 0.18”;
- “P80 completion: 6 sprints”;
- “10% modeled probability of disrupted sprint, median disruption multiplier 0.72”.

## How to Handle Adjustable Sprint Lengths

Sprints are fixed-length events in Scrum, but the chosen fixed length can differ between teams or scenarios.[^12] The safest implementation is:

1. allow a configured `sprint_length_weeks` as a whole number;
2. normalize historical capacity to weekly rates;
3. aggregate sampled weekly rates back into sprint capacity for the chosen sprint length.

If enough history exists for multiple sprint lengths, a more advanced option is to segment history by sprint length and prefer same-length history before falling back to normalized weekly pooling. That would preserve cadence-specific effects while still supporting scenario analysis.

For delivery-date projection, map sprint counts to dates using sprint boundaries rather than working-day accumulation. However, known calendar effects can still be folded in by scaling future sprint capacity by the ratio of available workdays in that sprint versus nominal workdays, leveraging the same calendar concepts already present in constrained scheduling.[^10][^11]

## How to Treat Partial Work and Carry-Over

There are two distinct ways a task can fail to land in a sprint; they require different modeling treatments.

**Type 1: Capacity-driven deferral.** The task was not pulled into the sprint because there was insufficient remaining capacity to start it. No effort is consumed and no capacity is charged; the task simply waits in the ready queue. This is the case addressed by non-preemptive whole-item pull: if the next ready task does not fit in remaining sprint capacity, it is deferred unchanged.

**Type 2: Execution-driven spill-over.** The task was pulled into the sprint, effort was expended against it, but the work was not completed by sprint end. This is a separate phenomenon: capacity is partially or fully consumed, yet no throughput credit is awarded. The task carries its remaining effort into the next sprint as a reduced-size item.

Atlassian's velocity guidance says only **fully completed** stories count toward sprint velocity.[^13] Both types of carry-over are consistent with that rule: deferred tasks contribute zero to velocity with zero capacity cost; spilled tasks contribute zero to velocity but do carry a capacity cost.

The default for this feature should be **non-preemptive whole-item pull with execution-driven spill-over modeled separately** (see section 6):

- a task that does not fit in remaining capacity is left for a future sprint (Type 1: no capacity consumed);
- a task that is pulled but triggers a spill-over event consumes a sampled fraction of sprint capacity and carries its remaining effort forward as a new, smaller task (Type 2);
- completed tasks are credited to throughput normally.

The two mechanisms combine naturally in the per-iteration algorithm:

1. For each ready task in pull order, if capacity remains for the full task, pull it and check for spill-over using the size-dependent probability model.
2. If a spill-over event fires, charge the consumed fraction, mark the remainder for the next sprint, and continue pulling other tasks with any remaining capacity.
3. If capacity would be exhausted before starting the full task, defer it without charging capacity.
4. At sprint end, compute delivered throughput from fully completed tasks only.

Diagnostics should record, per iteration, both the number of deferred tasks and the total remaining effort from spill-over events, so the aggregate carry-over distribution can be distinguished from capacity-driven deferral in reports.[^10][^13]

## Data Model Recommendation

### New project-file structures

Recommended new models:

- `SprintPlanningSpec`
- `SprintHistoryEntry`
- `SprintVolatilitySpec`
- `SprintSpilloverSpec`
- `SprintCarryoverRecord`
- `SprintPlanningResults`

Suggested fields:

| Model | Fields |
|---|---|
| `SprintPlanningSpec` | `enabled`, `sprint_length_weeks`, `capacity_mode`, `history`, `uncertainty_mode`, `volatility_overlay`, `spillover_config`, `priority_mode`, `service_level_expectation_days` |
| `SprintHistoryEntry` | `end_date?`, `sprint_length_weeks`, `completed_tasks?`, `completed_story_points?`, `team_size?`, `holiday_factor?`, `notes?` |
| `SprintVolatilitySpec` | `enabled`, `disruption_probability`, `multiplier_distribution` |
| `SprintSpilloverSpec` | `enabled`, `model` (`table` or `logistic`), `size_reference_points`, `size_brackets`, `consumed_fraction_alpha`, `consumed_fraction_beta` |
| `SprintCarryoverRecord` | `sprint_number`, `task_id`, `planned_points`, `consumed_fraction`, `remaining_points` |
| `SprintPlanningResults` | `sprint_counts`, `sprint_percentiles`, `date_percentiles`, `capacity_statistics`, `burnup_percentiles`, `carryover_statistics`, `spillover_statistics` |

### Task-level additions

If story-point sprint mode needs to coexist with time-based duration estimates, add a separate optional field such as `planning_story_points` on `Task`. That avoids conflating delivery forecasting units with time-estimation units.[^7][^13]

Optional additions:

- `priority` for pull order within the ready queue,
- `epic` / `milestone` grouping for richer burn-up views,
- `sprint_sized: true/false` to gate task-throughput mode warnings,
- `spillover_probability_override: float` to allow per-task overrides of the size-bracket default when a specific task is known to carry higher execution risk.

## Recommended Internal Component Design

| Component | Responsibility | Likely location |
|---|---|---|
| `SprintCapacitySampler` | Sample per-sprint capacity from history and volatility config | `/Users/joaper/Devel/mcprojsim/src/mcprojsim/planning/sprint_capacity.py` |
| `SprintPlanner` | Build ready queue, pull tasks into sprint buckets, advance dependencies | `/Users/joaper/Devel/mcprojsim/src/mcprojsim/planning/sprint_planner.py` |
| `SprintSimulationEngine` | Run N iterations and produce sprint-count arrays | `/Users/joaper/Devel/mcprojsim/src/mcprojsim/planning/sprint_engine.py` |
| `SprintPlanningResults` | Percentiles, dates, capacity stats, burn-up bands | `/Users/joaper/Devel/mcprojsim/src/mcprojsim/models/sprint_simulation.py` |

This keeps sprint planning modular and avoids destabilizing the current duration-based simulation engine.[^1][^2]

## Integration with Existing `mcprojsim` Concepts

### Reuse what already fits

- Reuse the repository’s Monte Carlo iteration pattern.[^1]
- Reuse the statistics/percentile reporting style.[^2][^9]
- Reuse the project dependency graph and task order.[^8][^10]
- Reuse calendar metadata to adjust future sprint capacity when desired.[^10][^11]

### Do **not** force-fit what does not

- Do not convert hours directly into story points.[^13]
- Do not reuse critical-path elapsed duration as sprint count; sprint planning is a backlog-capacity forecast, not a path-length forecast.[^3]
- Do not assume task-count throughput is valid unless items are right-sized.[^5]

## MVP vs. Follow-On Roadmap

### MVP

1. Add `sprint_planning` project schema.
2. Support `capacity_mode = story_points | tasks`.
3. Implement empirical capacity resampling.
4. Implement dependency-aware sprint pulling with whole-item completion.
5. Report `P50/P80/P90 sprints`, delivery dates, and historical capacity stats.

### Phase 2

1. Add optional volatility/disruption overlay.
2. Add execution-driven spill-over modeling with size-dependent probability and sampled consumed-fraction carry-over (see section 6). Report per-sprint carry-over distribution alongside the main sprints-to-done percentiles.
3. Add calendar-adjusted future sprint capacity.
4. Add burn-up percentile charts by sprint.
5. Add warnings for heterogeneous task sizes in task-throughput mode.

### Phase 3

1. Add parametric capacity models as advanced options.
2. Add scenario analysis for team-size changes.
3. Add support for multiple teams / multiple sprint lanes.

## Why This Is the Best-Fit Approach for `mcprojsim`

This design fits the repository because it preserves the current Monte Carlo style, keeps the existing duration/effort outputs intact, and adds a parallel forecast for sprint cadence rather than trying to reinterpret the current duration arrays.[^1][^2][^3] It is also well grounded in agile practice: Sprints are fixed cadence, velocity/throughput should be based on completed work, and forecasts should reflect observed variation rather than a single mean.[^4][^5][^12][^13]

Most importantly, it answers the actual user problem:

- adjustable sprint length in whole weeks,
- either tasks-per-sprint or story-points-per-sprint capacity,
- explicit uncertainty and volatility handling,
- and a percentile distribution for how many sprints it takes to finish the project.[^4][^5][^6]

## Confidence Assessment

**High confidence**

- `mcprojsim` is already structurally compatible with a sprint Monte Carlo extension because it already samples work stochastically, stores per-iteration outputs, and reports percentile/statistical summaries.[^1][^2]
- An empirical Monte Carlo sprint-capacity model is better founded than an average-velocity model, based on both agile forecasting references and the architecture of the codebase.[^4][^6]
- A dependency-aware sprint pull planner is the right way to model “subset of tasks per sprint” in this repository.[^8][^10]

**Medium confidence**

- Weekly normalization is the best way to support adjustable sprint lengths, but it may underrepresent ceremony/batching effects if a team has only ever worked in one sprint cadence.
- Task-count throughput mode is valuable, but only if tasks are roughly right-sized; some projects in `mcprojsim` may currently define tasks at too coarse a granularity for that to be reliable.[^5][^7]

**Assumptions / inferred design choices**

- I assume sprint planning is intended as an **additional** forecast view, not a replacement for the current duration/effort simulation.
- I assume “subset of tasks” means selecting whole tasks/items into sprints, not simulating arbitrary task fractions.
- I assume the product can introduce one or two new planning-specific fields on tasks if story-point sprint mode must coexist with hour-based duration estimates.

## Footnotes

[^1]: `/Users/joaper/Devel/mcprojsim/src/mcprojsim/simulation/engine.py:28-238` (commit `039b8a48f9730334626dce917d4d068fd85fcc50`)
[^2]: `/Users/joaper/Devel/mcprojsim/src/mcprojsim/models/simulation.py:29-128` and `/Users/joaper/Devel/mcprojsim/src/mcprojsim/models/simulation.py:229-267` (commit `039b8a48f9730334626dce917d4d068fd85fcc50`)
[^3]: `/Users/joaper/Devel/mcprojsim/src/mcprojsim/analysis/staffing.py:1-22` and `/Users/joaper/Devel/mcprojsim/src/mcprojsim/analysis/staffing.py:189-245` (commit `039b8a48f9730334626dce917d4d068fd85fcc50`)
[^4]: `https://www.scrum.org/resources/blog/monte-carlo-forecasting-scrum` (Scrum.org, “Monte Carlo forecasting in Scrum”)
[^5]: `https://www.scrum.org/resources/blog/throughput-driven-sprint-planning` (Scrum.org, “Throughput-Driven Sprint Planning”)
[^6]: `https://blog.leadingedje.com/post/agileforecasting/caseforit.html` (LeadingEDJE, “Agile Forecasting: Monte Carlo Simulations and Flow Metrics”)
[^7]: `/Users/joaper/Devel/mcprojsim/docs/user_guide/task_estimation.md:9-35` and `/Users/joaper/Devel/mcprojsim/src/mcprojsim/models/project.py:40-145` (commit `039b8a48f9730334626dce917d4d068fd85fcc50`)
[^8]: `/Users/joaper/Devel/mcprojsim/src/mcprojsim/simulation/engine.py:260-458` (commit `039b8a48f9730334626dce917d4d068fd85fcc50`)
[^9]: `/Users/joaper/Devel/mcprojsim/src/mcprojsim/analysis/statistics.py:8-67` and `/Users/joaper/Devel/mcprojsim/src/mcprojsim/models/simulation.py:236-247` (commit `039b8a48f9730334626dce917d4d068fd85fcc50`)
[^10]: `/Users/joaper/Devel/mcprojsim/src/mcprojsim/simulation/scheduler.py:12-31` and `/Users/joaper/Devel/mcprojsim/src/mcprojsim/simulation/scheduler.py:141-257` (commit `039b8a48f9730334626dce917d4d068fd85fcc50`)
[^11]: `/Users/joaper/Devel/mcprojsim/docs/user_guide/constrained.md:3-23` and `/Users/joaper/Devel/mcprojsim/docs/user_guide/constrained.md:26-35` (commit `039b8a48f9730334626dce917d4d068fd85fcc50`)
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
- Historical capacity entries that use a different sprint length than the configured sprint length SHALL be normalized to a weekly capacity rate before resampling.

### FR-SP-003: Capacity Planning Units
- The system SHALL support two mutually exclusive capacity modes: `story_points` and `tasks`.
- In `story_points` mode, each task SHALL expose a planning story-point value, either via an existing story-point estimate or a separate `planning_story_points` field on the task, and sprint capacity SHALL be measured in story points.
- In `tasks` mode, each eligible task SHALL count as one unit of work, and sprint capacity SHALL be measured in completed task count.
- The system SHALL warn when `tasks` mode is used and task sizes are heterogeneous, as throughput-based forecasting is only reliable when items are roughly comparable in size.
- The system SHALL NOT silently convert hours-based duration estimates into story points.

### FR-SP-004: Historical Capacity Input
- The system SHALL accept a list of historical sprint capacity observations provided by the user in the project definition file.
- Each history entry SHALL record at minimum the sprint length in weeks and the completed units (story points or tasks) for that sprint.
- History entries MAY optionally record end date, team size, a holiday scaling factor, and free-text notes.
- The system SHALL require at least two historical observations before running a sprint simulation.

### FR-SP-005: Empirical Capacity Resampling
- The default sprint-capacity model SHALL be empirical bootstrap resampling from the provided historical capacity observations.
- The system SHALL normalize history observations to a per-week capacity rate and aggregate sampled weekly rates to match the configured sprint length, so that historical sprints of differing lengths can be used together.
- The system SHALL NOT default to using only the historical mean velocity as the sprint capacity; point-estimate forecasting SHALL NOT be the primary output.

### FR-SP-006: Dependency-Aware Sprint Pull Simulation
- The system SHALL maintain a ready queue of tasks whose declared dependencies have been satisfied in prior sprints.
- In each simulated sprint, the system SHALL pull tasks from the ready queue in priority order until the sampled sprint capacity would be exceeded.
- A task that does not fit within remaining sprint capacity SHALL be deferred to a future sprint without consuming any capacity.
- After each sprint, the system SHALL unlock tasks whose dependencies are now fully satisfied and add them to the ready queue.
- The system SHALL repeat the sprint cycle until all tasks in the project backlog have been completed.
- Each simulation iteration SHALL record the total number of sprints required and the projected completion date.

### FR-SP-007: Sprint Simulation Output and Statistics
- The system SHALL run N iterations of the sprint simulation (using the same configurable iteration count as the existing Monte Carlo engine).
- The system SHALL report P50, P80, and P90 percentiles for the number of sprints required to complete the project.
- The system SHALL report projected delivery dates corresponding to each reported confidence level when a project start date is provided.
- The system SHALL report descriptive statistics for the simulated sprint-count distribution: mean, median, standard deviation, and coefficient of variation.
- The system SHALL report descriptive statistics for the input historical capacity series: mean, median, standard deviation, and coefficient of variation.

### FR-SP-008: Volatility Overlay
- The system SHALL support an optional sprint-level capacity volatility overlay that is disabled by default.
- When enabled, the system SHALL apply a multiplicative disruption factor to sampled sprint capacity with a configurable disruption probability and a configurable impact range.
- The effective sprint capacity SHALL be computed as the product of the resampled historical capacity and the sampled disruption multiplier.
- When no volatility overlay is configured, the multiplier SHALL default to 1.0, preserving the empirical-only behavior.
- The system SHALL support scenario-driven capacity overrides for individual future sprints to model known planned events such as public holidays or team unavailability.

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
- The system SHALL validate that at least two historical capacity entries are provided before accepting the sprint planning configuration.
- The system SHALL validate that all spill-over probability values are in the range [0.0, 1.0].
- The system SHALL validate that the Beta distribution parameters `alpha` and `beta` are both strictly positive.
- Tasks referencing `spillover_probability_override` SHALL fail validation if the value is outside [0.0, 1.0].
- When `capacity_mode` is `story_points`, the system SHALL validate that every task in the project backlog has a resolvable planning story-point value and SHALL report a validation error for any task that does not.

### FR-SP-013: Export and Reporting
- Sprint planning results SHALL be included in JSON and CSV exports when the sprint planning mode is active.
- Sprint planning results SHALL be clearly separated from the existing duration/effort simulation results in all output formats.
- CLI output SHALL indicate whether sprint planning mode was active and summarize the P50/P80/P90 sprint-count results.
- Exports SHALL include the capacity statistics for the input historical series alongside the simulated sprint-count percentiles.
- When the volatility overlay is enabled, exports SHALL report the disruption probability and the simulated disruption frequency observed across iterations.
- When the spill-over model is enabled, exports SHALL include the aggregate spill-over rate and the carry-over distribution summary.

### FR-SP-014: Internal Component Structure
- Sprint planning logic SHALL be implemented in a dedicated `planning/` module to preserve separation of concerns and avoid modifying the existing simulation engine.
- The module SHALL contain at minimum: a `SprintCapacitySampler` for resampling historical capacity, a `SprintPlanner` for managing the ready queue and sprint pulling, a `SprintSimulationEngine` for running N iterations, and a `SprintPlanningResults` model for holding output arrays and statistics.
- The sprint simulation engine SHALL reuse the existing project's random seed mechanism to ensure reproducible results when a seed is configured.