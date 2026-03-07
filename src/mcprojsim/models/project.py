"""Data models for projects, tasks, and risks."""

from datetime import date
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from mcprojsim.config import (
    DEFAULT_CONFIDENCE_LEVELS,
    DEFAULT_PROBABILITY_GREEN_THRESHOLD,
    DEFAULT_PROBABILITY_RED_THRESHOLD,
    DEFAULT_UNCERTAINTY_FACTOR_LEVELS,
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

    distribution: DistributionType = Field(default=DistributionType.TRIANGULAR)
    min: Optional[float] = Field(default=None, ge=0)
    most_likely: Optional[float] = Field(default=None, gt=0)
    max: Optional[float] = Field(default=None, ge=0)
    standard_deviation: Optional[float] = Field(default=None, gt=0)
    t_shirt_size: Optional[str] = Field(default=None)
    unit: str = Field(default="days")

    @model_validator(mode="after")
    def validate_distribution(self) -> "TaskEstimate":
        """Validate distribution parameters."""
        # If T-shirt size is specified, skip other validations
        # The actual values will be populated from config during simulation
        if self.t_shirt_size is not None:
            return self

        # For explicit estimates, most_likely is required
        if self.most_likely is None:
            raise ValueError("Either 't_shirt_size' or 'most_likely' must be specified")

        if self.distribution == DistributionType.TRIANGULAR:
            if self.min is None or self.max is None:
                raise ValueError(
                    "Triangular distribution requires min, most_likely, and max"
                )
            if not (self.min <= self.most_likely <= self.max):
                raise ValueError(
                    f"Must satisfy min <= most_likely <= max, "
                    f"got {self.min} <= {self.most_likely} <= {self.max}"
                )
        elif self.distribution == DistributionType.LOGNORMAL:
            if self.standard_deviation is None:
                raise ValueError(
                    "Lognormal distribution requires most_likely and standard_deviation"
                )
        return self


class RiskImpact(BaseModel):
    """Impact specification for a risk."""

    type: ImpactType
    value: float = Field(gt=0)
    unit: Optional[str] = Field(default="days")


class Risk(BaseModel):
    """Risk event that may affect task or project duration."""

    id: str
    name: str
    probability: float = Field(ge=0.0, le=1.0)
    impact: float | RiskImpact = Field(
        description="Time penalty as float (days) or RiskImpact object"
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

    def get_impact_value(self, base_duration: float = 0.0) -> float:
        """Get the impact value in absolute time units.

        Args:
            base_duration: Base duration for percentage calculations

        Returns:
            Impact in absolute time units (e.g., days)
        """
        if isinstance(self.impact, (int, float)):
            return float(self.impact)
        elif self.impact.type == ImpactType.ABSOLUTE:
            return self.impact.value
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
    risks: List[Risk] = Field(default_factory=list)

    def has_dependency(self, task_id: str) -> bool:
        """Check if this task depends on another task."""
        return task_id in self.dependencies


class ProjectMetadata(BaseModel):
    """Project metadata and configuration."""

    name: str
    description: Optional[str] = None
    start_date: date
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
    resources: List[Dict[str, Any]] = Field(default_factory=list)
    calendars: List[Dict[str, Any]] = Field(default_factory=list)

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

        return self

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

    def get_task_by_id(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None
