# API Reference

This page documents the main Python API intended for library consumers.

The most stable entry points are:

- Root package imports from `mcprojsim`
- Data models from `mcprojsim.models`
- File parsers from `mcprojsim.parsers`
- Exporters from `mcprojsim.exporters`
- Analysis helpers from `mcprojsim.analysis`
- Sprint-planning APIs from `mcprojsim.planning` and `mcprojsim.models.sprint_simulation`
- Configuration from `mcprojsim.config`

Internal helper modules under `mcprojsim.simulation` and `mcprojsim.utils` are usable, but they are less central to the day-to-day library workflow.

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

JSONExporter.export(results, "results.json")
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

## Core API

### `SimulationEngine`

Main entry point for Monte Carlo simulation.

```python
from mcprojsim import SimulationEngine

engine = SimulationEngine(
    iterations=10000,
    random_seed=42,
    config=config,
    show_progress=True,
)

results = engine.run(project)
```

Key constructor parameters:

- `iterations`: Number of Monte Carlo iterations
- `random_seed`: Seed for reproducible sampling
- `config`: `Config` object used for uncertainty multipliers, T-shirt mappings, and Story Point mappings
- `show_progress`: Whether to print progress updates during long runs

Key method:

- `run(project: Project) -> SimulationResults`

### `SimulationResults`

Holds the output of a simulation run, including durations, summary statistics, percentiles, and critical-path frequency data.

Useful attributes:

- `project_name`
- `iterations`
- `durations`
- `task_durations`
- `mean`
- `median`
- `std_dev`
- `min_duration`
- `max_duration`
- `percentiles`

Useful methods:

- `calculate_statistics()`
- `percentile(p: int) -> float`
- `effort_percentile(p: int) -> float`
- `get_critical_path() -> dict[str, float]`
- `get_critical_path_sequences(top_n: int | None = None) -> list[CriticalPathRecord]`
- `get_most_frequent_critical_path() -> CriticalPathRecord | None`
- `get_histogram_data(bins: int = 50)`
- `probability_of_completion(target_hours: float) -> float`
- `total_effort_hours() -> float`
- `get_risk_impact_summary() -> dict[str, dict[str, float]]`
- `to_dict() -> dict[str, Any]`

```python
print(f"Mean: {results.mean:.2f}")
print(f"Median: {results.median:.2f}")
print(f"P80: {results.percentile(80):.2f}")

criticality = results.get_critical_path()
for task_id, value in criticality.items():
    print(task_id, value)
```

### `SprintSimulationEngine`

Entry point for sprint-planning Monte Carlo simulation.

Import path:

```python
from mcprojsim.planning.sprint_engine import SprintSimulationEngine
```

Constructor parameters:

- `iterations`
- `random_seed`

Key method:

- `run(project: Project) -> SprintPlanningResults`

### `SprintPlanningResults`

Result model for sprint-planning simulations.

Import path:

```python
from mcprojsim.models.sprint_simulation import SprintPlanningResults
```

Useful methods:

- `calculate_statistics()`
- `percentile(p: int) -> float`
- `date_percentile(p: int) -> date | None`
- `delivery_date_for_sprints(sprint_count: float) -> date | None`
- `to_dict() -> dict[str, Any]`

## Project Models

The data model layer is richer than the previous version of this page suggested.

### `Project`

Represents the complete project definition.

Key fields:

- `project`: `ProjectMetadata`
- `tasks`: `list[Task]`
- `project_risks`: `list[Risk]`
- `resources`: `list[ResourceSpec]`
- `calendars`: `list[CalendarSpec]`
- `sprint_planning`: `SprintPlanningSpec | None`

Key method:

- `get_task_by_id(task_id: str) -> Task | None`

### `ProjectMetadata`

Stores top-level project settings such as:

- `name`
- `description`
- `start_date`
- `currency`
- `confidence_levels`
- `probability_red_threshold`
- `probability_green_threshold`
- `hours_per_day`
- `distribution`
- `team_size`

### `Task`

Represents a single work item in the project network.

Key fields:

- `id`
- `name`
- `description`
- `estimate`: `TaskEstimate`
- `dependencies`: `list[str]`
- `uncertainty_factors`: `UncertaintyFactors | None`
- `resources`: `list[str]`
- `risks`: `list[Risk]`

Key method:

- `has_dependency(task_id: str) -> bool`

### `TaskEstimate`

Supports four estimation styles:

- Triangular estimates via `low`, `expected`, and `high`
- Log-normal estimates via `low`, `expected`, and `high`
- T-shirt-sized estimates via `t_shirt_size`
- Story Point estimates via `story_points`

Key fields:

- `distribution`
- `low`
- `expected`
- `high`
- `t_shirt_size`
- `story_points`
- `unit`

### `Risk` and `RiskImpact`

Represents task-level or project-level risk.

`Risk` supports:

- `probability`
- `impact` as either a numeric absolute duration or a structured `RiskImpact`
- `description`

`RiskImpact` supports:

- `type`: percentage or absolute
- `value`
- `unit`

Useful method:

- `Risk.get_impact_value(base_duration: float = 0.0) -> float`

### `UncertaintyFactors`

Represents factor levels used to adjust base task duration.

Supported fields:

- `team_experience`
- `requirements_maturity`
- `technical_complexity`
- `team_distribution`
- `integration_complexity`

### Enums

The following enums are also part of the model API:

- `DistributionType`
- `ImpactType`
- `EffortUnit`

## Parsers

### `YAMLParser`

Parses YAML project files into `Project` objects.

Methods:

- `parse_file(file_path) -> Project`
- `parse_dict(data) -> Project`
- `validate_file(file_path) -> tuple[bool, str]`

```python
from mcprojsim.parsers import YAMLParser

parser = YAMLParser()
project = parser.parse_file("project.yaml")
is_valid, error = parser.validate_file("project.yaml")
```

### `TOMLParser`

Same interface as `YAMLParser`, but for TOML project files.

```python
from mcprojsim.parsers import TOMLParser

parser = TOMLParser()
project = parser.parse_file("project.toml")
```

## Configuration

### `Config`

Application configuration for simulation settings, output settings, uncertainty-factor multipliers, T-shirt-size mappings, and Story Point mappings.

Important methods:

- `Config.load_from_file(config_path) -> Config`
- `Config.get_default() -> Config`
- `get_uncertainty_multiplier(factor_name, level) -> float`
- `get_t_shirt_size(size) -> TShirtSizeConfig | None`
- `get_t_shirt_categories() -> list[str]`
- `resolve_t_shirt_size(size) -> TShirtSizeConfig`
- `get_story_point(points) -> StoryPointConfig | None`
- `get_lognormal_high_z_value() -> float`

Important nested models:

- `SimulationConfig`
- `OutputConfig`
- `TShirtSizeConfig`
- `StoryPointConfig`
- `UncertaintyFactorConfig`

```python
from mcprojsim.config import Config

config = Config.load_from_file("config.yaml")

multiplier = config.get_uncertainty_multiplier("team_experience", "high")
size = config.get_t_shirt_size("L")
epic_size = config.resolve_t_shirt_size("epic.M")
categories = config.get_t_shirt_categories()
story_points = config.get_story_point(5)
```

## Exporters

### `JSONExporter`

Exports summary results, percentiles, histogram data, and critical-path output to JSON.

Method:

- `export(results, output_path, config=None, critical_path_limit=None, sprint_results=None) -> None`

### `CSVExporter`

Exports summary results, percentiles, critical path, and histogram table to CSV.

Method:

- `export(results, output_path, config=None, critical_path_limit=None, sprint_results=None) -> None`

### `HTMLExporter`

Exports a formatted HTML report.

Method:

- `export(results, output_path, project=None, config=None, critical_path_limit=None, sprint_results=None) -> None`

If `project` is provided, the report can show richer task effort information. If `config` is also provided, T-shirt-sized tasks and Story Point tasks are rendered using the active simulation configuration rather than only default mappings.

```python
from mcprojsim.exporters import HTMLExporter

HTMLExporter.export(results, "results.html", project=project, config=config)
```

## Analysis Helpers

These APIs are currently exported but were missing from the previous documentation page.

### `StatisticalAnalyzer`

Convenience helpers for working directly with duration arrays.

Methods:

- `calculate_statistics(durations) -> dict[str, float]`
- `calculate_percentiles(durations, percentiles) -> dict[int, float]`
- `confidence_interval(durations, confidence=0.95) -> tuple[float, float]`

### `SensitivityAnalyzer`

Provides task-to-project sensitivity analysis based on simulated task durations.

Methods:

- `calculate_correlations(results: SimulationResults) -> dict[str, float]`
- `get_top_contributors(results: SimulationResults, n: int = 10)`

### `CriticalPathAnalyzer`

Thin analysis helper around `SimulationResults.get_critical_path()`.

Methods:

- `get_criticality_index(results: SimulationResults) -> dict[str, float]`
- `get_most_critical_tasks(results: SimulationResults, threshold: float = 0.5) -> list[str]`
- `get_most_frequent_paths(results: SimulationResults, top_n: int | None = None) -> list[CriticalPathRecord]`

### `StaffingAnalyzer`

Provides staffing recommendations and team-size tables using simulation results plus staffing config.

Methods:

- `calculate_staffing_table(results: SimulationResults, config: Config) -> list[StaffingRow]`
- `recommend_team_size(results: SimulationResults, config: Config) -> list[StaffingRecommendation]`

## Validation Utility

### `Validator`

Available from `mcprojsim.utils`.

Method:

- `validate_file(file_path) -> tuple[bool, str]`

This is a simple convenience wrapper that selects `YAMLParser` or `TOMLParser` based on file extension.

```python
from mcprojsim.utils import Validator

is_valid, error = Validator.validate_file("project.yaml")
```

### `setup_logging`

Also exported from `mcprojsim.utils`:

```python
from mcprojsim.utils import setup_logging
```

## Not a Stable User-Facing API?

The following modules are currently imported in `mcprojsim.simulation` and `mcprojsim.utils`, but they are more internal and subject to change without deprecation. They are not intended for direct use by library consumers, but they are technically accessible if you want to experiment or build on top of them.

- `mcprojsim.simulation.distributions`
- `mcprojsim.simulation.scheduler`
- `mcprojsim.simulation.risk_evaluator`
- `mcprojsim.utils.logging`


## Natural Language Parser

### `NLProjectParser`

Converts semi-structured, plain-text project descriptions into valid mcprojsim YAML project files. Also available via the `mcprojsim generate` CLI command and the MCP server's `generate_project_file` tool.

```python
from mcprojsim.nl_parser import NLProjectParser

parser = NLProjectParser()
```

Methods:

- `parse(text: str) -> ParsedProject` — extract project metadata and tasks from a text description
- `to_yaml(project: ParsedProject) -> str` — render a `ParsedProject` as a valid YAML project file
- `parse_and_generate(text: str) -> str` — convenience wrapper that calls `parse` then `to_yaml`

Supported input patterns:

- `Project name: My Project`
- `Start date: 2026-04-01`
- `Task 1: Backend API` followed by bullet points
- `Size: M` or `Size XL` (T-shirt sizes)
- `Story points: 5`
- `Estimate: 3/5/10 days` (low/expected/high)
- `Depends on Task 1, Task 3`

```python
description = """
Project name: Website Redesign
Start date: 2026-06-01

Task 1: Design mockups
- Size: M

Task 2: Frontend implementation
- Size: L
- Depends on Task 1
"""

yaml_output = parser.parse_and_generate(description)
```

### Data classes

- `ParsedProject` — extracted project-level data (`name`, `start_date`, `hours_per_day`, `tasks`, `confidence_levels`)
- `ParsedTask` — extracted task data (`name`, `t_shirt_size`, `story_points`, `low_estimate`/`expected_estimate`/`high_estimate`, `dependency_refs`)
- `ParsedResource` — extracted resource data (`name`, `availability`, `experience_level`, `productivity_level`, `calendar`, `sickness_prob`, `planned_absence`)
- `ParsedCalendar` — extracted calendar data (`id`, `work_hours_per_day`, `work_days`, `holidays`)
- `ParsedSprintPlanning` — extracted sprint-planning settings (`enabled`, `sprint_length_weeks`, `capacity_mode`, `history`, ...)
