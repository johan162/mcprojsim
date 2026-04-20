# Introduction

This chapter introduces the ideas behind probabilistic project estimation in a gradual way. The goal is not to jump directly into commands or file syntax, but to build a clear mental model of what Monte Carlo simulation is, why it is useful for project planning, and how the main concepts appear in `mcprojsim`.

The intended reader is generally knowledgeable about software projects and planning, but not necessarily familiar with Monte Carlo methods. For that reason, the discussion starts with familiar project problems and then moves step by step toward the simulation model used by the tool.



## A brief history of Monte Carlo methods

The Monte Carlo method was born from a moment of restless curiosity. In 1946, the physicist Stanislaw Ulam was recovering from illness and passing the time playing solitaire. He wondered what the probability of winning a particular Canfield layout might be. Rather than attempting a combinatorial proof, he realized it would be far simpler to play many hands and count the wins.

That insight — replacing analytical complexity with repeated random sampling — turned out to be profoundly useful. Ulam shared the idea with John von Neumann, and together they developed it into a computational technique for the nuclear weapons research at Los Alamos National Laboratory. The physicist Nicholas Metropolis suggested naming the method after the Monte Carlo Casino in Monaco where Ulam's uncle would borrow money from relatives to gamble. The name was also a nod to the role of chance at its core.

Since then, Monte Carlo methods (and more specifically its advanced cousin Markov Chain Monte Carlo (MCMC) methods) have found applications across nearly every quantitative field: nuclear physics, financial risk modeling, climate science, engineering reliability, drug development, and — closer to home — project estimation. The fundamental principle remains the same one that occurred to Ulam over a card game: when a problem is too complex to solve analytically, simulate it many times and study the results.

Project estimation is a natural fit for Monte Carlo methods because of the inherent uncertainty and complexity of software projects. By modeling tasks as probability distributions rather than fixed numbers, we can capture the range of possible outcomes and make more informed decisions about scheduling and risk management.


## Why software schedule estimates are difficult

Software projects are not repetitive production processes. They involve discovery, design trade-offs, unknown technical constraints, communication overhead, integration problems, and changing assumptions. Even when the team is experienced and the work is well understood, the true effort is rarely captured well by a single number.

This is not because software teams are uniquely poor at estimating. It is because the work itself is uncertain. A realistic planning method should therefore begin by acknowledging uncertainty rather than trying to hide it.

### The problem with single-point estimates

A single-point estimate such as "this task will take five days" appears precise, but it compresses several different possibilities into one number. It says nothing about how optimistic that estimate is, how much variation is plausible, or how likely delays are.

In practice, a task may finish early if the work is straightforward, finish near the expected time if things go normally, or finish much later if complications arise. A single-point estimate does not distinguish between these cases, which makes it difficult to reason about overall project risk.



## How Monte Carlo compares to other estimation approaches

Monte Carlo simulation is not the only way to handle uncertainty in project schedules, but it offers distinct advantages over the alternatives.

| Approach | How it works | Strengths | Limitations |
|----------|-------------|-----------|-------------|
| **Single-point estimate** | Each task gets one fixed duration | Simple, familiar | Hides uncertainty; no basis for confidence levels |
| **Expert judgment (Delphi)** | Experts discuss and converge on estimates | Captures experience and intuition | Subjective; hard to combine across many tasks systematically |
| **PERT** | Uses optimistic, likely, and pessimistic values in a weighted formula | Accounts for range; well-established method | Assumes independent tasks; uses simplified beta approximation; limited to one critical path |
| **Monte Carlo simulation** | Samples from distributions thousands of times, respecting dependencies and risks | Full probability distribution; handles dependencies, risks, and compounding uncertainty naturally | Requires more input data; results require interpretation |

The key advantage of Monte Carlo simulation is that it does not reduce uncertainty to a single number or a simple formula. Instead, it builds an entire distribution of possible outcomes. This makes it possible to answer questions like "what is the probability of finishing by a given date?" rather than only "what is the expected finish date?"



## From single numbers to structured uncertainty

Monte Carlo estimation begins with a shift in thinking: instead of asking for one exact duration, we ask for a structured description of plausible outcomes. In its most direct form, a task is described using three values:

| Parameter       | Meaning                                            | Example |
|-----------------|---------------------------------------------------|---------|
| **Minimum**     | Optimistic but plausible outcome                   | 3 days  |
| **Most likely** | Expected outcome under normal conditions           | 5 days  |
| **Maximum**     | Difficult but credible outcome if things go wrong  | 10 days |

These three values describe the shape of belief about the task. The minimum is not a best-case fantasy; it is the shortest duration that is still realistic. The maximum is not a worst-case catastrophe; it is the longest duration that is credibly possible without extraordinary events.

A range estimate contains more information than a single number. It tells us not only what outcome seems typical, but also how much variation surrounds it. That variation is essential at project level — even if every task has only moderate uncertainty, the combined uncertainty across many tasks can create a wide spread of overall completion dates.



## How Monte Carlo simulation uses these ranges

Once tasks are described as ranges, the simulator repeatedly samples possible values and computes the resulting project outcome each time. Each run of the simulation is one plausible version of how the project might unfold. By repeating the process many times, the tool builds a distribution of outcomes instead of a single answer.

Consider a single task estimated at 3 / 5 / 10 days. Across several iterations, the sampled durations might look like this:

| Iteration | Sampled duration |
|-----------|-----------------|
| 1         | 4.7 days        |
| 2         | 6.2 days        |
| 3         | 5.1 days        |
| 4         | 8.3 days        |
| 5         | 4.9 days        |
| ...       | ...             |
| 10,000    | 5.8 days        |

No single run is "the truth". The value of the method comes from looking at the collection of results. In `mcprojsim`, the default is 10,000 iterations, which is usually enough to provide a stable picture for most planning tasks.



## From many runs to a probability distribution

When we aggregate the results of many iterations, we can see not only the central tendency of the schedule, but also its spread. Instead of saying "the project ends in 73 days", we can say things like "there is a 50% chance of finishing by this date" or "there is an 80% chance of finishing by that date".

This is the point at which simulation becomes valuable for management decisions. Planning is rarely about the most likely outcome alone. It is often about deciding how much confidence is required before committing to a date.

### Common percentiles and what they mean

| Percentile | Interpretation | Typical use |
|------------|---------------|-------------|
| **P50**    | Half of simulated runs finish earlier | Neutral planning target; even split of risk |
| **P75**    | Three quarters of runs finish earlier | Moderate confidence |
| **P80**    | 80% of runs finish earlier | Common management target |
| **P90**    | 90% of runs finish earlier | Conservative; appropriate when lateness is costly |
| **P95**    | 95% of runs finish earlier | High confidence; useful for contractual commitments |
| **P99**    | 99% of runs finish earlier | Very high confidence, useful for mission critical commiments |

The important point is not that one percentile is always correct. The simulation allows stakeholders to choose a confidence level deliberately rather than inheriting one implicitly from an optimistic single-point estimate.



## Tasks, dependencies, and project structure

Real projects consist of many tasks, not one. Each task has its own estimate, and the tasks are not independent in a scheduling sense. Some can start immediately, while others must wait for predecessors to finish.

Dependencies determine the order in which work can occur. A task cannot begin simply because a team is ready to work on it; it may also require certain other tasks to be complete first. This matters because uncertainty propagates through the dependency network — a delay in one upstream task can delay many downstream tasks even if those later tasks are estimated accurately.

Project duration is not computed by adding all task durations together. Some tasks can run in parallel, while others form chains that must happen in sequence. The final project duration emerges from both the estimated task durations and the structure of the task network:

| Scenario | Tasks A and B (each 5 days) | Project duration |
|----------|----------------------------|-----------------|
| **Sequential** — B depends on A | A then B | 10 days |
| **Parallel** — no dependency | A alongside B | 5 days |
| **Partial overlap** — C depends on A, not B | A then C, B runs alongside | Depends on relative durations |

This is why task scheduling is a central part of project simulation. The same set of task estimates can lead to different overall project durations depending on how the work is connected.



## The critical path

In any given simulated run, some sequence of dependent tasks determines the final completion time. This sequence is the critical path.

Not every task contributes equally to schedule risk. Some tasks are important but not schedule-dominant. Others repeatedly determine whether the project finishes early or late.

A common mistake is to assume there is one fixed critical path. In deterministic planning this may be a useful simplification, but in a simulation context it is often wrong. Because task durations vary from run to run, the schedule-dominating path can also change. One of the strengths of Monte Carlo simulation is that it can show which tasks are *frequently* critical, not just which tasks are critical in one nominal plan. `mcprojsim` tracks this across all iterations and reports a criticality index for each task — the percentage of iterations in which that task appeared on the critical path.



## Two sources of schedule variation

Beyond the estimate range itself, `mcprojsim` models two additional sources of schedule variation. Understanding the distinction between them is important for building accurate project models.

| Source | Nature | How it works | Example |
|--------|--------|-------------|---------|
| **Uncertainty factors** | Persistent conditions | Multiply the sampled duration | An inexperienced team is 30% slower |
| **Risks** | Discrete events | Add time if triggered | A security audit adds 5 days with 30% probability |

Uncertainty factors describe conditions. Risks describe events. A difficult architecture is an uncertainty factor. A failed security audit that adds rework is a risk. This distinction helps the model stay understandable — not every source of delay should be represented as a probabilistic event.

### Uncertainty factors

Uncertainty factors are known characteristics of the working environment that systematically affect how long work takes. `mcprojsim` supports five configurable factors:

| Factor | What it captures |
|--------|-----------------|
| `team_experience` | Familiarity with the technology and domain |
| `requirements_maturity` | How well-defined and stable requirements are |
| `technical_complexity` | How technically challenging the work is |
| `team_distribution` | Colocated vs. distributed teams |
| `integration_complexity` | Degree of integration with other systems |

These factors are multiplicative. When a task specifies several of them, the multipliers are combined by multiplication. This means adverse factors compound — even moderate individual adjustments can produce a significant combined effect.

The numeric multipliers are defined in a separate configuration file, not in the project file. This allows teams to calibrate the meaning of labels like "high complexity" or "low maturity" to match their own experience, without changing the project definition. See [Uncertainty Factors](04_uncertainty_factors.md) for the full list of default multiplier values and guidance on calibration.

### Risks

Risks describe events that may or may not happen. Unlike uncertainty factors, which always apply, a risk triggers probabilistically in each simulation iteration. If it triggers, its impact is added to the duration.

Risks can be defined at two levels:

- **Task-level risks** apply to a specific task. For example, a database migration might have a 20% chance of encountering schema conflicts that add 2 days.
- **Project-level risks** apply to the project as a whole. For example, there might be a 15% chance that a key developer leaves, delaying the entire project by 20%.

Every risk combines two dimensions: how likely the event is, and how large the consequence is if it happens. A low-probability, high-impact event behaves very differently from a high-probability, low-impact event. Monte Carlo simulation captures both naturally without forcing them into a single oversimplified score.



## Effort estimation versus calendar scheduling

Everything discussed so far — task estimates, uncertainty factors, risks — describes how much *work* a task requires. This is the effort dimension, measured in hours of productive labor. But effort alone does not answer the question that stakeholders actually ask: "When will it be done?"

The answer to that question lives in a different dimension: calendar time. Calendar time is the elapsed clock time from project start to project finish, and it depends on much more than effort. Two projects with identical total effort can finish weeks or even months apart depending on how many people are available, when they work, and what interruptions occur along the way.

| Dimension | What it measures | Example |
|-----------|-----------------|---------|
| **Effort** | Total productive work required | 80 person-hours |
| **Calendar time** | Elapsed wall-clock duration | 15 working days (3 calendar weeks) |

The distinction matters because most planning conversations conflate the two. When someone estimates "this will take two weeks", they usually mean effort — but the listener hears a calendar commitment. A simulation that only models effort without considering how that effort maps onto real calendars will produce misleadingly optimistic dates.

Converting effort into calendar time requires knowing the capacity available at each point in time. If two people work full-time on a task, 80 hours of effort can finish in 40 clock-hours — five working days. If one person works half-time, the same effort stretches to 20 working days. The conversion is not a simple division; it must account for varying capacity across time as people come and go, work different schedules, and encounter interruptions.



## Constrained scheduling: from ideal plans to real-world schedules

Dependency-only scheduling assumes that any task can start immediately once its predecessors are complete, as if an unlimited number of equally skilled people were always available. This is a useful simplification for understanding project structure, but it does not reflect reality. Real projects have a finite number of people, and those people have different skills, work different hours, take holidays, and occasionally get sick.

Constrained scheduling bridges this gap. When the simulation knows about the actual team — who is available, when they work, and what skills they have — it can produce calendar dates that reflect genuine capacity rather than theoretical parallelism.

### Resources and capacity

In a constrained simulation, each team member is modeled as a resource with specific characteristics:

| Characteristic | What it captures | Why it matters |
|----------------|-----------------|----------------|
| **Availability** | Fraction of the workday this person is available | A 50%-available resource takes twice as long in calendar time |
| **Productivity** | Relative throughput compared to baseline | A senior developer may complete work faster than a junior one |
| **Experience level** | Skill tier of the resource | Some tasks require a minimum experience level |

These properties determine how quickly a resource converts effort into progress. The scheduler integrates effort over actual capacity windows — it does not simply divide effort by a fixed rate. When multiple resources work on the same task, their capacities combine, but practical limits prevent unrealistic compression (assigning eight people to an eight-hour task does not make it finish in one hour).

Because resources are finite, tasks sometimes cannot start even when their dependencies are satisfied. A task may be ready to go, but all qualified resources are occupied elsewhere. This waiting time — invisible in dependency-only mode — is a real and often significant contributor to project duration.

### Working calendars

People do not work around the clock. A working calendar defines the rhythm of productive time: which days of the week are working days, how many hours per day, and which dates are holidays. Different resources can follow different calendars — a full-time developer on a Monday-to-Friday schedule, a part-time contractor working four shorter days.

The effect on scheduling is direct. An eight-hour task that begins on Friday afternoon cannot finish until Monday. A task assigned to someone on a four-day week takes longer in calendar time than the same task assigned to someone working five days. Holidays create gaps where no progress occurs. All of these effects compound across the project, and they are especially visible in the tail of the schedule distribution — the dates at P90 and beyond that matter most for planning commitments.

### Planned and unplanned absence

Even on working days, people are not always available. Planned absences — vacations, conferences, training — are known in advance and can be specified per resource. The simulation treats these dates as non-working days for that individual, reducing their capacity to zero on those dates.

Unplanned absence is inherently stochastic. People get sick, have family emergencies, or encounter other interruptions that cannot be predicted. `mcprojsim` models this by assigning each resource a daily sickness probability. On each simulated working day, the simulator rolls a random check for each resource. If sickness triggers, the resource is unavailable for a realistic duration drawn from a probability distribution. Because this happens independently in each simulation iteration, the aggregate effect of unplanned absence emerges naturally in the results — some iterations see little disruption, others see more, and the overall distribution captures the range.

This stochastic modeling of absence is one of the reasons Monte Carlo simulation is particularly well suited to schedule planning. Deterministic methods either ignore absence entirely or account for it with a crude average discount. A simulation can model the actual variability: the possibility that two key people happen to be sick during the same critical week, or that the project runs smoothly with minimal disruption. Both scenarios contribute to the final probability distribution.

### Why constrained scheduling changes the picture

The combined effect of resource constraints, calendars, and absences is often substantial. A project that finishes in 130 hours under dependency-only scheduling might take 550 calendar-hours — over four times longer — when resource constraints and calendars are applied. The effort has not changed; the calendar reality has.

This is not a failure of estimation. It is a more honest picture of when work actually completes. The gap between effort-based estimates and calendar-based schedules is where many real-world planning surprises originate. By modeling resources, calendars, and absences explicitly, the simulation surfaces these effects before the project starts rather than after commitments have been made.

::: pagebreak-b5
:::

## What the simulation computes, step by step

For each iteration, the simulation follows this sequence:

| Step | Action | Scope |
|------|--------|-------|
| 1 | **Sample** a base duration for each task from its estimate distribution | Per task |
| 2 | **Adjust** each duration by multiplying in the task's uncertainty factors | Per task |
| 3 | **Evaluate** each task's risks — if triggered, add the impact | Per task |
| 4 | **Schedule** all tasks respecting dependency constraints | Whole project |
| 5 | **Calculate** the project duration as the latest task completion time | Whole project |
| 6 | **Evaluate** project-level risks — if triggered, add the impact | Whole project |

This process is repeated for every iteration. The final output is not the result of one deterministic calculation, but the statistical summary of many plausible project histories.



## Understanding the results

### Statistical summary

Simulation results should be read as statements about confidence, spread, and likelihood. A median outcome tells you what happens in the middle of the simulated runs. Percentiles tell you the duration that a given percentage of runs finish within.

These numbers are decision aids, not guarantees. They help users choose targets that reflect a chosen level of planning confidence.

### Histograms

A histogram gives a visual summary of how outcomes are distributed. A narrow histogram suggests relatively stable outcomes. A wide histogram suggests greater uncertainty. Skewness can indicate that the project has more downside risk than upside potential.

Even users who are not statistically trained can often read histograms effectively once they understand that the horizontal axis represents duration and the vertical axis represents frequency.

### Sensitivity and criticality

One of the most useful questions in project planning is not only "how long will this take?" but "what drives the answer?" Sensitivity analysis identifies which tasks contribute most to schedule variation. Criticality analysis shows which tasks most often appear on the critical path. Together, these views tell you where to focus mitigation and management attention.

### Staffing recommendations

Simulation results also help answer the question "how many people should work on this?" Adding people to a project increases capacity but also increases communication overhead — a trade-off famously described by Brooks's Law. `mcprojsim` uses the simulated total effort, the critical-path duration, and the peak parallelism in the schedule to recommend an optimal team size for different experience profiles. The recommendation is an advisory layer on top of the simulation, not a constraint on the simulation itself.

### Reproducibility

Although Monte Carlo simulation relies on randomness, it can be made reproducible. By setting a random seed, users can repeat the same simulation and obtain the same results. This is useful for analysis, review, automation, and auditability — it allows teams to discuss the same output without worrying that the numbers changed simply because the simulation was run again.



## How the input files reflect the model

`mcprojsim` uses two types of input files, each with a distinct purpose:

| File | Purpose | Contains |
|------|---------|----------|
| **Project file** (YAML or TOML) | Describes the specific project | Metadata, tasks, dependencies, estimates, risks |
| **Configuration file** (YAML) | Defines organizational assumptions | Uncertainty factor multipliers, T-shirt size mappings, story point mappings, simulation defaults |

This separation means the project file describes what is being planned, while the configuration file describes how the organization interprets uncertainty. Teams can share a single configuration across many projects, keeping individual project files focused and readable.

Before learning every schema detail, it helps to read a project file as a narrative. The project block says what is being planned. The task list says what must be done. Dependencies say in what order work becomes possible. Risks and uncertainty factors explain why durations may vary.

### Multiple ways to express estimates

`mcprojsim` supports several ways to express effort uncertainty. These are not competing approaches — they are different ways of expressing the same underlying concept, suited to different stages of planning.

| Estimate type | When to use it | Example |
|---------------|---------------|---------|
| **Explicit range** (low / expected / high) | When the team can provide numeric estimates | `low: 3, expected: 5, high: 10` |
| **T-shirt size** (XS through XXL) | For early-stage or relative estimation | `t_shirt_size: "M"` |
| **Story points** (1, 2, 3, 5, 8, 13, 21) | When the team uses story point estimation | `story_points: 5` |

T-shirt sizes and story points are mapped to numeric ranges in the configuration file, so they ultimately feed into the same simulation machinery as explicit estimates. They provide a natural bridge from familiar agile estimation practices into probabilistic simulation.



## When Monte Carlo estimation is most valuable

Monte Carlo methods are particularly helpful when projects have:

- Multiple tasks with dependencies that create compounding uncertainty
- Meaningful risk events that may or may not occur
- Stakeholders who need to reason in terms of confidence rather than optimistic commitments
- Significant consequences for late delivery, making conservative planning worthwhile

The method is less valuable when the work is trivial, highly repetitive, or too poorly defined to estimate in any structured way. Like any planning method, it works best when the inputs are thoughtful and the model is used with judgment.



## What comes next in this guide

The rest of the user guide builds on the concepts introduced here. Later chapters cover the project file format, configuration, risk and uncertainty factor modeling, and interpreting the generated outputs in detail.

By the time you move into those chapters, the goal is that the fields in the input files no longer feel arbitrary. They should feel like natural answers to the questions that this introduction has raised.

\newpage

