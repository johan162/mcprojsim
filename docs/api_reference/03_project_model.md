## Project Models

### `Project`

Represents the complete project definition with metadata, tasks, risks, resources, and calendars.

**Key fields:**

- `project`: `ProjectMetadata` — project name, start date, hours/day, etc.
- `tasks`: `list[Task]` — work items and their dependencies
- `project_risks`: `list[Risk]` — top-level project-level risks
- `resources`: `list[ResourceSpec]` — named resource pools
- `calendars`: `list[CalendarSpec]` — named calendars for holidays/exclusions
- `sprint_planning`: `SprintPlanningSpec | None` — sprint planning configuration if enabled

**Key methods:**

- `get_task_by_id(task_id: str) -> Task | None` — Retrieve a task by its ID
- `to_dict() -> dict[str, Any]` — Convert to a dictionary representation

**Example:**

```python
from mcprojsim.parsers import YAMLParser

parser = YAMLParser()
project = parser.parse_file("project.yaml")

# Access project metadata
print(f"Project name: {project.project.name}")
print(f"Start date: {project.project.start_date}")
print(f"Total tasks: {len(project.tasks)}")

# Find a specific task
task = project.get_task_by_id("backend_api")
if task:
    print(f"Task: {task.name}, Dependencies: {task.dependencies}")

# Access all risks
for risk in project.project_risks:
    print(f"Risk: {risk.name}, Probability: {risk.probability}")

# Check if sprint planning is configured
if project.sprint_planning and project.sprint_planning.enabled:
    print(f"Sprint length: {project.sprint_planning.sprint_length_weeks} weeks")
```

**Example: Building a Project Programmatically**

```python
from datetime import date
from mcprojsim.models.project import (
    Project, ProjectMetadata, Task, TaskEstimate, Risk,
)

project = Project(
    project=ProjectMetadata(
        name="My API Project",
        start_date=date(2026, 6, 1),
        hours_per_day=8.0,
    ),
    tasks=[
        Task(
            id="design",
            name="API Design",
            estimate=TaskEstimate(low=8, expected=16, high=32),
        ),
        Task(
            id="implement",
            name="Implementation",
            estimate=TaskEstimate(low=40, expected=80, high=160),
            dependencies=["design"],
        ),
        Task(
            id="test",
            name="Testing",
            estimate=TaskEstimate(t_shirt_size="M"),
            dependencies=["implement"],
        ),
    ],
    project_risks=[
        Risk(
            id="scope_creep",
            name="Scope Creep",
            probability=0.3,
            impact=40.0,
        ),
    ],
)
```

### `ProjectMetadata`

Stores top-level project settings and characteristics.

**Key fields:**

- `name`: str — Project name
- `description`: str | None — Optional project description
- `start_date`: date — Project start date
- `currency`: str | None — Currency for cost tracking (default: `"USD"`)
- `confidence_levels`: list[int] — Percentiles to include in reports (default: [10, 25, 50, 75, 80, 85, 90, 95, 99])
- `probability_red_threshold`: float — Probability threshold marking risk level (default: 0.5)
- `probability_green_threshold`: float — Probability threshold marking success (default: 0.9)
- `hours_per_day`: float — Working hours per day (default: 8.0)
- `distribution`: `DistributionType` — Default task duration distribution (default: `"triangular"`)
- `team_size`: int | None — Total team size (used for coordination overhead calculations and auto-generating resources)

**Example:**

```python
project = parser.parse_file("project.yaml")
meta = project.project

print(f"Project: {meta.name}")
print(f"Start: {meta.start_date}")
print(f"Tracked thresholds: {meta.confidence_levels}")
print(f"Hours/day: {meta.hours_per_day}")
if meta.team_size:
    print(f"Team size: {meta.team_size} people")
```

### `Task`

Represents a single work item in the project network.

**Key fields:**

- `id`: str — Unique task identifier
- `name`: str — Human-readable task name
- `description`: str | None — Optional task description
- `estimate`: `TaskEstimate` — Duration estimate
- `dependencies`: list[str] — List of task IDs this task depends on
- `uncertainty_factors`: `UncertaintyFactors | None` — Optional uncertainty adjustments
- `resources`: list[str] — Required resource names
- `max_resources`: int — Maximum number of resources that can be assigned (default: 1)
- `min_experience_level`: int — Minimum experience level required (1, 2, or 3; default: 1)
- `planning_story_points`: int | None — Story points override for sprint planning
- `priority`: int | None — Scheduling priority hint
- `spillover_probability_override`: float | None — Override for sprint spillover probability (0.0–1.0)
- `risks`: list[Risk] — Task-specific risks

**Key methods:**

- `has_dependency(task_id: str) -> bool` — Check if this task depends on another task
- `get_planning_story_points() -> int | None` — Return sprint-planning story points (falls back to `estimate.story_points`)

**Example:**

```python
# Iterate over all tasks
for task in project.tasks:
    print(f"Task: {task.id} - {task.name}")
    print(f"  Description: {task.description or 'N/A'}")
    print(f"  Resources: {task.resources}")
    print(f"  Depends on: {task.dependencies}")
    if task.estimate:
        print(f"  Estimate: {task.estimate.low}-{task.estimate.expected}-{task.estimate.high} hours")
    if task.risks:
        print(f"  Risks: {len(task.risks)} identified")
    print()

# Find tasks with no dependencies
root_tasks = [t for t in project.tasks if not t.dependencies]
print(f"Root tasks (no dependencies): {[t.id for t in root_tasks]}")

# Find the longest task
longest_task = max(project.tasks, key=lambda t: t.estimate.high if t.estimate else 0)
print(f"Longest task: {longest_task.id}, up to {longest_task.estimate.high} hours")
```

### `TaskEstimate`

Supports four estimation styles:

- Triangular estimates via `low`, `expected`, and `high`
- Log-normal estimates via `low`, `expected`, and `high`
- T-shirt-sized estimates via `t_shirt_size`
- Story Point estimates via `story_points`

**Key fields:**

- `distribution`: `DistributionType | None` — Override the default distribution for this task
- `low`: float | None — Minimum hours (optimistic)
- `expected`: float | None — Best estimate in hours
- `high`: float | None — Maximum hours (pessimistic)
- `t_shirt_size`: str | None — Size token (e.g. `"XS"`, `"S"`, `"M"`, `"L"`, `"XL"`, `"XXL"`, or `"category.size"`)
- `story_points`: int | None — Story point value
- `unit`: `EffortUnit | None` — Effort unit (`"hours"`, `"days"`, `"weeks"`). Must not be set when using symbolic estimates (T-shirt or story points) — the unit comes from configuration.

**Example:**

```python
for task in project.tasks:
    est = task.estimate
    
    if est.story_points:
        print(f"Task {task.id}: {est.story_points} story points")
    elif est.t_shirt_size:
        print(f"Task {task.id}: {est.t_shirt_size} T-shirt")
    else:
        print(f"Task {task.id}: {est.low}-{est.expected}-{est.high} hours")
    
    # Show the distribution type (if overridden for this task)
    if est.distribution:
        print(f"  Distribution: {est.distribution.value}")
```

### `Risk` and `RiskImpact`

Represents task-level or project-level risk.

**Risk fields:**

- `id`: str — Unique risk identifier
- `name`: str — Human-readable risk name
- `probability`: float — Probability this risk occurs (0.0 to 1.0)
- `impact`: float | `RiskImpact` — Impact when risk happens (float is treated as hours)
- `description`: str | None — Optional description

**RiskImpact fields:**

- `type`: `ImpactType` — `"percentage"` or `"absolute"`
- `value`: float — Percentage (0–100) or absolute hours
- `unit`: `EffortUnit | None` — Unit only relevant for absolute impacts

**Risk methods:**

- `get_impact_value(base_duration: float = 0.0, hours_per_day: float = 8.0) -> float` — Calculate numeric impact in hours

**Example:**

```python
# Access project-level risks
for risk in project.project_risks:
    impact = risk.get_impact_value()
    print(f"Project risk: {risk.name}")
    print(f"  Probability: {risk.probability * 100:.0f}%")
    print(f"  Impact: {impact:.1f} hours")

# Access task-level risks
for task in project.tasks:
    for risk in task.risks:
        impact = risk.get_impact_value(base_duration=task.estimate.expected)
        print(f"Task {task.id} risk: {risk.name}")
        print(f"  Probability: {risk.probability * 100:.0f}%")
        print(f"  Impact: {impact:.1f} hours")
```

### `ResourceSpec`

Defines an individual resource (team member) that can be assigned to tasks.

**Key fields:**

- `name`: str | None — Resource name (e.g. `"Alice"`, `"Backend Developer"`). Auto-generated if omitted.
- `id`: str | None — Legacy identifier (used as fallback for `name`)
- `availability`: float — Fraction of time available (0.0–1.0, default: 1.0)
- `calendar`: str — Calendar identifier to use (default: `"default"`)
- `experience_level`: int — Skill level: 1 (junior), 2 (mid), or 3 (senior). Default: 2
- `productivity_level`: float — Productivity multiplier (0.1–2.0, default: 1.0)
- `sickness_prob`: float — Probability of absence per scheduling unit (0.0–1.0, default: 0.0)
- `planned_absence`: list[date] — Specific dates this resource is unavailable

**Example:**

```python
for resource in project.resources:
    print(f"Resource: {resource.name}")
    print(f"  Availability: {resource.availability * 100:.0f}%")
    print(f"  Experience level: {resource.experience_level}")
    print(f"  Calendar: {resource.calendar}")
    if resource.planned_absence:
        print(f"  Planned absence: {len(resource.planned_absence)} days")
```

### `CalendarSpec`

Defines a working calendar for scheduling.

**Key fields:**

- `id`: str — Calendar identifier (default: `"default"`)
- `work_hours_per_day`: float — Working hours per day (default: 8.0)
- `work_days`: list[int] — Working days of the week, where 1=Monday through 7=Sunday (default: `[1, 2, 3, 4, 5]`)
- `holidays`: list[date] — Specific non-working dates

**Example:**

```python
for calendar in project.calendars:
    print(f"Calendar: {calendar.id}")
    print(f"  Work hours/day: {calendar.work_hours_per_day}")
    print(f"  Work days: {calendar.work_days}")
    if calendar.holidays:
        print(f"  Holidays: {len(calendar.holidays)} days")
```

### `UncertaintyFactors`

Applies multipliers to adjust base task duration based on project characteristics.

**Supported fields:**

- `team_experience`: `"high"` | `"medium"` | `"low"`
- `requirements_maturity`: `"high"` | `"medium"` | `"low"`
- `technical_complexity`: `"low"` | `"medium"` | `"high"`
- `team_distribution`: `"colocated"` | `"distributed"`
- `integration_complexity`: `"low"` | `"medium"` | `"high"`

Each is optional; only specified factors affect the task estimate. The actual multiplier values are defined in `Config.uncertainty_factors`.

**Example:**

```python
for task in project.tasks:
    if task.uncertainty_factors:
        factors = task.uncertainty_factors
        print(f"Task {task.id} uncertainty adjustments:")
        if factors.team_experience:
            print(f"  Team experience: {factors.team_experience}")
        if factors.technical_complexity:
            print(f"  Technical complexity: {factors.technical_complexity}")
```

### Sprint Planning Models

These models define the sprint-planning input configuration. They are populated from the `sprint_planning:` block in a project YAML file.

#### `SprintPlanningSpec`

Top-level sprint planning configuration.

**Key fields:**

- `enabled`: bool — Whether sprint planning is active (default: `False`)
- `sprint_length_weeks`: int — Length of each sprint in weeks
- `capacity_mode`: `SprintCapacityMode` — `"story_points"` or `"tasks"`
- `history`: list[`SprintHistoryEntry`] — Historical sprint outcomes (minimum 2 usable rows required)
- `planning_confidence_level`: float — Confidence level for commitment guidance (0–1)
- `removed_work_treatment`: `RemovedWorkTreatment` — `"churn_only"` or `"reduce_backlog"`
- `future_sprint_overrides`: list[`FutureSprintOverrideSpec`] — Per-sprint capacity adjustments
- `volatility_overlay`: `SprintVolatilitySpec` — Sprint disruption model
- `spillover`: `SprintSpilloverSpec` — Task spillover model
- `velocity_model`: `SprintVelocityModel` — `"empirical"` or `"neg_binomial"`
- `sickness`: `SprintSicknessSpec` — Per-person sickness model

#### `SprintHistoryEntry`

One historical sprint outcome row.

**Key fields:**

- `sprint_id`: str — Unique identifier for this sprint
- `sprint_length_weeks`: int | None — Override sprint length (defaults to parent)
- `completed_story_points`: float | None — Story points completed (mutually exclusive with `completed_tasks`)
- `completed_tasks`: int | None — Tasks completed (mutually exclusive with `completed_story_points`)
- `spillover_story_points`: float — Unfinished story points carried over (default: 0)
- `spillover_tasks`: int — Unfinished tasks carried over (default: 0)
- `added_story_points` / `added_tasks`: float / int — Work added mid-sprint (default: 0)
- `removed_story_points` / `removed_tasks`: float / int — Work removed mid-sprint (default: 0)
- `holiday_factor`: float — Capacity adjustment for holidays (default: 1.0)
- `end_date`: date | None — Sprint end date
- `team_size`: int | None — Team size during this sprint
- `notes`: str | None — Free-text notes

#### `SprintVolatilitySpec`

Sprint-level disruption overlay (unexpected events reducing capacity).

**Key fields:**

- `enabled`: bool (default: `False`)
- `disruption_probability`: float — Probability of disruption per sprint
- `disruption_multiplier_low` / `disruption_multiplier_expected` / `disruption_multiplier_high`: float — Triangular distribution for capacity reduction

#### `SprintSpilloverSpec`

Task-level execution spillover model.

**Key fields:**

- `enabled`: bool (default: `False`)
- `model`: `SprintSpilloverModel` — `"table"` or `"logistic"`
- `size_reference_points`: float — Reference point size for scaling
- `size_brackets`: list[`SprintSpilloverBracketSpec`] — Table-model probability brackets
- `consumed_fraction_alpha` / `consumed_fraction_beta`: float — Beta distribution parameters for consumed fraction
- `logistic_slope` / `logistic_intercept`: float — Logistic model parameters

#### `SprintSicknessSpec`

Per-person sickness model for sprint capacity.

**Key fields:**

- `enabled`: bool (default: `False`)
- `team_size`: int | None — Override team size for sickness calculations
- `probability_per_person_per_week`: float — Sickness probability
- `duration_log_mu` / `duration_log_sigma`: float — Log-normal parameters for sickness duration

### Enums

The following enums are part of the model API:

- `DistributionType` — `"triangular"` or `"lognormal"`
- `ImpactType` — `"percentage"` or `"absolute"`
- `EffortUnit` — `"hours"`, `"days"`, or `"weeks"`
- `SprintCapacityMode` — `"story_points"` or `"tasks"`
- `SprintVelocityModel` — `"empirical"` or `"neg_binomial"`
- `SprintSpilloverModel` — `"table"` or `"logistic"`
- `RemovedWorkTreatment` — `"churn_only"` or `"reduce_backlog"`
- `ConstrainedSchedulingAssignmentMode` — `"greedy_single_pass"` or `"criticality_two_pass"`

