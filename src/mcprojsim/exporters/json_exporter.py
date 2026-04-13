"""JSON exporter for simulation results."""

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import numpy as np

from mcprojsim.analysis.staffing import StaffingAnalyzer
from mcprojsim.config import Config
from mcprojsim.exporters.historic_base import build_historic_base
from mcprojsim.models.project import Project
from mcprojsim.models.simulation import SimulationResults
from mcprojsim.models.sprint_simulation import SprintPlanningResults


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
        sprint_results: SprintPlanningResults | None = None,
        project: Project | None = None,
        include_historic_base: bool = False,
        full_cost_detail: bool = False,
        fx_provider: Any = None,
        target_budget: float | None = None,
        target_hours: float | None = None,
    ) -> None:
        """Export results to JSON file.

        Args:
            results: Simulation results
            output_path: Path to output file
            config: Active configuration
            critical_path_limit: Maximum number of critical path sequences to include
            full_cost_detail: Include per-iteration task cost arrays (omitted by default)
            fx_provider: Optional ExchangeRateProvider for secondary currency output
            target_budget: Optional budget target for budget_analysis section
            target_hours: Optional duration target (hours) for joint_analysis section
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = JSONExporter._prepare_data(
            results,
            config,
            critical_path_limit,
            sprint_results,
            project,
            include_historic_base,
            full_cost_detail,
            fx_provider,
            target_budget,
            target_hours,
        )

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2, cls=NumpyEncoder)

    @staticmethod
    def _prepare_data(
        results: SimulationResults,
        config: Config | None = None,
        critical_path_limit: int | None = None,
        sprint_results: SprintPlanningResults | None = None,
        project: Project | None = None,
        include_historic_base: bool = False,
        full_cost_detail: bool = False,
        fx_provider: Any = None,
        target_budget: float | None = None,
        target_hours: float | None = None,
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
        bin_edges, counts = results.get_histogram_data(
            bins=effective_config.output.number_bins
        )

        # Get current date and time for simulation timestamp
        simulation_date = datetime.now().isoformat()

        start_date_str = results.start_date.isoformat() if results.start_date else None
        effective_default_distribution = (
            project.project.distribution.value if project is not None else None
        )
        data = {
            "project": {
                "name": results.project_name,
                "start_date": start_date_str,
                "num_tasks": (
                    len(results.critical_path_frequency)
                    if results.critical_path_frequency
                    else 0
                ),
                "effective_default_distribution": effective_default_distribution,
                "t_shirt_category_used": effective_config.t_shirt_size_default_category,
            },
            "simulation": {
                "date": simulation_date,
                "iterations": results.iterations,
                "random_seed": results.random_seed,
                "hours_per_day": results.hours_per_day,
            },
            "schedule": {
                "mode": results.schedule_mode,
                "resource_constraints_active": results.resource_constraints_active,
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
            "calendar_time_confidence_intervals": {
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
            "effort_confidence_intervals": {
                str(p): {
                    "person_hours": v,
                    "person_days": math.ceil(v / results.hours_per_day),
                }
                for p, v in sorted(results.effort_percentiles.items())
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
            "constrained_diagnostics": {
                "resource_wait_time_hours": results.resource_wait_time_hours,
                "resource_utilization": results.resource_utilization,
                "calendar_delay_time_hours": results.calendar_delay_time_hours,
            },
            "two_pass_traceability": (
                results.two_pass_trace.to_dict()
                if results.two_pass_trace is not None
                else None
            ),
            "histogram": {
                "bin_edges": bin_edges.tolist(),
                "counts": counts.tolist(),
            },
            "staffing": JSONExporter._prepare_staffing_data(results, effective_config),
        }

        if results.costs is not None and (
            config is None or config.cost.include_in_output
        ):
            cost_section: Dict[str, Any] = {
                "currency": results.currency or "?",
                "mean": (
                    round(float(results.cost_mean), 2)
                    if results.cost_mean is not None
                    else None
                ),
                "std_dev": (
                    round(float(results.cost_std_dev), 2)
                    if results.cost_std_dev is not None
                    else None
                ),
                "percentiles": {
                    str(p): round(v, 2)
                    for p, v in (results.cost_percentiles or {}).items()
                },
                "overhead_rate": project.project.overhead_rate if project else None,
            }
            if results.task_costs and not full_cost_detail:
                cost_section["task_costs"] = {
                    task_id: {
                        "mean": round(float(np.mean(arr)), 2),
                        "p50": round(float(np.percentile(arr, 50)), 2),
                        "p90": round(float(np.percentile(arr, 90)), 2),
                    }
                    for task_id, arr in results.task_costs.items()
                }
            elif results.task_costs and full_cost_detail:
                cost_section["task_costs"] = {
                    task_id: arr.tolist() for task_id, arr in results.task_costs.items()
                }
            if results.cost_analysis is not None:
                cost_section["sensitivity"] = {
                    k: round(v, 4) for k, v in results.cost_analysis.sensitivity.items()
                }
                cost_section["duration_correlation"] = round(
                    results.cost_analysis.duration_correlation, 4
                )
            # Secondary currencies
            if fx_provider is not None:
                from mcprojsim.exchange_rates import ExchangeRateProvider as _ERP

                _provider: _ERP = fx_provider
                sec_list: list[Dict[str, Any]] = []
                for target in list(_provider.requested_targets):
                    info = _provider.rate_info(target)
                    if info is None:
                        sec_list.append(
                            {"currency": target, "error": "rate_unavailable"}
                        )
                        continue
                    adj = info["adjusted_rate"]
                    mean_val = (
                        round(float(results.cost_mean * adj), 2)
                        if results.cost_mean is not None
                        else None
                    )
                    pcts_sec = {
                        str(p): round(v * adj, 2)
                        for p, v in (results.cost_percentiles or {}).items()
                    }
                    sec_entry: Dict[str, Any] = {
                        "currency": target,
                        "official_rate": info["official_rate"],
                        "adjusted_rate": info["adjusted_rate"],
                        "fx_conversion_cost": info["fx_conversion_cost"],
                        "fx_overhead_rate": info["fx_overhead_rate"],
                        "source": info["source"],
                        "fetched_at": info["fetched_at"],
                        "mean": mean_val,
                        "percentiles": pcts_sec,
                    }
                    sec_list.append(sec_entry)
                cost_section["secondary_currencies"] = sec_list
            data["cost"] = cost_section

        # Budget confidence analysis (Phase 3)
        if (
            results.costs is not None
            and target_budget is not None
            and (config is None or config.cost.include_in_output)
        ):
            prob = results.probability_within_budget(target_budget)
            _, ci_lo, ci_hi = results.budget_confidence_interval(target_budget)
            budget_analysis: Dict[str, Any] = {
                "target_budget": target_budget,
                "currency": results.currency or "EUR",
                "probability_within_budget": round(prob, 4),
                "confidence_interval_95": [round(ci_lo, 4), round(ci_hi, 4)],
                "budget_for_p50": round(results.budget_for_confidence(0.50), 2),
                "budget_for_p80": round(results.budget_for_confidence(0.80), 2),
                "budget_for_p90": round(results.budget_for_confidence(0.90), 2),
            }
            if target_hours is not None:
                marginal_duration = float(np.mean(results.durations <= target_hours))
                budget_analysis["joint_analysis"] = {
                    "target_hours": round(target_hours, 2),
                    "target_budget": target_budget,
                    "joint_probability": round(
                        results.joint_probability(target_hours, target_budget), 4
                    ),
                    "marginal_duration_probability": round(marginal_duration, 4),
                    "marginal_budget_probability": round(prob, 4),
                }
            data["budget_analysis"] = budget_analysis

        if sprint_results is not None:
            sprint_payload: Dict[str, Any] = JSONExporter._prepare_sprint_data(
                sprint_results
            )
            if include_historic_base:
                historic_base = build_historic_base(project)
                if historic_base is not None:
                    sprint_payload["historic_base"] = historic_base
            data["sprint_planning"] = sprint_payload

        return data

    @staticmethod
    def _prepare_sprint_data(
        sprint_results: SprintPlanningResults,
    ) -> Dict[str, Any]:
        """Prepare sprint-planning data for JSON export."""
        sprint_data = sprint_results.to_dict()
        diagnostics = sprint_results.historical_diagnostics
        sprint_data["sprint_count_confidence_intervals"] = {
            str(percentile): {
                "sprints": value,
                "delivery_date": (
                    delivery_date.isoformat() if delivery_date is not None else None
                ),
            }
            for percentile, value in sorted(sprint_results.percentiles.items())
            for delivery_date in [sprint_results.date_percentiles.get(percentile)]
        }
        sprint_data["historical_series_statistics"] = diagnostics.get(
            "series_statistics",
            {},
        )
        sprint_data["ratio_summaries"] = diagnostics.get("ratios", {})
        sprint_data["historical_correlations"] = diagnostics.get("correlations", {})

        # Planning assumptions: explicitly surface future sprint capacity adjustments
        sprint_data["planning_assumptions"] = {
            "future_sprint_overrides": sprint_results.future_sprint_overrides,
            "notes": "Future sprint overrides reduce effective sprint capacity for the specified sprints. "
            "Effective multiplier = holiday_factor * capacity_multiplier.",
        }

        return sprint_data

    @staticmethod
    def _prepare_staffing_data(
        results: SimulationResults,
        config: Config,
    ) -> Dict[str, Any]:
        """Prepare staffing analysis data for JSON export."""
        recommendations = StaffingAnalyzer.recommend_team_size(results, config)
        table = StaffingAnalyzer.calculate_staffing_table(results, config)
        effort_basis = recommendations[0].effort_basis if recommendations else "mean"
        effort_hours_used = (
            round(recommendations[0].total_effort_hours, 2)
            if recommendations
            else round(results.total_effort_hours(), 2)
        )
        return {
            "effort_basis": effort_basis,
            "total_effort_hours": round(results.total_effort_hours(), 2),
            "effort_hours_used": effort_hours_used,
            "max_parallel_tasks": results.max_parallel_tasks,
            "recommendations": [r.to_dict() for r in recommendations],
            "table": [r.to_dict() for r in table],
        }
