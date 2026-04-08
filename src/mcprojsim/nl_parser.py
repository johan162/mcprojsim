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

from datetime import date, datetime, timedelta
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

_REFERENCE_TOKEN_ALIASES: dict[str, set[str]] = {
    "db": {"db", "database"},
    "database": {"db", "database"},
    "api": {"api", "rest", "backend", "server"},
    "rest": {"api", "rest", "backend", "server"},
    "backend": {"api", "rest", "backend", "server"},
    "server": {"api", "rest", "backend", "server"},
    "frontend": {"frontend", "ui"},
    "ui": {"frontend", "ui"},
    "authentication": {"authentication", "auth", "login"},
    "auth": {"authentication", "auth", "login"},
    "login": {"authentication", "auth", "login"},
    "deployment": {"deployment", "deploy"},
    "deploy": {"deployment", "deploy"},
    "qa": {"qa", "test", "testing", "quality"},
    "test": {"qa", "test", "testing", "quality"},
    "testing": {"qa", "test", "testing", "quality"},
    "quality": {"qa", "test", "testing", "quality"},
}

_GENERIC_REFERENCE_TOKENS = {
    "a",
    "an",
    "and",
    "after",
    "being",
    "by",
    "depends",
    "done",
    "is",
    "on",
    "ready",
    "the",
    "this",
    "work",
}

_FUZZY_DURATION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\ba\s*few\s+hours?\b|\bcouple\s+of\s+hours?\b|"
            r"\ban?\s+hour\s+or\s+two\b",
            re.IGNORECASE,
        ),
        "XS",
    ),
    (
        re.compile(
            r"\ba\s*day\s+or\s+two\b|\bcouple\s+of\s+days?\b|"
            r"\ba?\s*(?:half\s+a?\s*)?day\b|\bone\s+day\b|"
            r"\ba\s+full\s+day\b|\b(?:a?\s*few|several)\s+days?\b",
            re.IGNORECASE,
        ),
        "S",
    ),
    (
        re.compile(
            r"\b(?:about\s+)?(?:a|one)\s+week\b|\b5\s+(?:working\s+)?days?\b|"
            r"\b(?:half\s+a\s+week)\b",
            re.IGNORECASE,
        ),
        "M",
    ),
    (
        re.compile(
            r"\b(?:a?\s*few|several)\s+weeks?\b|\ba\s+month\s+or\s+(?:so|two)\b",
            re.IGNORECASE,
        ),
        "L",
    ),
    (
        re.compile(
            r"\b(?:a|one)\s+month\b|\bfour\s+weeks?\b|\ba\s+full\s+month\b",
            re.IGNORECASE,
        ),
        "XL",
    ),
    (
        re.compile(
            r"\b(?:a?\s*couple\s+of\s+|two\s+)months?\b|\bsix\s+weeks?\b",
            re.IGNORECASE,
        ),
        "XL",
    ),
    (
        re.compile(
            r"\b(?:a?\s*few|several|[3-6])\s+months?\b|\ba\s+quarter\b|"
            r"\bhalf\s+a\s+year\b|\bsix\s+months\b",
            re.IGNORECASE,
        ),
        "XXL",
    ),
]


@dataclass
class ParsedTask:
    """A task extracted from a natural language description."""

    number: int
    name: str = ""
    t_shirt_size: str | None = None
    story_points: int | None = None
    low_estimate: float | None = None
    expected_estimate: float | None = None
    high_estimate: float | None = None
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
class ParsedSprintHistoryEntry:
    """A historical sprint outcome extracted from natural language."""

    sprint_id: str
    completed_story_points: float | None = None
    completed_tasks: int | None = None
    spillover_story_points: float | None = None
    spillover_tasks: int | None = None
    added_story_points: float | None = None
    added_tasks: int | None = None
    removed_story_points: float | None = None
    removed_tasks: int | None = None
    holiday_factor: float | None = None


@dataclass
class ParsedSprintPlanning:
    """Sprint planning configuration extracted from natural language."""

    enabled: bool = True
    sprint_length_weeks: int = 2
    capacity_mode: str = "story_points"
    planning_confidence_level: float | None = None
    removed_work_treatment: str | None = None
    velocity_model: str | None = None
    sickness_enabled: bool | None = None
    sickness_team_size: int | None = None
    sickness_probability_per_person_per_week: float | None = None
    sickness_duration_log_mu: float | None = None
    sickness_duration_log_sigma: float | None = None
    future_sprint_overrides: list[ParsedFutureSprintOverride] = field(
        default_factory=list
    )
    history: list[ParsedSprintHistoryEntry] = field(default_factory=list)


@dataclass
class ParsedFutureSprintOverride:
    """A future sprint capacity override extracted from natural language."""

    sprint_number: int | None = None
    start_date: str | None = None
    holiday_factor: float | None = None
    capacity_multiplier: float | None = None
    notes: str | None = None


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
    sprint_planning: ParsedSprintPlanning | None = None


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
    _RELATIVE_DATE_RE = re.compile(
        r"start(?:ing|s)?\s+(?:date\s*[:.=]?\s*)?"
        r"(next\s+(?:monday|tuesday|wednesday|thursday|friday)|"
        r"in\s+\d+\s+(?:days?|weeks?)|"
        r"(?:beginning|start)\s+of\s+(?:next\s+)?(?:month|[A-Za-z]+)|"
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"(?:\s+\d{1,2})?(?:\s+\d{4})?)\s*$",
        re.IGNORECASE,
    )
    _DESCRIPTION_RE = re.compile(r"description\s*[:.=]\s*(.+)", re.IGNORECASE)
    _HOURS_PER_DAY_RE = re.compile(
        r"hours?\s*per\s*day\s*[:.=]\s*([\d.]+)", re.IGNORECASE
    )
    _CONFIDENCE_RE = re.compile(
        r"confidence\s*(?:levels?)?\s*[:.=]\s*([\d,\s]+)", re.IGNORECASE
    )

    # -- Auto-task trigger patterns (unnumbered/plain lists) ------------------
    _PLAIN_NUMBERED_RE = re.compile(
        r"^(\d+)\s*[.)\]]\s*(.+)", re.IGNORECASE
    )  # "1. foo", "2) bar", "3] baz"
    _BRACKET_NUMBERED_RE = re.compile(
        r"^\[(\d+)\]\s*(.+)", re.IGNORECASE
    )  # "[1] foo", "[2] bar"
    _PLAIN_BULLET_RE = re.compile(
        r"^[-*•]\s+(.+)", re.IGNORECASE
    )  # "- foo", "* bar", "• baz"
    _HASH_NUMBERED_RE = re.compile(r"^#\s*(\d+)\s+(.+)", re.IGNORECASE)  # "# 1 foo"

    # -- Inline property patterns (auto-task line scanning) -------------------
    _INLINE_BRACKET_SIZE_RE = re.compile(r"[\[(](XS|S|M|L|XL|XXL)[\])]", re.IGNORECASE)
    _INLINE_RANGE_RE = re.compile(
        r"(?:about\s+|around\s+|roughly\s+|~\s*)?(\d+(?:\.\d+)?)"
        r"\s*(?:[-–—]|to)\s*(\d+(?:\.\d+)?)"
        r"(?:\s+(hours?|days?|weeks?|h|d|w))?",
        re.IGNORECASE,
    )
    _INLINE_POINT_WITH_QUALIFIER_RE = re.compile(
        r"(?:about|around|roughly|~|approx(?:imately)?)\s+(\d+(?:\.\d+)?)"
        r"(?:\s+(hours?|days?|weeks?|h|d|w))?",
        re.IGNORECASE,
    )
    _INLINE_POINT_WITH_TILDE_RE = re.compile(
        r"(?:about|around|roughly|approx(?:imately)?)?\s*~\s*(\d+(?:\.\d+)?)"
        r"(?:\s+(hours?|days?|weeks?|h|d|w))?",
        re.IGNORECASE,
    )
    _INLINE_DEPENDS_RE = re.compile(r"depends?\s*(?:on)?\s+(.+)", re.IGNORECASE)
    _INLINE_FUZZY_SIZE_RE = re.compile(
        r"(?:probably|likely|assume|estimate[ds]?\s+(?:as\s+)?)"
        r"\s+(?:an?\s+)?(XS|S|M|L|XL|XXL)\b",
        re.IGNORECASE,
    )

    # -- Task header -----------------------------------------------------------
    _TASK_HEADER_RE = re.compile(r"task\s*(\d+)\s*[:.=]?\s*(.*)", re.IGNORECASE)

    # -- Resource header -------------------------------------------------------
    _RESOURCE_HEADER_RE = re.compile(r"resource\s*(\d+)\s*[:.=]?\s*(.*)", re.IGNORECASE)

    # -- Calendar header -------------------------------------------------------
    _CALENDAR_HEADER_RE = re.compile(r"calendar\s*[:.=]?\s*(.+)", re.IGNORECASE)
    _SPRINT_PLANNING_HEADER_RE = re.compile(
        r"sprint\s*planning\s*[:.=]?\s*(.*)",
        re.IGNORECASE,
    )
    _SPRINT_HISTORY_HEADER_RE = re.compile(
        r"sprint\s*history(?:\s+([^:]+))?\s*[:.=]?\s*(.*)",
        re.IGNORECASE,
    )
    _FUTURE_OVERRIDE_HEADER_RE = re.compile(
        r"future\s*sprint\s*override(?:\s+([^:]+))?\s*[:.=]?\s*(.*)",
        re.IGNORECASE,
    )

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
    _DATE_TOKEN_RE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{8}|\d{1,2}\s+[A-Za-z]{3,9}")
    _DATE_RANGE_RE = re.compile(
        r"(?P<start>\d{4}-\d{2}-\d{2}|\d{8}|\d{1,2}\s+[A-Za-z]{3,9})"
        r"\s*(?:to|[-–—])\s*"
        r"(?P<end>\d{4}-\d{2}-\d{2}|\d{8}|\d{1,2}\s+[A-Za-z]{3,9})",
        re.IGNORECASE,
    )

    # -- Calendar bullet patterns ----------------------------------------------
    _CAL_WORK_HOURS_RE = re.compile(
        r"work\s*hours?(?:\s*per\s*day)?\s*[:.=]?\s*([\d.]+)", re.IGNORECASE
    )
    _CAL_WORK_DAYS_RE = re.compile(r"work\s*days?\s*[:.=]?\s*([\d,\s]+)", re.IGNORECASE)
    _CAL_HOLIDAYS_RE = re.compile(r"holidays?\s*[:.=]?\s*(.+)", re.IGNORECASE)
    _SPRINT_LENGTH_RE = re.compile(
        r"sprint\s*length\s*(?:weeks?)?\s*[:.=]?\s*(\d+)",
        re.IGNORECASE,
    )
    _SPRINT_LENGTH_CADENCE_RE = re.compile(
        r"(\d+)\s*(?:-|\s*)weeks?\s*sprints?",
        re.IGNORECASE,
    )
    _CAPACITY_MODE_RE = re.compile(
        r"capacity\s*mode\s*[:.=]?\s*(story\s*points?|tasks?)",
        re.IGNORECASE,
    )
    _VELOCITY_MODEL_RE = re.compile(
        r"velocity\s*model\s*[:.=]?\s*(empirical|neg(?:ative)?[_\s-]*binomial)",
        re.IGNORECASE,
    )
    _PLANNING_CONFIDENCE_RE = re.compile(
        r"planning\s*confidence\s*(?:level)?\s*[:.=]?\s*([\d.]+%?)",
        re.IGNORECASE,
    )
    _REMOVED_WORK_RE = re.compile(
        r"removed\s*work\s*treatment\s*[:.=]?\s*(.+)",
        re.IGNORECASE,
    )
    _SPRINT_SICKNESS_ENABLED_RE = re.compile(
        r"sickness\s*(?:model)?\s*[:.=]?\s*(enabled|disabled|on|off|true|false|yes|no)",
        re.IGNORECASE,
    )
    _SPRINT_NO_SICKNESS_RE = re.compile(
        r"no\s*sickness",
        re.IGNORECASE,
    )
    _SPRINT_SICKNESS_TEAM_SIZE_RE = re.compile(
        r"sickness\s*team\s*size\s*[:.=]?\s*(\d+)",
        re.IGNORECASE,
    )
    _SPRINT_SICKNESS_PROB_RE = re.compile(
        r"sickness\s*prob(?:ability)?(?:\s*per\s*person\s*per\s*week)?\s*[:.=]?\s*([\d.]+%?)",
        re.IGNORECASE,
    )
    _SPRINT_SICKNESS_MU_RE = re.compile(
        r"sickness\s*duration\s*log\s*mu\s*[:.=]?\s*([\d.]+)",
        re.IGNORECASE,
    )
    _SPRINT_SICKNESS_SIGMA_RE = re.compile(
        r"sickness\s*duration\s*log\s*sigma\s*[:.=]?\s*([\d.]+)",
        re.IGNORECASE,
    )
    _OVERRIDE_SPRINT_NUMBER_RE = re.compile(
        r"sprint\s*(?:number)?\s*[:.=]?\s*(\d+)",
        re.IGNORECASE,
    )
    _OVERRIDE_START_DATE_RE = re.compile(
        r"start\s*date\s*[:.=]?\s*(\d{4}-\d{2}-\d{2})",
        re.IGNORECASE,
    )
    _OVERRIDE_HOLIDAY_FACTOR_RE = re.compile(
        r"holiday\s*factor\s*[:.=]?\s*([\d.]+%?)",
        re.IGNORECASE,
    )
    _OVERRIDE_CAPACITY_MULTIPLIER_RE = re.compile(
        r"capacity\s*multiplier\s*[:.=]?\s*([\d.]+)",
        re.IGNORECASE,
    )
    _OVERRIDE_NOTES_RE = re.compile(r"notes?\s*[:.=]?\s*(.+)", re.IGNORECASE)
    _HISTORY_COMPLETED_RE = re.compile(
        r"(?:completed|done|finished|delivered)\s*[:.=]?\s*([\d.]+)(?:\s+(points?|story\s*points?|tasks?))?",
        re.IGNORECASE,
    )
    _HISTORY_SPILLOVER_RE = re.compile(
        r"(?:spillover|carryover|rolled\s*over)\s*[:.=]?\s*([\d.]+)(?:\s+(points?|story\s*points?|tasks?))?",
        re.IGNORECASE,
    )
    _HISTORY_ADDED_RE = re.compile(
        r"(?:added|scope\s*added)\s*[:.=]?\s*([\d.]+)(?:\s+(points?|story\s*points?|tasks?))?",
        re.IGNORECASE,
    )
    _HISTORY_REMOVED_RE = re.compile(
        r"(?:removed|scope\s*removed)\s*[:.=]?\s*([\d.]+)(?:\s+(points?|story\s*points?|tasks?))?",
        re.IGNORECASE,
    )
    _HOLIDAY_FACTOR_RE = re.compile(
        r"(?:holiday\s*factor|capacity\s*(?:was\s*)?)\s*[:.=]?\s*([\d.]+%?)",
        re.IGNORECASE,
    )

    # -- Public API ------------------------------------------------------------

    def __init__(
        self,
        current_year: int | None = None,
        today: date | None = None,
    ) -> None:
        self.today = today if today is not None else date.today()
        self.current_year = (
            current_year if current_year is not None else self.today.year
        )

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
        current_sprint_history: ParsedSprintHistoryEntry | None = None
        current_future_override: ParsedFutureSprintOverride | None = None
        in_sprint_planning = False
        # Auto-task detection state
        auto_task_mode = False
        auto_task_counter = 1
        any_explicit_task_seen = False

        def _flush_section() -> None:
            nonlocal current_task, current_resource, current_calendar
            nonlocal current_sprint_history, current_future_override
            if current_task is not None:
                project.tasks.append(current_task)
                current_task = None
            if current_resource is not None:
                project.resources.append(current_resource)
                current_resource = None
            if current_calendar is not None:
                project.calendars.append(current_calendar)
                current_calendar = None
            if current_sprint_history is not None:
                if project.sprint_planning is None:
                    project.sprint_planning = ParsedSprintPlanning()
                project.sprint_planning.history.append(current_sprint_history)
                current_sprint_history = None
            if current_future_override is not None:
                if project.sprint_planning is None:
                    project.sprint_planning = ParsedSprintPlanning()
                if any(
                    (
                        current_future_override.sprint_number is not None,
                        current_future_override.start_date is not None,
                        current_future_override.holiday_factor is not None,
                        current_future_override.capacity_multiplier is not None,
                        current_future_override.notes is not None,
                    )
                ):
                    project.sprint_planning.future_sprint_overrides.append(
                        current_future_override
                    )
                current_future_override = None

        def _current_sprint_weeks() -> int | None:
            if project.sprint_planning is None:
                return None
            return project.sprint_planning.sprint_length_weeks

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            # Check for task header
            task_match = self._TASK_HEADER_RE.match(line)
            if task_match:
                _flush_section()
                any_explicit_task_seen = True
                task_num = int(task_match.group(1))
                inline_name = task_match.group(2).strip().rstrip(":.")
                current_task = ParsedTask(number=task_num)
                if inline_name:
                    current_task.name = inline_name
                continue

            # Check for resource header
            resource_match = self._RESOURCE_HEADER_RE.match(line)
            if resource_match:
                in_sprint_planning = False
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
                in_sprint_planning = False
                _flush_section()
                cal_id = calendar_match.group(1).strip().rstrip(":.")
                current_calendar = ParsedCalendar(id=cal_id)
                continue

            sprint_planning_match = self._SPRINT_PLANNING_HEADER_RE.match(line)
            if sprint_planning_match:
                _flush_section()
                if project.sprint_planning is None:
                    project.sprint_planning = ParsedSprintPlanning()
                in_sprint_planning = True
                continue

            sprint_history_match = self._SPRINT_HISTORY_HEADER_RE.match(line)
            if sprint_history_match:
                _flush_section()
                if project.sprint_planning is None:
                    project.sprint_planning = ParsedSprintPlanning()
                in_sprint_planning = False
                sprint_id = (
                    sprint_history_match.group(1)
                    or sprint_history_match.group(2)
                    or f"SPR-{len(project.sprint_planning.history) + 1:03d}"
                )
                current_sprint_history = ParsedSprintHistoryEntry(
                    sprint_id=sprint_id.strip().rstrip(":."),
                )
                continue

            future_override_match = self._FUTURE_OVERRIDE_HEADER_RE.match(line)
            if future_override_match:
                _flush_section()
                if project.sprint_planning is None:
                    project.sprint_planning = ParsedSprintPlanning()
                in_sprint_planning = False
                locator = (
                    (
                        future_override_match.group(1)
                        or future_override_match.group(2)
                        or ""
                    )
                    .strip()
                    .rstrip(";:.")
                )
                current_future_override = ParsedFutureSprintOverride()
                if locator.isdigit():
                    current_future_override.sprint_number = int(locator)
                elif self._ISO_DATE_RE.fullmatch(locator):
                    current_future_override.start_date = locator
                continue

            # Auto-task mode: decide whether a line is a continuation,
            # a new auto-task, or ends the current auto-task section.
            if auto_task_mode and current_task is not None:
                is_indented = raw_line != raw_line.lstrip() and bool(line)
                if is_indented:
                    # Indented continuation → treat as task bullet
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
                    # Unmatched continuation → name or description
                    if not current_task.name:
                        current_task.name = bullet_text
                    elif not current_task.description:
                        current_task.description = bullet_text
                    continue
                # Not indented: check for a new auto-task item
                new_auto = self._try_start_auto_task(
                    line,
                    current_task,
                    auto_task_counter,
                    _current_sprint_weeks(),
                    project.tasks,
                    _flush_section,
                )
                if new_auto is not None:
                    current_task = new_auto
                    if new_auto.number >= auto_task_counter:
                        auto_task_counter = new_auto.number + 1
                    else:
                        auto_task_counter += 1
                    continue
                # Not indented and not a list item → close auto-task
                _flush_section()
                current_task = None
                auto_task_mode = False
                # Fall through to normal processing

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
                if self._try_parse_depends(bullet_text, current_task, project.tasks):
                    continue
                if self._try_parse_estimate(bullet_text, current_task):
                    continue

                before_state = (
                    current_task.name,
                    current_task.t_shirt_size,
                    current_task.low_estimate,
                    current_task.expected_estimate,
                    current_task.high_estimate,
                    tuple(current_task.dependency_refs),
                )
                self._extract_inline_properties(
                    bullet_text,
                    current_task,
                    sprint_weeks=_current_sprint_weeks(),
                    known_tasks=project.tasks,
                    assign_name=not bool(current_task.name),
                )
                after_state = (
                    current_task.name,
                    current_task.t_shirt_size,
                    current_task.low_estimate,
                    current_task.expected_estimate,
                    current_task.high_estimate,
                    tuple(current_task.dependency_refs),
                )
                if after_state != before_state:
                    if (
                        current_task.description is None
                        and current_task.name
                        and current_task.name != bullet_text
                        and before_state[0]
                    ):
                        current_task.description = bullet_text
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

            if current_sprint_history is not None:
                bullet_text = re.sub(r"^[-*•]\s*", "", line).strip()
                if not bullet_text:
                    continue
                self._try_parse_sprint_history_bullet(
                    bullet_text,
                    current_sprint_history,
                    project.sprint_planning,
                )
                continue

            if current_future_override is not None:
                bullet_text = re.sub(r"^[-*•]\s*", "", line).strip()
                if not bullet_text:
                    continue
                self._try_parse_future_override_bullet(
                    bullet_text,
                    current_future_override,
                )
                continue

            if in_sprint_planning and project.sprint_planning is not None:
                bullet_text = re.sub(r"^[-*•]\s*", "", line).strip()
                if not bullet_text:
                    continue
                self._try_parse_sprint_planning_bullet(
                    bullet_text, project.sprint_planning
                )
                continue

            # Auto-task detection: plain numbered/bullet/bracket lists
            if not any_explicit_task_seen and not self._is_section_open(
                current_resource,
                current_calendar,
                current_sprint_history,
                current_future_override,
                in_sprint_planning,
            ):
                auto_task_started = self._try_start_auto_task(
                    line,
                    current_task,
                    auto_task_counter,
                    _current_sprint_weeks(),
                    project.tasks,
                    _flush_section,
                )
                if auto_task_started is not None:
                    current_task = auto_task_started
                    auto_task_mode = True
                    if auto_task_started.number >= auto_task_counter:
                        auto_task_counter = auto_task_started.number + 1
                    else:
                        auto_task_counter += 1
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
            elif task.low_estimate is not None:
                lines.append("    estimate:")
                lines.append(f"      low: {self._fmt_num(task.low_estimate)}")
                if task.expected_estimate is not None:
                    lines.append(
                        f"      expected:" f" {self._fmt_num(task.expected_estimate)}"
                    )
                if task.high_estimate is not None:
                    lines.append(f"      high: {self._fmt_num(task.high_estimate)}")
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

        if project.sprint_planning is not None and (
            project.sprint_planning.history
            or project.sprint_planning.future_sprint_overrides
            or project.sprint_planning.velocity_model is not None
            or project.sprint_planning.removed_work_treatment is not None
            or project.sprint_planning.planning_confidence_level is not None
            or project.sprint_planning.sickness_enabled is not None
            or project.sprint_planning.sickness_team_size is not None
            or project.sprint_planning.sickness_probability_per_person_per_week
            is not None
            or project.sprint_planning.sickness_duration_log_mu is not None
            or project.sprint_planning.sickness_duration_log_sigma is not None
        ):
            lines.append("")
            lines.append("sprint_planning:")
            lines.append("  enabled: true")
            lines.append(
                f"  sprint_length_weeks: {project.sprint_planning.sprint_length_weeks}"
            )
            lines.append(f'  capacity_mode: "{project.sprint_planning.capacity_mode}"')
            if project.sprint_planning.planning_confidence_level is not None:
                lines.append(
                    "  planning_confidence_level: "
                    f"{self._fmt_num(project.sprint_planning.planning_confidence_level)}"
                )
            if project.sprint_planning.removed_work_treatment is not None:
                lines.append(
                    "  removed_work_treatment: "
                    f'"{project.sprint_planning.removed_work_treatment}"'
                )
            if project.sprint_planning.velocity_model is not None:
                lines.append(
                    f'  velocity_model: "{project.sprint_planning.velocity_model}"'
                )
            sickness_fields = [
                project.sprint_planning.sickness_enabled is not None,
                project.sprint_planning.sickness_team_size is not None,
                project.sprint_planning.sickness_probability_per_person_per_week
                is not None,
                project.sprint_planning.sickness_duration_log_mu is not None,
                project.sprint_planning.sickness_duration_log_sigma is not None,
            ]
            if any(sickness_fields):
                lines.append("  sickness:")
                if project.sprint_planning.sickness_enabled is not None:
                    lines.append(
                        "    enabled: "
                        f"{str(project.sprint_planning.sickness_enabled).lower()}"
                    )
                if project.sprint_planning.sickness_team_size is not None:
                    lines.append(
                        "    team_size: "
                        f"{project.sprint_planning.sickness_team_size}"
                    )
                if (
                    project.sprint_planning.sickness_probability_per_person_per_week
                    is not None
                ):
                    lines.append(
                        "    probability_per_person_per_week: "
                        f"{self._fmt_num(project.sprint_planning.sickness_probability_per_person_per_week)}"
                    )
                if project.sprint_planning.sickness_duration_log_mu is not None:
                    lines.append(
                        "    duration_log_mu: "
                        f"{self._fmt_num(project.sprint_planning.sickness_duration_log_mu)}"
                    )
                if project.sprint_planning.sickness_duration_log_sigma is not None:
                    lines.append(
                        "    duration_log_sigma: "
                        f"{self._fmt_num(project.sprint_planning.sickness_duration_log_sigma)}"
                    )
            if project.sprint_planning.future_sprint_overrides:
                lines.append("  future_sprint_overrides:")
                for override in project.sprint_planning.future_sprint_overrides:
                    lines.append("    -")
                    if override.sprint_number is not None:
                        lines.append(f"      sprint_number: {override.sprint_number}")
                    if override.start_date is not None:
                        lines.append(f'      start_date: "{override.start_date}"')
                    if override.holiday_factor is not None:
                        lines.append(
                            "      holiday_factor: "
                            f"{self._fmt_num(override.holiday_factor)}"
                        )
                    if override.capacity_multiplier is not None:
                        lines.append(
                            "      capacity_multiplier: "
                            f"{self._fmt_num(override.capacity_multiplier)}"
                        )
                    if override.notes:
                        lines.append(f"      notes: {self._yaml_str(override.notes)}")
            lines.append("  history:")
            for entry in project.sprint_planning.history:
                lines.append(f'    - sprint_id: "{entry.sprint_id}"')
                if entry.completed_story_points is not None:
                    lines.append(
                        "      completed_story_points: "
                        f"{self._fmt_num(entry.completed_story_points)}"
                    )
                if entry.completed_tasks is not None:
                    lines.append(f"      completed_tasks: {entry.completed_tasks}")
                if entry.spillover_story_points is not None:
                    lines.append(
                        "      spillover_story_points: "
                        f"{self._fmt_num(entry.spillover_story_points)}"
                    )
                if entry.spillover_tasks is not None:
                    lines.append(f"      spillover_tasks: {entry.spillover_tasks}")
                if entry.added_story_points is not None:
                    lines.append(
                        "      added_story_points: "
                        f"{self._fmt_num(entry.added_story_points)}"
                    )
                if entry.added_tasks is not None:
                    lines.append(f"      added_tasks: {entry.added_tasks}")
                if entry.removed_story_points is not None:
                    lines.append(
                        "      removed_story_points: "
                        f"{self._fmt_num(entry.removed_story_points)}"
                    )
                if entry.removed_tasks is not None:
                    lines.append(f"      removed_tasks: {entry.removed_tasks}")
                if entry.holiday_factor is not None:
                    lines.append(
                        f"      holiday_factor: {self._fmt_num(entry.holiday_factor)}"
                    )

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

    @staticmethod
    def _is_section_open(
        current_resource: ParsedResource | None,
        current_calendar: ParsedCalendar | None,
        current_sprint_history: ParsedSprintHistoryEntry | None,
        current_future_override: ParsedFutureSprintOverride | None,
        in_sprint_planning: bool,
    ) -> bool:
        """Return True if a non-task section is currently open."""
        return (
            current_resource is not None
            or current_calendar is not None
            or current_sprint_history is not None
            or current_future_override is not None
            or in_sprint_planning
        )

    def _try_start_auto_task(
        self,
        line: str,
        current_task: ParsedTask | None,
        auto_task_counter: int,
        sprint_weeks: int | None,
        known_tasks: list[ParsedTask],
        flush: object,
    ) -> ParsedTask | None:
        """Try to start an auto-detected task from a plain list line.

        Returns a new ParsedTask if the line matches an auto-task pattern,
        or None if it does not match.
        """
        # Bracket numbered: [1] foo
        m = self._BRACKET_NUMBERED_RE.match(line)
        if m:
            if current_task is not None:
                flush()  # type: ignore[operator]
            task_num = int(m.group(1))
            name = m.group(2).strip()
            task = ParsedTask(number=task_num, name=name)
            self._extract_inline_properties(
                name,
                task,
                sprint_weeks=sprint_weeks,
                known_tasks=known_tasks,
            )
            return task

        # Plain numbered: 1. foo, 2) bar
        m = self._PLAIN_NUMBERED_RE.match(line)
        if m:
            if current_task is not None:
                flush()  # type: ignore[operator]
            task_num = int(m.group(1))
            name = m.group(2).strip()
            task = ParsedTask(number=task_num, name=name)
            self._extract_inline_properties(
                name,
                task,
                sprint_weeks=sprint_weeks,
                known_tasks=known_tasks,
            )
            return task

        # Hash numbered: # 1 foo
        m = self._HASH_NUMBERED_RE.match(line)
        if m:
            if current_task is not None:
                flush()  # type: ignore[operator]
            task_num = int(m.group(1))
            name = m.group(2).strip()
            task = ParsedTask(number=task_num, name=name)
            self._extract_inline_properties(
                name,
                task,
                sprint_weeks=sprint_weeks,
                known_tasks=known_tasks,
            )
            return task

        # Plain bullet: - foo, * bar, • baz
        m = self._PLAIN_BULLET_RE.match(line)
        if m:
            if current_task is not None:
                flush()  # type: ignore[operator]
            name = m.group(1).strip()
            task = ParsedTask(number=auto_task_counter, name=name)
            self._extract_inline_properties(
                name,
                task,
                sprint_weeks=sprint_weeks,
                known_tasks=known_tasks,
            )
            return task

        return None

    def _extract_inline_properties(
        self,
        text: str,
        task: ParsedTask,
        sprint_weeks: int | None = None,
        known_tasks: list[ParsedTask] | None = None,
        assign_name: bool = True,
    ) -> None:
        """Extract inline size, estimate, or dependency from a task name line.

        Scans the text for bracketed/parenthesized size tokens, fuzzy size
        hints, inline estimate ranges, and dependency phrases.
        Modifies the task in-place and strips matched tokens from the name.
        """
        remaining = text

        # Bracketed/parenthesized size: [XL], (M)
        m = self._INLINE_BRACKET_SIZE_RE.search(remaining)
        if m and task.t_shirt_size is None:
            raw = m.group(1).upper()
            normalized = _SIZE_ALIASES.get(raw)
            if normalized and normalized in _VALID_SIZES:
                task.t_shirt_size = normalized
                remaining = (remaining[: m.start()] + remaining[m.end() :]).strip()

        # Fuzzy size hint: "probably an M", "likely L", "assume S"
        if task.t_shirt_size is None:
            m = self._INLINE_FUZZY_SIZE_RE.search(remaining)
            if m:
                raw = m.group(1).upper()
                normalized = _SIZE_ALIASES.get(raw)
                if normalized and normalized in _VALID_SIZES:
                    task.t_shirt_size = normalized
                    remaining = (remaining[: m.start()] + remaining[m.end() :]).strip()

        # Inline estimate range or qualified point estimate.
        if task.low_estimate is None:
            matched_slice = self._try_parse_inline_estimate(remaining, task)
            if matched_slice is not None:
                remaining = (
                    remaining[: matched_slice[0]] + remaining[matched_slice[1] :]
                ).strip()

        if task.t_shirt_size is None and task.low_estimate is None:
            matched_slice = self._try_parse_fuzzy_duration(
                remaining,
                task,
                sprint_weeks=sprint_weeks,
            )
            if matched_slice is not None:
                remaining = (
                    remaining[: matched_slice[0]] + remaining[matched_slice[1] :]
                ).strip()

        # Inline dependency: "depends on Task 1"
        m = self._INLINE_DEPENDS_RE.search(remaining)
        if m and not task.dependency_refs:
            dep_text = m.group(1)
            refs = self._resolve_dependency_refs(dep_text, known_tasks or [])
            if refs:
                task.dependency_refs = refs
                remaining = (remaining[: m.start()] + remaining[m.end() :]).strip()

        # Clean up the task name: remove extracted tokens
        cleaned = remaining.strip().rstrip(".,;:- ")
        if cleaned and assign_name:
            task.name = cleaned

    def _try_parse_inline_estimate(
        self,
        text: str,
        task: ParsedTask,
    ) -> tuple[int, int] | None:
        """Parse an inline range or qualified point estimate from task text."""
        range_match = self._INLINE_RANGE_RE.search(text)
        if range_match is not None:
            low = float(range_match.group(1))
            high = float(range_match.group(2))
            unit_token = range_match.group(3)
            if low < high and not self._looks_like_date_fragment(low, high, unit_token):
                task.low_estimate = low
                task.expected_estimate = (low + high) / 2
                task.high_estimate = high
                if unit_token:
                    task.estimate_unit = self._normalize_unit(unit_token)
                return (range_match.start(), range_match.end())

        tilde_match = self._INLINE_POINT_WITH_TILDE_RE.search(text)
        if tilde_match is not None:
            expected = float(tilde_match.group(1))
            task.low_estimate = round(expected * 0.75, 1)
            task.expected_estimate = expected
            task.high_estimate = round(expected * 2.5, 1)
            if tilde_match.group(2):
                task.estimate_unit = self._normalize_unit(tilde_match.group(2))
            return (tilde_match.start(), tilde_match.end())

        point_match = self._INLINE_POINT_WITH_QUALIFIER_RE.search(text)
        if point_match is not None:
            expected = float(point_match.group(1))
            task.low_estimate = round(expected * 0.7, 1)
            task.expected_estimate = expected
            task.high_estimate = round(expected * 1.8, 1)
            if point_match.group(2):
                task.estimate_unit = self._normalize_unit(point_match.group(2))
            return (point_match.start(), point_match.end())

        return None

    def _try_parse_fuzzy_duration(
        self,
        text: str,
        task: ParsedTask,
        sprint_weeks: int | None = None,
    ) -> tuple[int, int] | None:
        """Parse fuzzy natural-language duration phrases into T-shirt sizes."""
        sprint_match = re.search(r"\ba\s+sprint\b|\babout\s+a\s+sprint\b", text, re.IGNORECASE)
        if sprint_match is not None:
            task.t_shirt_size = self._t_shirt_size_for_sprint_weeks(sprint_weeks or 2)
            return (sprint_match.start(), sprint_match.end())

        for pattern, size in _FUZZY_DURATION_PATTERNS:
            match = pattern.search(text)
            if match is not None:
                task.t_shirt_size = size
                return (match.start(), match.end())
        return None

    @staticmethod
    def _t_shirt_size_for_sprint_weeks(sprint_weeks: int) -> str:
        """Map sprint cadence in weeks to a default T-shirt size."""
        if sprint_weeks <= 1:
            return "M"
        if sprint_weeks <= 3:
            return "L"
        if sprint_weeks <= 6:
            return "XL"
        return "XXL"

    @staticmethod
    def _looks_like_date_fragment(
        low: float,
        high: float,
        unit_token: str | None,
    ) -> bool:
        """Reject year-month style fragments such as 2026-04 as estimates."""
        if unit_token is not None:
            return False
        return low >= 1900 and low == int(low) and 1 <= high <= 31 and high == int(high)

    @staticmethod
    def _normalize_unit(unit_str: str) -> str:
        """Normalize a time unit string to canonical form."""
        u = unit_str.lower()
        if u.startswith("hour") or u == "h":
            return "hours"
        if u.startswith("week") or u == "w":
            return "weeks"
        return "days"

    def _try_parse_project_metadata(self, line: str, project: ParsedProject) -> bool:
        m = self._PROJECT_NAME_RE.match(line)
        if m:
            project.name = m.group(1).strip()
            return True

        m = self._START_DATE_RE.match(line)
        if m:
            project.start_date = m.group(1)
            return True

        m = self._RELATIVE_DATE_RE.match(line)
        if m:
            resolved = self._resolve_relative_date(m.group(1), self.today)
            if resolved is not None:
                project.start_date = resolved
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

    def _resolve_relative_date(self, phrase: str, today: date) -> str | None:
        """Resolve a relative start-date phrase to an ISO date string."""
        normalized = " ".join(phrase.strip().lower().split())
        if not normalized:
            return None

        weekday_names = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
        }
        if normalized.startswith("next "):
            weekday_name = normalized.removeprefix("next ").strip()
            if weekday_name in weekday_names:
                target_weekday = weekday_names[weekday_name]
                days_ahead = (target_weekday - today.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7
                return (today + timedelta(days=days_ahead)).isoformat()

        in_match = re.fullmatch(r"in\s+(\d+)\s+(days?|weeks?)", normalized)
        if in_match:
            magnitude = int(in_match.group(1))
            unit = in_match.group(2)
            if unit.startswith("week"):
                return (today + timedelta(weeks=magnitude)).isoformat()
            return (today + timedelta(days=magnitude)).isoformat()

        if normalized in {"beginning of next month", "start of next month"}:
            year = today.year + (1 if today.month == 12 else 0)
            next_month = 1 if today.month == 12 else today.month + 1
            return date(year, next_month, 1).isoformat()

        month_aliases = {
            "jan": 1,
            "january": 1,
            "feb": 2,
            "february": 2,
            "mar": 3,
            "march": 3,
            "apr": 4,
            "april": 4,
            "may": 5,
            "jun": 6,
            "june": 6,
            "jul": 7,
            "july": 7,
            "aug": 8,
            "august": 8,
            "sep": 9,
            "september": 9,
            "oct": 10,
            "october": 10,
            "nov": 11,
            "november": 11,
            "dec": 12,
            "december": 12,
        }

        beginning_match = re.fullmatch(
            r"(?:beginning|start) of (?:(next) )?([a-z]+)",
            normalized,
        )
        if beginning_match:
            is_next = beginning_match.group(1) is not None
            month_name = beginning_match.group(2)
            month_number = month_aliases.get(month_name)
            if month_number is not None:
                year = today.year
                if is_next or month_number < today.month:
                    year += 1
                return date(year, month_number, 1).isoformat()

        month_year_match = re.fullmatch(
            r"([a-z]+)(?:\s+(\d{1,2}))?(?:\s+(\d{4}))?",
            normalized,
        )
        if month_year_match:
            month_name = month_year_match.group(1)
            second_token = month_year_match.group(2)
            year_token = month_year_match.group(3)
            month_number = month_aliases.get(month_name)
            if month_number is not None:
                day_token: str | None = second_token
                if second_token is not None and len(second_token) == 4:
                    day_token = None
                    year_token = second_token
                day = int(day_token) if day_token is not None else 1
                year = int(year_token) if year_token is not None else today.year
                return date(year, month_number, day).isoformat()

        return None

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

    def _try_parse_depends(
        self,
        text: str,
        task: ParsedTask,
        known_tasks: list[ParsedTask] | None = None,
    ) -> bool:
        m = self._DEPENDS_RE.match(text)
        if m:
            dep_text = m.group(1)
            refs = self._resolve_dependency_refs(dep_text, known_tasks or [])
            task.dependency_refs = refs
            return True
        return False

    def _resolve_dependency_refs(
        self,
        dep_text: str,
        known_tasks: list[ParsedTask],
    ) -> list[str]:
        """Resolve dependency references from explicit task numbers or prior task names."""
        refs = self._TASK_REF_RE.findall(dep_text)
        if not refs:
            refs = re.findall(r"(\d+)", dep_text)
        if refs:
            return [str(int(ref)) for ref in refs]

        return self._resolve_task_ref_by_name(dep_text, known_tasks)

    def _resolve_task_ref_by_name(
        self,
        phrase: str,
        known_tasks: list[ParsedTask],
    ) -> list[str]:
        """Match a natural-language dependency phrase to previously parsed tasks."""
        phrase_tokens = self._reference_tokens(phrase)
        if not phrase_tokens:
            return []

        matches: list[str] = []
        for known_task in known_tasks:
            task_tokens = self._reference_tokens(known_task.name)
            overlap = phrase_tokens & task_tokens
            if len(overlap) >= 2:
                matches.append(str(known_task.number))
                continue

            if overlap and any(token in _REFERENCE_TOKEN_ALIASES for token in overlap):
                matches.append(str(known_task.number))

        return matches

    def _reference_tokens(self, text: str) -> set[str]:
        """Return normalized reference tokens with domain alias expansion."""
        base_tokens = {
            token
            for token in re.findall(r"[a-z0-9]+", text.lower())
            if token not in _GENERIC_REFERENCE_TOKENS
        }
        expanded_tokens = set(base_tokens)
        for token in base_tokens:
            expanded_tokens.update(_REFERENCE_TOKEN_ALIASES.get(token, {token}))
        return expanded_tokens

    def _try_parse_estimate(self, text: str, task: ParsedTask) -> bool:
        m = self._ESTIMATE_RE.match(text)
        if m:
            task.low_estimate = float(m.group(1))
            task.expected_estimate = float(m.group(2))
            task.high_estimate = float(m.group(3))
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
            dates = self._extract_dates(m.group(1))
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
            dates = self._extract_dates(m.group(1))
            if dates:
                calendar.holidays.extend(dates)
            return True

        return False

    def _try_parse_sprint_planning_bullet(
        self,
        text: str,
        sprint_planning: ParsedSprintPlanning,
    ) -> bool:
        """Parse one sprint-planning configuration bullet."""
        m = self._SPRINT_LENGTH_RE.match(text)
        if m:
            sprint_planning.sprint_length_weeks = int(m.group(1))
            return True

        m = self._SPRINT_LENGTH_CADENCE_RE.search(text)
        if m:
            sprint_planning.sprint_length_weeks = int(m.group(1))
            return True

        m = self._CAPACITY_MODE_RE.match(text)
        if m:
            normalized = m.group(1).lower().replace(" ", "_")
            sprint_planning.capacity_mode = (
                "story_points" if normalized.startswith("story") else "tasks"
            )
            return True

        m = self._PLANNING_CONFIDENCE_RE.match(text)
        if m:
            sprint_planning.planning_confidence_level = self._parse_probability_token(
                m.group(1)
            )
            return True

        m = self._VELOCITY_MODEL_RE.match(text)
        if m:
            token = m.group(1).lower().replace(" ", "_").replace("-", "_")
            if "binomial" in token:
                sprint_planning.velocity_model = "neg_binomial"
            else:
                sprint_planning.velocity_model = "empirical"
            return True

        m = self._REMOVED_WORK_RE.match(text)
        if m:
            normalized = self._normalize_removed_work_treatment(m.group(1).strip())
            if normalized is not None:
                sprint_planning.removed_work_treatment = normalized
                return True

        m = self._SPRINT_SICKNESS_ENABLED_RE.match(text)
        if m:
            token = m.group(1).strip().lower()
            sprint_planning.sickness_enabled = token in {
                "enabled",
                "on",
                "true",
                "yes",
            }
            return True

        if self._SPRINT_NO_SICKNESS_RE.search(text):
            sprint_planning.sickness_enabled = False
            return True

        m = self._SPRINT_SICKNESS_TEAM_SIZE_RE.match(text)
        if m:
            sprint_planning.sickness_team_size = int(m.group(1))
            return True

        m = self._SPRINT_SICKNESS_PROB_RE.match(text)
        if m:
            sprint_planning.sickness_probability_per_person_per_week = (
                self._parse_probability_token(m.group(1))
            )
            return True

        m = self._SPRINT_SICKNESS_MU_RE.match(text)
        if m:
            sprint_planning.sickness_duration_log_mu = float(m.group(1))
            return True

        m = self._SPRINT_SICKNESS_SIGMA_RE.match(text)
        if m:
            sprint_planning.sickness_duration_log_sigma = float(m.group(1))
            return True

        return False

    def _try_parse_future_override_bullet(
        self,
        text: str,
        override: ParsedFutureSprintOverride,
    ) -> bool:
        """Parse one future sprint override bullet."""
        m = self._OVERRIDE_SPRINT_NUMBER_RE.match(text)
        if m:
            override.sprint_number = int(m.group(1))
            return True

        m = self._OVERRIDE_START_DATE_RE.match(text)
        if m:
            override.start_date = m.group(1)
            return True

        m = self._OVERRIDE_HOLIDAY_FACTOR_RE.match(text)
        if m:
            override.holiday_factor = self._parse_probability_token(m.group(1))
            return True

        m = self._OVERRIDE_CAPACITY_MULTIPLIER_RE.match(text)
        if m:
            override.capacity_multiplier = float(m.group(1))
            return True

        m = self._OVERRIDE_NOTES_RE.match(text)
        if m:
            override.notes = m.group(1).strip()
            return True

        return False

    @staticmethod
    def _normalize_removed_work_treatment(value: str) -> str | None:
        """Normalize human-friendly removed-work treatment aliases."""
        token = value.strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "churn_only": "churn_only",
            "churn": "churn_only",
            "churnonly": "churn_only",
            "reduce_backlog": "reduce_backlog",
            "reduce": "reduce_backlog",
            "backlog": "reduce_backlog",
            "reducebacklog": "reduce_backlog",
        }
        return aliases.get(token)

    def _try_parse_sprint_history_bullet(
        self,
        text: str,
        entry: ParsedSprintHistoryEntry,
        sprint_planning: ParsedSprintPlanning | None,
    ) -> bool:
        """Parse one sprint-history bullet using canonical or synonym labels."""
        m = self._HISTORY_COMPLETED_RE.match(text)
        if m:
            self._assign_history_value(
                entry,
                field_prefix="completed",
                value=float(m.group(1)),
                unit_token=m.group(2),
                sprint_planning=sprint_planning,
            )
            return True

        m = self._HISTORY_SPILLOVER_RE.match(text)
        if m:
            self._assign_history_value(
                entry,
                field_prefix="spillover",
                value=float(m.group(1)),
                unit_token=m.group(2),
                sprint_planning=sprint_planning,
            )
            return True

        m = self._HISTORY_ADDED_RE.match(text)
        if m:
            self._assign_history_value(
                entry,
                field_prefix="added",
                value=float(m.group(1)),
                unit_token=m.group(2),
                sprint_planning=sprint_planning,
            )
            return True

        m = self._HISTORY_REMOVED_RE.match(text)
        if m:
            self._assign_history_value(
                entry,
                field_prefix="removed",
                value=float(m.group(1)),
                unit_token=m.group(2),
                sprint_planning=sprint_planning,
            )
            return True

        m = self._HOLIDAY_FACTOR_RE.match(text)
        if m:
            entry.holiday_factor = self._parse_probability_token(m.group(1))
            return True

        return False

    def _assign_history_value(
        self,
        entry: ParsedSprintHistoryEntry,
        field_prefix: str,
        value: float,
        unit_token: str | None,
        sprint_planning: ParsedSprintPlanning | None,
    ) -> None:
        """Assign a history field using explicit or inferred units."""
        inferred_mode = (
            sprint_planning.capacity_mode
            if sprint_planning is not None
            else "story_points"
        )
        token = (unit_token or "").lower().replace(" ", "")
        uses_tasks = token.startswith("task") or inferred_mode == "tasks"

        if field_prefix == "completed":
            if uses_tasks:
                entry.completed_tasks = int(value)
            else:
                entry.completed_story_points = value
            return

        if uses_tasks:
            setattr(entry, f"{field_prefix}_tasks", int(value))
        else:
            setattr(entry, f"{field_prefix}_story_points", value)

    @staticmethod
    def _parse_probability_token(token: str) -> float:
        """Parse decimal or percent tokens into 0..1 multipliers."""
        cleaned = token.strip()
        if cleaned.endswith("%"):
            return float(cleaned[:-1]) / 100.0
        value = float(cleaned)
        if value > 1.0:
            return value / 100.0
        return value

    def _extract_dates(self, text: str) -> list[str]:
        """Extract single dates and expand date ranges into ISO dates."""
        dates: list[str] = []
        consumed = [False] * len(text)

        for match in self._DATE_RANGE_RE.finditer(text):
            start_date = self._parse_date_token(match.group("start"))
            end_date = self._parse_date_token(match.group("end"))
            if start_date is None or end_date is None:
                continue

            range_start, range_end = sorted((start_date, end_date))
            for offset in range((range_end - range_start).days + 1):
                self._append_unique_date(
                    dates, (range_start + timedelta(days=offset)).isoformat()
                )

            for index in range(match.start(), match.end()):
                consumed[index] = True

        remaining_text = "".join(
            char if not consumed[index] else " " for index, char in enumerate(text)
        )

        for match in self._DATE_TOKEN_RE.finditer(remaining_text):
            parsed_date = self._parse_date_token(match.group(0))
            if parsed_date is not None:
                self._append_unique_date(dates, parsed_date.isoformat())

        return dates

    def _parse_date_token(self, token: str) -> date | None:
        """Parse a supported natural-language date token."""
        cleaned = " ".join(token.strip().split())
        if not cleaned:
            return None

        for fmt in ("%Y-%m-%d", "%Y%m%d"):
            try:
                return datetime.strptime(cleaned, fmt).date()
            except ValueError:
                pass

        normalized = cleaned.title()
        for fmt in ("%d %b %Y", "%d %B %Y"):
            try:
                return datetime.strptime(
                    f"{normalized} {self.current_year}", fmt
                ).date()
            except ValueError:
                pass

        return None

    @staticmethod
    def _append_unique_date(dates: list[str], value: str) -> None:
        """Append a date string once while preserving order."""
        if value not in dates:
            dates.append(value)

    @staticmethod
    def _yaml_str(s: str) -> str:
        """Safely quote a string for use in YAML output."""
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    @staticmethod
    def _fmt_num(n: float) -> str:
        """Format a number, dropping .0 from integers."""
        return str(int(n)) if n == int(n) else str(n)
