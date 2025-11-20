# API Reference

## Core Classes

### SimulationEngine

Main engine for running Monte Carlo simulations.

```python
from mcprojsim import SimulationEngine

engine = SimulationEngine(
    iterations=10000,
    random_seed=42,
    show_progress=True
)

results = engine.run(project)
```

**Parameters:**
- `iterations` (int): Number of Monte Carlo iterations (default: 10000)
- `random_seed` (Optional[int]): Random seed for reproducibility
- `config` (Optional[Config]): Configuration object
- `show_progress` (bool): Show progress updates (default: True)

**Methods:**
- `run(project: Project) -> SimulationResults`: Run simulation and return results

### Project

Project definition with tasks and risks.

```python
from mcprojsim.models import Project
from mcprojsim.parsers import YAMLParser

parser = YAMLParser()
project = parser.parse_file("project.yaml")
```

### SimulationResults

Results from Monte Carlo simulation.

```python
# Access statistics
print(f"Mean: {results.mean}")
print(f"Median: {results.median}")
print(f"Std Dev: {results.std_dev}")

# Get percentiles
p80 = results.percentile(80)
p90 = results.percentile(90)

# Get critical path
critical_path = results.get_critical_path()
for task_id, criticality in critical_path.items():
    print(f"{task_id}: {criticality:.2%}")

# Get histogram data
bin_edges, counts = results.get_histogram_data(bins=50)
```

## Parsers

### YAMLParser

Parse YAML project files.

```python
from mcprojsim.parsers import YAMLParser

parser = YAMLParser()

# Parse file
project = parser.parse_file("project.yaml")

# Validate file
is_valid, error = parser.validate_file("project.yaml")
```

### TOMLParser

Parse TOML project files.

```python
from mcprojsim.parsers import TOMLParser

parser = TOMLParser()
project = parser.parse_file("project.toml")
```

## Exporters

### JSONExporter

Export results to JSON.

```python
from mcprojsim.exporters import JSONExporter

JSONExporter.export(results, "results.json")
```

### CSVExporter

Export results to CSV.

```python
from mcprojsim.exporters import CSVExporter

CSVExporter.export(results, "results.csv")
```

### HTMLExporter

Export results to HTML.

```python
from mcprojsim.exporters import HTMLExporter

HTMLExporter.export(results, "results.html")
```

## Configuration

### Config

Configuration management.

```python
from mcprojsim.config import Config

# Load from file
config = Config.load_from_file("config.yaml")

# Get default config
config = Config.get_default()

# Get uncertainty multiplier
multiplier = config.get_uncertainty_multiplier(
    "team_experience", 
    "high"
)
```

## Complete Example

```python
from mcprojsim import Project, SimulationEngine
from mcprojsim.parsers import YAMLParser
from mcprojsim.exporters import JSONExporter, HTMLExporter
from mcprojsim.config import Config

# Load configuration
config = Config.load_from_file("config.yaml")

# Parse project
parser = YAMLParser()
project = parser.parse_file("project.yaml")

# Run simulation
engine = SimulationEngine(
    iterations=10000,
    random_seed=42,
    config=config
)
results = engine.run(project)

# Display results
print(f"Project: {results.project_name}")
print(f"Mean: {results.mean:.2f} days")
print(f"P50: {results.percentile(50):.2f} days")
print(f"P80: {results.percentile(80):.2f} days")
print(f"P90: {results.percentile(90):.2f} days")

# Export results
JSONExporter.export(results, "results.json")
HTMLExporter.export(results, "results.html")
```
