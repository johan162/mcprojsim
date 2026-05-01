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

## Quick command and flag map

This chapter focuses on building the project file step-by-step, but it helps to know the full CLI surface area up front.

### Commands at a glance

| Command | Purpose |
|---------|---------|
| `mcprojsim generate INPUT_FILE` | Generate a project YAML file from plain-text input |
| `mcprojsim validate PROJECT_FILE` | Validate a project file without simulating |
| `mcprojsim simulate PROJECT_FILE` | Run Monte Carlo simulation and optionally export reports |
| `mcprojsim config` | Show active configuration |

### Common `simulate` flags

| Flag | What it controls |
|------|------------------|
| `--iterations`, `-n` | Number of Monte Carlo iterations |
| `--seed`, `-s` | Reproducibility seed |
| `--config`, `-c` | Custom config file |
| `--target-date` | Probability of finishing on/before a target date |
| `--output-format`, `-f` | Export format(s): json, csv, html |
| `--output`, `-o` | Export output base path |
| `--critical-paths` | Number of critical path sequences shown/exported |
| `--table`, `-t` | Render CLI tabular sections as ASCII tables |
| `--minimal`, `-m` | Minimal console output mode |
| `--verbose`, `-v` | Show detailed informational messages |
| `--quiet`, `-q`, `-qq` | Reduce or suppress normal CLI output |
| `--staffing` | Expanded staffing recommendation tables |
| `--tshirt-category` | Override default T-shirt category  |
| `--velocity-model` | Override sprint velocity model for how historic data are used (`empirical`/`neg_binomial`) |
| `--no-sickness` | Disable sprint sickness modeling |
| `--two-pass` | Enable criticality two-pass scheduling (resource-constrained mode) |
| `--pass1-iterations` | Pass-1 iterations used by `--two-pass` |
| `--include-historic-base` | Add Historic Base section/series in HTML+JSON exports |

For full details, defaults, and examples, see [Running simulations](12_running_simulations.md).

This chapter intentionally uses only a small subset of these flags in each step.

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
      low: 2
      expected: 3
      high: 5
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
mcprojsim simulate first-project-step-1.yaml --iterations 5000 --seed 42 --minimal
```

Example result:

{{!mcprojsim simulate examples/01_first_project/first-project-step-1.yaml --iterations 5000 --seed 42 --minimal@B5:18*}}


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
      low: 2
      expected: 3
      high: 5
      unit: "days"
  - id: "task_002"
    name: "Deploy site"
    estimate:
      low: 1
      expected: 2
      high: 4
      unit: "days"
    dependencies: ["task_001"]
```

The new information is in the `dependencies` field. It says that deployment cannot start until the landing page work is complete.

Run it:

```bash
mcprojsim simulate first-project-step-2.yaml --iterations 5000 --seed 42 
```

Example result summary:

{{!mcprojsim simulate examples/01_first_project/first-project-step-2.yaml --iterations 5000 --seed 42@B5:16:14}}


Compared with the first example, the schedule is now longer because the project contains more work. More importantly, the dependency means the tasks form a chain rather than happening independently. This is the beginning of a project network.

This is also the point where the input file starts to describe more than estimates. It now describes project structure.

### Understanding the critical path output

Starting from this step, the CLI and exports also report full critical path sequences.

That means the tool now shows:

- **task-level criticality**, which answers: “how often was this task on a critical path?”
- **full path sequences**, which answer: “which complete dependency chains were most often critical?”

For this small example there is only one dependency chain, so the reported path is always:

```text
task_001 -> task_002 (5000/5000, 100.0%)
```

In larger projects, several different paths may become critical across the Monte Carlo iterations. The simulator aggregates those paths and shows the most common ones.

You can request more than the default two paths in the CLI:

```bash
mcprojsim simulate first-project-step-2.yaml --iterations 5000 --seed 42 --critical-paths 4
```

For this small project there is only one critical path, so specifying a larger report limit does not change the output.

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

Uncertainty factors are a way to convert known project conditions into tangible schedule effects. For example, requirements may be immature and likely to change after work begins, or the team may be distributed across countries and time zones, creating additional communication overhead and a higher risk of misunderstandings.

These types of know risks can be modelled by multiplicative factors. The program supports the following uncertaintly factors

| Factor                  | Default Level |
|-------------------------|---------------|
| `team_experience`       | `medium`      |
| `requirements_maturity` | `high`        |
| `technical_complexity`  | `low`         |
| `team_distribution`     | `colocated`   |
| `integration_complexity`| `low`         |

The name of the factors should be self-explanatory. The values of the factors are heuristically determined and can be adjusted for company or team specific circumstances in the config file.

The uncertainty factors can be applied both on project- and task level. In the following example we add them for each task.


```yaml
project:
  name: "Tiny Landing Page"
  description: "Adding uncertainty factors"
  start_date: "2026-03-01"
  confidence_levels: [50, 80, 90]
!!! yaml-cbreak-b5
tasks:
  - id: "task_001"
    name: "Create landing page"
    estimate:
      low: 2
      expected: 3
      high: 5
      unit: "days"
    uncertainty_factors:
      team_experience: "high"
      requirements_maturity: "medium"

  - id: "task_002"
    name: "Deploy site"
    estimate:
      low: 1
      expected: 2
      high: 4
      unit: "days"
    dependencies: ["task_001"]
    uncertainty_factors:
      team_experience: "medium"
      technical_complexity: "medium"
```

Run it with this configuration file:

```bash
mcprojsim simulate first-project-step-3.yaml --seed 42 --minimal
```

Example result summary:

{{!mcprojsim simulate examples/01_first_project/first-project-step-3.yaml --seed 42 --minimal@B5:18*}}


This is an important modeling step. As can be seen from the simulation these uncertainty factors add another day effort to be 80% certain.

To modify these factors according to the project specific circumstances add the specific values in separate config file that are used in the simulation. For example we can use slightly higher values for the uncertainty factors than the program uses by default as:

```yaml
uncertainty_factors:  
  team_experience:    
    high: 0.90    
    medium: 1.1    
    low: 1.50  
  requirements_maturity:    
    high: 1.0    
    medium: 1.40    
    low: 1.80  
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
    number_bins: 30
```

To see the programs default values use

```bash
mcprojsim config
```

The interesting part of the output is

```yaml
Uncertainty Factors:
  team_experience:
    high: 0.9
    medium: 1.0
    low: 1.3
  requirements_maturity:
    high: 1.0
    medium: 1.15
    low: 1.4
  technical_complexity:
    low: 1.0
    medium: 1.2
    high: 1.5
  team_distribution:
    colocated: 1.0
    distributed: 1.25
  integration_complexity:
    low: 1.0
    medium: 1.15
    high: 1.35
  ...  
```

Save these updated values as `first-project-step-3-config.yaml` and then run the simulation again using these values as 

```bash
mcprojsim simulate first-project-step-3.yaml --seed 42 --minimal --config first-project-step-3-config.yaml
```

We do not repeat the full output but show only the summary as

```txt
<-- SKIP -->
Calendar Time Statistical Summary:
  Mean: 57.19 hours (8 working days)
  Median (P50): 56.85 hours
  Std Dev: 8.87 hours
  Minimum: 31.76 hours
  Maximum: 87.52 hours
Project Effort Statistical Summary:
  Mean: 57.19 person-hours (8 person-days)
  Median (P50): 56.85 person-hours
  Std Dev: 8.87 person-hours
  Minimum: 31.76 person-hours
  Maximum: 87.52 person-hours
```

As expected, the simulation shows slightly higher effort and longer calendar time.

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
      low: 2
      expected: 3
      high: 5
      unit: "days"
    uncertainty_factors:
      team_experience: "high"
      requirements_maturity: "medium"
  - id: "task_002"
    name: "Deploy site"
    estimate:
      low: 1
      expected: 2
      high: 4
      unit: "days"
    dependencies: ["task_001"]
    uncertainty_factors:
      team_experience: "medium"
      technical_complexity: "medium"
    risks:
      - id: "risk_002"
        name: "Hosting problem"
        probability: 0.15
        impact: 1.5     # bare float = hours; use impact.type/value/unit for other units
```

Again, run this as:

```bash
mcprojsim simulate first-project-step-4.yaml \
  --config first-project-step-3-config.yaml \
  --iterations 5000 --seed 42 
```

Example result summary:

{{!mcprojsim simulate examples/01_first_project/first-project-step-4.yaml --config examples/01_first_project/first-project-step-3-config.yaml --iterations 5000 --seed 42 --minimal}}


Notice what happened relative to Step 3:

- the project mean increased 
- the upper percentiles increased,
- the spread increased.

In this example the change was the added overall project risk and we kept the task risks the same. For that reason we do not see any change in the task effort but only in the overall calendar time for the project.

A new section, **Risk Impact Analysis**, also appears. It shows how often each risk triggered and how much it added on average. In this example, `risk_002` ("Hosting problem") triggered in about 15% of iterations, adding 1.5 hours when it did — matching the 0.15 probability and 1.5-hour impact we specified.

That is exactly what we expect when we add plausible delay events to the model. The file is not just more detailed. It is representing more of the actual uncertainty that the team believes exists.

## An alternative style: T-shirt sized estimates

So far, every task has used an explicit estimate range with `low`, `expected`, and `high`. That is often the best choice when the team is comfortable expressing estimates directly in days.

However, some teams think more naturally in relative sizing. They can say that one task is `S`, another is `M`, and another is `XL`, even when they do not yet want to commit to detailed numeric ranges.

`mcprojsim` supports that style directly.

### Step 5: use `t_shirt_size` instead of explicit ranges

In the source code, a task estimate may specify the field `t_shirt_size` instead of `expected` and the related range values. Validation accepts that form, and the simulation engine later resolves the symbolic size to concrete `low`, `expected`, and `high` values from the active configuration.

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


### Categories of T-shirt sizes

T-shirt sizes are organized into categories so that the same label (`M`, `L`, etc.) can have different meanings depending on the type of work. An `M` story and an `M` epic represent vastly different amounts of work, and the category structure keeps those scales separate.

The built-in categories cover the common levels of planning granularity in software delivery:

| Category | Typical use | Example `M` expected (hours) |
|---|---|---:|
| `bug` | Individual defects and small fixes | 40 |
| `story` | User-facing features and tasks (default) | 60 |
| `epic` | Groups of related stories | 240 |
| `business/program` | Larger business capabilities or programmes | 4 000 |
| `initiative` | Strategic initiatives spanning multiple programmes | 20 000 |

The default category is `story`. When a task specifies a bare size like `t_shirt_size: "M"`, it is resolved against the `story` category unless you override `t_shirt_size_default_category` in the configuration file.

Use a qualified form such as `t_shirt_size: "epic.M"` to reference a size from a specific category directly, regardless of the default.


### How T-shirt sizes are configured

If you want to use a custom configuration file with T-shirt estimates, add a `t_shirt_sizes` section like this to the configuration file:

```yaml
t_shirt_sizes:
  story:
    XS:
      low: 3
      expected: 5
      high: 15
    S:
      low: 5
      expected: 16
      high: 40
    M:
      low: 40
      expected: 60
      high: 120

t_shirt_size_default_category: story
```

The application ships with built-in mappings for multiple categories (`bug`, `story`, `epic`, `business`, `initiative`) and defaults bare sizes like `M` to the `story` category. In this example, `t_shirt_size_default_category: story` makes bare sizes use story-scale values instead.

If you use your own configuration file, it is merged onto built-in defaults. That means you do **not** need to redefine `t_shirt_sizes` unless you want to override defaults.

The simulation engine resolves each T-shirt label against the active merged configuration and raises an error only when the requested category/size is unknown.

This detail is important: `t_shirt_size` is not just a comment or a reporting label. It is a real input that must be backed by a configuration mapping.

In other words, you have two common options:

- run without `--config` and use built-in size mappings, or
- run with `--config` to override only the categories/sizes you want to change.

Run the T-shirt-sized example like this:

```bash
mcprojsim simulate examples/tshirt_walkthrough_project.yaml \
  --config examples/tshirt_walkthrough_config.yaml \
  --seed 42 --iterations 5000 --minimal
```

Example result summary:

{{!mcprojsim simulate examples/tshirt_walkthrough_project.yaml --config examples/tshirt_walkthrough_config.yaml --seed 42 --iterations 5000 --minimal}}

The interpretation is exactly the same as for explicit ranges. The only difference is how the task effort was expressed in the input file.

T-shirt sizes are especially useful early in planning, when the team can compare tasks relative to each other more easily than they can assign precise numeric ranges. Later, if needed, the team can replace those symbolic sizes with explicit estimate ranges for finer control.

## Another alternative style: Story Point estimates

Some teams prefer to estimate backlog items in Story Points rather than T-shirt sizes or explicit day ranges.

`mcprojsim` supports that style as another symbolic estimate form. In the input file you provide a `story_points` value, and during simulation the active configuration resolves it to a numeric `(low, expected, high)` range in the configured unit (default: days).

**Important:** Story point estimates must not include a `unit` field in the project file. The unit is determined by the configuration file's `story_point_unit` setting (default: `"days"`).

Story points was originally conceived as a way to model actual working time where 1 SP was eqal to 1 uninterrupted day of work (something that rarely happens in real life). Now, SP is an estimat calibrated to a specific team and story points are only valid within the same and stable team as their own "currency" were each team have different exchange rates between SP <--> days. The program have *one* exchange rate by default but that can easily be adjusted by supplying a different exchange rate in a config file as shown below


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

### Default Story Point

The built-in Story Points have the following mapping to time (in days)

```yaml
Story Points (unit: days):
  1:
    low: 0.5, expected: 1.0, high: 3.0
  2:
    low: 1.0, expected: 2.0, high: 4.0
  3:
    low: 1.5, expected: 3.0, high: 5.0
  5:
    low: 3.0, expected: 5.0, high: 8.0
  8:
    low: 5.0, expected: 8.0, high: 15.0
  13:
    low: 8.0, expected: 13.0, high: 21.0
  21:
    low: 13.0, expected: 21.0, high: 34.0
```


### How Story Points are configured

The built-in story point values cover the Fibonacci sequence 1, 2, 3, 5, 8, 13, 21. If you want to customize any of those mappings, add a `story_points` section to the configuration file:

```yaml
story_points:
  1:
    low: 0.5
    expected: 1
    high: 3
  2:
    low: 1
    expected: 2
    high: 4
  3:
    low: 1.5
    expected: 3
    high: 5
  5:
    low: 3
    expected: 5
    high: 8
  8:
    low: 5
    expected: 8
    high: 15
```

These are built-in defaults. If you provide a custom configuration file, you may override only the Story Point values you want to recalibrate for your team; the remaining built-in defaults stay available.

As with T-shirt sizes, a custom config file does not need to redefine `story_points` unless you are changing them.

Run the Story Point example like this:

```bash
mcprojsim simulate first-project-step-6.yaml \
--config  first-project-step-6-config.yaml \
--iterations 5000 --seed 42  --minimal
```

Example result summary:

{{!mcprojsim simulate examples/01_first_project/first-project-step-6.yaml --config examples/01_first_project/first-project-step-6-config.yaml --iterations 5000 --seed 42 --minimal}}

Story Points are useful when the team has a stable internal understanding of what `1`, `2`, `3`, `5`, `8`, `13`, or `21` mean, but that understanding does not translate directly to raw hours or days. The config file is where that team-specific calibration belongs.

<!-- pagebreak:b5 -->

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

The tiny examples in this chapter are teaching examples. The files in the `examples/01_first_project` directory show how the same ideas scale up.

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

