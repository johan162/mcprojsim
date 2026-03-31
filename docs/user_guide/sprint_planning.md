# Sprint planning

Sprint planning adds a second forecasting layer on top of the normal duration simulation.

It is optional.

If your project file does not include a `sprint_planning` section, or if `sprint_planning.enabled` is `false`, `mcprojsim simulate` runs only the standard duration forecast.

The standard simulation answers:

- How long will the project probably take in calendar time and effort?

Sprint planning answers:

- How many sprints will it probably take to finish the current backlog?
- What is a conservative commitment level for the next sprint?
- How much spillover, scope churn, and sprint-to-sprint disruption should we expect?

This chapter introduces sprint planning gradually:

1. what it models
2. what input it needs
3. the smallest working file
4. richer fields for more realistic forecasting
5. how to generate these files from natural language
6. how external CSV and JSON history files work
7. how to interpret the output

## What sprint planning models

Sprint planning is built on real historical sprint outcomes. Instead of asking you to guess an abstract team velocity, MCProjSim samples from past sprint results and projects those patterns forward.

The model works with one of two capacity units:

- `story_points`: forecast completion based on historical delivered story points
- `tasks`: forecast completion based on historical completed task counts

From your sprint history it models these signals:

- completed work: how many story points or tasks were actually delivered
- spillover: work that was started but carried into a later sprint
- scope added: new work introduced during a sprint
- scope removed: work taken out during a sprint
- holiday factor: reduced effective capacity for a historical sprint
- future overrides: explicit planned reductions or increases for known upcoming sprints
- volatility: random sprint-level disruption, such as support load or incident response

Optional task-level spillover modeling can also simulate the case where a pulled item is only partially finished and returns as carryover into the next sprint.

## What input is required

To run sprint planning you need three things:

1. A normal project file with `project` and `tasks`
2. A `sprint_planning` section with a sprint length and capacity mode
3. At least two usable historical sprint observations with positive delivery signal

There is no separate sprint-planning CLI command. Sprint planning is activated during `mcprojsim simulate` when the project file contains `sprint_planning.enabled: true`.

You can define company-wide sprint defaults in `config.yaml` under `sprint_defaults` (for example sickness probabilities, velocity model, and planning confidence). When a project relies on built-in sprint defaults, `mcprojsim` applies values from `sprint_defaults`.

## Sprint setting precedence

When multiple sources define sprint-planning behavior, `mcprojsim` resolves values in this order (highest to lowest priority):

1. CLI flags
2. Project `sprint_planning` fields
3. Global `sprint_defaults` in `config.yaml`
4. Built-in defaults

Examples:

- `--velocity-model` overrides both project and config values
- a value set in project `sprint_planning` overrides `sprint_defaults`
- `sprint_defaults` provides company-wide defaults when project fields are not explicitly set

A historical row is usable when all of the following are true:

- it uses the correct unit family for the selected `capacity_mode`
- it includes exactly one delivery field: `completed_story_points` or `completed_tasks`
- its effective delivery signal is positive

In plain language, positive delivery signal means the sprint delivered or carried some work. The implementation counts this as:

- `completed_story_points + spillover_story_points > 0` in `story_points` mode
- `completed_tasks + spillover_tasks > 0` in `tasks` mode

There are a few important rules:

- In `story_points` mode, every task must have a resolvable story-point size. You can provide it either as `estimate.story_points` or as `planning_story_points`.
- In `tasks` mode, the backlog is forecast in item counts instead of points. This works best when tasks are roughly similar in size.
- If sprint spillover modeling is enabled, every task must have a resolvable story-point size, even if capacity mode is not `story_points`.

## Command workflow

Sprint planning uses the same CLI flow as the rest of the tool:

```bash
mcprojsim validate project.yaml
mcprojsim simulate project.yaml --seed 42 --iterations 10000
```

The important detail is that `simulate` is still the command that produces sprint-planning results. There is no separate `mcprojsim sprint-plan` command.

Typical workflow:

1. write the project YAML or TOML by hand, or generate it from natural language
2. validate it
3. run the simulation
4. inspect both the normal duration forecast and the sprint-planning summary

For example:

```bash
mcprojsim validate sprint_project.yaml
mcprojsim simulate sprint_project.yaml --seed 42 --iterations 10000
mcprojsim simulate sprint_project.yaml --seed 42 --iterations 10000 --table
mcprojsim simulate sprint_project.yaml --seed 42 --iterations 10000 --velocity-model neg_binomial
```

Sprint-planning flags that matter most in practice:

- `--velocity-model empirical|neg_binomial` overrides the project file velocity model for the current run
- `--no-sickness` disables sprint sickness modeling without editing the project file
- `--minimal` keeps the CLI output short and suppresses the detailed diagnostic sections
- `--table` formats the sprint summary and confidence intervals as ASCII tables
- `--output-format json,html,csv` writes export files in addition to CLI output
- `--include-historic-base` adds the historic baseline section to HTML and JSON exports when sprint history is available

Example export workflow:

```bash
mcprojsim simulate sprint_project.yaml \
  --seed 42 \
  --output out/sprint_forecast \
  --output-format json,html \
  --include-historic-base
```

Important export rule:

- `--include-historic-base` only works when `--output-format` includes `json` or `html`
- unsupported `--output-format` values now fail fast instead of being ignored

See [Running Simulations](running_simulations.md) for the full command reference.

## Build up the file gradually

### Step 1: start from a normal project file

Sprint planning does not replace the normal project definition. It extends it.

```yaml
project:
  name: "Website refresh"
  start_date: "2026-05-04"

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
```

At this point the file is valid for normal Monte Carlo simulation, but it does not yet contain any sprint-planning forecast.

That is the default and optional case: a standard project file without `sprint_planning` is still fully valid.

### Step 2: add the smallest useful `sprint_planning` section

Now add the sprint cadence, the unit family, and at least two historical sprint rows.

```yaml
project:
  name: "Website refresh"
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
  history:
    - sprint_id: "SPR-001"
      completed_story_points: 10
    - sprint_id: "SPR-002"
      completed_story_points: 9
```

This is the smallest practical setup:

- `enabled: true` turns sprint planning on
- `sprint_length_weeks: 2` says one sprint is two weeks long
- `capacity_mode: story_points` means backlog is measured in story points
- `history` supplies the real sprint outcomes the model will resample

### Step 3: add richer historical signals

The next improvement is to capture spillover and scope churn explicitly.

```yaml
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

This gives the simulation more behavioral information:

- `spillover_story_points` records started-but-not-finished work
- `added_story_points` records scope growth during a sprint
- `removed_story_points` records scope removed during a sprint
- `planning_confidence_level` controls how conservative the guidance should be

### Step 4: add forward-looking adjustments

Once the basic history is working, you can model upcoming known events and optional spillover/disruption behavior.

```yaml
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

At this stage the forecast can answer more realistic planning questions:

- what if sprint 2 will have reduced capacity?
- what if summer vacations affect a later sprint?
- what if some sprints are randomly disrupted?
- what if larger items often spill over?

## Built on historical real data

Sprint planning is intentionally empirical.

The model does not require you to declare a fixed team velocity like "10 points per sprint". Instead, it uses your actual sprint history and samples from it.

Each historical row describes what really happened in one sprint:

- delivered work
- spillover
- scope change
- optional holiday reduction

That means the forecast learns from the behavior of the team and the backlog as they were actually executed.

If your team historically delivers 9 to 12 points with occasional spillover and moderate churn, the model will project a future distribution consistent with those observations.

If the team changes substantially, the input history should change too. The forecast is only as representative as the data you feed it.

## All sprint-planning fields

This section is a full field reference for sprint planning and the task fields it depends on.

### Task-level fields used by sprint planning

| Field | Location | Default | Explanation |
|---|---|---:|---|
| `estimate.story_points` | `tasks[].estimate` | none | Story-point size used directly for story-point planning when present |
| `planning_story_points` | `tasks[]` | omitted | Optional explicit planning size. Overrides `estimate.story_points` for sprint planning only |
| `priority` | `tasks[]` | omitted | Lower values are pulled earlier when several tasks are ready in the same sprint |
| `spillover_probability_override` | `tasks[]` | omitted | Per-task override for spillover probability when spillover modeling is enabled |

### `sprint_planning` fields

| Field | Default if omitted | Explanation |
|---|---:|---|
| `enabled` | `false` | Enables sprint-planning simulation and reporting |
| `sprint_length_weeks` | none | Required sprint cadence in weeks |
| `capacity_mode` | none | Required. Either `story_points` or `tasks` |
| `history` | `[]` | Historical sprint observations. If `enabled` is true, at least two usable rows are required |
| `planning_confidence_level` | `0.80` | Confidence level used for commitment guidance and conservative heuristics |
| `removed_work_treatment` | `churn_only` | Whether removed work is tracked only as churn or also reduces remaining backlog |
| `future_sprint_overrides` | `[]` | Explicit adjustments for specific future sprints |
| `volatility_overlay` | default object | Optional random disruption model applied on top of sampled historical capacity |
| `spillover` | default object | Optional task-level spillover model |
| `velocity_model` | `empirical` | How future sprint velocity is sampled. Either `empirical` (resample historical rows) or `neg_binomial` (fit a Negative Binomial distribution to history) |
| `sickness` | default object | Optional per-person sickness-absence model that reduces sprint capacity stochastically |

### `sprint_planning.history[]` fields

| Field | Default if omitted | Explanation |
|---|---:|---|
| `sprint_id` | none | Required unique sprint identifier |
| `sprint_length_weeks` | inherited from `sprint_planning.sprint_length_weeks` | Historical sprint length. Useful when your old data mixes cadences |
| `completed_story_points` | none | Required in `story_points` mode |
| `completed_tasks` | none | Required in `tasks` mode |
| `spillover_story_points` | `0` | Carryover in story points |
| `spillover_tasks` | `0` | Carryover in tasks |
| `added_story_points` | `0` | Scope added during the sprint |
| `added_tasks` | `0` | Scope added during the sprint |
| `removed_story_points` | `0` | Scope removed during the sprint |
| `removed_tasks` | `0` | Scope removed during the sprint |
| `holiday_factor` | `1.0` | Historical effective-capacity multiplier. Use values below `1.0` for reduced-capacity sprints |
| `end_date` | omitted | Optional metadata only |
| `team_size` | omitted | Optional metadata only |
| `notes` | omitted | Optional metadata only |

### External `sprint_planning.history` descriptor fields

When you keep sprint history in a separate file, `history` is not a list of rows in the project file. Instead it becomes a small descriptor object with these fields:

| Field | Default if omitted | Explanation |
|---|---:|---|
| `format` | none | Required external history format. Supported values are `json` and `csv` |
| `path` | none | Required path to the external history file. Relative paths are resolved from the project file location |

### `future_sprint_overrides[]` fields

| Field | Default if omitted | Explanation |
|---|---:|---|
| `sprint_number` | omitted | Optional future sprint locator by number |
| `start_date` | omitted | Optional future sprint locator by boundary date |
| `holiday_factor` | `1.0` | Capacity multiplier for that future sprint |
| `capacity_multiplier` | `1.0` | Additional explicit multiplier for that future sprint |
| `notes` | omitted | Optional descriptive text |

Notes:

- At least one of `sprint_number` or `start_date` must be present.
- If both are present, they must point to the same future sprint.
- `start_date` must align to a sprint boundary derived from `project.start_date` and `sprint_length_weeks`.
- The effective multiplier for a future sprint is `holiday_factor × capacity_multiplier`. Both are combined multiplicatively.

Validation rules:

- `future_sprint_overrides` must be a list of objects
- each override must resolve to exactly one simulated future sprint
- two overrides must not target the same sprint after resolution
- `sprint_number` must be a positive integer
- `start_date` must be a valid ISO date in `YYYY-MM-DD` format
- `holiday_factor` and `capacity_multiplier` must both be greater than `0`
- use `holiday_factor` for known calendar reduction, `capacity_multiplier` for any additional explicit adjustment, or combine both when needed

### `volatility_overlay` fields

| Field | Default if omitted | Explanation |
|---|---:|---|
| `enabled` | `false` | Enables sprint-level disruption sampling |
| `disruption_probability` | `0.0` | Probability that a given sprint is disrupted |
| `disruption_multiplier_low` | `1.0` | Lower bound of the disruption multiplier |
| `disruption_multiplier_expected` | `1.0` | Most likely disruption multiplier |
| `disruption_multiplier_high` | `1.0` | Upper bound of the disruption multiplier |

The multipliers must satisfy `low <= expected <= high`.

### `spillover` fields

| Field | Default if omitted | Explanation |
|---|---:|---|
| `enabled` | `false` | Enables task-level spillover simulation |
| `model` | `table` | Spillover probability model. Either `table` or `logistic` |
| `size_reference_points` | `5.0` | Reference point scale used by the logistic model |
| `size_brackets` | built-in defaults | Table-model mapping from item size to spillover probability |
| `consumed_fraction_alpha` | `3.25` | Alpha parameter of the beta distribution for consumed fraction |
| `consumed_fraction_beta` | `1.75` | Beta parameter of the beta distribution for consumed fraction |
| `logistic_slope` | `1.9` | Logistic model slope |
| `logistic_intercept` | `-1.9924301646902063` | Logistic model intercept |

### `spillover.size_brackets[]` fields

| Field | Default if omitted | Explanation |
|---|---:|---|
| `max_points` | omitted | Inclusive upper bound of the bracket. Omit on the last row for the unbounded catch-all bracket |
| `probability` | none | Spillover probability for items in that bracket |

Built-in default brackets:

| `max_points` | `probability` |
|---:|---:|
| `2.0` | `0.05` |
| `5.0` | `0.12` |
| `8.0` | `0.25` |
| omitted | `0.40` |

### `sickness` fields

| Field | Default if omitted | Explanation |
|---|---:|---|
| `enabled` | `false` | Enable per-person sickness absence modeling |
| `team_size` | project `team_size` | Number of team members. Falls back to the top-level project `team_size` if omitted |
| `probability_per_person_per_week` | `0.058` | Probability that any one person starts a sickness episode in a given week |
| `duration_log_mu` | `0.693` | $\mu$ of the LogNormal duration distribution (log-scale). Default gives a median of 2 days. **Shared with constrained scheduling.** |
| `duration_log_sigma` | `0.75` | $\sigma$ of the LogNormal duration distribution (log-scale). Default gives mean ≈ 2.6 days, P90 ≈ 5.5 days. **Shared with constrained scheduling.** |

## How the simulation uses these fields

Once the input is loaded, the simulation uses the fields in this order:

1. normalize historical rows
2. choose the correct unit family (`story_points` or `tasks`)
3. sample future sprint outcomes from history
4. apply volatility, future overrides, and sickness multiplier
5. plan ready backlog items into each sprint
6. optionally create spillover remainder items
7. repeat until the backlog is done

More concretely:

- `holiday_factor` normalizes historical completed and spillover work to an equivalent full-capacity sprint before resampling
- `future_sprint_overrides` scale future sampled capacity for specific sprints
- when sickness modeling is enabled, a per-sprint sickness multiplier reduces capacity based on simulated team absences (duration parameters are shared with constrained scheduling, if both are used)
- `removed_work_treatment: churn_only` records removed work as churn but does not shrink the remaining backlog
- `removed_work_treatment: reduce_backlog` subtracts removed work from the remaining backlog
- `priority` affects which ready tasks are pulled first
- `spillover_probability_override` replaces the configured spillover model for one task

If `sprint_planning` is absent or disabled, none of these sprint-specific steps run and the tool falls back to the standard project duration simulation only.

## Statistical methods in detail

The sprint-planning forecast uses a small number of explicit statistical building blocks. Some quantities are sampled from named probability distributions. Others are sampled directly from the empirical historical data without fitting a parametric family.

The important distinction is:

- historical sprint capacity is modeled empirically from your past data
- disruption and spillover behavior use explicit probability distributions or deterministic probability formulas
- the final sprint-count forecast is the Monte Carlo output distribution produced by repeatedly simulating the backlog to completion

### Step 1: normalize the historical data

Before sampling, each sprint-history row is converted into a canonical internal row:

- `completed_units`
- `spillover_units`
- `added_units`
- `removed_units`
- `sprint_length_weeks`

The chosen unit family depends on `capacity_mode`:

- in `story_points` mode, the row uses the story-point fields
- in `tasks` mode, the row uses the task-count fields

Historical `holiday_factor` is then used to normalize delivered and spillover work to an equivalent full-capacity sprint:

$$
  \text{normalized completed} = \frac{\text{completed}}{\text{holiday factor}}
$$

$$
  \text{normalized spillover} = \frac{\text{spillover}}{\text{holiday factor}}
$$

This means a sprint with reduced availability is not treated as evidence that the team permanently has lower underlying capacity.

### Step 2: build the sampling distribution from history

The default velocity model is `empirical`.

For sprint capacity itself, the default implementation does not fit a Normal, Lognormal, Gamma, or any other named parametric distribution.

Instead, it uses an empirical discrete distribution over the normalized historical rows.

In practice that means:

- every usable historical row is one possible future sprint outcome
- each row has equal probability mass
- one row is sampled uniformly at random with replacement for each simulated sprint

So if the normalized completed capacities in your history are `[8, 10, 12]`, the model for a future sprint's nominal velocity is an empirical discrete distribution supported exactly on those values, each with probability $1/3$.

This approach has two important consequences:

- no distribution parameters such as mean/variance are estimated and then fed into a fitted curve for sprint velocity
- the observed joint behavior inside a historical row is preserved

That second point matters. When a row is sampled, its `completed_units`, `spillover_units`, `added_units`, and `removed_units` travel together. If historically high-delivery sprints also tended to have low spillover, that empirical relationship remains present in the sampled rows.

### Step 2b: Negative Binomial velocity model (optional)

When `velocity_model` is set to `neg_binomial`, the engine fits a Negative Binomial distribution to the normalized completed-units history using method-of-moments estimation.

The Negative Binomial (NB) provides a smooth parametric model for count-like sprint velocity data that naturally accounts for overdispersion — situations where the variance of historical velocity exceeds the mean.

**Parameter estimation:**

The engine computes the sample mean $\mu$ and sample variance $s^2$ of the normalized completed-units from the diagnostic rows, then derives:

$$
k = \frac{\mu^2}{s^2 - \mu}
$$

where $k$ is the dispersion parameter. If $s^2 \le \mu$ (no overdispersion), $k$ is treated as infinite and the distribution falls back to a Poisson model.

**Sampling:**

For each simulated sprint, the engine draws a completed-units value from:

$$
\text{completed} \sim \text{NegBinomial}\left(k, \; \frac{k}{k + \mu}\right)
$$

This distribution has mean $\mu$ and variance $\mu + \mu^2 / k$.

When $k$ is infinite (Poisson fallback), the draw is from $\text{Poisson}(\mu)$ instead.

Spillover, added scope, and removed scope are still sampled empirically from a random historical row for each sprint. That means the NB model changes only how velocity is generated — churn behavior continues to reflect observed historical patterns.

**When to use each model:**

- Use `empirical` (the default) when you have moderate history and want the forecast to reflect exact observed delivery patterns, including correlations between velocity and churn.
- Use `neg_binomial` when you want a smooth parametric velocity model, for example when you have enough history that the observed values look overdispersed and you want the simulation to interpolate between observed outcomes rather than only replaying them.

**Example:**

```yaml
sprint_planning:
  enabled: true
  sprint_length_weeks: 2
  capacity_mode: story_points
  velocity_model: neg_binomial
  history:
    - sprint_id: "SPR-001"
      completed_story_points: 10
      spillover_story_points: 1
    - sprint_id: "SPR-002"
      completed_story_points: 9
      spillover_story_points: 2
      added_story_points: 1
    - sprint_id: "SPR-003"
      completed_story_points: 14
      spillover_story_points: 1
    - sprint_id: "SPR-004"
      completed_story_points: 8
      spillover_story_points: 3
    - sprint_id: "SPR-005"
      completed_story_points: 12
```

The CLI flag `--velocity-model neg_binomial` can also override the project file setting without editing the YAML:

```bash
mcprojsim simulate sprint_project.yaml --seed 42 --velocity-model neg_binomial
```

The output summary will show the fitted NB parameters:

```text
Velocity Model: neg_binomial
NB mu: 10.6000
NB dispersion k: 18.7333
```

### Step 3: cadence matching and weekly fallback

The engine first tries to sample from historical rows whose `sprint_length_weeks` exactly match the requested future cadence.

That is the normal case.

If no rows match the requested cadence, the engine falls back to weekly normalization:

1. each historical row is converted into a one-week rate by dividing by its sprint length
2. the simulation samples one weekly row per future week
3. those weekly samples are summed to form the future sprint outcome

Statistically, that fallback is a sum of independent draws from the empirical weekly-rate distribution. It is still empirical, but now at the weekly level rather than at the full-sprint level.

### Which distributions are used for which quantities

The table below lists the actual modeling family used by each entity.

| Quantity | Source | Distribution / model used |
|---|---|---|
| Nominal sprint velocity (`completed_units`) | historical rows | Empirical discrete distribution over normalized historical rows (default), or Negative Binomial distribution fitted by method of moments when `velocity_model: neg_binomial` |
| Historical spillover units in sampled sprint outcome | historical rows | Empirical discrete distribution, sampled jointly with the same historical row as velocity (empirical model) or from a random historical row (NB model) |
| Historical scope added units | historical rows | Empirical discrete distribution, sampled jointly with the same historical row |
| Historical scope removed units | historical rows | Empirical discrete distribution, sampled jointly with the same historical row |
| Future override effect | `future_sprint_overrides` | Deterministic multiplier, no random distribution |
| Whether a sprint disruption occurs | `volatility_overlay.disruption_probability` | Bernoulli trial with probability $p$ |
| Disruption multiplier given a disruption | `volatility_overlay` multipliers | Triangular distribution |
| Number of people falling sick per week | `sickness.probability_per_person_per_week`, `sickness.team_size` | Binomial($n$, $p$) per sprint week where $n$ = team size, $p$ = weekly probability |
| Days lost per sickness event | `sickness.duration_log_mu`, `sickness.duration_log_sigma` | LogNormal($\mu$, $\sigma$) capped at remaining sprint working days |
| Spillover probability in `table` mode | `spillover.size_brackets` | Deterministic step function by story-point size |
| Spillover probability in `logistic` mode | `spillover` logistic fields | Logistic probability curve over story-point size |
| Whether a pulled item spills over | spillover probability | Bernoulli trial with item-specific probability $p_i$ |
| Fraction of a spilled item completed before carryover | `consumed_fraction_alpha`, `consumed_fraction_beta` | Beta distribution |
| Final sprint-count forecast | full Monte Carlo simulation | Empirical Monte Carlo output distribution over iterations |

### Detailed interpretation by entity

#### Sprint velocity

For a particular future sprint, nominal velocity is the sampled `completed_units` from one historical row (empirical model) or drawn from the fitted Negative Binomial distribution (NB model).

- In `story_points` mode, this is a story-point velocity.
- In `tasks` mode, this is a throughput count.

With the default `empirical` model, this is a discrete distribution based on the normalized history. With the `neg_binomial` model, the distribution is parametric with mean and dispersion estimated from history.

If volatility, future overrides, or sickness modeling are enabled, the effective velocity becomes:

$$
  \text{effective velocity} = \text{nominal velocity} \times \text{volatility multiplier} \times \text{future override multiplier} \times \text{sickness multiplier}
$$

#### Spillover, added scope, and removed scope at the sprint level

In the empirical model, these are sampled from the same historical row as velocity, not independently from separate fitted distributions. That preserves empirical row-level dependence between these quantities.

In the `neg_binomial` model, velocity is drawn from the fitted NB distribution. Spillover, added scope, and removed scope are then drawn from a randomly selected historical row, independently of the velocity draw. This breaks the joint row-level correlation but produces smooth parametric velocity variation.

#### Disruption frequency and impact

The volatility overlay is a two-stage model:

1. sample whether disruption happens using a Bernoulli trial with probability `disruption_probability`
2. if disruption occurs, sample the multiplicative impact from a triangular distribution with:

- lower bound = `disruption_multiplier_low`
- mode = `disruption_multiplier_expected`
- upper bound = `disruption_multiplier_high`

If all three multipliers are equal, the impact becomes deterministic.

#### Sickness absence

The sickness model is a two-stage per-person simulation that runs once per simulated sprint:

1. **Occurrence stage.** For each week in the sprint, draw the number of new sickness events from a Binomial distribution:

    $$
    \text{sick\_count}_w \sim \text{Binomial}(n, \, p)
    $$

    where $n$ is the team size and $p$ is `probability_per_person_per_week`.

2. **Duration stage.** For each sickness event, draw the duration from a LogNormal distribution:

    $$
    d_i \sim \text{LogNormal}(\mu, \, \sigma)
    $$

    Each draw is capped at the number of working days remaining in the sprint.

3. **Capacity multiplier.** Total lost days are summed and converted to a fractional multiplier:

    $$
    \text{sickness multiplier} = \max\!\left(0, \; 1 - \frac{\sum d_i}{n \times w \times 5}\right)
    $$

    where $w$ is `sprint_length_weeks` and 5 is the assumed working days per week.

This multiplier is applied multiplicatively alongside the volatility and future-override multipliers.

**Default calibration and EU/OECD motivation.**
The three default parameters are derived from published European and OECD labour-market statistics:

- The average EU worker takes roughly **7–8 sick days per year** (Eurostat, *Absence from work* data, 2019–2023;  OECD, *Health at a Glance*, 2023).
- Those days arise from approximately **3 sickness episodes per year** (Eurofound, *Sixth European Working Conditions Survey*, 2015; UK ONS, *Sickness absence in the labour market*, 2024).
- Across EU-27, average sickness-absence rates cluster around **2.5–3.8 %** of scheduled working days (Eurostat, table `hsw_abs_typ`, 2019–2022).

Converting to per-week parameters:

| Parameter | Value | Derivation |
|---|---:|---|
| `probability_per_person_per_week` | 0.058 | $3 \text{ episodes/year} \div 52 \text{ weeks} \approx 0.058$ |
| `duration_log_mu` | 0.693 | $\ln(2)$, giving a median duration of **2 working days** |
| `duration_log_sigma` | 0.75 | Produces mean ≈ 2.6 days, P90 ≈ 5.5 days, consistent with the right-skewed shape of sickness-duration data |

With these defaults and a team of 6 over a 2-week sprint, the expected capacity loss per sprint is roughly **2–4 %**, consistent with the EU-27 aggregate sickness-absence rate.

You can override any of these parameters to match your team's or region's reality.

**Example:**

```yaml
project:
  name: "Sprint with sickness"
  team_size: 6

sprint_planning:
  enabled: true
  sprint_length_weeks: 2
  capacity_mode: story_points
  sickness:
    enabled: true
    # team_size falls back to project.team_size (6) if not set here
  history:
    - sprint_id: "S1"
      completed_story_points: 10
    - sprint_id: "S2"
      completed_story_points: 12
    - sprint_id: "S3"
      completed_story_points: 9
```

To disable sickness from the CLI without editing the file:

```bash
mcprojsim simulate project.yaml --seed 42 --no-sickness
```

#### Item spillover

Item spillover is also a two-stage model:

1. compute the spillover probability for the item
2. if spillover occurs, sample the consumed fraction from a Beta distribution

The spillover probability $p_i$ is determined in this order:

1. `spillover_probability_override` on the task, if present
2. otherwise the configured global spillover model

The global model can be:

- `table`: a deterministic lookup based on the item's planning story points
- `logistic`: a logistic curve

Logistic mode uses exactly this sequence:

1. compute scaled points with a lower clamp:

$$
z = \max\!\left(\frac{x}{r}, 10^{-6}\right)
$$

2. compute the logit value:

$$
\ell = s \cdot \ln(z) + b
$$

3. convert to probability:

$$
p_i = \frac{1}{1 + e^{-\ell}}
$$

where:

- $x$ is the item's planning story points
- $r$ is `size_reference_points`
- $s$ is `logistic_slope`
- $b$ is `logistic_intercept`

The clamp on $z$ is important: it prevents invalid $\ln(0)$ or negative-log inputs when very small values appear.

For the logistic model, the probability is:

$$
p_i = \frac{1}{1 + e^{-\left(s \cdot \ln(x / r) + b\right)}}
$$

where:

- $x$ is the item's planning story points
- $r$ is `size_reference_points`
- $s$ is `logistic_slope`
- $b$ is `logistic_intercept`

Interpretation of slope and intercept:

- `logistic_slope` controls sensitivity to item size in log-space. Larger values make probability rise faster as $x$ increases.
- `logistic_intercept` shifts the curve up or down. At the reference size ($x=r$), the probability is:

$$
p(x=r) = \frac{1}{1 + e^{-b}}
$$

With the built-in defaults ($s=1.9$, $b=-1.9924301646902063$), this baseline is approximately 0.12.

If spillover occurs, the completed fraction is sampled from:

$$
  \text{Beta}(\alpha, \beta)
$$

with:

- $\alpha$ = `consumed_fraction_alpha`
- $\beta$ = `consumed_fraction_beta`

Then the sampled fraction is clamped to:

$$
  \text{consumed fraction} \in [10^{-6}, 0.999999]
$$

This guarantees both consumed and remaining work are strictly positive in the spillover branch.

The remaining fraction becomes carryover into the next sprint.

In implementation terms, if an item with size $u$ spills over:

$$
u_{\text{consumed}} = u \cdot f
$$

$$
u_{\text{remaining}} = u \cdot (1-f)
$$

where $f$ is the clamped Beta sample. If $u_{\text{remaining}} \le 10^{-9}$, no carryover item is created.

How `consumed_fraction_alpha` and `consumed_fraction_beta` affect behavior:

- Mean consumed fraction:

$$
\mathbb{E}[f] = \frac{\alpha}{\alpha + \beta}
$$

- Variance:

$$
\mathrm{Var}(f) = \frac{\alpha\beta}{(\alpha+\beta)^2(\alpha+\beta+1)}
$$

Interpretation:

- higher `consumed_fraction_alpha` shifts spillover events toward "mostly completed before carryover"
- higher `consumed_fraction_beta` shifts spillover events toward "mostly carried over"
- larger values of both parameters (with similar ratio) produce tighter clustering around the mean

With built-in defaults (`alpha=3.25`, `beta=1.75`):

$$
\mathbb{E}[f] = \frac{3.25}{3.25+1.75} = 0.65
$$

So, on average, a spillover event consumes about 65% of an item and carries about 35% into the next sprint (before clamping and tiny-remainder guard).

Spillover itself is a Bernoulli event using the computed probability $p_i$: if a uniform draw is below $p_i$, spillover happens; otherwise the item completes normally.

### What is estimated from history, and what is configured directly

This is the practical summary:

Estimated from historical data:

- empirical sprint velocity distribution (empirical model), or Negative Binomial mu and dispersion k (NB model)
- empirical spillover-unit distribution at sprint level
- empirical scope-added distribution
- empirical scope-removed distribution
- empirical correlations between those sprint-level quantities, because they are sampled as whole rows (empirical model only; the NB model samples churn independently)

Configured directly by the user rather than estimated from history:

- velocity model choice (`empirical` or `neg_binomial`)
- sickness absence parameters (probability, duration distribution, team size)
- volatility probability and triangular multiplier bounds
- future sprint override multipliers
- spillover probability table or logistic curve parameters
- beta-distribution parameters for partial completion of spilled items

So the historical data primarily determines the sprint-level capacity and churn distribution, while the optional advanced controls determine how that empirically sampled capacity is adjusted or how individual items may fragment across sprints.

### Percentiles and final forecast distribution

After many Monte Carlo iterations, the engine does not fit a named distribution to the resulting sprint counts. Instead it stores the simulated sprint counts directly and computes empirical percentiles such as P50, P80, and P90 from those samples.

- P50 is the median forecast
- P80 is a more conservative delivery target
- P90 is more conservative still

The same idea applies to the burn-up traces and to the displayed summary statistics.

### Burn-up percentiles

The engine records a cumulative delivery trace for each Monte Carlo iteration. After all iterations are complete, these traces are aligned by sprint number and summarized as percentile bands (P50, P80, P90) at each sprint boundary.

The result is a burn-up chart in tabular form: for each sprint, you can see the median cumulative delivery and the more conservative estimates. This lets you answer questions like "by sprint 3, how much work is likely to be done?" without committing to a single deterministic plan.

### Commitment guidance heuristic

The planned commitment guidance combines historical delivery and churn behavior at the configured confidence level.

The implementation first computes historical ratio series such as:

- spillover ratio = `spillover / (completed + spillover)`
- removal ratio = `removed / (completed + spillover + removed)`

It then combines historical percentiles into a conservative planning heuristic.

For confidence level $q$, the current implementation is approximately:

$$
  \text{guidance} = P50(\text{completed}) \times \left(1 - P_q(\text{spillover ratio})\right) \times \left(1 - P_q(\text{removal ratio})\right) - P_q(\text{scope added})
$$

This produces a conservative "what should we plan for" number in the current capacity unit.

It is important to read this as a heuristic derived from historical percentiles, not as the mean of a fitted probability distribution.

## Natural-language generation

You do not have to hand-write the YAML from scratch. The local `generate` command can create a sprint-planning project file from semi-structured text.

This is also optional. You can:

- write sprint-planning YAML or TOML by hand
- generate a starting file with `mcprojsim generate`
- skip sprint planning entirely and use only the normal project simulation

### Example 1: story-point-based sprint planning

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

Command:

```bash
mcprojsim generate sprint_description.txt -o sprint_project.yaml
```

Typical generated YAML:

```yaml
project:
  name: "Sprint Planning from Text"
  start_date: "2026-05-04"
  confidence_levels: [50, 80, 90, 95]

tasks:
  - id: "task_001"
    name: "Discovery"
    estimate:
      story_points: 3
    dependencies: []

  - id: "task_002"
    name: "API implementation"
    estimate:
      story_points: 5
    dependencies: []

sprint_planning:
  enabled: true
  sprint_length_weeks: 2
  capacity_mode: "story_points"
  planning_confidence_level: 0.8
  history:
    - sprint_id: "SPR-001"
      completed_story_points: 10
      spillover_story_points: 1
```

### Example 2: task-count throughput mode

```text
Project: Maintenance Queue
Start date: 2026-05-04
Task 1:
- Fix login issue
- Size: S
Task 2:
- Improve audit logs
- Size: S
Task 3:
- Add export endpoint
- Size: S
Sprint planning:
- Sprint length: 1
- Capacity mode: tasks
Sprint history S1:
- Done: 4 tasks
- Carryover: 1 tasks
Sprint history S2:
- Done: 5 tasks
```

Use `tasks` mode only when backlog items are roughly comparable. If task sizes vary a lot, story points usually give a more stable forecast.

The CLI will print a warning if it detects heterogeneous task sizes in `tasks` mode. For example:

```text
Warning: Sprint planning is using 'tasks' capacity mode, but task
planning sizes are heterogeneous. Throughput-based forecasting is
most reliable when items are roughly comparable in size.
```

### Example 3: include holiday effects in the text description

```text
Project: Summer Release
Start date: 2026-06-01
Task 1:
- Release prep
- Story points: 5
Sprint planning:
- Sprint length: 2
- Capacity mode: story points
Sprint history SPR-001:
- Done: 12 points
- Holiday factor: 90%
Sprint history SPR-002:
- Done: 9 points
- Carryover: 2 points
```

## Using external CSV or JSON history files

Inline history is convenient for short examples. For real teams, history often lives better in a separate data file.

The project file can point to external sprint history like this:

```yaml
sprint_planning:
  enabled: true
  sprint_length_weeks: 2
  capacity_mode: story_points
  history:
    format: json
    path: sprint_history.json
```

Or in TOML:

```toml
[sprint_planning]
enabled = true
sprint_length_weeks = 2
capacity_mode = "story_points"

[sprint_planning.history]
format = "csv"
path = "sprint_history.csv"
```

Supported formats:

- `json`
- `csv`

The history path may be relative. Relative paths are resolved from the project file location.

### JSON example

```json
{
  "metricDefinitions": {
    "committed_StoryPoints": "Sum of story points at sprint start",
    "completed_StoryPoints": "Sum of story points completed in sprint"
  },
  "sprints": [
    {
      "sprintUniqueID": "SPR-001",
      "startDate": "2026-01-01T09:00:00.000+01:00",
      "endDate": "2026-01-15T09:00:00.000+01:00",
      "metrics": {
        "committed_StoryPoints": 12,
        "completed_StoryPoints": 8,
        "spilledOver_StoryPoints": 1
      }
    },
    {
      "sprintUniqueID": "SPR-002",
      "endDate": "2026-01-29T09:00:00.000+01:00",
      "metrics": {
        "committed_StoryPoints": 14,
        "completed_StoryPoints": 10,
        "addedIntraSprint_StoryPoints": 2
      }
    }
  ]
}
```

### CSV example

```csv
sprintUniqueID,committed_StoryPoints,completed_StoryPoints,addedIntraSprint_StoryPoints,removedInSprint_StoryPoints,spilledOver_StoryPoints,startDate,endDate
SPR-001,12,8,0,0,1,2026-01-01T09:00:00.000+01:00,2026-01-15T09:00:00.000+01:00
SPR-002,14,10,2,0,0,2026-01-15T09:00:00.000+01:00,2026-01-29T09:00:00.000+01:00
```

The external file is loaded before validation, so the same schema rules still apply.

The same history-row rules still apply after loading:

- the rows must use the correct unit family
- sprint identifiers must be unique
- if sprint planning is enabled, at least two usable rows are still required

## Typical command output

The examples below were produced from real runs against working example files.

The `--minimal` (`-m`) flag controls how much output is displayed. With `--minimal`, only the summary block, sprint count statistics, and confidence intervals are shown. Without it, additional diagnostic sections are included: historical sprint series, ratio summaries, correlations, and burn-up percentiles.

When you also request file exports with `--output-format`, sprint-planning results are written into dedicated sprint sections in JSON and HTML output. The CLI summary focuses on forecast results; the richer planning-assumption details for future sprint overrides are surfaced in the exported reports.

### Validation output

```text
Validating .build/doc-examples/sprint_planning_minimal.yaml...
✓ Project file is valid!
```

### Minimal sprint-planning simulation output

```text
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

Note that the current CLI prints the `removed_work_treatment` value using its internal enum representation, for example `RemovedWorkTreatment.CHURN_ONLY`. This corresponds to the configuration value `churn_only` in the project file. Likewise, `RemovedWorkTreatment.REDUCE_BACKLOG` corresponds to `reduce_backlog`.

### Richer table output

```text
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

Sprint Count Confidence Intervals:
┌──────────────┬───────────┬───────────────────────────┐
│ Percentile   │ Sprints   │ Projected Delivery Date   │
├──────────────┼───────────┼───────────────────────────┤
│ P50          │ 4.00      │ 2026-06-15                │
│ P80          │ 5.00      │ 2026-06-29                │
│ P90          │ 7.00      │ 2026-07-27                │
└──────────────┴───────────┴───────────────────────────┘
```

### Extended output (non-minimal)

When `--minimal` is not set, the CLI appends several diagnostic sections after the main summary. These sections appear in both table and plain output modes.

#### Historical Sprint Series

Descriptive statistics for each normalized historical quantity:

```text
Historical Sprint Series:
  completed_units: mean=10.75, median=10.50, std=1.09, min=10.00, max=12.00
  spillover_units: mean=1.75, median=1.75, std=0.83, min=1.00, max=2.67
  added_units: mean=1.00, median=0.75, std=0.87, min=0.00, max=2.00
  removed_units: mean=0.50, median=0.50, std=0.50, min=0.00, max=1.00
```

These reflect the normalized rows the sampler actually uses.  Use them to sanity-check that holiday-factor normalization has not introduced unexpected values.

#### Historical Ratio Summaries

```text
Historical Ratio Summaries:
  scope_addition_ratio: mean=0.0834, median=0.0675, std=0.0686, P50=0.0675, P80=0.1349, P90=0.1519
  scope_removal_ratio: mean=0.0396, median=0.0396, std=0.0354, P50=0.0396, P80=0.0659, P90=0.0738
  spillover_ratio: mean=0.1380, median=0.1433, std=0.0404, P50=0.1433, P80=0.1678, P90=0.1799
```

These ratios feed the commitment-guidance heuristic.  Higher spillover or scope-addition ratios will push guidance lower.

#### Historical Correlations

```text
Historical Correlations:
  added_units|completed_units: -0.8036
  added_units|removed_units: 0.7906
  added_units|spillover_units: 0.8242
  completed_units|removed_units: -0.2747
  completed_units|spillover_units: -0.7656
  removed_units|spillover_units: 0.2747
```

Pearson correlations between normalized historical series.  They can highlight patterns such as "sprints with high added scope also tend to have high spillover".

#### Burn-up Percentiles

```text
Burn-up Percentiles:
  Sprint 1: P50=10.50, P80=12.00, P90=12.00
  Sprint 2: P50=21.00, P80=23.33, P90=24.00
  Sprint 3: P50=31.50, P80=34.67, P90=36.00
```

Cumulative delivery bands per sprint.  Read these as "by the end of sprint N, how many units are likely to be done".  The P80 and P90 columns reflect slower scenarios, so their cumulative values rise more slowly.

### HTML and JSON report visibility

Future sprint capacity adjustments are recorded explicitly in exported reports.

In HTML output, future overrides appear in a dedicated section named `Planning Assumptions: Future Sprint Capacity Adjustments`. Each row shows:

- the targeted sprint number or boundary date
- `holiday_factor`
- `capacity_multiplier`
- effective multiplier
- optional notes

In JSON output, the same data appears under:

- `sprint_planning.planning_assumptions.future_sprint_overrides`

The JSON planning-assumptions block also includes a short note explaining that the effective multiplier is:

$$
	\text{effective multiplier} = \text{holiday factor} \times \text{capacity multiplier}
$$

The CLI summary does not currently list every override row individually. It shows the resulting forecast and diagnostics, while HTML and JSON exports preserve the detailed future-sprint assumptions for review and audit.

If you want those report sections, use an export command such as:

```bash
mcprojsim simulate sprint_project.yaml \
  --output out/sprint_forecast \
  --output-format json,html
```

These outputs are best read as ranges, not promises. The goal is to make sprint planning explicit, data-driven, and auditable.