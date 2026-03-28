"""True integration tests for CLI commands (no engine/export monkeypatching)."""

from pathlib import Path
import json

from click.testing import CliRunner
import pytest
import yaml

from mcprojsim.cli import cli


@pytest.fixture(autouse=True)
def isolate_user_default_config_path(monkeypatch, tmp_path) -> None:
    """Keep tests independent from any real user-level config file."""
    isolated_path = tmp_path / "no-user-config.yaml"
    monkeypatch.setattr(
        "mcprojsim.cli._get_user_default_config_path",
        lambda: isolated_path,
    )


def test_validate_command_success_and_failure() -> None:
    """validate should return success for valid files and non-zero for invalid files."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        valid_file = Path("valid_project.yaml")
        invalid_file = Path("invalid_project.yaml")

        valid_file.write_text(
            yaml.safe_dump(
                {
                    "project": {"name": "Valid", "start_date": "2025-01-01"},
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

        invalid_file.write_text(
            yaml.safe_dump(
                {
                    "project": {"name": "Invalid", "start_date": "2025-01-01"},
                    "tasks": [
                        {
                            "id": "task_001",
                            "name": "Task",
                            "estimate": {"low": 5, "expected": 2, "high": 3},
                        }
                    ],
                }
            )
        )

        valid_result = runner.invoke(cli, ["validate", str(valid_file)])
        invalid_result = runner.invoke(cli, ["validate", str(invalid_file)])

    assert valid_result.exit_code == 0
    assert "Project file is valid" in valid_result.output

    assert invalid_result.exit_code != 0
    assert "Validation failed" in invalid_result.output


def test_simulate_exports_json_with_real_engine() -> None:
    """simulate should run end-to-end and create JSON output."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        project_file = Path("project.yaml")
        output_base = Path("results")

        project_file.write_text(
            yaml.safe_dump(
                {
                    "project": {"name": "CLI Integration", "start_date": "2025-01-01"},
                    "tasks": [
                        {
                            "id": "task_001",
                            "name": "Task 1",
                            "estimate": {"low": 1, "expected": 2, "high": 4},
                        },
                        {
                            "id": "task_002",
                            "name": "Task 2",
                            "estimate": {"low": 2, "expected": 3, "high": 5},
                            "dependencies": ["task_001"],
                        },
                    ],
                }
            )
        )

        result = runner.invoke(
            cli,
            [
                "simulate",
                str(project_file),
                "--iterations",
                "40",
                "--seed",
                "42",
                "--output-format",
                "json",
                "--output",
                str(output_base),
                "-qq",
            ],
        )

        json_output = Path("results.json")
        assert json_output.exists()
        payload = json.loads(json_output.read_text())

    assert result.exit_code == 0
    assert payload["project"]["name"] == "CLI Integration"
    assert payload["simulation"]["iterations"] == 40
    assert payload["statistics"]["mean_hours"] > 0


def test_simulate_tshirt_category_override_changes_results() -> None:
    """--tshirt-category should affect bare T-shirt token resolution end-to-end."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        project_file = Path("project.yaml")
        config_file = Path("config.yaml")

        project_file.write_text(
            yaml.safe_dump(
                {
                    "project": {"name": "TShirt Override", "start_date": "2025-01-01"},
                    "tasks": [
                        {
                            "id": "task_001",
                            "name": "Sized Task",
                            "estimate": {"t_shirt_size": "M"},
                        }
                    ],
                }
            )
        )

        config_file.write_text(
            yaml.safe_dump(
                {
                    "t_shirt_sizes": {
                        "story": {
                            "M": {"low": 1, "expected": 2, "high": 3},
                        },
                        "epic": {
                            "M": {"low": 100, "expected": 200, "high": 300},
                        },
                    },
                    "t_shirt_size_default_category": "story",
                }
            )
        )

        story_result = runner.invoke(
            cli,
            [
                "simulate",
                str(project_file),
                "--config",
                str(config_file),
                "--iterations",
                "1",
                "--seed",
                "7",
                "--output-format",
                "json",
                "--output",
                "story_run",
                "-qq",
            ],
        )

        epic_result = runner.invoke(
            cli,
            [
                "simulate",
                str(project_file),
                "--config",
                str(config_file),
                "--tshirt-category",
                "epic",
                "--iterations",
                "1",
                "--seed",
                "7",
                "--output-format",
                "json",
                "--output",
                "epic_run",
                "-qq",
            ],
        )

        story_payload = json.loads(Path("story_run.json").read_text())
        epic_payload = json.loads(Path("epic_run.json").read_text())

    assert story_result.exit_code == 0
    assert epic_result.exit_code == 0
    assert (
        epic_payload["statistics"]["mean_hours"]
        > story_payload["statistics"]["mean_hours"]
    )
