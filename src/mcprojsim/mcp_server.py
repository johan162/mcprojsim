"""MCP server for mcprojsim project file generation.

Exposes tools for generating syntactically correct mcprojsim project
specification files from natural language descriptions.

Usage:
    # Run directly
    python -m mcprojsim.mcp_server

    # Or via the installed entry point
    mcprojsim-mcp

Configure in your MCP client (e.g. Claude Desktop, VS Code) as:
    {
        "mcpServers": {
            "mcprojsim": {
                "command": "mcprojsim-mcp"
            }
        }
    }
"""

from __future__ import annotations

import math

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as e:
    raise ImportError(
        "MCP server requires the 'mcp' package. "
        "Install with: poetry install --with mcp"
    ) from e

from mcprojsim.nl_parser import NLProjectParser

mcp = FastMCP(
    "mcprojsim",
    instructions=(
        "Generate syntactically correct mcprojsim project specification "
        "files from natural language descriptions and run Monte Carlo "
        "project simulations."
    ),
)


@mcp.tool()
def generate_project_file(description: str) -> str:
    """Generate a mcprojsim YAML project file from a natural language description.

    Accepts a semi-structured project description and produces a valid YAML
    project specification file for use with mcprojsim Monte Carlo simulation.

    The description should include:
    - Project name (e.g., "Project name: My Project")
    - Start date in YYYY-MM-DD format (e.g., "Start date: 2026-01-15")
    - Numbered tasks with names, t-shirt sizes (XS/S/M/L/XL/XXL),
      and dependencies

    Supported task estimation methods:
    - T-shirt sizes: "Size: M" or "Size XL"
    - Story points: "Story points: 5"
    - Explicit ranges: "Estimate: 3/5/10 days"

    For constrained scheduling, you can also define:
    - Resources: "Resource N: Name" with bullets for Experience, Productivity,
      Availability, Calendar, Sickness, and Absence
    - Calendars: "Calendar: id" with bullets for Work hours, Work days,
      and Holidays
    - Task constraints: "Resources: Alice, Bob", "Max resources: 2",
      "Min experience: 3"

    Example input:

        Project name: My Project
        Start date: 2026-01-15

        Resource 1: Alice
        - Experience: 3
        - Productivity: 1.1

        Resource 2: Bob
        - Experience: 2

        Task 1:
        - Design phase
        - Size: M
        - Resources: Alice
        Task 2:
        - Implementation
        - Depends on Task 1
        - Size: XL
        - Resources: Alice, Bob
        - Max resources: 2

    Args:
        description: Semi-structured text describing the project, its tasks,
                    sizing estimates, resources, and dependencies.

    Returns:
        Syntactically correct YAML project file content ready for mcprojsim.
    """
    parser = NLProjectParser()
    return parser.parse_and_generate(description)


@mcp.tool()
def validate_project_description(description: str) -> str:
    """Check whether a project description can be parsed, reporting issues.

    Validates the description without generating a file, and reports
    any warnings or errors found.

    Args:
        description: Semi-structured text describing the project.

    Returns:
        Validation report with any warnings or errors.
    """
    parser = NLProjectParser()
    try:
        project = parser.parse(description)
    except ValueError as e:
        return f"ERROR: {e}"

    issues: list[str] = []

    if project.name == "Untitled Project":
        issues.append(
            "WARNING: No project name found. " "Defaulting to 'Untitled Project'."
        )
    if not project.start_date:
        issues.append("WARNING: No start date specified.")

    task_nums = {t.number for t in project.tasks}
    resource_names = {r.name for r in project.resources}
    for task in project.tasks:
        has_estimate = (
            task.t_shirt_size is not None
            or task.story_points is not None
            or task.min_estimate is not None
        )
        if not has_estimate:
            issues.append(
                f"WARNING: Task {task.number} ('{task.name}') " f"has no estimate."
            )

        for ref in task.dependency_refs:
            if int(ref) not in task_nums:
                issues.append(
                    f"ERROR: Task {task.number} depends on "
                    f"Task {ref}, which does not exist."
                )

        for res_name in task.resources:
            if resource_names and res_name not in resource_names:
                issues.append(
                    f"ERROR: Task {task.number} references unknown "
                    f"resource '{res_name}'."
                )

    if issues:
        return "Validation issues:\n" + "\n".join(f"  - {issue}" for issue in issues)

    return f"Valid: '{project.name}' with {len(project.tasks)} task(s)."


@mcp.tool()
def simulate_project(
    description: str,
    iterations: int = 10000,
    seed: int | None = None,
    config_yaml: str | None = None,
) -> str:
    """Generate a project file from a description and run a Monte Carlo simulation.

    Combines project generation and simulation in a single step: parses a
    natural language project description, builds a valid project specification,
    and runs a Monte Carlo simulation on it.

    The description should include:
    - Project name (e.g., "Project name: My Project")
    - Start date in YYYY-MM-DD format (e.g., "Start date: 2026-01-15")
    - Numbered tasks with names, sizes or estimates, and dependencies

    Args:
        description: Semi-structured text describing the project.
        iterations: Number of simulation iterations (default 10000).
        seed: Optional random seed for reproducible results.
        config_yaml: Optional YAML configuration content (as a string)
                     for custom T-shirt size mappings, uncertainty factors, etc.

    Returns:
        Simulation results summary including the generated YAML,
        statistics, confidence intervals, delivery dates, and critical paths.
    """
    import tempfile
    from pathlib import Path

    from mcprojsim.config import Config
    from mcprojsim.parsers.yaml_parser import YAMLParser
    from mcprojsim.simulation import SimulationEngine

    # Parse and generate YAML
    nl_parser = NLProjectParser()
    project_data = nl_parser.parse(description)
    yaml_str = nl_parser.to_yaml(project_data)

    # Load config
    if config_yaml:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_yaml)
            config_path = f.name
        try:
            cfg = Config.load_from_file(config_path)
        finally:
            Path(config_path).unlink()
    else:
        cfg = Config.get_default()

    # Parse the generated YAML into a Project object
    import yaml

    data = yaml.safe_load(yaml_str)
    yaml_parser = YAMLParser()
    project = yaml_parser.parse_dict(data)

    # Run simulation
    engine = SimulationEngine(
        iterations=iterations,
        random_seed=seed,
        config=cfg,
        show_progress=False,
    )
    results = engine.run(project)

    # Format output
    hours_per_day = results.hours_per_day
    mean_wd = math.ceil(results.mean / hours_per_day)
    critical_path_limit = cfg.output.critical_path_report_limit

    lines: list[str] = []
    lines.append("=== Generated Project YAML ===")
    lines.append(yaml_str)
    lines.append("=== Simulation Results ===")
    lines.append(f"Project: {results.project_name}")
    lines.append(f"Iterations: {results.iterations}")
    lines.append(f"Hours per Day: {hours_per_day}")
    lines.append(f"Mean: {results.mean:.2f} hours ({mean_wd} working days)")
    lines.append(f"Median (P50): {results.median:.2f} hours")
    lines.append(f"Std Dev: {results.std_dev:.2f} hours")
    cv = results.std_dev / results.mean if results.mean > 0 else 0
    lines.append(f"Coefficient of Variation: {cv:.4f}")
    lines.append(f"Skewness: {results.skewness:.4f}")
    lines.append(f"Excess Kurtosis: {results.kurtosis:.4f}")
    lines.append("")
    lines.append("Confidence Intervals:")
    for p in sorted(results.percentiles.keys()):
        hours = results.percentiles[p]
        wd = math.ceil(hours / hours_per_day)
        delivery = results.delivery_date(hours)
        date_str = f"  ({delivery.isoformat()})" if delivery else ""
        lines.append(f"  P{p}: {hours:.2f} hours ({wd} working days){date_str}")

    # Sensitivity analysis
    if results.sensitivity:
        lines.append("")
        lines.append("Sensitivity Analysis (top contributors):")
        sorted_sens = sorted(
            results.sensitivity.items(),
            key=lambda x: abs(x[1]),
            reverse=True,
        )
        for task_id, corr in sorted_sens[:10]:
            lines.append(f"  {task_id}: {corr:+.4f}")

    # Schedule slack
    if results.task_slack:
        lines.append("")
        lines.append("Schedule Slack:")
        for task_id, slack_val in sorted(
            results.task_slack.items(), key=lambda x: x[1]
        ):
            status = "Critical" if slack_val < 0.01 else f"{slack_val:.1f}h buffer"
            lines.append(f"  {task_id}: {slack_val:.2f} hours ({status})")

    # Risk impact summary
    risk_summary = results.get_risk_impact_summary()
    has_risk_data = any(s["trigger_rate"] > 0 for s in risk_summary.values())
    if has_risk_data:
        lines.append("")
        lines.append("Risk Impact Analysis:")
        for task_id, stats in sorted(risk_summary.items()):
            if stats["trigger_rate"] > 0:
                lines.append(
                    f"  {task_id}: mean={stats['mean_impact']:.2f}h, "
                    f"triggers={stats['trigger_rate']*100:.1f}%, "
                    f"mean_when_triggered={stats['mean_when_triggered']:.2f}h"
                )

    critical_path_records = results.get_critical_path_sequences(critical_path_limit)
    if critical_path_records:
        lines.append("")
        lines.append("Most Frequent Critical Paths:")
        for index, record in enumerate(critical_path_records, start=1):
            lines.append(
                f"  {index}. {record.format_path()} "
                f"({record.count}/{results.iterations},"
                f" {record.frequency * 100:.1f}%)"
            )

    return "\n".join(lines)


def main() -> None:
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
