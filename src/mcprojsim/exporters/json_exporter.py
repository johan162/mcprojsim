"""JSON exporter for simulation results."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import numpy as np

from mcprojsim.config import Config
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
    def export(
        results: SimulationResults,
        output_path: Path | str,
        config: Config | None = None,
        critical_path_limit: int | None = None,
    ) -> None:
        """Export results to JSON file.

        Args:
            results: Simulation results
            output_path: Path to output file
            config: Active configuration
            critical_path_limit: Maximum number of critical path sequences to include
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = JSONExporter._prepare_data(results, config, critical_path_limit)

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2, cls=NumpyEncoder)

    @staticmethod
    def _prepare_data(
        results: SimulationResults,
        config: Config | None = None,
        critical_path_limit: int | None = None,
    ) -> Dict[str, Any]:
        """Prepare data for JSON export.

        Args:
            results: Simulation results

        Returns:
            Dictionary of data
        """
        effective_config = config or Config.get_default()
        report_limit = (
            critical_path_limit or effective_config.output.critical_path_report_limit
        )

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
            "critical_path_sequences": [
                {
                    "rank": index,
                    "path": list(record.path),
                    "path_display": record.format_path(),
                    "count": record.count,
                    "frequency": record.frequency,
                }
                for index, record in enumerate(
                    results.get_critical_path_sequences(report_limit),
                    start=1,
                )
            ],
            "histogram": {
                "bin_edges": bin_edges.tolist(),
                "counts": counts.tolist(),
            },
        }
