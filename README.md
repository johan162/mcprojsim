# Monte Carlo Project Simulator (mcprojsim)


**Stop guessing deadlines. Start simulating them !**

| Category | Link |
|----------|--------|
|**Package**|[![PyPI version](https://img.shields.io/pypi/v/mcprojsim.svg)](https://pypi.org/project/mcprojsim/) [![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)|
|**Documentation**|[![Documentation](https://img.shields.io/badge/docs-mkdocs-blue)](https://johan162.github.io/mcprojsim/)|
|**License**|[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)|
|**Release**|[![GitHub release](https://img.shields.io/github/v/release/johan162/mcprojsim?include_prereleases)](https://github.com/johan162/mcprojsim/releases)|
|**CI/CD**|[![CI](https://github.com/johan162/mcprojsim/actions/workflows/ci.yml/badge.svg)](https://github.com/johan162/mcprojsim/actions/workflows/ci.yml) [![Doc build](https://github.com/johan162/mcprojsim/actions/workflows/docs.yml/badge.svg)](https://github.com/johan162/mcprojsim/actions/workflows/docs.yml) [![Coverage](https://img.shields.io/badge/coverage-89%25-brightgreen.svg)](coverage.svg)|
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

- Monte Carlo schedule simulation with configurable iterations and reproducible seeds
- Range-based estimates using explicit low/expected/high values, T-shirt sizes, story points, and multi-category symbolic sizing
- Dependency-only scheduling plus resource- and calendar-constrained scheduling when resources are present
- Risk and uncertainty modeling for both tasks and the overall project
- Analysis outputs including percentiles, delivery dates, critical paths, sensitivity, slack, risk impact, staffing guidance, and target-date probability
- JSON, CSV, and HTML exports, plus optional ASCII table output in the CLI
- Natural-language project generation from plain text with `mcprojsim generate`
- MCP server support for assistant-driven generation, validation, and simulation workflows
- Sprint planning support with empirical or negative binomial velocity models, sickness modelling, spillover, and historical metrics import

## Recommended installation

Most users fall into one of two paths:

- **Terminal-first CLI usage**: install with `pipx`.
- **MCP-assisted usage**: use the released MCP bundle or the optional MCP package install described in [docs/user_guide/mcp-server.md](docs/user_guide/mcp-server.md).

For direct terminal-only CLI usage, `pipx` remains the simplest manual install path:

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

For the fastest first run, start with [Quickstart Guide](https://johan162.github.io/mcprojsim/quickstart/). For the fuller documentation path after that, use the published [User Guide](https://johan162.github.io/mcprojsim/).

> [!TIP] 
> There is also a prepared Docker image if you prefer to use an isolated environment to run in. 
> There is also a accompaning script in `bin/mcprojsim.sh` to run the program in the container in the same way as the Python executable installed via `pipx`


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
      low: 3
      expected: 5
      high: 10
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
mcprojsim simulate project.yaml --seed 12345 --table
```

Typical outputs (see the `--help` for how to specify output) include:

- `*_results.json` for full machine-readable output
- `*_results.csv` for tabular summaries
- `*_results.html` for a browsable report

## Documentation map

Use the entry point that matches your goal:

|Documentation Link|Purpose|
|------------------|-------|
| [Quickstart Guide](https://johan162.github.io/mcprojsim/quickstart/) | Fastest terminal-based first run |
| [User Documentation](https://johan162.github.io/mcprojsim/) | The full documentation site |
| [User Guide](https://johan162.github.io/mcprojsim/user_guide/getting_started/) | The User Guide section |
| [Development Guide](https://johan162.github.io/mcprojsim/development/) | contributor and source-checkout workflows |


Additional runnable examples can be seen in the [Examples section](https://johan162.github.io/mcprojsim/examples/) of the user guide or in the project directory [examples/](examples/).

## Example commands

```bash
# Generate a project file from a natural language description
mcprojsim generate examples/nl_example.txt -o my_project.yaml

# Validate an input file
mcprojsim validate examples/sample_project.yaml

# Run a reproducible simulation
mcprojsim simulate examples/sample_project.yaml --seed 42

# Use a custom configuration
mcprojsim simulate examples/sample_project.yaml --config examples/sample_config.yaml --seed 42

# Calculate probability of meeting a target date
mcprojsim simulate examples/sample_project.yaml --target-date 2026-06-01

# Format tabular sections for easier reading
mcprojsim simulate examples/sample_project.yaml --table --seed 42
```

For full CLI coverage, including constrained scheduling, sprint planning, quiet/minimal modes, staffing, and export options, see [docs/user_guide/running_simulations.md](docs/user_guide/running_simulations.md).

## MCP server integration

`mcprojsim` can run as a [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server, letting AI assistants such as GitHub Copilot, Claude Desktop, or any MCP-compatible client generate project files, validate descriptions, and run simulations conversationally.

Preferred path: install the released MCP bundle artifact from GitHub Releases with your assistant, or follow the manual setup in [docs/user_guide/mcp-server.md](docs/user_guide/mcp-server.md).

For end-to-end setup, installation tradeoffs, and natural-language input examples, see [docs/user_guide/mcp-server.md](docs/user_guide/mcp-server.md).


### Example prompt to get your assistant to install `mcprojsim`:

```txt
Download and install the latest mcprojsim MCP server from GitHub Releases. Follow the README.md for installation instructions.
```

See the MCP server [detailed documentation](https://johan162.github.io/mcprojsim/user_guide/mcp-server/#what-is-the-mcp-server) for examples of using the server.


## Citation

If you use this tool in research or project planning, please cite:

```text
@software{mcprojsim,
  title = {Monte Carlo Project Simulator},
  author = {Johan Persson},
  year = {2026},
  url = {https://github.com/johan162/mcprojsim},
  version = {0.8.3}
}
```

## License

MIT License - see [LICENSE](LICENSE).

## Acknowledgments

Inspired by the work of:

- Steve McConnell - *Software Estimation: Demystifying the Black Art*
- Frederick Brooks - *The Mythical Man-Month*
- Douglas Hubbard - *How to Measure Anything in Cybersecurity Risk*
