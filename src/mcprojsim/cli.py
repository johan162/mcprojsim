"""Command-line interface for Monte Carlo Project Simulator."""

from pathlib import Path
import sys
import time
from typing import Optional, Union

import click
import yaml

from mcprojsim import __version__
from mcprojsim.config import (
    Config,
    DEFAULT_SIMULATION_ITERATIONS,
    DEFAULT_SPRINT_PLANNING_CONFIDENCE_LEVEL,
    DEFAULT_SPRINT_REMOVED_WORK_TREATMENT,
    DEFAULT_SPRINT_SICKNESS_DURATION_LOG_MU,
    DEFAULT_SPRINT_SICKNESS_DURATION_LOG_SIGMA,
    DEFAULT_SPRINT_SICKNESS_PROBABILITY_PER_PERSON_PER_WEEK,
    DEFAULT_SPRINT_SPILLOVER_CONSUMED_FRACTION_ALPHA,
    DEFAULT_SPRINT_SPILLOVER_CONSUMED_FRACTION_BETA,
    DEFAULT_SPRINT_SPILLOVER_LOGISTIC_INTERCEPT,
    DEFAULT_SPRINT_SPILLOVER_LOGISTIC_SLOPE,
    DEFAULT_SPRINT_SPILLOVER_MODEL,
    DEFAULT_SPRINT_SPILLOVER_SIZE_REFERENCE_POINTS,
    DEFAULT_SPRINT_VELOCITY_MODEL,
    DEFAULT_SPRINT_VOLATILITY_DISRUPTION_MULTIPLIER_EXPECTED,
    DEFAULT_SPRINT_VOLATILITY_DISRUPTION_MULTIPLIER_HIGH,
    DEFAULT_SPRINT_VOLATILITY_DISRUPTION_MULTIPLIER_LOW,
    DEFAULT_SPRINT_VOLATILITY_DISRUPTION_PROBABILITY,
)
from mcprojsim.exporters import CSVExporter, HTMLExporter, JSONExporter
from mcprojsim.models.project import Project
from mcprojsim.models.simulation import SimulationResults
from mcprojsim.models.sprint_simulation import SprintPlanningResults
from mcprojsim.parsers import TOMLParser, YAMLParser
from mcprojsim.planning.sprint_engine import SprintSimulationEngine
from mcprojsim.simulation import SimulationEngine
from mcprojsim.simulation.distributions import fit_shifted_lognormal
from mcprojsim.utils import Validator, setup_logging


def _get_user_default_config_path() -> Path:
    """Return the default user-level configuration file path."""
    return Path.home() / ".mcprojsim" / "configuration.yaml"


def _get_generated_default_config_path() -> Path:
    """Return the output path for generated default configuration."""
    return Path.home() / ".mcprojsim" / "config.yaml"


def _load_config_with_user_default(
    config_file: Optional[str],
) -> tuple[Config, Path | None]:
    """Load config with precedence: CLI file > user default file > built-in defaults."""
    if config_file:
        config_path = Path(config_file)
        return Config.load_from_file(config_path), config_path

    user_config_path = _get_user_default_config_path()
    if user_config_path.exists():
        return Config.load_from_file(user_config_path), user_config_path

    return Config.get_default(), None


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


def _format_shifted_lognormal_parameters(
    label: str,
    low: float,
    expected: float,
    high: float,
    z_score: float,
) -> str:
    """Format shifted-lognormal parameters derived from a configured range."""
    try:
        mu, sigma = fit_shifted_lognormal(low, expected, high, z_score)
    except ValueError as exc:
        raise click.ClickException(
            f"Cannot derive log-normal parameters for {label}: {exc}"
        ) from exc

    return f"mu: {mu:.4f}, sigma: {sigma:.4f}, z-score: {z_score:.4f}"


def _run_sprint_simulation_with_metrics(
    engine: SprintSimulationEngine,
    project: Project,
) -> tuple[SprintPlanningResults, float, int | None]:
    """Run sprint planning and collect elapsed time and peak memory delta."""
    rss_before = _get_max_rss_bytes()
    started_at = time.perf_counter()
    results = engine.run(project)
    elapsed_seconds = time.perf_counter() - started_at
    rss_after = _get_max_rss_bytes()

    peak_memory_bytes = None
    if rss_before is not None and rss_after is not None:
        peak_memory_bytes = max(0, rss_after - rss_before)

    return results, elapsed_seconds, peak_memory_bytes


def _echo_sprint_results(
    sprint_results: SprintPlanningResults,
    table: bool,
    minimal: bool,
) -> None:
    """Print sprint-planning results to the CLI."""
    import math

    if table:
        from tabulate import tabulate as _tabulate

        summary_rows = [
            ["Sprint Length", f"{sprint_results.sprint_length_weeks} weeks"],
            [
                "Planning Confidence Level",
                f"{sprint_results.planning_confidence_level * 100:.0f}%",
            ],
            ["Removed Work Treatment", sprint_results.removed_work_treatment],
            [
                "Velocity Model",
                str(
                    sprint_results.historical_diagnostics.get(
                        "velocity_model", "empirical"
                    )
                ),
            ],
            [
                "Planned Commitment Guidance",
                f"{sprint_results.planned_commitment_guidance:.2f}",
            ],
            [
                "Historical Sampling Mode",
                str(sprint_results.historical_diagnostics.get("sampling_mode", "")),
            ],
            [
                "Historical Observations",
                str(sprint_results.historical_diagnostics.get("observation_count", 0)),
            ],
            [
                "Carryover Mean",
                f"{sprint_results.carryover_statistics.get('mean', 0.0):.2f}",
            ],
            [
                "Aggregate Spillover Rate",
                f"{sprint_results.spillover_statistics.get('aggregate_spillover_rate', {}).get('mean', 0.0):.4f}",
            ],
            [
                "Observed Disruption Frequency",
                f"{sprint_results.disruption_statistics.get('observed_frequency', 0.0):.4f}",
            ],
        ]
        sickness_diag = sprint_results.historical_diagnostics.get("sickness", {})
        if sickness_diag.get("enabled"):
            summary_rows.append(
                ["Sickness Model", f"team_size={sickness_diag.get('team_size')}"]
            )
        nb_params = sprint_results.historical_diagnostics.get("neg_binomial_params")
        if nb_params is not None:
            summary_rows.append(["NB mu", f"{nb_params['mu']:.4f}"])
            k_display = (
                f"{nb_params['k']:.4f}"
                if nb_params["k"] is not None
                else "inf (Poisson fallback)"
            )
            summary_rows.append(["NB dispersion k", k_display])
        stat_rows = [
            ["Mean", f"{sprint_results.mean:.2f} sprints"],
            ["Median (P50)", f"{sprint_results.median:.2f} sprints"],
            ["Std Dev", f"{sprint_results.std_dev:.2f} sprints"],
            ["Minimum", f"{sprint_results.min_sprints:.2f} sprints"],
            ["Maximum", f"{sprint_results.max_sprints:.2f} sprints"],
            [
                "Coefficient of Variation",
                f"{(sprint_results.std_dev / sprint_results.mean if sprint_results.mean > 0 else 0.0):.4f}",
            ],
        ]
        percentile_rows = [
            [
                f"P{percentile}",
                f"{value:.2f}",
                delivery_date.isoformat() if delivery_date is not None else "",
            ]
            for percentile, value in sorted(sprint_results.percentiles.items())
            for delivery_date in [sprint_results.date_percentiles.get(percentile)]
        ]

        click.echo("\nSprint Planning Summary:")
        click.echo(
            _tabulate(
                summary_rows,
                headers=["Field", "Value"],
                tablefmt="simple_outline",
                disable_numparse=True,
            )
        )
        click.echo("\nSprint Count Statistical Summary:")
        click.echo(
            _tabulate(
                stat_rows,
                headers=["Metric", "Value"],
                tablefmt="simple_outline",
                disable_numparse=True,
            )
        )
        click.echo("\nSprint Count Confidence Intervals:")
        click.echo(
            _tabulate(
                percentile_rows,
                headers=["Percentile", "Sprints", "Projected Delivery Date"],
                tablefmt="simple_outline",
                disable_numparse=True,
            )
        )

        if not minimal:
            series_statistics = sprint_results.historical_diagnostics.get(
                "series_statistics",
                {},
            )
            if series_statistics:
                history_rows = [
                    [
                        series_name,
                        f"{stats['mean']:.2f}",
                        f"{stats['median']:.2f}",
                        f"{stats['std_dev']:.2f}",
                        f"{stats['min']:.2f}",
                        f"{stats['max']:.2f}",
                    ]
                    for series_name, stats in sorted(series_statistics.items())
                ]
                click.echo("\nHistorical Sprint Series:")
                click.echo(
                    _tabulate(
                        history_rows,
                        headers=["Series", "Mean", "Median", "Std Dev", "Min", "Max"],
                        tablefmt="simple_outline",
                        disable_numparse=True,
                    )
                )

            ratio_summaries = sprint_results.historical_diagnostics.get(
                "ratios",
                {},
            )
            if ratio_summaries:
                ratio_rows = [
                    [
                        ratio_name,
                        f"{stats['mean']:.4f}",
                        f"{stats['median']:.4f}",
                        f"{stats['std_dev']:.4f}",
                        f"{stats.get('percentiles', {}).get(50, 0.0):.4f}",
                        f"{stats.get('percentiles', {}).get(80, 0.0):.4f}",
                        f"{stats.get('percentiles', {}).get(90, 0.0):.4f}",
                    ]
                    for ratio_name, stats in sorted(ratio_summaries.items())
                ]
                click.echo("\nHistorical Ratio Summaries:")
                click.echo(
                    _tabulate(
                        ratio_rows,
                        headers=[
                            "Ratio",
                            "Mean",
                            "Median",
                            "Std Dev",
                            "P50",
                            "P80",
                            "P90",
                        ],
                        tablefmt="simple_outline",
                        disable_numparse=True,
                    )
                )

            correlations = sprint_results.historical_diagnostics.get(
                "correlations",
                {},
            )
            if correlations:
                correlation_rows = [
                    [pair_name, f"{value:.4f}"]
                    for pair_name, value in sorted(correlations.items())
                ]
                click.echo("\nHistorical Correlations:")
                click.echo(
                    _tabulate(
                        correlation_rows,
                        headers=["Series Pair", "Pearson Correlation"],
                        tablefmt="simple_outline",
                        disable_numparse=True,
                    )
                )

            if sprint_results.burnup_percentiles:
                burnup_rows = [
                    [
                        int(point["sprint_number"]),
                        f"{point['p50']:.2f}",
                        f"{point['p80']:.2f}",
                        f"{point['p90']:.2f}",
                    ]
                    for point in sprint_results.burnup_percentiles
                ]
                click.echo("\nBurn-up Percentiles:")
                click.echo(
                    _tabulate(
                        burnup_rows,
                        headers=["Sprint", "P50", "P80", "P90"],
                        tablefmt="simple_outline",
                        disable_numparse=True,
                    )
                )
    else:
        click.echo("\nSprint Planning Summary:")
        click.echo(f"Sprint Length: {sprint_results.sprint_length_weeks} weeks")
        click.echo(
            "Planning Confidence Level: "
            f"{sprint_results.planning_confidence_level * 100:.0f}%"
        )
        click.echo(f"Removed Work Treatment: {sprint_results.removed_work_treatment}")
        click.echo(
            "Velocity Model: "
            f"{sprint_results.historical_diagnostics.get('velocity_model', 'empirical')}"
        )
        click.echo(
            "Planned Commitment Guidance: "
            f"{sprint_results.planned_commitment_guidance:.2f}"
        )
        click.echo(
            "Historical Sampling Mode: "
            f"{sprint_results.historical_diagnostics.get('sampling_mode', '')}"
        )
        click.echo(
            "Historical Observations: "
            f"{sprint_results.historical_diagnostics.get('observation_count', 0)}"
        )
        nb_params = sprint_results.historical_diagnostics.get("neg_binomial_params")
        if nb_params is not None:
            click.echo(f"NB mu: {nb_params['mu']:.4f}")
            if nb_params["k"] is not None:
                click.echo(f"NB dispersion k: {nb_params['k']:.4f}")
            else:
                click.echo("NB dispersion k: inf (Poisson fallback)")
        click.echo(
            "Carryover Mean: "
            f"{sprint_results.carryover_statistics.get('mean', 0.0):.2f}"
        )
        click.echo(
            "Aggregate Spillover Rate: "
            f"{sprint_results.spillover_statistics.get('aggregate_spillover_rate', {}).get('mean', 0.0):.4f}"
        )
        click.echo(
            "Observed Disruption Frequency: "
            f"{sprint_results.disruption_statistics.get('observed_frequency', 0.0):.4f}"
        )
        sickness_diag = sprint_results.historical_diagnostics.get("sickness", {})
        if sickness_diag.get("enabled"):
            click.echo(f"Sickness Model: team_size={sickness_diag.get('team_size')}")

        click.echo("\nSprint Count Statistical Summary:")
        click.echo(f"Mean: {sprint_results.mean:.2f} sprints")
        click.echo(f"Median (P50): {sprint_results.median:.2f} sprints")
        click.echo(f"Std Dev: {sprint_results.std_dev:.2f} sprints")
        click.echo(f"Minimum: {sprint_results.min_sprints:.2f} sprints")
        click.echo(f"Maximum: {sprint_results.max_sprints:.2f} sprints")
        click.echo(
            "Coefficient of Variation: "
            f"{(sprint_results.std_dev / sprint_results.mean if sprint_results.mean > 0 else 0.0):.4f}"
        )

        click.echo("\nSprint Count Confidence Intervals:")
        for percentile, value in sorted(sprint_results.percentiles.items()):
            delivery_date = sprint_results.date_percentiles.get(percentile)
            date_str = f"  ({delivery_date.isoformat()})" if delivery_date else ""
            rounded_sprints = math.ceil(value) if not value.is_integer() else int(value)
            click.echo(f"  P{percentile}: {rounded_sprints} sprints{date_str}")

        if not minimal:
            series_statistics = sprint_results.historical_diagnostics.get(
                "series_statistics",
                {},
            )
            if series_statistics:
                click.echo("\nHistorical Sprint Series:")
                for series_name, stats in sorted(series_statistics.items()):
                    click.echo(
                        f"  {series_name}: mean={stats['mean']:.2f}, "
                        f"median={stats['median']:.2f}, std={stats['std_dev']:.2f}, "
                        f"min={stats['min']:.2f}, max={stats['max']:.2f}"
                    )

            ratio_summaries = sprint_results.historical_diagnostics.get(
                "ratios",
                {},
            )
            if ratio_summaries:
                click.echo("\nHistorical Ratio Summaries:")
                for ratio_name, stats in sorted(ratio_summaries.items()):
                    percentiles = stats.get("percentiles", {})
                    click.echo(
                        f"  {ratio_name}: mean={stats['mean']:.4f}, "
                        f"median={stats['median']:.4f}, std={stats['std_dev']:.4f}, "
                        f"P50={percentiles.get(50, 0.0):.4f}, "
                        f"P80={percentiles.get(80, 0.0):.4f}, "
                        f"P90={percentiles.get(90, 0.0):.4f}"
                    )

            correlations = sprint_results.historical_diagnostics.get(
                "correlations",
                {},
            )
            if correlations:
                click.echo("\nHistorical Correlations:")
                for pair_name, value in sorted(correlations.items()):
                    click.echo(f"  {pair_name}: {value:.4f}")

            if sprint_results.burnup_percentiles:
                click.echo("\nBurn-up Percentiles:")
                for point in sprint_results.burnup_percentiles:
                    click.echo(
                        f"  Sprint {int(point['sprint_number'])}: "
                        f"P50={point['p50']:.2f}, "
                        f"P80={point['p80']:.2f}, "
                        f"P90={point['p90']:.2f}"
                    )


def _get_tasks_mode_heterogeneity_warning(project: Project) -> str | None:
    """Return a warning when tasks-mode forecasting uses clearly uneven items."""
    sprint_planning = project.sprint_planning
    if sprint_planning is None or not sprint_planning.enabled:
        return None
    if sprint_planning.capacity_mode != "tasks":
        return None
    if len(project.tasks) < 2:
        return None

    planning_sizes: list[int] = []
    for task in project.tasks:
        planning_size = task.get_planning_story_points()
        if planning_size is not None:
            planning_sizes.append(planning_size)
    if len(planning_sizes) >= 2:
        if max(planning_sizes) > min(planning_sizes):
            return (
                "Warning: Sprint planning is using 'tasks' capacity mode, but task "
                "planning sizes are heterogeneous. Throughput-based forecasting is "
                "most reliable when items are roughly comparable in size."
            )
        return None

    expected_estimates = [
        float(task.estimate.expected)
        for task in project.tasks
        if task.estimate.expected is not None
    ]
    if len(expected_estimates) >= 2 and max(expected_estimates) > min(
        expected_estimates
    ):
        return (
            "Warning: Sprint planning is using 'tasks' capacity mode, but task "
            "estimates vary across the backlog. Throughput-based forecasting is most "
            "reliable when items are roughly comparable in size."
        )

    return None


def _apply_sprint_defaults(project: Project, cfg: Config) -> None:
    """Apply company-wide sprint defaults when project values use built-in defaults."""
    sprint_planning = project.sprint_planning
    if sprint_planning is None or not sprint_planning.enabled:
        return

    sprint_defaults = cfg.sprint_defaults

    if (
        sprint_planning.planning_confidence_level
        == DEFAULT_SPRINT_PLANNING_CONFIDENCE_LEVEL
    ):
        sprint_planning.planning_confidence_level = (
            sprint_defaults.planning_confidence_level
        )

    if (
        sprint_planning.removed_work_treatment.value
        == DEFAULT_SPRINT_REMOVED_WORK_TREATMENT
    ):
        sprint_planning.removed_work_treatment = type(
            sprint_planning.removed_work_treatment
        )(sprint_defaults.removed_work_treatment)

    if sprint_planning.velocity_model.value == DEFAULT_SPRINT_VELOCITY_MODEL:
        sprint_planning.velocity_model = type(sprint_planning.velocity_model)(
            sprint_defaults.velocity_model
        )

    if (
        sprint_planning.volatility_overlay.disruption_probability
        == DEFAULT_SPRINT_VOLATILITY_DISRUPTION_PROBABILITY
    ):
        sprint_planning.volatility_overlay.disruption_probability = (
            sprint_defaults.volatility_disruption_probability
        )
    if (
        sprint_planning.volatility_overlay.disruption_multiplier_low
        == DEFAULT_SPRINT_VOLATILITY_DISRUPTION_MULTIPLIER_LOW
    ):
        sprint_planning.volatility_overlay.disruption_multiplier_low = (
            sprint_defaults.volatility_disruption_multiplier_low
        )
    if (
        sprint_planning.volatility_overlay.disruption_multiplier_expected
        == DEFAULT_SPRINT_VOLATILITY_DISRUPTION_MULTIPLIER_EXPECTED
    ):
        sprint_planning.volatility_overlay.disruption_multiplier_expected = (
            sprint_defaults.volatility_disruption_multiplier_expected
        )
    if (
        sprint_planning.volatility_overlay.disruption_multiplier_high
        == DEFAULT_SPRINT_VOLATILITY_DISRUPTION_MULTIPLIER_HIGH
    ):
        sprint_planning.volatility_overlay.disruption_multiplier_high = (
            sprint_defaults.volatility_disruption_multiplier_high
        )

    if sprint_planning.spillover.model.value == DEFAULT_SPRINT_SPILLOVER_MODEL:
        sprint_planning.spillover.model = type(sprint_planning.spillover.model)(
            sprint_defaults.spillover_model
        )
    if (
        sprint_planning.spillover.size_reference_points
        == DEFAULT_SPRINT_SPILLOVER_SIZE_REFERENCE_POINTS
    ):
        sprint_planning.spillover.size_reference_points = (
            sprint_defaults.spillover_size_reference_points
        )
    if (
        sprint_planning.spillover.consumed_fraction_alpha
        == DEFAULT_SPRINT_SPILLOVER_CONSUMED_FRACTION_ALPHA
    ):
        sprint_planning.spillover.consumed_fraction_alpha = (
            sprint_defaults.spillover_consumed_fraction_alpha
        )
    if (
        sprint_planning.spillover.consumed_fraction_beta
        == DEFAULT_SPRINT_SPILLOVER_CONSUMED_FRACTION_BETA
    ):
        sprint_planning.spillover.consumed_fraction_beta = (
            sprint_defaults.spillover_consumed_fraction_beta
        )
    if (
        sprint_planning.spillover.logistic_slope
        == DEFAULT_SPRINT_SPILLOVER_LOGISTIC_SLOPE
    ):
        sprint_planning.spillover.logistic_slope = (
            sprint_defaults.spillover_logistic_slope
        )
    if (
        sprint_planning.spillover.logistic_intercept
        == DEFAULT_SPRINT_SPILLOVER_LOGISTIC_INTERCEPT
    ):
        sprint_planning.spillover.logistic_intercept = (
            sprint_defaults.spillover_logistic_intercept
        )

    if sprint_planning.sickness.enabled is False:
        sprint_planning.sickness.enabled = sprint_defaults.sickness.enabled
    if (
        sprint_planning.sickness.probability_per_person_per_week
        == DEFAULT_SPRINT_SICKNESS_PROBABILITY_PER_PERSON_PER_WEEK
    ):
        sprint_planning.sickness.probability_per_person_per_week = (
            sprint_defaults.sickness.probability_per_person_per_week
        )
    if (
        sprint_planning.sickness.duration_log_mu
        == DEFAULT_SPRINT_SICKNESS_DURATION_LOG_MU
    ):
        sprint_planning.sickness.duration_log_mu = (
            sprint_defaults.sickness.duration_log_mu
        )
    if (
        sprint_planning.sickness.duration_log_sigma
        == DEFAULT_SPRINT_SICKNESS_DURATION_LOG_SIGMA
    ):
        sprint_planning.sickness.duration_log_sigma = (
            sprint_defaults.sickness.duration_log_sigma
        )


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
    "--tshirt-category",
    type=str,
    default=None,
    help="Override default T-shirt category for bare size tokens.",
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
@click.option(
    "--velocity-model",
    type=click.Choice(["empirical", "neg_binomial"]),
    default=None,
    help="Override sprint planning velocity model (empirical or neg_binomial).",
)
@click.option(
    "--no-sickness",
    is_flag=True,
    help="Disable sickness modeling regardless of project file settings.",
)
@click.option(
    "--include-historic-base",
    is_flag=True,
    help=(
        "Include a Historic Base section in HTML output and matching historic "
        "baseline payload in JSON output when sprint planning history is available."
    ),
)
@click.option(
    "--two-pass",
    is_flag=True,
    default=False,
    help=(
        "Enable criticality-two-pass scheduling for this run. "
        "Only has effect when resource-constrained scheduling is active. "
        "Overrides the config file assignment_mode setting."
    ),
)
@click.option(
    "--pass1-iterations",
    type=int,
    default=None,
    help=(
        "Number of pass-1 iterations for criticality ranking when --two-pass is used. "
        "Defaults to the config value (1000). Capped to --iterations."
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
    tshirt_category: Optional[str],
    minimal: bool,
    velocity_model: Optional[str],
    no_sickness: bool,
    include_historic_base: bool,
    two_pass: bool,
    pass1_iterations: Optional[int],
) -> None:
    """Run Monte Carlo simulation for a project."""
    if quiet < 2:
        click.echo(f"mcprojsim, version {__version__}")
    logger = setup_logging(level="INFO" if verbose else "WARNING")

    try:
        # Load configuration
        cfg, loaded_config_path = _load_config_with_user_default(config)
        if loaded_config_path is not None:
            logger.info(f"Loaded configuration from {loaded_config_path}")
        else:
            logger.info("Using built-in default configuration")

        if tshirt_category is not None:
            normalized_category = tshirt_category.strip().lower()
            valid_categories = cfg.get_t_shirt_categories()
            if normalized_category not in valid_categories:
                allowed = ", ".join(valid_categories)
                raise ValueError(
                    "Invalid value for --tshirt-category: "
                    f"'{tshirt_category}'. Valid categories: {allowed}"
                )
            cfg.t_shirt_size_default_category = normalized_category
            logger.info(
                "Overriding T-shirt default category to %s",
                normalized_category,
            )

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

        _apply_sprint_defaults(project, cfg)

        tasks_mode_warning = _get_tasks_mode_heterogeneity_warning(project)
        if tasks_mode_warning is not None and quiet < 2:
            click.echo(tasks_mode_warning)

        if velocity_model is not None and project.sprint_planning is not None:
            from mcprojsim.models.project import SprintVelocityModel

            project.sprint_planning.velocity_model = SprintVelocityModel(velocity_model)

        if no_sickness and project.sprint_planning is not None:
            project.sprint_planning.sickness.enabled = False

        # Resolve sickness team_size from project metadata if needed
        if (
            project.sprint_planning is not None
            and project.sprint_planning.sickness.enabled
            and project.sprint_planning.sickness.team_size is None
        ):
            if project.project.team_size is not None:
                project.sprint_planning.sickness.team_size = project.project.team_size
            else:
                click.echo(
                    "Error: Sickness modeling is enabled but no team_size is set. "
                    "Set team_size in sprint_planning.sickness or project metadata."
                )
                return

        # Run simulation
        logger.info(f"Running simulation with {iterations} iterations")
        engine = SimulationEngine(
            iterations=iterations,
            random_seed=seed,
            config=cfg,
            show_progress=quiet == 0,
            two_pass=two_pass,
            pass1_iterations=pass1_iterations,
        )
        results, elapsed_seconds, peak_memory_bytes = _run_simulation_with_metrics(
            engine, project
        )
        sprint_results: SprintPlanningResults | None = None
        sprint_elapsed_seconds: float | None = None
        sprint_peak_memory_bytes: int | None = None
        if project.sprint_planning is not None and project.sprint_planning.enabled:
            sprint_engine = SprintSimulationEngine(
                iterations=iterations,
                random_seed=seed,
            )
            (
                sprint_results,
                sprint_elapsed_seconds,
                sprint_peak_memory_bytes,
            ) = _run_sprint_simulation_with_metrics(sprint_engine, project)
        critical_path_limit = critical_paths or cfg.output.critical_path_report_limit

        if quiet < 2 and not minimal:
            click.echo(f"Simulation time: {elapsed_seconds:.2f} seconds")
            click.echo(
                "Peak simulation memory: " f"{_format_memory_size(peak_memory_bytes)}"
            )
            if sprint_results is not None and sprint_elapsed_seconds is not None:
                click.echo(
                    f"Sprint planning time: {sprint_elapsed_seconds:.2f} seconds"
                )
                click.echo(
                    "Peak sprint-planning memory: "
                    f"{_format_memory_size(sprint_peak_memory_bytes)}"
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

                    two_pass_trace = getattr(results, "two_pass_trace", None)
                    if two_pass_trace is not None and two_pass_trace.enabled:
                        tp = two_pass_trace
                        tp_rows = [
                            ["Pass-1 Iterations", str(tp.pass1_iterations)],
                            ["Pass-2 Iterations", str(tp.pass2_iterations)],
                            ["Ranking Method", tp.ranking_method],
                            ["Pass-1 Mean (hours)", f"{tp.pass1_mean_hours:.2f}"],
                            ["Pass-2 Mean (hours)", f"{tp.pass2_mean_hours:.2f}"],
                            ["Delta Mean (hours)", f"{tp.delta_mean_hours:+.2f}"],
                            ["Pass-1 P80 (hours)", f"{tp.pass1_p80_hours:.2f}"],
                            ["Pass-2 P80 (hours)", f"{tp.pass2_p80_hours:.2f}"],
                            ["Delta P80 (hours)", f"{tp.delta_p80_hours:+.2f}"],
                            ["Pass-1 P95 (hours)", f"{tp.pass1_p95_hours:.2f}"],
                            ["Pass-2 P95 (hours)", f"{tp.pass2_p95_hours:.2f}"],
                            ["Delta P95 (hours)", f"{tp.delta_p95_hours:+.2f}"],
                            ["Delta Res. Wait (hours)", f"{tp.delta_resource_wait_hours:+.2f}"],
                        ]
                        click.echo("\nTwo-Pass Scheduling Traceability:")
                        click.echo(
                            _tabulate(
                                tp_rows,
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

                    two_pass_trace = getattr(results, "two_pass_trace", None)
                    if two_pass_trace is not None and two_pass_trace.enabled:
                        tp = two_pass_trace
                        click.echo("\nTwo-Pass Scheduling Traceability:")
                        click.echo(
                            f"  Pass-1 iterations: {tp.pass1_iterations} | "
                            f"Pass-2 iterations: {tp.pass2_iterations}"
                        )
                        click.echo(
                            f"  Mean: {tp.pass1_mean_hours:.2f}h (pass-1) → "
                            f"{tp.pass2_mean_hours:.2f}h (pass-2) "
                            f"[delta {tp.delta_mean_hours:+.2f}h]"
                        )
                        click.echo(
                            f"  P80:  {tp.pass1_p80_hours:.2f}h (pass-1) → "
                            f"{tp.pass2_p80_hours:.2f}h (pass-2) "
                            f"[delta {tp.delta_p80_hours:+.2f}h]"
                        )
                        click.echo(
                            f"  P95:  {tp.pass1_p95_hours:.2f}h (pass-1) → "
                            f"{tp.pass2_p95_hours:.2f}h (pass-2) "
                            f"[delta {tp.delta_p95_hours:+.2f}h]"
                        )
                        click.echo(
                            f"  Resource wait delta: {tp.delta_resource_wait_hours:+.2f}h"
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

            if sprint_results is not None:
                _echo_sprint_results(sprint_results, table=table, minimal=minimal)

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
                    if sprint_results is not None:
                        JSONExporter.export(
                            results,
                            output_file,
                            config=cfg,
                            critical_path_limit=critical_path_limit,
                            sprint_results=sprint_results,
                            project=project,
                            include_historic_base=include_historic_base,
                        )
                    else:
                        JSONExporter.export(
                            results,
                            output_file,
                            config=cfg,
                            critical_path_limit=critical_path_limit,
                            project=project,
                            include_historic_base=include_historic_base,
                        )
                    if quiet == 0 and not minimal:
                        click.echo(f"\nResults exported to {output_file}")
                elif fmt == "csv":
                    output_file = base_output.with_suffix(".csv")
                    if sprint_results is not None:
                        CSVExporter.export(
                            results,
                            output_file,
                            config=cfg,
                            critical_path_limit=critical_path_limit,
                            sprint_results=sprint_results,
                        )
                    else:
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
                    if sprint_results is not None:
                        HTMLExporter.export(
                            results,
                            output_file,
                            project=project,
                            config=cfg,
                            critical_path_limit=critical_path_limit,
                            sprint_results=sprint_results,
                            include_historic_base=include_historic_base,
                        )
                    else:
                        HTMLExporter.export(
                            results,
                            output_file,
                            project=project,
                            config=cfg,
                            critical_path_limit=critical_path_limit,
                            include_historic_base=include_historic_base,
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


@cli.command(name="config")
@click.option("--config-file", "-c", type=click.Path(exists=True), help="Config file")
@click.option(
    "--generate",
    is_flag=True,
    help="Generate a default configuration file at ~/.mcprojsim/config.yaml.",
)
def config(config_file: Optional[str], generate: bool) -> None:
    """Show current configuration and optionally generate a default config file."""
    if generate:
        generated_config_path = _get_generated_default_config_path()
        generated_config_path.parent.mkdir(parents=True, exist_ok=True)

        default_cfg = Config.get_default()
        generated_config_path.write_text(
            yaml.safe_dump(
                default_cfg.model_dump(mode="json", exclude_none=True),
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        click.echo(f"Generated default configuration: {generated_config_path}")

    cfg, loaded_config_path = _load_config_with_user_default(config_file)
    if loaded_config_path is not None:
        click.echo(f"Configuration from {loaded_config_path}:")
    else:
        click.echo("Default configuration:")

    click.echo("\nUncertainty Factors:")
    for factor_name, levels in cfg.uncertainty_factors.items():
        click.echo(f"  {factor_name}:")
        for level, value in levels.items():
            click.echo(f"    {level}: {value}")

    lognormal_z_score = cfg.get_lognormal_high_z_value()

    click.echo(f"\nT-Shirt Sizes (unit: {cfg.t_shirt_size_unit.value}):")
    click.echo(f"  default_category: {cfg.t_shirt_size_default_category}")
    click.echo(f"  categories: {', '.join(cfg.get_t_shirt_categories())}")
    for category, size_map in cfg.t_shirt_sizes.items():
        click.echo(f"  {category}:")
        for size, size_config in size_map.items():
            click.echo(f"    {size}:")
            click.echo(
                "      "
                f"low: {size_config.low}, expected: {size_config.expected}, "
                f"high: {size_config.high}"
            )
            click.echo(
                "      lognormal params: "
                + _format_shifted_lognormal_parameters(
                    f"T-shirt size {category}.{size}",
                    size_config.low,
                    size_config.expected,
                    size_config.high,
                    lognormal_z_score,
                )
            )

    click.echo(f"\nStory Points (unit: {cfg.story_point_unit.value}):")
    for points, sp_config in sorted(cfg.story_points.items()):
        click.echo(f"  {points}:")
        click.echo(
            f"    low: {sp_config.low}, expected: {sp_config.expected}, high: {sp_config.high}"
        )
        click.echo(
            "    lognormal params: "
            + _format_shifted_lognormal_parameters(
                f"story point {points}",
                sp_config.low,
                sp_config.expected,
                sp_config.high,
                lognormal_z_score,
            )
        )

    click.echo("\nSimulation:")
    click.echo(f"  Default iterations: {cfg.simulation.default_iterations}")
    click.echo(f"  Random seed: {cfg.simulation.random_seed}")
    click.echo(
        "  Max stored critical paths: " f"{cfg.simulation.max_stored_critical_paths}"
    )
    click.echo("\nLognormal:")
    click.echo(
        "  High percentile for 'high' value: " f"P{cfg.lognormal.high_percentile}"
    )

    click.echo("\nOutput:")
    click.echo(f"  Formats: {', '.join(cfg.output.formats)}")
    click.echo(f"  Include histogram: {cfg.output.include_histogram}")
    click.echo(f"  Histogram bins: {cfg.output.histogram_bins}")
    click.echo(
        "  Critical path report limit: " f"{cfg.output.critical_path_report_limit}"
    )

    click.echo("\nSprint Defaults:")
    click.echo(
        "  Planning confidence level: "
        f"{cfg.sprint_defaults.planning_confidence_level}"
    )
    click.echo(
        "  Removed work treatment: " f"{cfg.sprint_defaults.removed_work_treatment}"
    )
    click.echo(f"  Velocity model: {cfg.sprint_defaults.velocity_model}")
    click.echo(
        "  Volatility disruption probability: "
        f"{cfg.sprint_defaults.volatility_disruption_probability}"
    )
    click.echo(
        "  Volatility disruption multiplier (low/expected/high): "
        f"{cfg.sprint_defaults.volatility_disruption_multiplier_low}/"
        f"{cfg.sprint_defaults.volatility_disruption_multiplier_expected}/"
        f"{cfg.sprint_defaults.volatility_disruption_multiplier_high}"
    )
    click.echo(f"  Spillover model: {cfg.sprint_defaults.spillover_model}")
    click.echo(
        "  Spillover size reference points: "
        f"{cfg.sprint_defaults.spillover_size_reference_points}"
    )
    click.echo(
        "  Spillover consumed fraction alpha/beta: "
        f"{cfg.sprint_defaults.spillover_consumed_fraction_alpha}/"
        f"{cfg.sprint_defaults.spillover_consumed_fraction_beta}"
    )
    click.echo(
        "  Spillover logistic slope/intercept: "
        f"{cfg.sprint_defaults.spillover_logistic_slope}/"
        f"{cfg.sprint_defaults.spillover_logistic_intercept}"
    )
    click.echo(f"  Sickness enabled: {cfg.sprint_defaults.sickness.enabled}")
    click.echo(
        "  Sickness probability per person per week: "
        f"{cfg.sprint_defaults.sickness.probability_per_person_per_week}"
    )
    click.echo(
        "  Sickness duration log mu/sigma: "
        f"{cfg.sprint_defaults.sickness.duration_log_mu}/"
        f"{cfg.sprint_defaults.sickness.duration_log_sigma}"
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
        resource_names = {r.name for r in project.resources}
        for task in project.tasks:
            has_estimate = (
                task.t_shirt_size is not None
                or task.story_points is not None
                or task.low_estimate is not None
            )
            if not has_estimate:
                issues.append(f"Task {task.number} ('{task.name}') has no estimate")
            for ref in task.dependency_refs:
                if int(ref) not in task_nums:
                    issues.append(
                        f"Task {task.number} depends on Task {ref}, which does not exist"
                    )
            for res_name in task.resources:
                if resource_names and res_name not in resource_names:
                    issues.append(
                        f"Task {task.number} references unknown resource"
                        f" '{res_name}'"
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
