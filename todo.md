# Project TODO for MVP

The goal is to implement all MVP requirements in `docs/mcprojsim_reqs.md` to be able to reach 1.0.0

## Not implemented yet

### 1. Two-pass critical-path-aware simulation mode (FR-034, FR-042)

The requirements specify a configurable two-pass scheduling mode where:
- Pass 1 computes baseline criticality indices under resource/calendar constraints
- Pass 2 prioritizes assignments for tasks ranked by pass-1 criticality
- The system reports pass-1 versus pass-2 outcome deltas for traceability

Current state:

- only single-pass greedy assignment is implemented
- no CLI or config toggle to enable two-pass mode
- no acceptance tests for pass-delta behavior

### 2. Environment-based configuration selection (FR-012)

Current state:

- a single config file can be loaded
- defaults can be merged with user overrides

What is missing:

- no built-in `dev` / `prod` / `team` environment profile selection
- no environment-aware config resolution

### 3. Sickness duration configuration in config.yaml (FR-040)

Sickness duration distribution parameters are hardcoded in the scheduler (`sigma=0.5`, `mode_days=2.0`). The requirements specify these should be configurable via configuration.

What is missing:

- no sickness configuration section in `config.yaml` schema
- no way to override sickness-duration mode or dispersion per project or config file
- per-member `sickness_prob` is configurable but the duration model is not

### 4. Pluggable distribution and risk model architecture (NFR-008)

The requirements specify that distribution types and risk models should be pluggable/extensible.

Current state:

- distributions use a hardcoded `if/elif` dispatch on `DistributionType` enum
- only `TRIANGULAR` and `LOGNORMAL` are supported
- risk models are not extensible beyond the built-in `PERCENTAGE` / `ABSOLUTE` impact types
- no plugin or factory pattern for adding new distribution or risk model types


## Partially implemented

### 1. Output configuration is modeled, but not fully honored

Current state:

- config supports `output.formats`, `include_histogram`, and `histogram_bins`
- CLI can print those settings

What is missing:

- CLI export behavior is driven by `--output-format`, not `config.output.formats`
- exporters always generate histograms instead of honoring `config.output.include_histogram`
- all three exporters hardcode 50 bins instead of using `config.output.histogram_bins`

### 2. Logging is only partially configurable (NFR-010)

Current state:

- logs include timestamps, logger name, and level
- the logging helper accepts a log-level argument
- `-v` / `--verbose` sets INFO level

What is missing:

- no `--log-level` CLI option for arbitrary level selection (DEBUG, INFO, WARNING, ERROR)
- no config-file-driven log level
- no environment-driven logging configuration in the main workflow

### 3. Progress reporting interval mismatch (FR-013)

Current state:

- progress can be shown during simulation
- quiet mode is supported
- progress reports every 10% of iterations

What is missing:

- requirement says every **5%** of iterations **or** every 1000 iterations (whichever comes first)
- implementation reports at 10% intervals only
- for smaller runs (< 10k iterations), progress can be sparser than required

### 4. Default percentile coverage does not include P10 (FR-010)

Current state:

- the engine computes percentiles listed in `project.confidence_levels`
- default confidence levels are `[25, 50, 75, 80, 85, 90, 95, 99]`

What is missing:

- requirements call out `P10, P25, P50, P75, P80, P90, P95, P99`
- `P10` is not produced by default (users can add it per-project but it is not in the default list)

### 5. Documentation gaps

Current state:

- All major functionality and grammar are documented
- Detailed step-by-step guide to write project files are done
- README and QUICKSTART guides done

What is missing:

- Complete user guide section on how configuration affects simulation
- More in-depth description of risks and uncertainty factors and how to determine those
- Migration guidance for adopting explicit team/resource definitions (FR-036)


# Completed

### Resource-constrained scheduling and calendar enforcement (FR-009, FR-026–FR-039)

- `ResourceSpec` and `CalendarSpec` are full Pydantic models with validation
- `team_size` auto-populates resources; explicit resources validated against team_size
- scheduler implements both `dependency_only` and `resource_constrained` modes
- calendars, holidays, planned absence, and sickness episodes enforced during scheduling
- `max_resources` and `min_experience_level` enforced per task
- deterministic greedy assignment with sorted tie-breaking for reproducibility
- sickness modeled via daily Bernoulli start + log-normal duration
- resource utilization, wait time, and calendar delay diagnostics reported
- CLI, JSON, CSV, HTML exports distinguish schedule mode and include resource metrics

### Critical path reporting as full path sequences (FR-008, FR-019)

- each iteration records full critical path sequences
- results aggregate the most frequent full critical paths across runs
- the number of stored paths is configurable in `config.yaml`
- CLI and exporters report canonical full critical path sequences

### Validation with line numbers and structured reports (FR-001, FR-015)

- YAML and TOML parsers report line-number-aware error messages
- `validate_project_payload()` detects unknown fields with typo suggestions
- `ValidationIssue` dataclass provides structured reports with path, message, and suggestion
- numeric ranges, dates, dependency references, circular dependencies, resource/calendar references all validated

### Sensitivity analysis fully integrated (FR-011)

- Spearman rank correlations computed automatically during simulation
- sensitivity results stored in `SimulationResults.sensitivity`
- CLI displays top 10 contributors to schedule variance
- JSON, CSV, and HTML exports include sensitivity metrics
- HTML includes tornado chart visualization


### Staffing analysis and team-size recommendations (FR-025)

- Brooks's Law communication-overhead model with configurable per-person penalty
- three configurable experience profiles (senior, mixed, junior)
- recommended team size computed as smallest where adding one more yields < 5% improvement
- staffing table with team size, effective capacity, calendar days, delivery date, efficiency
- `--staffing` CLI flag shows full table; advisory always shown in default output
- staffing data included in JSON, CSV, and HTML exports

### Delivery date forecasting and target-date probability (FR-017)

- simulated effort converted to working-day counts using `hours_per_day`
- forecast delivery dates calculated for reported confidence levels when start date is available
- `--target-date` computes probability of completion on or before specified date

### Schedule slack analysis (FR-018)

- total float calculated per task via backward pass from project end
- mean slack reported across simulation iterations
- tasks with effectively zero slack identified as critical

### Risk impact summary reporting (FR-020)

- realized task-level risk impact tracked during simulation
- mean realized risk impact per task reported
- task-level risk trigger rate and mean impact when triggered reported

### Extended distribution shape statistics (FR-024)

- skewness and excess kurtosis calculated for simulated duration distribution
- included in CLI output, SimulationResults, and all export formats

### Natural-language parsing and project generation (FR-021, FR-022, FR-023)

- NL parser extracts project metadata, tasks, dependencies, estimates (T-shirt, story points, explicit)
- resources, calendars, and task-level constraints parsed from NL input
- `generate` command produces syntactically correct YAML with normalized task IDs
- `--validate-only` reports warnings and errors without generating a file
- MCP server exposes `generate_project_file`, `validate_project_description`, and `simulate_project` tools

### Story points and T-shirt size estimates (FR-016)

- story points (1, 2, 3, 5, 8, 13, 21) converted to effort via configurable mappings
- T-shirt sizes (XS, S, M, L, XL, XXL) converted to effort via configurable mappings
- unit settings available for both estimate types
