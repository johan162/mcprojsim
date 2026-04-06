
## Natural Language Parser

### `NLProjectParser`

Converts semi-structured, plain-text project descriptions into valid mcprojsim YAML project files. Also available via the `mcprojsim generate` CLI command and the MCP server's `generate_project_file` tool.

```python
from mcprojsim.nl_parser import NLProjectParser

parser = NLProjectParser()
```

Methods:

- `parse(text: str) -> ParsedProject` — extract project metadata and tasks from a text description
- `to_yaml(project: ParsedProject) -> str` — render a `ParsedProject` as a valid YAML project file
- `parse_and_generate(text: str) -> str` — convenience wrapper that calls `parse` then `to_yaml`

Supported input patterns:

- `Project name: My Project`
- `Start date: 2026-04-01`
- `Task 1: Backend API` followed by bullet points
- `Size: M` or `Size XL` (T-shirt sizes)
- `Story points: 5`
- `Estimate: 3/5/10 days` (low/expected/high)
- `Depends on Task 1, Task 3`

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

### Data classes

- `ParsedProject` — extracted project-level data (`name`, `start_date`, `description`, `hours_per_day`, `tasks`, `confidence_levels`, `resources`, `calendars`, `sprint_planning`)
- `ParsedTask` — extracted task data (`name`, `t_shirt_size`, `story_points`, `low_estimate`/`expected_estimate`/`high_estimate`, `dependency_refs`)
- `ParsedResource` — extracted resource data (`name`, `availability`, `experience_level`, `productivity_level`, `calendar`, `sickness_prob`, `planned_absence`)
- `ParsedCalendar` — extracted calendar data (`id`, `work_hours_per_day`, `work_days`, `holidays`)
- `ParsedSprintPlanning` — extracted sprint-planning settings (`enabled`, `sprint_length_weeks`, `capacity_mode`, `history`, ...)

