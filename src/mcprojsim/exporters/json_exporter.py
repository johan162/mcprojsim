"""JSON exporter for simulation results."""

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import numpy as np

from mcprojsim.analysis.staffing import StaffingAnalyzer
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
                "hours_per_day": results.hours_per_day,
            },
            "statistics": {
                "mean_hours": results.mean,
                "mean_working_days": math.ceil(results.mean / results.hours_per_day),
                "median_hours": results.median,
                "std_dev_hours": results.std_dev,
                "min_hours": results.min_duration,
                "max_hours": results.max_duration,
                "coefficient_of_variation": (
                    results.std_dev / results.mean if results.mean > 0 else 0
                ),
                "skewness": results.skewness,
                "kurtosis": results.kurtosis,
            },
            "percentiles": {
                str(p): {
                    "hours": v,
                    "working_days": math.ceil(v / results.hours_per_day),
                    "delivery_date": (
                        dd.isoformat()
                        if (dd := results.delivery_date(v)) is not None
                        else None
                    ),
                }
                for p, v in sorted(results.percentiles.items())
            },
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
            "sensitivity": {
                task_id: corr
                for task_id, corr in sorted(
                    results.sensitivity.items(),
                    key=lambda x: abs(x[1]),
                    reverse=True,
                )
            },
            "schedule_slack": results.task_slack,
            "risk_impact": results.get_risk_impact_summary(),
            "histogram": {
                "bin_edges": bin_edges.tolist(),
                "counts": counts.tolist(),
            },
            "staffing": JSONExporter._prepare_staffing_data(results, effective_config),
        }

    @staticmethod
    def _prepare_staffing_data(
        results: SimulationResults,
        config: Config,
    ) -> Dict[str, Any]:
        """Prepare staffing analysis data for JSON export."""
        recommendations = StaffingAnalyzer.recommend_team_size(results, config)
        table = StaffingAnalyzer.calculate_staffing_table(results, config)
        return {
            "total_effort_hours": round(results.total_effort_hours(), 2),
            "max_parallel_tasks": results.max_parallel_tasks,
            "recommendations": [r.to_dict() for r in recommendations],
            "table": [r.to_dict() for r in table],
        }
