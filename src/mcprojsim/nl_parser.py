"""Natural language project description parser for mcprojsim.

Parses semi-structured, informal project descriptions into syntactically
correct mcprojsim YAML project specification files.

Supported input patterns:
    - Project name: "Project name: My Project"
    - Start date: "Start date: 2026-01-15"
    - Tasks: "Task N:" followed by bullet points
    - T-shirt sizes: "Size: M", "Size XL", "Size. XL"
    - Story points: "Story points: 5"
    - Explicit estimates: "Estimate: 3/5/10 days"
    - Dependencies: "Depends on Task 1", "Depends on Task 1, Task 2"
    - Resources: "Resource N: Name" followed by bullet points
    - Calendars: "Calendar: id" followed by bullet points
    - Task constraints: "Resources: Alice, Bob", "Max resources: 2",
      "Min experience: 3"
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Canonical T-shirt size aliases for normalization
_SIZE_ALIASES: dict[str, str] = {
    "XS": "XS",
    "EXTRA SMALL": "XS",
    "EXTRASMALL": "XS",
    "S": "S",
    "SMALL": "S",
    "M": "M",
    "MEDIUM": "M",
    "MED": "M",
    "L": "L",
    "LARGE": "L",
    "XL": "XL",
    "EXTRA LARGE": "XL",
    "EXTRALARGE": "XL",
    "XXL": "XXL",
    "EXTRA EXTRA LARGE": "XXL",
    "2XL": "XXL",
}

_VALID_SIZES = {"XS", "S", "M", "L", "XL", "XXL"}


@dataclass
class ParsedTask:
    """A task extracted from a natural language description."""

    number: int
    name: str = ""
    t_shirt_size: str | None = None
    story_points: int | None = None
    min_estimate: float | None = None
    most_likely_estimate: float | None = None
    max_estimate: float | None = None
    estimate_unit: str = "days"
    dependency_refs: list[str] = field(default_factory=list)
    description: str | None = None
    resources: list[str] = field(default_factory=list)
    max_resources: int = 1
    min_experience_level: int = 1


@dataclass
class ParsedResource:
    """A resource/team member extracted from a natural language description."""

    number: int
    name: str = ""
    availability: float = 1.0
    experience_level: int = 2
    productivity_level: float = 1.0
    calendar: str = "default"
    sickness_prob: float = 0.0
    planned_absence: list[str] = field(default_factory=list)


@dataclass
class ParsedCalendar:
    """A working calendar extracted from a natural language description."""

    id: str = "default"
    work_hours_per_day: float = 8.0
    work_days: list[int] = field(default_factory=lambda: [1, 2, 3, 4, 5])
    holidays: list[str] = field(default_factory=list)


@dataclass
class ParsedProject:
    """A project extracted from a natural language description."""

    name: str = "Untitled Project"
    start_date: str | None = None
    description: str | None = None
    hours_per_day: float = 8.0
    tasks: list[ParsedTask] = field(default_factory=list)
    confidence_levels: list[int] = field(default_factory=lambda: [50, 80, 90, 95])
    resources: list[ParsedResource] = field(default_factory=list)
    calendars: list[ParsedCalendar] = field(default_factory=list)


class NLProjectParser:
    """Parser for semi-structured natural language project descriptions.

    Extracts project metadata (name, date) and task definitions
    (name, size, dependencies, estimates) from informal text and
    generates valid mcprojsim YAML project files.
    """

    # -- Project-level patterns ------------------------------------------------
    _PROJECT_NAME_RE = re.compile(r"project\s*(?:name)?\s*[:.=]\s*(.+)", re.IGNORECASE)
    _START_DATE_RE = re.compile(
        r"start\s*date\s*[:.=]\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE
    )
    _DESCRIPTION_RE = re.compile(r"description\s*[:.=]\s*(.+)", re.IGNORECASE)
    _HOURS_PER_DAY_RE = re.compile(
        r"hours?\s*per\s*day\s*[:.=]\s*([\d.]+)", re.IGNORECASE
    )
    _CONFIDENCE_RE = re.compile(
        r"confidence\s*(?:levels?)?\s*[:.=]\s*([\d,\s]+)", re.IGNORECASE
    )

    # -- Task header -----------------------------------------------------------
    _TASK_HEADER_RE = re.compile(r"task\s*(\d+)\s*[:.=]?\s*(.*)", re.IGNORECASE)

    # -- Resource header -------------------------------------------------------
    _RESOURCE_HEADER_RE = re.compile(r"resource\s*(\d+)\s*[:.=]?\s*(.*)", re.IGNORECASE)

    # -- Calendar header -------------------------------------------------------
    _CALENDAR_HEADER_RE = re.compile(r"calendar\s*[:.=]?\s*(.+)", re.IGNORECASE)

    # -- Task bullet patterns --------------------------------------------------
    _NAME_RE = re.compile(r"name\s*[:.=]?\s*(.+)", re.IGNORECASE)
    _SIZE_RE = re.compile(r"size\s*[:.=]?\s*(.+)", re.IGNORECASE)
    _STORY_POINTS_RE = re.compile(
        r"(?:story\s*)?points?\s*[:.=]?\s*(\d+)", re.IGNORECASE
    )
    _DEPENDS_RE = re.compile(r"depends?\s*(?:on)?\s*[:.=]?\s*(.+)", re.IGNORECASE)
    _ESTIMATE_RE = re.compile(
        r"estimate\s*[:.=]?\s*([\d.]+)\s*[-/,]\s*([\d.]+)\s*[-/,]\s*([\d.]+)"
        r"(?:\s+(hours?|days?|weeks?|h|d|w))?",
        re.IGNORECASE,
    )
    _TASK_REF_RE = re.compile(r"task\s*(\d+)", re.IGNORECASE)

    # -- Task constraint bullet patterns ---------------------------------------
    _TASK_RESOURCES_RE = re.compile(r"resources?\s*[:.=]?\s*(.+)", re.IGNORECASE)
    _TASK_MAX_RESOURCES_RE = re.compile(
        r"max\s*resources?\s*[:.=]?\s*(\d+)", re.IGNORECASE
    )
    _TASK_MIN_EXPERIENCE_RE = re.compile(
        r"min(?:imum)?\s*experience(?:\s*level)?\s*[:.=]?\s*([123])", re.IGNORECASE
    )

    # -- Resource bullet patterns ----------------------------------------------
    _RES_EXPERIENCE_RE = re.compile(
        r"experience(?:\s*level)?\s*[:.=]?\s*([123])", re.IGNORECASE
    )
    _RES_PRODUCTIVITY_RE = re.compile(
        r"productivity(?:\s*level)?\s*[:.=]?\s*([\d.]+)", re.IGNORECASE
    )
    _RES_AVAILABILITY_RE = re.compile(
        r"availability\s*[:.=]?\s*([\d.]+)", re.IGNORECASE
    )
    _RES_CALENDAR_RE = re.compile(r"calendar\s*[:.=]?\s*(\S+)", re.IGNORECASE)
    _RES_SICKNESS_RE = re.compile(
        r"sickness(?:\s*prob(?:ability)?)?\s*[:.=]?\s*([\d.]+)", re.IGNORECASE
    )
    _RES_ABSENCE_RE = re.compile(
        r"(?:planned\s*)?absence\s*[:.=]?\s*(.+)", re.IGNORECASE
    )
    _ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

    # -- Calendar bullet patterns ----------------------------------------------
    _CAL_WORK_HOURS_RE = re.compile(
        r"work\s*hours?(?:\s*per\s*day)?\s*[:.=]?\s*([\d.]+)", re.IGNORECASE
    )
    _CAL_WORK_DAYS_RE = re.compile(r"work\s*days?\s*[:.=]?\s*([\d,\s]+)", re.IGNORECASE)
    _CAL_HOLIDAYS_RE = re.compile(r"holidays?\s*[:.=]?\s*(.+)", re.IGNORECASE)

    # -- Public API ------------------------------------------------------------

    def parse(self, text: str) -> ParsedProject:
        """Parse a natural language project description.

        Args:
            text: Semi-structured project description text.

        Returns:
            ParsedProject with extracted information.

        Raises:
            ValueError: If no tasks are found in the description.
        """
        project = ParsedProject()
        lines = text.strip().splitlines()
        current_task: ParsedTask | None = None
        current_resource: ParsedResource | None = None
        current_calendar: ParsedCalendar | None = None

        def _flush_section() -> None:
            nonlocal current_task, current_resource, current_calendar
            if current_task is not None:
                project.tasks.append(current_task)
                current_task = None
            if current_resource is not None:
                project.resources.append(current_resource)
                current_resource = None
            if current_calendar is not None:
                project.calendars.append(current_calendar)
                current_calendar = None

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            # Check for task header
            task_match = self._TASK_HEADER_RE.match(line)
            if task_match:
                _flush_section()
                task_num = int(task_match.group(1))
                inline_name = task_match.group(2).strip().rstrip(":.")
                current_task = ParsedTask(number=task_num)
                if inline_name:
                    current_task.name = inline_name
                continue

            # Check for resource header
            resource_match = self._RESOURCE_HEADER_RE.match(line)
            if resource_match:
                _flush_section()
                res_num = int(resource_match.group(1))
                inline_name = resource_match.group(2).strip().rstrip(":.")
                current_resource = ParsedResource(number=res_num)
                if inline_name:
                    current_resource.name = inline_name
                continue

            # Check for calendar header (raw line without bullet prefix
            # won't match inside a section where lines start with - or *)
            calendar_match = self._CALENDAR_HEADER_RE.match(line)
            if calendar_match:
                _flush_section()
                cal_id = calendar_match.group(1).strip().rstrip(":.")
                current_calendar = ParsedCalendar(id=cal_id)
                continue

            # Inside a task: process bullet points
            if current_task is not None:
                bullet_text = re.sub(r"^[-*•]\s*", "", line).strip()
                if not bullet_text:
                    continue

                if self._try_parse_task_name(bullet_text, current_task):
                    continue
                if self._try_parse_task_max_resources(bullet_text, current_task):
                    continue
                if self._try_parse_task_min_experience(bullet_text, current_task):
                    continue
                if self._try_parse_task_resources(bullet_text, current_task):
                    continue
                if self._try_parse_size(bullet_text, current_task):
                    continue
                if self._try_parse_story_points(bullet_text, current_task):
                    continue
                if self._try_parse_depends(bullet_text, current_task):
                    continue
                if self._try_parse_estimate(bullet_text, current_task):
                    continue

                # Unmatched bullet → task name or description
                if not current_task.name:
                    current_task.name = bullet_text
                elif not current_task.description:
                    current_task.description = bullet_text
                continue

            # Inside a resource: process bullet points
            if current_resource is not None:
                bullet_text = re.sub(r"^[-*•]\s*", "", line).strip()
                if not bullet_text:
                    continue
                self._try_parse_resource_bullet(bullet_text, current_resource)
                continue

            # Inside a calendar: process bullet points
            if current_calendar is not None:
                bullet_text = re.sub(r"^[-*•]\s*", "", line).strip()
                if not bullet_text:
                    continue
                self._try_parse_calendar_bullet(bullet_text, current_calendar)
                continue

            # Project-level metadata
            self._try_parse_project_metadata(line, project)

        # Flush the last open section
        _flush_section()

        if not project.tasks:
            raise ValueError("No tasks found in the project description.")

        # Default task names for tasks without an explicit name
        for task in project.tasks:
            if not task.name:
                task.name = f"Task {task.number}"

        # Default resource names for resources without an explicit name
        for resource in project.resources:
            if not resource.name:
                resource.name = f"resource_{resource.number:03d}"

        return project

    def to_yaml(self, project: ParsedProject) -> str:
        """Convert a ParsedProject to a valid mcprojsim YAML project file.

        Args:
            project: The parsed project data.

        Returns:
            YAML string ready to be saved as a project file.
        """
        task_id_map: dict[str, str] = {}
        for task in project.tasks:
            task_id_map[str(task.number)] = f"task_{task.number:03d}"

        lines: list[str] = []
        lines.append("project:")
        lines.append(f"  name: {self._yaml_str(project.name)}")
        if project.description:
            lines.append(f"  description: {self._yaml_str(project.description)}")
        if project.start_date:
            lines.append(f'  start_date: "{project.start_date}"')
        if project.hours_per_day != 8.0:
            lines.append(f"  hours_per_day: {self._fmt_num(project.hours_per_day)}")
        cl = ", ".join(str(c) for c in project.confidence_levels)
        lines.append(f"  confidence_levels: [{cl}]")
        lines.append("")
        lines.append("tasks:")

        for i, task in enumerate(project.tasks):
            if i > 0:
                lines.append("")
            tid = task_id_map[str(task.number)]
            lines.append(f'  - id: "{tid}"')
            lines.append(f"    name: {self._yaml_str(task.name)}")
            if task.description:
                lines.append(f"    description: {self._yaml_str(task.description)}")

            # Estimate section
            if task.t_shirt_size:
                lines.append("    estimate:")
                lines.append(f'      t_shirt_size: "{task.t_shirt_size}"')
            elif task.story_points is not None:
                lines.append("    estimate:")
                lines.append(f"      story_points: {task.story_points}")
            elif task.min_estimate is not None:
                lines.append("    estimate:")
                lines.append(f"      min: {self._fmt_num(task.min_estimate)}")
                if task.most_likely_estimate is not None:
                    lines.append(
                        f"      most_likely:"
                        f" {self._fmt_num(task.most_likely_estimate)}"
                    )
                if task.max_estimate is not None:
                    lines.append(f"      max: {self._fmt_num(task.max_estimate)}")
                lines.append(f'      unit: "{task.estimate_unit}"')

            # Dependencies
            deps = []
            for ref in task.dependency_refs:
                dep_id = task_id_map.get(ref)
                if dep_id:
                    deps.append(dep_id)
            if deps:
                dep_str = ", ".join(f'"{d}"' for d in deps)
                lines.append(f"    dependencies: [{dep_str}]")
            else:
                lines.append("    dependencies: []")

            # Resource constraints (only emit non-defaults)
            if task.resources:
                res_str = ", ".join(f'"{r}"' for r in task.resources)
                lines.append(f"    resources: [{res_str}]")
            if task.max_resources != 1:
                lines.append(f"    max_resources: {task.max_resources}")
            if task.min_experience_level != 1:
                lines.append(f"    min_experience_level: {task.min_experience_level}")

        # Resources section
        if project.resources:
            lines.append("")
            lines.append("resources:")
            for resource in project.resources:
                lines.append(f'  - name: "{resource.name}"')
                if resource.calendar != "default":
                    lines.append(f'    calendar: "{resource.calendar}"')
                if resource.availability != 1.0:
                    lines.append(
                        f"    availability:" f" {self._fmt_num(resource.availability)}"
                    )
                lines.append(f"    experience_level: {resource.experience_level}")
                lines.append(
                    f"    productivity_level:"
                    f" {self._fmt_num(resource.productivity_level)}"
                )
                if resource.sickness_prob > 0.0:
                    lines.append(
                        f"    sickness_prob:"
                        f" {self._fmt_num(resource.sickness_prob)}"
                    )
                if resource.planned_absence:
                    absence_str = ", ".join(f'"{d}"' for d in resource.planned_absence)
                    lines.append(f"    planned_absence: [{absence_str}]")

        # Calendars section
        if project.calendars:
            lines.append("")
            lines.append("calendars:")
            for calendar in project.calendars:
                lines.append(f'  - id: "{calendar.id}"')
                lines.append(
                    f"    work_hours_per_day:"
                    f" {self._fmt_num(calendar.work_hours_per_day)}"
                )
                days_str = ", ".join(str(d) for d in calendar.work_days)
                lines.append(f"    work_days: [{days_str}]")
                if calendar.holidays:
                    holidays_str = ", ".join(f'"{h}"' for h in calendar.holidays)
                    lines.append(f"    holidays: [{holidays_str}]")

        lines.append("")
        return "\n".join(lines)

    def parse_and_generate(self, text: str) -> str:
        """Parse a description and generate a YAML project file.

        Convenience method combining parse() and to_yaml().

        Args:
            text: Semi-structured project description text.

        Returns:
            Valid mcprojsim YAML project file content.
        """
        project = self.parse(text)
        return self.to_yaml(project)

    # -- Private helpers -------------------------------------------------------

    def _try_parse_project_metadata(self, line: str, project: ParsedProject) -> bool:
        m = self._PROJECT_NAME_RE.match(line)
        if m:
            project.name = m.group(1).strip()
            return True

        m = self._START_DATE_RE.match(line)
        if m:
            project.start_date = m.group(1)
            return True

        m = self._DESCRIPTION_RE.match(line)
        if m:
            project.description = m.group(1).strip()
            return True

        m = self._HOURS_PER_DAY_RE.match(line)
        if m:
            project.hours_per_day = float(m.group(1))
            return True

        m = self._CONFIDENCE_RE.match(line)
        if m:
            levels = [int(x.strip()) for x in m.group(1).split(",") if x.strip()]
            if levels:
                project.confidence_levels = sorted(levels)
            return True

        return False

    def _try_parse_size(self, text: str, task: ParsedTask) -> bool:
        m = self._SIZE_RE.match(text)
        if m:
            raw = m.group(1).strip().rstrip(".,;:")
            if not raw:
                return False
            # Try full text first, then first word only
            words = raw.split()
            full_upper = raw.upper()
            first_upper = words[0].upper()
            normalized = _SIZE_ALIASES.get(full_upper) or _SIZE_ALIASES.get(first_upper)
            if normalized and normalized in _VALID_SIZES:
                task.t_shirt_size = normalized
                return True
        return False

    def _try_parse_task_name(self, text: str, task: ParsedTask) -> bool:
        m = self._NAME_RE.match(text)
        if m:
            name = m.group(1).strip().rstrip(".,;:")
            if name and not task.name:
                task.name = name
                return True
        return False

    def _try_parse_story_points(self, text: str, task: ParsedTask) -> bool:
        m = self._STORY_POINTS_RE.match(text)
        if m:
            task.story_points = int(m.group(1))
            return True
        return False

    def _try_parse_depends(self, text: str, task: ParsedTask) -> bool:
        m = self._DEPENDS_RE.match(text)
        if m:
            dep_text = m.group(1)
            refs = self._TASK_REF_RE.findall(dep_text)
            if not refs:
                # Fallback: extract plain numbers
                refs = re.findall(r"(\d+)", dep_text)
            task.dependency_refs = [str(int(r)) for r in refs]
            return True
        return False

    def _try_parse_estimate(self, text: str, task: ParsedTask) -> bool:
        m = self._ESTIMATE_RE.match(text)
        if m:
            task.min_estimate = float(m.group(1))
            task.most_likely_estimate = float(m.group(2))
            task.max_estimate = float(m.group(3))
            if m.group(4):
                unit = m.group(4).lower()
                if unit.startswith("hour") or unit == "h":
                    task.estimate_unit = "hours"
                elif unit.startswith("day") or unit == "d":
                    task.estimate_unit = "days"
                elif unit.startswith("week") or unit == "w":
                    task.estimate_unit = "weeks"
            return True
        return False

    def _try_parse_task_resources(self, text: str, task: ParsedTask) -> bool:
        m = self._TASK_RESOURCES_RE.match(text)
        if m:
            raw = m.group(1).strip()
            names = [n.strip() for n in raw.split(",") if n.strip()]
            if names:
                task.resources = names
                return True
        return False

    def _try_parse_task_max_resources(self, text: str, task: ParsedTask) -> bool:
        m = self._TASK_MAX_RESOURCES_RE.match(text)
        if m:
            task.max_resources = int(m.group(1))
            return True
        return False

    def _try_parse_task_min_experience(self, text: str, task: ParsedTask) -> bool:
        m = self._TASK_MIN_EXPERIENCE_RE.match(text)
        if m:
            task.min_experience_level = int(m.group(1))
            return True
        return False

    def _try_parse_resource_bullet(self, text: str, resource: ParsedResource) -> bool:
        m = self._RES_EXPERIENCE_RE.match(text)
        if m:
            resource.experience_level = int(m.group(1))
            return True

        m = self._RES_PRODUCTIVITY_RE.match(text)
        if m:
            resource.productivity_level = float(m.group(1))
            return True

        m = self._RES_AVAILABILITY_RE.match(text)
        if m:
            resource.availability = float(m.group(1))
            return True

        m = self._RES_CALENDAR_RE.match(text)
        if m:
            resource.calendar = m.group(1).strip()
            return True

        m = self._RES_SICKNESS_RE.match(text)
        if m:
            resource.sickness_prob = float(m.group(1))
            return True

        m = self._RES_ABSENCE_RE.match(text)
        if m:
            dates = self._ISO_DATE_RE.findall(m.group(1))
            if dates:
                resource.planned_absence.extend(dates)
                return True

        # Unmatched bullet could be the resource name
        if not resource.name:
            resource.name = text
            return True

        return False

    def _try_parse_calendar_bullet(self, text: str, calendar: ParsedCalendar) -> bool:
        m = self._CAL_WORK_HOURS_RE.match(text)
        if m:
            calendar.work_hours_per_day = float(m.group(1))
            return True

        m = self._CAL_WORK_DAYS_RE.match(text)
        if m:
            days = [
                int(d.strip()) for d in m.group(1).split(",") if d.strip().isdigit()
            ]
            if days:
                calendar.work_days = days
            return True

        m = self._CAL_HOLIDAYS_RE.match(text)
        if m:
            dates = self._ISO_DATE_RE.findall(m.group(1))
            if dates:
                calendar.holidays.extend(dates)
            return True

        return False

    @staticmethod
    def _yaml_str(s: str) -> str:
        """Safely quote a string for use in YAML output."""
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    @staticmethod
    def _fmt_num(n: float) -> str:
        """Format a number, dropping .0 from integers."""
        return str(int(n)) if n == int(n) else str(n)
