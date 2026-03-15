"""Command-line interface for Monte Carlo Project Simulator."""

from pathlib import Path
import sys
import time
from typing import Optional, Union

import click

from mcprojsim import __version__
from mcprojsim.config import Config, DEFAULT_SIMULATION_ITERATIONS
from mcprojsim.exporters import CSVExporter, HTMLExporter, JSONExporter
from mcprojsim.models.project import Project
from mcprojsim.models.simulation import SimulationResults
from mcprojsim.parsers import TOMLParser, YAMLParser
from mcprojsim.simulation import SimulationEngine
from mcprojsim.utils import Validator, setup_logging


def _get_max_rss_bytes() -> int | None:
    """Return the process peak resident set size in bytes when available."""
    try:
        import resource
    except ImportError:
        return None

    max_rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if max_rss < 0:
        return None

    # macOS reports bytes, while Linux and several other Unix platforms
    # report kibibytes.
    if sys.platform == "darwin":
        return max_rss

    return max_rss * 1024


def _format_memory_size(num_bytes: int | None) -> str:
    """Format a memory size in human-readable binary units."""
    if num_bytes is None:
        return "unavailable"

    value = float(num_bytes)
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024.0

    return f"{value:.2f} TiB"


def _run_simulation_with_metrics(
    engine: SimulationEngine,
    project: Project,
) -> tuple[SimulationResults, float, int | None]:
    """Run a simulation and collect elapsed time and peak memory delta."""
    rss_before = _get_max_rss_bytes()
    started_at = time.perf_counter()
    results = engine.run(project)
    elapsed_seconds = time.perf_counter() - started_at
    rss_after = _get_max_rss_bytes()

    peak_memory_bytes = None
    if rss_before is not None and rss_after is not None:
        peak_memory_bytes = max(0, rss_after - rss_before)

    return results, elapsed_seconds, peak_memory_bytes


@click.group()
@click.version_option(version=__version__, prog_name="mcprojsim")
def cli() -> None:
    """Monte Carlo Project Simulator - Probabilistic project estimation."""
    pass


@cli.command()
@click.argument("project_file", type=click.Path(exists=True))
@click.option(
    "--iterations",
    "-n",
    type=int,
    default=DEFAULT_SIMULATION_ITERATIONS,
    help="Number of simulation iterations",
)
@click.option("--config", "-c", type=click.Path(exists=True), help="Configuration file")
@click.option("--seed", "-s", type=int, help="Random seed for reproducibility")
@click.option(
    "--output", "-o", type=click.Path(), help="Output file path (without extension)"
)
@click.option(
    "--output-format",
    "-f",
    default="",
    help="Output formats (comma-separated: json,csv,html). If not specified, only CLI output is shown.",
)
@click.option(
    "--critical-paths",
    type=int,
    help="Number of full critical path sequences to include in CLI output and exports.",
)
@click.option(
    "--quiet",
    "-q",
    count=True,
    help=(
        "Reduce CLI output verbosity. Use -q to suppress detailed output and "
        "-qq to suppress all normal output."
    ),
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed informational messages.",
)
@click.option(
    "--target-date",
    type=str,
    default=None,
    help="Target completion date (YYYY-MM-DD) to calculate probability of meeting.",
)
@click.option(
    "--table",
    "-t",
    is_flag=True,
    help="Format tabular output sections as ASCII tables.",
)
@click.option(
    "--staffing",
    is_flag=True,
    help="Show full staffing analysis table with team-size recommendations.",
)
@click.option(
    "--minimal",
    "-m",
    is_flag=True,
    help=(
        "Show minimal output: version, project overview, calendar/effort "
        "statistical summaries, and calendar confidence intervals only."
    ),
)
def simulate(
    project_file: str,
    iterations: int,
    config: Optional[str],
    seed: Optional[int],
    output: Optional[str],
    output_format: str,
    critical_paths: Optional[int],
    quiet: int,
    verbose: bool,
    target_date: Optional[str],
    table: bool,
    staffing: bool,
    minimal: bool,
) -> None:
    """Run Monte Carlo simulation for a project."""
    if quiet < 2:
        click.echo(f"mcprojsim, version {__version__}")
    logger = setup_logging(level="INFO" if verbose else "WARNING")

    try:
        # Load configuration
        if config:
            cfg = Config.load_from_file(config)
            logger.info(f"Loaded configuration from {config}")
        else:
            cfg = Config.get_default()
            logger.info("Using default configuration")

        # Parse project file
        project_path = Path(project_file)
        parser: Union[YAMLParser, TOMLParser]
        if project_path.suffix in [".yaml", ".yml"]:
            parser = YAMLParser()
        elif project_path.suffix == ".toml":
            parser = TOMLParser()
        else:
            click.echo(f"Error: Unsupported file format {project_path.suffix}")
            return

        logger.info(f"Loading project from {project_file}")
        project = parser.parse_file(project_file)
        logger.info(f"Loaded project: {project.project.name}")

        # Run simulation
        logger.info(f"Running simulation with {iterations} iterations")
        engine = SimulationEngine(
            iterations=iterations,
            random_seed=seed,
            config=cfg,
            show_progress=quiet == 0,
        )
        results, elapsed_seconds, peak_memory_bytes = _run_simulation_with_metrics(
            engine, project
        )
        critical_path_limit = critical_paths or cfg.output.critical_path_report_limit

        if quiet < 2 and not minimal:
            click.echo(f"Simulation time: {elapsed_seconds:.2f} seconds")
            click.echo(
                "Peak simulation memory: " f"{_format_memory_size(peak_memory_bytes)}"
            )

        if quiet == 0:
            import math

            from tabulate import tabulate as _tabulate

            hours_per_day = results.hours_per_day
            mean_wd = math.ceil(results.mean / hours_per_day)
            cv = results.std_dev / results.mean if results.mean > 0 else 0
            min_duration = getattr(results, "min_duration", results.mean)
            max_duration = getattr(results, "max_duration", results.mean)
            schedule_mode = getattr(results, "schedule_mode", "dependency_only")
            constraints_active = getattr(
                results,
                "resource_constraints_active",
                False,
            )
            resource_wait_time_hours = getattr(results, "resource_wait_time_hours", 0.0)
            resource_utilization = getattr(results, "resource_utilization", 0.0)
            calendar_delay_time_hours = getattr(
                results,
                "calendar_delay_time_hours",
                0.0,
            )

            effort_durations = getattr(results, "effort_durations", None)
            effort_stats: dict[str, float | int]
            if effort_durations is not None and len(effort_durations) > 0:
                import numpy as np
                from scipy import stats as scipy_stats

                effort_arr = np.asarray(effort_durations)
                effort_mean = float(np.mean(effort_arr))
                effort_std = float(np.std(effort_arr))
                effort_stats = {
                    "mean": effort_mean,
                    "median": float(np.median(effort_arr)),
                    "std_dev": effort_std,
                    "min": float(np.min(effort_arr)),
                    "max": float(np.max(effort_arr)),
                    "cv": effort_std / effort_mean if effort_mean > 0 else 0.0,
                    "skewness": (
                        float(scipy_stats.skew(effort_arr)) if effort_std > 0 else 0.0
                    ),
                    "kurtosis": (
                        float(scipy_stats.kurtosis(effort_arr))
                        if effort_std > 0
                        else 0.0
                    ),
                    "mean_person_days": math.ceil(effort_mean / hours_per_day),
                }
            else:
                effort_mean_fallback = float(results.total_effort_hours())
                effort_stats = {
                    "mean": effort_mean_fallback,
                    "median": effort_mean_fallback,
                    "std_dev": 0.0,
                    "min": effort_mean_fallback,
                    "max": effort_mean_fallback,
                    "cv": 0.0,
                    "skewness": 0.0,
                    "kurtosis": 0.0,
                    "mean_person_days": math.ceil(effort_mean_fallback / hours_per_day),
                }

            click.echo("\n=== Simulation Results ===")

            if table:
                common_rows = [
                    ["Project", results.project_name],
                    ["Hours per Day", f"{hours_per_day}"],
                    ["Max Parallel Tasks", f"{results.max_parallel_tasks}"],
                    ["Schedule Mode", schedule_mode],
                ]
                calendar_summary_rows = [
                    ["Mean", f"{results.mean:.2f} hours ({mean_wd} working days)"],
                    ["Median (P50)", f"{results.median:.2f} hours"],
                    ["Std Dev", f"{results.std_dev:.2f} hours"],
                    ["Minimum", f"{min_duration:.2f} hours"],
                    ["Maximum", f"{max_duration:.2f} hours"],
                    ["Coefficient of Variation", f"{cv:.4f}"],
                    ["Skewness", f"{results.skewness:.4f}"],
                    ["Excess Kurtosis", f"{results.kurtosis:.4f}"],
                ]
                effort_summary_rows = [
                    [
                        "Mean",
                        (
                            f"{effort_stats['mean']:.2f} person-hours "
                            f"({effort_stats['mean_person_days']} person-days)"
                        ),
                    ],
                    ["Median (P50)", f"{effort_stats['median']:.2f} person-hours"],
                    ["Std Dev", f"{effort_stats['std_dev']:.2f} person-hours"],
                    ["Minimum", f"{effort_stats['min']:.2f} person-hours"],
                    ["Maximum", f"{effort_stats['max']:.2f} person-hours"],
                    ["Coefficient of Variation", f"{effort_stats['cv']:.4f}"],
                    ["Skewness", f"{effort_stats['skewness']:.4f}"],
                    ["Excess Kurtosis", f"{effort_stats['kurtosis']:.4f}"],
                ]
                click.echo("\nProject Overview:")
                click.echo(
                    _tabulate(
                        common_rows,
                        headers=["Field", "Value"],
                        tablefmt="simple_outline",
                        disable_numparse=True,
                    )
                )
                click.echo("\nCalendar Time Statistical Summary:")
                click.echo(
                    _tabulate(
                        calendar_summary_rows,
                        headers=["Metric", "Value"],
                        tablefmt="simple_outline",
                        disable_numparse=True,
                    )
                )
                click.echo("\nProject Effort Statistical Summary:")
                click.echo(
                    _tabulate(
                        effort_summary_rows,
                        headers=["Metric", "Value"],
                        tablefmt="simple_outline",
                        disable_numparse=True,
                    )
                )
            else:
                click.echo("\nProject Overview:")
                click.echo(f"Project: {results.project_name}")
                click.echo(f"Hours per Day: {hours_per_day}")
                click.echo(f"Max Parallel Tasks: {results.max_parallel_tasks}")
                click.echo(f"Schedule Mode: {schedule_mode}")

                click.echo("\nCalendar Time Statistical Summary:")
                click.echo(f"Mean: {results.mean:.2f} hours ({mean_wd} working days)")
                click.echo(f"Median (P50): {results.median:.2f} hours")
                click.echo(f"Std Dev: {results.std_dev:.2f} hours")
                click.echo(f"Minimum: {min_duration:.2f} hours")
                click.echo(f"Maximum: {max_duration:.2f} hours")
                click.echo(f"Coefficient of Variation: {cv:.4f}")
                click.echo(f"Skewness: {results.skewness:.4f}")
                click.echo(f"Excess Kurtosis: {results.kurtosis:.4f}")

                click.echo("\nProject Effort Statistical Summary:")
                click.echo(
                    "Mean: "
                    f"{effort_stats['mean']:.2f} person-hours "
                    f"({effort_stats['mean_person_days']} person-days)"
                )
                click.echo(f"Median (P50): {effort_stats['median']:.2f} person-hours")
                click.echo(f"Std Dev: {effort_stats['std_dev']:.2f} person-hours")
                click.echo(f"Minimum: {effort_stats['min']:.2f} person-hours")
                click.echo(f"Maximum: {effort_stats['max']:.2f} person-hours")
                click.echo(f"Coefficient of Variation: {effort_stats['cv']:.4f}")
                click.echo(f"Skewness: {effort_stats['skewness']:.4f}")
                click.echo(f"Excess Kurtosis: {effort_stats['kurtosis']:.4f}")

            if table:
                # Confidence Intervals table
                ci_rows = []
                for p in sorted(results.percentiles.keys()):
                    hours = results.percentiles[p]
                    wd = math.ceil(hours / hours_per_day)
                    delivery = results.delivery_date(hours)
                    date_str = delivery.isoformat() if delivery else ""
                    ci_rows.append([f"P{p}", f"{hours:.2f}", wd, date_str])
                click.echo("\nCalendar Time Confidence Intervals:")
                click.echo(
                    _tabulate(
                        ci_rows,
                        headers=["Percentile", "Hours", "Working Days", "Date"],
                        tablefmt="simple_outline",
                    )
                )

                if not minimal:
                    # Effort confidence intervals table
                    if results.effort_percentiles:
                        effort_rows = []
                        for p in sorted(results.effort_percentiles.keys()):
                            eh = results.effort_percentiles[p]
                            epd = math.ceil(eh / hours_per_day)
                            effort_rows.append([f"P{p}", f"{eh:.2f}", epd])
                        click.echo("\nEffort Confidence Intervals:")
                        click.echo(
                            _tabulate(
                                effort_rows,
                                headers=["Percentile", "Person-Hours", "Person-Days"],
                                tablefmt="simple_outline",
                            )
                        )

                    # Sensitivity analysis table
                    if results.sensitivity:
                        sorted_sens = sorted(
                            results.sensitivity.items(),
                            key=lambda x: abs(x[1]),
                            reverse=True,
                        )
                        sens_rows = [
                            [tid, f"{corr:+.4f}"] for tid, corr in sorted_sens[:10]
                        ]
                        click.echo("\nSensitivity Analysis (top contributors):")
                        click.echo(
                            _tabulate(
                                sens_rows,
                                headers=["Task", "Correlation"],
                                tablefmt="simple_outline",
                                disable_numparse=True,
                            )
                        )

                    # Schedule slack table
                    if results.task_slack:
                        slack_rows = []
                        for task_id, slack_val in sorted(
                            results.task_slack.items(), key=lambda x: x[1]
                        ):
                            status = (
                                "Critical"
                                if slack_val < 0.01
                                else f"{slack_val:.1f}h buffer"
                            )
                            slack_rows.append([task_id, f"{slack_val:.2f}", status])
                        click.echo("\nSchedule Slack:")
                        click.echo(
                            _tabulate(
                                slack_rows,
                                headers=["Task", "Slack (hours)", "Status"],
                                tablefmt="simple_outline",
                                disable_numparse=True,
                            )
                        )

                    # Risk impact table
                    risk_summary = results.get_risk_impact_summary()
                    has_risk_data = any(
                        s["trigger_rate"] > 0 for s in risk_summary.values()
                    )
                    if has_risk_data:
                        risk_rows = []
                        for task_id, stats in sorted(risk_summary.items()):
                            if stats["trigger_rate"] > 0:
                                risk_rows.append(
                                    [
                                        task_id,
                                        f"{stats['mean_impact']:.2f}",
                                        f"{stats['trigger_rate']*100:.1f}%",
                                        f"{stats['mean_when_triggered']:.2f}",
                                    ]
                                )
                        click.echo("\nRisk Impact Analysis:")
                        click.echo(
                            _tabulate(
                                risk_rows,
                                headers=[
                                    "Task",
                                    "Mean (hours)",
                                    "Trigger Rate",
                                    "Mean When Triggered (hours)",
                                ],
                                tablefmt="simple_outline",
                            )
                        )

                    if constraints_active:
                        diagnostics_rows = [
                            [
                                "Average Resource Wait (hours)",
                                f"{resource_wait_time_hours:.2f}",
                            ],
                            [
                                "Effective Resource Utilization",
                                f"{resource_utilization*100:.1f}%",
                            ],
                            [
                                "Calendar Delay Contribution (hours)",
                                f"{calendar_delay_time_hours:.2f}",
                            ],
                        ]
                        click.echo("\nConstrained Schedule Diagnostics:")
                        click.echo(
                            _tabulate(
                                diagnostics_rows,
                                headers=["Metric", "Value"],
                                tablefmt="simple_outline",
                                disable_numparse=True,
                            )
                        )

            else:
                # Plain text output
                click.echo("\nCalendar Time Confidence Intervals:")
                for p in sorted(results.percentiles.keys()):
                    hours = results.percentiles[p]
                    wd = math.ceil(hours / hours_per_day)
                    delivery = results.delivery_date(hours)
                    date_str = f"  ({delivery.isoformat()})" if delivery else ""
                    click.echo(
                        f"  P{p}: {hours:.2f} hours" f" ({wd} working days){date_str}"
                    )

                if not minimal:
                    # Effort confidence intervals (plain-text)
                    if results.effort_percentiles:
                        click.echo("\nEffort Confidence Intervals:")
                        for p in sorted(results.effort_percentiles.keys()):
                            eh = results.effort_percentiles[p]
                            epd = math.ceil(eh / hours_per_day)
                            click.echo(
                                f"  P{p}: {eh:.2f} person-hours" f" ({epd} person-days)"
                            )

                    # Sensitivity analysis
                    if results.sensitivity:
                        click.echo("\nSensitivity Analysis (top contributors):")
                        sorted_sens = sorted(
                            results.sensitivity.items(),
                            key=lambda x: abs(x[1]),
                            reverse=True,
                        )
                        for task_id, corr in sorted_sens[:10]:
                            click.echo(f"  {task_id}: {corr:+.4f}")

                    # Schedule slack
                    if results.task_slack:
                        click.echo("\nSchedule Slack:")
                        for task_id, slack_val in sorted(
                            results.task_slack.items(), key=lambda x: x[1]
                        ):
                            status = (
                                "Critical"
                                if slack_val < 0.01
                                else f"{slack_val:.1f}h buffer"
                            )
                            click.echo(f"  {task_id}: {slack_val:.2f} hours ({status})")

                    # Risk impact summary
                    risk_summary = results.get_risk_impact_summary()
                    has_risk_data = any(
                        s["trigger_rate"] > 0 for s in risk_summary.values()
                    )
                    if has_risk_data:
                        click.echo("\nRisk Impact Analysis:")
                        for task_id, stats in sorted(risk_summary.items()):
                            if stats["trigger_rate"] > 0:
                                click.echo(
                                    f"  {task_id}: mean={stats['mean_impact']:.2f}h, "
                                    f"triggers={stats['trigger_rate']*100:.1f}%, "
                                    f"mean_when_triggered={stats['mean_when_triggered']:.2f}h"
                                )

                    if constraints_active:
                        click.echo("\nConstrained Schedule Diagnostics:")
                        click.echo(
                            "  Average Resource Wait: "
                            f"{resource_wait_time_hours:.2f} hours"
                        )
                        click.echo(
                            "  Effective Resource Utilization: "
                            f"{resource_utilization*100:.1f}%"
                        )
                        click.echo(
                            "  Calendar Delay Contribution: "
                            f"{calendar_delay_time_hours:.2f} hours"
                        )

            # Probability of target date
            if target_date and not minimal:
                from datetime import date as date_type

                try:
                    target = date_type.fromisoformat(target_date)
                    if results.start_date:
                        # Count working days between start and target
                        working_days = 0
                        current = results.start_date
                        from datetime import timedelta

                        while current < target:
                            current += timedelta(days=1)
                            if current.weekday() < 5:
                                working_days += 1
                        target_hours = working_days * hours_per_day
                        prob = results.probability_of_completion(target_hours)
                        click.echo(
                            f"\nProbability of completing by {target_date}: "
                            f"{prob*100:.1f}% ({working_days} working days, {target_hours:.0f} hours)"
                        )
                    else:
                        click.echo(
                            f"\nCannot compute probability for {target_date}: no start_date in project"
                        )
                except ValueError:
                    click.echo(f"\nInvalid target date format: {target_date}")

            if not minimal:
                critical_path_records = results.get_critical_path_sequences(
                    critical_path_limit
                )
                if critical_path_records:
                    click.echo("\nMost Frequent Critical Paths:")
                    for index, record in enumerate(critical_path_records, start=1):
                        click.echo(
                            "  "
                            f"{index}. {record.format_path()} "
                            f"({record.count}/{results.iterations}, {record.frequency * 100:.1f}%)"
                        )

            # --- Staffing advisory (always shown) and full table (--staffing) ---
            if not minimal:
                from mcprojsim.analysis.staffing import StaffingAnalyzer

                staffing_recs = StaffingAnalyzer.recommend_team_size(results, cfg)
                if staffing_recs:
                    # Default advisory uses the 'mixed' profile if present,
                    # otherwise the first profile alphabetically.
                    mixed_recs = [r for r in staffing_recs if r.profile == "mixed"]
                    advisory = mixed_recs[0] if mixed_recs else staffing_recs[0]
                    total_effort = advisory.total_effort_hours
                    total_effort_wd = math.ceil(total_effort / hours_per_day)
                    basis_label = (
                        f"{advisory.effort_basis} effort"
                        if advisory.effort_basis == "mean"
                        else f"{advisory.effort_basis} effort percentile"
                    )

                    click.echo(
                        f"\nStaffing (based on {basis_label}): "
                        f"{advisory.recommended_team_size} people "
                        f"recommended ({advisory.profile} team), "
                        f"{advisory.calendar_working_days} working days"
                    )
                    click.echo(
                        f"  Total effort: {total_effort:,.0f} person-hours "
                        f"({total_effort_wd} person-days) | "
                        f"Parallelism ratio: {advisory.parallelism_ratio:.1f}"
                    )

                if staffing and staffing_recs:
                    staffing_table = StaffingAnalyzer.calculate_staffing_table(
                        results, cfg
                    )
                    profiles_sorted = sorted({r.profile for r in staffing_recs})
                    for prof in profiles_sorted:
                        prof_rows = [r for r in staffing_table if r.profile == prof]
                        rec = next(
                            (r for r in staffing_recs if r.profile == prof), None
                        )
                        rec_n = rec.recommended_team_size if rec else 0
                        click.echo(
                            f"\nStaffing Analysis ({prof} team, "
                            f"overhead={cfg.staffing.experience_profiles[prof].communication_overhead:.0%}/person, "
                            f"productivity={cfg.staffing.experience_profiles[prof].productivity_factor:.0%}):"
                        )
                        if rec:
                            eb = rec.effort_basis
                            eb_label = "mean" if eb == "mean" else f"{eb} percentile"
                            click.echo(
                                f"  Effort basis: {eb_label} "
                                f"({rec.total_effort_hours:,.0f} person-hours, "
                                f"{rec.critical_path_hours:,.0f} critical-path hours)"
                            )
                        if table:
                            st_rows = []
                            for r in prof_rows:
                                marker = " *" if r.team_size == rec_n else ""
                                date_str = (
                                    r.delivery_date.isoformat()
                                    if r.delivery_date
                                    else ""
                                )
                                st_rows.append(
                                    [
                                        f"{r.team_size}{marker}",
                                        f"{r.effective_capacity:.2f}",
                                        f"{r.calendar_working_days}",
                                        date_str,
                                        f"{r.efficiency * 100:.1f}%",
                                    ]
                                )
                            click.echo(
                                _tabulate(
                                    st_rows,
                                    headers=[
                                        "Team Size",
                                        "Eff. Capacity",
                                        "Working Days",
                                        "Delivery Date",
                                        "Efficiency",
                                    ],
                                    tablefmt="simple_outline",
                                    disable_numparse=True,
                                )
                            )
                        else:
                            for r in prof_rows:
                                marker = (
                                    "  <-- recommended" if r.team_size == rec_n else ""
                                )
                                date_str = (
                                    f"  ({r.delivery_date.isoformat()})"
                                    if r.delivery_date
                                    else ""
                                )
                                click.echo(
                                    f"  {r.team_size} people: "
                                    f"{r.calendar_working_days} working days, "
                                    f"eff. capacity {r.effective_capacity:.2f}, "
                                    f"efficiency {r.efficiency * 100:.1f}%"
                                    f"{date_str}{marker}"
                                )

        # Export results (only if formats are explicitly specified)
        if output_format.strip():
            formats = [f.strip().lower() for f in output_format.split(",") if f.strip()]
            base_output = (
                Path(output) if output else Path(f"{project.project.name}_results")
            )

            for fmt in formats:
                if fmt == "json":
                    output_file = base_output.with_suffix(".json")
                    JSONExporter.export(
                        results,
                        output_file,
                        config=cfg,
                        critical_path_limit=critical_path_limit,
                    )
                    if quiet == 0 and not minimal:
                        click.echo(f"\nResults exported to {output_file}")
                elif fmt == "csv":
                    output_file = base_output.with_suffix(".csv")
                    CSVExporter.export(
                        results,
                        output_file,
                        config=cfg,
                        critical_path_limit=critical_path_limit,
                    )
                    if quiet == 0 and not minimal:
                        click.echo(f"Results exported to {output_file}")
                elif fmt == "html":
                    output_file = base_output.with_suffix(".html")
                    HTMLExporter.export(
                        results,
                        output_file,
                        project=project,
                        config=cfg,
                        critical_path_limit=critical_path_limit,
                    )
                    if quiet == 0 and not minimal:
                        click.echo(f"Results exported to {output_file}")
                else:
                    if quiet == 0 and not minimal:
                        click.echo(f"Warning: Unknown format '{fmt}' ignored")
        else:
            if quiet == 0 and not minimal:
                click.echo(
                    "\nNo export formats specified. Use -f to export results to files."
                )

    except Exception as e:
        logger.error(f"Error during simulation: {e}")
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.argument("project_file", type=click.Path(exists=True))
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed informational messages.",
)
def validate(project_file: str, verbose: bool) -> None:
    """Validate a project definition file."""
    logger = setup_logging(level="INFO" if verbose else "WARNING")

    click.echo(f"Validating {project_file}...")

    is_valid, error_message = Validator.validate_file(project_file)

    if is_valid:
        click.echo("✓ Project file is valid!")
        logger.info(f"Project file {project_file} is valid")
    else:
        click.echo("✗ Validation failed:", err=True)
        click.echo(f"  {error_message}", err=True)
        logger.error(f"Validation failed for {project_file}: {error_message}")
        raise click.Abort()


@cli.group()
def config() -> None:
    """Configuration management commands."""
    pass


@config.command(name="show")
@click.option("--config-file", "-c", type=click.Path(exists=True), help="Config file")
def show_config(config_file: Optional[str]) -> None:
    """Show current configuration."""
    if config_file:
        cfg = Config.load_from_file(config_file)
        click.echo(f"Configuration from {config_file}:")
    else:
        cfg = Config.get_default()
        click.echo("Default configuration:")

    click.echo("\nUncertainty Factors:")
    for factor_name, levels in cfg.uncertainty_factors.items():
        click.echo(f"  {factor_name}:")
        for level, value in levels.items():
            click.echo(f"    {level}: {value}")

    click.echo(f"\nT-Shirt Sizes (unit: {cfg.t_shirt_size_unit.value}):")
    for size, config in cfg.t_shirt_sizes.items():
        click.echo(f"  {size}:")
        click.echo(
            f"    min: {config.min}, most_likely: {config.most_likely}, max: {config.max}"
        )

    click.echo(f"\nStory Points (unit: {cfg.story_point_unit.value}):")
    for points, sp_config in sorted(cfg.story_points.items()):
        click.echo(f"  {points}:")
        click.echo(
            f"    min: {sp_config.min}, most_likely: {sp_config.most_likely}, max: {sp_config.max}"
        )

    click.echo("\nSimulation:")
    click.echo(f"  Default iterations: {cfg.simulation.default_iterations}")
    click.echo(f"  Random seed: {cfg.simulation.random_seed}")
    click.echo(
        "  Max stored critical paths: " f"{cfg.simulation.max_stored_critical_paths}"
    )

    click.echo("\nOutput:")
    click.echo(f"  Formats: {', '.join(cfg.output.formats)}")
    click.echo(f"  Include histogram: {cfg.output.include_histogram}")
    click.echo(f"  Histogram bins: {cfg.output.histogram_bins}")
    click.echo(
        "  Critical path report limit: " f"{cfg.output.critical_path_report_limit}"
    )


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output YAML file path (default: print to stdout)",
)
@click.option(
    "--validate-only",
    is_flag=True,
    help="Only validate the description, do not generate YAML",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed informational messages.",
)
def generate(
    input_file: str,
    output: Optional[str],
    validate_only: bool,
    verbose: bool,
) -> None:
    """Generate a project YAML file from a natural language description.

    Reads a plain-text project description from INPUT_FILE and produces
    a syntactically correct mcprojsim project specification in YAML format.
    """
    from mcprojsim.nl_parser import NLProjectParser

    logger = setup_logging(level="INFO" if verbose else "WARNING")
    input_path = Path(input_file)
    text = input_path.read_text(encoding="utf-8")

    parser = NLProjectParser()

    try:
        project = parser.parse(text)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        logger.error(f"Failed to parse {input_file}: {e}")
        raise click.Abort()

    if validate_only:
        issues: list[str] = []
        if project.name == "Untitled Project":
            issues.append("No project name found (will default to 'Untitled Project')")
        if not project.start_date:
            issues.append("No start date specified")
        task_nums = {t.number for t in project.tasks}
        for task in project.tasks:
            has_estimate = (
                task.t_shirt_size is not None
                or task.story_points is not None
                or task.min_estimate is not None
            )
            if not has_estimate:
                issues.append(f"Task {task.number} ('{task.name}') has no estimate")
            for ref in task.dependency_refs:
                if int(ref) not in task_nums:
                    issues.append(
                        f"Task {task.number} depends on Task {ref}, which does not exist"
                    )
        if issues:
            click.echo("Validation issues:")
            for issue in issues:
                click.echo(f"  ⚠ {issue}")
        else:
            click.echo(f"✓ Valid: '{project.name}' with {len(project.tasks)} task(s)")
        return

    yaml_output = parser.to_yaml(project)

    if output:
        output_path = Path(output)
        output_path.write_text(yaml_output, encoding="utf-8")
        click.echo(f"✓ Generated {output_path} ({len(project.tasks)} tasks)")
        logger.info(f"Generated project file {output_path} from {input_file}")
    else:
        click.echo(yaml_output)


if __name__ == "__main__":
    cli()
