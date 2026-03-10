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


@dataclass
class ParsedProject:
    """A project extracted from a natural language description."""

    name: str = "Untitled Project"
    start_date: str | None = None
    description: str | None = None
    hours_per_day: float = 8.0
    tasks: list[ParsedTask] = field(default_factory=list)
    confidence_levels: list[int] = field(default_factory=lambda: [50, 80, 90, 95])


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

    # -- Task bullet patterns --------------------------------------------------
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

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            # Check for task header
            task_match = self._TASK_HEADER_RE.match(line)
            if task_match:
                if current_task is not None:
                    project.tasks.append(current_task)
                task_num = int(task_match.group(1))
                inline_name = task_match.group(2).strip().rstrip(":.")
                current_task = ParsedTask(number=task_num)
                if inline_name:
                    current_task.name = inline_name
                continue

            # Inside a task: process bullet points
            if current_task is not None:
                bullet_text = re.sub(r"^[-*•]\s*", "", line).strip()
                if not bullet_text:
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

            # Project-level metadata
            self._try_parse_project_metadata(line, project)

        # Append the last task
        if current_task is not None:
            project.tasks.append(current_task)

        if not project.tasks:
            raise ValueError("No tasks found in the project description.")

        # Default task names for tasks without an explicit name
        for task in project.tasks:
            if not task.name:
                task.name = f"Task {task.number}"

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

    @staticmethod
    def _yaml_str(s: str) -> str:
        """Safely quote a string for use in YAML output."""
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    @staticmethod
    def _fmt_num(n: float) -> str:
        """Format a number, dropping .0 from integers."""
        return str(int(n)) if n == int(n) else str(n)
