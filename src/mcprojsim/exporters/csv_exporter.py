"""CSV exporter for simulation results."""

import csv
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from mcprojsim.analysis.staffing import StaffingAnalyzer
from mcprojsim.config import Config
from mcprojsim.models.project import Project
from mcprojsim.models.simulation import SimulationResults
from mcprojsim.models.sprint_simulation import SprintPlanningResults


class CSVExporter:
    """Exporter for CSV format."""

    @staticmethod
    def export(
        results: SimulationResults,
        output_path: Path | str,
        project: Project | None = None,
        config: Config | None = None,
        critical_path_limit: int | None = None,
        sprint_results: SprintPlanningResults | None = None,
        fx_provider: Any | None = None,
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
            start_date_str = (
                results.start_date.isoformat()
                if results.start_date
                else "Not specified"
            )
            writer.writerow(["Start Date", start_date_str])
            num_tasks = (
                len(results.critical_path_frequency)
                if results.critical_path_frequency
                else 0
            )
            writer.writerow(["Number of Tasks", num_tasks])
            effective_default_distribution = (
                project.project.distribution.value
                if project is not None
                else "Not specified"
            )
            writer.writerow(
                ["Effective Default Distribution", effective_default_distribution]
            )
            writer.writerow(
                [
                    "T-Shirt Category Used",
                    effective_config.t_shirt_size_default_category,
                ]
            )
            writer.writerow(["Simulation Date", simulation_date])
            writer.writerow(["Iterations", results.iterations])
            writer.writerow(["Random Seed", results.random_seed])
            writer.writerow(["Hours per Day", results.hours_per_day])
            writer.writerow(["Schedule Mode", results.schedule_mode])
            writer.writerow([])

            # Write statistics
            writer.writerow(["Statistics", ""])
            writer.writerow(["Mean (hours)", f"{results.mean:.2f}"])
            writer.writerow(
                [
                    "Mean (working days)",
                    math.ceil(results.mean / results.hours_per_day),
                ]
            )
            writer.writerow(["Median (hours)", f"{results.median:.2f}"])
            writer.writerow(["Std Dev (hours)", f"{results.std_dev:.2f}"])
            writer.writerow(["Min (hours)", f"{results.min_duration:.2f}"])
            writer.writerow(["Max (hours)", f"{results.max_duration:.2f}"])
            cv = results.std_dev / results.mean if results.mean > 0 else 0
            writer.writerow(["Coefficient of Variation", f"{cv:.4f}"])
            writer.writerow(["Skewness", f"{results.skewness:.4f}"])
            writer.writerow(["Kurtosis", f"{results.kurtosis:.4f}"])
            writer.writerow([])

            # Write calendar time confidence intervals
            writer.writerow(["Calendar Time Confidence Intervals", ""])
            for percentile, value in sorted(results.percentiles.items()):
                working_days = math.ceil(value / results.hours_per_day)
                delivery = results.delivery_date(value)
                date_str = delivery.isoformat() if delivery else ""
                writer.writerow(
                    [
                        f"P{percentile}",
                        f"{value:.2f} hours",
                        f"{working_days} working days",
                        date_str,
                    ]
                )
            writer.writerow([])

            # Write effort confidence intervals
            if results.effort_percentiles:
                writer.writerow(["Effort Confidence Intervals", ""])
                for percentile, value in sorted(results.effort_percentiles.items()):
                    person_days = math.ceil(value / results.hours_per_day)
                    writer.writerow(
                        [
                            f"P{percentile}",
                            f"{value:.2f} person-hours",
                            f"{person_days} person-days",
                        ]
                    )
                writer.writerow([])

            # Write cost statistics
            if results.costs is not None and (
                config is None or effective_config.cost.include_in_output
            ):
                currency = results.currency or ""
                writer.writerow(["Cost Statistics", ""])
                if results.cost_mean is not None:
                    writer.writerow(["cost_mean", f"{results.cost_mean:.2f}", currency])
                if results.cost_std_dev is not None:
                    writer.writerow(
                        ["cost_std_dev", f"{results.cost_std_dev:.2f}", currency]
                    )
                for p, v in sorted((results.cost_percentiles or {}).items()):
                    writer.writerow([f"cost_p{p}", f"{v:.2f}", currency])

                # Write secondary currency costs
                if fx_provider is not None and project is not None:
                    import numpy as np

                    sec_curs = list(project.project.secondary_currencies)
                    if sec_curs:
                        writer.writerow([])
                        writer.writerow(
                            ["secondary_currency_costs", "statistic", "value"]
                        )
                        for cur in sec_curs:
                            cost_arr = fx_provider.convert_array(results.costs, cur)
                            if cost_arr is None:
                                writer.writerow([cur, "error", "rate_unavailable"])
                                continue
                            if results.cost_mean is not None:
                                writer.writerow(
                                    [cur, "mean", f"{float(np.mean(cost_arr)):.2f}"]
                                )
                            for p, v in sorted(
                                (results.cost_percentiles or {}).items()
                            ):
                                pv = float(np.percentile(cost_arr, p))
                                writer.writerow([cur, f"p{p}", f"{pv:.2f}"])

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
            effective_config = config or Config.get_default()
            bin_edges, counts = results.get_histogram_data(
                bins=effective_config.output.number_bins
            )
            writer.writerow(["Bin Edge (hours)", "Count", "Cumulative %"])

            cumulative_count = 0
            total_count = sum(counts)

            for _, (edge, count) in enumerate(zip(bin_edges[1:], counts)):
                cumulative_count += count
                cumulative_pct = (
                    (cumulative_count / total_count * 100) if total_count > 0 else 0
                )
                writer.writerow([f"{edge:.2f}", int(count), f"{cumulative_pct:.2f}"])

            # Write sensitivity analysis
            if results.sensitivity:
                writer.writerow([])
                writer.writerow(
                    ["Sensitivity Analysis", "Correlation", "Abs Correlation"]
                )
                for task_id, corr in sorted(
                    results.sensitivity.items(),
                    key=lambda x: abs(x[1]),
                    reverse=True,
                ):
                    writer.writerow([task_id, f"{corr:.4f}", f"{abs(corr):.4f}"])

            # Write schedule slack
            if results.task_slack:
                writer.writerow([])
                writer.writerow(["Schedule Slack", "Mean Slack (hours)"])
                for task_id, slack_val in sorted(
                    results.task_slack.items(),
                    key=lambda x: x[1],
                ):
                    writer.writerow([task_id, f"{slack_val:.2f}"])

            # Write risk impact summary
            risk_summary = results.get_risk_impact_summary()
            has_risk_data = any(s["trigger_rate"] > 0 for s in risk_summary.values())
            if has_risk_data:
                writer.writerow([])
                writer.writerow(
                    [
                        "Risk Impact",
                        "Mean Impact (hours)",
                        "Trigger Rate",
                        "Mean When Triggered (hours)",
                    ]
                )
                for task_id, stats in sorted(risk_summary.items()):
                    if stats["trigger_rate"] > 0:
                        writer.writerow(
                            [
                                task_id,
                                f"{stats['mean_impact']:.2f}",
                                f"{stats['trigger_rate']:.4f}",
                                f"{stats['mean_when_triggered']:.2f}",
                            ]
                        )

            if results.resource_constraints_active:
                writer.writerow([])
                writer.writerow(["Constrained Schedule Diagnostics", ""])
                writer.writerow(
                    [
                        "Average Resource Wait (hours)",
                        f"{results.resource_wait_time_hours:.2f}",
                    ]
                )
                writer.writerow(
                    [
                        "Effective Resource Utilization",
                        f"{results.resource_utilization:.4f}",
                    ]
                )
                writer.writerow(
                    [
                        "Calendar Delay Contribution (hours)",
                        f"{results.calendar_delay_time_hours:.2f}",
                    ]
                )

            two_pass_trace = getattr(results, "two_pass_trace", None)
            if two_pass_trace is not None and two_pass_trace.enabled:
                tp = two_pass_trace
                writer.writerow([])
                writer.writerow(["Two-Pass Scheduling Traceability", ""])
                writer.writerow(["Pass-1 Iterations", tp.pass1_iterations])
                writer.writerow(["Pass-2 Iterations", tp.pass2_iterations])
                writer.writerow(["Ranking Method", tp.ranking_method])
                writer.writerow(["Pass-1 Mean (hours)", f"{tp.pass1_mean_hours:.2f}"])
                writer.writerow(["Pass-2 Mean (hours)", f"{tp.pass2_mean_hours:.2f}"])
                writer.writerow(["Delta Mean (hours)", f"{tp.delta_mean_hours:+.2f}"])
                writer.writerow(["Pass-1 P80 (hours)", f"{tp.pass1_p80_hours:.2f}"])
                writer.writerow(["Pass-2 P80 (hours)", f"{tp.pass2_p80_hours:.2f}"])
                writer.writerow(["Delta P80 (hours)", f"{tp.delta_p80_hours:+.2f}"])
                writer.writerow(["Pass-1 P90 (hours)", f"{tp.pass1_p90_hours:.2f}"])
                writer.writerow(["Pass-2 P90 (hours)", f"{tp.pass2_p90_hours:.2f}"])
                writer.writerow(["Delta P90 (hours)", f"{tp.delta_p90_hours:+.2f}"])
                writer.writerow(["Pass-1 P95 (hours)", f"{tp.pass1_p95_hours:.2f}"])
                writer.writerow(["Pass-2 P95 (hours)", f"{tp.pass2_p95_hours:.2f}"])
                writer.writerow(["Delta P95 (hours)", f"{tp.delta_p95_hours:+.2f}"])
                writer.writerow(
                    [
                        "Delta Resource Wait (hours)",
                        f"{tp.delta_resource_wait_hours:+.2f}",
                    ]
                )
                writer.writerow([])
                writer.writerow(["Task Criticality Index (pass-1)", ""])
                for task_id, ci in sorted(
                    tp.task_criticality_index.items(),
                    key=lambda x: (-x[1], x[0]),
                ):
                    writer.writerow([task_id, f"{ci:.4f}"])

            # Write staffing analysis
            writer.writerow([])
            recommendations = StaffingAnalyzer.recommend_team_size(
                results, effective_config
            )
            effort_basis = (
                recommendations[0].effort_basis if recommendations else "mean"
            )
            effort_hours_used = (
                round(recommendations[0].total_effort_hours, 2)
                if recommendations
                else round(results.total_effort_hours(), 2)
            )
            writer.writerow(["Staffing Effort Basis", effort_basis])
            writer.writerow(["Staffing Effort Hours Used", f"{effort_hours_used:.2f}"])
            writer.writerow(
                [
                    "Staffing Recommendations",
                    "Team Size",
                    "Working Days",
                    "Delivery Date",
                    "Efficiency",
                ]
            )
            for rec in recommendations:
                date_str = rec.delivery_date.isoformat() if rec.delivery_date else ""
                writer.writerow(
                    [
                        rec.profile,
                        rec.recommended_team_size,
                        rec.calendar_working_days,
                        date_str,
                        f"{rec.efficiency:.4f}",
                    ]
                )

            writer.writerow([])
            table_rows = StaffingAnalyzer.calculate_staffing_table(
                results, effective_config
            )
            writer.writerow(
                [
                    "Staffing Table",
                    "Team Size",
                    "Profile",
                    "Eff. Capacity",
                    "Working Days",
                    "Delivery Date",
                    "Efficiency",
                ]
            )
            for row in table_rows:
                date_str = row.delivery_date.isoformat() if row.delivery_date else ""
                writer.writerow(
                    [
                        "",
                        row.team_size,
                        row.profile,
                        f"{row.effective_capacity:.2f}",
                        row.calendar_working_days,
                        date_str,
                        f"{row.efficiency:.4f}",
                    ]
                )

            if sprint_results is not None:
                writer.writerow([])
                writer.writerow(["Sprint Planning", ""])
                writer.writerow(
                    ["Sprint Length (weeks)", sprint_results.sprint_length_weeks]
                )
                writer.writerow(
                    [
                        "Planning Confidence Level",
                        f"{sprint_results.planning_confidence_level:.0%}",
                    ]
                )
                writer.writerow(
                    ["Removed Work Treatment", sprint_results.removed_work_treatment]
                )
                writer.writerow(
                    [
                        "Planned Commitment Guidance",
                        f"{sprint_results.planned_commitment_guidance:.2f}",
                    ]
                )
                writer.writerow(
                    [
                        "Historical Sampling Mode",
                        sprint_results.historical_diagnostics.get("sampling_mode", ""),
                    ]
                )
                writer.writerow(
                    [
                        "Historical Observation Count",
                        sprint_results.historical_diagnostics.get(
                            "observation_count", 0
                        ),
                    ]
                )
                writer.writerow([])
                writer.writerow(["Sprint Count Statistical Summary", ""])
                writer.writerow(["Mean (sprints)", f"{sprint_results.mean:.2f}"])
                writer.writerow(["Median (P50)", f"{sprint_results.median:.2f}"])
                writer.writerow(["Std Dev (sprints)", f"{sprint_results.std_dev:.2f}"])
                writer.writerow(["Min (sprints)", f"{sprint_results.min_sprints:.2f}"])
                writer.writerow(["Max (sprints)", f"{sprint_results.max_sprints:.2f}"])
                writer.writerow([])
                writer.writerow(
                    ["Sprint Count Confidence Intervals", "Sprints", "Delivery Date"]
                )
                for percentile, value in sorted(sprint_results.percentiles.items()):
                    delivery_date = sprint_results.date_percentiles.get(percentile)
                    writer.writerow(
                        [
                            f"P{percentile}",
                            f"{value:.2f}",
                            delivery_date.isoformat() if delivery_date else "",
                        ]
                    )

                if sprint_results.carryover_statistics:
                    writer.writerow([])
                    writer.writerow(["Carryover Diagnostics", "Value"])
                    for metric, value in sorted(
                        sprint_results.carryover_statistics.items()
                    ):
                        writer.writerow([metric, value])

                if sprint_results.spillover_statistics:
                    writer.writerow([])
                    writer.writerow(["Spillover Diagnostics", "Value"])
                    aggregate_rate = sprint_results.spillover_statistics.get(
                        "aggregate_spillover_rate",
                        {},
                    )
                    for metric, value in sorted(aggregate_rate.items()):
                        writer.writerow([f"aggregate_spillover_rate.{metric}", value])

                if sprint_results.disruption_statistics:
                    writer.writerow([])
                    writer.writerow(["Disruption Diagnostics", "Value"])
                    for metric, value in sorted(
                        sprint_results.disruption_statistics.items()
                    ):
                        writer.writerow([metric, value])

                if sprint_results.burnup_percentiles:
                    writer.writerow([])
                    writer.writerow(["Burn-up Percentiles", "P50", "P80", "P90"])
                    for point in sprint_results.burnup_percentiles:
                        writer.writerow(
                            [
                                f"Sprint {int(point['sprint_number'])}",
                                point["p50"],
                                point["p80"],
                                point["p90"],
                            ]
                        )

                series_statistics = sprint_results.historical_diagnostics.get(
                    "series_statistics",
                    {},
                )
                if series_statistics:
                    writer.writerow([])
                    writer.writerow(
                        [
                            "Historical Series Statistics",
                            "Mean",
                            "Median",
                            "Std Dev",
                            "Min",
                            "Max",
                        ]
                    )
                    for series_name, stats in sorted(series_statistics.items()):
                        writer.writerow(
                            [
                                series_name,
                                f"{stats['mean']:.2f}",
                                f"{stats['median']:.2f}",
                                f"{stats['std_dev']:.2f}",
                                f"{stats['min']:.2f}",
                                f"{stats['max']:.2f}",
                            ]
                        )

                ratio_summaries = sprint_results.historical_diagnostics.get(
                    "ratios",
                    {},
                )
                if ratio_summaries:
                    writer.writerow([])
                    writer.writerow(
                        [
                            "Historical Ratio Summaries",
                            "Mean",
                            "Median",
                            "Std Dev",
                            "P50",
                            "P80",
                            "P90",
                        ]
                    )
                    for ratio_name, stats in sorted(ratio_summaries.items()):
                        percentiles = stats.get("percentiles", {})
                        writer.writerow(
                            [
                                ratio_name,
                                f"{stats['mean']:.4f}",
                                f"{stats['median']:.4f}",
                                f"{stats['std_dev']:.4f}",
                                f"{percentiles.get(50, 0.0):.4f}",
                                f"{percentiles.get(80, 0.0):.4f}",
                                f"{percentiles.get(90, 0.0):.4f}",
                            ]
                        )

                correlations = sprint_results.historical_diagnostics.get(
                    "correlations",
                    {},
                )
                if correlations:
                    writer.writerow([])
                    writer.writerow(["Historical Correlations", "Pearson Correlation"])
                    for pair_name, value in sorted(correlations.items()):
                        writer.writerow([pair_name, f"{value:.4f}"])
