"""Tests for the command-line interface."""

from pathlib import Path
from typing import Any

import yaml
from click.testing import CliRunner
import numpy as np
import pytest

from mcprojsim import __version__
from mcprojsim.cli import cli
from mcprojsim.config import DEFAULT_SIMULATION_ITERATIONS, Config
from mcprojsim.models.sprint_simulation import SprintPlanningResults
from mcprojsim.simulation.distributions import fit_shifted_lognormal


@pytest.fixture(autouse=True)
def isolate_user_default_config_path(monkeypatch, tmp_path) -> None:
    """Keep tests independent from any real user-level config file."""
    isolated_path = tmp_path / "no-user-config.yaml"
    monkeypatch.setattr(
        "mcprojsim.cli._get_user_default_config_path",
        lambda: isolated_path,
    )


class TestCli:
    """CLI tests."""

    def test_version_matches_package_version(self) -> None:
        """The --version output should show the package name and version."""
        runner = CliRunner()

        result = runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert result.output == f"mcprojsim, version {__version__}\n"

    def test_simulate_uses_default_iteration_constant(self, monkeypatch) -> None:
        """The simulate command should use the shared default iteration constant."""
        runner = CliRunner()
        captured: dict[str, Any] = {}

        class FakeEngine:
            def __init__(
                self,
                iterations: int,
                random_seed: int | None,
                config,
                show_progress: bool,
            ) -> None:
                captured["iterations"] = iterations
                captured["random_seed"] = random_seed
                captured["config"] = config
                captured["show_progress"] = show_progress

            def run(self, project):
                class FakeResults:
                    project_name = project.project.name
                    mean = 1.0
                    median = 1.0
                    std_dev = 0.0
                    skewness = 0.0
                    kurtosis = 0.0
                    sensitivity = {}
                    task_slack = {}
                    percentiles = {50: 1.0}
                    effort_percentiles: dict[int, float] = {}
                    hours_per_day = 8.0
                    max_parallel_tasks = 0

                    def total_effort_hours(self):
                        return 1.0

                    def get_critical_path_sequences(self, top_n=None):
                        return []

                    def delivery_date(self, hours):
                        return None

                    def get_risk_impact_summary(self):
                        return {}

                return FakeResults()

        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", FakeEngine)

        with runner.isolated_filesystem():
            project_file = Path("project.yaml")
            project_file.write_text(
                yaml.safe_dump(
                    {
                        "project": {"name": "CLI Test", "start_date": "2025-01-01"},
                        "tasks": [
                            {
                                "id": "task_001",
                                "name": "Task",
                                "estimate": {"low": 1, "expected": 2, "high": 3},
                            }
                        ],
                    }
                )
            )

            result = runner.invoke(cli, ["simulate", str(project_file), "--quiet"])

        assert result.exit_code == 0
        assert captured["iterations"] == DEFAULT_SIMULATION_ITERATIONS
        assert captured["show_progress"] is False

    def test_simulate_passes_loaded_config_to_html_export(self, monkeypatch) -> None:
        """The simulate command should pass the loaded config to HTML export."""
        runner = CliRunner()
        captured: dict[str, Any] = {}

        class FakeEngine:
            def __init__(self, iterations, random_seed, config, show_progress) -> None:
                captured["engine_config"] = config

            def run(self, project):
                class FakeResults:
                    project_name = project.project.name
                    mean = 1.0
                    median = 1.0
                    std_dev = 0.0
                    skewness = 0.0
                    kurtosis = 0.0
                    sensitivity = {}
                    task_slack = {}
                    percentiles = {50: 1.0}
                    effort_percentiles: dict[int, float] = {}
                    hours_per_day = 8.0
                    max_parallel_tasks = 0

                    def total_effort_hours(self):
                        return 1.0

                    def get_critical_path_sequences(self, top_n=None):
                        return []

                    def delivery_date(self, hours):
                        return None

                    def get_risk_impact_summary(self):
                        return {}

                return FakeResults()

        def fake_export(
            results,
            output_path,
            project=None,
            config=None,
            critical_path_limit=None,
            sprint_results=None,
        ):
            captured["output_path"] = str(output_path)
            captured["project"] = project
            captured["html_config"] = config
            captured["critical_path_limit"] = critical_path_limit

        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", FakeEngine)
        monkeypatch.setattr("mcprojsim.cli.HTMLExporter.export", fake_export)

        with runner.isolated_filesystem():
            project_file = Path("project.yaml")
            config_file = Path("config.yaml")

            project_file.write_text(
                yaml.safe_dump(
                    {
                        "project": {"name": "CLI Test", "start_date": "2025-01-01"},
                        "tasks": [
                            {
                                "id": "task_001",
                                "name": "Task",
                                "estimate": {"t_shirt_size": "M"},
                            }
                        ],
                    }
                )
            )
            config_file.write_text(
                yaml.safe_dump(
                    {"t_shirt_sizes": {"M": {"low": 10, "expected": 20, "high": 30}}}
                )
            )

            result = runner.invoke(
                cli,
                [
                    "simulate",
                    str(project_file),
                    "--config",
                    str(config_file),
                    "--output-format",
                    "html",
                    "--output",
                    "result",
                    "--quiet",
                ],
            )

        assert result.exit_code == 0
        assert captured["output_path"].endswith("result.html")
        assert captured["project"].project.name == "CLI Test"
        assert captured["html_config"] is captured["engine_config"]
        assert captured["html_config"].get_t_shirt_size("M").expected == 20
        assert captured["critical_path_limit"] == 2

    def test_simulate_tshirt_category_override(self, monkeypatch) -> None:
        """The simulate command should override default T-shirt category."""
        runner = CliRunner()
        captured: dict[str, Any] = {}

        class FakeEngine:
            def __init__(self, iterations, random_seed, config, show_progress) -> None:
                captured["config"] = config

            def run(self, project):
                class FakeResults:
                    project_name = project.project.name
                    mean = 1.0
                    median = 1.0
                    std_dev = 0.0
                    skewness = 0.0
                    kurtosis = 0.0
                    sensitivity = {}
                    task_slack = {}
                    percentiles = {50: 1.0}
                    effort_percentiles: dict[int, float] = {}
                    hours_per_day = 8.0
                    max_parallel_tasks = 0

                    def total_effort_hours(self):
                        return 1.0

                    def get_critical_path_sequences(self, top_n=None):
                        return []

                    def delivery_date(self, hours):
                        return None

                    def get_risk_impact_summary(self):
                        return {}

                return FakeResults()

        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", FakeEngine)

        with runner.isolated_filesystem():
            project_file = Path("project.yaml")
            project_file.write_text(
                yaml.safe_dump(
                    {
                        "project": {"name": "CLI Test", "start_date": "2025-01-01"},
                        "tasks": [
                            {
                                "id": "task_001",
                                "name": "Task",
                                "estimate": {"t_shirt_size": "M"},
                            }
                        ],
                    }
                )
            )

            result = runner.invoke(
                cli,
                [
                    "simulate",
                    str(project_file),
                    "--tshirt-category",
                    "epic",
                    "--quiet",
                ],
            )

        assert result.exit_code == 0
        assert captured["config"].t_shirt_size_default_category == "epic"

    def test_simulate_invalid_tshirt_category_override(self) -> None:
        """Invalid --tshirt-category values should fail with clear guidance."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            project_file = Path("project.yaml")
            project_file.write_text(
                yaml.safe_dump(
                    {
                        "project": {"name": "CLI Test", "start_date": "2025-01-01"},
                        "tasks": [
                            {
                                "id": "task_001",
                                "name": "Task",
                                "estimate": {"low": 1, "expected": 2, "high": 3},
                            }
                        ],
                    }
                )
            )

            result = runner.invoke(
                cli,
                [
                    "simulate",
                    str(project_file),
                    "--tshirt-category",
                    "foo",
                ],
            )

        assert result.exit_code != 0
        assert "Invalid value for --tshirt-category" in result.output
        assert "Valid categories:" in result.output

    def test_simulate_loads_user_default_config_when_present(
        self, monkeypatch, tmp_path
    ) -> None:
        """simulate should load ~/.mcprojsim/configuration.yaml when it exists."""
        runner = CliRunner()
        captured: dict[str, Any] = {}

        class FakeEngine:
            def __init__(self, iterations, random_seed, config, show_progress) -> None:
                captured["config"] = config

            def run(self, project):
                class FakeResults:
                    project_name = project.project.name
                    mean = 1.0
                    median = 1.0
                    std_dev = 0.0
                    skewness = 0.0
                    kurtosis = 0.0
                    sensitivity = {}
                    task_slack = {}
                    percentiles = {50: 1.0}
                    effort_percentiles: dict[int, float] = {}
                    hours_per_day = 8.0
                    max_parallel_tasks = 0

                    def total_effort_hours(self):
                        return 1.0

                    def get_critical_path_sequences(self, top_n=None):
                        return []

                    def delivery_date(self, hours):
                        return None

                    def get_risk_impact_summary(self):
                        return {}

                return FakeResults()

        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", FakeEngine)

        user_config = tmp_path / "configuration.yaml"
        user_config.write_text(
            yaml.safe_dump(
                {
                    "t_shirt_sizes": {
                        "story": {"M": {"low": 10, "expected": 20, "high": 30}}
                    },
                    "t_shirt_size_default_category": "story",
                }
            )
        )
        monkeypatch.setattr(
            "mcprojsim.cli._get_user_default_config_path",
            lambda: user_config,
        )

        with runner.isolated_filesystem():
            project_file = Path("project.yaml")
            project_file.write_text(
                yaml.safe_dump(
                    {
                        "project": {"name": "CLI Test", "start_date": "2025-01-01"},
                        "tasks": [
                            {
                                "id": "task_001",
                                "name": "Task",
                                "estimate": {"t_shirt_size": "M"},
                            }
                        ],
                    }
                )
            )

            result = runner.invoke(cli, ["simulate", str(project_file), "--quiet"])

        assert result.exit_code == 0
        assert captured["config"].t_shirt_size_default_category == "story"
        assert captured["config"].t_shirt_sizes["story"]["M"].expected == 20.0

    def test_simulate_cli_config_overrides_user_default(
        self, monkeypatch, tmp_path
    ) -> None:
        """--config should take precedence over user default configuration."""
        runner = CliRunner()
        captured: dict[str, Any] = {}

        class FakeEngine:
            def __init__(self, iterations, random_seed, config, show_progress) -> None:
                captured["config"] = config

            def run(self, project):
                class FakeResults:
                    project_name = project.project.name
                    mean = 1.0
                    median = 1.0
                    std_dev = 0.0
                    skewness = 0.0
                    kurtosis = 0.0
                    sensitivity = {}
                    task_slack = {}
                    percentiles = {50: 1.0}
                    effort_percentiles: dict[int, float] = {}
                    hours_per_day = 8.0
                    max_parallel_tasks = 0

                    def total_effort_hours(self):
                        return 1.0

                    def get_critical_path_sequences(self, top_n=None):
                        return []

                    def delivery_date(self, hours):
                        return None

                    def get_risk_impact_summary(self):
                        return {}

                return FakeResults()

        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", FakeEngine)

        user_config = tmp_path / "configuration.yaml"
        user_config.write_text(
            yaml.safe_dump({"t_shirt_size_default_category": "story"})
        )
        monkeypatch.setattr(
            "mcprojsim.cli._get_user_default_config_path",
            lambda: user_config,
        )

        with runner.isolated_filesystem():
            project_file = Path("project.yaml")
            cli_config = Path("cli_config.yaml")
            project_file.write_text(
                yaml.safe_dump(
                    {
                        "project": {"name": "CLI Test", "start_date": "2025-01-01"},
                        "tasks": [
                            {
                                "id": "task_001",
                                "name": "Task",
                                "estimate": {"t_shirt_size": "M"},
                            }
                        ],
                    }
                )
            )
            cli_config.write_text(
                yaml.safe_dump({"t_shirt_size_default_category": "bug"})
            )

            result = runner.invoke(
                cli,
                ["simulate", str(project_file), "--config", str(cli_config), "--quiet"],
            )

        assert result.exit_code == 0
        assert captured["config"].t_shirt_size_default_category == "bug"

    def test_simulate_shows_critical_path_sequences(self, monkeypatch) -> None:
        """The simulate command should print the most frequent critical paths."""
        runner = CliRunner()

        class FakeEngine:
            def __init__(self, iterations, random_seed, config, show_progress) -> None:
                pass

            def run(self, project):
                class CriticalPathRecord:
                    def __init__(self, path, count, frequency) -> None:
                        self.path = path
                        self.count = count
                        self.frequency = frequency

                    def format_path(self) -> str:
                        return " -> ".join(self.path)

                class FakeResults:
                    project_name = project.project.name
                    mean = 1.0
                    median = 1.0
                    std_dev = 0.0
                    skewness = 0.0
                    kurtosis = 0.0
                    sensitivity = {}
                    task_slack = {}
                    percentiles = {50: 1.0}
                    effort_percentiles: dict[int, float] = {}
                    iterations = 10
                    hours_per_day = 8.0
                    max_parallel_tasks = 0

                    def total_effort_hours(self):
                        return 1.0

                    def get_critical_path_sequences(self, top_n=None):
                        return [
                            CriticalPathRecord(
                                ("task_001", "task_002"),
                                7,
                                0.7,
                            )
                        ]

                    def delivery_date(self, hours):
                        return None

                    def get_risk_impact_summary(self):
                        return {}

                return FakeResults()

        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", FakeEngine)

        with runner.isolated_filesystem():
            project_file = Path("project.yaml")
            project_file.write_text(
                yaml.safe_dump(
                    {
                        "project": {"name": "CLI Test", "start_date": "2025-01-01"},
                        "tasks": [
                            {
                                "id": "task_001",
                                "name": "Task",
                                "estimate": {"low": 1, "expected": 2, "high": 3},
                            }
                        ],
                    }
                )
            )

            result = runner.invoke(cli, ["simulate", str(project_file)])
        assert result.exit_code == 0
        assert "Most Frequent Critical Paths" in result.output
        assert "task_001 -> task_002" in result.output

    def test_simulate_shows_sprint_planning_summary(self, monkeypatch) -> None:
        """The simulate command should print sprint-planning results when enabled."""
        runner = CliRunner()

        class FakeEngine:
            def __init__(self, iterations, random_seed, config, show_progress) -> None:
                pass

            def run(self, project):
                class FakeResults:
                    project_name = project.project.name
                    mean = 1.0
                    median = 1.0
                    std_dev = 0.0
                    skewness = 0.0
                    kurtosis = 0.0
                    sensitivity = {}
                    task_slack = {}
                    percentiles = {50: 1.0}
                    effort_percentiles: dict[int, float] = {}
                    iterations = 10
                    hours_per_day = 8.0
                    max_parallel_tasks = 0

                    def total_effort_hours(self):
                        return 1.0

                    def get_critical_path_sequences(self, top_n=None):
                        return []

                    def delivery_date(self, hours):
                        return None

                    def get_risk_impact_summary(self):
                        return {}

                return FakeResults()

        class FakeSprintEngine:
            def __init__(self, iterations, random_seed) -> None:
                pass

            def run(self, project):
                results = SprintPlanningResults(
                    iterations=10,
                    project_name=project.project.name,
                    sprint_length_weeks=2,
                    sprint_counts=np.array([2.0, 2.0, 3.0]),
                    random_seed=42,
                    planning_confidence_level=0.8,
                    removed_work_treatment="churn_only",
                    historical_diagnostics={
                        "sampling_mode": "matching_cadence",
                        "observation_count": 3,
                        "series_statistics": {
                            "completed_units": {
                                "mean": 6.0,
                                "median": 6.0,
                                "std_dev": 0.5,
                                "min": 5.0,
                                "max": 7.0,
                            }
                        },
                        "ratios": {
                            "spillover_ratio": {
                                "mean": 0.1111,
                                "median": 0.1000,
                                "std_dev": 0.0500,
                                "percentiles": {50: 0.1, 80: 0.15, 90: 0.18},
                            }
                        },
                        "correlations": {
                            "completed_units|spillover_units": -0.4200,
                        },
                    },
                    planned_commitment_guidance=4.0,
                    carryover_statistics={"mean": 1.2},
                    spillover_statistics={"aggregate_spillover_rate": {"mean": 0.3}},
                    disruption_statistics={"observed_frequency": 0.2},
                    burnup_percentiles=[
                        {"sprint_number": 1.0, "p50": 3.0, "p80": 4.0, "p90": 5.0}
                    ],
                )
                results.calculate_statistics()
                for percentile in (50, 80, 90):
                    results.percentile(percentile)
                return results

        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", FakeEngine)
        monkeypatch.setattr("mcprojsim.cli.SprintSimulationEngine", FakeSprintEngine)

        with runner.isolated_filesystem():
            project_file = Path("project.yaml")
            project_file.write_text(
                yaml.safe_dump(
                    {
                        "project": {"name": "CLI Test", "start_date": "2025-01-01"},
                        "tasks": [
                            {
                                "id": "task_001",
                                "name": "Task",
                                "estimate": {"low": 1, "expected": 2, "high": 3},
                                "planning_story_points": 3,
                            }
                        ],
                        "sprint_planning": {
                            "enabled": True,
                            "sprint_length_weeks": 2,
                            "capacity_mode": "story_points",
                            "history": [
                                {"sprint_id": "S1", "completed_story_points": 5},
                                {"sprint_id": "S2", "completed_story_points": 6},
                            ],
                        },
                    }
                )
            )

            result = runner.invoke(cli, ["simulate", str(project_file)])

        assert result.exit_code == 0
        assert "Sprint Planning Summary:" in result.output
        assert "Sprint Count Confidence Intervals:" in result.output
        assert "Historical Sprint Series:" in result.output
        assert "Historical Ratio Summaries:" in result.output
        assert "spillover_ratio" in result.output
        assert "Historical Correlations:" in result.output
        assert "completed_units|spillover_units" in result.output
        assert "Carryover Mean:" in result.output
        assert "Burn-up Percentiles:" in result.output

    def test_simulate_passes_sprint_results_to_exporters(self, monkeypatch) -> None:
        """The simulate command should pass sprint results into exporter calls."""
        runner = CliRunner()
        captured: dict[str, Any] = {}

        class FakeEngine:
            def __init__(self, iterations, random_seed, config, show_progress) -> None:
                pass

            def run(self, project):
                class FakeResults:
                    project_name = project.project.name
                    mean = 1.0
                    median = 1.0
                    std_dev = 0.0
                    skewness = 0.0
                    kurtosis = 0.0
                    sensitivity = {}
                    task_slack = {}
                    percentiles = {50: 1.0}
                    effort_percentiles: dict[int, float] = {}
                    iterations = 10
                    hours_per_day = 8.0
                    max_parallel_tasks = 0

                    def total_effort_hours(self):
                        return 1.0

                    def get_critical_path_sequences(self, top_n=None):
                        return []

                    def delivery_date(self, hours):
                        return None

                    def get_risk_impact_summary(self):
                        return {}

                return FakeResults()

        class FakeSprintEngine:
            def __init__(self, iterations, random_seed) -> None:
                pass

            def run(self, project):
                results = SprintPlanningResults(
                    iterations=10,
                    project_name=project.project.name,
                    sprint_length_weeks=2,
                    sprint_counts=np.array([2.0, 2.0, 3.0]),
                    random_seed=42,
                    planning_confidence_level=0.8,
                    removed_work_treatment="churn_only",
                    historical_diagnostics={
                        "sampling_mode": "matching_cadence",
                        "observation_count": 3,
                    },
                    planned_commitment_guidance=4.0,
                    carryover_statistics={"mean": 1.2},
                    spillover_statistics={"aggregate_spillover_rate": {"mean": 0.3}},
                    disruption_statistics={"observed_frequency": 0.2},
                    burnup_percentiles=[
                        {"sprint_number": 1.0, "p50": 3.0, "p80": 4.0, "p90": 5.0}
                    ],
                )
                results.calculate_statistics()
                for percentile in (50, 80, 90):
                    results.percentile(percentile)
                return results

        def fake_json_export(
            results,
            output_path,
            config=None,
            critical_path_limit=None,
            sprint_results=None,
        ):
            captured["json_sprint_results"] = sprint_results

        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", FakeEngine)
        monkeypatch.setattr("mcprojsim.cli.SprintSimulationEngine", FakeSprintEngine)
        monkeypatch.setattr("mcprojsim.cli.JSONExporter.export", fake_json_export)

        with runner.isolated_filesystem():
            project_file = Path("project.yaml")
            project_file.write_text(
                yaml.safe_dump(
                    {
                        "project": {"name": "CLI Test", "start_date": "2025-01-01"},
                        "tasks": [
                            {
                                "id": "task_001",
                                "name": "Task",
                                "estimate": {"low": 1, "expected": 2, "high": 3},
                                "planning_story_points": 3,
                            }
                        ],
                        "sprint_planning": {
                            "enabled": True,
                            "sprint_length_weeks": 2,
                            "capacity_mode": "story_points",
                            "history": [
                                {"sprint_id": "S1", "completed_story_points": 5},
                                {"sprint_id": "S2", "completed_story_points": 6},
                            ],
                        },
                    }
                )
            )

            result = runner.invoke(
                cli,
                [
                    "simulate",
                    str(project_file),
                    "--output-format",
                    "json",
                    "--output",
                    "result",
                    "--quiet",
                ],
            )

        assert result.exit_code == 0
        assert captured["json_sprint_results"] is not None

    def test_simulate_warns_for_heterogeneous_tasks_mode(self, monkeypatch) -> None:
        """The simulate command should warn when tasks mode uses uneven task sizes."""
        runner = CliRunner()

        class FakeEngine:
            def __init__(self, iterations, random_seed, config, show_progress) -> None:
                pass

            def run(self, project):
                class FakeResults:
                    project_name = project.project.name
                    mean = 1.0
                    median = 1.0
                    std_dev = 0.0
                    skewness = 0.0
                    kurtosis = 0.0
                    sensitivity = {}
                    task_slack = {}
                    percentiles = {50: 1.0}
                    effort_percentiles: dict[int, float] = {}
                    iterations = 10
                    hours_per_day = 8.0
                    max_parallel_tasks = 0

                    def total_effort_hours(self):
                        return 1.0

                    def get_critical_path_sequences(self, top_n=None):
                        return []

                    def delivery_date(self, hours):
                        return None

                    def get_risk_impact_summary(self):
                        return {}

                return FakeResults()

        class FakeSprintEngine:
            def __init__(self, iterations, random_seed) -> None:
                pass

            def run(self, project):
                results = SprintPlanningResults(
                    iterations=10,
                    project_name=project.project.name,
                    sprint_length_weeks=2,
                    sprint_counts=np.array([1.0, 1.0, 2.0]),
                    random_seed=42,
                    planning_confidence_level=0.8,
                    removed_work_treatment="churn_only",
                    historical_diagnostics={
                        "sampling_mode": "matching_cadence",
                        "observation_count": 2,
                    },
                    planned_commitment_guidance=2.0,
                )
                results.calculate_statistics()
                for percentile in (50, 80, 90):
                    results.percentile(percentile)
                return results

        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", FakeEngine)
        monkeypatch.setattr("mcprojsim.cli.SprintSimulationEngine", FakeSprintEngine)

        with runner.isolated_filesystem():
            project_file = Path("project.yaml")
            project_file.write_text(
                yaml.safe_dump(
                    {
                        "project": {"name": "CLI Test", "start_date": "2025-01-01"},
                        "tasks": [
                            {
                                "id": "task_001",
                                "name": "Small Task",
                                "estimate": {"low": 1, "expected": 1, "high": 2},
                                "planning_story_points": 2,
                            },
                            {
                                "id": "task_002",
                                "name": "Large Task",
                                "estimate": {"low": 3, "expected": 5, "high": 8},
                                "planning_story_points": 8,
                            },
                        ],
                        "sprint_planning": {
                            "enabled": True,
                            "sprint_length_weeks": 2,
                            "capacity_mode": "tasks",
                            "history": [
                                {"sprint_id": "S1", "completed_tasks": 1},
                                {"sprint_id": "S2", "completed_tasks": 2},
                            ],
                        },
                    }
                )
            )

            result = runner.invoke(cli, ["simulate", str(project_file)])

        assert result.exit_code == 0
        assert (
            "Warning: Sprint planning is using 'tasks' capacity mode" in result.output
        )

    def test_simulate_reports_time_and_memory(self, monkeypatch) -> None:
        """The simulate command should print elapsed time and memory usage."""
        runner = CliRunner()

        class FakeEngine:
            def __init__(self, iterations, random_seed, config, show_progress) -> None:
                pass

        class FakeResults:
            project_name = "CLI Test"
            mean = 1.0
            median = 1.0
            std_dev = 0.0
            skewness = 0.0
            kurtosis = 0.0
            sensitivity: dict[str, float] = {}
            task_slack: dict[str, float] = {}
            percentiles: dict[int, float] = {50: 1.0}
            effort_percentiles: dict[int, float] = {}
            hours_per_day = 8.0
            max_parallel_tasks = 0

            def total_effort_hours(self):
                return 1.0

            def get_critical_path_sequences(self, top_n=None):
                return []

            def delivery_date(self, hours):
                return None

            def get_risk_impact_summary(self):
                return {}

        def fake_run_simulation_with_metrics(engine, project):
            return FakeResults(), 12.34, 64 * 1024 * 1024

        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", FakeEngine)
        monkeypatch.setattr(
            "mcprojsim.cli._run_simulation_with_metrics",
            fake_run_simulation_with_metrics,
        )

        with runner.isolated_filesystem():
            project_file = Path("project.yaml")
            project_file.write_text(
                yaml.safe_dump(
                    {
                        "project": {"name": "CLI Test", "start_date": "2025-01-01"},
                        "tasks": [
                            {
                                "id": "task_001",
                                "name": "Task",
                                "estimate": {"low": 1, "expected": 2, "high": 3},
                            }
                        ],
                    }
                )
            )

            result = runner.invoke(cli, ["simulate", str(project_file), "--quiet"])

        assert result.exit_code == 0
        assert "Simulation time: 12.34 seconds" in result.output
        assert "Peak simulation memory: 64.00 MiB" in result.output

    def test_config_displays_shifted_lognormal_parameters(self) -> None:
        """The config command should include derived log-normal parameters."""
        runner = CliRunner()

        result = runner.invoke(cli, ["config"])

        assert result.exit_code == 0
        default_z = 1.6448536269514722
        tshirt_mu, tshirt_sigma = fit_shifted_lognormal(40, 60, 120, default_z)
        story_mu, story_sigma = fit_shifted_lognormal(3, 5, 8, default_z)
        assert "default_category: epic" in result.output
        assert "categories: story, bug, epic, business, initiative" in result.output
        assert (
            "lognormal params: "
            f"mu: {tshirt_mu:.4f}, sigma: {tshirt_sigma:.4f}, "
            f"z-score: {default_z:.4f}"
        ) in result.output
        assert (
            "    lognormal params: "
            f"mu: {story_mu:.4f}, sigma: {story_sigma:.4f}, "
            f"z-score: {default_z:.4f}"
        ) in result.output

    def test_config_uses_user_default_when_present(self, monkeypatch, tmp_path) -> None:
        """config should use user-level default config when available."""
        runner = CliRunner()
        user_config = tmp_path / "configuration.yaml"
        user_config.write_text(
            yaml.safe_dump({"t_shirt_size_default_category": "story"})
        )
        monkeypatch.setattr(
            "mcprojsim.cli._get_user_default_config_path",
            lambda: user_config,
        )

        result = runner.invoke(cli, ["config"])

        assert result.exit_code == 0
        assert f"Configuration from {user_config}:" in result.output
        assert "default_category: story" in result.output

    def test_config_generate_creates_default_config_file(
        self, monkeypatch, tmp_path
    ) -> None:
        """--generate should create ~/.mcprojsim/config.yaml with default values."""
        runner = CliRunner()
        generated_path = tmp_path / ".mcprojsim" / "config.yaml"

        monkeypatch.setattr(
            "mcprojsim.cli._get_generated_default_config_path",
            lambda: generated_path,
        )

        result = runner.invoke(cli, ["config", "--generate"])

        assert result.exit_code == 0
        assert f"Generated default configuration: {generated_path}" in result.output
        assert generated_path.exists()

        generated_data = yaml.safe_load(generated_path.read_text(encoding="utf-8"))
        expected_data = Config.get_default().model_dump(mode="json", exclude_none=True)
        assert generated_data == expected_data

    def test_config_generate_creates_parent_directory(
        self, monkeypatch, tmp_path
    ) -> None:
        """--generate should create the parent directory when it does not exist."""
        runner = CliRunner()
        generated_dir = tmp_path / "missing" / "nested" / ".mcprojsim"
        generated_path = generated_dir / "config.yaml"
        assert not generated_dir.exists()

        monkeypatch.setattr(
            "mcprojsim.cli._get_generated_default_config_path",
            lambda: generated_path,
        )

        result = runner.invoke(cli, ["config", "--generate"])

        assert result.exit_code == 0
        assert generated_dir.exists()
        assert generated_path.exists()

    def test_config_uses_custom_lognormal_percentile(self, tmp_path) -> None:
        """Custom config percentiles should change displayed z-scores and fit."""
        runner = CliRunner()
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.safe_dump(
                {
                    "lognormal": {"high_percentile": 90},
                    "t_shirt_sizes": {"M": {"low": 4, "expected": 6, "high": 10}},
                    "story_points": {5: {"low": 2, "expected": 3, "high": 7}},
                }
            )
        )

        result = runner.invoke(cli, ["config", "-c", str(config_file)])

        assert result.exit_code == 0
        custom_z = 1.2815515655446008
        tshirt_mu, tshirt_sigma = fit_shifted_lognormal(4, 6, 10, custom_z)
        story_mu, story_sigma = fit_shifted_lognormal(2, 3, 7, custom_z)
        assert "High percentile for 'high' value: P90" in result.output
        assert "default_category: epic" in result.output
        assert (
            "lognormal params: "
            f"mu: {tshirt_mu:.4f}, sigma: {tshirt_sigma:.4f}, "
            f"z-score: {custom_z:.4f}"
        ) in result.output
        assert (
            "    lognormal params: "
            f"mu: {story_mu:.4f}, sigma: {story_sigma:.4f}, "
            f"z-score: {custom_z:.4f}"
        ) in result.output

    def test_simulate_double_quiet_suppresses_all_normal_output(
        self, monkeypatch
    ) -> None:
        """-qq should suppress version, timing, memory, and other normal output."""
        runner = CliRunner()
        captured: dict[str, Any] = {}

        class FakeEngine:
            def __init__(
                self,
                iterations: int,
                random_seed: int | None,
                config,
                show_progress: bool,
            ) -> None:
                captured["show_progress"] = show_progress

        class FakeResults:
            project_name = "CLI Test"
            mean = 1.0
            median = 1.0
            std_dev = 0.0
            skewness = 0.0
            kurtosis = 0.0
            sensitivity: dict[str, float] = {}
            task_slack: dict[str, float] = {}
            percentiles: dict[int, float] = {50: 1.0}
            effort_percentiles: dict[int, float] = {}
            hours_per_day = 8.0
            max_parallel_tasks = 0

            def total_effort_hours(self):
                return 1.0

            def get_critical_path_sequences(self, top_n=None):
                return []

            def delivery_date(self, hours):
                return None

            def get_risk_impact_summary(self):
                return {}

        def fake_run_simulation_with_metrics(engine, project):
            return FakeResults(), 12.34, 64 * 1024 * 1024

        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", FakeEngine)
        monkeypatch.setattr(
            "mcprojsim.cli._run_simulation_with_metrics",
            fake_run_simulation_with_metrics,
        )

        with runner.isolated_filesystem():
            project_file = Path("project.yaml")
            project_file.write_text(
                yaml.safe_dump(
                    {
                        "project": {"name": "CLI Test", "start_date": "2025-01-01"},
                        "tasks": [
                            {
                                "id": "task_001",
                                "name": "Task",
                                "estimate": {"low": 1, "expected": 2, "high": 3},
                            }
                        ],
                    }
                )
            )

            result = runner.invoke(cli, ["simulate", str(project_file), "-qq"])

        assert result.exit_code == 0
        assert result.output == ""
        assert captured["show_progress"] is False

    def test_validate_shows_line_numbers_and_suggestions(self) -> None:
        """The validate command should surface source-aware parser errors."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            project_file = Path("project.yaml")
            project_file.write_text("""
project:
  name: CLI Test
  start_date: 2025-01-01
tasks:
  - id: task_001
    name: Task
    estimate:
      low: 1
      mostlikely: 2
      high: 3
""".strip())

            result = runner.invoke(cli, ["validate", str(project_file)])

        assert result.exit_code != 0
        assert "line 9" in result.output
        assert "mostlikely" in result.output
        assert "Unknown field" in result.output

    def test_validate_fails_when_assigned_resource_is_underqualified(self) -> None:
        """validate should fail when task resource assignment violates min experience."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            project_file = Path("project.yaml")
            project_file.write_text(
                yaml.safe_dump(
                    {
                        "project": {
                            "name": "CLI Experience Test",
                            "start_date": "2025-01-01",
                        },
                        "tasks": [
                            {
                                "id": "task_001",
                                "name": "Senior Task",
                                "estimate": {"low": 1, "expected": 2, "high": 3},
                                "resources": ["junior_dev"],
                                "min_experience_level": 3,
                            }
                        ],
                        "resources": [
                            {
                                "name": "junior_dev",
                                "experience_level": 1,
                            }
                        ],
                    }
                )
            )

            result = runner.invoke(cli, ["validate", str(project_file)])

        assert result.exit_code != 0
        assert "requires min_experience_level" in result.output

    def test_simulate_fails_when_assigned_resource_is_underqualified(self) -> None:
        """simulate should fail when task resource assignment violates min experience."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            project_file = Path("project.yaml")
            project_file.write_text(
                yaml.safe_dump(
                    {
                        "project": {
                            "name": "CLI Experience Test",
                            "start_date": "2025-01-01",
                        },
                        "tasks": [
                            {
                                "id": "task_001",
                                "name": "Senior Task",
                                "estimate": {"low": 1, "expected": 2, "high": 3},
                                "resources": ["junior_dev"],
                                "min_experience_level": 3,
                            }
                        ],
                        "resources": [
                            {
                                "name": "junior_dev",
                                "experience_level": 1,
                            }
                        ],
                    }
                )
            )

            result = runner.invoke(cli, ["simulate", str(project_file)])

        assert result.exit_code != 0
        assert "requires min_experience_level" in result.output

    def test_validate_fails_when_resources_exceed_team_size(self) -> None:
        """validate should fail when explicit resources exceed team_size."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            project_file = Path("project.yaml")
            project_file.write_text(
                yaml.safe_dump(
                    {
                        "project": {
                            "name": "CLI Team Size Test",
                            "start_date": "2025-01-01",
                            "team_size": 1,
                        },
                        "tasks": [
                            {
                                "id": "task_001",
                                "name": "Task",
                                "estimate": {"low": 1, "expected": 2, "high": 3},
                            }
                        ],
                        "resources": [
                            {"name": "alice"},
                            {"name": "bob"},
                        ],
                    }
                )
            )

            result = runner.invoke(cli, ["validate", str(project_file)])

        assert result.exit_code != 0
        assert (
            "team_size is smaller than explicitly specified resources" in result.output
        )

    def test_simulate_fails_when_resources_exceed_team_size(self) -> None:
        """simulate should fail when explicit resources exceed team_size."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            project_file = Path("project.yaml")
            project_file.write_text(
                yaml.safe_dump(
                    {
                        "project": {
                            "name": "CLI Team Size Test",
                            "start_date": "2025-01-01",
                            "team_size": 1,
                        },
                        "tasks": [
                            {
                                "id": "task_001",
                                "name": "Task",
                                "estimate": {"low": 1, "expected": 2, "high": 3},
                            }
                        ],
                        "resources": [
                            {"name": "alice"},
                            {"name": "bob"},
                        ],
                    }
                )
            )

            result = runner.invoke(cli, ["simulate", str(project_file)])

        assert result.exit_code != 0
        assert (
            "team_size is smaller than explicitly specified resources" in result.output
        )

    def test_no_sickness_flag_disables_sickness(self, monkeypatch) -> None:
        """The --no-sickness flag should disable sickness modeling."""
        runner = CliRunner()
        captured_project: list[Any] = []

        class FakeEngine:
            def __init__(self, iterations, random_seed, config, show_progress) -> None:
                pass

            def run(self, project):
                class FakeResults:
                    project_name = project.project.name
                    mean = 1.0
                    median = 1.0
                    std_dev = 0.0
                    skewness = 0.0
                    kurtosis = 0.0
                    sensitivity = {}
                    task_slack = {}
                    percentiles = {50: 1.0}
                    effort_percentiles: dict[int, float] = {}
                    iterations = 10
                    hours_per_day = 8.0
                    max_parallel_tasks = 0

                    def total_effort_hours(self):
                        return 1.0

                    def get_critical_path_sequences(self, top_n=None):
                        return []

                    def delivery_date(self, hours):
                        return None

                    def get_risk_impact_summary(self):
                        return {}

                return FakeResults()

        class FakeSprintEngine:
            def __init__(self, iterations, random_seed) -> None:
                pass

            def run(self, project):
                captured_project.append(project)
                results = SprintPlanningResults(
                    iterations=10,
                    project_name=project.project.name,
                    sprint_length_weeks=2,
                    sprint_counts=np.array([2.0, 3.0]),
                    random_seed=42,
                    planning_confidence_level=0.8,
                    removed_work_treatment="churn_only",
                    historical_diagnostics={
                        "sampling_mode": "matching_cadence",
                        "observation_count": 2,
                    },
                    planned_commitment_guidance=4.0,
                    carryover_statistics={"mean": 0.0},
                    spillover_statistics={"aggregate_spillover_rate": {"mean": 0.0}},
                    disruption_statistics={"observed_frequency": 0.0},
                    burnup_percentiles=[],
                )
                results.calculate_statistics()
                return results

        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", FakeEngine)
        monkeypatch.setattr("mcprojsim.cli.SprintSimulationEngine", FakeSprintEngine)

        with runner.isolated_filesystem():
            project_file = Path("project.yaml")
            project_file.write_text(
                yaml.safe_dump(
                    {
                        "project": {
                            "name": "Sickness Test",
                            "start_date": "2025-01-01",
                            "team_size": 6,
                        },
                        "tasks": [
                            {
                                "id": "task_001",
                                "name": "Task",
                                "estimate": {"low": 1, "expected": 2, "high": 3},
                                "planning_story_points": 3,
                            }
                        ],
                        "sprint_planning": {
                            "enabled": True,
                            "sprint_length_weeks": 2,
                            "capacity_mode": "story_points",
                            "sickness": {"enabled": True},
                            "history": [
                                {"sprint_id": "S1", "completed_story_points": 5},
                                {"sprint_id": "S2", "completed_story_points": 6},
                            ],
                        },
                    }
                )
            )

            result = runner.invoke(
                cli, ["simulate", str(project_file), "--no-sickness", "-q"]
            )

        assert result.exit_code == 0
        assert len(captured_project) == 1
        assert captured_project[0].sprint_planning.sickness.enabled is False

    def test_sickness_requires_team_size(self) -> None:
        """Sickness enabled without team_size should produce an error."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            project_file = Path("project.yaml")
            project_file.write_text(
                yaml.safe_dump(
                    {
                        "project": {
                            "name": "No Team Size",
                            "start_date": "2025-01-01",
                        },
                        "tasks": [
                            {
                                "id": "task_001",
                                "name": "Task",
                                "estimate": {"low": 1, "expected": 2, "high": 3},
                                "planning_story_points": 3,
                            }
                        ],
                        "sprint_planning": {
                            "enabled": True,
                            "sprint_length_weeks": 2,
                            "capacity_mode": "story_points",
                            "sickness": {"enabled": True},
                            "history": [
                                {"sprint_id": "S1", "completed_story_points": 5},
                                {"sprint_id": "S2", "completed_story_points": 6},
                            ],
                        },
                    }
                )
            )

            result = runner.invoke(cli, ["simulate", str(project_file)])

        assert "Sickness modeling is enabled but no team_size" in result.output

    def test_sickness_falls_back_to_project_team_size(self, monkeypatch) -> None:
        """Sickness with no local team_size should resolve from project metadata."""
        runner = CliRunner()
        captured_project: list[Any] = []

        class FakeEngine:
            def __init__(self, iterations, random_seed, config, show_progress) -> None:
                pass

            def run(self, project):
                class FakeResults:
                    project_name = project.project.name
                    mean = 1.0
                    median = 1.0
                    std_dev = 0.0
                    skewness = 0.0
                    kurtosis = 0.0
                    sensitivity = {}
                    task_slack = {}
                    percentiles = {50: 1.0}
                    effort_percentiles: dict[int, float] = {}
                    iterations = 10
                    hours_per_day = 8.0
                    max_parallel_tasks = 0

                    def total_effort_hours(self):
                        return 1.0

                    def get_critical_path_sequences(self, top_n=None):
                        return []

                    def delivery_date(self, hours):
                        return None

                    def get_risk_impact_summary(self):
                        return {}

                return FakeResults()

        class FakeSprintEngine:
            def __init__(self, iterations, random_seed) -> None:
                pass

            def run(self, project):
                captured_project.append(project)
                results = SprintPlanningResults(
                    iterations=10,
                    project_name=project.project.name,
                    sprint_length_weeks=2,
                    sprint_counts=np.array([2.0, 3.0]),
                    random_seed=42,
                    planning_confidence_level=0.8,
                    removed_work_treatment="churn_only",
                    historical_diagnostics={
                        "sampling_mode": "matching_cadence",
                        "observation_count": 2,
                    },
                    planned_commitment_guidance=4.0,
                    carryover_statistics={"mean": 0.0},
                    spillover_statistics={"aggregate_spillover_rate": {"mean": 0.0}},
                    disruption_statistics={"observed_frequency": 0.0},
                    burnup_percentiles=[],
                )
                results.calculate_statistics()
                return results

        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", FakeEngine)
        monkeypatch.setattr("mcprojsim.cli.SprintSimulationEngine", FakeSprintEngine)

        with runner.isolated_filesystem():
            project_file = Path("project.yaml")
            project_file.write_text(
                yaml.safe_dump(
                    {
                        "project": {
                            "name": "Fallback",
                            "start_date": "2025-01-01",
                            "team_size": 7,
                        },
                        "tasks": [
                            {
                                "id": "task_001",
                                "name": "Task",
                                "estimate": {"low": 1, "expected": 2, "high": 3},
                                "planning_story_points": 3,
                            }
                        ],
                        "sprint_planning": {
                            "enabled": True,
                            "sprint_length_weeks": 2,
                            "capacity_mode": "story_points",
                            "sickness": {"enabled": True},
                            "history": [
                                {"sprint_id": "S1", "completed_story_points": 5},
                                {"sprint_id": "S2", "completed_story_points": 6},
                            ],
                        },
                    }
                )
            )

            result = runner.invoke(cli, ["simulate", str(project_file), "-q"])

        assert result.exit_code == 0
        assert len(captured_project) == 1
        assert captured_project[0].sprint_planning.sickness.team_size == 7

    def test_velocity_model_flag_overrides_project(self, monkeypatch) -> None:
        """The --velocity-model flag should override the project file setting."""
        runner = CliRunner()
        captured_project: list[Any] = []

        class FakeEngine:
            def __init__(self, iterations, random_seed, config, show_progress) -> None:
                pass

            def run(self, project):
                class FakeResults:
                    project_name = project.project.name
                    mean = 1.0
                    median = 1.0
                    std_dev = 0.0
                    skewness = 0.0
                    kurtosis = 0.0
                    sensitivity = {}
                    task_slack = {}
                    percentiles = {50: 1.0}
                    effort_percentiles: dict[int, float] = {}
                    iterations = 10
                    hours_per_day = 8.0
                    max_parallel_tasks = 0

                    def total_effort_hours(self):
                        return 1.0

                    def get_critical_path_sequences(self, top_n=None):
                        return []

                    def delivery_date(self, hours):
                        return None

                    def get_risk_impact_summary(self):
                        return {}

                return FakeResults()

        class FakeSprintEngine:
            def __init__(self, iterations, random_seed) -> None:
                pass

            def run(self, project):
                captured_project.append(project)
                results = SprintPlanningResults(
                    iterations=10,
                    project_name=project.project.name,
                    sprint_length_weeks=2,
                    sprint_counts=np.array([2.0, 3.0]),
                    random_seed=42,
                    planning_confidence_level=0.8,
                    removed_work_treatment="churn_only",
                    historical_diagnostics={
                        "sampling_mode": "matching_cadence",
                        "velocity_model": "neg_binomial",
                        "observation_count": 2,
                    },
                    planned_commitment_guidance=4.0,
                    carryover_statistics={"mean": 0.0},
                    spillover_statistics={"aggregate_spillover_rate": {"mean": 0.0}},
                    disruption_statistics={"observed_frequency": 0.0},
                    burnup_percentiles=[],
                )
                results.calculate_statistics()
                return results

        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", FakeEngine)
        monkeypatch.setattr("mcprojsim.cli.SprintSimulationEngine", FakeSprintEngine)

        with runner.isolated_filesystem():
            project_file = Path("project.yaml")
            project_file.write_text(
                yaml.safe_dump(
                    {
                        "project": {
                            "name": "NB Override",
                            "start_date": "2025-01-01",
                        },
                        "tasks": [
                            {
                                "id": "task_001",
                                "name": "Task",
                                "estimate": {"low": 1, "expected": 2, "high": 3},
                                "planning_story_points": 3,
                            }
                        ],
                        "sprint_planning": {
                            "enabled": True,
                            "sprint_length_weeks": 2,
                            "capacity_mode": "story_points",
                            "history": [
                                {"sprint_id": "S1", "completed_story_points": 5},
                                {"sprint_id": "S2", "completed_story_points": 6},
                            ],
                        },
                    }
                )
            )

            result = runner.invoke(
                cli,
                [
                    "simulate",
                    str(project_file),
                    "--velocity-model",
                    "neg_binomial",
                    "-q",
                ],
            )

        assert result.exit_code == 0
        assert len(captured_project) == 1
        assert (
            captured_project[0].sprint_planning.velocity_model.value == "neg_binomial"
        )

    def test_simulate_applies_sprint_defaults_from_config(self, monkeypatch) -> None:
        """Global sprint_defaults should apply when project uses built-in defaults."""
        runner = CliRunner()
        captured_project: list[Any] = []

        class FakeEngine:
            def __init__(self, iterations, random_seed, config, show_progress) -> None:
                pass

            def run(self, project):
                class FakeResults:
                    project_name = project.project.name
                    mean = 1.0
                    median = 1.0
                    std_dev = 0.0
                    skewness = 0.0
                    kurtosis = 0.0
                    sensitivity = {}
                    task_slack = {}
                    percentiles = {50: 1.0}
                    effort_percentiles: dict[int, float] = {}
                    iterations = 10
                    hours_per_day = 8.0
                    max_parallel_tasks = 0

                    def total_effort_hours(self):
                        return 1.0

                    def get_critical_path_sequences(self, top_n=None):
                        return []

                    def delivery_date(self, hours):
                        return None

                    def get_risk_impact_summary(self):
                        return {}

                return FakeResults()

        class FakeSprintEngine:
            def __init__(self, iterations, random_seed) -> None:
                pass

            def run(self, project):
                captured_project.append(project)
                results = SprintPlanningResults(
                    iterations=10,
                    project_name=project.project.name,
                    sprint_length_weeks=2,
                    sprint_counts=np.array([2.0, 3.0]),
                    random_seed=42,
                    planning_confidence_level=project.sprint_planning.planning_confidence_level,
                    removed_work_treatment=project.sprint_planning.removed_work_treatment.value,
                    historical_diagnostics={
                        "sampling_mode": "matching_cadence",
                        "velocity_model": project.sprint_planning.velocity_model.value,
                        "observation_count": 2,
                    },
                    planned_commitment_guidance=4.0,
                    carryover_statistics={"mean": 0.0},
                    spillover_statistics={"aggregate_spillover_rate": {"mean": 0.0}},
                    disruption_statistics={"observed_frequency": 0.0},
                    burnup_percentiles=[],
                )
                results.calculate_statistics()
                return results

        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", FakeEngine)
        monkeypatch.setattr("mcprojsim.cli.SprintSimulationEngine", FakeSprintEngine)

        with runner.isolated_filesystem():
            project_file = Path("project.yaml")
            config_file = Path("config.yaml")

            project_file.write_text(
                yaml.safe_dump(
                    {
                        "project": {
                            "name": "Sprint Defaults",
                            "start_date": "2025-01-01",
                            "team_size": 6,
                        },
                        "tasks": [
                            {
                                "id": "task_001",
                                "name": "Task",
                                "estimate": {"low": 1, "expected": 2, "high": 3},
                                "planning_story_points": 3,
                            }
                        ],
                        "sprint_planning": {
                            "enabled": True,
                            "sprint_length_weeks": 2,
                            "capacity_mode": "story_points",
                            "history": [
                                {"sprint_id": "S1", "completed_story_points": 5},
                                {"sprint_id": "S2", "completed_story_points": 6},
                            ],
                        },
                    }
                )
            )

            config_file.write_text(
                yaml.safe_dump(
                    {
                        "sprint_defaults": {
                            "planning_confidence_level": 0.9,
                            "removed_work_treatment": "reduce_backlog",
                            "velocity_model": "neg_binomial",
                            "sickness": {
                                "enabled": True,
                                "probability_per_person_per_week": 0.08,
                                "duration_log_mu": 0.6,
                                "duration_log_sigma": 0.5,
                            },
                        }
                    }
                )
            )

            result = runner.invoke(
                cli,
                ["simulate", str(project_file), "--config", str(config_file), "-q"],
            )

        assert result.exit_code == 0
        assert len(captured_project) == 1
        sprint = captured_project[0].sprint_planning
        assert sprint is not None
        assert sprint.planning_confidence_level == 0.9
        assert sprint.removed_work_treatment.value == "reduce_backlog"
        assert sprint.velocity_model.value == "neg_binomial"
        assert sprint.sickness.enabled is True
        assert sprint.sickness.probability_per_person_per_week == 0.08
        assert sprint.sickness.duration_log_mu == 0.6
        assert sprint.sickness.duration_log_sigma == 0.5
