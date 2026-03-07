# Quick Start Guide - mcprojsim

## Best for end users: Install with `pipx`

If you want a normal `mcprojsim` command without using Poetry, install the application with `pipx`.
This gives you an isolated installation while exposing the CLI directly on your `PATH`.

### 1. Install `pipx`

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

### 2. Install `mcprojsim`

```bash
pipx install mcprojsim
```

### 3. Run the CLI directly

```bash
mcprojsim --help
mcprojsim --version
mcprojsim validate examples/sample_project.yaml
```

This is the recommended non-container option for end users.

## Preferred: Run with Podman or Docker

Running `mcprojsim` as a container is the recommended option for end users.
It avoids installing Poetry locally and gives you an isolated runtime with the CLI already configured.

### Prerequisites

- Docker or Podman

### 1. Build the Container Image

```bash
git clone https://github.com/johan162/mcprojsim.git
cd mcprojsim

# Preferred: Podman
podman build -t mcprojsim .

# Alternative: Docker
docker build -t mcprojsim .
```

### 2. Run the CLI in the Container

The container entrypoint is already set to `mcprojsim`, so you only pass the command arguments.

```bash
# Preferred: Podman
podman run --rm mcprojsim --help
podman run --rm mcprojsim --version

# Alternative: Docker
docker run --rm mcprojsim --help
docker run --rm mcprojsim --version
```

### 3. Run Simulations with Local Files

Mount your current directory into the container so `mcprojsim` can read project files and write output files.

```bash
# Docker
docker run --rm -v "$PWD:/work" mcprojsim validate examples/sample_project.yaml
docker run --rm -v "$PWD:/work" mcprojsim simulate examples/sample_project.yaml --seed 42

# Podman
podman run --rm -v "$PWD:/work:Z" mcprojsim validate examples/sample_project.yaml
podman run --rm -v "$PWD:/work:Z" mcprojsim simulate examples/sample_project.yaml --seed 42
```

Generated output files such as JSON, CSV, and HTML reports will be written to your local working directory.

### Proxy / Corporate Network Build Example

If your network uses HTTPS interception or an internal proxy CA, standard container builds may fail when installing dependencies.
In that case, pass your proxy CA certificate explicitly as a build secret.

```bash
# Preferred: Podman
podman build \
	--build-arg USE_PROXY_CA=true \
	--secret id=proxy_ca,src=CA_proxy_fw_all.pem \
	-t mcprojsim .

# Alternative: Docker
docker build \
	--build-arg USE_PROXY_CA=true \
	--secret id=proxy_ca,src=CA_proxy_fw_all.pem \
	-t mcprojsim .
```

If you are not behind such a proxy, do not pass these options. A normal `podman build -t mcprojsim .` or `docker build -t mcprojsim .` is enough.

## Alternative: Local Installation with Poetry

Use this if you are working from a source checkout, developing the project, or contributing changes.

### Prerequisites

- Python 3.14 or higher
- [Poetry](https://python-poetry.org/) 2.0+ for dependency management

Install Poetry if you haven't already:
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

### 1. Clone and Install

```bash
git clone https://github.com/johan162/mcprojsim.git
cd mcprojsim

# Install all dependencies (including dev dependencies)
poetry install
```

### 2. Verify the Installation

```bash
poetry run mcprojsim --version
# Output: mcprojsim, version 1.0.0
```

You can also open a Poetry shell if you prefer:

```bash
poetry shell
mcprojsim --help
```

## Usage Examples

### Validate a Project File

```bash
poetry run mcprojsim validate examples/sample_project.yaml
```

Docker equivalent:

```bash
docker run --rm -v "$PWD:/work" mcprojsim validate examples/sample_project.yaml
```

### Run a Simulation

```bash
# Quick test with 1000 iterations
poetry run mcprojsim simulate examples/sample_project.yaml --iterations 1000

# Full simulation with 10000 iterations (default)
poetry run mcprojsim simulate examples/sample_project.yaml

# With custom configuration
poetry run mcprojsim simulate examples/sample_project.yaml --config examples/sample_config.yaml

# With reproducible results
poetry run mcprojsim simulate examples/sample_project.yaml --seed 42

# Quiet mode (no progress output)
poetry run mcprojsim simulate examples/sample_project.yaml --quiet
```

Docker equivalent:

```bash
docker run --rm -v "$PWD:/work" mcprojsim simulate examples/sample_project.yaml --iterations 1000
docker run --rm -v "$PWD:/work" mcprojsim simulate examples/sample_project.yaml --config examples/sample_config.yaml
```

### View Configuration

```bash
# Show default configuration
poetry run mcprojsim config show

# Show custom configuration
poetry run mcprojsim config show --config-file examples/sample_config.yaml
```

Docker equivalent:

```bash
docker run --rm -v "$PWD:/work" mcprojsim config show
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
│   ├── mkbld.sh            # Build package
│   ├── mkrelease.sh        # Create release
│   ├── mkdocs.sh           # Build documentation
│   └── mkghrelease.sh      # GitHub release
└── tests/                  # Unit and integration tests
```

## Development

### Run Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=mcprojsim --cov-report=html

# Run tests in parallel
poetry run pytest -n auto
```

### Code Quality

```bash
# Format code
poetry run black src/ tests/

# Type checking
poetry run mypy src/

# Linting
poetry run flake8 src/ tests/
```

### Build Package

```bash
poetry build
```

### Build Documentation

```bash
# Install with documentation dependencies
poetry install --with docs

# Serve locally at http://127.0.0.1:8000
poetry run mkdocs serve
```

## Key Features

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
# Validate project
poetry run mcprojsim validate examples/sample_project.yaml
# ✓ Project file is valid!

# Run simulation
poetry run mcprojsim simulate examples/sample_project.yaml --seed 42
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
