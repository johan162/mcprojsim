"""Critical path analysis."""

from typing import Dict, List

from mcprojsim.models.simulation import SimulationResults


class CriticalPathAnalyzer:
    """Analyzer for critical path identification."""

    @staticmethod
    def get_criticality_index(results: SimulationResults) -> Dict[str, float]:
        """Get criticality index for each task.

        Args:
            results: Simulation results

        Returns:
            Dictionary mapping task IDs to criticality (0.0-1.0)
        """
        return results.get_critical_path()

    @staticmethod
    def get_most_critical_tasks(
        results: SimulationResults, threshold: float = 0.5
    ) -> List[str]:
        """Get tasks that are critical in at least threshold % of iterations.

        Args:
            results: Simulation results
            threshold: Minimum criticality threshold (0.0-1.0)

        Returns:
            List of critical task IDs
        """
        criticality = CriticalPathAnalyzer.get_criticality_index(results)
        return [task_id for task_id, crit in criticality.items() if crit >= threshold]
