# Project TODO for MVP

The goal is to implement all MVP requirements in `docs/mcprojsim_reqs.md` to be able to reach 1.0.0

## Not implemented yet

### 1. Dedicated typed resource/calendar models from the architecture section

The requirements architecture describes dedicated resource/calendar models, but the implementation currently stores top-level resources and calendars as raw dictionaries.

What is missing:

- no `models/resource.py`
- no typed `Resource` / `Calendar` models
- no validation beyond raw dictionary acceptance

### 2. Environment-based configuration selection (FR-012)

Current state:

- a single config file can be loaded
- defaults can be merged with user overrides

What is missing:

- no built-in `dev` / `prod` / `team` environment profile selection
- no environment-aware config resolution



## Partially implemented

### 1. Resource modeling is parse-only (FR-009)

Resources and calendars are accepted by the models, but they are not consumed anywhere in the simulation engine or scheduler. This is better than having no structure at all, but it is still far short of the requirement.


### 2. Output configuration is modeled, but not fully honored

Current state:

- config supports `output.formats`, `include_histogram`, and `histogram_bins`
- CLI can print those settings

What is missing:

- CLI export behavior is driven by `--output-format`, not `config.output.formats`
- exporters hardcode histogram generation instead of honoring `include_histogram`
- exporters hardcode 50 bins instead of using `config.output.histogram_bins`

### 3. Logging is only partially configurable (NFR-010)

Current state:

- logs include timestamps, logger name, and level
- the logging helper accepts a log-level argument

What is missing:

- no CLI option for log level
- no config-file-driven log level
- no environment-driven logging configuration in the main workflow


# Completed

### Most frequent critical path reporting as an actual path (FR-008)

Current state:

- each iteration now records the full critical path sequences, not only the set of critical tasks
- results aggregate the most frequent full critical paths across runs
- the number of stored paths is configurable in `config.yaml`
- CLI and exporters now report canonical full critical path sequences

### Validation errors with line numbers (FR-001)

Current state:

- parsing and model validation are implemented
- errors are returned as exception messages

What is missing:

- no YAML/TOML line-number reporting
- no field-location-to-source-location mapping
- no parser-side error localization for end users

### Percentile coverage is incomplete by default (FR-010)

Current state:

- the engine computes percentiles listed in `project.confidence_levels`
- the percentile API can compute any percentile on demand
- default confidence levels are `[25, 50, 75, 80, 85, 90, 95, 99]`

What is missing:

- requirements call out `P10, P25, P50, P75, P80, P90, P95, P99`
- `P10`, `P25`, and `P99` are not produced by default
- exports only contain percentiles that were actually computed for the run

### Complete all section of the user guide & documentation

Current state:

- All major functionalty and grammar are documented
- Detailed step-by-step guide to write project files are done
- README and QUICKSTART guides done (but could use some shortening)

What is missing:

- Complete user guide with detailed description and explanations of how the configuration affects simulation
- More in depth description of risks and uncertainty factors and how to determine those

### Sensitivity analysis exists as helpers, but is not integrated end-to-end (FR-011)

Current state:

- `analysis/sensitivity.py` computes Spearman rank correlations
- it can also return top contributors to schedule variance
- task duration samples are stored in `SimulationResults`

What is missing:

- simulation runs do not automatically compute/store sensitivity outputs
- CLI does not display sensitivity analysis
- JSON / CSV / HTML exports do not report sensitivity metrics
- there is no built-in “top N contributors” report in the main workflow


### Progress reporting only satisfies part of the requirement (FR-013)

Current state:

- progress can be shown during simulation
- quiet mode is supported
- progress prints every 1000 iterations

What is missing:

- requirement says every 5% of iterations **or** every 1000 iterations
- implementation only checks the 1000-iteration rule
- for smaller runs, progress can be sparser than required

### Validation/schema handling is only partially aligned with the requirement (FR-001, FR-015)

Current state:

- validation is strong at the model level via Pydantic
- numeric ranges, dates, dependency references, and circular dependencies are checked

What is missing:

- no explicit user-facing schema artifact
- no normalized structured validation report
- no line-number-aware validation output


## Resource-aware scheduling and calendar enforcement (FR-009)

Current state:

- `Task.resources` exists
- top-level `Project.resources` and `Project.calendars` exist
- the scheduler ignores all of them

What is missing:

- no prevention of resource over-allocation
- no use of resource availability
- no work-hours-per-day handling
- no holiday or non-working-period handling
- no resource-constrained scheduling / leveling
