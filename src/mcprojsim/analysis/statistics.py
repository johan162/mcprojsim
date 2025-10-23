"""Statistical analysis utilities."""

from typing import Dict

import numpy as np
from scipy import stats

from mcprojsim.models.simulation import SimulationResults


class StatisticalAnalyzer:
    """Analyzer for simulation statistics."""

    @staticmethod
    def calculate_statistics(durations: np.ndarray) -> Dict[str, float]:
        """Calculate statistical measures.

        Args:
            durations: Array of duration values

        Returns:
            Dictionary of statistical measures
        """
        return {
            "mean": float(np.mean(durations)),
            "median": float(np.median(durations)),
            "std_dev": float(np.std(durations)),
            "variance": float(np.var(durations)),
            "min": float(np.min(durations)),
            "max": float(np.max(durations)),
            "range": float(np.max(durations) - np.min(durations)),
            "coefficient_of_variation": (
                float(np.std(durations) / np.mean(durations))
                if np.mean(durations) > 0
                else 0.0
            ),
        }

    @staticmethod
    def calculate_percentiles(
        durations: np.ndarray, percentiles: list[int]
    ) -> Dict[int, float]:
        """Calculate percentile values.

        Args:
            durations: Array of duration values
            percentiles: List of percentile values (0-100)

        Returns:
            Dictionary mapping percentiles to values
        """
        return {p: float(np.percentile(durations, p)) for p in percentiles}

    @staticmethod
    def confidence_interval(
        durations: np.ndarray, confidence: float = 0.95
    ) -> tuple[float, float]:
        """Calculate confidence interval.

        Args:
            durations: Array of duration values
            confidence: Confidence level (default 0.95)

        Returns:
            Tuple of (lower_bound, upper_bound)
        """
        mean = np.mean(durations)
        sem = stats.sem(durations)
        ci = stats.t.interval(confidence, len(durations) - 1, loc=mean, scale=sem)
        return float(ci[0]), float(ci[1])
