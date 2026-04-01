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
import tempfile
from pathlib import Path
from typing import Optional

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as e:
    raise ImportError(
        "MCP server requires the 'mcp' package. "
        "Install with: poetry install --with mcp"
    ) from e

from mcprojsim.nl_parser import NLProjectParser


def _load_config_from_yaml(config_yaml: str | None):
    """Load Config from inline YAML or return defaults."""
    from mcprojsim.config import Config

    if not config_yaml:
        return Config.get_default()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(config_yaml)
        config_path = f.name
    try:
        return Config.load_from_file(config_path)
    finally:
        Path(config_path).unlink(missing_ok=True)


def _prepare_project_from_description(
    description: str,
    cfg,
    velocity_model: str | None = None,
    no_sickness: bool = False,
):
    """Parse NL description into Project and apply CLI-equivalent sprint defaults."""
    import yaml

    from mcprojsim.cli import _apply_sprint_defaults
    from mcprojsim.models.project import SprintVelocityModel
    from mcprojsim.parsers.yaml_parser import YAMLParser

    nl_parser = NLProjectParser()
    project_data = nl_parser.parse(description)
    yaml_str = nl_parser.to_yaml(project_data)

    data = yaml.safe_load(yaml_str)
    yaml_parser = YAMLParser()
    project = yaml_parser.parse_dict(data)

    _apply_runtime_sprint_overrides(
        project=project,
        cfg=cfg,
        velocity_model=velocity_model,
        no_sickness=no_sickness,
    )

    return project, yaml_str


def _prepare_project_from_yaml(
    project_yaml: str,
    cfg,
    velocity_model: str | None = None,
    no_sickness: bool = False,
):
    """Parse YAML content into Project and apply CLI-equivalent runtime defaults."""
    import yaml

    from mcprojsim.parsers.yaml_parser import YAMLParser

    data = yaml.safe_load(project_yaml)
    yaml_parser = YAMLParser()
    project = yaml_parser.parse_dict(data)

    _apply_runtime_sprint_overrides(
        project=project,
        cfg=cfg,
        velocity_model=velocity_model,
        no_sickness=no_sickness,
    )

    return project


def _apply_runtime_sprint_overrides(
    project,
    cfg,
    velocity_model: str | None = None,
    no_sickness: bool = False,
) -> None:
    """Apply sprint defaults and runtime overrides to keep MCP aligned with CLI."""
    from mcprojsim.cli import _apply_sprint_defaults
    from mcprojsim.models.project import SprintVelocityModel

    _apply_sprint_defaults(project, cfg)

    if velocity_model is not None and project.sprint_planning is not None:
        project.sprint_planning.velocity_model = SprintVelocityModel(velocity_model)

    if no_sickness and project.sprint_planning is not None:
        project.sprint_planning.sickness.enabled = False

    if (
        project.sprint_planning is not None
        and project.sprint_planning.sickness.enabled
        and project.sprint_planning.sickness.team_size is None
    ):
        if project.project.team_size is not None:
            project.sprint_planning.sickness.team_size = project.project.team_size
        else:
            raise ValueError(
                "Sickness modeling is enabled but no team_size is set. "
                "Set team_size in sprint_planning.sickness or project metadata."
            )


def _format_simulation_output(
    yaml_str: str,
    results,
    critical_path_limit: int,
) -> str:
    """Render simulation output in the same MCP-friendly text layout."""
    hours_per_day = results.hours_per_day
    mean_wd = math.ceil(results.mean / hours_per_day)

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

    if results.task_slack:
        lines.append("")
        lines.append("Schedule Slack:")
        for task_id, slack_val in sorted(
            results.task_slack.items(), key=lambda x: x[1]
        ):
            status = "Critical" if slack_val < 0.01 else f"{slack_val:.1f}h buffer"
            lines.append(f"  {task_id}: {slack_val:.2f} hours ({status})")

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

    two_pass_trace = getattr(results, "two_pass_trace", None)
    if two_pass_trace is not None and two_pass_trace.enabled:
        lines.append("")
        lines.append("Two-Pass Scheduling Traceability:")
        lines.append(f"  Pass-1 Iterations: {two_pass_trace.pass1_iterations}")
        lines.append(f"  Assignment Mode: {two_pass_trace.assignment_mode}")
        lines.append(f"  P80 Delta: {two_pass_trace.delta_p80_hours:+.2f} hours")

    return "\n".join(lines)


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
            or task.low_estimate is not None
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
def validate_generated_project_yaml(
    description: str,
    config_yaml: str | None = None,
    velocity_model: str | None = None,
    no_sickness: bool = False,
) -> str:
    """Validate generated YAML using full parser/model semantics.

    Runs the same end-to-end validation path as regular YAML project parsing,
    including sprint-default application and runtime sprint overrides used by
    simulation.

    Args:
        description: Semi-structured text describing the project.
        config_yaml: Optional YAML configuration content.
        velocity_model: Optional sprint velocity model override
            ("empirical" or "neg_binomial").
        no_sickness: Disable sprint sickness modeling for this validation.

    Returns:
        Validation report and the generated YAML content.
    """
    if velocity_model is not None and velocity_model not in {
        "empirical",
        "neg_binomial",
    }:
        return (
            "ERROR: Invalid velocity_model. " "Expected 'empirical' or 'neg_binomial'."
        )

    try:
        cfg = _load_config_from_yaml(config_yaml)
        project, yaml_str = _prepare_project_from_description(
            description=description,
            cfg=cfg,
            velocity_model=velocity_model,
            no_sickness=no_sickness,
        )
    except Exception as e:
        return f"ERROR: {e}"

    lines: list[str] = []
    lines.append("Valid generated project YAML.")
    lines.append(f"Project: {project.project.name}")
    lines.append(f"Tasks: {len(project.tasks)}")
    lines.append("=== Generated Project YAML ===")
    lines.append(yaml_str)
    return "\n".join(lines)


@mcp.tool()
def validate_project_yaml(
    project_yaml: str,
    config_yaml: str | None = None,
    velocity_model: str | None = None,
    no_sickness: bool = False,
) -> str:
    """Validate an existing project YAML payload using full parser/model semantics.

    Args:
        project_yaml: Existing mcprojsim project YAML content.
        config_yaml: Optional YAML configuration content.
        velocity_model: Optional sprint velocity model override
            ("empirical" or "neg_binomial").
        no_sickness: Disable sprint sickness modeling for this validation.

    Returns:
        Validation report for the provided YAML payload.
    """
    if velocity_model is not None and velocity_model not in {
        "empirical",
        "neg_binomial",
    }:
        return (
            "ERROR: Invalid velocity_model. " "Expected 'empirical' or 'neg_binomial'."
        )

    try:
        cfg = _load_config_from_yaml(config_yaml)
        project = _prepare_project_from_yaml(
            project_yaml=project_yaml,
            cfg=cfg,
            velocity_model=velocity_model,
            no_sickness=no_sickness,
        )
    except Exception as e:
        return f"ERROR: {e}"

    lines: list[str] = []
    lines.append("Valid project YAML.")
    lines.append(f"Project: {project.project.name}")
    lines.append(f"Tasks: {len(project.tasks)}")
    return "\n".join(lines)


@mcp.tool()
def simulate_project(
    description: str,
    iterations: int = 10000,
    seed: int | None = None,
    config_yaml: str | None = None,
    velocity_model: str | None = None,
    no_sickness: bool = False,
    two_pass: bool = False,
    pass1_iterations: Optional[int] = None,
    critical_paths_limit: Optional[int] = None,
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
        velocity_model: Optional sprint velocity model override
            ("empirical" or "neg_binomial").
        no_sickness: Disable sprint sickness modeling for this run.
        two_pass: Enable criticality-two-pass scheduling for constrained mode.
        pass1_iterations: Optional pass-1 iteration override for two-pass mode.
        critical_paths_limit: Optional critical path report limit override.

    Returns:
        Simulation results summary including the generated YAML,
        statistics, confidence intervals, delivery dates, and critical paths.
    """
    from mcprojsim.simulation import SimulationEngine

    if velocity_model is not None and velocity_model not in {
        "empirical",
        "neg_binomial",
    }:
        raise ValueError(
            "Invalid velocity_model. Expected 'empirical' or 'neg_binomial'."
        )

    cfg = _load_config_from_yaml(config_yaml)
    project, yaml_str = _prepare_project_from_description(
        description=description,
        cfg=cfg,
        velocity_model=velocity_model,
        no_sickness=no_sickness,
    )

    engine = SimulationEngine(
        iterations=iterations,
        random_seed=seed,
        config=cfg,
        show_progress=False,
        two_pass=two_pass,
        pass1_iterations=pass1_iterations,
    )
    results = engine.run(project)
    critical_path_limit = critical_paths_limit or cfg.output.critical_path_report_limit
    return _format_simulation_output(yaml_str, results, critical_path_limit)


@mcp.tool()
def simulate_project_yaml(
    project_yaml: str,
    iterations: int = 10000,
    seed: int | None = None,
    config_yaml: str | None = None,
    velocity_model: str | None = None,
    no_sickness: bool = False,
    two_pass: bool = False,
    pass1_iterations: Optional[int] = None,
    critical_paths_limit: Optional[int] = None,
) -> str:
    """Run a simulation directly from existing YAML content.

    This is useful when MCP clients already maintain project YAML and only need
    validation/simulation controls without NL regeneration.
    """
    from mcprojsim.simulation import SimulationEngine

    if velocity_model is not None and velocity_model not in {
        "empirical",
        "neg_binomial",
    }:
        raise ValueError(
            "Invalid velocity_model. Expected 'empirical' or 'neg_binomial'."
        )

    cfg = _load_config_from_yaml(config_yaml)
    project = _prepare_project_from_yaml(
        project_yaml=project_yaml,
        cfg=cfg,
        velocity_model=velocity_model,
        no_sickness=no_sickness,
    )

    engine = SimulationEngine(
        iterations=iterations,
        random_seed=seed,
        config=cfg,
        show_progress=False,
        two_pass=two_pass,
        pass1_iterations=pass1_iterations,
    )
    results = engine.run(project)
    critical_path_limit = critical_paths_limit or cfg.output.critical_path_report_limit
    return _format_simulation_output(project_yaml, results, critical_path_limit)


@mcp.tool()
def update_project_yaml(
    existing_yaml: str,
    update_description: str,
    replace_tasks: bool = False,
) -> str:
    """Update an existing project YAML payload from natural-language instructions.

    The update description can include project metadata, sprint-planning fields,
    and tasks. By default, tasks are preserved unless ``replace_tasks`` is true.

    Args:
        existing_yaml: Existing mcprojsim project YAML content.
        update_description: Semi-structured NL update instructions.
        replace_tasks: Replace existing tasks with parsed tasks from updates.

    Returns:
        Updated YAML content.
    """
    import yaml

    nl_parser = NLProjectParser()

    try:
        existing_data = yaml.safe_load(existing_yaml)
        if not isinstance(existing_data, dict):
            return "ERROR: existing_yaml must decode to a YAML mapping/object."
    except Exception as e:
        return f"ERROR: Invalid existing_yaml: {e}"

    try:
        updates_project = nl_parser.parse(update_description)
        updates_yaml = nl_parser.to_yaml(updates_project)
        updates_data = yaml.safe_load(updates_yaml)
    except Exception as e:
        return f"ERROR: Could not parse update_description: {e}"

    project_block = existing_data.setdefault("project", {})
    if not isinstance(project_block, dict):
        return "ERROR: existing_yaml project section must be a mapping/object."

    if updates_project.name != "Untitled Project":
        project_block["name"] = updates_project.name
    if updates_project.start_date is not None:
        project_block["start_date"] = updates_project.start_date
    if updates_project.description is not None:
        project_block["description"] = updates_project.description
    if updates_project.hours_per_day != 8.0:
        project_block["hours_per_day"] = updates_project.hours_per_day
    if updates_project.confidence_levels != [50, 80, 90, 95]:
        project_block["confidence_levels"] = updates_project.confidence_levels

    if replace_tasks:
        existing_data["tasks"] = updates_data.get("tasks", [])

    if updates_data.get("sprint_planning") is not None:
        existing_data["sprint_planning"] = updates_data["sprint_planning"]

    if updates_data.get("resources"):
        existing_data["resources"] = updates_data["resources"]
    if updates_data.get("calendars"):
        existing_data["calendars"] = updates_data["calendars"]

    return yaml.safe_dump(existing_data, sort_keys=False)


def main() -> None:
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
