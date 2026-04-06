# API Reference

This page documents the main Python API intended for library consumers. For installation and first steps, see the [Quickstart](../quickstart.md).

The most stable entry points are:

- **Root package imports** from `mcprojsim` — Quick-start for common workflows
- **Data models** from `mcprojsim.models` — Project structure, tasks, risks, estimates
- **File parsers** from `mcprojsim.parsers` — Load YAML/TOML project files
- **Simulation engine** from `mcprojsim` — Run Monte Carlo schedule simulations
- **Exporters** from `mcprojsim.exporters` — Generate JSON, CSV, and HTML reports
- **Configuration** from `mcprojsim.config` — Simulation settings, uncertainty factors, estimate mappings
- **Analysis helpers** from `mcprojsim.analysis` — Statistical, sensitivity, critical-path, and staffing analysis
- **Sprint-planning APIs** from `mcprojsim.planning` and `mcprojsim.models.sprint_simulation` — Forecast sprint-based delivery
- **Natural language parser** from `mcprojsim.nl_parser` — Convert text descriptions to project files

!!! note "Internal modules"
    Modules under `mcprojsim.simulation` (distributions, scheduler, risk_evaluator) and `mcprojsim.utils` are accessible but considered internal. They may change without deprecation notice.

## Key Concepts

Before diving into the API, it helps to understand four concepts that mcprojsim distinguishes:

**Elapsed duration vs total effort.** *Elapsed duration* is the calendar time from project start to finish — what a Gantt chart shows. *Total effort* is the sum of all person-hours across every task, regardless of parallelism. A 100-hour project done by two people in parallel has ~50 hours elapsed duration but 100 hours of effort. `SimulationResults.mean` and `.percentile()` report elapsed duration; `.total_effort_hours()`, `.effort_percentile()`, and `.effort_durations` report effort.

**Dependency-only vs resource-constrained scheduling.** When a project defines no resources, the scheduler runs in *dependency-only* mode: tasks start as soon as their predecessors finish, with unlimited parallelism. When resources are defined, *constrained scheduling* activates: tasks compete for finite resource slots, potentially queuing behind other work. Check `results.schedule_mode` and `results.resource_constraints_active` to see which mode was used.

**Two-pass scheduling.** An optional extension of constrained scheduling. Pass 1 runs a smaller batch of iterations with simple greedy dispatch to rank tasks by criticality index. Pass 2 re-runs the full simulation using those ranks as scheduling priorities. Enable via `SimulationEngine(two_pass=True)` or `config.constrained_scheduling.assignment_mode = "criticality_two_pass"`. Results include a `two_pass_trace` with pass-1 vs pass-2 comparison data.

**Coordination overhead / team size.** When `project.project.team_size` is set, mcprojsim applies Brooks's Law–inspired communication overhead: larger teams lose a fraction of capacity to coordination. The staffing analyzer models this via `communication_overhead` and `min_individual_productivity` parameters per experience profile.

## Root Package

The root package currently exports:

- `Project`
- `Task`
- `Risk`
- `SimulationEngine`
- `__version__`

```python
from mcprojsim import Project, Task, Risk, SimulationEngine, __version__
```

Use these imports when you want the shortest path for common programmatic usage.

## Simulation Workflow

The standard schedule-simulation workflow is:

1. Load a project definition with `YAMLParser` or `TOMLParser`
2. Optionally load a `Config`
3. Run `SimulationEngine`
4. Inspect `SimulationResults`
5. Export the results if needed

```python
from mcprojsim import SimulationEngine
from mcprojsim.config import Config
from mcprojsim.parsers import YAMLParser
from mcprojsim.exporters import JSONExporter, HTMLExporter

project = YAMLParser().parse_file("project.yaml")
config = Config.load_from_file("config.yaml")

engine = SimulationEngine(
    iterations=10000,
    random_seed=42,
    config=config,
    show_progress=True,
)
results = engine.run(project)

print(results.mean)
print(results.percentile(90))
print(results.get_critical_path())

JSONExporter.export(results, "results.json", config=config, project=project)
HTMLExporter.export(results, "results.html", project=project, config=config)
```

Sprint-planning workflow (when `project.sprint_planning.enabled` is true):

1. Load a `Project`
2. Run `SprintSimulationEngine`
3. Inspect `SprintPlanningResults`

```python
from mcprojsim.parsers import YAMLParser
from mcprojsim.planning.sprint_engine import SprintSimulationEngine

project = YAMLParser().parse_file("sprint_project.yaml")
engine = SprintSimulationEngine(iterations=5000, random_seed=42)
results = engine.run(project)

print(results.mean)
print(results.percentile(90))
print(results.date_percentile(90))
```

