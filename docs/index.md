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

Install as a CLI tool with `pipx`:

```bash
# If `pipx` is not installed:
python3 -m pip install --user pipx
python3 -m pipx ensurepath

# Install MCProjSim as a CLI tool:
pipx install mcprojsim         
```

Then verify the installation:

```bash
mcprojsim --help
mcprojsim --version
```

### 2. Describe your project

Create a file `project.yaml` (or let MCProjSim [generate one from plain text](user_guide/running_simulations.md)):

```yaml
project:
  name: "My Project"
  start_date: "2025-11-01"

tasks:
  - id: "task_001"
    name: "Backend API"
    estimate:
      min: 5
      most_likely: 8
      max: 15
      unit: "days"
    uncertainty_factors:
      team_experience: "medium"
      technical_complexity: "high"
```

### 3. Run & read the results

```bash
mcprojsim simulate project.yaml --table
```

```text
=== Simulation Results ===
┌──────────────────────────┬────────────────────────────────┐
│ Parameter                │ Value                          │
├──────────────────────────┼────────────────────────────────┤
│ Project                  │ My Project                     │
│ Mean                     │ 579.93 hours (73 working days) │
│ Std Dev                  │ 78.50 hours                    │
│ Coefficient of Variation │ 0.1354                         │
└──────────────────────────┴────────────────────────────────┘

Confidence Intervals:
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
| **Risk modeling** | Task-level and project-level risks with probability and impact |
| **Uncertainty factors** | Team experience, requirements maturity, technical complexity, and more |
| **Analysis** | Sensitivity (Spearman ρ), skewness, kurtosis, CV, probability-of-date |
| **Output** | CLI (plain or `--table`), JSON, CSV, HTML reports |
| **AI integration** | Built-in [MCP server](user_guide/mcp-server.md) for use with GitHub Copilot, Claude Desktop, and other MCP clients |
| **NL input** | Generate project files from natural-language descriptions with `mcprojsim generate` |

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

    [:octicons-arrow-right-24: Configuration](configuration.md)

</div>

### Additional resources

| Resource | Description |
|---|---|
| [Running Simulations](user_guide/running_simulations.md) | CLI options: `--table`, `--verbose`, `--target-date`, export formats |
| [Interpreting Results](user_guide/interpreting_results.md) | How to read confidence intervals, sensitivity, slack, and risk impact |
| [MCP Server](user_guide/mcp-server.md) | Use MCProjSim as an AI-powered simulation tool from your editor |
| [API Reference](api_reference.md) | Integrate MCProjSim into your own Python scripts |
| [Formal Grammar](grammar.md) | Full EBNF specification for project files |
| [Development](development.md) | Set up a dev environment, run tests, build docs, and use containers |
| [Changelog](CHANGELOG.md) | Release history and migration notes |

## License

MIT License — see [LICENSE](https://github.com/johan162/mcprojsim/blob/main/LICENSE) for details.
