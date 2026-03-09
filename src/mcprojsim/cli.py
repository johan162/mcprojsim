"""Command-line interface for Monte Carlo Project Simulator."""

from pathlib import Path
from typing import Optional, Union

import click

from mcprojsim import __version__
from mcprojsim.config import Config, DEFAULT_SIMULATION_ITERATIONS
from mcprojsim.exporters import CSVExporter, HTMLExporter, JSONExporter
from mcprojsim.parsers import TOMLParser, YAMLParser
from mcprojsim.simulation import SimulationEngine
from mcprojsim.utils import Validator, setup_logging


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
def simulate(
    project_file: str,
    iterations: int,
    config: Optional[str],
    seed: Optional[int],
    output: Optional[str],
    output_format: str,
    critical_paths: Optional[int],
    quiet: bool,
) -> None:
    """Run Monte Carlo simulation for a project."""
    click.echo(f"mcprojsim, version {__version__}")
    logger = setup_logging()

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
        results = engine.run(project)
        critical_path_limit = critical_paths or cfg.output.critical_path_report_limit

        if not quiet:
            click.echo("\n=== Simulation Results ===")
            click.echo(f"Project: {results.project_name}")
            click.echo(f"Mean: {results.mean:.2f} days")
            click.echo(f"Median (P50): {results.median:.2f} days")
            click.echo(f"Std Dev: {results.std_dev:.2f} days")
            click.echo("\nConfidence Intervals:")
            for p in sorted(results.percentiles.keys()):
                click.echo(f"  P{p}: {results.percentiles[p]:.2f} days")

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
def validate(project_file: str) -> None:
    """Validate a project definition file."""
    logger = setup_logging()

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

    click.echo("\nT-Shirt Sizes (effort estimates in days):")
    for size, config in cfg.t_shirt_sizes.items():
        click.echo(f"  {size}:")
        click.echo(
            f"    min: {config.min}, most_likely: {config.most_likely}, max: {config.max}"
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


if __name__ == "__main__":
    cli()
