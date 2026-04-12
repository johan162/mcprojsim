"""Cost analysis: sensitivity and duration-cost correlation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, cast

import numpy as np
from scipy import stats as scipy_stats

if TYPE_CHECKING:
    from mcprojsim.models.simulation import SimulationResults


@dataclass
class CostAnalysis:
    """Phase 2 analysis results for cost data.

    Produced by CostAnalyzer.analyze(). Contains derived analysis artifacts
    that are separate from the raw simulation output in SimulationResults.
    """

    sensitivity: Dict[str, float] = field(default_factory=dict)
    """Spearman rank correlation between each task's cost array and total project
    cost. Values near 1.0 mean the task is a major cost driver; values near 0
    mean the task contributes little to cost variance."""

    duration_correlation: float = 0.0
    """Pearson r between total cost array and elapsed duration array. In most
    projects this will be very high (>0.9); it diverges when resource rates
    vary significantly or when fixed costs dominate."""


class CostAnalyzer:
    """Post-simulation cost analysis.

    Computes cost sensitivity (which tasks drive cost variance) and the
    cost-duration correlation. Accepts SimulationResults and returns a
    CostAnalysis dataclass.

    Example:
        analyzer = CostAnalyzer()
        analysis = analyzer.analyze(results)
        print(analysis.sensitivity)           # {task_id: spearman_r, ...}
        print(analysis.duration_correlation)  # Pearson r
    """

    def analyze(self, results: "SimulationResults") -> CostAnalysis:
        """Run cost analysis on simulation results.

        Args:
            results: SimulationResults with costs and task_costs populated.
                     If costs is None, returns a CostAnalysis with empty fields.

        Returns:
            CostAnalysis with sensitivity and duration_correlation.
        """
        if results.costs is None or results.task_costs is None:
            return CostAnalysis()

        return CostAnalysis(
            sensitivity=self._compute_sensitivity(results),
            duration_correlation=self._compute_duration_correlation(results),
        )

    def _compute_sensitivity(self, results: "SimulationResults") -> Dict[str, float]:
        """Spearman rank correlation between per-task cost and total project cost."""
        total = results.costs
        if total is None or len(total) == 0:
            return {}

        sensitivity: Dict[str, float] = {}
        for task_id, task_cost_arr in (results.task_costs or {}).items():
            if len(task_cost_arr) != len(total):
                continue
            # Tasks with zero variance in both arrays have no meaningful correlation.
            if np.std(task_cost_arr) == 0 and np.std(total) == 0:
                sensitivity[task_id] = 0.0
                continue
            _result = cast(
                tuple[float, float], scipy_stats.spearmanr(task_cost_arr, total)
            )
            corr = _result[0]
            sensitivity[task_id] = float(corr) if not np.isnan(corr) else 0.0

        return dict(
            sorted(sensitivity.items(), key=lambda kv: abs(kv[1]), reverse=True)
        )

    def _compute_duration_correlation(self, results: "SimulationResults") -> float:
        """Pearson r between total cost and elapsed duration."""
        if results.costs is None or len(results.costs) == 0:
            return 0.0
        if np.std(results.costs) == 0 or np.std(results.durations) == 0:
            return 0.0
        _result = cast(
            tuple[float, float], scipy_stats.pearsonr(results.costs, results.durations)
        )
        corr = _result[0]
        return float(corr) if not np.isnan(corr) else 0.0
