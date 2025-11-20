"""JSON exporter for simulation results."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import numpy as np

from mcprojsim.models.simulation import SimulationResults


class NumpyEncoder(json.JSONEncoder):
    """JSON encoder that handles NumPy types."""

    def default(self, o: Any) -> Any:
        if isinstance(o, np.integer):
            return int(o)
        elif isinstance(o, np.floating):
            return float(o)
        elif isinstance(o, np.ndarray):
            return o.tolist()
        return super().default(o)


class JSONExporter:
    """Exporter for JSON format."""

    @staticmethod
    def export(results: SimulationResults, output_path: Path | str) -> None:
        """Export results to JSON file.

        Args:
            results: Simulation results
            output_path: Path to output file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = JSONExporter._prepare_data(results)

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2, cls=NumpyEncoder)

    @staticmethod
    def _prepare_data(results: SimulationResults) -> Dict[str, Any]:
        """Prepare data for JSON export.

        Args:
            results: Simulation results

        Returns:
            Dictionary of data
        """
        # Get histogram data
        bin_edges, counts = results.get_histogram_data(bins=50)

        # Get current date and time for simulation timestamp
        simulation_date = datetime.now().isoformat()

        return {
            "project": {"name": results.project_name},
            "simulation": {
                "date": simulation_date,
                "iterations": results.iterations,
                "random_seed": results.random_seed,
            },
            "statistics": {
                "mean": results.mean,
                "median": results.median,
                "std_dev": results.std_dev,
                "min": results.min_duration,
                "max": results.max_duration,
                "coefficient_of_variation": (
                    results.std_dev / results.mean if results.mean > 0 else 0
                ),
            },
            "percentiles": results.percentiles,
            "critical_path": results.get_critical_path(),
            "histogram": {
                "bin_edges": bin_edges.tolist(),
                "counts": counts.tolist(),
            },
        }
