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
@click.option("--quiet", "-q", is_flag=True, help="Suppress progress output")
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
def simulate(
    project_file: str,
    iterations: int,
    config: Optional[str],
    seed: Optional[int],
    output: Optional[str],
    output_format: str,
    critical_paths: Optional[int],
    quiet: bool,
    verbose: bool,
    target_date: Optional[str],
    table: bool,
) -> None:
    """Run Monte Carlo simulation for a project."""
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
            show_progress=not quiet,
        )
        results, elapsed_seconds, peak_memory_bytes = _run_simulation_with_metrics(
            engine, project
        )
        critical_path_limit = critical_paths or cfg.output.critical_path_report_limit

        click.echo(f"Simulation time: {elapsed_seconds:.2f} seconds")
        click.echo(
            "Peak simulation memory: " f"{_format_memory_size(peak_memory_bytes)}"
        )

        if not quiet:
            import math

            hours_per_day = results.hours_per_day
            mean_wd = math.ceil(results.mean / hours_per_day)
            cv = results.std_dev / results.mean if results.mean > 0 else 0

            click.echo("\n=== Simulation Results ===")

            if table:
                from tabulate import tabulate as _tabulate

                summary_rows = [
                    ["Project", results.project_name],
                    ["Hours per Day", f"{hours_per_day}"],
                    ["Mean", f"{results.mean:.2f} hours ({mean_wd} working days)"],
                    ["Median (P50)", f"{results.median:.2f} hours"],
                    ["Std Dev", f"{results.std_dev:.2f} hours"],
                    ["Coefficient of Variation", f"{cv:.4f}"],
                    ["Skewness", f"{results.skewness:.4f}"],
                    ["Excess Kurtosis", f"{results.kurtosis:.4f}"],
                ]
                click.echo(
                    _tabulate(
                        summary_rows,
                        headers=["Parameter", "Value"],
                        tablefmt="simple_outline",
                        disable_numparse=True,
                    )
                )
            else:
                click.echo(f"Project: {results.project_name}")
                click.echo(f"Hours per Day: {hours_per_day}")
                click.echo(f"Mean: {results.mean:.2f} hours ({mean_wd} working days)")
                click.echo(f"Median (P50): {results.median:.2f} hours")
                click.echo(f"Std Dev: {results.std_dev:.2f} hours")
                click.echo(f"Coefficient of Variation: {cv:.4f}")
                click.echo(f"Skewness: {results.skewness:.4f}")
                click.echo(f"Excess Kurtosis: {results.kurtosis:.4f}")

            if table:
                # Confidence Intervals table
                ci_rows = []
                for p in sorted(results.percentiles.keys()):
                    hours = results.percentiles[p]
                    wd = math.ceil(hours / hours_per_day)
                    delivery = results.delivery_date(hours)
                    date_str = delivery.isoformat() if delivery else ""
                    ci_rows.append([f"P{p}", f"{hours:.2f}", wd, date_str])
                click.echo("\nConfidence Intervals:")
                click.echo(
                    _tabulate(
                        ci_rows,
                        headers=["Percentile", "Hours", "Working Days", "Date"],
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

            else:
                # Plain text output
                click.echo("\nConfidence Intervals:")
                for p in sorted(results.percentiles.keys()):
                    hours = results.percentiles[p]
                    wd = math.ceil(hours / hours_per_day)
                    delivery = results.delivery_date(hours)
                    date_str = f"  ({delivery.isoformat()})" if delivery else ""
                    click.echo(
                        f"  P{p}: {hours:.2f} hours" f" ({wd} working days){date_str}"
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

            # Probability of target date
            if target_date:
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
                    if not quiet:
                        click.echo(f"\nResults exported to {output_file}")
                elif fmt == "csv":
                    output_file = base_output.with_suffix(".csv")
                    CSVExporter.export(
                        results,
                        output_file,
                        config=cfg,
                        critical_path_limit=critical_path_limit,
                    )
                    if not quiet:
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
                    if not quiet:
                        click.echo(f"Results exported to {output_file}")
                else:
                    if not quiet:
                        click.echo(f"Warning: Unknown format '{fmt}' ignored")
        else:
            if not quiet:
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
