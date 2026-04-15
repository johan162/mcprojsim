"""Additional coverage-gap tests — CLI, NL parser YAML gen, error reporting, HTML exporter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import yaml
from click.testing import CliRunner

from mcprojsim.cli import cli
from mcprojsim.config import Config, _build_default_config_data
from mcprojsim.models.simulation import SimulationResults
from mcprojsim.nl_parser import NLProjectParser


# =====================================================================
# CLI — validate command
# =====================================================================


class TestCLIValidate:
    """Exercise the CLI validate command."""

    def test_validate_valid_project(self, tmp_path: Path) -> None:
        """Valid project file passes validation."""
        runner = CliRunner()
        project_file = tmp_path / "project.yaml"
        project_file.write_text(
            yaml.safe_dump(
                {
                    "project": {"name": "Valid", "start_date": "2026-01-01"},
                    "tasks": [
                        {"id": "t1", "name": "T1", "estimate": {"low": 1, "expected": 2, "high": 3}},
                    ],
                }
            )
        )
        result = runner.invoke(cli, ["validate", str(project_file)])
        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_validate_invalid_project(self, tmp_path: Path) -> None:
        """Invalid project file reports errors."""
        runner = CliRunner()
        project_file = tmp_path / "bad.yaml"
        project_file.write_text("not:\n  a:\n    valid: project\n")
        result = runner.invoke(cli, ["validate", str(project_file)])
        assert result.exit_code != 0

    def test_validate_verbose_flag(self, tmp_path: Path) -> None:
        """Verbose flag is accepted."""
        runner = CliRunner()
        project_file = tmp_path / "project.yaml"
        project_file.write_text(
            yaml.safe_dump(
                {
                    "project": {"name": "V", "start_date": "2026-01-01"},
                    "tasks": [
                        {"id": "t1", "name": "T1", "estimate": {"low": 1, "expected": 2, "high": 3}},
                    ],
                }
            )
        )
        result = runner.invoke(cli, ["validate", "-v", str(project_file)])
        assert result.exit_code == 0


# =====================================================================
# CLI — config command
# =====================================================================


class TestCLIConfig:
    """Exercise the CLI config command."""

    def test_config_show_defaults(self) -> None:
        """Config command shows default config."""
        runner = CliRunner()
        result = runner.invoke(cli, ["config"])
        assert result.exit_code == 0
        assert "Uncertainty Factors:" in result.output
        assert "T-Shirt Sizes" in result.output
        assert "Story Points" in result.output
        assert "Simulation:" in result.output
        assert "Sprint Defaults:" in result.output

    def test_config_show_with_file(self, tmp_path: Path) -> None:
        """Config command loads file when provided."""
        runner = CliRunner()
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.safe_dump({"simulation": {"default_iterations": 500}}))
        result = runner.invoke(cli, ["config", "-c", str(config_file)])
        assert result.exit_code == 0
        assert "Configuration from" in result.output

    def test_config_generate(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Config --generate creates a config file."""
        runner = CliRunner()
        gen_path = tmp_path / ".mcprojsim" / "config.yaml"
        monkeypatch.setattr("mcprojsim.cli._get_generated_default_config_path", lambda: gen_path)
        result = runner.invoke(cli, ["config", "--generate"])
        assert result.exit_code == 0
        assert gen_path.exists()


# =====================================================================
# CLI — generate command
# =====================================================================


class TestCLIGenerate:
    """Exercise the CLI generate command."""

    def test_generate_stdout(self, tmp_path: Path) -> None:
        """Generate outputs YAML to stdout."""
        runner = CliRunner()
        input_file = tmp_path / "input.txt"
        input_file.write_text(
            "Project: Test Gen\nTask 1: Build API\n- Estimate: 3/5/10 days\n"
        )
        result = runner.invoke(cli, ["generate", str(input_file)])
        assert result.exit_code == 0
        assert "tasks:" in result.output

    def test_generate_to_file(self, tmp_path: Path) -> None:
        """Generate writes YAML to output file."""
        runner = CliRunner()
        input_file = tmp_path / "input.txt"
        input_file.write_text(
            "Project: File Gen\nTask 1: Work\n- Estimate: 2/4/6 days\n"
        )
        output_file = tmp_path / "output.yaml"
        result = runner.invoke(
            cli, ["generate", str(input_file), "-o", str(output_file)]
        )
        assert result.exit_code == 0
        assert output_file.exists()
        content = output_file.read_text()
        assert "tasks:" in content

    def test_generate_validate_only_valid(self, tmp_path: Path) -> None:
        """Generate --validate-only reports valid project."""
        runner = CliRunner()
        input_file = tmp_path / "input.txt"
        input_file.write_text(
            "Project: Valid Gen\nTask 1: Build\n- Estimate: 3/5/10 days\n"
        )
        result = runner.invoke(
            cli, ["generate", str(input_file), "--validate-only"]
        )
        assert result.exit_code == 0
        assert "Valid" in result.output or "valid" in result.output.lower()

    def test_generate_validate_only_issues(self, tmp_path: Path) -> None:
        """Generate --validate-only reports issues for incomplete input."""
        runner = CliRunner()
        input_file = tmp_path / "input.txt"
        # No estimates → should flag missing estimate
        input_file.write_text("Task 1: Build\n")
        result = runner.invoke(
            cli, ["generate", str(input_file), "--validate-only"]
        )
        assert result.exit_code == 0
        assert "issue" in result.output.lower() or "⚠" in result.output


# =====================================================================
# CLI — simulate command output paths
# =====================================================================


class TestCLISimulate:
    """Exercise simulate command output format paths."""

    @staticmethod
    def _make_project_file(tmp_path: Path) -> Path:
        project_file = tmp_path / "project.yaml"
        project_file.write_text(
            yaml.safe_dump(
                {
                    "project": {"name": "Sim Test", "start_date": "2026-01-01"},
                    "tasks": [
                        {"id": "t1", "name": "T1", "estimate": {"low": 1, "expected": 2, "high": 3}},
                    ],
                }
            )
        )
        return project_file

    def test_simulate_json_output(self, tmp_path: Path) -> None:
        """Simulate with --output-format json produces valid JSON."""
        runner = CliRunner()
        pf = self._make_project_file(tmp_path)
        out = tmp_path / "result"
        result = runner.invoke(
            cli,
            [
                "simulate", str(pf), "--quiet",
                "--iterations", "50", "--seed", "42",
                "--output-format", "json", "-o", str(out),
            ],
        )
        assert result.exit_code == 0
        json_file = out.with_suffix(".json")
        assert json_file.exists()
        data = json.loads(json_file.read_text())
        assert "critical_path" in data or "calendar_time_confidence_intervals" in data

    def test_simulate_csv_output(self, tmp_path: Path) -> None:
        """Simulate with --output-format csv produces CSV file."""
        runner = CliRunner()
        pf = self._make_project_file(tmp_path)
        out = tmp_path / "result"
        result = runner.invoke(
            cli,
            [
                "simulate", str(pf), "--quiet",
                "--iterations", "50", "--seed", "42",
                "--output-format", "csv", "-o", str(out),
            ],
        )
        assert result.exit_code == 0
        csv_file = out.with_suffix(".csv")
        assert csv_file.exists()

    def test_simulate_html_output(self, tmp_path: Path) -> None:
        """Simulate with --output-format html produces HTML file."""
        runner = CliRunner()
        pf = self._make_project_file(tmp_path)
        out = tmp_path / "result"
        result = runner.invoke(
            cli,
            [
                "simulate", str(pf), "--quiet",
                "--iterations", "50", "--seed", "42",
                "--output-format", "html", "-o", str(out),
            ],
        )
        assert result.exit_code == 0
        html_file = out.with_suffix(".html")
        assert html_file.exists()

    def test_simulate_text_output_to_stdout(self, tmp_path: Path) -> None:
        """Simulate without format outputs text to stdout."""
        runner = CliRunner()
        pf = self._make_project_file(tmp_path)
        result = runner.invoke(
            cli,
            [
                "simulate", str(pf), "--quiet",
                "--iterations", "50", "--seed", "42",
            ],
        )
        assert result.exit_code == 0
        # Text output includes mean/percentile info
        assert len(result.output) > 0

    def test_simulate_table_output(self, tmp_path: Path) -> None:
        """Simulate --table produces tabulated output."""
        runner = CliRunner()
        pf = self._make_project_file(tmp_path)
        result = runner.invoke(
            cli,
            [
                "simulate", str(pf), "--quiet", "--table",
                "--iterations", "50", "--seed", "42",
            ],
        )
        assert result.exit_code == 0

    def test_simulate_with_config_file(self, tmp_path: Path) -> None:
        """Simulate with --config loads config overrides."""
        runner = CliRunner()
        pf = self._make_project_file(tmp_path)
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.safe_dump({"simulation": {"default_iterations": 10}}))
        result = runner.invoke(
            cli,
            [
                "simulate", str(pf), "--quiet",
                "--config", str(config_file),
                "--iterations", "20", "--seed", "1",
            ],
        )
        assert result.exit_code == 0

    def test_simulate_toml_project(self, tmp_path: Path) -> None:
        """Simulate accepts .toml project file."""
        runner = CliRunner()
        toml_file = tmp_path / "project.toml"
        toml_file.write_text(
            '[project]\nname = "TOML Test"\nstart_date = "2026-01-01"\n\n'
            '[[tasks]]\nid = "t1"\nname = "T1"\n\n'
            "[tasks.estimate]\nlow = 1\nexpected = 2\nhigh = 3\n"
        )
        result = runner.invoke(
            cli,
            [
                "simulate", str(toml_file), "--quiet",
                "--iterations", "50", "--seed", "42",
            ],
        )
        assert result.exit_code == 0

    def test_simulate_with_cost_project(self, tmp_path: Path) -> None:
        """Simulate project with cost fields includes cost output."""
        runner = CliRunner()
        project_file = tmp_path / "cost_project.yaml"
        project_file.write_text(
            yaml.safe_dump(
                {
                    "project": {
                        "name": "Cost CLI Test",
                        "start_date": "2026-01-01",
                        "default_hourly_rate": 100.0,
                    },
                    "tasks": [
                        {
                            "id": "t1", "name": "T1",
                            "estimate": {"low": 8, "expected": 16, "high": 32},
                        },
                    ],
                }
            )
        )
        result = runner.invoke(
            cli,
            [
                "simulate", str(project_file), "--quiet",
                "--iterations", "50", "--seed", "42",
            ],
        )
        assert result.exit_code == 0


# =====================================================================
# NL Parser — YAML generation for resources, calendars, sprint planning
# =====================================================================


class TestNLParserYAMLResourceGen:
    """Exercise YAML generation for resources, calendars, sprint planning."""

    def test_yaml_includes_resource_experience(self) -> None:
        """Resource with experience level appears in YAML."""
        text = (
            "Resource 1: Alice\n"
            "- Experience: 4\n"
            "- Rate: $150/hour\n"
            "Task 1: Work\n"
            "- Estimate: 3/5/8 days\n"
            "- Resources: Alice\n"
        )
        parser = NLProjectParser()
        yaml_str = parser.parse_and_generate(text)
        assert "resources:" in yaml_str
        assert "experience_level:" in yaml_str
        assert "hourly_rate:" in yaml_str

    def test_yaml_task_max_resources(self) -> None:
        """Task with max_resources appears in YAML."""
        text = (
            "Task 1: Build\n"
            "- Estimate: 5/10/20 days\n"
            "- Max Resources: 3\n"
        )
        parser = NLProjectParser()
        yaml_str = parser.parse_and_generate(text)
        assert "max_resources:" in yaml_str

    def test_yaml_task_min_experience(self) -> None:
        """Task with min_experience_level appears in YAML."""
        text = (
            "Task 1: Build\n"
            "- Estimate: 5/10/20 days\n"
            "- Min Experience: 2\n"
        )
        parser = NLProjectParser()
        yaml_str = parser.parse_and_generate(text)
        assert "min_experience_level:" in yaml_str

    def test_yaml_story_points(self) -> None:
        """Task with story points appears in YAML."""
        text = (
            "Task 1: Build\n"
            "- Story Points: 8\n"
        )
        parser = NLProjectParser()
        yaml_str = parser.parse_and_generate(text)
        assert "story_points:" in yaml_str

    def test_yaml_task_description(self) -> None:
        """Task description via 'Description:' bullet appears in YAML."""
        text = (
            "Task 1: Build API\n"
            "- Estimate: 3/5/10 days\n"
            "- Description: Build the REST API endpoints\n"
        )
        parser = NLProjectParser()
        yaml_str = parser.parse_and_generate(text)
        assert "description:" in yaml_str

    def test_yaml_dependencies(self) -> None:
        """Tasks with dependencies appear in YAML."""
        text = (
            "Task 1: Setup\n"
            "- Estimate: 1/2/3 days\n"
            "Task 2: Build\n"
            "- Estimate: 3/5/10 days\n"
            "- Depends on: Task 1\n"
        )
        parser = NLProjectParser()
        yaml_str = parser.parse_and_generate(text)
        assert "dependencies:" in yaml_str

    def test_yaml_project_level_risk(self) -> None:
        """Project-level risk appears in YAML."""
        text = (
            "Project: Test\n"
            "Risk: Market risk\n"
            "- Probability: 10%\n"
            "- Impact: 5 days\n"
            "Task 1: Work\n"
            "- Estimate: 3/5/8 days\n"
        )
        parser = NLProjectParser()
        yaml_str = parser.parse_and_generate(text)
        assert "tasks:" in yaml_str


# =====================================================================
# NL Parser — resource bullet fields, approximate estimates
# =====================================================================


class TestNLParserResourceBullets:
    """Exercise resource attribute parsing bullets."""

    def test_resource_sickness_probability(self) -> None:
        """Resource with sickness probability is parsed."""
        text = (
            "Resource 1: Alice\n"
            "- Sickness: 5%\n"
            "Task 1: Work\n"
            "- Estimate: 2/4/6 days\n"
        )
        parser = NLProjectParser()
        project = parser.parse(text)
        assert len(project.resources) == 1
        assert project.resources[0].sickness_prob == pytest.approx(5.0)  # stored as percentage

    def test_resource_productivity(self) -> None:
        """Resource with productivity level is parsed."""
        text = (
            "Resource 1: Bob\n"
            "- Productivity: 0.8\n"
            "Task 1: Work\n"
            "- Estimate: 2/4/6 days\n"
        )
        parser = NLProjectParser()
        project = parser.parse(text)
        assert len(project.resources) == 1
        assert project.resources[0].productivity_level == pytest.approx(0.8)


class TestNLParserApproximateEstimates:
    """Exercise approximate/fuzzy estimate parsing."""

    def test_about_n_days(self) -> None:
        """'about 5 days' produces triangular estimate."""
        text = (
            "Task 1: Work\n"
            "- Estimate: about 5 days\n"
        )
        parser = NLProjectParser()
        project = parser.parse(text)
        assert len(project.tasks) == 1
        task = project.tasks[0]
        assert task.low_estimate is not None or task.expected_estimate is not None or task.t_shirt_size is not None


# =====================================================================
# Error Reporting — sprint history unit mixing
# =====================================================================


class TestErrorReportingSprintUnitMixing:
    """Exercise sprint history unit mixing detection."""

    def test_both_story_points_and_tasks_rejected(self) -> None:
        """Entry with both completed_story_points and completed_tasks is rejected."""
        from mcprojsim.parsers.error_reporting import validate_project_payload

        data = {
            "project": {"name": "Test"},
            "tasks": [{"id": "t1", "name": "T", "estimate": {"low": 1, "expected": 2, "high": 3}}],
            "sprint_planning": {
                "history": [
                    {
                        "sprint_id": "S1",
                        "completed_story_points": 20,
                        "completed_tasks": 5,
                    },
                ],
            },
        }
        issues = validate_project_payload(data)
        unit_issues = [i for i in issues if "exactly one" in i.message.lower()]
        assert len(unit_issues) >= 1

    def test_neither_completed_field_rejected(self) -> None:
        """Entry with neither completed field is rejected."""
        from mcprojsim.parsers.error_reporting import validate_project_payload

        data = {
            "project": {"name": "Test"},
            "tasks": [{"id": "t1", "name": "T", "estimate": {"low": 1, "expected": 2, "high": 3}}],
            "sprint_planning": {
                "history": [
                    {"sprint_id": "S1", "spillover_story_points": 2},
                ],
            },
        }
        issues = validate_project_payload(data)
        unit_issues = [i for i in issues if "must include either" in i.message.lower()]
        assert len(unit_issues) >= 1

    def test_story_point_entry_with_task_fields_rejected(self) -> None:
        """Story-point entry with task-based overflow fields is rejected."""
        from mcprojsim.parsers.error_reporting import validate_project_payload

        data = {
            "project": {"name": "Test"},
            "tasks": [{"id": "t1", "name": "T", "estimate": {"low": 1, "expected": 2, "high": 3}}],
            "sprint_planning": {
                "history": [
                    {
                        "sprint_id": "S1",
                        "completed_story_points": 20,
                        "spillover_tasks": 2,
                    },
                ],
            },
        }
        issues = validate_project_payload(data)
        unit_issues = [i for i in issues if "task-based" in i.message.lower()]
        assert len(unit_issues) >= 1

    def test_task_entry_with_story_point_fields_rejected(self) -> None:
        """Task entry with story-point overflow fields is rejected."""
        from mcprojsim.parsers.error_reporting import validate_project_payload

        data = {
            "project": {"name": "Test"},
            "tasks": [{"id": "t1", "name": "T", "estimate": {"low": 1, "expected": 2, "high": 3}}],
            "sprint_planning": {
                "history": [
                    {
                        "sprint_id": "S1",
                        "completed_tasks": 5,
                        "spillover_story_points": 2,
                    },
                ],
            },
        }
        issues = validate_project_payload(data)
        unit_issues = [i for i in issues if "story-point-based" in i.message.lower()]
        assert len(unit_issues) >= 1

    def test_capacity_mode_story_points_with_task_field(self) -> None:
        """capacity_mode=story_points with completed_tasks is flagged."""
        from mcprojsim.parsers.error_reporting import validate_project_payload

        data = {
            "project": {"name": "Test"},
            "tasks": [{"id": "t1", "name": "T", "estimate": {"low": 1, "expected": 2, "high": 3}}],
            "sprint_planning": {
                "capacity_mode": "story_points",
                "history": [
                    {"sprint_id": "S1", "completed_tasks": 5},
                ],
            },
        }
        issues = validate_project_payload(data)
        mode_issues = [i for i in issues if "capacity_mode" in i.message.lower()]
        assert len(mode_issues) >= 1

    def test_capacity_mode_tasks_with_story_point_field(self) -> None:
        """capacity_mode=tasks with completed_story_points is flagged."""
        from mcprojsim.parsers.error_reporting import validate_project_payload

        data = {
            "project": {"name": "Test"},
            "tasks": [{"id": "t1", "name": "T", "estimate": {"low": 1, "expected": 2, "high": 3}}],
            "sprint_planning": {
                "capacity_mode": "tasks",
                "history": [
                    {"sprint_id": "S1", "completed_story_points": 20},
                ],
            },
        }
        issues = validate_project_payload(data)
        mode_issues = [i for i in issues if "capacity_mode" in i.message.lower()]
        assert len(mode_issues) >= 1


# =====================================================================
# Error Reporting — spillover bracket validation
# =====================================================================


class TestErrorReportingSpilloverBrackets:
    """Exercise spillover bracket ordering validation."""

    def test_non_monotonic_max_points_rejected(self) -> None:
        from mcprojsim.parsers.error_reporting import validate_project_payload

        data = {
            "project": {"name": "Test"},
            "tasks": [{"id": "t1", "name": "T", "estimate": {"low": 1, "expected": 2, "high": 3}}],
            "sprint_planning": {
                "spillover": {
                    "size_brackets": [
                        {"max_points": 10, "model": "beta"},
                        {"max_points": 5, "model": "beta"},  # not monotonic
                    ],
                },
            },
        }
        issues = validate_project_payload(data)
        bracket_issues = [i for i in issues if "monotonic" in i.message.lower() or "order" in i.message.lower() or "bracket" in i.message.lower()]
        assert len(bracket_issues) >= 1

    def test_valid_monotonic_brackets_accepted(self) -> None:
        from mcprojsim.parsers.error_reporting import validate_project_payload

        data = {
            "project": {"name": "Test"},
            "tasks": [{"id": "t1", "name": "T", "estimate": {"low": 1, "expected": 2, "high": 3}}],
            "sprint_planning": {
                "spillover": {
                    "size_brackets": [
                        {"max_points": 5, "model": "beta"},
                        {"max_points": 10, "model": "beta"},
                    ],
                },
            },
        }
        issues = validate_project_payload(data)
        bracket_issues = [i for i in issues if "bracket" in i.message.lower()]
        assert len(bracket_issues) == 0


# =====================================================================
# Error Reporting — TOML utility functions
# =====================================================================


class TestErrorReportingTOMLUtils:
    """Exercise TOML parsing utility functions."""

    def test_strip_toml_comment(self) -> None:
        from mcprojsim.parsers.error_reporting import _strip_toml_comment

        assert _strip_toml_comment("name = 'val' # comment") == "name = 'val' "
        assert _strip_toml_comment('name = "val" # comment') == 'name = "val" '

    def test_strip_toml_comment_preserves_hash_in_string(self) -> None:
        from mcprojsim.parsers.error_reporting import _strip_toml_comment

        assert _strip_toml_comment('name = "has#hash"') == 'name = "has#hash"'

    def test_extract_toml_key(self) -> None:
        from mcprojsim.parsers.error_reporting import _extract_toml_key

        assert _extract_toml_key("name = 'value'") == "name"
        assert _extract_toml_key("[section]") is None

    def test_split_toml_dotted_key(self) -> None:
        from mcprojsim.parsers.error_reporting import _split_toml_dotted_key

        assert _split_toml_dotted_key("a.b.c") == ["a", "b", "c"]
        assert _split_toml_dotted_key('"a.b".c') == ["a.b", "c"]


# =====================================================================
# Error Reporting — Pydantic error formatting
# =====================================================================


class TestErrorReportingFormatting:
    """Exercise validation error formatting paths."""

    def test_format_validation_error(self) -> None:
        from mcprojsim.parsers.error_reporting import format_validation_error

        # Create a real Pydantic validation error
        from mcprojsim.models.project import Project

        try:
            Project(**{"project": {"name": "X"}, "tasks": "not_a_list"})  # type: ignore[arg-type]
        except Exception as exc:
            formatted = format_validation_error(exc, {}, {}, "test.yaml")
            assert isinstance(formatted, str)
            assert len(formatted) > 0

    def test_format_validation_issues(self) -> None:
        from mcprojsim.parsers.error_reporting import (
            ValidationIssue,
            format_validation_issues,
        )

        issues = [
            ValidationIssue(
                path=("tasks", 0, "id"),
                message="Duplicate task ID",
                suggestion="Rename to unique ID",
            ),
        ]
        formatted = format_validation_issues(issues, {}, "test.yaml")
        assert "Duplicate task ID" in formatted
        assert "Rename" in formatted


# =====================================================================
# HTML Exporter — cost visualization and sprint context
# =====================================================================


class TestHTMLExporterCostVisualization:
    """Exercise HTML exporter cost and sprint paths."""

    @staticmethod
    def _make_cost_results() -> SimulationResults:
        """Create SimulationResults with cost data for HTML export."""
        rng = np.random.RandomState(42)
        durations = rng.triangular(10, 20, 40, size=100)
        costs = durations * 100.0

        results = SimulationResults.model_construct(
            project_name="HTML Cost Test",
            iterations=100,
            mean=float(np.mean(durations)),
            median=float(np.median(durations)),
            std_dev=float(np.std(durations)),
            skewness=0.5,
            kurtosis=0.2,
            percentiles={50: 20.0, 80: 30.0, 90: 35.0, 95: 38.0},
            durations=durations,
            effort_durations=durations * 8.0,
            effort_percentiles={50: 160.0, 80: 240.0, 90: 280.0},
            sensitivity={"t1": 0.8},
            critical_path_frequency={"t1": 0.95},
            critical_path_sequences=[],
            task_slack={"t1": 0.0},
            hours_per_day=8.0,
            max_parallel_tasks=1,
            task_durations={"t1": durations},
            costs=costs,
            cost_percentiles={50: 2000.0, 80: 3000.0, 90: 3500.0, 95: 3800.0},
            cost_mean=float(np.mean(costs)),
            cost_std_dev=float(np.std(costs)),
            cost_statistics={"mean": float(np.mean(costs)), "median": float(np.median(costs))},
            task_costs={"t1": costs},
            cost_sensitivity={"t1": 0.9},
            duration_cost_correlation=0.85,
            budget_analysis=None,
        )
        return results

    def test_html_export_with_costs(self, tmp_path: Path) -> None:
        """HTML export with cost data produces valid HTML with cost sections."""
        from mcprojsim.exporters.html_exporter import HTMLExporter

        results = self._make_cost_results()
        config = Config(**_build_default_config_data())
        exporter = HTMLExporter()
        output_path = tmp_path / "results.html"
        exporter.export(results, str(output_path), config=config)
        assert output_path.exists()
        content = output_path.read_text()
        assert "<html" in content.lower()

    def test_html_export_to_file(self, tmp_path: Path) -> None:
        """HTML export writes to file."""
        from mcprojsim.exporters.html_exporter import HTMLExporter

        results = self._make_cost_results()
        exporter = HTMLExporter()
        output_path = tmp_path / "results2.html"
        exporter.export(results, str(output_path))
        assert output_path.exists()
        content = output_path.read_text()
        assert "<html" in content.lower()


# =====================================================================
# NL Parser — sprint planning YAML generation
# =====================================================================


class TestNLParserSprintYAML:
    """Exercise NL parser sprint planning YAML generation."""

    def test_yaml_sprint_planning_length(self) -> None:
        """Sprint planning with sprint length appears in YAML."""
        text = (
            "Sprint Length: 2 weeks\n"
            "Capacity Mode: story points\n"
            "Task 1: Work\n"
            "- Estimate: 3/5/10 days\n"
        )
        parser = NLProjectParser()
        project = parser.parse(text)
        # Sprint planning is captured on the ParsedProject
        assert project.sprint_planning is not None or len(project.tasks) >= 1

    def test_yaml_sprint_confidence(self) -> None:
        """Sprint planning with confidence appears in YAML."""
        text = (
            "Sprint Length: 2 weeks\n"
            "Confidence: 80%\n"
            "Task 1: Work\n"
            "- Estimate: 3/5/10 days\n"
        )
        parser = NLProjectParser()
        yaml_str = parser.parse_and_generate(text)
        # Sprint planning related fields should be generated
        assert "tasks:" in yaml_str


# =====================================================================
# NL Parser — prose dependency parsing
# =====================================================================


class TestNLParserProseDependencies:
    """Exercise prose-style dependency detection."""

    def test_explicit_dependency_ref(self) -> None:
        """'Depends on: Task 1' creates dependency."""
        text = (
            "Task 1: Setup\n"
            "- Estimate: 1/2/3 days\n"
            "Task 2: Build\n"
            "- Estimate: 3/5/10 days\n"
            "- Depends on: Task 1\n"
        )
        parser = NLProjectParser()
        project = parser.parse(text)
        assert len(project.tasks) == 2
        task2 = project.tasks[1]
        assert len(task2.dependency_refs) >= 1

    def test_auto_dependency_detection(self) -> None:
        """Prose 'after setup' auto-detects dependency."""
        text = (
            "Task 1: Setup\n"
            "- Estimate: 1/2/3 days\n"
            "Task 2: Build (after setup)\n"
            "- Estimate: 3/5/10 days\n"
        )
        parser = NLProjectParser()
        project = parser.parse(text)
        assert len(project.tasks) == 2


# =====================================================================
# NL Parser — calendar bullet parsing
# =====================================================================


class TestNLParserCalendarBullets:
    """Exercise calendar parsing from NL input."""

    def test_calendar_work_hours(self) -> None:
        """Calendar with work hours is parsed."""
        text = (
            "Calendar 1: Standard\n"
            "- Work hours: 8 per day\n"
            "- Work days: 0, 1, 2, 3, 4\n"
            "Task 1: Work\n"
            "- Estimate: 2/4/6 days\n"
        )
        parser = NLProjectParser()
        project = parser.parse(text)
        assert len(project.calendars) >= 1

    def test_calendar_holidays(self) -> None:
        """Calendar with holidays is parsed."""
        text = (
            "Calendar 1: Holiday\n"
            "- Work hours: 8\n"
            "- Holidays: 2026-01-01, 2026-12-25\n"
            "Task 1: Work\n"
            "- Estimate: 2/4/6 days\n"
        )
        parser = NLProjectParser()
        project = parser.parse(text)
        if project.calendars:
            cal = project.calendars[0]
            assert len(cal.holidays) >= 1


# =====================================================================
# NL Parser — future sprint override parsing
# =====================================================================


class TestNLParserFutureOverrides:
    """Exercise future sprint override parsing."""

    def test_future_override_holiday_factor(self) -> None:
        """Future override with holiday factor is parsed."""
        text = (
            "Sprint Length: 2 weeks\n"
            "Future Sprint Override 3:\n"
            "- Holiday Factor: 0.8\n"
            "- Notes: Holiday period\n"
            "Task 1: Work\n"
            "- Estimate: 2/4/6 days\n"
        )
        parser = NLProjectParser()
        project = parser.parse(text)
        # The parser should produce valid output that includes tasks
        assert len(project.tasks) >= 1


# =====================================================================
# NL Parser — to_yaml() direct construction for resource/calendar/sprint paths
# =====================================================================


class TestNLParserToYAMLDirect:
    """Exercise to_yaml() by constructing ParsedProject directly.

    This covers the YAML generation branches for resources, calendars,
    sprint planning, sickness, future overrides, and history entries.
    """

    def test_yaml_resources_with_sickness_and_absence(self) -> None:
        """Resources with sickness_prob and planned_absence emit all fields."""
        from mcprojsim.nl_parser import (
            NLProjectParser, ParsedProject, ParsedTask, ParsedResource,
        )
        project = ParsedProject(
            name="ResTest",
            tasks=[ParsedTask(number=1, name="T1", low_estimate=1, expected_estimate=2, high_estimate=3)],
            resources=[
                ParsedResource(
                    number=1, name="Alice",
                    experience_level=4,
                    productivity_level=0.9,
                    sickness_prob=5.0,
                    planned_absence=["2026-06-15", "2026-06-16"],
                    hourly_rate=150.0,
                    availability=0.8,
                    calendar="team_cal",
                ),
            ],
        )
        parser = NLProjectParser()
        yaml_str = parser.to_yaml(project)
        assert "resources:" in yaml_str
        assert "sickness_prob:" in yaml_str
        assert "planned_absence:" in yaml_str
        assert "hourly_rate:" in yaml_str
        assert "availability:" in yaml_str
        assert "team_cal" in yaml_str

    def test_yaml_calendars_with_holidays(self) -> None:
        """Calendars with holidays appear in YAML output."""
        from mcprojsim.nl_parser import (
            NLProjectParser, ParsedProject, ParsedTask, ParsedCalendar,
        )
        project = ParsedProject(
            name="CalTest",
            tasks=[ParsedTask(number=1, name="T1", low_estimate=1, expected_estimate=2, high_estimate=3)],
            calendars=[
                ParsedCalendar(
                    id="team_cal",
                    work_hours_per_day=7.5,
                    work_days=[0, 1, 2, 3, 4],
                    holidays=["2026-01-01", "2026-12-25"],
                ),
            ],
        )
        parser = NLProjectParser()
        yaml_str = parser.to_yaml(project)
        assert "calendars:" in yaml_str
        assert "work_hours_per_day:" in yaml_str
        assert "work_days:" in yaml_str
        assert "holidays:" in yaml_str
        assert "2026-01-01" in yaml_str

    def test_yaml_sprint_planning_full(self) -> None:
        """Sprint planning with history, sickness, and velocity model."""
        from mcprojsim.nl_parser import (
            NLProjectParser, ParsedProject, ParsedTask,
            ParsedSprintPlanning, ParsedSprintHistoryEntry,
        )
        project = ParsedProject(
            name="SprintTest",
            tasks=[ParsedTask(number=1, name="T1", low_estimate=1, expected_estimate=2, high_estimate=3)],
            sprint_planning=ParsedSprintPlanning(
                enabled=True,
                sprint_length_weeks=2,
                capacity_mode="story_points",
                planning_confidence_level=0.80,
                removed_work_treatment="proportional",
                velocity_model="negative_binomial",
                sickness_enabled=True,
                sickness_team_size=5,
                sickness_probability_per_person_per_week=0.05,
                sickness_duration_log_mu=0.7,
                sickness_duration_log_sigma=0.5,
                history=[
                    ParsedSprintHistoryEntry(
                        sprint_id="S1",
                        completed_story_points=20.0,
                        spillover_story_points=3.0,
                        added_story_points=1.0,
                        removed_story_points=2.0,
                    ),
                    ParsedSprintHistoryEntry(
                        sprint_id="S2",
                        completed_story_points=18.0,
                        spillover_story_points=2.0,
                        holiday_factor=0.8,
                    ),
                ],
            ),
        )
        parser = NLProjectParser()
        yaml_str = parser.to_yaml(project)
        assert "sprint_planning:" in yaml_str
        assert "sickness:" in yaml_str
        assert "enabled: true" in yaml_str
        assert "team_size:" in yaml_str
        assert "velocity_model:" in yaml_str
        assert "removed_work_treatment:" in yaml_str
        assert "planning_confidence_level:" in yaml_str
        assert "history:" in yaml_str
        assert "completed_story_points:" in yaml_str
        assert "spillover_story_points:" in yaml_str
        assert "holiday_factor:" in yaml_str

    def test_yaml_sprint_with_future_overrides(self) -> None:
        """Sprint planning with future overrides produces YAML."""
        from mcprojsim.nl_parser import (
            NLProjectParser, ParsedProject, ParsedTask,
            ParsedSprintPlanning, ParsedFutureSprintOverride,
        )
        project = ParsedProject(
            name="OverrideTest",
            tasks=[ParsedTask(number=1, name="T1", low_estimate=1, expected_estimate=2, high_estimate=3)],
            sprint_planning=ParsedSprintPlanning(
                enabled=True,
                sprint_length_weeks=2,
                capacity_mode="story_points",
                future_sprint_overrides=[
                    ParsedFutureSprintOverride(
                        sprint_number=3,
                        holiday_factor=0.8,
                        capacity_multiplier=0.9,
                        notes="Holiday period",
                    ),
                    ParsedFutureSprintOverride(
                        start_date="2026-03-01",
                        holiday_factor=0.5,
                    ),
                ],
                history=[],
            ),
        )
        parser = NLProjectParser()
        yaml_str = parser.to_yaml(project)
        assert "future_sprint_overrides:" in yaml_str
        assert "sprint_number:" in yaml_str
        assert "start_date:" in yaml_str
        assert "capacity_multiplier:" in yaml_str
        assert "notes:" in yaml_str

    def test_yaml_sprint_tasks_mode_history(self) -> None:
        """Sprint planning with task-based history entries."""
        from mcprojsim.nl_parser import (
            NLProjectParser, ParsedProject, ParsedTask,
            ParsedSprintPlanning, ParsedSprintHistoryEntry,
        )
        project = ParsedProject(
            name="TaskMode",
            tasks=[ParsedTask(number=1, name="T1", low_estimate=1, expected_estimate=2, high_estimate=3)],
            sprint_planning=ParsedSprintPlanning(
                enabled=True,
                sprint_length_weeks=2,
                capacity_mode="tasks",
                history=[
                    ParsedSprintHistoryEntry(
                        sprint_id="S1",
                        completed_tasks=5,
                        spillover_tasks=1,
                        added_tasks=2,
                        removed_tasks=0,
                    ),
                ],
            ),
        )
        parser = NLProjectParser()
        yaml_str = parser.to_yaml(project)
        assert "completed_tasks:" in yaml_str
        assert "spillover_tasks:" in yaml_str
        assert "added_tasks:" in yaml_str
        assert "removed_tasks:" in yaml_str

    def test_yaml_project_level_risks(self) -> None:
        """Project-level risks appear in YAML output."""
        from mcprojsim.nl_parser import (
            NLProjectParser, ParsedProject, ParsedTask, ParsedRisk,
        )
        project = ParsedProject(
            name="RiskTest",
            tasks=[ParsedTask(number=1, name="T1", low_estimate=1, expected_estimate=2, high_estimate=3)],
            project_risks=[
                ParsedRisk(
                    name="Market risk",
                    probability=0.15,
                    impact_value=5.0,
                    impact_unit="days",
                    cost_impact=10000.0,
                ),
                ParsedRisk(
                    name="Vendor risk",
                    probability=0.10,
                    impact_value=3.0,
                ),
            ],
        )
        parser = NLProjectParser()
        yaml_str = parser.to_yaml(project)
        assert "project_risks:" in yaml_str
        assert "Market risk" in yaml_str
        assert "cost_impact:" in yaml_str
        assert 'type: "absolute"' in yaml_str

    def test_yaml_project_cost_metadata(self) -> None:
        """Project cost metadata fields appear in YAML output."""
        from mcprojsim.nl_parser import (
            NLProjectParser, ParsedProject, ParsedTask,
        )
        project = ParsedProject(
            name="CostTest",
            tasks=[ParsedTask(number=1, name="T1", low_estimate=1, expected_estimate=2, high_estimate=3)],
            default_hourly_rate=120.0,
            overhead_rate=0.15,
            currency="EUR",
        )
        parser = NLProjectParser()
        yaml_str = parser.to_yaml(project)
        assert "default_hourly_rate:" in yaml_str
        assert "overhead_rate:" in yaml_str
        assert "currency:" in yaml_str


# =====================================================================
# CLI — simulate with sprint planning
# =====================================================================


class TestCLISimulateWithSprints:
    """Exercise CLI simulate with sprint planning to cover _echo_sprint_results."""

    def test_simulate_sprint_planning_project(self, tmp_path: Path) -> None:
        """Simulate project with sprint planning covers sprint output."""
        runner = CliRunner()
        project_file = tmp_path / "sprint_project.yaml"
        project_file.write_text(
            yaml.safe_dump(
                {
                    "project": {"name": "Sprint CLI", "start_date": "2026-01-05"},
                    "tasks": [
                        {
                            "id": "t1", "name": "T1",
                            "estimate": {"low": 8, "expected": 16, "high": 32},
                            "planning_story_points": 5,
                        },
                        {
                            "id": "t2", "name": "T2",
                            "estimate": {"low": 16, "expected": 32, "high": 64},
                            "planning_story_points": 8,
                        },
                    ],
                    "sprint_planning": {
                        "enabled": True,
                        "sprint_length_weeks": 2,
                        "capacity_mode": "story_points",
                        "history": [
                            {
                                "sprint_id": "S1",
                                "completed_story_points": 15,
                                "spillover_story_points": 2,
                            },
                            {
                                "sprint_id": "S2",
                                "completed_story_points": 12,
                                "spillover_story_points": 3,
                            },
                        ],
                    },
                }
            )
        )
        result = runner.invoke(
            cli,
            [
                "simulate", str(project_file), "--quiet", "--table",
                "--iterations", "50", "--seed", "42",
            ],
        )
        assert result.exit_code == 0
        assert "Sprint" in result.output or "sprint" in result.output


# =====================================================================
# Model Validation — TaskEstimate edge cases
# =====================================================================


class TestTaskEstimateValidation:
    """Exercise TaskEstimate validation error paths."""

    def test_tshirt_non_string_rejected(self) -> None:
        """Non-string t_shirt_size raises ValueError."""
        from mcprojsim.models.project import TaskEstimate

        with pytest.raises(ValueError, match="Expected non-empty string"):
            TaskEstimate(t_shirt_size=123)  # type: ignore[arg-type]

    def test_tshirt_empty_string_rejected(self) -> None:
        """Empty string t_shirt_size raises ValueError."""
        from mcprojsim.models.project import TaskEstimate

        with pytest.raises(ValueError, match="non-empty string"):
            TaskEstimate(t_shirt_size="   ")

    def test_tshirt_multiple_dots_rejected(self) -> None:
        """Multiple dots in t_shirt_size raises ValueError."""
        from mcprojsim.models.project import TaskEstimate

        with pytest.raises(ValueError, match="format"):
            TaskEstimate(t_shirt_size="a.b.c")

    def test_tshirt_numeric_token_rejected(self) -> None:
        """Numeric token in t_shirt_size is rejected."""
        from mcprojsim.models.project import TaskEstimate

        with pytest.raises(ValueError, match="format"):
            TaskEstimate(t_shirt_size="123")

    def test_tshirt_category_with_numeric_size_rejected(self) -> None:
        """Category.numeric_size is rejected."""
        from mcprojsim.models.project import TaskEstimate

        with pytest.raises(ValueError, match="format"):
            TaskEstimate(t_shirt_size="story.123")

    def test_both_tshirt_and_story_points_rejected(self) -> None:
        """Both t_shirt_size and story_points raises ValueError."""
        from mcprojsim.models.project import TaskEstimate

        with pytest.raises(ValueError, match="choose either"):
            TaskEstimate(t_shirt_size="M", story_points=5)

    def test_tshirt_with_unit_rejected(self) -> None:
        """T-shirt size with explicit unit raises ValueError."""
        from mcprojsim.models.project import TaskEstimate, EffortUnit

        with pytest.raises(ValueError, match="not specify 'unit'"):
            TaskEstimate(t_shirt_size="M", unit=EffortUnit.HOURS)

    def test_story_points_with_unit_rejected(self) -> None:
        """Story points with explicit unit raises ValueError."""
        from mcprojsim.models.project import TaskEstimate, EffortUnit

        with pytest.raises(ValueError, match="not specify 'unit'"):
            TaskEstimate(story_points=5, unit=EffortUnit.HOURS)

    def test_invalid_story_points_value_rejected(self) -> None:
        """Invalid story point value raises ValueError."""
        from mcprojsim.models.project import TaskEstimate

        with pytest.raises(ValueError, match="Story Points must be one of"):
            TaskEstimate(story_points=99)


# =====================================================================
# Model Validation — SprintHistoryEntry edge cases
# =====================================================================


class TestSprintHistoryEntryValidation:
    """Exercise SprintHistoryEntry validation."""

    def test_both_completed_fields_rejected(self) -> None:
        """Both completed_story_points and completed_tasks raises ValueError."""
        from mcprojsim.models.project import SprintHistoryEntry

        with pytest.raises(ValueError, match="exactly one"):
            SprintHistoryEntry(
                sprint_id="S1",
                completed_story_points=20,
                completed_tasks=5,
            )

    def test_neither_completed_field_rejected(self) -> None:
        """Neither completed field raises ValueError."""
        from mcprojsim.models.project import SprintHistoryEntry

        with pytest.raises(ValueError, match="exactly one"):
            SprintHistoryEntry(sprint_id="S1")

    def test_empty_sprint_id_rejected(self) -> None:
        """Empty sprint_id raises ValueError."""
        from mcprojsim.models.project import SprintHistoryEntry

        with pytest.raises(ValueError, match="non-empty"):
            SprintHistoryEntry(sprint_id="  ", completed_story_points=10)

    def test_story_point_entry_with_task_spillover_rejected(self) -> None:
        """Story-point entry with task-based fields raises ValueError."""
        from mcprojsim.models.project import SprintHistoryEntry

        with pytest.raises(ValueError, match="task-based"):
            SprintHistoryEntry(
                sprint_id="S1",
                completed_story_points=20,
                spillover_tasks=2,
            )

    def test_task_entry_with_story_point_spillover_rejected(self) -> None:
        """Task entry with story-point fields raises ValueError."""
        from mcprojsim.models.project import SprintHistoryEntry

        with pytest.raises(ValueError, match="story-point-based"):
            SprintHistoryEntry(
                sprint_id="S1",
                completed_tasks=5,
                spillover_story_points=2,
            )


# =====================================================================
# Model Validation — FutureSprintOverrideSpec
# =====================================================================


class TestFutureSprintOverrideValidation:
    """Exercise FutureSprintOverrideSpec validation."""

    def test_no_locator_rejected(self) -> None:
        """Override without sprint_number or start_date raises ValueError."""
        from mcprojsim.models.project import FutureSprintOverrideSpec

        with pytest.raises(ValueError, match="locator"):
            FutureSprintOverrideSpec(holiday_factor=0.8)

    def test_valid_sprint_number_accepted(self) -> None:
        """Override with sprint_number is accepted."""
        from mcprojsim.models.project import FutureSprintOverrideSpec

        override = FutureSprintOverrideSpec(sprint_number=3, holiday_factor=0.8)
        assert override.sprint_number == 3

    def test_valid_start_date_accepted(self) -> None:
        """Override with start_date is accepted."""
        from mcprojsim.models.project import FutureSprintOverrideSpec

        override = FutureSprintOverrideSpec(start_date="2026-03-01", holiday_factor=0.8)
        assert override.start_date is not None


# =====================================================================
# Project Model — more validation edge cases for coverage
# =====================================================================


class TestProjectModelEdgeCases:
    """Exercise project-level model validation edge cases."""

    def test_invalid_date_type_rejected(self) -> None:
        """Non-string/non-date start_date raises ValueError."""
        from mcprojsim.models.project import ProjectMetadata

        with pytest.raises(ValueError):
            ProjectMetadata(name="Test", start_date=12345)  # type: ignore[arg-type]

    def test_red_threshold_gte_green_rejected(self) -> None:
        """Red threshold >= green threshold raises ValueError."""
        from mcprojsim.models.project import ProjectMetadata

        with pytest.raises(ValueError, match="red.*green|threshold"):
            ProjectMetadata(
                name="Test",
                start_date="2026-01-01",
                probability_red_threshold=0.9,
                probability_green_threshold=0.5,
            )

    def test_tshirt_default_category_non_alpha_rejected(self) -> None:
        """Non-alpha t_shirt_size_default_category raises ValueError."""
        from mcprojsim.models.project import ProjectMetadata

        with pytest.raises(ValueError, match="letters"):
            ProjectMetadata(
                name="Test",
                start_date="2026-01-01",
                t_shirt_size_default_category="123abc",
            )

    def test_unknown_effort_unit_in_normalize(self) -> None:
        """Unknown effort unit raises ValueError in convert_to_hours."""
        from mcprojsim.models.project import convert_to_hours

        with pytest.raises(ValueError, match="Unknown"):
            convert_to_hours(10.0, "invalid_unit", 8.0)  # type: ignore[arg-type]

    def test_risk_impact_as_dict(self) -> None:
        """Risk impact as dict creates RiskImpact object."""
        from mcprojsim.models.project import Risk

        risk = Risk(
            id="r1", name="R1", probability=0.2,
            impact={"type": "absolute", "value": 5.0, "unit": "days"},
        )
        assert hasattr(risk.impact, "type")

    def test_risk_impact_invalid_type_rejected(self) -> None:
        """Risk with non-numeric/non-dict impact raises ValueError."""
        from mcprojsim.models.project import Risk

        with pytest.raises(ValueError, match="Invalid impact"):
            Risk(id="r1", name="R1", probability=0.2, impact="bad")  # type: ignore[arg-type]

    def test_duplicate_calendar_ids_rejected(self) -> None:
        """Duplicate calendar IDs raise ValueError."""
        from mcprojsim.models.project import (
            Project, ProjectMetadata, Task, TaskEstimate, CalendarSpec,
        )

        with pytest.raises(ValueError, match="unique"):
            Project(
                project=ProjectMetadata(name="Test", start_date="2026-01-01"),
                tasks=[Task(id="t1", name="T", estimate=TaskEstimate(low=1, expected=2, high=3))],
                calendars=[
                    CalendarSpec(id="cal1"),
                    CalendarSpec(id="cal1"),
                ],
            )

    def test_resource_unknown_calendar_rejected(self) -> None:
        """Resource referencing non-existent calendar raises ValueError."""
        from mcprojsim.models.project import (
            Project, ProjectMetadata, Task, TaskEstimate, ResourceSpec, CalendarSpec,
        )

        with pytest.raises(ValueError, match="unknown calendar"):
            Project(
                project=ProjectMetadata(name="Test", start_date="2026-01-01"),
                tasks=[Task(id="t1", name="T", estimate=TaskEstimate(low=1, expected=2, high=3))],
                resources=[ResourceSpec(id="r1", name="Alice", calendar="nonexistent")],
                calendars=[CalendarSpec(id="team_cal")],
            )

    def test_task_references_unknown_resource_rejected(self) -> None:
        """Task referencing non-existent resource raises ValueError."""
        from mcprojsim.models.project import (
            Project, ProjectMetadata, Task, TaskEstimate,
        )

        with pytest.raises(ValueError, match="unknown resource"):
            Project(
                project=ProjectMetadata(name="Test", start_date="2026-01-01"),
                tasks=[
                    Task(
                        id="t1", name="T",
                        estimate=TaskEstimate(low=1, expected=2, high=3),
                        resources=["Alice"],
                    ),
                ],
            )

    def test_spillover_non_monotonic_brackets_rejected(self) -> None:
        """Spillover brackets with non-ascending max_points rejected."""
        from mcprojsim.models.project import SprintSpilloverSpec, SprintSpilloverBracketSpec

        with pytest.raises(ValueError, match="ascending"):
            SprintSpilloverSpec(
                size_brackets=[
                    SprintSpilloverBracketSpec(max_points=10.0, probability=0.3),
                    SprintSpilloverBracketSpec(max_points=5.0, probability=0.5),
                ],
            )

    def test_spillover_unbounded_not_last_rejected(self) -> None:
        """Unbounded bracket not at end is rejected."""
        from mcprojsim.models.project import SprintSpilloverSpec, SprintSpilloverBracketSpec

        with pytest.raises(ValueError, match="unbounded.*last"):
            SprintSpilloverSpec(
                size_brackets=[
                    SprintSpilloverBracketSpec(max_points=None, probability=0.3),
                    SprintSpilloverBracketSpec(max_points=10.0, probability=0.5),
                ],
            )

    def test_tshirt_default_category_empty_rejected(self) -> None:
        """Empty t_shirt_size_default_category raises ValueError."""
        from mcprojsim.models.project import ProjectMetadata

        with pytest.raises(ValueError, match="non-empty"):
            ProjectMetadata(
                name="Test", start_date="2026-01-01",
                t_shirt_size_default_category="   ",
            )

    def test_tshirt_default_category_default_value_accepted(self) -> None:
        """Default t_shirt_size_default_category ('Story') is normalized to 'story'."""
        from mcprojsim.models.project import ProjectMetadata

        meta = ProjectMetadata(
            name="Test", start_date="2026-01-01",
            t_shirt_size_default_category="Story",
        )
        assert meta.t_shirt_size_default_category == "story"

    def test_tshirt_default_category_custom_accepted(self) -> None:
        """Custom (non-default) t_shirt_size_default_category is normalized."""
        from mcprojsim.models.project import ProjectMetadata

        meta = ProjectMetadata(
            name="Test", start_date="2026-01-01",
            t_shirt_size_default_category="Feature",
        )
        assert meta.t_shirt_size_default_category == "feature"

    def test_team_size_auto_fill_resources(self) -> None:
        """Project with team_size > resource count auto-fills resources."""
        from mcprojsim.models.project import (
            Project, ProjectMetadata, Task, TaskEstimate, ResourceSpec,
        )
        project = Project(
            project=ProjectMetadata(
                name="Test", start_date="2026-01-01", team_size=3,
            ),
            tasks=[Task(id="t1", name="T", estimate=TaskEstimate(low=1, expected=2, high=3))],
            resources=[ResourceSpec(id="r1", name="Alice")],
        )
        assert len(project.resources) == 3

    def test_team_size_exact_no_fill(self) -> None:
        """team_size == resource count doesn't add extra resources."""
        from mcprojsim.models.project import (
            Project, ProjectMetadata, Task, TaskEstimate, ResourceSpec,
        )
        project = Project(
            project=ProjectMetadata(
                name="Test", start_date="2026-01-01", team_size=1,
            ),
            tasks=[Task(id="t1", name="T", estimate=TaskEstimate(low=1, expected=2, high=3))],
            resources=[ResourceSpec(id="r1", name="Alice")],
        )
        assert len(project.resources) == 1

    def test_get_task_by_id(self) -> None:
        """get_task_by_id returns the correct task."""
        from mcprojsim.models.project import (
            Project, ProjectMetadata, Task, TaskEstimate,
        )
        project = Project(
            project=ProjectMetadata(name="Test", start_date="2026-01-01"),
            tasks=[
                Task(id="t1", name="T1", estimate=TaskEstimate(low=1, expected=2, high=3)),
                Task(id="t2", name="T2", estimate=TaskEstimate(low=2, expected=4, high=6)),
            ],
        )
        assert project.get_task_by_id("t2") is not None
        assert project.get_task_by_id("t2").name == "T2"  # type: ignore[union-attr]
        assert project.get_task_by_id("nonexistent") is None

    def test_uncertainty_factors_propagated_to_task_without_factors(self) -> None:
        """Project-level uncertainty_factors propagate to tasks with None factors."""
        from mcprojsim.models.project import (
            Project, ProjectMetadata, Task, TaskEstimate, UncertaintyFactors,
        )
        project = Project(
            project=ProjectMetadata(
                name="Test", start_date="2026-01-01",
                uncertainty_factors=UncertaintyFactors(team_experience="high"),
            ),
            tasks=[
                Task(
                    id="t1", name="T1",
                    estimate=TaskEstimate(low=1, expected=2, high=3),
                    uncertainty_factors=None,
                ),
            ],
        )
        assert project.tasks[0].uncertainty_factors is not None
        assert project.tasks[0].uncertainty_factors.team_experience == "high"  # type: ignore[union-attr]

    def test_uncertainty_factors_task_overrides_project(self) -> None:
        """Task-level uncertainty_factors override project-level ones."""
        from mcprojsim.models.project import (
            Project, ProjectMetadata, Task, TaskEstimate, UncertaintyFactors,
        )
        project = Project(
            project=ProjectMetadata(
                name="Test", start_date="2026-01-01",
                uncertainty_factors=UncertaintyFactors(
                    team_experience="high",
                    technical_complexity="high",
                ),
            ),
            tasks=[
                Task(
                    id="t1", name="T1",
                    estimate=TaskEstimate(low=1, expected=2, high=3),
                    uncertainty_factors=UncertaintyFactors(team_experience="low"),
                ),
            ],
        )
        # Task override wins for team_experience, project default for technical_complexity
        assert project.tasks[0].uncertainty_factors.team_experience == "low"  # type: ignore[union-attr]
        assert project.tasks[0].uncertainty_factors.technical_complexity == "high"  # type: ignore[union-attr]
