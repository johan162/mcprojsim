# Running simulations

This chapter is a reference for the `mcprojsim` command-line interface. It covers all four commands: `generate`, `validate`, `simulate`, and `config show`.

---

## Command overview

| Command | Purpose |
|---------|---------|
| `mcprojsim generate` | Create a project YAML file from a natural language description |
| `mcprojsim validate` | Check a project file for errors without running a simulation |
| `mcprojsim simulate` | Run a Monte Carlo simulation and produce results |
| `mcprojsim config show` | Display the active configuration |

A typical workflow runs these commands in sequence: generate (or write by hand) → validate → simulate.

---

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

The input file is a semi-structured text description. See [MCP Server & Natural Language Project Input](mcp-server.md) for the full input format reference, supported fields, and examples.

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

---

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

---

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
| `--critical-paths N` | Number of critical paths to display | 2 |
| `-q`, `--quiet` | Suppress progress output | off |
| `-v`, `--verbose` | Show detailed informational messages (config loaded, project parsed, etc.) | off |
| `--target-date DATE` | Target completion date (`YYYY-MM-DD`) to calculate probability of meeting | none |

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

# Quiet mode (suppress progress bars)
mcprojsim simulate project.yaml --quiet

# Verbose mode (show config/project loading details)
mcprojsim simulate project.yaml --verbose
```

### Output

The simulation prints a summary to the terminal:

```text
=== Simulation Results ===
Project: Website Refresh
Hours per Day: 8.0
Mean: 126.78 hours (16 working days)
Median (P50): 125.36 hours
Std Dev: 18.01 hours

Confidence Intervals:
  P50: 125.36 hours (16 working days)  (2026-04-22)
  P80: 143.08 hours (18 working days)  (2026-04-24)
  P90: 151.74 hours (19 working days)  (2026-04-27)

Most Frequent Critical Paths:
  1. task_001 -> task_002 (10000/10000, 100.0%)
```

When export formats are specified with `-f`, the following files are created:

| Format | Content |
|--------|---------|
| `json` | Full machine-readable results including histogram data |
| `csv` | Tabular summary with statistics, percentiles, and critical paths |
| `html` | Interactive report with thermometer chart and distribution histogram |

---

## `mcprojsim config show`

Displays the active configuration (uncertainty factor multipliers, T-shirt size mappings, story point mappings, simulation defaults).

### Usage

```bash
mcprojsim config show [--config-file FILE]
```

### Examples

```bash
# Show built-in defaults
mcprojsim config show

# Show a custom configuration merged with defaults
mcprojsim config show --config-file my_config.yaml
```
