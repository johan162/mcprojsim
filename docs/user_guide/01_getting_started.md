# Getting Started

Welcome to the Monte Carlo Project Simulator User Guide.

This short, hands-on chapter is meant to quickly show you mcprojsim in action. If you want a quick, practical tour, follow along: you'll create a sample project file, run a Monte Carlo simulation, and learn how to read the key results and reports. We keep theory to a minimum here — the goal is to spark your curiosity and get you producing real outputs quickly so you can explore the deeper chapters with a bit of context where more advanced concepts are introduced.

## What you'll learn

- Quick generation of a valid project file from a plain-text description.
- Running a reproducible Monte Carlo simulation and exporting report files.
- Using sensitivity and critical-path outputs to find the tasks that drive schedule risk.


## Before you start

You need:

- **Python 3.13 or newer**
- A terminal
- `pipx` for the easiest CLI install (recommended), or `pip`

If you do not have `pipx` yet:

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

## Install mcprojsim

### With pipx (recommended)

`pipx` installs command-line tools in their own isolated virtual environments while still making the command globally available on your `PATH`. This is important for a tool like `mcprojsim` for several reasons:

**Dependency isolation**
`pip install` drops packages directly into your system or user Python environment. If any dependency conflicts with something already installed — another tool, a framework, or a library your own code depends on — one of them will break silently or produce subtle wrong-version behaviour. `pipx` eliminates this entirely: every tool lives in its own throwaway environment that no other tool can disrupt.

**No accidental breakage of system Python**
On macOS and most Linux distributions, the system Python interpreter manages OS-level utilities. Polluting its site-packages with `pip install` can degrade or break unrelated system tools. `pipx` never touches the system interpreter.

**Easy upgrades and rollbacks**
```bash
pipx upgrade mcprojsim       # upgrade to latest
pipx install mcprojsim==0.10 # pin an exact version
pipx uninstall mcprojsim     # clean uninstall, no residue
```
Plain `pip` leaves orphaned package files behind on uninstall; `pipx` removes the entire environment atomically.

**Safe alongside virtual environments**
If you are already working inside a project `venv` or a Conda environment, `pipx` still installs into a separate location. Your project dependencies and the `mcprojsim` CLI remain fully decoupled.

**In summary**: use `pipx` when you want a CLI tool that just works, stays out of your way, and does not drift your Python environment over time.

```bash
pipx install mcprojsim
```

### With pip (if you know what you are doing!)

```bash
pip install mcprojsim
```
### Run mcprojsim using a Docker image from `ghcr.io`

If you prefer not to install Python or want to try `mcprojsim` without installing, you can run it using the official Docker image. 

You can run the image directly with `docker run`, but it is a bit more complex to set up and use.

```bash
docker run --rm -v "$(pwd)":/app ghcr.io/johan162/mcprojsim:latest --help
```

In the source distribution there is a helper script `mcprojsim.sh` that simplifies running the Docker image. It handles mounting the current directory and passing through command-line arguments, so you can use it as if `mcprojsim` were installed locally. It is available in the `bin/` directory of the repository, so you can copy it to a location on your `PATH` for easy access.

First pull the latest image:

```bash
docker pull ghcr.io/johan162/mcprojsim:latest
```

Then you can run `mcprojsim` commands using the `mcprojsim.sh` script (just be sure to put it in your `PATH` or always run it with `./mcprojsim.sh` from the directory where it is located). For example, to see the help message:

```bash
./mcprojsim.sh --help
```

## Verify the installation:

```bash
mcprojsim --version
mcprojsim --help
```

or , if you installed with Docker:

```bash
./mcprojsim.sh --version
./mcprojsim.sh --help
```

Note: You need to add the location of `mcprojsim.sh` to your `PATH` or always run it with `./mcprojsim.sh` from the directory where it is located

## Creating the project specification file

Project files describe the project to be simulated and is written in a (fairly) easy to
read YAML format. Here we will only touch on the essentials needed to simulate a basic 
project.

See the [Project Files](project_files.md) reference for all available fields.

The project file below defines a basic project `"Website Refresh"` with two tasks where the 
second task depends on the first one finishing. Most fields should be easy to understand
but the `confidence_levels` deserves a closer explanation. 

The project simulation results are statistical analysis. This means the result is not single
number when the project is done. Instead the result is a range of numbers with an associated
confidence of success. With the numbers given in the project file the result will be the
`50%`, `80%`, and `90%` confidence levels. 

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
      low: 2
      expected: 3
      high: 5
      unit: "days"
  - id: "task_002"
    name: "Frontend changes"
    estimate:
      low: 4
      expected: 6
      high: 10
      unit: "days"
    dependencies: ["task_001"]
    uncertainty_factors:
      team_experience: "medium"
      technical_complexity: "medium"
```


## Generating a project file

An alternative way than get all project files details right is to describe your project in plain text and let `mcprojsim generate` command produce the detailed YAML project specification from a less strict textual description of a project.

Create a file named `description.txt` and write the following (indentation and blank rows has no meaning)

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

That is it — the generated `project.yaml` is ready for validation and simulation. You can use T-shirt sizes (`XS`, `S`, `M`, `L`, `XL`, `XXL`), story points, or explicit `low/expected/high` estimates. See [Running Simulations](running_simulations.md) for the full `generate` command reference.

!!! tip "Flexible input formats"
    You don't have to use the `Task N:` header format. The parser also accepts plain numbered lists, bullet lists, and even inline sizes — great for copy-paste from meeting notes or planning tools:

    ```text
    Project name: Website Refresh
    Start date: 2026-04-01

    1. Design updates [S]
    2. Frontend changes (M) depends on Task 1
    ```

    See [Natural Language Input](nl_processing.md) for the full range of supported formats.


## Validate the file

Before simulating, check the file for errors:

```bash
mcprojsim validate project.yaml
```

Expected result:

```text
Validating project.yaml...
✓ Project file is valid!
```

If validation fails, read the reported field name and fix the YAML file before continuing.

Tip: common validation issues are missing `id` fields on tasks, invalid date formats, or incorrect field names — see [Project Files](project_files.md) for the full field reference and examples.


## Run your first simulation

Simulation is done with the `simulate` command as shown below. The optional flag `--seed` is used to
specify a seed for the simulation. This is useful to be able to get repeatable results or to see how
specific changes in the project (such as adding risks) alters the result of the simulation 
while keeping everything else the same. If no seed is specified an automatic random seed is used.

```bash
mcprojsim simulate project.yaml --seed 42
```

What this does:

- Runs the default 10 000 Monte Carlo iterations
- Uses `--seed 42` so the result is reproducible
- Prints a summary to the terminal

Tip: increase precision with `--iterations` (tradeoff: runtime vs accuracy) and use `--seed` for reproducible runs; see [Running Simulations](running_simulations.md) for full CLI options.

Depending on the version of `mcprojsim` used the output will look something like the following (numbers will vary by version and platform):

```text
mcprojsim, version 0.12.0
Progress: 100.0% (10000/10000)
Simulation time: 0.62 seconds
Peak simulation memory: 1.48 MiB

=== Simulation Results ===

Project Overview:
Project: Website Refresh
Hours per Day: 8.0
Max Parallel Tasks: 1
Schedule Mode: dependency_only

Calendar Time Statistical Summary:
Mean: 126.93 hours (16 working days)
Median (P50): 125.74 hours
Std Dev: 17.68 hours
Minimum: 78.43 hours
Maximum: 184.27 hours
Coefficient of Variation: 0.1393
Skewness: 0.2267
Excess Kurtosis: -0.4206

Project Effort Statistical Summary:
Mean: 126.93 person-hours (16 person-days)
Median (P50): 125.74 person-hours
Std Dev: 17.68 person-hours
Minimum: 78.43 person-hours
Maximum: 184.27 person-hours
Coefficient of Variation: 0.1393
Skewness: 0.2267
Excess Kurtosis: -0.4206

Calendar Time Confidence Intervals:
  P50: 125.74 hours (16 working days)  (2026-04-23)
  P80: 142.59 hours (18 working days)  (2026-04-27)
  P90: 151.18 hours (19 working days)  (2026-04-28)

Effort Confidence Intervals:
  P50: 125.74 person-hours (16 person-days)
  P80: 142.59 person-hours (18 person-days)
  P90: 151.18 person-hours (19 person-days)

Sensitivity Analysis (top contributors):
  task_002: +0.8911
  task_001: +0.4236

Schedule Slack:
  task_001: 0.00 hours (Critical)
  task_002: 0.00 hours (Critical)

Most Frequent Critical Paths:
  1. task_001 -> task_002 (10000/10000, 100.0%)

Staffing (based on mean effort): 1 people recommended (mixed team), 19 working days
  Total effort: 127 person-hours (16 person-days) | Parallelism ratio: 1.0

No export formats specified. Use -f to export results to files.
```

## Export results

To generate report files, add `-f` with the desired formats:

```bash
mcprojsim simulate project.yaml --seed 42 -f json,csv,html
```

If you want to control where the files are written and what base name they use, add `-o` as well:

```bash
mcprojsim simulate project.yaml --seed 42 -o results/website_refresh -f json,csv,html
```

This creates files like:

```text
Website Refresh_results.json
Website Refresh_results.csv
Website Refresh_results.html
```

With `-o results/website_refresh`, the exported files would instead use that path prefix:

```text
results/website_refresh.json
results/website_refresh.csv
results/website_refresh.html
```

The HTML report is the best starting point — open it in your browser:

```bash
open "Website Refresh_results.html"     # macOS
xdg-open "Website Refresh_results.html" # Linux
```

Tip: export HTML first (`-f html`) to inspect sensitivity, critical paths, and charts in the rendered report — it is the easiest way to explore results visually.
 
## What the main results mean

The output is organised into sections. Here is what each section means:

**Project Overview** shows that this is a dependency-only simulation (no resource constraints). `Max Parallel Tasks` is the peak number of tasks that ran in parallel across all iterations.

**Calendar Time Statistical Summary** describes the *elapsed project duration* distribution. This is how long the project takes from start to finish on the calendar, based on the 10,000 simulated runs.

**Project Effort Statistical Summary** describes total *person-hours* across all tasks. For a single-developer project with sequential tasks the two summaries are identical; they diverge once tasks run in parallel or resources are constrained.

The confidence interval table, like this:

| Percentile | Meaning | Typical use |
|------------|---------|-------------|
| **P50** | Half of simulated runs finish earlier | Internal discussion target |
| **P80** | 80% of runs finish earlier | Common management target |
| **P90** | 90% of runs finish earlier | Conservative commitment |

is shown twice — once for calendar time and once for effort — with projected delivery dates (weekends excluded) shown alongside each calendar row.

The other sections in the sample output are worth a quick first-pass explanation too:

- **Sensitivity Analysis** shows which tasks are most strongly associated with the overall finish date moving later. Higher positive values usually mean those tasks are stronger schedule drivers.
- **Schedule Slack** shows how much a task can slip before it starts delaying the overall project. A task marked **Critical** has essentially no slack.
- **Most Frequent Critical Paths** shows the dependency chains that most often determine the final finish date across the Monte Carlo runs.
- **Staffing** is an advisory recommendation for team size derived from the simulated effort and parallelism.

At this level, treat these as decision aids:

- percentiles help you choose a date target
- sensitivity helps you see where uncertainty matters most
- critical paths and slack help you see where sequencing risk is concentrated



## Useful next commands

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
- [Configuration](configuration.md) — customize uncertainty factors and mappings
- [Examples](../examples.md) — working example projects
- [Constrained Scheduling](constrained.md), for modeling resource limits and their impact on schedules
- [MCP Server](mcp-server.md), for AI-assisted project file generation and integration

## Try these example projects

- `examples/sample_project.yaml` — full sample with risks and resources
- `examples/quickstart_project.yaml` — minimal quickstart example used in this chapter
- `examples/resource_cap_small_task.yaml` — a small resource-constrained example to try constrained scheduling

\newpage
