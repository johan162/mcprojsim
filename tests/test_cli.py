"""Tests for the command-line interface."""

from pathlib import Path

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
        captured: dict[str, object] = {}

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
                    percentiles = {50: 1.0}

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
        captured: dict[str, object] = {}

        class FakeEngine:
            def __init__(self, iterations, random_seed, config, show_progress) -> None:
                captured["engine_config"] = config

            def run(self, project):
                class FakeResults:
                    project_name = project.project.name
                    mean = 1.0
                    median = 1.0
                    std_dev = 0.0
                    percentiles = {50: 1.0}

                return FakeResults()

        def fake_export(results, output_path, project=None, config=None):
            captured["output_path"] = str(output_path)
            captured["project"] = project
            captured["html_config"] = config

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
