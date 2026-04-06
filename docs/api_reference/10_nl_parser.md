
## Natural Language Parser

### `NLProjectParser`

Converts semi-structured, plain-text project descriptions into valid mcprojsim YAML project files. Also available via the `mcprojsim generate` CLI command and the MCP server's `generate_project_file` tool.

```python
from mcprojsim.nl_parser import NLProjectParser

parser = NLProjectParser()
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `parse` | `(text: str) -> ParsedProject` | Extract project metadata and tasks from a text description. Returns a `ParsedProject`. Raises `ValueError` if no tasks are found. |
| `to_yaml` | `(project: ParsedProject) -> str` | Render a `ParsedProject` as a valid YAML project file string. |
| `parse_and_generate` | `(text: str) -> str` | Convenience wrapper: calls `parse` then `to_yaml` and returns the YAML string directly. |

#### Input format

The parser processes the description line by line using a section-based state machine. A **section header** line (e.g. `Task 1:`, `Resource 2: Alice`, `Sprint planning:`) opens a new section; subsequent **bullet lines** (prefixed with `-`, `*`, or `•`) are parsed as properties of that section. Blank lines are ignored. Project-level metadata (name, start date, etc.) can appear anywhere outside a section.

**Separators are flexible.** In most patterns the separator between keyword and value can be `:`, `.`, `=`, or a space, and the keyword itself is case-insensitive. For example, all of the following are equivalent:

```
Size: M
Size. M
Size = M
size XL
```

---

#### Project-level metadata

These lines can appear before the first task or between sections:

| Keyword | Example | Notes |
|---------|---------|-------|
| `Project name:` / `Project:` | `Project name: Website Redesign` | |
| `Start date:` | `Start date: 2026-06-01` | ISO 8601 (`YYYY-MM-DD`) |
| `Description:` | `Description: Q3 infrastructure work` | |
| `Hours per day:` | `Hours per day: 7.5` | Default `8.0` |
| `Confidence levels:` | `Confidence levels: 50, 80, 90, 95` | Comma-separated percentiles |

---

#### Tasks

A task section starts with `Task N:` optionally followed by the task name on the same line. Subsequent bullet lines define properties:

| Bullet keyword | Example | Notes |
|----------------|---------|-------|
| `Name:` | `- Name: Backend API` | Also accepted as first unmatched bullet |
| `Size:` | `- Size: M` | See size aliases below |
| `Story points:` / `Points:` | `- Story points: 5` | |
| `Estimate:` | `- Estimate: 3/5/10 days` | `low/expected/high`, separator `/` `-` or `,` |
| `Depends on:` / `Depends:` / `Depend on:` | `- Depends on Task 1, Task 3` | References by task number |
| `Resources:` | `- Resources: Alice, Bob` | Names must match a `Resource N:` header |
| `Max resources:` | `- Max resources: 2` | Concurrent resource cap |
| `Min experience:` / `Min experience level:` | `- Min experience: 2` | 1–3 |

**Estimate units** for explicit estimates: `hours` / `hour` / `h`, `days` / `day` / `d`, `weeks` / `week` / `w`.

**T-shirt size aliases** — all of the following map to a canonical size:

| Canonical | Accepted aliases |
|-----------|-----------------|
| `XS` | `XS`, `Extra Small`, `Extrasmall` |
| `S` | `S`, `Small` |
| `M` | `M`, `Medium`, `Med` |
| `L` | `L`, `Large` |
| `XL` | `XL`, `Extra Large`, `Extralarge` |
| `XXL` | `XXL`, `Extra Extra Large`, `2XL` |

---

#### Resources

A resource section starts with `Resource N: Name`. Bullet properties:

| Bullet keyword | Example | Notes |
|----------------|---------|-------|
| `Experience level:` / `Experience:` | `- Experience: 3` | 1–3 |
| `Productivity level:` / `Productivity:` | `- Productivity: 1.1` | Multiplier, default `1.0` |
| `Availability:` | `- Availability: 0.8` | Fraction of full-time, 0–1 |
| `Calendar:` | `- Calendar: part_time` | References a `Calendar:` section ID |
| `Sickness prob:` / `Sickness:` | `- Sickness: 0.02` | Per-day probability |
| `Absence:` / `Planned absence:` | `- Absence: 2026-05-15, 2026-06-01` | Comma-separated ISO dates or date ranges (`2026-05-20 to 2026-05-22`) |

---

#### Calendars

A calendar section starts with `Calendar: id`. Bullet properties:

| Bullet keyword | Example | Notes |
|----------------|---------|-------|
| `Work hours per day:` / `Work hours:` | `- Work hours: 7` | |
| `Work days:` | `- Work days: 1, 2, 3, 4` | Integers, 1=Mon … 7=Sun |
| `Holidays:` | `- Holidays: 2026-12-25, 2026-12-26` | ISO 8601 dates |

---

#### Sprint planning

A `Sprint planning:` header opens the sprint planning section. Bullet properties:

| Bullet keyword | Example | Notes |
|----------------|---------|-------|
| `Sprint length:` | `- Sprint length: 2` | Weeks; also `2-week sprints` |
| `Capacity mode:` | `- Capacity mode: story points` | `story points` or `tasks` |
| `Planning confidence level:` | `- Planning confidence level: 80%` | |
| `Velocity model:` | `- Velocity model: empirical` | `empirical` or `neg_binomial` |
| `Removed work treatment:` | `- Removed work treatment: churn_only` | `churn_only` or `reduce_backlog` |
| `Sickness:` | `- Sickness: enabled` | `enabled`/`disabled`/`on`/`off`/`yes`/`no`/`true`/`false`; also `No sickness` |
| `Sickness team size:` | `- Sickness team size: 6` | |
| `Sickness probability per person per week:` | `- Sickness probability: 5%` | |
| `Sickness duration log mu:` | `- Sickness duration log mu: 1.1` | |
| `Sickness duration log sigma:` | `- Sickness duration log sigma: 0.4` | |

**Sprint history** entries use `Sprint history <id>:` as the header (auto-ID generated as `SPR-001`, `SPR-002`, … if omitted). Bullet keywords:

| Bullet keyword | Aliases | Notes |
|----------------|---------|-------|
| `Completed:` | `Done:`, `Finished:`, `Delivered:` | `10 points` or `10 tasks` |
| `Spillover:` | `Carryover:`, `Rolled over:` | |
| `Added:` | `Scope added:` | |
| `Removed:` | `Scope removed:` | |
| `Holiday factor:` | | Capacity reduction factor |

**Future sprint overrides** use `Future sprint override <N>:` or `Future sprint override <YYYY-MM-DD>:` as the header. Bullet properties: `Sprint number:`, `Start date:`, `Holiday factor:`, `Capacity multiplier:`, `Notes:`.

---

#### Complete example

```text
Project name: Platform Migration
Start date: 2026-05-01

Resource 1: Alice
- Experience: 3
- Productivity: 1.1
- Sickness: 0.02
- Absence: 2026-05-15

Resource 2: Bob
- Experience: 2
- Availability: 0.8

Calendar: default
- Work hours: 8
- Work days: 1, 2, 3, 4, 5
- Holidays: 2026-05-25

Task 1: Architecture design
- Estimate: 16/24/40 hours
- Min experience: 2

Task 2: Core implementation
- Estimate: 80/120/180 hours
- Depends on Task 1
- Resources: Alice, Bob
- Max resources: 2
- Min experience: 2
```

```python
from mcprojsim.nl_parser import NLProjectParser

yaml_output = NLProjectParser().parse_and_generate(description)
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
