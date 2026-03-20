"""Data models for projects, tasks, and risks."""

from datetime import date
from enum import Enum
from typing import Any, List, Optional

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from mcprojsim.config import (
    DEFAULT_CONFIDENCE_LEVELS,
    DEFAULT_PROBABILITY_GREEN_THRESHOLD,
    DEFAULT_PROBABILITY_RED_THRESHOLD,
    DEFAULT_STORY_POINT_VALUES,
    DEFAULT_UNCERTAINTY_FACTOR_LEVELS,
    EffortUnit,
)


class DistributionType(str, Enum):
    """Types of probability distributions."""

    TRIANGULAR = "triangular"
    LOGNORMAL = "lognormal"


class ImpactType(str, Enum):
    """Types of risk impact."""

    PERCENTAGE = "percentage"
    ABSOLUTE = "absolute"


class TaskEstimate(BaseModel):
    """Task effort estimate with distribution parameters."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    distribution: DistributionType | None = Field(default=None)
    low: Optional[float] = Field(
        default=None,
        ge=0,
        validation_alias=AliasChoices("low", "min"),
    )
    expected: Optional[float] = Field(
        default=None,
        gt=0,
        validation_alias=AliasChoices("expected", "most_likely"),
    )
    high: Optional[float] = Field(
        default=None,
        ge=0,
        validation_alias=AliasChoices("high", "max"),
    )
    t_shirt_size: Optional[str] = Field(default=None)
    story_points: Optional[int] = Field(default=None, gt=0)
    unit: Optional[EffortUnit] = Field(default=None)

    @model_validator(mode="after")
    def validate_distribution(self) -> "TaskEstimate":
        """Validate distribution parameters."""
        symbolic_modes = [
            self.t_shirt_size is not None,
            self.story_points is not None,
        ]

        if sum(symbolic_modes) > 1:
            raise ValueError(
                "Only one symbolic estimate may be specified: "
                "choose either 't_shirt_size' or 'story_points'"
            )

        # If a symbolic estimate is specified, skip numeric validation.
        # The actual values will be populated from config during simulation.
        # Unit must NOT be set by the user; it comes from config.
        if self.t_shirt_size is not None:
            if "unit" in self.model_fields_set:
                raise ValueError(
                    "T-shirt size estimates must not specify 'unit' in the project file. "
                    "The unit is defined in the configuration."
                )
            return self

        if self.story_points is not None:
            allowed_story_points = set(DEFAULT_STORY_POINT_VALUES.keys())
            if self.story_points not in allowed_story_points:
                allowed = ", ".join(
                    str(value) for value in sorted(allowed_story_points)
                )
                raise ValueError(
                    f"Story Points must be one of: {allowed}; got {self.story_points}"
                )

            if "unit" in self.model_fields_set:
                raise ValueError(
                    "Story Point estimates must not specify 'unit' in the project file. "
                    "The unit is defined in the configuration."
                )
            return self

        # For explicit estimates, expected is required
        if self.expected is None:
            raise ValueError(
                "Either 't_shirt_size', 'story_points', or 'expected' must be specified"
            )

        # Default unit for explicit estimates is hours
        if self.unit is None:
            self.unit = EffortUnit.HOURS

        if self.low is None or self.high is None:
            raise ValueError("Explicit estimates require low, expected, and high")
        if not (self.low <= self.expected <= self.high):
            raise ValueError(
                f"Must satisfy low <= expected <= high, "
                f"got {self.low} <= {self.expected} <= {self.high}"
            )
        if self.distribution == DistributionType.LOGNORMAL and not (
            self.low < self.expected < self.high
        ):
            raise ValueError("Lognormal distribution requires low < expected < high")
        return self

    def validate_effective_distribution(
        self, distribution: DistributionType
    ) -> "TaskEstimate":
        """Validate range semantics for the effective distribution in use."""
        if self.t_shirt_size is not None or self.story_points is not None:
            return self
        if (
            distribution == DistributionType.LOGNORMAL
            and self.low is not None
            and self.expected is not None
            and self.high is not None
            and not (self.low < self.expected < self.high)
        ):
            raise ValueError("Lognormal distribution requires low < expected < high")
        return self


def convert_to_hours(value: float, unit: EffortUnit, hours_per_day: float) -> float:
    """Convert a value from the given unit to hours.

    Args:
        value: Numeric value to convert
        unit: Source unit
        hours_per_day: Working hours per day

    Returns:
        Value in hours
    """
    if unit == EffortUnit.HOURS:
        return value
    elif unit == EffortUnit.DAYS:
        return value * hours_per_day
    elif unit == EffortUnit.WEEKS:
        return value * hours_per_day * 5
    else:
        raise ValueError(f"Unknown effort unit: {unit}")


class RiskImpact(BaseModel):
    """Impact specification for a risk."""

    type: ImpactType
    value: float = Field(gt=0)
    unit: Optional[EffortUnit] = Field(default=None)


class Risk(BaseModel):
    """Risk event that may affect task or project duration."""

    id: str
    name: str
    probability: float = Field(ge=0.0, le=1.0)
    impact: float | RiskImpact = Field(
        description="Time penalty as float (hours) or RiskImpact object"
    )
    description: Optional[str] = None

    @field_validator("impact", mode="before")
    @classmethod
    def validate_impact(cls, v: Any) -> float | RiskImpact:
        """Convert numeric impact to float, keep RiskImpact as is."""
        if isinstance(v, (int, float)):
            return float(v)
        elif isinstance(v, dict):
            return RiskImpact(**v)
        elif isinstance(v, RiskImpact):
            return v
        else:
            raise ValueError(
                f"Invalid impact value: {v}. Must be a number or RiskImpact object."
            )

    def get_impact_value(
        self, base_duration: float = 0.0, hours_per_day: float = 8.0
    ) -> float:
        """Get the impact value converted to hours.

        Args:
            base_duration: Base duration in hours for percentage calculations
            hours_per_day: Working hours per day for unit conversion

        Returns:
            Impact in hours
        """
        if isinstance(self.impact, (int, float)):
            # Raw float impacts are in hours (the canonical unit)
            return float(self.impact)
        elif self.impact.type == ImpactType.ABSOLUTE:
            value = self.impact.value
            unit = self.impact.unit or EffortUnit.HOURS
            return convert_to_hours(value, unit, hours_per_day)
        else:  # PERCENTAGE
            return base_duration * (self.impact.value / 100.0)


class UncertaintyFactors(BaseModel):
    """Uncertainty factors affecting task estimates."""

    team_experience: Optional[str] = Field(
        default=DEFAULT_UNCERTAINTY_FACTOR_LEVELS["team_experience"]
    )
    requirements_maturity: Optional[str] = Field(
        default=DEFAULT_UNCERTAINTY_FACTOR_LEVELS["requirements_maturity"]
    )
    technical_complexity: Optional[str] = Field(
        default=DEFAULT_UNCERTAINTY_FACTOR_LEVELS["technical_complexity"]
    )
    team_distribution: Optional[str] = Field(
        default=DEFAULT_UNCERTAINTY_FACTOR_LEVELS["team_distribution"]
    )
    integration_complexity: Optional[str] = Field(
        default=DEFAULT_UNCERTAINTY_FACTOR_LEVELS["integration_complexity"]
    )


class Task(BaseModel):
    """Project task with estimates and dependencies."""

    id: str
    name: str
    description: Optional[str] = None
    estimate: TaskEstimate
    dependencies: List[str] = Field(default_factory=list)
    uncertainty_factors: Optional[UncertaintyFactors] = Field(
        default_factory=UncertaintyFactors
    )
    resources: List[str] = Field(default_factory=list)
    max_resources: int = Field(default=1, ge=1)
    min_experience_level: int = Field(default=1)
    risks: List[Risk] = Field(default_factory=list)

    @field_validator("min_experience_level")
    @classmethod
    def validate_min_experience_level(cls, value: int) -> int:
        """Validate minimum experience level."""
        if value not in {1, 2, 3}:
            raise ValueError("min_experience_level must be one of: 1, 2, 3")
        return value

    def has_dependency(self, task_id: str) -> bool:
        """Check if this task depends on another task."""
        return task_id in self.dependencies


class ProjectMetadata(BaseModel):
    """Project metadata and configuration."""

    name: str
    description: Optional[str] = None
    start_date: date
    hours_per_day: float = Field(
        default=8.0,
        gt=0,
        description="Working hours per day (default 8)",
    )
    currency: Optional[str] = Field(default="USD")
    confidence_levels: List[int] = Field(
        default_factory=lambda: list(DEFAULT_CONFIDENCE_LEVELS)
    )
    probability_red_threshold: float = Field(
        default=DEFAULT_PROBABILITY_RED_THRESHOLD,
        ge=0.0,
        le=1.0,
        description="Probability threshold below which is shown as red (default 50%)",
    )
    probability_green_threshold: float = Field(
        default=DEFAULT_PROBABILITY_GREEN_THRESHOLD,
        ge=0.0,
        le=1.0,
        description="Probability threshold above which is shown as green (default 90%)",
    )
    distribution: DistributionType = Field(
        default=DistributionType.TRIANGULAR,
        description=(
            "Default task estimate distribution when a task does not specify one"
        ),
    )
    team_size: Optional[int] = Field(default=None, ge=0)

    @field_validator("start_date", mode="before")
    @classmethod
    def parse_date(cls, v: Any) -> date:
        """Parse date from string if needed."""
        if isinstance(v, str):
            return date.fromisoformat(v)
        elif isinstance(v, date):
            return v
        else:
            raise ValueError(
                f"Invalid date value: {v}. Must be a date object or ISO format string."
            )

    @model_validator(mode="after")
    def validate_thresholds(self) -> "ProjectMetadata":
        """Validate that red threshold is less than green threshold."""
        if self.probability_red_threshold >= self.probability_green_threshold:
            raise ValueError(
                f"probability_red_threshold ({self.probability_red_threshold}) "
                f"must be less than probability_green_threshold ({self.probability_green_threshold})"
            )
        return self


class Project(BaseModel):
    """Complete project definition."""

    project: ProjectMetadata
    tasks: List[Task]
    project_risks: List[Risk] = Field(default_factory=list)
    resources: List["ResourceSpec"] = Field(default_factory=list)
    calendars: List["CalendarSpec"] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_project(self) -> "Project":
        """Validate project integrity."""
        # Check unique task IDs
        task_ids = [task.id for task in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("Task IDs must be unique")

        # Check at least one task
        if not self.tasks:
            raise ValueError("Project must have at least one task")

        # Validate dependencies exist
        for task in self.tasks:
            for dep_id in task.dependencies:
                if dep_id not in task_ids:
                    raise ValueError(
                        f"Task {task.id} depends on non-existent task {dep_id}"
                    )

        # Check for circular dependencies
        self._check_circular_dependencies()

        # Validate effective task distributions after project defaults are known
        self._validate_effective_task_distributions()

        # Validate and normalize resources
        self._normalize_and_validate_resources()
        self._validate_calendars()
        self._validate_resource_references()

        return self

    def _normalize_and_validate_resources(self) -> None:
        """Normalize resource names and validate uniqueness/defaults."""
        self._apply_team_size_resource_rules()

        used_names: set[str] = set()
        next_index = 1

        for resource in self.resources:
            if not resource.name:
                while True:
                    candidate = f"resource_{next_index:03d}"
                    next_index += 1
                    if candidate not in used_names:
                        resource.name = candidate
                        break

            if resource.name in used_names:
                raise ValueError(f"Resource names must be unique: {resource.name}")
            used_names.add(resource.name)

    def _apply_team_size_resource_rules(self) -> None:
        """Apply validation and defaults for team_size vs explicit resources.

        Rules:
        - team_size is None or 0: keep explicitly specified resources only.
        - team_size > 0 and explicit resources > team_size: validation error.
        - team_size > 0 and explicit resources < team_size: append default
          resources so total count equals team_size.
        """
        team_size = self.project.team_size
        if team_size is None or team_size == 0:
            return

        explicit_count = len(self.resources)
        if explicit_count > team_size:
            raise ValueError(
                "team_size is smaller than explicitly specified resources: "
                f"team_size={team_size}, resources={explicit_count}"
            )

        missing = team_size - explicit_count
        if missing <= 0:
            return

        self.resources.extend(ResourceSpec() for _ in range(missing))

    def _validate_calendars(self) -> None:
        """Validate calendar identifier uniqueness."""
        calendar_ids = [calendar.id for calendar in self.calendars]
        if len(calendar_ids) != len(set(calendar_ids)):
            raise ValueError("Calendar IDs must be unique")

    def _validate_resource_references(self) -> None:
        """Validate task and resource references to resources/calendars."""
        resource_names = {resource.name for resource in self.resources if resource.name}
        resource_by_name = {
            resource.name: resource for resource in self.resources if resource.name
        }
        available_calendar_ids = {calendar.id for calendar in self.calendars} or {
            "default"
        }

        for task in self.tasks:
            for resource_name in task.resources:
                if resource_name not in resource_names:
                    raise ValueError(
                        f"Task {task.id} references unknown resource {resource_name}"
                    )

                resource = resource_by_name[resource_name]
                if resource.experience_level < task.min_experience_level:
                    raise ValueError(
                        f"Task {task.id} requires min_experience_level "
                        f"{task.min_experience_level}, but assigned resource "
                        f"{resource_name} has experience_level "
                        f"{resource.experience_level}"
                    )

        for resource in self.resources:
            if resource.calendar not in available_calendar_ids:
                raise ValueError(
                    f"Resource {resource.name} references unknown calendar {resource.calendar}"
                )

    def _check_circular_dependencies(self) -> None:
        """Check for circular dependencies using DFS."""
        task_map = {task.id: task for task in self.tasks}

        def has_cycle(task_id: str, visited: set[str], rec_stack: set[str]) -> bool:
            visited.add(task_id)
            rec_stack.add(task_id)

            task = task_map[task_id]
            for dep_id in task.dependencies:
                if dep_id not in visited:
                    if has_cycle(dep_id, visited, rec_stack):
                        return True
                elif dep_id in rec_stack:
                    return True

            rec_stack.remove(task_id)
            return False

        visited: set[str] = set()
        for task in self.tasks:
            if task.id not in visited:
                if has_cycle(task.id, visited, set()):
                    raise ValueError(
                        f"Circular dependency detected involving task {task.id}"
                    )

    def _validate_effective_task_distributions(self) -> None:
        """Validate explicit task ranges against the effective distribution."""
        for task in self.tasks:
            effective_distribution = (
                task.estimate.distribution or self.project.distribution
            )
            try:
                task.estimate.validate_effective_distribution(effective_distribution)
            except ValueError as error:
                raise ValueError(f"Task {task.id}: {error}") from error

    def get_task_by_id(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None


class ResourceSpec(BaseModel):
    """Individual resource/member specification."""

    name: Optional[str] = None
    id: Optional[str] = None
    availability: float = Field(default=1.0, gt=0.0, le=1.0)
    calendar: str = Field(default="default")
    experience_level: int = Field(default=2)
    productivity_level: float = Field(default=1.0)
    sickness_prob: float = Field(default=0.0, ge=0.0, le=1.0)
    planned_absence: List[date] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_name(self) -> "ResourceSpec":
        """Use legacy id as fallback name."""
        if self.name is None and self.id is not None:
            self.name = self.id
        return self

    @field_validator("experience_level")
    @classmethod
    def validate_experience_level(cls, value: int) -> int:
        """Validate experience level."""
        if value not in {1, 2, 3}:
            raise ValueError("experience_level must be one of: 1, 2, 3")
        return value

    @field_validator("productivity_level")
    @classmethod
    def validate_productivity_level(cls, value: float) -> float:
        """Validate productivity level."""
        if value < 0.1 or value > 2.0:
            raise ValueError("productivity_level must be between 0.1 and 2.0")
        return value


class CalendarSpec(BaseModel):
    """Working calendar specification."""

    id: str = Field(default="default")
    work_hours_per_day: float = Field(default=8.0, gt=0)
    work_days: List[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5])
    holidays: List[date] = Field(default_factory=list)

    @field_validator("work_days")
    @classmethod
    def validate_work_days(cls, value: List[int]) -> List[int]:
        """Validate work day values (1=Mon ... 7=Sun)."""
        for day in value:
            if day < 1 or day > 7:
                raise ValueError("work_days entries must be integers in range 1..7")
        return value
