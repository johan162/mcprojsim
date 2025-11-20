# Monte Carlo Project Simulator (mcprojsim)

| Category | Link |
|----------|--------|
|**Package**|[![PyPI version](https://img.shields.io/pypi/v/mcprojsim.svg)](https://pypi.org/project/mcprojsim/) [![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)|
|**Documentation**|[![Documentation](https://img.shields.io/badge/docs-mkdocs-blue)](https://johan162.github.io/mcprojsim/)|
|**License**|[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)|
|**Release**|[![GitHub release](https://img.shields.io/github/v/release/johan162/mcprojsim?include_prereleases)](https://github.com/johan162/mcprojsim/releases)|
|**CI/CD**|[![CI](https://github.com/johan162/mcprojsim/actions/workflows/ci.yml/badge.svg)](https://github.com/johan162/mcprojsim/actions/workflows/ci.yml) [![Doc build](https://github.com/johan162/mcprojsim/actions/workflows/docs.yml/badge.svg)](https://github.com/johan162/mcprojsim/actions/workflows/docs.yml) [![Coverage](https://img.shields.io/badge/coverage-83%25-green)](coverage.svg)|
|**Code Quality**|[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) [![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/) [![Linting: flake8](https://img.shields.io/badge/linting-flake8-yellowgreen)](https://flake8.pycqa.org/)|
|Repo URL|[![GitHub](https://img.shields.io/badge/GitHub-100000?style=flat-square&logo=github&logoColor=white)](https://github.com/johan162/mcprojsim)|


## Overview

A Monte Carlo simulation system for software development effort estimation. This tool helps you generate probabilistic estimates for project completion by modeling uncertainties in task duration, applying risk impacts, handling task dependencies, and generating confidence intervals through iterative simulation.

## Features

- **Triangular & Log-Normal Distribution Sampling** for task estimates
- **Project-Level and Task-Level Risk Modeling** with probabilistic impacts
- **Task Dependency Resolution** (precedence constraints)
- **Uncertainty Factor Application** (team experience, requirements maturity, etc.)
- **Resource Allocation and Availability Modeling**
- **Percentile-Based Confidence Intervals** (P50, P75, P80, P85, P90, P95)
- **Sensitivity Analysis** and critical path identification
- **Multiple Export Formats** (JSON, CSV, HTML reports)

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/johan162/mcprojsim.git
cd mcprojsim

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"

# Or install with documentation dependencies
pip install -e ".[docs]"
```

### From PyPI (when published)

```bash
pip install mcprojsim
```

## Quick Start

### 1. Create a Project Definition File

Create a `project.yaml` file:

```yaml
project:
  name: "My Project"
  description: "Sample project for estimation"
  start_date: "2025-11-01"
  confidence_levels: [50, 75, 80, 85, 90, 95]

tasks:
  - id: "task_001"
    name: "Database schema design"
    description: "Design normalized schema"
    estimate:
      min: 3
      most_likely: 5
      max: 10
      unit: "days"
    dependencies: []
    uncertainty_factors:
      team_experience: "high"
      requirements_maturity: "medium"
      technical_complexity: "low"
    risks:
      - id: "risk_001"
        name: "Schema migration issues"
        probability: 0.20
        impact: 2
```

### 2. Run the Simulation

```bash
# Run with default settings (10,000 iterations)
mc-estimate simulate project.yaml

# Specify number of iterations
mc-estimate simulate project.yaml --iterations 50000

# Use custom config file
mc-estimate simulate project.yaml --config custom_config.yaml

# Specify random seed for reproducibility
mc-estimate simulate project.yaml --seed 12345

# Export to specific formats
mc-estimate simulate project.yaml --output-format json,html
```

### 3. Validate Input Files

```bash
mc-estimate validate project.yaml
```

## Command-Line Interface

### Commands

- `mc-estimate simulate <project-file>` - Run Monte Carlo simulation
- `mc-estimate validate <project-file>` - Validate input file without running
- `mc-estimate config show` - Show current configuration

### Options

- `--iterations, -n` - Number of simulation iterations (default: 10000)
- `--config, -c` - Path to configuration file
- `--seed, -s` - Random seed for reproducibility
- `--output, -o` - Output file path
- `--output-format, -f` - Output formats: json, csv, html (comma-separated)
- `--quiet, -q` - Suppress progress output

## Python API

```python
from mcprojsim import Project, SimulationEngine
from mcprojsim.parsers import YAMLParser

# Load project
parser = YAMLParser()
project = parser.parse_file("project.yaml")

# Run simulation
engine = SimulationEngine(iterations=10000, random_seed=42)
results = engine.run(project)

# Access results
print(f"P50 (Median): {results.percentile(50)} days")
print(f"P90: {results.percentile(90)} days")
print(f"Mean: {results.mean} days")
print(f"Std Dev: {results.std_dev} days")

# Get critical path
critical_tasks = results.get_critical_path()
for task_id, criticality in critical_tasks.items():
    print(f"{task_id}: {criticality*100:.1f}% critical")
```

## Configuration

Create a `config.yaml` file to customize uncertainty factors:

```yaml
uncertainty_factors:
  team_experience:
    high: 0.90      # 10% faster
    medium: 1.0     # Baseline
    low: 1.30       # 30% slower
  
  requirements_maturity:
    high: 1.0
    medium: 1.15
    low: 1.40

simulation:
  default_iterations: 10000
  random_seed: null

output:
  formats: ["json", "csv", "html"]
  include_histogram: true
  histogram_bins: 50
```

## Examples

See the `examples/` directory for:
- `sample_project.yaml` - Complete project definition example
- `sample_config.yaml` - Configuration file example

```

## Documentation

Comprehensive documentation is available in the `docs/` directory:

- **[Getting Started](docs/getting_started.md)** - Step-by-step guide to your first simulation
- **[Formal Grammar](docs/grammar.md)** - Complete EBNF specification of the input file format
- **[Examples](docs/examples.md)** - Working examples and use cases
- **[Configuration](docs/configuration.md)** - Customizing uncertainty factors
- **[API Reference](docs/api_reference.md)** - Python API documentation

### View Documentation Locally

```bash
# Install documentation dependencies
pip install -e ".[docs]"

# Serve documentation locally at http://127.0.0.1:8000
mkdocs serve
```

## Development

### Setup Development Environment

```bash
# Install with development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=mcprojsim --cov-report=html

# Run specific test file
pytest tests/test_simulation.py
```

### Code Quality

```bash
# Format code
black src/ tests/

# Type checking
mypy src/

# Linting
flake8 src/ tests/
```

### Build Documentation

```bash
# Install documentation dependencies
pip install -e ".[docs]"

# Serve documentation locally
mkdocs serve

# Build documentation
mkdocs build
```

## Project Structure

```
mcprojsim/
├── src/mcprojsim/          # Source code
│   ├── models/             # Data models
│   ├── parsers/            # Input file parsers
│   ├── simulation/         # Simulation engine
│   ├── analysis/           # Statistical analysis
│   ├── exporters/          # Output exporters
│   └── utils/              # Utilities
├── tests/                  # Test files
├── docs/                   # Documentation
├── examples/               # Example files
└── scripts/                # Build scripts
```

## Requirements

- Python 3.9+
- NumPy 1.24+
- Pandas 2.0+
- PyYAML 6.0+
- Pydantic 2.0+
- Click 8.0+

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run the test suite
5. Submit a pull request

## Support

For issues and questions:
- GitHub Issues: https://github.com/johan162/mcprojsim/issues
- Documentation: https://github.com/johan162/mcprojsim/docs

## Citation

If you use this tool in your research or project management, please cite:

```
@software{mcprojsim,
  title = {Monte Carlo Project Simulator},
  author = {Johan Persson},
  year = {2025},
  url = {https://github.com/johan162/mcprojsim}
  version={0.0.1-rc3}
}
```

## Acknowledgments

Inspired by the work of:
- Steve McConnell - *Software Estimation: Demystifying the Black Art*
- Frederick Brooks - *The Mythical Man-Month*
- Douglas Hubbard - *How to Measure Anything in Cybersecurity Risk*
