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

### 3.2 Non-Functional Requirements

**NFR-001: Performance**
- The system SHALL complete 10,000 iterations for a 50-task project in under 60 seconds on standard hardware
- Memory usage SHALL NOT exceed 500MB for projects with up to 500 tasks

**NFR-002: Code Quality**
- Code SHALL be formatted with Black (line length 88)
- Type hints SHALL be provided for all functions and methods
- Type checking SHALL pass with mypy in strict mode
- Linting SHALL pass with flake8 with minimal warnings

**NFR-003: Test Coverage**
- Unit test coverage SHALL exceed 85%
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
      value: 20  # 20% delay or 20 days if absolute
    description: "Risk of losing senior developer mid-project"
  
  - id: "risk_002"
    name: "Requirements change"
    probability: 0.30
    impact:
      type: "absolute"
      value: 10
      unit: "days"
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
      unit: "days"  # or "hours"
    
    dependencies: []  # No predecessors
    
    uncertainty_factors:
      team_experience: "high"  # high, medium, low
      requirements_maturity: "medium"
      technical_complexity: "low"
      team_distribution: "colocated"  # colocated, distributed
      integration_complexity: "low"
    
    resources: ["backend_dev_1", "dba_1"]  # Optional
    
    risks:
      - id: "task_risk_001"
        name: "Schema migration issues"
        probability: 0.20
        impact: 2  # days
    
  - id: "task_002"
    name: "API endpoint implementation"
    estimate:
      min: 5
      most_likely: 8
      max: 15
      unit: "days"
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
* After that, scheduler.py computes an earliest-start schedule using only dependency constraints: 
  * tasks with no dependencies start at time 0,
  * a task starts at the maximum end time of its predecessors,
  * independent tasks therefore do run in parallel today.
* Project duration is then computed as the maximum end time in the schedule, not as the sum of all task durations. That directly contradicts the idea that the engine just adds all task efforts together.
* Only after the scheduled project duration is known does the engine apply project-level risks. This means project-wide risk penalties affect final duration, but they do not affect critical-path membership for that iteration.
* The scheduler then identifies the critical path for that iteration by:
  * finding every task that ends exactly at project completion,
  * recursively walking backward through predecessors whose end time exactly matches the successor’s start time,
  * collecting all such tasks into a set.

### 6.4 Critical Path Identification

For each iteration, identify the longest path through the task network. Track frequency of each task appearing on critical path.

* This is a dependency-only critical path, not a resource-constrained critical chain.
* A task is counted as critical in an iteration if it lies on at least one longest dependency path in that specific sampled schedule.
* Across all iterations, the engine increments a counter per task in the results field critical_path_frequency in simulation.py.
* The method get_critical_path then converts those counts into a criticality index by dividing by the number of iterations.
* So the exported number is really: “how often was this task on a critical path across the Monte Carlo runs?”

### 6.5 Limitations

* No resource constraints are used in scheduling today. The scheduler ignores task resources, project resources, and calendars.
* That means the current critical path is purely precedence-based.
* Top-level resources and calendars are parsed into the project model, but they are **NOT** used in scheduling (yet)
* Task-level resources are also present in the model, but not consumed by the scheduler.
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
print(f"P50 (Median): {results.percentile(50)} days")
print(f"P90: {results.percentile(90)} days")
print(f"Mean: {results.mean} days")
print(f"Std Dev: {results.std_dev} days")

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
