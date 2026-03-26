# Monte Carlo Project Simulator (mcprojsim)

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

- **Natural language project input** — generate valid project files from plain-text descriptions using `mcprojsim generate`
- **Selectable iterations** - Monte Carlo schedule simulation with configurable iteration counts
- **Multiple distributions** - Range-based task estimates using triangular and log-normal distributions
- **Selection of units** - Unit-aware estimation: supports hours, days, and weeks with automatic conversion to a canonical hours-based internal representation
- **Work hours per day** - Configurable `hours_per_day` per project, with working-day and delivery-date reporting
- **Dependency scheduling** - Task dependencies and schedule-aware project duration calculation
- **Constrained scheduling** - Resource- and calendar-aware scheduling mode with automatic activation when resources are present (explicit or team-size generated)
- **Resource handling** - Task/resource constraints (`resources`, `max_resources`, `min_experience_level`), availability, productivity, experience levels, and calendar/absence/sickness effects
- **Risk modelling** - Task-level and project-level risk modeling
- **Uncertainty factors** - Configurable uncertainty factors such as team experience and requirements maturity
- **T-Shirt and Story Point** - T-shirt size and story point symbolic estimates with configurable unit defaults
- **Multi-category T-shirt sizing** - Category-aware symbolic sizing (for example `bug.M`, `story.M`, `epic.M`) with a configurable default category and CLI override (`--tshirt-category`)
- **Multiple export formats** - Exported results in JSON, CSV, and HTML formats
- **Result analysis** - Critical path and sensitivity-oriented analysis outputs
- **Sensitivity analysis** — Spearman rank correlation identifies which tasks most influence total duration
- **Schedule slack** — CPM-based total float calculation highlights critical vs. buffered tasks
- **Risk impact analysis** — per-task trigger rates, mean impact, and mean-when-triggered statistics
- **Statistical distribution metrics** — skewness, excess kurtosis, and coefficient of variation for the overall schedule distribution
- **Probability-of-date** — calculate the likelihood of finishing by a given target date (`--target-date`)
- **Staffing analysis** — Brooks's Law–aware team-size recommendations for multiple experience profiles (`--staffing`)
- **ASCII table output** — optional `--table` flag formats CLI results as bordered tables for easier reading
- **Sprint planning** — Monte Carlo sprint forecasting with empirical or Negative Binomial velocity models, sickness modelling, item spillover, and historical metrics import (CSV or JSON)
- Reproducible runs with explicit random seeds

## Recommended installation

For most users running `mcprojsim` through an MCP-capable assistant, the recommended path is the **MCP bundle artifact** from GitHub Releases.

If the machine has Python 3.13+, you can typically ask your assistant to install and configure the bundle directly.
That means no manual `pip`, `pipx`, or environment setup commands are required in normal MCP-client workflows.

For direct terminal-only CLI usage (without MCP), `pipx` remains the simplest manual install path:

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
- [docs/user_guide/constrained.md](docs/user_guide/constrained.md) — resource/calendar-constrained scheduling, assignment behavior, and diagnostics
- [docs/user_guide/sprint_planning.md](docs/user_guide/sprint_planning.md) — sprint planning, velocity models, sickness, and historical metric import
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

# Run resource/calendar-constrained scheduling example
mcprojsim simulate examples/resource_cap_small_task.yaml --seed 42 --table

# Reproduce a run exactly
mcprojsim simulate examples/sample_project.yaml --seed 42

# Format output as ASCII tables
mcprojsim simulate examples/sample_project.yaml --table

# Calculate probability of meeting a target date
mcprojsim simulate examples/sample_project.yaml --target-date 2026-06-01

# Combine options
mcprojsim simulate examples/sample_project.yaml --config examples/sample_config.yaml --table --verbose --seed 42

# Sprint planning with negative binomial velocity model and sickness modelling
mcprojsim simulate examples/sprint_nb_sickness_large.yaml --seed 42 --velocity-model neg_binomial
```

## MCP server integration

`mcprojsim` can run as a [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server, letting AI assistants such as GitHub Copilot, Claude Desktop, or any MCP-compatible client generate project files, validate descriptions, and run simulations conversationally.

### Preferred install path: MCP bundle artifact

Each release includes an MCP bundle artifact: `mcprojsim-mcp-bundle-<version>.zip`.

On systems with Python 3.13+, the preferred workflow is to ask your MCP-capable assistant to install/configure this bundle.
In that workflow, no manual package-install commands are needed.

Example prompt to your assistant to install:

- ***"Download and install the latest mcprojsim MCP server from GitHub Releases. Follow the README.md for 
installation instructions."***

Once installed the server exposes three tools:

| Tool | Description |
|------|-------------|
| `generate_project_file` | Convert a natural-language project description into a valid YAML project file |
| `validate_project_description` | Check a description for missing data or inconsistencies without generating a file |
| `simulate_project` | Generate, validate, and simulate in one step — returns full statistical results |


### A basic example of a prompt

After restarting the assistant (needed to load the new MCP Server) ask for a simple project simulation:

- ***"Simulate a project that starts 2025-05-01 and has two M-size tasks that depends on each-other. Show the result for all complete date percentiles in a table."*** 

```txt
● Here are the simulation results for the two-task project (sequential M→M, starting 2025-05-01):

  ┌────────────┬───────┬──────────────┬───────────────┐
  │ Percentile │ Hours │ Working Days │ Delivery Date │
  ├────────────┼───────┼──────────────┼───────────────┤
  │ P50        │ 230.8 │ 29           │ 2025-06-11    │
  ├────────────┼───────┼──────────────┼───────────────┤
  │ P80        │ 265.3 │ 34           │ 2025-06-18    │
  ├────────────┼───────┼──────────────┼───────────────┤
  │ P90        │ 283.4 │ 36           │ 2025-06-20    │
  ├────────────┼───────┼──────────────┼───────────────┤
  │ P95        │ 298.7 │ 38           │ 2025-06-24    │
  └────────────┴───────┴──────────────┴───────────────┘

  Key stats: Mean ~233h (30 days) · Std dev ~38h · Both tasks are on the critical path 100% of the time.
```

To get more statistics try:

- ***"Show the summary statistics for this simulation in a table."***


```txt
● From the previous simulation results:

  ┌──────────────────────────┬────────────────────────────────┐
  │ Statistic                │ Value                          │
  ├──────────────────────────┼────────────────────────────────┤
  │ Mean                     │ 232.64 hours (30 working days) │
  ├──────────────────────────┼────────────────────────────────┤
  │ Median (P50)             │ 230.82 hours (29 working days) │
  ├──────────────────────────┼────────────────────────────────┤
  │ Std Dev                  │ 37.97 hours                    │
  ├──────────────────────────┼────────────────────────────────┤
  │ Coefficient of Variation │ 0.1632                         │
  ├──────────────────────────┼────────────────────────────────┤
  │ Skewness                 │ 0.2703                         │
  ├──────────────────────────┼────────────────────────────────┤
  │ Excess Kurtosis          │ -0.3336                        │
  ├──────────────────────────┼────────────────────────────────┤
  │ Iterations               │ 10,000                         │
  ├──────────────────────────┼────────────────────────────────┤
  │ Hours per Day            │ 8.0                            │
  └──────────────────────────┴────────────────────────────────┘
```



### Manual install path

If you prefer a manual install path, use one of the options below.

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
  version = {0.8.0}
}
```

## License

MIT License - see [LICENSE](LICENSE).

## Acknowledgments

Inspired by the work of:

- Steve McConnell - *Software Estimation: Demystifying the Black Art*
- Frederick Brooks - *The Mythical Man-Month*
- Douglas Hubbard - *How to Measure Anything in Cybersecurity Risk*
