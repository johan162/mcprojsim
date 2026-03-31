"""Sprint-planning result models."""

import math
from datetime import date, timedelta
from typing import Any, Optional

import numpy as np
from pydantic import BaseModel, Field


class SprintPlanningResults(BaseModel):
    """Results from sprint-based Monte Carlo planning."""

    model_config = {"arbitrary_types_allowed": True}

    iterations: int
    project_name: str
    sprint_length_weeks: int
    sprint_counts: np.ndarray = Field(description="Array of sprints-to-done samples")
    random_seed: int | None = None
    start_date: Optional[date] = None
    planning_confidence_level: float = 0.80
    removed_work_treatment: str = "churn_only"
    historical_diagnostics: dict[str, Any] = Field(default_factory=dict)
    planned_commitment_guidance: float = 0.0
    carryover_statistics: dict[str, Any] = Field(default_factory=dict)
    spillover_statistics: dict[str, Any] = Field(default_factory=dict)
    disruption_statistics: dict[str, Any] = Field(default_factory=dict)
    burnup_percentiles: list[dict[str, float]] = Field(default_factory=list)
    future_sprint_overrides: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Applied future sprint capacity adjustments for planning transparency",
    )

    mean: float = 0.0
    median: float = 0.0
    std_dev: float = 0.0
    min_sprints: float = 0.0
    max_sprints: float = 0.0
    percentiles: dict[int, float] = Field(default_factory=dict)
    date_percentiles: dict[int, date | None] = Field(default_factory=dict)

    def calculate_statistics(self) -> None:
        """Calculate summary statistics for sprint-count samples."""
        self.mean = float(np.mean(self.sprint_counts))
        self.median = float(np.median(self.sprint_counts))
        self.std_dev = float(np.std(self.sprint_counts))
        self.min_sprints = float(np.min(self.sprint_counts))
        self.max_sprints = float(np.max(self.sprint_counts))

    def percentile(self, p: int) -> float:
        """Return the percentile of the sprint-count distribution."""
        if p not in self.percentiles:
            self.percentiles[p] = float(np.percentile(self.sprint_counts, p))
        return self.percentiles[p]

    def date_percentile(self, p: int) -> date | None:
        """Map a sprint-count percentile to a sprint-boundary date."""
        if p not in self.date_percentiles:
            self.date_percentiles[p] = self.delivery_date_for_sprints(
                self.percentile(p)
            )
        return self.date_percentiles[p]

    def delivery_date_for_sprints(self, sprint_count: float) -> date | None:
        """Map a sprint count to a projected delivery date."""
        if self.start_date is None:
            return None

        sprint_boundaries = max(0, math.ceil(sprint_count) - 1)
        return self.start_date + timedelta(
            days=sprint_boundaries * self.sprint_length_weeks * 7
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert sprint-planning results to a serializable dictionary."""
        return {
            "project_name": self.project_name,
            "iterations": self.iterations,
            "random_seed": self.random_seed,
            "sprint_length_weeks": self.sprint_length_weeks,
            "statistics": {
                "mean": self.mean,
                "median": self.median,
                "std_dev": self.std_dev,
                "min": self.min_sprints,
                "max": self.max_sprints,
                "coefficient_of_variation": (
                    self.std_dev / self.mean if self.mean > 0 else 0.0
                ),
            },
            "percentiles": self.percentiles,
            "date_percentiles": {
                str(key): value.isoformat() if value is not None else None
                for key, value in self.date_percentiles.items()
            },
            "planning_confidence_level": self.planning_confidence_level,
            "planned_commitment_guidance": self.planned_commitment_guidance,
            "removed_work_treatment": self.removed_work_treatment,
            "historical_diagnostics": self.historical_diagnostics,
            "carryover_statistics": self.carryover_statistics,
            "spillover_statistics": self.spillover_statistics,
            "disruption_statistics": self.disruption_statistics,
            "burnup_percentiles": self.burnup_percentiles,
            "future_sprint_overrides": self.future_sprint_overrides,
        }
