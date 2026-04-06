
## Exporters

All exporters support histogram data, critical-path output, sprint-planning results, and historic-base data (when available). The histogram bin count defaults to 50 but is controlled by `config.output.histogram_bins`.

### `JSONExporter`

Exports comprehensive results including all percentiles, statistics, histogram data, critical paths, risk summaries, and sprint-planning data to JSON.

**Method:** `export(results, output_path, config=None, critical_path_limit=None, sprint_results=None, project=None, include_historic_base=False) -> None`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `results` | `SimulationResults` | required | Simulation results object. |
| `output_path` | `Path \| str` | required | File path for JSON output. |
| `config` | `Config \| None` | `None` | Active configuration; controls histogram bin count and other settings. |
| `critical_path_limit` | `int \| None` | `None` | Override number of critical paths to include (defaults to `config.output.critical_path_report_limit`). |
| `sprint_results` | `SprintPlanningResults \| None` | `None` | Sprint planning results to embed (optional). |
| `project` | `Project \| None` | `None` | Original project definition; enables richer output (optional). |
| `include_historic_base` | `bool` | `False` | Include historic baseline data when available. |

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

**Method:** `export(results, output_path, config=None, critical_path_limit=None, sprint_results=None) -> None`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `results` | `SimulationResults` | required | Simulation results object. |
| `output_path` | `Path \| str` | required | File path for CSV output. |
| `config` | `Config \| None` | `None` | Active configuration; controls histogram bins and report limits. |
| `critical_path_limit` | `int \| None` | `None` | Override number of critical paths to include. |
| `sprint_results` | `SprintPlanningResults \| None` | `None` | Sprint planning results to embed (optional). |

**Example:**

```python
from mcprojsim.exporters import CSVExporter

CSVExporter.export(results, "results.csv", config=config)
```

### `HTMLExporter`

Exports a formatted, interactive HTML report with thermometers, percentile tables, charts (using matplotlib), critical-path analysis, staffing recommendations, and sprint-planning traceability.

**Method:** `export(results, output_path, project=None, config=None, critical_path_limit=None, sprint_results=None, include_historic_base=False) -> None`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `results` | `SimulationResults` | required | Simulation results object. |
| `output_path` | `Path \| str` | required | File path for HTML output. |
| `project` | `Project \| None` | `None` | Original project definition; unlocks richer task and effort display (optional). |
| `config` | `Config \| None` | `None` | Active configuration; used for T-shirt size labels and histogram bins (optional). |
| `critical_path_limit` | `int \| None` | `None` | Override number of critical paths to include. |
| `sprint_results` | `SprintPlanningResults \| None` | `None` | Sprint planning results to embed (optional). |
| `include_historic_base` | `bool` | `False` | Include historic baseline data when available. |

**When `project` and `config` are provided:**

- T-shirt-sized tasks are rendered with the active configuration labels.
- Story-point tasks show the configured hour ranges.
- Task descriptions and dependencies are included.
- Effort data is shown per task.

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

