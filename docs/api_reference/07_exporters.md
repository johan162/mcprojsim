
## Exporters

All exporters support histogram data, critical-path output, sprint-planning results, and historic-base data (when available). The histogram bin count defaults to 50 but is controlled by `config.output.histogram_bins`.

### `JSONExporter`

Exports comprehensive results including all percentiles, statistics, histogram data, critical paths, risk summaries, and sprint-planning data to JSON.

**Method:**

- `export(results: SimulationResults, output_path: Path | str, config: Config | None = None, critical_path_limit: int | None = None, sprint_results: SprintPlanningResults | None = None, project: Project | None = None, include_historic_base: bool = False) -> None`

**Parameters:**

- `results` — Simulation results object
- `output_path` — File path for JSON output
- `config` — Active configuration (used for histogram bin count and other settings)
- `critical_path_limit` — Override number of critical paths to include (default from config)
- `sprint_results` — Sprint planning results (optional)
- `project` — Original project definition (optional; enables richer output)
- `include_historic_base` — Include historic baseline data if available

**Example:**

```python
from mcprojsim.exporters import JSONExporter

JSONExporter.export(
    results,
    "results.json",
    config=config,
    project=project,
    critical_path_limit=5,
    sprint_results=sprint_results,
)
```

### `CSVExporter`

Exports results as a CSV table format: metrics, percentiles, critical paths, histogram data, risk impact, resource diagnostics, and sprint data.

**Method:**

- `export(results: SimulationResults, output_path: Path | str, config: Config | None = None, critical_path_limit: int | None = None, sprint_results: SprintPlanningResults | None = None) -> None`

**Example:**

```python
from mcprojsim.exporters import CSVExporter

CSVExporter.export(results, "results.csv", config=config)
```

### `HTMLExporter`

Exports a formatted, interactive HTML report with thermometers, percentile tables, charts (using matplotlib), critical-path analysis, staffing recommendations, and sprint-planning traceability.

**Method:**

- `export(results: SimulationResults, output_path: Path | str, project: Project | None = None, config: Config | None = None, critical_path_limit: int | None = None, sprint_results: SprintPlanningResults | None = None, include_historic_base: bool = False) -> None`

**Key features when `project` and `config` are provided:**

- T-shirt-sized tasks are rendered with the active configuration labels
- Story-point tasks show the configured hour ranges
- Task descriptions and dependencies are included
- Effort data is shown per task

**Example:**

```python
from mcprojsim.exporters import HTMLExporter

HTMLExporter.export(
    results,
    "report.html",
    project=project,
    config=config,
    critical_path_limit=10,
    sprint_results=sprint_results,
    include_historic_base=True
)
```

