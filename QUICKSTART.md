# Quick Start: your first 10 minutes with `mcprojsim`

This guide is for end users who want to get from installation to a first simulation as quickly as possible.

In the next few minutes you will:

1. install `mcprojsim`
2. create a tiny project file
3. validate it
4. run a simulation
5. open the generated report

## Before you start

You need:

- Python 3.14 or newer
- a terminal
- `pipx` for the easiest CLI install

If you do not have `pipx` yet, install it first:

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

## 1. Install `mcprojsim`

```bash
pipx install mcprojsim
```

Verify that it works:

```bash
mcprojsim --version
mcprojsim --help
```

## 2. Create your first project file

Create a file named `project.yaml` with this content:

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

This example is intentionally small:

- one project
- two tasks
- one dependency
- one uncertainty profile

That is enough for a meaningful first simulation and the output will be

```bash
% mcprojsim simulate quickstart_example.yaml 
2026-03-09 06:18:07,536 - mcprojsim - INFO - Using default configuration
Loading project from quickstart_example.yaml...
2026-03-09 06:18:07,538 - mcprojsim - INFO - Loaded project: Website Refresh
Running simulation with 10000 iterations...
Progress: 10.0% (1000/10000)
Progress: 20.0% (2000/10000)
Progress: 30.0% (3000/10000)
Progress: 40.0% (4000/10000)
Progress: 50.0% (5000/10000)
Progress: 60.0% (6000/10000)
Progress: 70.0% (7000/10000)
Progress: 80.0% (8000/10000)
Progress: 90.0% (9000/10000)
Progress: 100.0% (10000/10000)

=== Simulation Results ===
Project: Website Refresh
Mean: 15.85 days
Median (P50): 15.67 days
Std Dev: 2.25 days

Confidence Intervals:
  P50: 15.67 days
  P80: 17.88 days
  P90: 18.97 days

Most Frequent Critical Paths:
  1. task_001 -> task_002 (10000/10000, 100.0%)

No export formats specified. Use -f to export results to files.
```

## 3. Validate the file

Before simulating, validate the input:

```bash
mcprojsim validate project.yaml
```

Expected result:

```text
✓ Project file is valid!
```

If validation fails, read the reported field name and fix the YAML file before continuing.

## 4. Run your first simulation

```bash
mcprojsim simulate project.yaml --seed 42
```

What this does:

- runs the default number of simulation iterations
- uses `--seed 42` so the result is reproducible
- writes result files into your current working directory

You should see a summary with values such as:

- mean duration
- median (`P50`)
- higher-confidence targets such as `P80` and `P90`

## 5. Open the generated results

After the run finishes, look for files like these:

```text
Website Refresh_results.json
Website Refresh_results.csv
Website Refresh_results.html
```

The most useful file for a first look is the HTML report.
Open it in your browser.

On macOS you can use:

```bash
open "Website Refresh_results.html"
```

## 6. Useful next commands

Run again with more iterations:

```bash
mcprojsim simulate project.yaml --iterations 50000 --seed 42
```

Use a custom configuration file:

```bash
mcprojsim simulate project.yaml --config my_config.yaml --seed 42
```

Suppress progress output:

```bash
mcprojsim simulate project.yaml --quiet
```

## What the main results mean

- `P50`: about a 50% chance of finishing within this duration
- `P80`: a more conservative planning target
- `P90`: a high-confidence planning target

A common practical pattern is:

- use `P50` for internal discussion
- use `P80` or `P90` for commitments where lateness matters

## If you want to go further

After this first run, the best next documents are:

- [docs/getting_started.md](docs/getting_started.md) — a fuller walkthrough
- [docs/user_guide/introduction.md](docs/user_guide/introduction.md) — Monte Carlo concepts
- [docs/user_guide/your_first_project.md](docs/user_guide/your_first_project.md) — build richer project files step by step
- [docs/user_guide/project_files.md](docs/user_guide/project_files.md) — project file reference
- [docs/configuration.md](docs/configuration.md) — uncertainty factors and config
- [docs/examples.md](docs/examples.md) — example projects

## Need a different installation path?

This guide intentionally focuses on the fastest end-user path.

If `pipx` is not the right fit, see:

- [README.md](README.md) for the project overview
- [docs/getting_started.md](docs/getting_started.md) for basic install and first-run material
- [scripts/README.md](scripts/README.md) if you are working from a source checkout
