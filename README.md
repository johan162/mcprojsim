# Monte Carlo Project Simulator (mcprojsim)

| Category | Link |
|----------|--------|
|**Package**|[![PyPI version](https://img.shields.io/pypi/v/mcprojsim.svg)](https://pypi.org/project/mcprojsim/) [![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)|
|**Documentation**|[![Documentation](https://img.shields.io/badge/docs-mkdocs-blue)](https://johan162.github.io/mcprojsim/)|
|**License**|[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)|
|**Release**|[![GitHub release](https://img.shields.io/github/v/release/johan162/mcprojsim?include_prereleases)](https://github.com/johan162/mcprojsim/releases)|
|**CI/CD**|[![CI](https://github.com/johan162/mcprojsim/actions/workflows/ci.yml/badge.svg)](https://github.com/johan162/mcprojsim/actions/workflows/ci.yml) [![Doc build](https://github.com/johan162/mcprojsim/actions/workflows/docs.yml/badge.svg)](https://github.com/johan162/mcprojsim/actions/workflows/docs.yml) [![Coverage](https://img.shields.io/badge/coverage-83%25-brightgreen.svg)](coverage.svg)|
|**Code Quality**|[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) [![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/) [![Linting: flake8](https://img.shields.io/badge/linting-flake8-yellowgreen)](https://flake8.pycqa.org/)|
|Repo URL|[![GitHub](https://img.shields.io/badge/GitHub-100000?style=flat-square&logo=github&logoColor=white)](https://github.com/johan162/mcprojsim)|


# Table of Content

- [Monte Carlo Project Simulator (mcprojsim)](#monte-carlo-project-simulator-mcprojsim)
- [Table of Content](#table-of-content)
  - [Overview](#overview)
  - [Features](#features)
  - [Installation](#installation)
    - [Best for end users: Install with `pipx`](#best-for-end-users-install-with-pipx)
      - [Install with `pipx`](#install-with-pipx)
      - [Install a pre-release from TestPyPI](#install-a-pre-release-from-testpypi)
    - [Preferred: Run with Podman or Docker](#preferred-run-with-podman-or-docker)
      - [Prerequisites](#prerequisites)
      - [Build the container image](#build-the-container-image)
      - [Run the CLI in the container](#run-the-cli-in-the-container)
      - [Run simulations with local files](#run-simulations-with-local-files)
      - [Container Troubleshooting](#container-troubleshooting)
    - [Local development / source install prerequisites](#local-development--source-install-prerequisites)
    - [From Source](#from-source)
    - [Activate the Virtual Environment](#activate-the-virtual-environment)
    - [From PyPI (when published)](#from-pypi-when-published)
  - [Quick Start](#quick-start)
    - [1. Create a Project Definition File](#1-create-a-project-definition-file)
    - [2. Run the Simulation](#2-run-the-simulation)
    - [3. Validate Input Files](#3-validate-input-files)
  - [Command-Line Interface](#command-line-interface)
    - [Commands](#commands)
    - [Options](#options)
  - [Configuration](#configuration)
  - [Examples](#examples)
    - [Documentation Server Options](#documentation-server-options)
  - [Development](#development)
    - [Setup Development Environment](#setup-development-environment)
    - [Run Tests](#run-tests)
    - [Code Quality](#code-quality)
    - [Build Documentation](#build-documentation)
  - [Project Structure](#project-structure)
  - [Requirements](#requirements)
  - [License](#license)
  - [Contributing](#contributing)
  - [Support](#support)
  - [Citation](#citation)
  - [Acknowledgments](#acknowledgments)


## Overview

A Monte Carlo simulation system for software development effort estimation. This tool helps you generate probabilistic estimates for project completion by modeling uncertainties in task duration, applying risk impacts, handling task dependencies, and generating confidence intervals through iterative simulation.

## Features

- **Triangular & Log-Normal Distribution Sampling** for task estimates
- **Project-Level and Task-Level Risk Modeling** with probabilistic impacts
- **Task Dependency Resolution** (precedence constraints)
- **Uncertainty Factor Application** (team experience, requirements maturity, etc.)
- **Resource Allocation and Availability Modeling**
- **Percentile-Based Confidence Intervals** (P25, P50, P75, P80, P85, P90, P95, P99)
- **Sensitivity Analysis** and critical path identification
- **Multiple Export Formats** (JSON, CSV, HTML reports)

## Installation

### Best for end users: Install with `pipx`

If you want to install `mcprojsim` as a normal command-line tool, `pipx` is the simplest option.
It installs the application in an isolated environment and makes the `mcprojsim` command directly available on your `PATH`.

#### Install with `pipx`

```bash
# Install pipx if needed
python3 -m pip install --user pipx
python3 -m pipx ensurepath

# Install mcprojsim
pipx install mcprojsim

# Run it directly
mcprojsim --help
mcprojsim --version
```

This is the recommended non-container option for end users.

#### Install a pre-release from TestPyPI

Pre-releases are published (based on pre-release tags) to TestPyPI before a full production release reaches PyPI.
When installing from TestPyPI, use TestPyPI as the main index and keep PyPI as the extra index for dependencies.

```bash
# Install the latest pre-release from TestPyPI
pipx install \
  --pip-args="--pre --index-url https://test.pypi.org/simple --extra-index-url https://pypi.org/simple" \
  mcprojsim

# Or install a specific pre-release version
pipx install \
  --pip-args="--index-url https://test.pypi.org/simple --extra-index-url https://pypi.org/simple" \
  mcprojsim==0.2.0rc2
```

If `mcprojsim` is already installed with `pipx`, use `pipx upgrade` with the same `--pip-args` values.

### Preferred: Run with Podman or Docker

Running `mcprojsim` as a container is the recommended option for end users.
It avoids installing Poetry locally and provides an isolated runtime with the CLI preconfigured.

#### Prerequisites

- Podman or Docker

#### Build the container image

```bash
# Clone the repository
git clone https://github.com/johan162/mcprojsim.git
cd mcprojsim

# Preferred: Podman
podman build -t mcprojsim .

# Alternative: Docker
docker build -t mcprojsim .
```

#### Run the CLI in the container

The container entrypoint is already set to `mcprojsim`, so you only need to pass the CLI arguments.

```bash
# Preferred: Podman
podman run --rm mcprojsim --help
podman run --rm mcprojsim --version

# Alternative: Docker
docker run --rm mcprojsim --help
```

#### Run simulations with local files

Mount your working directory into the container so it can read input files and write result files.

```bash
# Preferred: Podman
podman run --rm -v "$PWD:/work:Z" mcprojsim validate examples/sample_project.yaml
podman run --rm -v "$PWD:/work:Z" mcprojsim simulate examples/sample_project.yaml --seed 42

# Alternative: Docker
docker run --rm -v "$PWD:/work" mcprojsim validate examples/sample_project.yaml
docker run --rm -v "$PWD:/work" mcprojsim simulate examples/sample_project.yaml --seed 42
```

Generated JSON, CSV, and HTML reports are written back to your local working directory.

#### Container Troubleshooting

- **No proxy in your environment:** you do not need any certificate file or extra build flags. A standard `podman build -t mcprojsim .` or `docker build -t mcprojsim .` works as-is.
- **Corporate proxy / TLS interception:** some environments re-sign HTTPS traffic with an internal CA. In that case, pass the CA certificate as a build secret so Poetry and `pip` can trust outbound HTTPS during the image build.

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

- **Why this is needed:** Dockerfile `COPY` wildcard patterns do **not** silently ignore missing files. The glob is resolved while preparing the build context, and if it matches nothing, the build fails. That is why `COPY CA_proxy_fw_all.pem* ...` still errors when the file does not exist.
- **Why the new approach is better:** using an optional build secret keeps standard builds simple, avoids placeholder files in the repository, and only requires the certificate when proxy mode is explicitly enabled.

### Local development / source install prerequisites

- Python 3.14 or higher
- [Poetry](https://python-poetry.org/) for dependency management

Install Poetry if you haven't already:
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

### From Source

```bash
# Clone the repository
git clone https://github.com/johan162/mcprojsim.git
cd mcprojsim

# Install all dependencies (including dev dependencies)
poetry install

# Or install only production dependencies
poetry install --only main

# Or install with documentation dependencies
poetry install --with docs
```

### Activate the Virtual Environment

```bash
# Activate the Poetry-managed virtual environment
poetry shell

# Or run commands directly with poetry run
poetry run mcprojsim --help
```

### From PyPI (when published)

```bash
# Using pip
pip install mcprojsim

# Or using Poetry in your project
poetry add mcprojsim
```

To install a pre-release with `pip`, point the main index at TestPyPI and keep PyPI as the fallback for dependencies:

```bash
pip install --pre --index-url https://test.pypi.org/simple --extra-index-url https://pypi.org/simple mcprojsim
```

If you prefer running the project from a source checkout without installing it locally, you can also use the containerized CLI wrapper:

```bash
./bin/mcprojsim.sh --help
./bin/mcprojsim.sh simulate project.yaml --seed 12345
```

## Quick Start

### 1. Create a Project Definition File

Create a `project.yaml` file:

```yaml
project:
  name: "My Project"
  description: "Sample project for estimation"
  start_date: "2025-11-01"
  confidence_levels: [25, 50, 75, 80, 85, 90, 95, 99]

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
poetry run mcprojsim simulate project.yaml

# Or activate the shell first
poetry shell
mcprojsim simulate project.yaml

# Specify number of iterations
mcprojsim simulate project.yaml --iterations 50000

# Use custom config file
mcprojsim simulate project.yaml --config custom_config.yaml

# Specify random seed for reproducibility
mcprojsim simulate project.yaml --seed 12345

# Export to specific formats
mcprojsim simulate project.yaml --output-format json,html
```

Container equivalent:

```bash
# Preferred: Podman
podman run --rm -v "$PWD:/work:Z" mcprojsim simulate project.yaml --seed 12345

# Alternative: Docker
docker run --rm -v "$PWD:/work" mcprojsim simulate project.yaml --seed 12345
```

### 3. Validate Input Files

```bash
mcprojsim validate project.yaml
```

Container equivalent:

```bash
# Preferred: Podman
podman run --rm -v "$PWD:/work:Z" mcprojsim validate project.yaml

# Alternative: Docker
docker run --rm -v "$PWD:/work" mcprojsim validate project.yaml
```

## Command-Line Interface

### Commands

- `mcprojsim simulate <project-file>` - Run Monte Carlo simulation
- `mcprojsim validate <project-file>` - Validate input file without running
- `mcprojsim config show` - Show current configuration

### Options

- `--iterations, -n` - Number of simulation iterations (default: 10000)
- `--config, -c` - Path to configuration file
- `--seed, -s` - Random seed for reproducibility
- `--output, -o` - Output file path
- `--output-format, -f` - Output formats: json, csv, html (comma-separated)
- `--quiet, -q` - Suppress progress output


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

Use the local MkDocs server when you are editing documentation or Python code and want fast live-reload during development.

```bash
# Install with documentation dependencies
poetry install --with docs

# Serve documentation locally at http://127.0.0.1:8000
poetry run mkdocs serve
```

### Documentation Server Options

- Use `make docs-serve` for day-to-day documentation editing with the fastest feedback loop.
- Use `make docs-container-start` when you want to validate the containerized docs environment or run the docs server without relying on a local Poetry environment.
- Use `./scripts/docs-contctl.sh ...` directly when you want full container lifecycle control such as `start`, `stop`, `restart`, `status`, `logs`, or `build`.

```bash
# Fast local development server
make docs-serve

# Containerized docs server
make docs-container-start

# Direct container management
./scripts/docs-contctl.sh status
./scripts/docs-contctl.sh logs --follow
```

## Development

### Setup Development Environment

```bash
# Install with all dependencies including dev dependencies
poetry install

# Activate the virtual environment
poetry shell

# Install pre-commit hooks
pre-commit install
```

### Run Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=mcprojsim --cov-report=html

# Run tests in parallel
poetry run pytest -n auto

# Run specific test file
poetry run pytest tests/test_simulation.py
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

### Build Documentation

Choose the command based on what you are doing:

- `make docs-serve` or `poetry run mkdocs serve` for editing docs locally.
- `make docs-container-start` for the containerized docs server.
- `make docs-container-stop` and `make docs-container-logs` for container lifecycle tasks.

```bash
# Install with documentation dependencies
poetry install --with docs

# Serve documentation locally
poetry run mkdocs serve

# Or use the Makefile wrapper
make docs-serve

# Start the containerized docs server
make docs-container-start

# Stop the containerized docs server
make docs-container-stop

# Build documentation
poetry run mkdocs build
```

## Project Structure

```
mcprojsim/
├── bin/                    # User-facing wrapper scripts
│   └── mcprojsim.sh        # Runs the containerized CLI like a local command
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
└── scripts/                # Build, release, setup, and docs-control scripts
```

## Requirements

- Python 3.14+
- Poetry 2.0+
- NumPy 2.3.4+
- PyYAML 6.0+
- Pydantic 2.0+
- Click 8.0+

All Python dependencies are managed by Poetry and will be installed automatically.

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
  year = {2026},
  url = {https://github.com/johan162/mcprojsim},
  version = {0.2.0rc6}
}
```

## Acknowledgments

Inspired by the work of:
- Steve McConnell - *Software Estimation: Demystifying the Black Art*
- Frederick Brooks - *The Mythical Man-Month*
- Douglas Hubbard - *How to Measure Anything in Cybersecurity Risk*
