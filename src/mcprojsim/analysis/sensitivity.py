"""Sensitivity analysis for task impacts."""

from typing import Dict
import numpy as np
from scipy import stats
from mcprojsim.models.simulation import SimulationResults


class SensitivityAnalyzer:
    """Analyzer for sensitivity analysis."""

    @staticmethod
    def calculate_correlations(results: SimulationResults) -> Dict[str, float]:
        """Calculate Spearman rank correlation between task durations and project.

        Args:
            results: Simulation results

        Returns:
            Dictionary mapping task IDs to correlation coefficients
        """
        correlations: Dict[str, float] = {}

        for task_id, task_durations in results.task_durations.items():
            # Calculate Spearman correlation
            # Convert to numpy arrays to ensure proper typing
            x: np.ndarray = np.asarray(task_durations)
            y: np.ndarray = np.asarray(results.durations)

            # stats.spearmanr returns a tuple (correlation, p-value)
            correlation_coeff, _ = stats.spearmanr(x, y)
            # Explicit cast to handle scipy type inference issues
            correlations[task_id] = float(np.asarray(correlation_coeff).item())

        return correlations

    @staticmethod
    def get_top_contributors(
        results: SimulationResults, n: int = 10
    ) -> list[tuple[str, float]]:
        """Get top N tasks contributing to schedule variance.

        Args:
            results: Simulation results
            n: Number of top tasks to return

        Returns:
            List of (task_id, correlation) tuples, sorted by correlation
        """
        correlations = SensitivityAnalyzer.calculate_correlations(results)

        # Sort by absolute correlation value
        sorted_tasks = sorted(
            correlations.items(), key=lambda x: abs(x[1]), reverse=True
        )

        return sorted_tasks[:n]
