# Your first project

This chapter shows how to build a project input file gradually.

The goal is not to start with a large “realistic” file and explain it all at once. Instead, we begin with the smallest useful example and then add one idea at a time: more tasks, dependencies, configuration, uncertainty factors, and risks.

That approach mirrors how most teams actually learn the tool. First they want to know the minimum needed to run a simulation. After that, they want to enrich the model with the information they already have about the work, the team, and the main sources of schedule risk.

The examples in this chapter are intentionally small, but they follow the same style as the more complete files in `examples/sample_project.yaml`, `examples/sample_config.yaml`, `examples/tshirt_sizing_project.yaml`, and `examples/story_points_walkthrough_project.yaml`.

## Chapter outline

In this chapter we will build the input in six stages:

1. Start with the smallest possible project file.
2. Add a second task and a dependency.
3. Introduce a configuration file and uncertainty factors.
4. Add task-level and project-level risks.
5. Express work with T-shirt sizes.
6. Express work with Story Points.

At each step we will run the simulation and look at how the results change.

## The smallest possible project file

The simplest useful project file contains two top-level sections:

- `project`: basic metadata about the project.
- `tasks`: at least one task with an estimate.

That is enough to validate the file and run a simulation.

### Step 1: one task, one estimate

Start with a single task:

```yaml
project:
  name: "Tiny Landing Page"
  description: "The smallest possible example"
  start_date: "2026-03-01"
  confidence_levels: [50, 80, 90]

tasks:
  - id: "task_001"
    name: "Create landing page"
    estimate:
      min: 2
      most_likely: 3
      max: 5
      unit: "days"
```

This file does not yet say anything about dependencies, team characteristics, or risks. It simply says: “we have one task, and we believe it is likely to take around three days, but with some uncertainty around that value”.

Before simulating, it is good practice to validate the file:

```bash
mcprojsim validate first-project-step-1.yaml
```

Expected result:

```text
Validating first-project-step-1.yaml...
✓ Project file is valid!
```

Now run the simulation:

```bash
mcprojsim simulate first-project-step-1.yaml --iterations 5000 --seed 42
```

Example result summary:

```text
=== Simulation Results ===
Project: Tiny Landing Page
Hours per Day: 8.0
Mean: 42.26 hours (6 working days)
Median (P50): 41.52 hours
Std Dev: 7.93 hours

Confidence Intervals:
  P50: 41.52 hours (6 working days)
  P80: 49.60 hours (7 working days)
  P90: 53.44 hours (7 working days)
```

The important thing here is not the exact numbers. The important thing is that even a one-task project produces a range of likely outcomes rather than one fixed answer. Results are reported in hours (the canonical internal unit) with working days shown alongside.

## Add structure: a second task and a dependency

A one-task example is useful for learning the mechanics, but real projects are interesting because tasks interact. The next step is therefore to add a second task that depends on the first one.

### Step 2: sequence the work

```yaml
project:
  name: "Tiny Landing Page"
  description: "Adding sequencing"
  start_date: "2026-03-01"
  confidence_levels: [50, 80, 90]

tasks:
  - id: "task_001"
    name: "Create landing page"
    estimate:
      min: 2
      most_likely: 3
      max: 5
      unit: "days"

  - id: "task_002"
    name: "Deploy site"
    estimate:
      min: 1
      most_likely: 2
      max: 4
      unit: "days"
    dependencies: ["task_001"]
```

The new information is in the `dependencies` field. It says that deployment cannot start until the landing page work is complete.

Run it:

```bash
mcprojsim simulate first-project-step-2.yaml --iterations 5000 --seed 42
```

Example result summary:

```text
=== Simulation Results ===
Project: Tiny Landing Page
Hours per Day: 8.0
Mean: 71.58 hours (9 working days)
Median (P50): 71.20 hours
Std Dev: 10.96 hours

Confidence Intervals:
  P50: 71.20 hours (9 working days)
  P80: 80.96 hours (11 working days)
  P90: 86.00 hours (11 working days)

Most Frequent Critical Paths:
  1. task_001 -> task_002 (5000/5000, 100.0%)
```

Compared with the first example, the schedule is now longer because the project contains more work. More importantly, the dependency means the tasks form a chain rather than happening independently. This is the beginning of a project network.

This is also the point where the input file starts to describe more than estimates. It now describes project structure.

### Understanding the critical path output

Starting from this step, the CLI and exports also report full critical path sequences.

That means the tool now shows:

- **task-level criticality**, which answers: “how often was this task on a critical path?”
- **full path sequences**, which answer: “which complete dependency chains were most often critical?”

For this small example there is only one dependency chain, so the reported path is always:

```text
task_001 -> task_002
```

In larger projects, several different paths may become critical across the Monte Carlo iterations. The simulator aggregates those paths and shows the most common ones.

You can request more than the default two paths in the CLI:

```bash
mcprojsim simulate first-project-step-2.yaml --iterations 5000 --seed 42 --critical-paths 4
```

And you can control how many are stored and reported by default through `config.yaml`:

```yaml
simulation:
  max_stored_critical_paths: 20

output:
  critical_path_report_limit: 2
```

## Add organizational knowledge with a configuration file

So far, the estimates came entirely from the task ranges themselves. In practice, teams usually know more than that. They often know whether the team is experienced, whether the requirements are mature, or whether the technical environment is unusually complex.

In `mcprojsim`, that sort of shared interpretation belongs in a configuration file.

### Step 3: add uncertainty factors

First create a configuration file:

```yaml
uncertainty_factors:
  team_experience:
    high: 0.90
    medium: 1.0
    low: 1.25

  requirements_maturity:
    high: 1.0
    medium: 1.10
    low: 1.30

  technical_complexity:
    low: 1.0
    medium: 1.15
    high: 1.40

simulation:
  default_iterations: 10000
  random_seed: null

output:
  formats: ["json"]
  include_histogram: true
  histogram_bins: 30
```

Then add uncertainty-factor labels to the project file:

```yaml
project:
  name: "Tiny Landing Page"
  description: "Adding uncertainty factors"
  start_date: "2026-03-01"
  confidence_levels: [50, 80, 90]

tasks:
  - id: "task_001"
    name: "Create landing page"
    estimate:
      min: 2
      most_likely: 3
      max: 5
      unit: "days"
    uncertainty_factors:
      team_experience: "high"
      requirements_maturity: "medium"

  - id: "task_002"
    name: "Deploy site"
    estimate:
      min: 1
      most_likely: 2
      max: 4
      unit: "days"
    dependencies: ["task_001"]
    uncertainty_factors:
      team_experience: "medium"
      technical_complexity: "medium"
```

Run it with the configuration file:

```bash
mcprojsim simulate first-project-step-3.yaml \
  --config first-project-config.yaml \
  --iterations 5000 \
  --seed 42
```

Example result summary:

```text
=== Simulation Results ===
Project: Tiny Landing Page
Hours per Day: 8.0
Mean: 53.76 hours (7 working days)
Median (P50): 53.44 hours
Std Dev: 8.32 hours

Confidence Intervals:
  P50: 53.44 hours (7 working days)
  P80: 60.88 hours (8 working days)
  P90: 64.64 hours (9 working days)
```

This is an important modeling step.

The project file still contains the project-specific facts: tasks, estimates, and dependencies. The configuration file now contains the organization’s shared interpretation of labels such as `high team_experience` or `medium technical_complexity`.

In this example, the overall forecast becomes shorter than in Step 2 because the chosen factors make part of the work more favorable than the neutral baseline.

## Add explicit risk events

Uncertainty factors model persistent conditions around the work. Risks model events that may or may not happen.

That distinction matters. A distributed team is not an event; it is a condition. A late stakeholder change is an event; it may happen, or it may not.

### Step 4: add project-level and task-level risks

```yaml
project:
  name: "Tiny Landing Page"
  description: "Adding risk events"
  start_date: "2026-03-01"
  confidence_levels: [50, 80, 90]

project_risks:
  - id: "risk_001"
    name: "Late stakeholder changes"
    probability: 0.20
    impact:
      type: "absolute"
      value: 2
      unit: "days"

tasks:
  - id: "task_001"
    name: "Create landing page"
    estimate:
      min: 2
      most_likely: 3
      max: 5
      unit: "days"
    uncertainty_factors:
      team_experience: "high"
      requirements_maturity: "medium"

  - id: "task_002"
    name: "Deploy site"
    estimate:
      min: 1
      most_likely: 2
      max: 4
      unit: "days"
    dependencies: ["task_001"]
    uncertainty_factors:
      team_experience: "medium"
      technical_complexity: "medium"
    risks:
      - id: "risk_002"
        name: "Hosting problem"
        probability: 0.15
        impact: 1.5
```

Run it:

```bash
mcprojsim simulate first-project-step-4.yaml \
  --config first-project-config.yaml \
  --iterations 5000 \
  --seed 42
```

Example result summary:

```text
=== Simulation Results ===
Project: Tiny Landing Page
Hours per Day: 8.0
Mean: 58.88 hours (8 working days)
Median (P50): 58.00 hours
Std Dev: 11.36 hours

Confidence Intervals:
  P50: 58.00 hours (8 working days)
  P80: 68.56 hours (9 working days)
  P90: 74.32 hours (10 working days)
```

Notice what happened relative to Step 3:

- the mean increased,
- the upper percentiles increased,
- the spread increased.

That is exactly what we expect when we add plausible delay events to the model. The file is not just more detailed. It is representing more of the actual uncertainty that the team believes exists.

## An alternative style: T-shirt sized estimates

So far, every task has used an explicit estimate range with `min`, `most_likely`, and `max`. That is often the best choice when the team is comfortable expressing estimates directly in days.

However, some teams think more naturally in relative sizing. They can say that one task is `S`, another is `M`, and another is `XL`, even when they do not yet want to commit to detailed numeric ranges.

`mcprojsim` supports that style directly.

### Step 5: use `t_shirt_size` instead of explicit ranges

In the source code, a task estimate may specify `t_shirt_size` instead of `most_likely` and the related range values. Validation accepts that form, and the simulation engine later resolves the symbolic size to concrete `min`, `most_likely`, and `max` values from the active configuration.

That means a T-shirt-sized task still becomes an ordinary probabilistic range during simulation. The symbolic label is just a more convenient way to express the estimate in the input file.

**Important:** T-shirt size estimates must not include a `unit` field in the project file. The unit is determined by the configuration file's `t_shirt_size_unit` setting (default: `"hours"`).

Here is a small example:

```yaml
project:
  name: "Tiny Landing Page"
  description: "T-shirt sizing example"
  start_date: "2026-03-01"
  confidence_levels: [50, 80, 90]

tasks:
  - id: "task_001"
    name: "Design page"
    estimate:
      t_shirt_size: "S"
    dependencies: []
    uncertainty_factors:
      team_experience: "high"
      requirements_maturity: "high"

  - id: "task_002"
    name: "Build page"
    estimate:
      t_shirt_size: "M"
    dependencies: ["task_001"]
    uncertainty_factors:
      team_experience: "medium"
      technical_complexity: "medium"

  - id: "task_003"
    name: "Deploy page"
    estimate:
      t_shirt_size: "XS"
    dependencies: ["task_002"]
```

Note that no `unit` field appears on any task — the unit is taken from the configuration.

The same example is also available as `examples/tshirt_walkthrough_project.yaml`, with a matching configuration file at `examples/tshirt_walkthrough_config.yaml`.

### How T-shirt sizes are configured

If you want to use a custom configuration file with T-shirt estimates, add a `t_shirt_sizes` section like this:

```yaml
t_shirt_sizes:
  XS:
    min: 0.5
    most_likely: 1
    max: 2
  S:
    min: 1
    most_likely: 2
    max: 4
  M:
    min: 3
    most_likely: 5
    max: 8
  L:
    min: 5
    most_likely: 8
    max: 13
  XL:
    min: 8
    most_likely: 13
    max: 21
  XXL:
    min: 13
    most_likely: 21
    max: 34
```

These are the same default mappings provided by the application itself. If you run without a custom configuration file, those built-in sizes are available automatically.

If you do use your own configuration file and want to use T-shirt sizes, make sure that file includes a `t_shirt_sizes` section. The simulation engine resolves the label by looking it up in the active configuration, and it raises an error if the size is unknown.

This detail is important: `t_shirt_size` is not just a comment or a reporting label. It is a real input that must be backed by a configuration mapping.

In other words, you have two safe options:

- run without `--config` and use the built-in size mappings, or
- use `--config` with a file that explicitly defines `t_shirt_sizes`.

Run the T-shirt-sized example like this:

```bash
mcprojsim simulate examples/tshirt_walkthrough_project.yaml \
  --config examples/tshirt_walkthrough_config.yaml \
  --iterations 5000 \
  --seed 42
```

Example result summary:

```text
=== Simulation Results ===
Project: Tiny Landing Page
Hours per Day: 8.0
Mean: 11.46 hours (2 working days)
Median (P50): 11.37 hours
Std Dev: 1.63 hours

Confidence Intervals:
  P50: 11.37 hours (2 working days)
  P80: 12.87 hours (2 working days)
  P90: 13.67 hours (2 working days)
```

The interpretation is exactly the same as for explicit ranges. The only difference is how the task effort was expressed in the input file.

T-shirt sizes are especially useful early in planning, when the team can compare tasks relative to each other more easily than they can assign precise numeric ranges. Later, if needed, the team can replace those symbolic sizes with explicit estimate ranges for finer control.

## Another alternative style: Story Point estimates

Some teams prefer to estimate backlog items in Story Points rather than T-shirt sizes or explicit day ranges.

`mcprojsim` supports that style as another symbolic estimate form. In the input file you provide a `story_points` value, and during simulation the active configuration resolves it to a numeric `(min, most_likely, max)` range in the configured unit (default: days).

**Important:** Story point estimates must not include a `unit` field in the project file. The unit is determined by the configuration file's `story_point_unit` setting (default: `"days"`).

### Step 6: use `story_points`

Here is a small Story Point example:

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

  - id: "task_002"
    name: "Build page"
    estimate:
      story_points: 5
    dependencies: ["task_001"]

  - id: "task_003"
    name: "Deploy page"
    estimate:
      story_points: 1
    dependencies: ["task_002"]
```

Note that no `unit` field appears on any task — the unit is taken from the configuration.

The same example is also available as `examples/story_points_walkthrough_project.yaml`, with a matching configuration file at `examples/story_points_walkthrough_config.yaml`.

### How Story Points are configured

If you want to customize Story Point mappings, add a `story_points` section to the configuration file:

```yaml
story_points:
  1:
    min: 0.5
    most_likely: 1
    max: 3
  2:
    min: 1
    most_likely: 2
    max: 4
  3:
    min: 1.5
    most_likely: 3
    max: 5
  5:
    min: 3
    most_likely: 5
    max: 8
  8:
    min: 5
    most_likely: 8
    max: 15
```

These are built-in defaults. If you provide a custom configuration file, you may override only the Story Point values you want to recalibrate for your team; the remaining built-in defaults stay available.

Run the Story Point example like this:

```bash
mcprojsim simulate examples/story_points_walkthrough_project.yaml \
  --config examples/story_points_walkthrough_config.yaml \
  --iterations 5000 \
  --seed 42
```

Story Points are useful when the team has a stable internal understanding of what `1`, `2`, `3`, `5`, or `8` mean, but that understanding does not translate directly to raw hours or days. The config file is where that team-specific calibration belongs.

## What each stage added

It is useful to summarize what changed at each step:

| Step | New concept | Why it matters |
|---|---|---|
| 1 | Single task with a range estimate | Gives the smallest valid simulation input |
| 2 | Dependencies | Turns isolated tasks into a schedule network |
| 3 | Configuration and uncertainty factors | Adds team and context knowledge without cluttering the project file |
| 4 | Risks | Models probabilistic events that may push the schedule later |
| 5 | T-shirt sizes | Lets teams express effort symbolically while still simulating numeric ranges |
| 6 | Story Points | Lets agile teams use calibrated relative sizing while still simulating numeric ranges |

This is a good way to think about building real project files. Start with the structure that is definitely known. Then add more realism in layers.

## A practical workflow for real projects

When building your own project file, the following sequence usually works well:

1. List the tasks.
2. Add simple effort ranges.
3. Add dependencies.
4. Validate the file.
5. Run an initial simulation.
6. Add uncertainty factors from a shared configuration file.
7. Add the most important task-level and project-level risks.
8. Re-run the simulation and compare the percentiles.

This approach helps prevent over-modeling too early. A simple, valid project file that you understand is more useful than a large, complicated file that nobody fully trusts.

## How this chapter connects to the shipped examples

The tiny examples in this chapter are teaching examples. The files in the `examples/` directory show how the same ideas scale up.

- `examples/sample_project.yaml` shows a more complete project with several tasks, dependencies, uncertainty factors, and risks.
- `examples/sample_config.yaml` shows a fuller configuration with reusable uncertainty-factor mappings and output settings.
- `examples/tshirt_sizing_project.yaml` shows an alternative style where tasks use T-shirt sizes instead of explicit `min`, `most_likely`, and `max` values.
- `examples/story_points_walkthrough_project.yaml` shows the same symbolic-estimate idea using Story Points and a configuration mapping.
- `examples/project_with_custom_thresholds.yaml` shows how project-level reporting thresholds can be tuned for stricter or more conservative decision-making.

If you have understood the stages in this chapter, those larger example files should now feel much easier to read.

## What to try next

Once you are comfortable with the basic structure, good next experiments are:

- change a dependency and see how the forecast moves,
- add a task-level risk and compare P80 or P90,
- move uncertainty-factor labels from one level to another,
- try T-shirt sizes instead of explicit estimate ranges,
- try Story Points with a team-calibrated config mapping,
- export JSON or HTML output and inspect the richer reports.

The next chapters go deeper into the input format and configuration options. The purpose of this chapter was simply to get you from “empty file” to “first useful simulation” in a gradual and understandable way.

\newpage

