# Project Roadmap

## Getting to MVP

The goal is to implement all MVP requirements in `docs/mcprojsim_reqs.md` to be able to reach 1.0.0


### Next patch release

Release: 0.15.1

Tasks:
- Repaginate user guide with pagination macros for B5 & A4
- Verify basic simulation results with old MC spreadhseet

Completed Tasks:
- Fix table formatting
- Review Dev guide so it is up to date
- Review User Guide (and fix broken links) to make sure it hasn't drifted
- Review EBNF Grammar
- Review top-level README
- Support `--list` flag for `config` command verb


## Post-MVP (1.0.0) Themes

Ideas on what to focus future development on

- Forecast calibration and trustworthiness.
- Better handling of non-stationary teams and changing backlog behavior.
- Stronger scenario planning and policy simulation.
- MCP and NL parser upgrades that reduce user ambiguity and rework.


### High-Value New Functionality 

1. Backtesting and calibration reports.
    - Automatically replay past projects/sprints and score forecast quality.
    - Report calibration metrics like coverage of P50/P80/P90, Brier-like reliability, and bias drift.
    - This is one of the highest ROI features because it tells users when to trust the model.

2. Regime-change detection.
    - Detect shifts in throughput behavior (team changes, major process changes, roadmap phase shifts).
    - Use rolling windows and change-point tests to split historical data into coherent eras.
    - Forecast from recent regime only or weighted regimes.

3. Hierarchical uncertainty modeling.
    - Separate uncertainty into team-level, item-level, and systemic volatility.
    - This enables more realistic sensitivity and better “what if team changes by X” analysis.
    
4. Dependency-risk propagation.
    - Model delay contagion through dependency networks.
    - Add network-level fragility metrics (single-point-of-failure tasks, bottleneck centrality).

5. Advanced scenario engine.
    - Policy simulations such as WIP limits, staffing changes, batch size changes, planned interruption policies.
    - Return comparative distributions rather than single-run outputs.

6. Portfolio-level planning.
    - Multiple concurrent projects sharing teams/capacity with contention.
    - This unlocks strategic planning, not just per-project estimation.

7. MCP Server: Obvious Next Features

    - Structured explain endpoint. Return “why this forecast” with top drivers, assumptions, and confidence caveats.
    - Scenario compare endpoint. Accept baseline plus N variants, return ranked deltas for P50/P80/P90 and risk flags.
    - Batch validation/simulation endpoint. Validate or simulate many project specs in one request, useful for CI or portfolio jobs.
    - Contract hardening. Stable schemas, versioned response formats, explicit deprecation policy.
    - Provenance metadata. Include model version, config hash, input digest, random seed, and diagnostics for reproducibility.

8. NL Parser: Obvious Next Features

    - Clarification-first parsing mode. If ambiguous fields exist, return targeted clarification questions instead of silent assumptions.
    - Round-trip confidence and uncertainty tags. For each parsed field: confidence level, inferred-from text span, and ambiguity reason.
    - Incremental editing support. “Apply patch” semantics to existing project specs from new natural language deltas.
    - Better dependency and date extraction. Detect relative sequencing language, sprint references, and implicit milestone constraints.
    - Domain lexicon + synonym packs. Team-specific vocabulary mapping (story synonyms, role names, effort idioms).
    - Strict/lenient parse profiles. Strict for production pipelines, lenient for ideation, both with transparent diagnostics.


## Not yet fully implemented in current specification


### 1. Environment-based configuration selection (FR-012)

Current state:

- a single config file can be loaded
- defaults can be merged with user overrides

What is missing:

- no built-in `dev` / `prod` / `team` environment profile selection
- no environment-aware config resolution


### 2. Pluggable distribution and risk model architecture (NFR-008)

The requirements specify that distribution types and risk models should be pluggable/extensible.

Current state:

- distributions use a hardcoded `if/elif` dispatch on `DistributionType` enum
- only `TRIANGULAR` and `LOGNORMAL` are supported
- risk models are not extensible beyond the built-in `PERCENTAGE` / `ABSOLUTE` impact types
- no plugin or factory pattern for adding new distribution or risk model types


## Partially implemented

### 1. Output configuration is modeled, but not fully honored

Current state:

- config supports `output.formats`, `include_histogram`, and `number_bins`
- CLI can print those settings

What is missing:

- CLI export behavior is driven by `--output-format`, not `config.output.formats`
- exporters always generate histograms instead of honoring `config.output.include_histogram`
- all three exporters hardcode 50 bins instead of using `config.output.number_bins`


### 2. Logging is only partially configurable (NFR-010)

Current state:

- logs include timestamps, logger name, and level
- the logging helper accepts a log-level argument
- `-v` / `--verbose` sets INFO level

What is missing:

- no `--log-level` CLI option for arbitrary level selection (DEBUG, INFO, WARNING, ERROR)
- no config-file-driven log level
- no environment-driven logging configuration in the main workflow


### 3. Documentation gaps

Current state:

- All major functionality and grammar are documented
- Detailed step-by-step guide to write project files are done
- README and QUICKSTART guides done

What is missing:

- Complete user guide section on how configuration affects simulation
- More in-depth description of risks and uncertainty factors and how to determine those

# Roadmap

## Conservative release plan post-1.0.0

### v1.1.x - Forecast trust and calibration baseline (non-breaking)

Goals:

- Add backtesting workflows that replay historical projects/sprints.
- Add reliability metrics (P50/P80/P90 coverage, bias, spread diagnostics).
- Add reproducibility metadata in outputs and MCP responses (seed/config/model version).

Release gates:

- deterministic backtesting in CI
- calibration report available in JSON/HTML/CLI
- no schema or contract breaks

### v1.2.x - Workflow and automation expansion (non-breaking)

Goals:

- Scenario compare mode (baseline plus N alternatives with delta summaries).
- Clarification-first NL parsing for ambiguous input.
- MCP batch validate/simulate endpoints for CI and portfolio pipelines.
- Parser confidence tags and better diagnostics.

Release gates:

- scenario regression corpus stable
- reduced parse-rework in acceptance tests
- stable batch MCP endpoints

### v2.0.0 - Contracted schemas and explainability overhaul (breaking)

Goals:

- Versioned JSON/MCP schemas with explicit compatibility policy.
- Standardized output field naming and payload shape.
- Structured explain payloads (drivers, assumptions, caveats).
- Remove/deprecate ambiguous legacy aliases.

Release gates:

- migration checker command published
- migration guide with before/after examples
- contract test suite passing for CLI/exporters/MCP

### v2.1.x-v2.2.x - Regime-aware forecasting and robust resampling (non-breaking)

Goals:

- Detect throughput regime shifts/change points.
- Add regime-weighted forecast modes (recent-only, blended, auto).
- Add robust temporal resampling (moving/block bootstrap, disruption-conditioned sampling).
- Add explicit forecast reliability score in reports.

Release gates:

- better calibration than v2.0 on regime-shift benchmarks
- no regression on stable-history benchmarks

### v3.0.0 - Bayesian model family and optional MCMC backend (breaking)

Goals:

- Introduce Bayesian model family configuration.
- Represent parameter uncertainty explicitly in forecast diagnostics.
- Add optional MCMC backend for advanced inference use cases.
- Keep a fast non-MCMC mode for runtime-sensitive workflows.

Release gates:

- posterior predictive checks and calibration thresholds pass
- runtime/performance envelope documented
- v2-to-v3 config migration tooling available

### v3.1.x+ - Portfolio and policy simulation expansion

Goals:

- Shared-capacity multi-project simulation.
- Policy simulation (WIP caps, staffing policies, interruption controls).
- MCP scenario orchestration for portfolio-level analysis.

Notes:

- Use a later major only if the core project data model changes materially.

## Why majors are warranted in this plan

- v2.0.0: output/API contract and schema normalization affects integrations.
- v3.0.0: core statistical semantics and configuration model changes.


## MCMC positioning

- MCMC is valid once sufficient historical depth and calibration evidence justify it.
- Keep it out of immediate post-1.0 releases until v1.x/v2.x trust metrics prove need.



# Completed

### Two-pass critical-path-aware simulation mode (FR-034, FR-042)

The requirements specify a configurable two-pass scheduling mode where:
- Pass 1 computes baseline criticality indices under resource/calendar constraints
- Pass 2 prioritizes assignments for tasks ranked by pass-1 criticality
- The system reports pass-1 versus pass-2 outcome deltas for traceability


### Sickness duration configuration in config.yaml (FR-040)

- Sickness duration distribution parameters can be set in config file for the scheduler. 
- sickness configuration section in `config.yaml` schema
- override sickness-duration mode or dispersion per project or config file
- per-member `sickness_prob` is configurable 


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
