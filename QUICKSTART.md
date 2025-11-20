# Quick Start Guide - mcprojsim

## Installation

The project is now set up and ready to use! Here's how to get started:

### 1. Activate the Virtual Environment

```bash
cd /Users/ljp/Devel/python/mcprojsim
source venv/bin/activate
```

### 2. Test the Installation

```bash
mc-estimate --version
# Output: mc-estimate, version 1.0.0
```

## Usage Examples

### Validate a Project File

```bash
mc-estimate validate examples/sample_project.yaml
```

### Run a Simulation

```bash
# Quick test with 1000 iterations
mc-estimate simulate examples/sample_project.yaml --iterations 1000

# Full simulation with 10000 iterations (default)
mc-estimate simulate examples/sample_project.yaml

# With custom configuration
mc-estimate simulate examples/sample_project.yaml --config examples/sample_config.yaml

# With reproducible results
mc-estimate simulate examples/sample_project.yaml --seed 42

# Quiet mode (no progress output)
mc-estimate simulate examples/sample_project.yaml --quiet
```

### View Configuration

```bash
# Show default configuration
mc-estimate config show

# Show custom configuration
mc-estimate config show --config-file examples/sample_config.yaml
```

## Output Files

After running a simulation, you'll get three output files:

1. **JSON** - Complete results with all data
2. **CSV** - Tabular summary for Excel
3. **HTML** - Interactive report (open in browser)

Example:
```
Customer Portal Redesign_results.json
Customer Portal Redesign_results.csv
Customer Portal Redesign_results.html
```

## Project Structure

```
mcprojsim/
├── src/mcprojsim/          # Source code
│   ├── cli.py              # Command-line interface
│   ├── config.py           # Configuration management
│   ├── models/             # Data models (Project, Task, Risk)
│   ├── parsers/            # YAML/TOML parsers
│   ├── simulation/         # Monte Carlo simulation engine
│   ├── analysis/           # Statistical analysis
│   ├── exporters/          # Output exporters
│   └── utils/              # Utilities
├── examples/               # Example project files
│   ├── sample_project.yaml
│   └── sample_config.yaml
├── docs/                   # Documentation
├── scripts/                # Build scripts
│   ├── mkblbd.sh          # Build package
│   ├── mkrelease.sh       # Create release
│   ├── mkdocs.sh          # Build documentation
│   └── mkghrelease.sh     # GitHub release
└── tests/                  # Tests (to be added)
```

## Development

### Run Tests (when added)

```bash
pytest
pytest --cov=mcprojsim
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

### Build Package

```bash
./scripts/mkblbd.sh
```

### Build Documentation

```bash
./scripts/mkdocs.sh
mkdocs serve  # Serve locally at http://127.0.0.1:8000
```

## Key Features Implemented

✅ **Core Models** - Project, Task, Risk with Pydantic validation
✅ **Parsers** - YAML and TOML support
✅ **Simulation Engine** - Monte Carlo with 10,000+ iterations
✅ **Distributions** - Triangular and Log-Normal
✅ **Risk Modeling** - Task-level and project-level risks
✅ **Dependency Management** - Topological sort with cycle detection
✅ **Critical Path Analysis** - Identifies frequently critical tasks
✅ **Uncertainty Factors** - Team experience, requirements maturity, etc.
✅ **Multiple Exporters** - JSON, CSV, HTML
✅ **CLI Interface** - Full-featured command-line tool
✅ **Configuration** - Customizable uncertainty factors
✅ **Reproducibility** - Random seed support
✅ **Documentation** - MkDocs with Material theme

## Example Session

```bash
# Activate environment
source venv/bin/activate

# Validate project
mc-estimate validate examples/sample_project.yaml
# ✓ Project file is valid!

# Run simulation
mc-estimate simulate examples/sample_project.yaml --seed 42
# Progress: 100.0% (10000/10000)
# === Simulation Results ===
# Project: Customer Portal Redesign
# Mean: 72.38 days
# Median (P50): 71.87 days
# P80: 80.07 days
# P90: 84.31 days
# P95: 88.42 days

# View HTML report
open "Customer Portal Redesign_results.html"
```

## Python API

You can also use mcprojsim programmatically:

```python
from mcprojsim import SimulationEngine
from mcprojsim.parsers import YAMLParser
from mcprojsim.exporters import HTMLExporter

# Parse project
parser = YAMLParser()
project = parser.parse_file("examples/sample_project.yaml")

# Run simulation
engine = SimulationEngine(iterations=10000, random_seed=42)
results = engine.run(project)

# Access results
print(f"Mean: {results.mean:.2f} days")
print(f"P90: {results.percentile(90):.2f} days")

# Export
HTMLExporter.export(results, "my_results.html")
```

## Next Steps

1. Create your own project YAML file
2. Customize uncertainty factors in config.yaml
3. Run simulations and analyze results
4. Integrate into your project management workflow

## Support

- Documentation: `docs/` directory
- Examples: `examples/` directory
- Source code: `src/mcprojsim/`

## License

MIT License - See LICENSE file
