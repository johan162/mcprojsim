"""Simulation result models."""

import math
from datetime import date, timedelta
from typing import Any, Dict, Optional

import numpy as np
from pydantic import BaseModel, Field
from scipy import stats as scipy_stats

from mcprojsim.config import (
    DEFAULT_PROBABILITY_GREEN_THRESHOLD,
    DEFAULT_PROBABILITY_RED_THRESHOLD,
)


class CriticalPathRecord(BaseModel):
    """Aggregated full critical path sequence information."""

    path: tuple[str, ...]
    count: int
    frequency: float

    def format_path(self) -> str:
        """Format the path as a readable arrow-separated string."""
        return " -> ".join(self.path)


class TwoPassDelta(BaseModel):
    """Traceability payload for two-pass constrained scheduling results."""

    enabled: bool = False
    pass1_iterations: int = 0
    pass2_iterations: int = 0
    ranking_method: str = "criticality_index"
    # Pass-1 aggregate statistics
    pass1_mean_hours: float = 0.0
    pass1_p50_hours: float = 0.0
    pass1_p80_hours: float = 0.0
    pass1_p90_hours: float = 0.0
    pass1_p95_hours: float = 0.0
    pass1_resource_wait_hours: float = 0.0
    pass1_resource_utilization: float = 0.0
    pass1_calendar_delay_hours: float = 0.0
    # Pass-2 aggregate statistics (full run)
    pass2_mean_hours: float = 0.0
    pass2_p50_hours: float = 0.0
    pass2_p80_hours: float = 0.0
    pass2_p90_hours: float = 0.0
    pass2_p95_hours: float = 0.0
    pass2_resource_wait_hours: float = 0.0
    pass2_resource_utilization: float = 0.0
    pass2_calendar_delay_hours: float = 0.0
    # Delta = pass-2 minus pass-1 (negative = improvement)
    delta_mean_hours: float = 0.0
    delta_p50_hours: float = 0.0
    delta_p80_hours: float = 0.0
    delta_p90_hours: float = 0.0
    delta_p95_hours: float = 0.0
    delta_resource_wait_hours: float = 0.0
    delta_resource_utilization: float = 0.0
    delta_calendar_delay_hours: float = 0.0
    # Per-task criticality indices from pass-1
    task_criticality_index: Dict[str, float] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Return the traceability payload as a plain dictionary."""
        return {
            "enabled": self.enabled,
            "pass1_iterations": self.pass1_iterations,
            "pass2_iterations": self.pass2_iterations,
            "ranking_method": self.ranking_method,
            "pass1": {
                "mean_hours": self.pass1_mean_hours,
                "p50_hours": self.pass1_p50_hours,
                "p80_hours": self.pass1_p80_hours,
                "p90_hours": self.pass1_p90_hours,
                "p95_hours": self.pass1_p95_hours,
                "resource_wait_hours": self.pass1_resource_wait_hours,
                "resource_utilization": self.pass1_resource_utilization,
                "calendar_delay_hours": self.pass1_calendar_delay_hours,
            },
            "pass2": {
                "mean_hours": self.pass2_mean_hours,
                "p50_hours": self.pass2_p50_hours,
                "p80_hours": self.pass2_p80_hours,
                "p90_hours": self.pass2_p90_hours,
                "p95_hours": self.pass2_p95_hours,
                "resource_wait_hours": self.pass2_resource_wait_hours,
                "resource_utilization": self.pass2_resource_utilization,
                "calendar_delay_hours": self.pass2_calendar_delay_hours,
            },
            "delta": {
                "mean_hours": self.delta_mean_hours,
                "p50_hours": self.delta_p50_hours,
                "p80_hours": self.delta_p80_hours,
                "p90_hours": self.delta_p90_hours,
                "p95_hours": self.delta_p95_hours,
                "resource_wait_hours": self.delta_resource_wait_hours,
                "resource_utilization": self.delta_resource_utilization,
                "calendar_delay_hours": self.delta_calendar_delay_hours,
            },
            "task_criticality_index": self.task_criticality_index,
        }


class SimulationResults(BaseModel):
    """Results from Monte Carlo simulation."""

    model_config = {"arbitrary_types_allowed": True}

    iterations: int
    project_name: str
    durations: np.ndarray = Field(description="Array of project durations")
    task_durations: Dict[str, np.ndarray] = Field(default_factory=dict)
    critical_path_frequency: Dict[str, int] = Field(default_factory=dict)
    critical_path_sequences: list[CriticalPathRecord] = Field(default_factory=list)
    random_seed: int | None = None
    probability_red_threshold: float = DEFAULT_PROBABILITY_RED_THRESHOLD
    probability_green_threshold: float = DEFAULT_PROBABILITY_GREEN_THRESHOLD
    hours_per_day: float = 8.0
    start_date: Optional[date] = None

    # Sensitivity analysis (Spearman rank correlations)
    sensitivity: Dict[str, float] = Field(default_factory=dict)

    # Schedule slack (mean total float per task across iterations)
    task_slack: Dict[str, float] = Field(default_factory=dict)

    # Peak parallelism observed across all iterations
    max_parallel_tasks: int = 0

    # Scheduling mode metadata and constrained diagnostics
    schedule_mode: str = "dependency_only"
    resource_constraints_active: bool = False
    resource_wait_time_hours: float = 0.0
    resource_utilization: float = 0.0
    calendar_delay_time_hours: float = 0.0

    # Risk impact tracking
    risk_impacts: Dict[str, np.ndarray] = Field(default_factory=dict)
    project_risk_impacts: np.ndarray = Field(default_factory=lambda: np.array([]))

    # Per-iteration total effort (sum of all task durations per iteration)
    effort_durations: np.ndarray = Field(
        default_factory=lambda: np.array([]),
        description="Per-iteration total person-effort in hours",
    )

    # Two-pass scheduling traceability (populated only when two-pass mode is active)
    two_pass_trace: Optional["TwoPassDelta"] = None

    mean: float = 0.0
    median: float = 0.0
    std_dev: float = 0.0
    min_duration: float = 0.0
    max_duration: float = 0.0
    skewness: float = 0.0
    kurtosis: float = 0.0
    percentiles: Dict[int, float] = Field(default_factory=dict)
    effort_percentiles: Dict[int, float] = Field(default_factory=dict)

    def calculate_statistics(self) -> None:
        """Calculate statistical measures from simulation results."""
        self.mean = float(np.mean(self.durations))
        self.median = float(np.median(self.durations))
        self.std_dev = float(np.std(self.durations))
        self.min_duration = float(np.min(self.durations))
        self.max_duration = float(np.max(self.durations))
        if self.std_dev > 0:
            self.skewness = float(scipy_stats.skew(self.durations))
            self.kurtosis = float(scipy_stats.kurtosis(self.durations))
        else:
            self.skewness = 0.0
            self.kurtosis = 0.0

    def percentile(self, p: int) -> float:
        """Get percentile value.

        Args:
            p: Percentile (0-100)

        Returns:
            Duration value at the given percentile
        """
        if p not in self.percentiles:
            self.percentiles[p] = float(np.percentile(self.durations, p))
        return self.percentiles[p]

    def effort_percentile(self, p: int) -> float:
        """Get percentile of total person-effort across iterations.

        Args:
            p: Percentile (0-100)

        Returns:
            Total effort value (person-hours) at the given percentile.
            Falls back to :meth:`total_effort_hours` when the per-iteration
            effort distribution is not available.
        """
        if p not in self.effort_percentiles:
            if len(self.effort_durations) > 0:
                self.effort_percentiles[p] = float(
                    np.percentile(self.effort_durations, p)
                )
            else:
                # Fallback: no per-iteration data; use the mean-based total.
                self.effort_percentiles[p] = self.total_effort_hours()
        return self.effort_percentiles[p]

    def get_critical_path(self) -> Dict[str, float]:
        """Get criticality index for each task.

        Returns:
            Dictionary mapping task IDs to their criticality (0.0 to 1.0)
        """
        if not self.critical_path_frequency:
            return {}

        return {
            task_id: count / self.iterations
            for task_id, count in self.critical_path_frequency.items()
        }

    def get_critical_path_sequences(
        self, top_n: int | None = None
    ) -> list[CriticalPathRecord]:
        """Get the most frequent full critical path sequences.

        Args:
            top_n: Maximum number of paths to return. If omitted, return all stored.

        Returns:
            List of aggregated critical path records in descending frequency order.
        """
        if top_n is None:
            return list(self.critical_path_sequences)

        return list(self.critical_path_sequences[:top_n])

    def get_most_frequent_critical_path(self) -> CriticalPathRecord | None:
        """Get the single most frequent full critical path sequence."""
        if not self.critical_path_sequences:
            return None

        return self.critical_path_sequences[0]

    def get_histogram_data(self, bins: int = 50) -> tuple[np.ndarray, np.ndarray]:
        """Get histogram data for visualization.

        Args:
            bins: Number of histogram bins

        Returns:
            Tuple of (bin_edges, frequencies)
        """
        counts, bin_edges = np.histogram(self.durations, bins=bins)
        return bin_edges, counts

    def probability_of_completion(self, target_hours: float) -> float:
        """Calculate the probability of completing within target hours.

        Args:
            target_hours: Target duration in hours

        Returns:
            Probability (0.0 to 1.0) of completing within the target
        """
        return float(np.mean(self.durations <= target_hours))

    def total_effort_hours(self) -> float:
        """Compute the total person-effort across all tasks in hours.

        This is the sum of per-task mean durations and represents the total
        amount of work regardless of parallelism.  It differs from
        :pyattr:`mean` which is the *elapsed* project duration (critical-path
        time).

        Returns:
            Total person-hours of effort.
        """
        if not self.task_durations:
            return self.mean
        return float(sum(np.mean(d) for d in self.task_durations.values()))

    def get_risk_impact_summary(self) -> Dict[str, Dict[str, float]]:
        """Get summary statistics for risk impacts per task.

        Returns:
            Dictionary mapping task IDs to their risk impact statistics:
            mean, trigger_rate (fraction of iterations where risk > 0),
            mean_when_triggered (mean impact excluding zero-impact iterations)
        """
        summary: Dict[str, Dict[str, float]] = {}
        for task_id, impacts in self.risk_impacts.items():
            arr = np.asarray(impacts)
            triggered = arr > 0
            trigger_rate = float(np.mean(triggered))
            mean_impact = float(np.mean(arr))
            mean_when_triggered = (
                float(np.mean(arr[triggered])) if np.any(triggered) else 0.0
            )
            summary[task_id] = {
                "mean_impact": mean_impact,
                "trigger_rate": trigger_rate,
                "mean_when_triggered": mean_when_triggered,
            }
        return summary

    def to_dict(self) -> Dict[str, Any]:
        """Convert results to dictionary for export."""
        return {
            "project_name": self.project_name,
            "iterations": self.iterations,
            "random_seed": self.random_seed,
            "hours_per_day": self.hours_per_day,
            "statistics": {
                "mean": self.mean,
                "median": self.median,
                "std_dev": self.std_dev,
                "min": self.min_duration,
                "max": self.max_duration,
                "coefficient_of_variation": (
                    self.std_dev / self.mean if self.mean > 0 else 0
                ),
                "skewness": self.skewness,
                "kurtosis": self.kurtosis,
            },
            "percentiles": self.percentiles,
            "sensitivity": self.sensitivity,
            "critical_path": self.get_critical_path(),
            "critical_path_sequences": [
                {
                    "path": list(record.path),
                    "count": record.count,
                    "frequency": record.frequency,
                }
                for record in self.critical_path_sequences
            ],
            "max_parallel_tasks": self.max_parallel_tasks,
            "schedule_mode": self.schedule_mode,
            "resource_constraints_active": self.resource_constraints_active,
            "constrained_diagnostics": {
                "resource_wait_time_hours": self.resource_wait_time_hours,
                "resource_utilization": self.resource_utilization,
                "calendar_delay_time_hours": self.calendar_delay_time_hours,
            },
            "two_pass_traceability": (
                self.two_pass_trace.to_dict() if self.two_pass_trace is not None else None
            ),
        }

    def hours_to_working_days(self, hours: float) -> int:
        """Convert hours to working days using ceiling rounding.

        Args:
            hours: Effort in hours

        Returns:
            Number of working days (ceiling)
        """
        return math.ceil(hours / self.hours_per_day)

    def delivery_date(self, effort_hours: float) -> date | None:
        """Calculate the delivery date from effort hours.

        Adds the required number of working days to start_date,
        skipping weekends (Saturday and Sunday).

        Args:
            effort_hours: Total effort in hours

        Returns:
            Projected delivery date, or None if no start_date
        """
        if self.start_date is None:
            return None
        working_days_needed = self.hours_to_working_days(effort_hours)
        return _add_working_days(self.start_date, working_days_needed)


def _add_working_days(start: date, working_days: int) -> date:
    """Add working days to a date, skipping weekends.

    Args:
        start: Start date
        working_days: Number of working days to add

    Returns:
        Target date after adding the working days
    """
    current = start
    added = 0
    while added < working_days:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Monday=0 .. Friday=4
            added += 1
    return current
