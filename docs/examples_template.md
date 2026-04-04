# Examples

- [Examples](#examples)
  - [Basic Project with Explicit Estimates](#basic-project-with-explicit-estimates)
  - [T-Shirt Sizing](#t-shirt-sizing)
  - [Story Points](#story-points)
  - [Complex Project with Risks](#complex-project-with-risks)
  - [Log-Normal Distribution](#log-normal-distribution)
  - [Constrained Scheduling with `team_size`](#constrained-scheduling-with-team_size)
  - [Constrained Scheduling with Explicit Resources and Calendars](#constrained-scheduling-with-explicit-resources-and-calendars)
  - [Natural Language Project Generation](#natural-language-project-generation)
    - [Basic text input (dependency-only)](#basic-text-input-dependency-only)
    - [Text input with resources and calendars (constrained)](#text-input-with-resources-and-calendars-constrained)
  - [Sprint Planning](#sprint-planning)
    - [Minimal story-point forecast](#minimal-story-point-forecast)
    - [Advanced sprint forecast](#advanced-sprint-forecast)
    - [Tasks mode and external history](#tasks-mode-and-external-history)
  - [Running Examples](#running-examples)
    - [Common CLI options](#common-cli-options)
    - [Additional example files](#additional-example-files)


This page provides practical examples of project definitions, progressing from simple to complex. Each example includes real simulation output. For complete specification details, see the [Formal Grammar](grammar.md).

All outputs below were generated with `--minimal --seed 42` for reproducibility. Use `--seed` to get identical results on your machine.



## Basic Project with Explicit Estimates

A simple project with two sequential tasks using three-point (min / most likely / max) estimates. This is the simplest useful project definition.

{{file:examples/quickstart_example.yaml}}

{{run:poetry run mcprojsim simulate examples/quickstart_example.yaml --minimal --seed 42}}

Key observations: two sequential tasks, no parallelism (`Max Parallel Tasks: 1`), `dependency_only` scheduling.

See `examples/quickstart_example.yaml` in the repository.



## T-Shirt Sizing

For quick estimation using relative sizes (`XS`, `S`, `M`, `L`, `XL`, `XXL`). T-shirt sizes map to default effort ranges that are configurable via the [configuration file](user_guide/task_estimation.md#t-shirt-size-estimates).

{{file:examples/tshirt_sizing_project.yaml}}

{{run:poetry run mcprojsim simulate examples/tshirt_sizing_project.yaml --minimal --seed 42}}

Key observations: two independent starting tasks yield `Max Parallel Tasks: 2`. The wide P10–P99 spread (938–1590 working days) reflects the inherent uncertainty of T-shirt sizing for large effort items.

Note: T-shirt size and story point estimates must **not** include a `unit` field in the project file. The unit is controlled by the configuration.

See `examples/tshirt_sizing_project.yaml` in the repository.



## Story Points

For agile-style relative estimation using calibrated story point mappings. Default mappings are configurable via the [configuration file](user_guide/task_estimation.md#story-point-estimates).

{{file:examples/story_points_walkthrough_project.yaml}}

{{run:poetry run mcprojsim simulate examples/story_points_walkthrough_project.yaml --minimal --table --seed 42}}

Key observations: small project with low uncertainty — the CV is only 0.15 and P50 to P90 spans just 3 working days.

See `examples/story_points_walkthrough_project.yaml` in the repository.



## Complex Project with Risks

A realistic project with 8 tasks, complex dependencies, uncertainty factors, and both task-level and project-level risks.

{{file:examples/sample_project.yaml}}

{{run:poetry run mcprojsim simulate examples/sample_project.yaml --minimal --seed 42}}

Key observations:

- Effort and calendar time differ (`86 person-days` effort vs `73 working days` calendar) because some tasks run in parallel.
- The positive skewness (0.48) shows a right-skewed distribution — risks and uncertainty create a longer tail toward delays.

See `examples/sample_project.yaml` in the repository.



## Log-Normal Distribution

For tasks where extreme overruns are more probable than a triangular distribution predicts:

```yaml
tasks:
  - id: "research"
    name: "Research new technology"
    estimate:
      distribution: "lognormal"
      low: 2
      expected: 5
      high: 14
      unit: "days"
    dependencies: []
```

The shifted log-normal distribution produces a heavier right tail, making it
suitable for research, exploration, or tasks with high uncertainty about upper
bounds.



## Constrained Scheduling with `team_size`

The simplest way to activate resource-constrained scheduling: add `team_size` to the project metadata. This auto-generates default resources.

{{file:examples/team_size_demo_with_team_size.yaml}}

{{run:poetry run mcprojsim simulate examples/team_size_demo_with_team_size.yaml --minimal --seed 42}}

Compare with the same project **without** `team_size` (dependency-only mode):

{{run:poetry run mcprojsim simulate examples/team_size_demo_base.yaml --minimal --seed 42}}

Key observations:

- Adding `team_size` switches from `dependency_only` to `resource_constrained`.
- Calendar time increases significantly (P50: 17 → 67 working days) because resources are assigned one at a time by default (`max_resources: 1`), and working calendars now account for weekends and non-working hours.
- Effort remains the same — only elapsed calendar time changes.

See `examples/team_size_demo_base.yaml` and `examples/team_size_demo_with_team_size.yaml` in the repository.



## Constrained Scheduling with Explicit Resources and Calendars

For full control, define resources with individual skill levels, productivity, sickness probability, and planned absences. Attach resources to named calendars with custom work patterns.

{{file:examples/constrained_portal.yaml}}

{{run:poetry run mcprojsim simulate examples/constrained_portal.yaml --minimal --seed 42 --iterations 200}}

Key observations:

- `resources` on `task_002` restricts it to only `alice` and `bob`.
- `max_resources: 2` allows both to work in parallel on that task.
- `min_experience_level: 2` filters out any resource below that skill tier.
- `sickness_prob` introduces stochastic sick days that vary across iterations.
- `planned_absence` blocks specific dates deterministically.
- Bob's `part_time` calendar (6 hours/day, Mon–Thu) reduces his available capacity.
- Calendar time (78 working days) is much larger than effort (22 person-days) due to calendar constraints, weekends, holidays, and sickness.

For a full constrained walkthrough with incremental complexity, see the [Constrained Scheduling Guide](user_guide/constrained.md).



## Natural Language Project Generation

The `generate` command converts plain-text project descriptions into valid YAML project files. This lets you sketch a project quickly and iterate.

### Basic text input (dependency-only)

{{file:examples/nl_example.txt}}

{{run:poetry run mcprojsim generate examples/nl_example.txt -o .build/gen-examples/nl_project.yaml >/dev/null 2>&1 && poetry run mcprojsim simulate .build/gen-examples/nl_project.yaml --minimal --seed 42}}

### Text input with resources and calendars (constrained)

The `generate` command also supports resource definitions, calendar definitions, and task-level resource constraints:

{{file:examples/nl_constrained_example.txt}}

{{run:poetry run mcprojsim generate examples/nl_constrained_example.txt -o .build/gen-examples/nl_constrained_project.yaml >/dev/null 2>&1 && poetry run mcprojsim simulate .build/gen-examples/nl_constrained_project.yaml --minimal --seed 42 --iterations 200}}

The generated YAML includes full `resources:` and `calendars:` sections. Use `--validate-only` to check your description before generating:

{{run:poetry run mcprojsim generate examples/nl_constrained_example.txt --validate-only}}

See `examples/nl_example.txt` and `examples/nl_constrained_example.txt` in the repository.



## Sprint Planning

Sprint-planning examples combine the normal task simulation with a sprint-based forecast built from historical sprint results.

### Minimal story-point forecast

{{file:examples/sprint_planning_minimal.yaml}}

{{run:poetry run mcprojsim simulate examples/sprint_planning_minimal.yaml --minimal --seed 42}}

Key observations:

- Uses `story_points` as the sprint-capacity unit.
- Three historical sprint rows are enough to start forecasting.
- The sprint summary shows commitment guidance and sprint-count percentiles alongside the regular project forecast.

### Advanced sprint forecast

{{file:examples/sprint_planning_advanced.yaml}}

{{run:poetry run mcprojsim simulate examples/sprint_planning_advanced.yaml --minimal --table --seed 42 --iterations 200}}

Key observations:

- `future_sprint_overrides` model known upcoming capacity reductions.
- `volatility_overlay` adds random sprint-level disruption.
- `spillover` plus `spillover_probability_override` let larger items partially carry into later sprints.

### Tasks mode and external history

Tasks mode is useful for service or maintenance backlogs where items are intentionally kept to similar size.

{{file:examples/sprint_planning_tasks.yaml}}

{{run:poetry run mcprojsim simulate examples/sprint_planning_tasks.yaml --minimal --seed 42}}

The same sprint-planning workflow can load history from external data files:

{{file:examples/sprint_planning_external_json.yaml}}

{{file:examples/sprint_planning_history.json}}

{{file:examples/sprint_planning_external_csv.toml}}

{{file:examples/sprint_planning_history.csv}}

Natural-language input also supports sprint-planning sections:

{{file:examples/sprint_planning_nl.txt}}

{{run:poetry run mcprojsim generate examples/sprint_planning_nl.txt -o .build/gen-examples/sprint_planning_nl.yaml >/dev/null 2>&1 && poetry run mcprojsim simulate .build/gen-examples/sprint_planning_nl.yaml --minimal --seed 42}}



## Running Examples

### Common CLI options

```bash
# Basic simulation
mcprojsim simulate examples/quickstart_example.yaml

# Minimal output for quick overview
mcprojsim simulate examples/sample_project.yaml --minimal

# Reproducible results with a seed
mcprojsim simulate examples/sample_project.yaml --seed 42

# More iterations for higher accuracy
mcprojsim simulate examples/sample_project.yaml --iterations 50000

# With custom config (uncertainty factors, output settings)
mcprojsim simulate examples/sample_project.yaml \
  --config examples/sample_config.yaml

# Tabular output format
mcprojsim simulate examples/sample_project.yaml --table

# Check probability of hitting a target date
mcprojsim simulate examples/sample_project.yaml \
  --target-date 2026-03-15

# Show top 5 critical path sequences
mcprojsim simulate examples/sample_project.yaml \
  --critical-paths 5

# Export to multiple formats
mcprojsim simulate examples/sample_project.yaml \
  -f json,csv,html -o results/portal
```

### Additional example files

| File | Demonstrates |
|---|---|
| `quickstart_example.yaml` | Basic explicit estimates |
| `tshirt_sizing_project.yaml` | T-shirt size estimation with risks |
| `story_points_walkthrough_project.yaml` | Story point estimation |
| `sample_project.yaml` | Complex project with risks and dependencies |
| `project_with_custom_thresholds.yaml` | Custom probability thresholds |
| `team_size_demo_base.yaml` | Dependency-only baseline |
| `team_size_demo_with_team_size.yaml` | `team_size` constrained scheduling |
| `resource_cap_small_task.yaml` | Auto-capping on short tasks |
| `resource_cap_large_task.yaml` | Global coordination cap on large tasks |
| `sprint_planning_minimal.yaml` | Minimal story-point sprint forecast |
| `sprint_planning_advanced.yaml` | Advanced sprint forecast with spillover, volatility, and overrides |
| `sprint_planning_tasks.yaml` | Throughput-style sprint planning in `tasks` mode |
| `sprint_planning_external_json.yaml` | YAML project loading external JSON sprint history |
| `sprint_planning_external_csv.toml` | TOML project loading external CSV sprint history |
| `sprint_planning_nl.txt` | Natural-language sprint planning input |
| `nl_example.txt` | Natural language input (basic) |
| `nl_constrained_example.txt` | Natural language input with resources |
| `sample_config.yaml` | Custom configuration file |
