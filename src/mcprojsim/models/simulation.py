"""Simulation result models."""

from typing import Any, Dict

import numpy as np
from pydantic import BaseModel, Field

from mcprojsim.config import (
    DEFAULT_PROBABILITY_GREEN_THRESHOLD,
    DEFAULT_PROBABILITY_RED_THRESHOLD,
)


class SimulationResults(BaseModel):
    """Results from Monte Carlo simulation."""

    model_config = {"arbitrary_types_allowed": True}

    iterations: int
    project_name: str
    durations: np.ndarray = Field(description="Array of project durations")
    task_durations: Dict[str, np.ndarray] = Field(default_factory=dict)
    critical_path_frequency: Dict[str, int] = Field(default_factory=dict)
    random_seed: int | None = None
    probability_red_threshold: float = DEFAULT_PROBABILITY_RED_THRESHOLD
    probability_green_threshold: float = DEFAULT_PROBABILITY_GREEN_THRESHOLD

    mean: float = 0.0
    median: float = 0.0
    std_dev: float = 0.0
    min_duration: float = 0.0
    max_duration: float = 0.0
    percentiles: Dict[int, float] = Field(default_factory=dict)

    def calculate_statistics(self) -> None:
        """Calculate statistical measures from simulation results."""
        self.mean = float(np.mean(self.durations))
        self.median = float(np.median(self.durations))
        self.std_dev = float(np.std(self.durations))
        self.min_duration = float(np.min(self.durations))
        self.max_duration = float(np.max(self.durations))

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

    def get_histogram_data(self, bins: int = 50) -> tuple[np.ndarray, np.ndarray]:
        """Get histogram data for visualization.

        Args:
            bins: Number of histogram bins

        Returns:
            Tuple of (bin_edges, frequencies)
        """
        counts, bin_edges = np.histogram(self.durations, bins=bins)
        return bin_edges, counts

    def to_dict(self) -> Dict[str, Any]:
        """Convert results to dictionary for export."""
        return {
            "project_name": self.project_name,
            "iterations": self.iterations,
            "random_seed": self.random_seed,
            "statistics": {
                "mean": self.mean,
                "median": self.median,
                "std_dev": self.std_dev,
                "min": self.min_duration,
                "max": self.max_duration,
                "coefficient_of_variation": (
                    self.std_dev / self.mean if self.mean > 0 else 0
                ),
            },
            "percentiles": self.percentiles,
            "critical_path": self.get_critical_path(),
        }
