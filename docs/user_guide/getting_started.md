# Getting Started

This short, hands-on chapter shows you mcprojsim in action. If you want a quick, practical tour, follow along: you'll create a sample project file, run a Monte Carlo simulation, and learn how to read the key results and reports. We keep theory to a minimum here — the goal is to spark your curiosity and get you producing real outputs quickly so you can explore the deeper chapters with context.

What you'll learn

- Quick generation of a valid project file from a plain-text description.
- Running a reproducible Monte Carlo simulation and exporting interactive reports.
- Using sensitivity and critical-path outputs to find the tasks that drive schedule risk.


## Before you start

You need:

- **Python 3.14 or newer**
- A terminal
- `pipx` for the easiest CLI install (recommended), or `pip`

If you do not have `pipx` yet:

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```



## Install mcprojsim

### With pipx (recommended)

```bash
pipx install mcprojsim
```

### With pip

```bash
pip install mcprojsim
```

### From source

```bash
git clone https://github.com/johan162/mcprojsim.git
cd mcprojsim
pip install -e .
```

Verify the installation:

```bash
mcprojsim --version
mcprojsim --help
```


## Create your first project file

The quickest way is to describe your project in plain text and let `mcprojsim generate` produce the YAML for you.

Create a file named `description.txt`:

```text
Project name: Website Refresh
Description: Small example project
Start date: 2026-04-01

Task 1:
- Design updates
- Size: S

Task 2:
- Frontend changes
- Depends on Task 1
- Size: M
```

Generate the project file:

```bash
mcprojsim generate description.txt -o project.yaml
```

That is it — the generated `project.yaml` is ready for validation and simulation. You can use T-shirt sizes (`XS`, `S`, `M`, `L`, `XL`, `XXL`), story points, or explicit `min/most_likely/max` estimates. See [Running Simulations](running_simulations.md) for the full `generate` command reference.

??? tip "Alternative: write the YAML by hand"

    If you prefer full control, create `project.yaml` manually:

    ```yaml
    project:
      name: "Website Refresh"
      description: "Small example project"
      start_date: "2026-04-01"
      confidence_levels: [50, 80, 90]

    tasks:
      - id: "task_001"
        name: "Design updates"
        estimate:
          min: 2
          most_likely: 3
          max: 5
          unit: "days"

      - id: "task_002"
        name: "Frontend changes"
        estimate:
          min: 4
          most_likely: 6
          max: 10
          unit: "days"
        dependencies: ["task_001"]
        uncertainty_factors:
          team_experience: "medium"
          technical_complexity: "medium"
    ```

    See the [Project Files](project_files.md) reference for all available fields.



## Validate the file

Before simulating, check the file for errors:

```bash
mcprojsim validate project.yaml
```

Expected result:

```text
✓ Project file is valid!
```

If validation fails, read the reported field name and fix the YAML file before continuing.

Tip: common validation issues are missing `id` fields on tasks, invalid date formats, or incorrect field names — see [Project Files](project_files.md) for the full field reference and examples.



## Run your first simulation

```bash
mcprojsim simulate project.yaml --seed 42
```

What this does:

- Runs the default 10 000 Monte Carlo iterations
- Uses `--seed 42` so the result is reproducible
- Prints a summary to the terminal

Tip: increase precision with `--iterations` (tradeoff: runtime vs accuracy) and use `--seed` for reproducible runs; see [Running Simulations](running_simulations.md) for full CLI options.

You should see output like:

```text
mcprojsim, version 0.4.4
Progress: 100.0% (10000/10000)

=== Simulation Results ===
Project: Website Refresh
Hours per Day: 8.0
Mean: 126.93 hours (16 working days)
Median (P50): 125.74 hours
Std Dev: 17.68 hours
Coefficient of Variation: 0.1393
Skewness: 0.2267
Excess Kurtosis: -0.4206

Confidence Intervals:
  P50: 125.74 hours (16 working days)  (2026-04-23)
  P80: 142.59 hours (18 working days)  (2026-04-27)
  P90: 151.18 hours (19 working days)  (2026-04-28)

Sensitivity Analysis (top contributors):
  task_002: +0.8911
  task_001: +0.4236

Schedule Slack:
  task_001: 0.00 hours (Critical)
  task_002: 0.00 hours (Critical)

Most Frequent Critical Paths:
  1. task_001 -> task_002 (10000/10000, 100.0%)

No export formats specified. Use -f to export results to files.
```



## Export results

To generate report files, add `-f` with the desired formats:

```bash
mcprojsim simulate project.yaml --seed 42 -f json,csv,html
```

This creates files like:

```text
Website Refresh_results.json
Website Refresh_results.csv
Website Refresh_results.html
```

The HTML report is the best starting point — open it in your browser:

```bash
open "Website Refresh_results.html"     # macOS
xdg-open "Website Refresh_results.html" # Linux
```

Tip: export HTML first (`-f html`) to interactively inspect sensitivity, critical paths and charts — it is the easiest way to explore results visually.



## What the main results mean

| Percentile | Meaning | Typical use |
|------------|---------|-------------|
| **P50** | Half of simulated runs finish earlier | Internal discussion target |
| **P80** | 80% of runs finish earlier | Common management target |
| **P90** | 90% of runs finish earlier | Conservative commitment |

All durations are reported in **hours** (the canonical internal unit), with **working days** and **projected delivery dates** (weekends excluded) shown alongside.



## 7. Useful next commands

Run with more iterations for higher precision:

```bash
mcprojsim simulate project.yaml --iterations 50000 --seed 42
```

Use a custom configuration file:

```bash
mcprojsim simulate project.yaml --config my_config.yaml --seed 42
```

Suppress progress output (useful in CI/CD):

```bash
mcprojsim simulate project.yaml --quiet
```


## Where to go next

- [Introduction](introduction.md) — the ideas behind Monte Carlo project estimation
- [Your First Project](your_first_project.md) — build a richer project file step by step
- [Task Estimation](task_estimation.md) — T-shirt sizes, story points, and explicit ranges
- [Project Files](project_files.md) — complete project file reference
- [Configuration](../configuration.md) — customize uncertainty factors and mappings
- [Examples](../examples.md) — working example projects

## Try these example projects

- `examples/sample_project.yaml` — full sample with risks and resources
- `examples/quickstart_project.yaml` — minimal quickstart example used in this chapter
- `examples/resource_cap_small_task.yaml` — a small resource-constrained example to try constrained scheduling

## Next steps (recommended learning path)

- Beginner: follow this chapter and open the HTML report to inspect results.
- Intermediate: read [Your First Project](your_first_project.md) and [Task Estimation](task_estimation.md) to improve input quality.
- Advanced: explore [Configuration](../configuration.md), [Constrained Scheduling](constrained.md), and [MCP Server](mcp-server.md) for automation and integrations.

\newpage
