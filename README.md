# Monte Carlo Project Simulator (mcprojsim)

| Category | Link |
|----------|--------|
|**Package**|[![PyPI version](https://img.shields.io/pypi/v/mcprojsim.svg)](https://pypi.org/project/mcprojsim/) [![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)|
|**Documentation**|[![Documentation](https://img.shields.io/badge/docs-mkdocs-blue)](https://johan162.github.io/mcprojsim/)|
|**License**|[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)|
|**Release**|[![GitHub release](https://img.shields.io/github/v/release/johan162/mcprojsim?include_prereleases)](https://github.com/johan162/mcprojsim/releases)|
|**CI/CD**|[![CI](https://github.com/johan162/mcprojsim/actions/workflows/ci.yml/badge.svg)](https://github.com/johan162/mcprojsim/actions/workflows/ci.yml) [![Doc build](https://github.com/johan162/mcprojsim/actions/workflows/docs.yml/badge.svg)](https://github.com/johan162/mcprojsim/actions/workflows/docs.yml) [![Coverage](https://img.shields.io/badge/coverage-88%25-brightgreen.svg)](coverage.svg)|
|**Code Quality**|[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) [![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/) [![Linting: flake8](https://img.shields.io/badge/linting-flake8-yellowgreen)](https://flake8.pycqa.org/)|
|Repo URL|[![GitHub](https://img.shields.io/badge/GitHub-100000?style=flat-square&logo=github&logoColor=white)](https://github.com/johan162/mcprojsim)|

## Overview

`mcprojsim` is a Monte Carlo simulation tool for projects with emphasis on agile software project estimation.
Instead of producing a single deadline, it models uncertainty in task duration, dependencies, risks, and other schedule drivers to produce confidence-based forecast ranges.

It is intended for teams that want answers such as:

- What is the likely completion range for this project?
- What is the $P50$, $P80$, or $P90$ delivery date?
- Which tasks most often drive schedule risk?
- How do risks and uncertainty factors change the forecast?

## Key features

- **Natural language project input** — generate valid project files from plain-text descriptions using `mcprojsim generate`
- Monte Carlo schedule simulation with configurable iteration counts
- Range-based task estimates using triangular and log-normal distributions
- Unit-aware estimation: supports hours, days, and weeks with automatic conversion to a canonical hours-based internal representation
- Configurable `hours_per_day` per project, with working-day and delivery-date reporting
- Task dependencies and schedule-aware project duration calculation
- Task-level and project-level risk modeling
- Configurable uncertainty factors such as team experience and requirements maturity
- T-shirt size and story point symbolic estimates with configurable unit defaults
- Exported results in JSON, CSV, and HTML formats
- Critical path and sensitivity-oriented analysis outputs
- **Sensitivity analysis** — Spearman rank correlation identifies which tasks most influence total duration
- **Schedule slack** — CPM-based total float calculation highlights critical vs. buffered tasks
- **Risk impact analysis** — per-task trigger rates, mean impact, and mean-when-triggered statistics
- **Statistical distribution metrics** — skewness, excess kurtosis, and coefficient of variation for the overall schedule distribution
- **Probability-of-date** — calculate the likelihood of finishing by a given target date (`--target-date`)
- **ASCII table output** — optional `--table` flag formats CLI results as bordered tables for easier reading
- Reproducible runs with explicit random seeds

## Recommended installation

For most end users, `pipx` is the simplest way to install `mcprojsim` as a CLI tool.

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
pipx install mcprojsim
```

Then verify the installation:

```bash
mcprojsim --help
mcprojsim --version
```

For a first-run walkthrough, see the 10-min [QUICKSTART.md](QUICKSTART.md). After this we recommend going through the [User Guide](https://johan162.github.io/mcprojsim/)

## Minimal example

Create a file named `project.yaml`:

```yaml
project:
  name: "My Project"
  description: "Sample project for estimation"
  start_date: "2025-11-01"
  confidence_levels: [50, 80, 90]

tasks:
  - id: "task_001"
    name: "Database schema design"
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
```

Validate the file:

```bash
mcprojsim validate project.yaml
```

Run a simulation:

```bash
mcprojsim simulate project.yaml --seed 12345
```

Typical outputs (see the `--help` for how to specify output) include:

- `*_results.json` for full machine-readable output
- `*_results.csv` for tabular summaries
- `*_results.html` for a browsable report

## Documentation map

Use the local document that matches your goal:

- [QUICKSTART.md](QUICKSTART.md) — installation paths, first commands, container usage, and local setup
- [docs/getting_started.md](docs/getting_started.md) — first simulation walkthrough
- [docs/user_guide/introduction.md](docs/user_guide/introduction.md) — concepts behind Monte Carlo estimation
- [docs/user_guide/your_first_project.md](docs/user_guide/your_first_project.md) — build a project file step by step
- [docs/user_guide/project_files.md](docs/user_guide/project_files.md) — project file reference
- [docs/configuration.md](docs/configuration.md) — uncertainty factors and runtime configuration
- [docs/examples.md](docs/examples.md) — example projects and usage patterns
- [docs/api_reference.md](docs/api_reference.md) — Python API usage

The full published documentation is also available at <https://johan162.github.io/mcprojsim/>.

## Example commands

```bash
# Generate a project file from a natural language description
mcprojsim generate examples/nl_example.txt -o my_project.yaml

# Validate an input file
mcprojsim validate examples/sample_project.yaml

# Run a default simulation
mcprojsim simulate examples/sample_project.yaml

# Use a custom configuration
mcprojsim simulate examples/sample_project.yaml --config examples/sample_config.yaml

# Reproduce a run exactly
mcprojsim simulate examples/sample_project.yaml --seed 42

# Format output as ASCII tables
mcprojsim simulate examples/sample_project.yaml --table

# Calculate probability of meeting a target date
mcprojsim simulate examples/sample_project.yaml --target-date 2026-06-01

# Combine options
mcprojsim simulate examples/sample_project.yaml --config examples/sample_config.yaml --table --verbose --seed 42
```

## MCP server integration

`mcprojsim` can run as a [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server, letting AI assistants such as GitHub Copilot, Claude Desktop, or any MCP-compatible client generate project files, validate descriptions, and run simulations conversationally.

Install with the optional MCP dependency group:

```bash
pipx install "mcprojsim[mcp]"
```

Or, from a source checkout:

```bash
poetry install --with mcp
```

Add the server to your MCP client configuration (e.g. VS Code `settings.json` or Claude Desktop `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "mcprojsim": {
      "command": "mcprojsim-mcp"
    }
  }
}
```

The server exposes three tools:

| Tool | Description |
|------|-------------|
| `generate_project_file` | Convert a natural-language project description into a valid YAML project file |
| `validate_project_description` | Check a description for missing data or inconsistencies without generating a file |
| `simulate_project` | Generate, validate, and simulate in one step — returns full statistical results |

## For developers

If you want to work from a source checkout, run tests, build docs, or use containers, start with:

- [QUICKSTART.md](QUICKSTART.md)
- [scripts/README.md](scripts/README.md)
- [docs/index.md](docs/index.md)

The detailed developer documentation (including how to configure and build the container) is available at

- [docs/development.md](docs/development.md)

## Contributing

Contributions are welcome.

1. Fork the repository
2. Read the [Developer Guide](docs/development.md) to set up your environment and understand the codebase
3. Create a feature branch
4. Make your changes with tests
5. Use the `./scripts/mkbld.sh` script to build and test your changes locally
6. Submit a pull request

## Support

- Bug reports: [MCProjSim Issues](https://github.com/johan162/mcprojsim/issues)
- Full documentation: [MCProjSim Documentation](https://johan162.github.io/mcprojsim/)


## Citation

If you use this tool in research or project planning, please cite:

```text
@software{mcprojsim,
  title = {Monte Carlo Project Simulator},
  author = {Johan Persson},
  year = {2026},
  url = {https://github.com/johan162/mcprojsim},
  version = {0.4.7}
}
```

## License

MIT License - see [LICENSE](LICENSE).

## Acknowledgments

Inspired by the work of:

- Steve McConnell - *Software Estimation: Demystifying the Black Art*
- Frederick Brooks - *The Mythical Man-Month*
- Douglas Hubbard - *How to Measure Anything in Cybersecurity Risk*
