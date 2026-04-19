
# Exporters

## Overview

The exporters module converts a `SimulationResults` object into persistent output files. All three exporters — `JSONExporter`, `CSVExporter`, and `HTMLExporter` — expose the same design: a single static `export()` class method that writes directly to a file path. Choose JSON for downstream tooling and API integration, CSV for spreadsheet analysis, and HTML for human-readable reports that can be shared without any tooling. Sprint-planning results and the original `Project` definition are optional enrichments accepted by all three. The `include_historic_base` flag embeds baseline comparison data and is supported only by JSON and HTML; passing it to CSV raises a `ValueError`.

**When to use this module:** Write simulation output to disk from your own Python code, or extend a pipeline that consumes JSON, CSV, or HTML artefacts.

| Capability | Description |
|---|---|
| JSON export | Full results: percentiles, statistics, histogram, critical paths, risk summaries, sprint data |
| CSV export | Flat table: metrics, percentiles, critical paths, histogram bins, risk impact, resource diagnostics |
| HTML export | Self-contained visual report with embedded charts (requires `matplotlib`) |
| Sprint results embedding | All three exporters accept optional `SprintPlanningResults` |
| Historic baseline | `include_historic_base=True` embeds baseline comparison data (JSON and HTML only) |
| Config-driven output | Histogram bin count and critical-path report limit come from `Config.output` |

**Imports:**
```python
from mcprojsim.exporters import JSONExporter, CSVExporter, HTMLExporter
```

All exporters support histogram data, critical-path output, sprint-planning results, and historic-base data (when available). The histogram bin count defaults to 50 but is controlled by `config.output.number_bins`.

## `JSONExporter`

Exports comprehensive results including all percentiles, statistics, histogram data, critical paths, risk summaries, and sprint-planning data to JSON.

**Method:** `export(results, output_path, config=None, critical_path_limit=None, sprint_results=None, project=None, include_historic_base=False, full_cost_detail=False, fx_provider=None, target_budget=None, target_hours=None) -> None`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `results` | `SimulationResults` | required | Simulation results object. |
| `output_path` | `Path \| str` | required | File path for JSON output. |
| `config` | `Config \| None` | `None` | Active configuration; controls histogram bin count and other settings. |
| `critical_path_limit` | `int \| None` | `None` | Override number of critical paths to include (defaults to `config.output.critical_path_report_limit`). |
| `sprint_results` | `SprintPlanningResults \| None` | `None` | Sprint planning results to embed (optional). |
| `project` | `Project \| None` | `None` | Original project definition; enables richer output (optional). |
| `include_historic_base` | `bool` | `False` | Include historic baseline data when available. |
| `full_cost_detail` | `bool` | `False` | When `True`, includes per-task cost breakdowns and cost-distribution histograms in the JSON output. |
| `fx_provider` | `Any \| None` | `None` | Foreign-exchange rate provider for multi-currency cost output (optional). |
| `target_budget` | `float \| None` | `None` | Target budget for budget-confidence analysis in the output. |
| `target_hours` | `float \| None` | `None` | Target duration (hours) for joint probability analysis in the output. |

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

## `CSVExporter`

Exports results as a CSV table format: metrics, percentiles, critical paths, histogram data, risk impact, resource diagnostics, and sprint data.

**Method:** `export(results, output_path, project=None, config=None, critical_path_limit=None, sprint_results=None, fx_provider=None) -> None`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `results` | `SimulationResults` | required | Simulation results object. |
| `output_path` | `Path \| str` | required | File path for CSV output. |
| `project` | `Project \| None` | `None` | Original project definition (optional; enables per-task detail). |
| `config` | `Config \| None` | `None` | Active configuration; controls histogram bins and report limits. |
| `critical_path_limit` | `int \| None` | `None` | Override number of critical paths to include. |
| `sprint_results` | `SprintPlanningResults \| None` | `None` | Sprint planning results to embed (optional). |
| `fx_provider` | `Any \| None` | `None` | Foreign-exchange rate provider for multi-currency cost output (optional). |

**Example:**

```python
from mcprojsim.exporters import CSVExporter

CSVExporter.export(results, "results.csv", config=config)
```

## `HTMLExporter`

Exports a formatted, interactive HTML report with thermometers, percentile tables, charts (using matplotlib), critical-path analysis, staffing recommendations, and sprint-planning traceability.

**Method:** `export(results, output_path, project=None, config=None, critical_path_limit=None, sprint_results=None, fx_provider=None) -> None`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `results` | `SimulationResults` | required | Simulation results object. |
| `output_path` | `Path \| str` | required | File path for HTML output. |
| `project` | `Project \| None` | `None` | Original project definition; unlocks richer task and effort display (optional). |
| `config` | `Config \| None` | `None` | Active configuration; used for T-shirt size labels and histogram bins (optional). |
| `critical_path_limit` | `int \| None` | `None` | Override number of critical paths to include. |
| `sprint_results` | `SprintPlanningResults \| None` | `None` | Sprint planning results to embed (optional). |
| `fx_provider` | `Any \| None` | `None` | Foreign-exchange rate provider for multi-currency cost output (optional). |

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

