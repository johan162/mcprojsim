# Monte Carlo Project Simulator

**Stop guessing deadlines. Start simulating them.**

MCProjSim runs thousands of Monte Carlo simulations on your project plan and turns uncertain task estimates into confidence-based delivery forecasts — so you can tell stakeholders *"we have a 90 % chance of finishing by March 2nd"* instead of *"it'll take about 10 weeks"*.



## Why MCProjSim?

Traditional estimation produces a single number that is almost always wrong.
Monte Carlo simulation replaces that number with a **probability distribution** that honestly reflects what you know — and what you don't:

| Traditional estimate | MCProjSim forecast |
|---|---|
| "The project will take 72 days." | "There is a 50 % chance of finishing in 72 days, and a 90 % chance of finishing in 86 days." |

Beyond schedule ranges, MCProjSim also tells you **why** a schedule might slip:

- **Sensitivity analysis** — which tasks drive the most variance (Spearman rank correlation)
- **Schedule slack** — which tasks are on the critical path and which have float
- **Risk impact analysis** — how often each risk fires and how much time it costs
- **Probability-of-date** — the likelihood of meeting a specific target date

## Quick start

### 1. Install

!!! info "Requires Python 3.13 or newer"

Install as a CLI tool with `pipx` (recommended) or `pip`:

```bash
# If `pipx` is not installed:
python3 -m pip install --user pipx
python3 -m pipx ensurepath

# Install MCProjSim as a CLI tool:
pipx install mcprojsim

# Or with pip:
pip install mcprojsim
```

Then verify the installation:

```bash
mcprojsim --help
mcprojsim --version
```

### 2. Describe your project

Create a file `project.yaml` (or let MCProjSim [generate one from plain text](user_guide/getting_started.md)):

```yaml
project:
  name: "My Project"
  start_date: "2025-11-01"

tasks:
  - id: "design"
    name: "System Design"
    estimate:
      low: 3
      expected: 5
      high: 10
      unit: "days"

  - id: "backend"
    name: "Backend API"
    dependencies: ["design"]
    estimate:
      low: 5
      expected: 8
      high: 15
      unit: "days"
    uncertainty_factors:
      team_experience: "medium"
      technical_complexity: "high"

  - id: "frontend"
    name: "Frontend UI"
    dependencies: ["design"]
    estimate:
      low: 4
      expected: 7
      high: 12
      unit: "days"
```

### 3. Run & read the results

```bash
mcprojsim simulate project.yaml --table
```

```text
=== Simulation Results ===

Project Overview:
┌────────────────────┬────────────────┐
│ Field              │ Value          │
├────────────────────┼────────────────┤
│ Project            │ My Project     │
│ Hours per Day      │ 8.0            │
│ Max Parallel Tasks │ 2              │
│ Schedule Mode      │ dependency_only│
└────────────────────┴────────────────┘

Calendar Time Statistical Summary:
┌──────────────────────────┬────────────────────────────────┐
│ Metric                   │ Value                          │
├──────────────────────────┼────────────────────────────────┤
│ Mean                     │ 579.93 hours (73 working days) │
│ Median (P50)             │ 572.84 hours                   │
│ Std Dev                  │ 78.50 hours                    │
│ Coefficient of Variation │ 0.1354                         │
└──────────────────────────┴────────────────────────────────┘

Calendar Time Confidence Intervals:
┌────────────┬─────────┬────────────────┬────────────┐
│ Percentile │   Hours │   Working Days │ Date       │
├────────────┼─────────┼────────────────┼────────────┤
│ P50        │  572.84 │             72 │ 2026-02-10 │
│ P80        │  642.91 │             81 │ 2026-02-23 │
│ P90        │  684.51 │             86 │ 2026-03-02 │
└────────────┴─────────┴────────────────┴────────────┘
```

The full output also includes sensitivity analysis, schedule slack, risk impact, and critical path information.
See [Interpreting Results](user_guide/interpreting_results.md) for a detailed walkthrough of every output section.

## Key features

| Category | Highlights |
|---|---|
| **Estimation** | Three-point estimates (min / most likely / max), T-shirt sizes, story points — in hours, days, or weeks |
| **Simulation** | Triangular & log-normal distributions, configurable iteration count, reproducible seeds |
| **Dependencies & scheduling** | Automatic critical path detection, schedule slack calculation |
| **Resource-constrained scheduling** | Finite team capacity, sickness & absence modeling, working calendars with holidays |
| **Sprint planning** | Sprint-based Monte Carlo forecasting with historical velocity, disruption overlays, and spillover modeling |
| **Risk modeling** | Task-level and project-level risks with probability and impact |
| **Uncertainty factors** | Team experience, requirements maturity, technical complexity, and more |
| **Analysis** | Sensitivity (Spearman ρ), staffing recommendations, skewness, kurtosis, CV, probability-of-date |
| **Output** | CLI (plain or `--table`), JSON, CSV, HTML reports |
| **Input formats** | YAML and TOML project files, or generate from natural-language descriptions with `mcprojsim generate` |
| **AI integration** | Built-in [MCP server](user_guide/mcp-server.md) for use with GitHub Copilot, Claude Desktop, and other MCP clients |

## Where to go next

<div class="grid cards" markdown>

-   **:material-rocket-launch: Getting Started**

    Install MCProjSim, create your first project file, and run a simulation in under 10 minutes.

    [:octicons-arrow-right-24: Getting Started](user_guide/getting_started.md)

-   **:material-book-open-variant: User Guide**

    Everything from task estimation and risk modeling to interpreting output and configuring uncertainty factors.

    [:octicons-arrow-right-24: Your First Project](user_guide/your_first_project.md)

-   **:material-file-document-outline: Examples**

    Ready-to-run example projects covering T-shirt sizing, story points, custom thresholds, and more.

    [:octicons-arrow-right-24: Examples](examples.md)

-   **:material-cog: Configuration**

    Customize uncertainty factors, T-shirt size mappings, story point scales, and output settings.

    [:octicons-arrow-right-24: Configuration](user_guide/configuration.md)

</div>

### Additional resources

| Resource | Description |
|---|---|
| [PDF Documentation Bundles](https://github.com/johan162/mcprojsim/releases/latest) | Both **Print** and **Tablet** friendly versions |
| [Quick Start](https://johan162.github.io/mcprojsim/quickstart/) | Your first 10 min with MCProjSim |
| [On Line Documentation](https://johan162.github.io/mcprojsim/) | Full documentation landing page |
| [MCP Server](user_guide/mcp-server.md) | Use MCProjSim as a tool from your AI assistant |
| [Development](development.md) | Set up a dev environment, run tests, build docs, and use containers |
| [Changelog](CHANGELOG.md) | Release history and migration notes |



## License

MIT License — see [LICENSE](https://github.com/johan162/mcprojsim/blob/main/LICENSE) for details.

## Contributing

Contributions are welcome.

1. Fork the repository
2. Read the [Developer Guide](https://johan162.github.io/mcprojsim/development/) to set up your environment and understand the codebase
3. Create a feature branch
4. Make your changes with tests
5. Use the `./scripts/mkbld.sh` script to build and test your changes locally
6. Submit a pull request

