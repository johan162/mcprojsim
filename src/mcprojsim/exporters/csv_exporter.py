"""CSV exporter for simulation results."""

import csv
from datetime import datetime
from pathlib import Path

from mcprojsim.config import Config
from mcprojsim.models.simulation import SimulationResults


class CSVExporter:
    """Exporter for CSV format."""

    @staticmethod
    def export(
        results: SimulationResults,
        output_path: Path | str,
        config: Config | None = None,
        critical_path_limit: int | None = None,
    ) -> None:
        """Export results to CSV file.

        Args:
            results: Simulation results
            output_path: Path to output file
            config: Active configuration
            critical_path_limit: Maximum number of critical path sequences to include
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        effective_config = config or Config.get_default()
        report_limit = (
            critical_path_limit or effective_config.output.critical_path_report_limit
        )

        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)

            # Write header
            writer.writerow(["Metric", "Value"])

            # Write project info
            simulation_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            writer.writerow(["Project Name", results.project_name])
            writer.writerow(["Simulation Date", simulation_date])
            writer.writerow(["Iterations", results.iterations])
            writer.writerow(["Random Seed", results.random_seed])
            writer.writerow([])

            # Write statistics
            writer.writerow(["Statistics", ""])
            writer.writerow(["Mean", f"{results.mean:.2f}"])
            writer.writerow(["Median", f"{results.median:.2f}"])
            writer.writerow(["Std Dev", f"{results.std_dev:.2f}"])
            writer.writerow(["Min", f"{results.min_duration:.2f}"])
            writer.writerow(["Max", f"{results.max_duration:.2f}"])
            cv = results.std_dev / results.mean if results.mean > 0 else 0
            writer.writerow(["Coefficient of Variation", f"{cv:.4f}"])
            writer.writerow([])

            # Write percentiles
            writer.writerow(["Percentiles", ""])
            for percentile, value in sorted(results.percentiles.items()):
                writer.writerow([f"P{percentile}", f"{value:.2f}"])
            writer.writerow([])

            # Write critical path
            writer.writerow(["Critical Path", "Criticality"])
            critical_path = results.get_critical_path()
            for task_id, criticality in sorted(
                critical_path.items(), key=lambda x: x[1], reverse=True
            ):
                writer.writerow([task_id, f"{criticality:.4f}"])
            writer.writerow([])

            writer.writerow(
                ["Critical Path Sequences", "Count", "Frequency", "Percentage"]
            )
            for record in results.get_critical_path_sequences(report_limit):
                writer.writerow(
                    [
                        record.format_path(),
                        record.count,
                        f"{record.frequency:.4f}",
                        f"{record.frequency * 100:.1f}%",
                    ]
                )
            writer.writerow([])

            # Write histogram
            writer.writerow(["Histogram Data", ""])
            bin_edges, counts = results.get_histogram_data(bins=50)
            writer.writerow(["Bin Edge (days)", "Count", "Cumulative %"])

            cumulative_count = 0
            total_count = sum(counts)

            for i, (edge, count) in enumerate(zip(bin_edges[1:], counts)):
                cumulative_count += count
                cumulative_pct = (
                    (cumulative_count / total_count * 100) if total_count > 0 else 0
                )
                writer.writerow([f"{edge:.2f}", int(count), f"{cumulative_pct:.2f}"])
