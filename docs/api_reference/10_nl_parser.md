
## Natural Language Parser

### `NLProjectParser`

Converts semi-structured, plain-text project descriptions into valid mcprojsim YAML project files. Also available via the `mcprojsim generate` CLI command and the MCP server's `generate_project_file` tool.

```python
from mcprojsim.nl_parser import NLProjectParser

parser = NLProjectParser()
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `parse` | `(text: str) -> ParsedProject` | Extract project metadata and tasks from a text description. |
| `to_yaml` | `(project: ParsedProject) -> str` | Render a `ParsedProject` as a valid YAML project file string. |
| `parse_and_generate` | `(text: str) -> str` | Convenience wrapper: calls `parse` then `to_yaml` and returns the YAML string. |

**Supported input patterns:**

| Pattern | Example |
|---------|---------|
| Project name | `Project name: My Project` |
| Start date | `Start date: 2026-04-01` |
| Task header | `Task 1: Backend API` followed by bullet points |
| T-shirt size | `Size: M` or `Size XL` |
| Story points | `Story points: 5` |
| Explicit estimate | `Estimate: 3/5/10 days` (low/expected/high) |
| Dependencies | `Depends on Task 1, Task 3` |
| Resource | `Resource 1: Alice` followed by bullet points |
| Calendar | `Calendar: default` followed by bullet points |
| Task constraints | `Resources: Alice, Bob` · `Max resources: 2` · `Min experience: 3` |

```python
description = """
Project name: Website Redesign
Start date: 2026-06-01

Task 1: Design mockups
- Size: M

Task 2: Frontend implementation
- Size: L
- Depends on Task 1
"""

yaml_output = parser.parse_and_generate(description)
```

### Data Classes

#### `ParsedProject`

Top-level container for all data extracted from a natural language description.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | `"Untitled Project"` | Project name. |
| `start_date` | `str \| None` | `None` | ISO 8601 start date string. |
| `description` | `str \| None` | `None` | Optional project description. |
| `hours_per_day` | `float` | `8.0` | Working hours per day. |
| `tasks` | `list[ParsedTask]` | `[]` | Extracted tasks. |
| `confidence_levels` | `list[int]` | `[50, 80, 90, 95]` | Percentile confidence levels to report. |
| `resources` | `list[ParsedResource]` | `[]` | Extracted team members/resources. |
| `calendars` | `list[ParsedCalendar]` | `[]` | Extracted working calendars. |
| `sprint_planning` | `ParsedSprintPlanning \| None` | `None` | Sprint planning configuration, if present. |

#### `ParsedTask`

A single task extracted from the description.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `number` | `int` | required | Task number as written in the input (e.g., `1` for `Task 1:`). |
| `name` | `str` | `""` | Task name. |
| `t_shirt_size` | `str \| None` | `None` | Normalised T-shirt size label (e.g., `"M"`, `"XL"`). |
| `story_points` | `int \| None` | `None` | Story point estimate. |
| `low_estimate` | `float \| None` | `None` | Optimistic explicit estimate. |
| `expected_estimate` | `float \| None` | `None` | Expected explicit estimate. |
| `high_estimate` | `float \| None` | `None` | Pessimistic explicit estimate. |
| `estimate_unit` | `str` | `"days"` | Unit for explicit estimates (`"days"` or `"hours"`). |
| `dependency_refs` | `list[str]` | `[]` | Raw dependency references as written (e.g., `["Task 1"]`). |
| `description` | `str \| None` | `None` | Optional task description text. |
| `resources` | `list[str]` | `[]` | Resource names assigned to the task. |
| `max_resources` | `int` | `1` | Maximum number of resources that can work the task concurrently. |
| `min_experience_level` | `int` | `1` | Minimum experience level required for an assigned resource. |

#### `ParsedResource`

A team member or resource extracted from the description.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `number` | `int` | required | Resource number as written in the input (e.g., `1` for `Resource 1:`). |
| `name` | `str` | `""` | Resource name. |
| `availability` | `float` | `1.0` | Fraction of working time available (0.0–1.0). |
| `experience_level` | `int` | `2` | Experience level (1 = junior … 5 = senior). |
| `productivity_level` | `float` | `1.0` | Productivity multiplier. |
| `calendar` | `str` | `"default"` | Calendar ID used by this resource. |
| `sickness_prob` | `float` | `0.0` | Per-day sickness probability. |
| `planned_absence` | `list[str]` | `[]` | List of planned absence date strings. |

#### `ParsedCalendar`

A working calendar extracted from the description.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | `str` | `"default"` | Calendar identifier. |
| `work_hours_per_day` | `float` | `8.0` | Working hours per day. |
| `work_days` | `list[int]` | `[1, 2, 3, 4, 5]` | Working days of the week (1 = Monday … 7 = Sunday). |
| `holidays` | `list[str]` | `[]` | ISO 8601 holiday date strings. |

#### `ParsedSprintPlanning`

Sprint planning configuration extracted from the description.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `True` | Whether sprint planning is enabled. |
| `sprint_length_weeks` | `int` | `2` | Sprint length in weeks. |
| `capacity_mode` | `str` | `"story_points"` | Capacity tracking mode (`"story_points"` or `"tasks"`). |
| `planning_confidence_level` | `float \| None` | `None` | Confidence level override for commitment guidance. |
| `removed_work_treatment` | `str \| None` | `None` | How removed work is handled (`"churn_only"` or `"reduce_backlog"`). |
| `velocity_model` | `str \| None` | `None` | Velocity model override (`"empirical"` or `"neg_binomial"`). |
| `sickness_enabled` | `bool \| None` | `None` | Override for sickness simulation. |
| `sickness_team_size` | `int \| None` | `None` | Team size for sickness modelling. |
| `sickness_probability_per_person_per_week` | `float \| None` | `None` | Per-person-per-week sickness probability override. |
| `sickness_duration_log_mu` | `float \| None` | `None` | Log-mean for sickness duration distribution override. |
| `sickness_duration_log_sigma` | `float \| None` | `None` | Log-sigma for sickness duration distribution override. |
| `future_sprint_overrides` | `list[ParsedFutureSprintOverride]` | `[]` | Capacity overrides for future sprints. |
| `history` | `list[ParsedSprintHistoryEntry]` | `[]` | Historical sprint data. |

#### `ParsedFutureSprintOverride`

A capacity override for a future sprint.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sprint_number` | `int \| None` | `None` | Sprint number this override applies to. |
| `start_date` | `str \| None` | `None` | ISO 8601 start date for the overridden sprint. |
| `holiday_factor` | `float \| None` | `None` | Capacity reduction factor due to holidays (0.0–1.0). |
| `capacity_multiplier` | `float \| None` | `None` | Overall capacity multiplier for the sprint. |
| `notes` | `str \| None` | `None` | Free-text notes for this override. |

#### `ParsedSprintHistoryEntry`

A historical sprint outcome.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sprint_id` | `str` | required | Unique sprint identifier. |
| `completed_story_points` | `float \| None` | `None` | Story points completed in the sprint. |
| `completed_tasks` | `int \| None` | `None` | Tasks completed (task-capacity mode). |
| `spillover_story_points` | `float \| None` | `None` | Story points that spilled over to the next sprint. |
| `spillover_tasks` | `int \| None` | `None` | Tasks that spilled over (task-capacity mode). |
| `added_story_points` | `float \| None` | `None` | Story points added mid-sprint. |
| `added_tasks` | `int \| None` | `None` | Tasks added mid-sprint (task-capacity mode). |
| `removed_story_points` | `float \| None` | `None` | Story points removed mid-sprint. |
| `removed_tasks` | `int \| None` | `None` | Tasks removed mid-sprint (task-capacity mode). |
| `holiday_factor` | `float \| None` | `None` | Capacity reduction factor applied to this sprint. |
