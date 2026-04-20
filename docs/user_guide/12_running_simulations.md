# Running simulations

This chapter is a reference for the `mcprojsim` command-line interface. It covers all four commands: `generate`, `validate`, `simulate`, and `config`.



## Command overview

| Command | Purpose |
|---------|---------|
| `mcprojsim generate` | Create a project YAML file from a natural language description |
| `mcprojsim validate` | Check a project file for errors without running a simulation |
| `mcprojsim simulate` | Run a Monte Carlo simulation and produce results |
| `mcprojsim config` | Display the active configuration |

A typical workflow runs these commands in sequence: generate (or write by hand) → validate → simulate.



## `mcprojsim generate`

Converts a plain-text project description into a syntactically correct YAML project file. The parser runs locally — no AI service or network access is required.

### Usage

```bash
mcprojsim generate INPUT_FILE [-o OUTPUT_FILE] [--validate-only] [-v]
```

### Options

| Option | Description |
|--------|-------------|
| `INPUT_FILE` | Path to a plain-text file containing the project description (required) |
| `-o`, `--output FILE` | Write the generated YAML to a file. If omitted, the YAML is printed to stdout |
| `--validate-only` | Check the description for issues without generating output |
| `-v`, `--verbose` | Show detailed informational messages (e.g. file loaded, tasks parsed) |

### Examples

```bash
# Print generated YAML to the terminal
mcprojsim generate description.txt

# Save to a file
mcprojsim generate description.txt -o my_project.yaml

# Validate the description without generating
mcprojsim generate --validate-only description.txt

# Generate and then simulate in one pipeline
mcprojsim generate description.txt -o project.yaml && mcprojsim simulate project.yaml
```

### Input format

The input file is a semi-structured text description. See [MCP Server & Natural Language Project Input](16_mcp-server.md) for the full input format reference, supported fields, and examples.

A minimal example:

```text
Project name: My Project
Start date: 2026-04-01
Task 1:
- Design phase
- Size: M
Task 2:
- Implementation
- Depends on Task 1
- Size: XL
```



## `mcprojsim validate`

Checks a YAML or TOML project file for structural and semantic errors.

### Usage

```bash
mcprojsim validate PROJECT_FILE [-v]
```

### Options

| Option | Description |
|--------|-------------|
| `-v`, `--verbose` | Show detailed informational messages |

### Examples

```bash
mcprojsim validate project.yaml
```

Successful output:

```text
✓ Project file is valid!
```

If the file has errors, the validator reports the issue and aborts:

```text
✗ Validation failed:
  Task 'task_003' depends on 'task_999', which does not exist
```

It is good practice to validate before every simulation, especially after editing a file or generating one with `mcprojsim generate`.



## `mcprojsim simulate`

Runs the Monte Carlo simulation on a validated project file.

### Usage

```bash
mcprojsim simulate PROJECT_FILE [OPTIONS]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `-n`, `--iterations NUM` | Number of simulation iterations | 10000 |
| `-c`, `--config FILE` | Custom configuration file | built-in defaults |
| `-s`, `--seed INT` | Random seed for reproducibility | random |
| `-o`, `--output PATH` | Output file base path (without extension) | project name |
| `-f`, `--output-format FORMATS` | Comma-separated export formats: `json`, `csv`, `html` | none |
| `--critical-paths N` | Number of critical paths to display | config default: 2 |
| `--number-bins N` | Number of histogram bins for distribution charts in JSON, CSV, and HTML exports. Overrides the config file setting if specified. | 50 |
| `--target-budget AMOUNT` | Report probability of staying within the provided budget amount | none |
| `--full-cost-detail` | Include per-iteration task-cost arrays in JSON output | off |
| `--no-fx` | Disable exchange-rate fetches for secondary currency reporting | off |
| `-q`, `-qq`, `--quiet` | Reduce CLI output verbosity. Use `-q` to suppress detailed output, or `-qq` to suppress all normal output | off |
| `-v`, `--verbose` | Show detailed informational messages (config loaded, project parsed, etc.) | off |
| `-t`, `--table` | Format tabular output sections (confidence intervals, sensitivity, slack, risk impact, staffing) as ASCII tables | off |
| `-m`, `--minimal` | Show minimal console output: version, project overview, calendar/effort statistical summaries, and calendar confidence intervals only | off |
| `--staffing` | Show full staffing analysis table with team-size recommendations per experience profile | off |
| `--tshirt-category CATEGORY` | Override default T-shirt category for bare values like `M` during this run | config setting |
| `--target-date DATE` | Target completion date (`YYYY-MM-DD`) to calculate probability of meeting | none |
| `--velocity-model MODEL` | Override the sprint planning velocity model for how to use historic data (`empirical` or `neg_binomial`). Applies only when sprint planning is enabled in the project file. | project file setting |
| `--no-sickness` | Disable sickness modelling regardless of the project file setting. Applies only when sprint planning is enabled. | off |
| `--include-historic-base` | Add a `Historic Base` section to HTML reports (historic summary + committed/completed bar chart) and include matching historic baseline rows/summary in JSON under `sprint_planning.historic_base`. **Requires `-f` to include `json` or `html`.** | off |
| `--two-pass` | Enable criticality two-pass scheduling. Only has effect when resource-constrained scheduling is active. Overrides the config file `assignment_mode` setting. | off |
| `--pass1-iterations N` | Number of pass-1 iterations for criticality ranking when `--two-pass` is used. Capped to `--iterations`. | 1000 (from config) |
| `--workers N \| auto` | Number of worker processes for parallel simulation. Pass a positive integer or `auto` to use all available CPUs. Ignored when iterations or task count is below the parallel threshold. | 1 (sequential) |

### Examples

```bash
# Default simulation
mcprojsim simulate project.yaml

# Reproducible run with a seed
mcprojsim simulate project.yaml --seed 42

# More iterations for higher precision
mcprojsim simulate project.yaml --iterations 50000 --seed 42

# Custom configuration
mcprojsim simulate project.yaml --config my_config.yaml

# Export to all formats
mcprojsim simulate project.yaml -f json,csv,html -o results/my_project

# Custom histogram bins for more granular distribution charts
mcprojsim simulate project.yaml -f json,csv,html --number-bins 100 -o results/my_project

# Budget probability analysis
mcprojsim simulate project.yaml --target-budget 45000

# Include full task-cost arrays in JSON export
mcprojsim simulate project.yaml -f json --full-cost-detail

# Disable FX lookups (offline/CI mode)
mcprojsim simulate project.yaml --no-fx

# Quiet mode (suppress progress bars)
mcprojsim simulate project.yaml --quiet

# Fully quiet mode (suppress all normal CLI output)
mcprojsim simulate project.yaml -qq

# Verbose mode (show config/project loading details)
mcprojsim simulate project.yaml --verbose

# Table mode (ASCII tables for tabular sections)
mcprojsim simulate project.yaml --table

# Minimal output mode (core summaries only)
mcprojsim simulate project.yaml --minimal

# Show staffing recommendations
mcprojsim simulate project.yaml --staffing

# Override bare T-shirt sizes to use the epic category
mcprojsim simulate project.yaml --tshirt-category epic

# Staffing with table formatting
mcprojsim simulate project.yaml --staffing --table
```

```bash
# Sprint planning: switch velocity model to negative binomial
mcprojsim simulate sprint_project.yaml --velocity-model neg_binomial

# Sprint planning: disable sickness modelling
mcprojsim simulate sprint_project.yaml --no-sickness

# Include Historic Base in HTML/JSON exports
mcprojsim simulate sprint_project.yaml -f json,html --include-historic-base
```

```bash
# Parallel simulation: use 4 worker processes
mcprojsim simulate project.yaml --workers 4 --seed 42

# Parallel simulation: use all available CPUs
mcprojsim simulate project.yaml --workers auto --seed 42

# Force sequential execution explicitly
mcprojsim simulate project.yaml --workers 1
```

### Output

By default, the simulation prints a plain-text summary. With `--table` (`-t`), the project overview, statistical summaries, confidence intervals, sensitivity analysis, schedule slack, and risk impact sections are all formatted as ASCII tables with column headers and box-drawing borders:

```text
Calendar Time Confidence Intervals:
┌──────────────┬─────────┬────────────────┬────────────┐
│ Percentile   │   Hours │   Working Days │ Date       │
├──────────────┼─────────┼────────────────┼────────────┤
│ P25          │  522.75 │             66 │ 2026-02-02 │
│ P50          │  571.84 │             72 │ 2026-02-10 │
│ P90          │  682.94 │             86 │ 2026-03-02 │
│ P99          │  790.61 │             99 │ 2026-03-19 │
└──────────────┴─────────┴────────────────┴────────────┘
```

#### Staffing output

A short staffing advisory is always included at the end of the output (unless `--quiet` is active):

```text
Staffing (based on mean effort): 3 people recommended (mixed team), 38 working days
  Total effort: 910 person-hours (114 person-days) | Parallelism ratio: 1.6
```

By default the staffing analysis uses **mean** effort and elapsed time. To base it on a specific confidence level, set `staffing.effort_percentile` in your configuration file:

```yaml
staffing:
  effort_percentile: 80  # use P80 effort and elapsed time
```

If `staffing.effort_percentile` is omitted, mean effort and mean elapsed time are used. The mean effort is calculated as the average total effort across all iterations, and the mean elapsed time is the average project duration. If the distribution is symmetric, the mean and median (P50) will be close, but for skewed distributions they can differ significantly. 

If the percentile is set to a higher value like 80 or 90, the staffing recommendation will be based on a more conservative estimate of effort and elapsed time, which can lead to recommending more staff to mitigate the risk of overruns. A staffing percentile of 90, for example, would recommend a team size that has a 90% chance of completing the project within the estimated effort and time, providing a buffer against uncertainty.

The reason we say both effort and elapsed time is that the staffing model considers both how much total work there is (effort) and how long the project takes (elapsed time) to determine how many people are needed. A higher effort percentile means the model assumes a higher total workload, while a higher elapsed time percentile means it assumes a longer project duration. Both factors influence the recommended team size to ensure the project can be completed within the desired confidence level.

The reason they are not separated into `staffing.effort_percentile` and `staffing.elapsed_time_percentile` is that they are inherently linked in the staffing model. The number of staff needed depends on both the total effort and the project duration, so it makes sense to use the same confidence level for both to maintain consistency in the risk tolerance. If they were set separately, it could lead to conflicting recommendations (e.g., a high effort percentile but a low elapsed time percentile might recommend more staff than necessary, or vice versa). By using a single `effort_percentile`, we ensure that the staffing recommendation is based on a coherent risk profile.

With this setting the output changes to:

```text
Staffing (based on P80 effort percentile): 3 people recommended (mixed team), 42 working days
  Total effort: 1,024 person-hours (128 person-days) | Parallelism ratio: 1.6
```

Using a higher percentile produces more conservative staffing (since we want to be more confident in our recommendations because it accounts for higher-effort scenarios).

Pass `--staffing` to expand this into a full table for each experience profile (senior, mixed, junior). With `--table`:

```text
Staffing Analysis (senior team, overhead=4%/person, productivity=100%):
  Effort basis: mean (910 person-hours, 571 critical-path hours)
┌─────────────┬─────────────────┬────────────────┬─────────────────┬──────────────┐
│ Team Size   │ Eff. Capacity   │ Working Days   │ Delivery Date   │ Efficiency   │
├─────────────┼─────────────────┼────────────────┼─────────────────┼──────────────┤
│ 1           │ 1.00            │ 114            │ 2026-06-15      │ 100.0%       │
│ 2           │ 1.92            │ 60             │ 2026-03-27      │ 96.0%        │
│ 3 *         │ 2.76            │ 42             │ 2026-03-02      │ 92.2%        │
└─────────────┴─────────────────┴────────────────┴─────────────────┴──────────────┘
```

The `*` suffix in the "Team Size" column marks the recommended team size for that profile. Without `--table`, the same information appears in plain indented text with `<-- recommended` annotations. See [Interpreting Results — Staffing recommendations](13_interpreting_results.md#staffing-recommendations) for a detailed explanation of the model and columns.

Without `--table`, the same data is printed as indented text:

```text
=== Simulation Results ===

Project Overview:
Project: Website Refresh
Hours per Day: 8.0
Max Parallel Tasks: 2
Schedule Mode: dependency_only

Calendar Time Statistical Summary:
Mean: 126.78 hours (16 working days)
Median (P50): 125.36 hours
Std Dev: 18.01 hours
Minimum: 98.40 hours
Maximum: 192.30 hours
Coefficient of Variation: 0.1421
Skewness: 0.4123
Excess Kurtosis: -0.2341

Project Effort Statistical Summary:
Mean: 232.45 person-hours (30 person-days)
Median (P50): 229.80 person-hours
Std Dev: 34.22 person-hours
...

Calendar Time Confidence Intervals:
  P50: 125.36 hours (16 working days)  (2026-04-22)
  P80: 143.08 hours (18 working days)  (2026-04-24)
  P90: 151.74 hours (19 working days)  (2026-04-27)

Most Frequent Critical Paths:
  1. task_001 -> task_002 (10000/10000, 100.0%)

Staffing (based on mean effort): 3 people recommended (mixed team), 38 working days
  Total effort: 910 person-hours (114 person-days) | Parallelism ratio: 1.6
```

When export formats are specified with `-f`, the following files are created:

| Format | Content |
|--------|---------|
| `json` | Full machine-readable results including histogram data |
| `csv` | Tabular summary with statistics, percentiles, and critical paths |
| `html` | Interactive report with thermometer chart and distribution histogram |



## `mcprojsim config`

Displays the active configuration (uncertainty factor multipliers, T-shirt size mappings, story point mappings, simulation defaults).

### Usage

```bash
mcprojsim config [-c CONFIG_FILE] [--list] [--generate]
```

### Options

| Option | Description |
|--------|-------------|
| `-c`, `--config-file FILE` | Show configuration merged with a custom YAML file |
| `--list`, `--show` | List current configuration settings. Alias `--show` is identical. When omitted, the same output is produced by default for backward compatibility. |
| `--generate` | Write the built-in default configuration to `~/.mcprojsim/config.yaml` |

!!! note
    The auto-loaded user default configuration file (applied automatically when no `-c` flag is given to any command) lives at `~/.mcprojsim/configuration.yaml` — note the full name `configuration.yaml`, not `config.yaml`. The `--generate` flag writes to `config.yaml` as a starting template; rename it to `configuration.yaml` if you want it to be picked up automatically.

### Examples

```bash
# Show built-in defaults (all three forms are equivalent)
mcprojsim config
mcprojsim config --list
mcprojsim config --show

# Show a custom configuration merged with defaults
mcprojsim config --config-file my_config.yaml
mcprojsim config --list --config-file my_config.yaml

# Generate a default configuration file at ~/.mcprojsim/config.yaml
mcprojsim config --generate
```


## Parallel simulation

By default `mcprojsim simulate` runs iterations sequentially on a single process. For large iteration counts or computationally heavy projects you can distribute the work across multiple CPU cores with `--workers`.

### How it works

When `--workers N` is set and both the iteration count and task count both exceed an absolute minimum thresholds (500 iterations and 5 tasks respectively) but also exceeds heuristic limits that takes how heavy
the execution are into account. For example, a dependency-only simulation (no resource constrains) will almost never benefit from parallel execution as each iteration is trivial and most time will be spent 
in the parallel overhead. Hence, only one worker will be deployed in all but the most extreme dependency-only simulations.

If the heuristics finds that several workers are beneficial the engine will:

1. Partitions the total iterations into many small micro-chunks (more chunks than workers for smooth progress and load balancing).
2. Submits chunks to a short-lived `ProcessPoolExecutor` with `N` workers, using the `spawn` start method for safety on all platforms.
3. Merges results in deterministic order after all workers finish.
4. Runs the normal post-processing (`_build_results`, statistics, sensitivity analysis) in the parent process.

For smaller workloads the engine falls back to the sequential path automatically, so `--workers 4` on a tiny project has no overhead cost.

Progress reporting still works in parallel mode. When stdout progress is enabled, updates are emitted as chunks complete. If you use `progress_callback`, it remains active even when stdout progress is disabled. Single-pass runs report `iterations` as the total; two-pass runs report `pass1_iterations + iterations` as the total so callback progress stays monotonic across both phases. Parallel mode may therefore call the callback more frequently than sequential mode.

### Reproducibility

Results are deterministic for a fixed `(--seed, --workers)` combination. Changing the number of workers changes how the random seed is partitioned across chunks, so the exact duration values will differ between a 1-worker run and a 4-worker run even with the same seed. To reproduce results exactly, use the same `--workers` value as the original run.

> The sequential path (`--workers 1`) is unchanged by this feature. Two runs with `--workers 1` and the same `--seed` produce bit-for-bit identical output.

### Performance expectations

Parallel execution adds fixed overhead:

- Process pool startup and teardown (~50–200 ms per run on typical hardware).
- Argument serialisation and result deserialisation across worker processes.
- Serial post-processing (statistics, sensitivity analysis) after merge.

Because of this overhead, parallel mode is most beneficial for larger workloads:

| Workload | Expected speedup on 8 cores |
|----------|---------------------------:|
| < 500 iterations or < 5 tasks | Falls back to sequential |
| ~10 000 iterations, ~30 tasks | Roughly 2× to 4× |
| Heavy workloads with minimal post-processing | Up to ~4× to 5× |

Benchmark your own project with `--workers 1`, `--workers 2`, `--workers 4`, and `--workers auto` to find the best setting.

### Usage

```bash
# Use 4 worker processes
mcprojsim simulate project.yaml --workers 4 --seed 42

# Use all available CPUs
mcprojsim simulate project.yaml --workers auto --seed 42

# Force sequential (default)
mcprojsim simulate project.yaml --workers 1
```


\newpage

