## Project Models

### `Project`

Represents the complete project definition with metadata, tasks, risks, resources, and calendars.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `project` | `ProjectMetadata` | required | Project name, start date, hours/day, and thresholds |
| `tasks` | `list[Task]` | required | Work items and their dependencies |
| `project_risks` | `list[Risk]` | `[]` | Top-level project-level risks |
| `resources` | `list[ResourceSpec]` | `[]` | Named resource pools |
| `calendars` | `list[CalendarSpec]` | `[]` | Named calendars for holidays/exclusions |
| `sprint_planning` | `SprintPlanningSpec \| None` | `None` | Sprint planning configuration if enabled |

**Key methods:**

- `get_task_by_id(task_id: str) -> Task | None` — Retrieve a task by its ID

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

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | required | Project name |
| `description` | `str \| None` | `None` | Optional project description |
| `start_date` | `date` | required | Project start date |
| `hours_per_day` | `float` | `8.0` | Working hours per day |
| `currency` | `str \| None` | `"USD"` | Currency for cost tracking |
| `confidence_levels` | `list[int]` | `[10, 25, 50, 75, 80, 85, 90, 95, 99]` | Percentiles to include in reports |
| `probability_red_threshold` | `float` | `0.5` | Probability below which delivery is shown as red |
| `probability_green_threshold` | `float` | `0.9` | Probability above which delivery is shown as green |
| `distribution` | `DistributionType` | `"triangular"` | Default task duration distribution |
| `team_size` | `int \| None` | `None` | Total team size; used for coordination overhead and auto-generating resources |

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

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | `str` | required | Unique task identifier |
| `name` | `str` | required | Human-readable task name |
| `description` | `str \| None` | `None` | Optional task description |
| `estimate` | `TaskEstimate` | required | Duration estimate |
| `dependencies` | `list[str]` | `[]` | Task IDs this task depends on |
| `uncertainty_factors` | `UncertaintyFactors \| None` | `UncertaintyFactors()` | Uncertainty adjustments; defaults to a new instance with all-medium/colocated levels |
| `resources` | `list[str]` | `[]` | Required resource names |
| `max_resources` | `int` | `1` | Maximum number of resources that can be assigned |
| `min_experience_level` | `int` | `1` | Minimum experience level required (1, 2, or 3) |
| `planning_story_points` | `int \| None` | `None` | Story points override for sprint planning |
| `priority` | `int \| None` | `None` | Scheduling priority hint |
| `spillover_probability_override` | `float \| None` | `None` | Override for sprint spillover probability (0.0–1.0) |
| `risks` | `list[Risk]` | `[]` | Task-specific risks |

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

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `distribution` | `DistributionType \| None` | `None` | Override the project-level distribution for this task |
| `low` | `float \| None` | `None` | Minimum duration (optimistic). Also accepted as `min`. |
| `expected` | `float \| None` | `None` | Best-guess duration. Also accepted as `most_likely`. |
| `high` | `float \| None` | `None` | Maximum duration (pessimistic). Also accepted as `max`. |
| `t_shirt_size` | `str \| None` | `None` | Size token, e.g. `"M"`, `"XL"`, or `"epic.L"` |
| `story_points` | `int \| None` | `None` | Story point value (allowed: 1, 2, 3, 5, 8, 13, 21) |
| `unit` | `EffortUnit \| None` | `None` (hours for explicit estimates) | Effort unit (`"hours"`, `"days"`, `"weeks"`). Must not be set for symbolic estimates — the unit comes from configuration. |

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

**`Risk` fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | `str` | required | Unique risk identifier |
| `name` | `str` | required | Human-readable risk name |
| `probability` | `float` | required | Probability this risk occurs (0.0–1.0) |
| `impact` | `float \| RiskImpact` | required | Time penalty in hours (float), or a `RiskImpact` object |
| `description` | `str \| None` | `None` | Optional description |

**`RiskImpact` fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | `ImpactType` | required | `"percentage"` or `"absolute"` |
| `value` | `float` | required | Percentage (0–100) or absolute duration |
| `unit` | `EffortUnit \| None` | `None` | Unit for absolute impacts (`"hours"`, `"days"`, `"weeks"`) |

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

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str \| None` | `None` | Resource name (e.g. `"Alice"`). Auto-generated as `resource_001` etc. if omitted. |
| `id` | `str \| None` | `None` | Legacy identifier used as fallback when `name` is not set |
| `availability` | `float` | `1.0` | Fraction of time available (must be > 0.0, ≤ 1.0) |
| `calendar` | `str` | `"default"` | Calendar identifier to use |
| `experience_level` | `int` | `2` | Skill level: 1 (junior), 2 (mid), or 3 (senior) |
| `productivity_level` | `float` | `1.0` | Productivity multiplier (0.1–2.0) |
| `sickness_prob` | `float` | `0.0` | Probability of absence per scheduling unit (0.0–1.0) |
| `planned_absence` | `list[date]` | `[]` | Specific dates this resource is unavailable |

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

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | `str` | `"default"` | Calendar identifier |
| `work_hours_per_day` | `float` | `8.0` | Working hours per day |
| `work_days` | `list[int]` | `[1, 2, 3, 4, 5]` | Working days of the week (1=Monday … 7=Sunday) |
| `holidays` | `list[date]` | `[]` | Specific non-working dates |

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

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `team_experience` | `str \| None` | `"medium"` | Team experience: `"high"`, `"medium"`, or `"low"` |
| `requirements_maturity` | `str \| None` | `"medium"` | Requirements maturity: `"high"`, `"medium"`, or `"low"` |
| `technical_complexity` | `str \| None` | `"medium"` | Technical complexity: `"low"`, `"medium"`, or `"high"` |
| `team_distribution` | `str \| None` | `"colocated"` | Team distribution: `"colocated"` or `"distributed"` |
| `integration_complexity` | `str \| None` | `"medium"` | Integration complexity: `"low"`, `"medium"`, or `"high"` |

All fields default to their neutral level (`"medium"` or `"colocated"`), which maps to a 1.0 multiplier and has no effect on the estimate. Only changing a field away from its default affects the task duration. The actual multiplier values are defined in `Config.uncertainty_factors`.

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

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `False` | Whether sprint planning is active |
| `sprint_length_weeks` | `int` | required | Length of each sprint in weeks |
| `capacity_mode` | `SprintCapacityMode` | required | `"story_points"` or `"tasks"` |
| `history` | `list[SprintHistoryEntry]` | `[]` | Historical sprint outcomes (minimum 2 usable rows required when `enabled`) |
| `planning_confidence_level` | `float` | `0.80` | Confidence level for commitment guidance (0–1) |
| `removed_work_treatment` | `RemovedWorkTreatment` | `"churn_only"` | How removed scope affects forecasts: `"churn_only"` or `"reduce_backlog"` |
| `future_sprint_overrides` | `list[FutureSprintOverrideSpec]` | `[]` | Per-sprint capacity adjustments |
| `volatility_overlay` | `SprintVolatilitySpec` | `SprintVolatilitySpec()` | Sprint disruption model |
| `spillover` | `SprintSpilloverSpec` | `SprintSpilloverSpec()` | Task spillover model |
| `velocity_model` | `SprintVelocityModel` | `"empirical"` | `"empirical"` or `"neg_binomial"` |
| `sickness` | `SprintSicknessSpec` | `SprintSicknessSpec()` | Per-person sickness model |

#### `SprintHistoryEntry`

One historical sprint outcome row.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sprint_id` | `str` | required | Unique identifier for this sprint |
| `sprint_length_weeks` | `int \| None` | `None` | Override sprint length (defaults to parent `SprintPlanningSpec.sprint_length_weeks`) |
| `completed_story_points` | `float \| None` | `None` | Story points completed (mutually exclusive with `completed_tasks`) |
| `completed_tasks` | `int \| None` | `None` | Tasks completed (mutually exclusive with `completed_story_points`) |
| `spillover_story_points` | `float` | `0` | Unfinished story points carried over |
| `spillover_tasks` | `int` | `0` | Unfinished tasks carried over |
| `added_story_points` | `float` | `0` | Story points added mid-sprint |
| `added_tasks` | `int` | `0` | Tasks added mid-sprint |
| `removed_story_points` | `float` | `0` | Story points removed mid-sprint |
| `removed_tasks` | `int` | `0` | Tasks removed mid-sprint |
| `holiday_factor` | `float` | `1.0` | Capacity adjustment for holidays |
| `end_date` | `date \| None` | `None` | Sprint end date |
| `team_size` | `int \| None` | `None` | Team size during this sprint |
| `notes` | `str \| None` | `None` | Free-text notes |

#### `FutureSprintOverrideSpec`

Forward-looking capacity adjustment for a specific future sprint. At least one of `sprint_number` or `start_date` must be provided.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sprint_number` | `int \| None` | `None` | Target sprint by 1-based number |
| `start_date` | `date \| None` | `None` | Target sprint by start date (must align to a sprint boundary) |
| `holiday_factor` | `float` | `1.0` | Capacity adjustment for holidays |
| `capacity_multiplier` | `float` | `1.0` | Overall capacity multiplier for this sprint |
| `notes` | `str \| None` | `None` | Free-text notes |

#### `SprintVolatilitySpec`

Sprint-level disruption overlay (unexpected events reducing capacity).

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `False` | Whether the volatility overlay is active |
| `disruption_probability` | `float` | `0.0` | Probability of disruption per sprint (0.0–1.0) |
| `disruption_multiplier_low` | `float` | `1.0` | Low end of triangular capacity-reduction distribution |
| `disruption_multiplier_expected` | `float` | `1.0` | Expected value of capacity-reduction distribution |
| `disruption_multiplier_high` | `float` | `1.0` | High end of triangular capacity-reduction distribution |

#### `SprintSpilloverSpec`

Task-level execution spillover model.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `False` | Whether spillover modeling is active |
| `model` | `SprintSpilloverModel` | `"table"` | `"table"` or `"logistic"` |
| `size_reference_points` | `float` | `5.0` | Reference size for normalizing story-point brackets |
| `size_brackets` | `list[SprintSpilloverBracketSpec]` | (default table) | Table-model probability brackets (ascending `max_points`, last entry must be unbounded) |
| `consumed_fraction_alpha` | `float` | `3.25` | Beta distribution α for spilled fraction consumed |
| `consumed_fraction_beta` | `float` | `1.75` | Beta distribution β for spilled fraction consumed |
| `logistic_slope` | `float` | `1.9` | Logistic model slope parameter |
| `logistic_intercept` | `float` | `≈ -1.992` | Logistic model intercept parameter |

#### `SprintSpilloverBracketSpec`

One bracket in the table-based spillover model, mapping a story-point range to a spillover probability.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_points` | `float \| None` | `None` | Upper bound of this bracket in story points. `None` creates an unbounded catch-all bracket (must be last). |
| `probability` | `float` | required | Spillover probability for tasks in this bracket (0.0–1.0) |

#### `SprintSicknessSpec`

Per-person sickness model for sprint capacity.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `False` | Whether sickness modeling is active |
| `team_size` | `int \| None` | `None` | Override team size for sickness calculations |
| `probability_per_person_per_week` | `float` | `0.058` | Sickness probability per person per week |
| `duration_log_mu` | `float` | `0.693` | Log-normal μ for sickness duration |
| `duration_log_sigma` | `float` | `0.75` | Log-normal σ for sickness duration |

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

