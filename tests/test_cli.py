"""Tests for the command-line interface."""

from pathlib import Path
from typing import Any

import yaml
from click.testing import CliRunner

from mcprojsim import __version__
from mcprojsim.cli import cli
from mcprojsim.config import DEFAULT_SIMULATION_ITERATIONS


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
                                "estimate": {"min": 1, "most_likely": 2, "max": 3},
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
                    {"t_shirt_sizes": {"M": {"min": 10, "most_likely": 20, "max": 30}}}
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
        assert captured["html_config"].get_t_shirt_size("M").most_likely == 20
        assert captured["critical_path_limit"] == 2

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
                                "estimate": {"min": 1, "most_likely": 2, "max": 3},
                            }
                        ],
                    }
                )
            )

            result = runner.invoke(cli, ["simulate", str(project_file)])

        assert result.exit_code == 0
        assert "Most Frequent Critical Paths" in result.output
        assert "task_001 -> task_002" in result.output

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
                                "estimate": {"min": 1, "most_likely": 2, "max": 3},
                            }
                        ],
                    }
                )
            )

            result = runner.invoke(cli, ["simulate", str(project_file), "--quiet"])

        assert result.exit_code == 0
        assert "Simulation time: 12.34 seconds" in result.output
        assert "Peak simulation memory: 64.00 MiB" in result.output

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
                                "estimate": {"min": 1, "most_likely": 2, "max": 3},
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
      min: 1
      mostlikely: 2
      max: 3
""".strip())

            result = runner.invoke(cli, ["validate", str(project_file)])

        assert result.exit_code != 0
        assert "line 9" in result.output
        assert "most_likely" in result.output

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
                                "estimate": {"min": 1, "most_likely": 2, "max": 3},
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
                                "estimate": {"min": 1, "most_likely": 2, "max": 3},
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
