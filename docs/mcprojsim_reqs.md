# Monte Carlo Software Development Estimation System
## Formal Specification v1.0

---

## 1. Executive Summary

This document specifies a Monte Carlo simulation system for software development effort estimation. The system models uncertainties in task duration, applies risk impacts, handles task dependencies, and generates probabilistic project completion forecasts through iterative simulation.

---

## 2. System Overview

### 2.1 Purpose
Provide probabilistic estimates for software project completion through Monte Carlo simulation, accounting for task uncertainty, risk events, complexity factors, and resource constraints.

### 2.2 Key Features
- Triangular distribution sampling for task estimates
- Project-level and task-level risk modeling
- Task dependency resolution (precedence constraints)
- Uncertainty factor application (team experience, requirements maturity, etc.)
- Resource allocation and availability modeling
- Percentile-based confidence intervals (P50, P80, P90, P95)
- Sensitivity analysis and critical path identification
- Export results to multiple formats (JSON, CSV, HTML reports)

---

## 3. Detailed Requirements

### 3.1 Functional Requirements

**FR-001: Input File Parsing**
- The system SHALL parse project definition files in YAML or TOML format
- The system SHALL validate input files against a defined schema
- The system SHALL report specific validation errors with line numbers

**FR-002: Triangular Distribution Sampling**
- Each task estimate SHALL be defined with either a triangular distribution specified with (minimum, most_likely, maximum) values or a log-normal distribution specified with (most_likely, standard_deviation)
- The system SHALL sample from triangular distributions using numpy.random.triangular or a log-normal distributions using numpy.random.lognormal
- The system SHALL validate that min ≤ most_likely ≤ max for a triangular distribution

**FR-003: Monte Carlo Simulation Execution**
- The system SHALL perform N iterations (configurable, default 10,000)
- Each iteration SHALL sample all task durations independently
- The system SHALL respect task dependencies in each iteration
- The system SHALL apply risk events probabilistically in each iteration

**FR-004: Task-Level Risk Modeling**
- Tasks MAY specify zero or more risk events
- Each risk SHALL have a probability (0.0 to 1.0) and impact (time penalty)
- Risks SHALL be evaluated independently in each simulation iteration
- Multiple risks on a single task SHALL have cumulative impacts when triggered

**FR-005: Project-Level Risk Modeling**
- Projects MAY specify zero or more project-wide risks
- Project risks SHALL apply time penalties to the overall project duration
- Project risks SHALL be evaluated once per iteration
- Project risk impacts MAY be specified as percentage or absolute time values
- Absolute risk impacts expressed as plain numbers SHALL be treated as hours
- Structured absolute risk impacts MAY specify a unit (hours, days, weeks) which SHALL be converted to hours

**FR-006: Uncertainty Factor Application**
- The system SHALL support configurable uncertainty factors via configuration file
- Each factor SHALL have a multiplier (e.g., 1.0 = no impact, 1.3 = 30% increase)
- Task estimates SHALL be adjusted by multiplying all uncertainty factors
- Supported factors SHALL include: team_experience, requirements_maturity, team_distribution, technical_complexity, integration_complexity

**FR-007: Task Dependency Management**
- Tasks MAY specify dependencies on other tasks by task ID
- The system SHALL validate that all dependency references exist
- The system SHALL detect circular dependencies and reject invalid configurations
- The system SHALL compute task start times respecting all dependencies

**FR-008: Critical Path Analysis**
- The system SHALL identify the critical path in each iteration
- The system SHALL report the most frequent critical path across iterations
- The system SHALL report criticality index (% of iterations on critical path) per task

**FR-009: Resource Modeling**
- Tasks MAY specify required resources by name
- Resources MAY have availability constraints (work hours per day, holidays)
- The system SHALL prevent resource over-allocation in each iteration
- The system SHALL support resource calendars with non-working periods

**FR-010: Simulation Results Statistics**
- The system SHALL calculate mean, median, standard deviation of project duration
- The system SHALL report percentile values: P10, P25, P50, P75, P80, P90, P95, P99
- The system SHALL generate histogram data for visualization
- The system SHALL calculate coefficient of variation

**FR-011: Sensitivity Analysis**
- The system SHALL compute Spearman rank correlation between task durations and project completion
- The system SHALL identify top N contributors to schedule variance
- The system SHALL report task-level sensitivity metrics

**FR-012: Configuration Management**
- The system SHALL load uncertainty factors from a separate configuration file
- The system SHALL support environment-based configurations (dev, prod)
- Configuration SHALL be validated against schema

**FR-013: Progress Tracking**
- The system SHALL display progress during long-running simulations
- Progress updates SHALL occur every 5% of iterations or every 1000 iterations
- The system SHALL support quiet mode for batch processing

**FR-014: Result Export**
- The system SHALL export results to JSON format with full statistics
- The system SHALL export summary results to CSV format
- The system SHALL generate HTML reports with embedded visualizations
- The system SHALL save histogram data for external plotting

**FR-015: Validation and Error Handling**
- The system SHALL validate all input files before simulation
- The system SHALL report clear error messages for invalid inputs
- The system SHALL gracefully handle missing optional fields
- The system SHALL validate date formats and numeric ranges

**FR-016: Support for StoryPoints and T-Shirt Size Estimates**
- The system shall support estimates specified as Story Points (1,2,3,5,8,11,21) which are converted to effort in configuration
- The system shall support T-shirt sizes (S,M,L,XL) which are converted to effort in configuration

**FR-017: Delivery Date Forecasting and Target-Date Probability**
- The system SHALL convert simulated effort values into working-day counts using the project's configured hours per day
- The system SHALL calculate forecast delivery dates for reported confidence levels when a project start date is available
- The system SHALL compute the probability of completing on or before a user-specified target date

**FR-018: Schedule Slack Analysis**
- The system SHALL calculate total float (schedule slack) for each task from the dependency-based schedule
- The system SHALL report mean task slack across simulation iterations
- Tasks with effectively zero slack SHALL be identified as critical in schedule slack reporting

**FR-019: Full Critical Path Sequence Reporting**
- The system SHALL capture complete critical path sequences for each simulation iteration
- The system SHALL aggregate and rank the most frequent full critical path sequences across iterations
- The system SHALL include a configurable number of the top critical path sequences in command-line output and exported reports

**FR-020: Risk Impact Summary Reporting**
- The system SHALL track realized task-level risk impact during simulation iterations
- The system SHALL report mean realized risk impact per task
- The system SHALL report task-level risk trigger rate and mean impact when triggered

**FR-021: Natural-Language Project Description Parsing**
- The system SHALL parse semi-structured natural-language project descriptions into an internal project representation
- The parser SHALL extract project metadata including project name, start date, description, hours per day, and confidence levels when provided
- The parser SHALL extract numbered tasks, task dependencies, T-shirt sizes, Story Points, and explicit three-point estimates with optional effort units

**FR-022: Project File Generation from Natural-Language Descriptions**
- The system SHALL generate syntactically correct mcprojsim YAML project files from supported natural-language descriptions
- Generated task identifiers SHALL be normalized into valid project task IDs and dependency references SHALL be mapped accordingly
- The system SHALL support validation-only analysis of natural-language project descriptions, reporting warnings and errors without generating a project file

**FR-023: MCP Server Integration**
- The system SHALL provide an MCP server interface for generating project files from natural-language descriptions
- The system SHALL provide MCP tools to validate natural-language project descriptions before generation
- The system SHALL provide an MCP tool that generates a project definition and executes a simulation in a single request

**FR-024: Extended Distribution Shape Statistics**
- The system SHALL calculate skewness for the simulated project duration distribution
- The system SHALL calculate excess kurtosis for the simulated project duration distribution
- The system SHALL include these distribution-shape metrics in result reporting and exports

**FR-025: Staffing Analysis and Team-Size Recommendations**
- The system SHALL compute total effort as the sum of mean task durations across simulation iterations
- The system SHALL model communication overhead using a linear per-person penalty clamped to a configurable minimum individual productivity floor
- The system SHALL compute effective team capacity as the product of team size, individual productivity, and a per-profile productivity factor
- The system SHALL compute calendar duration as the maximum of the critical-path duration and total effort divided by effective capacity
- The system SHALL determine the recommended team size as the smallest number of people where adding one more reduces calendar time by less than 5%
- The system SHALL provide three configurable experience profiles (senior, mixed, junior), each with an independent productivity factor and communication overhead coefficient
- The system SHALL produce a staffing table showing team size, effective capacity, calendar working days, projected delivery date, and efficiency for each profile up to the maximum parallel task count
- The system SHALL display a short staffing advisory in default CLI output when not in quiet mode
- The system SHALL display the full staffing analysis table when the `--staffing` CLI flag is specified
- The system SHALL include staffing recommendations and table data in JSON and CSV exports
- The system SHALL offer configuration to decide which effort percentile to base staffing suggestion on

### 3.1.1 Resource and Calendar-Constrained Scheduling

**FR-026: Team Size and Member Model**
- The system SHALL allow project-level `team_size` as an integer >= 0.
- If `team_size > 0`, validation SHALL ensure the effective resource pool size equals `team_size` by auto-generating default resources when needed.
- If `team_size` is omitted or `0`, no team-size-driven resources SHALL be generated.
- Team members SHALL be identifiable for assignment, availability, and sickness modeling.

**FR-027: Productivity and Experience Attributes**
- Each team member SHALL have default productivity 1.0 (1 person-hour per clock hour).
- Productivity SHALL be configurable per member in the range 0.1 to 2.0.
- Each team member SHALL have experience level 1, 2, or 3 (Junior, Mid, Expert).
- Invalid productivity/experience values SHALL fail validation.

**FR-028: Working Calendar Defaults and Holidays**
- The default calendar SHALL include Monday–Friday as working days and exclude weekends.
- Projects MAY define public holidays as non-working dates.
- Holidays SHALL be applied to calendar-time simulation and delivery-date forecasting.

**FR-029: Member Time-Off and Vacation**
- The system SHALL support member-specific non-working dates (vacation/days off).
- Member time off SHALL override default working-day availability for those dates.
- Overlapping holidays/weekends/time-off SHALL not double-penalize availability.

**FR-030: Calendar-Aware Percentiles and Dates**
- Calendar-time percentiles SHALL account for all non-working periods (weekends, holidays, member days off).
- Delivery-date forecasts SHALL be computed from constrained schedules, not dependency-only elapsed hours.

**FR-031: Task Resource Constraints and Qualification**
- Tasks SHALL support max concurrent assignees per task; default is 1 when unspecified.
- Tasks SHALL support minimum experience requirement; default is level 1 when unspecified.
- All members SHALL be eligible for all tasks unless constrained by minimum experience.
- The scheduler SHALL never assign more than task max resources concurrently.
- The scheduler SHALL also apply a practical auto-cap per task based on effort granularity and coordination limits.

**FR-032: Sickness Event Modeling**
- Each member SHALL have a daily sickness-start probability in [0.0, 1.0].
- Sickness start SHALL be modeled as independent Bernoulli trials per working day.
- Sickness duration SHALL follow a log-normal distribution configured in config, with default mode 2 working days.
- During sickness periods, member availability SHALL be zero.

**FR-033: Resource Assignment Strategy**
- The system SHALL use deterministic greedy assignment when resource contention exists.
- The strategy SHALL be deterministic for a fixed seed and equal-priority ties.
- Tie-breaking rules SHALL be defined (ready tasks in sorted order, eligible resources in sorted order).
- The scheduler SHALL start ready tasks with currently available eligible resources and SHALL NOT delay start to wait for additional resources.

**FR-034: Two-Pass Critical-Path-Aware Simulation Mode**
- A two-pass critical-path-aware assignment mode MAY be added in a future release.
- The current baseline does not expose two-pass mode as a CLI or config toggle.

**FR-035: Resource/Calendar Reporting and Export**
- The system SHALL report resource-constrained metrics: wait time due to resource contention, utilization, and calendar delay contribution.
- JSON/CSV/HTML exports SHALL include these metrics when resource mode is active.
- CLI output SHALL distinguish dependency-only vs resource-constrained schedule semantics.

**FR-036: Backward Compatibility and Fallback Behavior**
- Existing project files without resource/calendar/team fields SHALL remain valid.
- In absence of explicit resource settings, behavior SHALL default to prior-compatible assumptions (task max resources=1, experience min=1, default calendar).
- If neither resources nor team-size-generated resources exist, scheduling SHALL run in dependency-only mode.
- Migration guidance SHALL be documented for adopting explicit team/resource definitions.

**FR-037: Resource and Calendar Schema Validation**
- Team size SHALL be validated as an integer >= 0.
- Team-member productivity SHALL be validated in the closed range [0.1, 2.0].
- Team-member experience level SHALL be validated as one of {1, 2, 3}.
- Task-level `max_resources` SHALL be validated as an integer >= 1.
- Task-level `min_experience_level` SHALL be validated as one of {1, 2, 3}.
- Calendar identifiers, resource identifiers, and task identifiers SHALL be unique within their namespaces.
- References from tasks to resources/calendars SHALL be validated; unknown references SHALL fail validation.
- If explicit resources exceed `team_size` (when `team_size > 0`), validation SHALL fail.
- Holiday, vacation, and day-off dates SHALL be validated as ISO 8601 dates.
- Invalid sickness parameters (probability outside [0,1], invalid distribution parameters, or invalid start-day metadata) SHALL fail validation.

**FR-038: Scheduling Semantics Under Resource Constraints**
- Resource-constrained scheduling SHALL preserve dependency constraints as hard constraints.
- A task SHALL start only when dependencies are met and required resources satisfying minimum experience are available.
- Tasks SHALL be non-preemptive by default once started; optional preemption behavior MAY be added later behind configuration.
- When multiple eligible tasks compete for the same resource pool, the assignment policy SHALL apply deterministic tie-breaking.
- Reported calendar duration SHALL be the completion time of the resource-constrained schedule, not a dependency-only earliest-start schedule.

**FR-039: Calendar Computation Rules**
- Weekends, configured public holidays, individual vacations/days off, and sickness periods SHALL all be treated as non-working time for affected members.
- Resource availability SHALL be computed at working-calendar granularity (working day and working hours per day).
- Conversion between effort and elapsed calendar time SHALL use project `hours_per_day` and the active calendar/resource constraints.
- Delivery-date forecasting SHALL use the resource- and calendar-constrained timeline.

**FR-040: Sickness Configuration and Defaults**
- The sickness model SHALL support per-member default probability and optional day-specific overrides.
- When day-specific overrides are present, they SHALL take precedence over the default daily probability for matching dates.
- The default sickness-duration distribution SHALL be log-normal with mode = 2 working days.
- Configuration SHALL expose parameters needed to reproduce the duration distribution (at minimum mode and dispersion).

**FR-041: Reporting and Export Contract for Resource-Constrained Runs**
- CLI, JSON, CSV, and HTML outputs SHALL explicitly indicate whether resource/calendar constraints were active.
- Outputs SHALL include resource-related diagnostics at minimum: average queue/wait time due to resource contention, effective utilization, and delay attributable to non-working periods.
- Critical-path reporting SHALL document whether reported criticality reflects dependency-only paths or resource-constrained critical chains.
- Comparative fields MAY include dependency-only baseline versus constrained schedule deltas when available.

**FR-042: Two-Pass Mode Configuration and Acceptance Criteria**
- Two-pass mode SHALL be configurable with default disabled.
- Pass 1 SHALL compute baseline criticality indices under configured resource/calendar constraints.
- Pass 2 SHALL prioritize assignments for tasks ranked by pass-1 criticality, then allocate remaining capacity to other ready tasks.
- The system SHALL expose deterministic acceptance tests demonstrating that two-pass mode does not violate dependency or resource constraints.
- The system SHALL report pass-1 versus pass-2 outcome deltas for traceability.

**FR-043: Unique Resource Naming and Defaulting Rules**
- Reources SHALL be specified as a vector in the project specification
- Each resource specified individually SHALL have a unique `name` within the project.
- If `experience_level` is omitted for a resource, the system SHALL default it to level 2.
- If `productivity_level` is omitted for a resource, the system SHALL default it to 1.0.
- If a resource entry omits `name`, the system SHALL assign a generated name using the format `resource_nnn`.
- Generated names SHALL use ordered, zero-padded three-digit suffixes (`resource_001`, `resource_002`, `resource_003`, ...).
- Auto-generated names SHALL also be validated for uniqueness against explicitly provided names.

**FR-044: Resource Specification Schema**
- Each resource object SHALL support the fields `name`, `experience_level`, `productivity_level`, and `sickness_prob`.
- Each resource object SHALL support `planned_absence` as a list of dates.
- `planned_absence` dates SHALL be interpreted as non-working days for that resource.
- `planned_absence` entries SHALL be validated as ISO 8601 dates.
- Resource fields omitted by the user SHALL use defaults defined by FR-043 and FR-040.

### 3.1.2 Implementation Plan for Resource and Calendar-Constrained Scheduling

**Phase A: DONE! Data Model and Schema Foundation**
- Add/normalize schema for team size, team members, productivity, experience, calendars, holidays, vacations/days off, sickness configuration, and task resource limits.
- Implement validation rules from FR-037 and FR-040 across parser and model layers.
- Preserve backward compatibility defaults per FR-036.

**Phase B: DONE! Updated project file specification**
- Add parsing of resource specification in the projects specification from FR-043, FR-044
- The documentation SHALL be described in user guide `project_files.md`
- The grammar SHALL be formalized in `docs/grammar.md` with EBNF grammar for the resource and calendar specification

**Phase C: Resource/Calendar Scheduling Core**
- Extend scheduler to enforce resource availability and minimum experience constraints while respecting dependencies.
- Apply non-working calendar windows and member unavailability (holiday/vacation/sickness) during scheduling.
- Ensure deterministic tie-breaking and reproducibility with fixed random seeds.

**Phase D: Sickness and Availability Simulation**
- Implement per-member sickness start process and log-normal duration sampling.
- Integrate sickness episodes into member availability timelines used by the scheduler.
- Add targeted unit tests for probability bounds, distribution parameters, and edge cases.

**Phase E: Two-Pass Critical-Path Prioritization**
- Implement configurable two-pass mode (default off).
- Pass 1 computes constrained criticality; Pass 2 applies critical-path-prioritized assignment.
- Add regression and determinism tests for pass-delta behavior.

**Phase F: Metrics, Exports, and UX**
- Add resource/calendar diagnostics required by FR-041 to CLI and all exporters.
- Annotate reports with schedule mode (dependency-only vs constrained).
- Keep existing fields stable unless explicitly versioned.

**Phase G: Documentation and Rollout**
- Update user/project file docs with canonical schema and migration examples.
- Update algorithm and limitations sections to remove dependency-only caveats once implementation is complete.
- Add end-to-end fixtures and performance checks for constrained schedules.

### 3.1.3 Implementation Decisions and Selections (Current Baseline)

- Resource-constrained scheduling is implemented as an explicit scheduler mode (`use_resource_constraints`) to preserve backward compatibility for existing dependency-only workflows.
- Two scheduling modes are supported:
  - dependency-only (`dependency_only`) when no resources are available after validation,
  - resource-constrained (`resource_constrained`) when resources are available.
- Task execution in resource-constrained mode is non-preemptive in the current baseline.
- Resource assignment is deterministic and stable (sorted task IDs and resource names) to preserve reproducibility with fixed random seeds.
- Missing resource names are auto-generated in ordered format `resource_001`, `resource_002`, ... and validated for uniqueness.
- Legacy top-level resource field `id` is accepted as a backward-compatible fallback for `name`.
- Task-level resource references are validated against resolved resource names; unknown references fail fast during project validation.
- Calendar validation is introduced at schema level (ID uniqueness, work-day range 1..7, ISO-8601 date parsing for holidays/absences), while full calendar-aware scheduling behavior is implemented incrementally in later phases.
- Engine scheduling enables resource-constrained mode when validated resources are present; this includes resources explicitly defined in the project file and resources auto-generated from `team_size > 0`.
- `team_size` semantics in baseline:
  - `team_size` omitted or `0`: keep explicit resources only,
  - explicit resources > `team_size` (when `team_size > 0`): validation error,
  - explicit resources < `team_size`: auto-fill with default resources up to `team_size`.
- In constrained mode, elapsed task duration is integrated over calendar windows and time-varying capacity rather than computed as a simple static ratio.
- Sickness episodes are generated per resource per iteration using an independent daily start probability and a log-normal duration model (default mode 2 days, baseline sigma 0.5).
- Planned absences and sickness days are treated as non-working days for affected resources in constrained scheduling.
- Working-time boundaries are currently modeled from day start with `work_hours_per_day` length; explicit shift start times are deferred to a later phase.
- Practical assignment cap is applied in constrained mode:
  - `granularity_cap = max(1, floor(task_effort_hours / MIN_EFFORT_PER_ASSIGNEE_HOURS))`,
  - `coordination_cap = MAX_ASSIGNEES_PER_TASK`,
  - effective per-task auto-cap `= min(granularity_cap, coordination_cap)`.
- Current baseline constants are `MIN_EFFORT_PER_ASSIGNEE_HOURS = 16.0` and `MAX_ASSIGNEES_PER_TASK = 3`.
- Current assignment is greedy start-now: when at least one eligible resource is available, the task starts; scheduler does not wait for additional resources.
- Two-pass criticality-prioritized assignment is not currently enabled in baseline CLI/config.

 

### 3.2 Non-Functional Requirements

**NFR-001: Performance**
- The system SHALL complete 50,000 iterations for a 100-task project in under 90 seconds on AMD64 architecture with 16GB of memory
- Memory usage SHALL NOT exceed 800MB for projects with up to 100 tasks

**NFR-002: Code Quality**
- Code SHALL be formatted with Black (line length 88)
- Type hints SHALL be provided for all functions and methods
- Type checking SHALL pass with mypy in strict mode
- Linting SHALL pass with flake8 with minimal warnings

**NFR-003: Test Coverage**
- Unit test coverage SHALL exceed 80%
- All core simulation logic SHALL have unit tests
- Integration tests SHALL validate end-to-end workflows
- Tests SHALL use pytest framework

**NFR-004: Documentation**
- API documentation SHALL be generated with MkDocs
- All public functions SHALL have docstrings in Google style
- User guide SHALL include quickstart and examples
- Configuration file format SHALL be fully documented

**NFR-005: Maintainability**
- Code SHALL follow SOLID principles
- Modules SHALL have clear separation of concerns
- Maximum cyclomatic complexity per function SHALL be 10
- Public API SHALL use semantic versioning

**NFR-006: Portability**
- The system SHALL run on Python 3.9+
- Dependencies SHALL be minimal and well-maintained
- The system SHALL work on Windows, macOS, and Linux

**NFR-007: Reproducibility**
- Simulations SHALL support random seed specification
- Results SHALL be reproducible given the same seed and input
- Seed SHALL be reported in output for audit trails

**NFR-008: Extensibility**
- Distribution types SHALL be pluggable (triangular, PERT, normal)
- Risk models SHALL be extensible
- Output formats SHALL be pluggable

**NFR-009: Usability**
- CLI SHALL provide helpful error messages
- CLI SHALL support --help for all commands
- Examples SHALL be provided in the repository

**NFR-010: Logging**
- The system SHALL log warnings and errors
- Log level SHALL be configurable
- Logs SHALL include timestamps and context

---

## 4. Input File Format Specification

### 4.1 Project Definition File (YAML/TOML)

The primary input is a project definition file containing:

#### 4.1.1 Project Metadata
```yaml
project:
  name: "Project Apollo"
  description: "Next-generation customer portal"
  start_date: "2025-11-01"
  hours_per_day: 8.0  # Optional, default 8.0; used for unit conversion and working-day reporting
  currency: "USD"  # Optional
  confidence_levels: [50, 80, 90, 95]  # Optional, percentiles to report
```

#### 4.1.2 Project-Level Risks
```yaml
project_risks:
  - id: "risk_001"
    name: "Key developer leaves"
    probability: 0.15
    impact:
      type: "percentage"  # or "absolute"
      value: 20  # 20% delay or 20 hours if absolute
    description: "Risk of losing senior developer mid-project"
  
  - id: "risk_002"
    name: "Requirements change"
    probability: 0.30
    impact:
      type: "absolute"
      value: 10
      unit: "days"  # Explicit unit; converted to hours internally
```

#### 4.1.3 Task Definitions
```yaml
tasks:
  - id: "task_001"
    name: "Database schema design"
    description: "Design normalized schema for customer data"
    estimate:
      min: 3
      most_likely: 5
      max: 10
      unit: "days"  # "hours" (default), "days", or "weeks"; converted to hours internally
    
    dependencies: []  # No predecessors
    
    uncertainty_factors:
      team_experience: "high"  # high, medium, low
      requirements_maturity: "medium"
      technical_complexity: "low"
      team_distribution: "colocated"  # colocated, distributed
      integration_complexity: "low"
    
    resources: ["backend_dev_1", "dba_1"]  # Optional
    max_resources: 2
    min_experience_level: 1
    
    risks:
      - id: "task_risk_001"
        name: "Schema migration issues"
        probability: 0.20
        impact: 2  # hours (plain numbers are always hours)
    
  - id: "task_002"
    name: "API endpoint implementation"
    estimate:
      min: 5
      most_likely: 8
      max: 15
      unit: "days"  # Converted to hours using hours_per_day
    dependencies: ["task_001"]  # Depends on task_001
    uncertainty_factors:
      team_experience: "medium"
      requirements_maturity: "high"
      technical_complexity: "medium"
    resources: ["backend_dev_1", "backend_dev_2"]
    risks: []
```

#### 4.1.4 Resource Definitions (Optional)
```yaml
resources:
  - id: "backend_dev_1"
    name: "Senior Backend Developer"
    availability: 1.0  # Full-time
    calendar: "standard"  # Reference to calendar
  
  - id: "dba_1"
    name: "Database Administrator"
    availability: 0.5  # Half-time on this project
    calendar: "standard"

calendars:
  - id: "standard"
    work_hours_per_day: 8
    work_days: [1, 2, 3, 4, 5]  # Monday-Friday
    holidays:
      - "2025-12-25"
      - "2026-01-01"
```

### 4.2 Configuration File (config.yaml)

Defines uncertainty factor multipliers:

```yaml
uncertainty_factors:
  team_experience:
    high: 0.90      # Experienced team is 10% faster
    medium: 1.0     # Baseline
    low: 1.30       # Inexperienced team is 30% slower
  
  requirements_maturity:
    high: 1.0
    medium: 1.15
    low: 1.40
  
  technical_complexity:
    low: 1.0
    medium: 1.20
    high: 1.50
  
  team_distribution:
    colocated: 1.0
    distributed: 1.25
  
  integration_complexity:
    low: 1.0
    medium: 1.15
    high: 1.35

simulation:
  default_iterations: 10000
  random_seed: null  # null for random, or integer for reproducibility
  
output:
  formats: ["json", "csv", "html"]
  include_histogram: true
  histogram_bins: 50
```

---

## 5. System Architecture

### 5.1 Module Structure

```
monte_carlo_estimator/

src/
├── __init__.py
├── cli.py                 # Command-line interface
├── config.py              # Configuration management
├── models/
│   ├── __init__.py
│   ├── project.py         # Project, Task, Risk models
│   ├── resource.py        # Resource and Calendar models
│   └── simulation.py      # Simulation result models
├── parsers/
│   ├── __init__.py
│   ├── yaml_parser.py     # YAML input parser
│   └── toml_parser.py     # TOML input parser
├── simulation/
│   ├── __init__.py
│   ├── engine.py          # Monte Carlo simulation engine
│   ├── distributions.py   # Probability distributions
│   ├── scheduler.py       # Task scheduling with dependencies
│   └── risk_evaluator.py  # Risk event evaluation
├── analysis/
│   ├── __init__.py
│   ├── statistics.py      # Statistical analysis
│   ├── sensitivity.py     # Sensitivity analysis
│   └── critical_path.py   # Critical path analysis
├── exporters/
│   ├── __init__.py
│   ├── json_exporter.py
│   ├── csv_exporter.py
│   └── html_exporter.py
└── utils/
    ├── __init__.py
    ├── validation.py      # Input validation
    └── logging.py         # Logging utilities

tests/
├── __init__.py
├── test_models.py
├── test_parsers.py
├── test_simulation.py
├── test_analysis.py
├── test_integration.py
└── fixtures/
    ├── sample_project.yaml
    └── sample_config.yaml

docs/
├── index.md
├── getting_started.md
├── configuration.md
├── api_reference.md
└── examples/

scripts/
├──mkblbd.sh
├──mkrelease.sh
├──mkdocs.sh
└──mkghrelease.sh

examples/
├── sample_project.yaml
└── sample_config.yaml

```

### 5.2 Core Classes

#### Project
- Properties: name, description, start_date, tasks, project_risks
- Methods: validate(), get_task_by_id()

#### Task
- Properties: id, name, estimate (min, most_likely, max), dependencies, uncertainty_factors, risks, resources
- Methods: calculate_adjusted_estimate(), has_dependency()

#### Risk
- Properties: id, name, probability, impact
- Methods: evaluate() → bool, get_impact_value()

#### SimulationEngine
- Methods: run_simulation(n_iterations), run_single_iteration()

#### TaskScheduler
- Methods: schedule_tasks(task_durations, dependencies) → schedule
- Implements topological sort for dependency resolution

#### StatisticalAnalyzer
- Methods: calculate_statistics(), generate_histogram(), compute_percentiles()

---

## 6. Algorithms

### 6.1 Monte Carlo Simulation Loop

```
FOR iteration = 1 TO N:
    durations = {}
    
    FOR each task:
        # Sample base duration
        base = sample_triangular(task.min, task.most_likely, task.max)
        
        # Apply uncertainty factors
        adjusted = base * product(uncertainty_multipliers)
        
        # Apply task-level risks
        FOR each risk in task.risks:
            IF random() < risk.probability:
                adjusted += risk.impact
        
        durations[task.id] = adjusted
    
    # Schedule tasks respecting dependencies
    schedule = schedule_tasks(durations, dependencies)
    project_duration = max(schedule.end_times)
    
    # Apply project-level risks
    FOR each project_risk:
        IF random() < project_risk.probability:
            project_duration += project_risk.impact
    
    results[iteration] = project_duration

RETURN statistics(results)
```

### 6.2 Dependency Resolution (Topological Sort)

Uses Kahn's algorithm for topological sorting to determine task execution order while respecting precedence constraints.

### 6.3 How project duration is calculated

* In engine.py, each iteration first samples every task duration from its estimate distribution.
* The engine then adjusts each sampled duration with uncertainty factors and task-level risks before scheduling.
* The scheduler mode is selected per iteration from validated project resources:
  * `dependency_only` when no resources exist,
  * `resource_constrained` when resources exist (explicitly defined or generated from `team_size > 0`).
* In dependency-only mode, tasks start at earliest dependency-feasible times.
* In resource-constrained mode, start and end times also depend on eligibility (`resources`, `min_experience_level`), assignment caps (`max_resources` and practical auto-cap), calendars, planned absence, and sickness episodes.
* Project duration is computed as the maximum task end time in the resulting schedule, not as the sum of task durations.
* Only after scheduled duration is known does the engine apply project-level risks.

### 6.4 Critical Path Identification

For each iteration, identify the longest path through the task network. Track frequency of each task appearing on critical path.

* Critical-path tracing is currently based on dependency timing relationships in the realized schedule.
* A task is counted as critical in an iteration if it lies on at least one longest dependency path in that specific sampled schedule.
* Across all iterations, the engine increments a counter per task in the results field critical_path_frequency in simulation.py.
* The method get_critical_path then converts those counts into a criticality index by dividing by the number of iterations.
* So the exported number is really: “how often was this task on a critical path across the Monte Carlo runs?”

### 6.5 Limitations

* Two-pass criticality-prioritized assignment mode is not currently enabled as a user-facing toggle.
* Assignment strategy is deterministic greedy rather than globally optimal schedule optimization.
* Critical-path reporting reflects dependency relationships and should not be interpreted as a full resource-critical-chain optimizer.
* Project-level risks are applied after schedule calculation, so they can make the project finish later without changing which tasks were counted as critical.
* If multiple terminal tasks finish at the same project end time, the code traces all of them, so one iteration can contribute multiple branches rather than one single canonical path.

---

## 7. Technology Stack

### 7.1 Core Dependencies
- **Python**: 3.9+
- **NumPy**: 1.24+ (numerical operations, random sampling)
- **Pandas**: 2.0+ (data manipulation, result aggregation)
- **PyYAML**: 6.0+ (YAML parsing)
- **tomli/tomli-w**: 2.0+ (TOML parsing/writing)
- **Pydantic**: 2.0+ (data validation and settings management)
- **Click**: 8.0+ (CLI framework)

### 7.2 Development Dependencies
- **pytest**: 7.0+ (testing framework)
- **pytest-cov**: 4.0+ (coverage reporting)
- **black**: 23.0+ (code formatting)
- **mypy**: 1.0+ (static type checking)
- **flake8**: 6.0+ (linting)
- **pre-commit**: 3.0+ (git hooks for quality checks)

### 7.3 Documentation Dependencies
- **mkdocs**: 1.5+ (documentation site generator)
- **mkdocs-material**: 9.0+ (Material theme)
- **mkdocstrings**: 0.22+ (API documentation from docstrings)

---

## 8. Usage Examples

### 8.1 Command-Line Interface

```bash
# Run simulation with default settings
mc-estimate simulate project.yaml

# Specify number of iterations
mc-estimate simulate project.yaml --iterations 50000

# Use custom config file
mc-estimate simulate project.yaml --config custom_config.yaml

# Specify random seed for reproducibility
mc-estimate simulate project.yaml --seed 12345

# Export to specific formats
mc-estimate simulate project.yaml --output-format json,html

# Validate input file without running simulation
mc-estimate validate project.yaml

# Show configuration
mc-estimate config show
```

### 8.2 Python API

```python
from monte_carlo_estimator import Project, SimulationEngine
from monte_carlo_estimator.parsers import YAMLParser

# Load project
parser = YAMLParser()
project = parser.parse_file("project.yaml")

# Run simulation
engine = SimulationEngine(iterations=10000, random_seed=42)
results = engine.run(project)

# Access results
print(f"P50 (Median): {results.percentile(50):.1f} hours")
print(f"P90: {results.percentile(90):.1f} hours")
print(f"Mean: {results.mean:.1f} hours")
print(f"Std Dev: {results.std_dev:.1f} hours")

# Get critical path
critical_tasks = results.get_critical_path()
for task_id, criticality in critical_tasks.items():
    print(f"{task_id}: {criticality*100:.1f}% critical")
```

---

## 9. Validation Rules

1. All task IDs must be unique
2. All dependency references must exist
3. No circular dependencies
4. Estimate: min ≤ most_likely ≤ max
5. Probabilities must be in range [0, 1]
6. Impacts must be non-negative
7. Start date must be valid ISO 8601 format
8. Resource availability must be in range (0, 1]
9. Uncertainty factor levels must match config definitions
10. At least one task must be defined

---

## 10. Output Formats

### 10.1 JSON Output
Complete simulation results with all statistics, histogram data, and metadata.

### 10.2 CSV Output
Tabular summary with key percentiles and statistics for easy import to Excel.

### 10.3 HTML Report
Interactive report with:
- Project summary
- Statistical summary table
- Histogram visualization
- Critical path analysis
- Sensitivity analysis chart
- Risk impact summary

---

## 11. Future Enhancements (Out of Scope for v1.0)

1. Support for PERT distribution as alternative to triangular
2. Cost modeling in addition to time
3. Resource leveling optimization
4. Multi-project portfolio analysis
5. Integration with Jira/Azure DevOps
6. Real-time progress tracking vs. baseline
7. Machine learning for improved estimate calibration
8. Web-based UI
9. Correlation between task durations (currently assumes independence)
10. Weather/external factor modeling

---

## 12. References

- *Software Estimation: Demystifying the Black Art* by Steve McConnell
- *The Mythical Man-Month* by Frederick Brooks
- *How to Measure Anything in Cybersecurity Risk* by Douglas Hubbard
- NIST Guide for Risk Analysis
- PMI PMBOK Guide (7th Edition)

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-10-23 | Initial | Initial specification |

---

**End of Specification**
