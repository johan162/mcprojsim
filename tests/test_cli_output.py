"""Tests for CLI output rendering paths (plain text, table, exports, target-date)."""

from datetime import date
from pathlib import Path

import yaml
from click.testing import CliRunner

from mcprojsim.cli import cli

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_PROJECT_YAML = {
    "project": {"name": "CLI Output Test", "start_date": "2026-01-05"},
    "tasks": [
        {
            "id": "task_001",
            "name": "Alpha",
            "estimate": {"min": 3, "most_likely": 5, "max": 8},
        },
        {
            "id": "task_002",
            "name": "Beta",
            "estimate": {"min": 2, "most_likely": 4, "max": 6},
            "dependencies": ["task_001"],
        },
    ],
}


class _FakeResults:
    """Fake results with all fields populated for output coverage."""

    project_name = "CLI Output Test"
    mean = 40.0
    median = 38.0
    std_dev = 6.0
    skewness = 0.5
    kurtosis = 0.3
    iterations = 100
    hours_per_day = 8.0
    start_date: date | None = date(2026, 1, 5)
    sensitivity = {"task_001": 0.85, "task_002": -0.42}
    task_slack = {"task_001": 0.0, "task_002": 4.5}
    percentiles = {50: 38.0, 80: 44.0, 90: 48.0}
    effort_percentiles: dict[int, float] = {}
    max_parallel_tasks = 2
    schedule_mode = "resource_constrained"
    resource_constraints_active = True
    resource_wait_time_hours = 1.5
    resource_utilization = 0.7
    calendar_delay_time_hours = 4.0

    def total_effort_hours(self):
        return 60.0

    def delivery_date(self, hours):
        if self.start_date is None:
            return None
        import math
        from datetime import timedelta

        wd = math.ceil(hours / self.hours_per_day)
        current = self.start_date
        added = 0
        while added < wd:
            current += timedelta(days=1)
            if current.weekday() < 5:
                added += 1
        return current

    def get_critical_path_sequences(self, top_n=None):
        return []

    def get_risk_impact_summary(self):
        return {
            "task_001": {
                "mean_impact": 2.0,
                "trigger_rate": 0.25,
                "mean_when_triggered": 8.0,
            },
            "task_002": {
                "mean_impact": 0.0,
                "trigger_rate": 0.0,
                "mean_when_triggered": 0.0,
            },
        }

    def probability_of_completion(self, target_hours):
        # Simple linear model for testing
        if target_hours >= 60:
            return 1.0
        if target_hours <= 20:
            return 0.0
        return (target_hours - 20) / 40


class _FakeEngine:
    def __init__(self, iterations, random_seed, config, show_progress):
        pass

    def run(self, project):
        return _FakeResults()


def _write_project(runner_fs):
    """Write the test project file inside an isolated filesystem."""
    p = Path("project.yaml")
    p.write_text(yaml.safe_dump(_PROJECT_YAML))
    return str(p)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSimulatePlainOutput:
    """Plain text output (no --table)."""

    def test_plain_summary(self, monkeypatch):
        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", _FakeEngine)
        runner = CliRunner()
        with runner.isolated_filesystem():
            pf = _write_project(None)
            result = runner.invoke(cli, ["simulate", pf])
        assert result.exit_code == 0
        assert "Simulation Results" in result.output
        assert "Project: CLI Output Test" in result.output
        assert "Mean: 40.00 hours" in result.output
        assert "Skewness: 0.5000" in result.output

    def test_plain_confidence_intervals(self, monkeypatch):
        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", _FakeEngine)
        runner = CliRunner()
        with runner.isolated_filesystem():
            pf = _write_project(None)
            result = runner.invoke(cli, ["simulate", pf])
        assert "Confidence Intervals" in result.output
        assert "P50:" in result.output
        assert "P80:" in result.output

    def test_plain_sensitivity(self, monkeypatch):
        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", _FakeEngine)
        runner = CliRunner()
        with runner.isolated_filesystem():
            pf = _write_project(None)
            result = runner.invoke(cli, ["simulate", pf])
        assert "Sensitivity Analysis" in result.output
        assert "task_001" in result.output
        assert "+0.8500" in result.output

    def test_plain_slack(self, monkeypatch):
        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", _FakeEngine)
        runner = CliRunner()
        with runner.isolated_filesystem():
            pf = _write_project(None)
            result = runner.invoke(cli, ["simulate", pf])
        assert "Schedule Slack" in result.output
        assert "Critical" in result.output
        assert "4.5h buffer" in result.output

    def test_plain_risk_impact(self, monkeypatch):
        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", _FakeEngine)
        runner = CliRunner()
        with runner.isolated_filesystem():
            pf = _write_project(None)
            result = runner.invoke(cli, ["simulate", pf])
        assert "Risk Impact Analysis" in result.output
        assert "triggers=25.0%" in result.output

    def test_plain_constrained_diagnostics(self, monkeypatch):
        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", _FakeEngine)
        runner = CliRunner()
        with runner.isolated_filesystem():
            pf = _write_project(None)
            result = runner.invoke(cli, ["simulate", pf])
        assert "Schedule Mode: resource_constrained" in result.output
        assert "Constrained Schedule Diagnostics" in result.output
        assert "Average Resource Wait" in result.output


class TestSimulateTableOutput:
    """Table-formatted output (--table)."""

    def test_table_summary(self, monkeypatch):
        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", _FakeEngine)
        runner = CliRunner()
        with runner.isolated_filesystem():
            pf = _write_project(None)
            result = runner.invoke(cli, ["simulate", pf, "--table"])
        assert result.exit_code == 0
        assert "Project Overview" in result.output
        assert "Calendar Time Statistical Summary" in result.output
        assert "Project Effort Statistical Summary" in result.output
        assert "Field" in result.output
        assert "Value" in result.output
        assert "CLI Output Test" in result.output

    def test_table_confidence_intervals(self, monkeypatch):
        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", _FakeEngine)
        runner = CliRunner()
        with runner.isolated_filesystem():
            pf = _write_project(None)
            result = runner.invoke(cli, ["simulate", pf, "--table"])
        assert "Percentile" in result.output
        assert "Working Days" in result.output

    def test_table_sensitivity(self, monkeypatch):
        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", _FakeEngine)
        runner = CliRunner()
        with runner.isolated_filesystem():
            pf = _write_project(None)
            result = runner.invoke(cli, ["simulate", pf, "--table"])
        assert "Correlation" in result.output
        assert "+0.8500" in result.output

    def test_table_slack(self, monkeypatch):
        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", _FakeEngine)
        runner = CliRunner()
        with runner.isolated_filesystem():
            pf = _write_project(None)
            result = runner.invoke(cli, ["simulate", pf, "--table"])
        assert "Slack (hours)" in result.output
        assert "Critical" in result.output

    def test_table_risk_impact(self, monkeypatch):
        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", _FakeEngine)
        runner = CliRunner()
        with runner.isolated_filesystem():
            pf = _write_project(None)
            result = runner.invoke(cli, ["simulate", pf, "--table"])
        assert "Trigger Rate" in result.output
        assert "25.0%" in result.output

    def test_table_constrained_diagnostics(self, monkeypatch):
        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", _FakeEngine)
        runner = CliRunner()
        with runner.isolated_filesystem():
            pf = _write_project(None)
            result = runner.invoke(cli, ["simulate", pf, "--table"])
        assert "Schedule Mode" in result.output
        assert "resource_constrained" in result.output
        assert "Constrained Schedule Diagnostics" in result.output
        assert "Effective Resource Utilization" in result.output


class TestSimulateTargetDate:
    """Target date probability calculation."""

    def test_target_date_with_start_date(self, monkeypatch):
        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", _FakeEngine)
        runner = CliRunner()
        with runner.isolated_filesystem():
            pf = _write_project(None)
            result = runner.invoke(cli, ["simulate", pf, "--target-date", "2026-03-01"])
        assert result.exit_code == 0
        assert "Probability of completing by 2026-03-01" in result.output

    def test_target_date_no_start_date(self, monkeypatch):
        class NoStartResults(_FakeResults):
            start_date = None

            def delivery_date(self, hours):
                return None

        class NoStartEngine:
            def __init__(self, iterations, random_seed, config, show_progress):
                pass

            def run(self, project):
                return NoStartResults()

        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", NoStartEngine)
        runner = CliRunner()
        with runner.isolated_filesystem():
            pf = _write_project(None)
            result = runner.invoke(cli, ["simulate", pf, "--target-date", "2026-03-01"])
        assert "Cannot compute probability" in result.output

    def test_target_date_invalid_format(self, monkeypatch):
        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", _FakeEngine)
        runner = CliRunner()
        with runner.isolated_filesystem():
            pf = _write_project(None)
            result = runner.invoke(cli, ["simulate", pf, "--target-date", "not-a-date"])
        assert "Invalid target date format" in result.output


class TestSimulateExports:
    """Export format dispatch."""

    def test_json_export(self, monkeypatch):
        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", _FakeEngine)
        captured = {}

        def fake_json_export(
            results, output_path, config=None, critical_path_limit=None
        ):
            captured["path"] = str(output_path)

        monkeypatch.setattr("mcprojsim.cli.JSONExporter.export", fake_json_export)
        runner = CliRunner()
        with runner.isolated_filesystem():
            pf = _write_project(None)
            result = runner.invoke(
                cli, ["simulate", pf, "-f", "json", "-o", "out", "--quiet"]
            )
        assert result.exit_code == 0
        assert captured["path"].endswith(".json")

    def test_csv_export(self, monkeypatch):
        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", _FakeEngine)
        captured = {}

        def fake_csv_export(
            results, output_path, config=None, critical_path_limit=None
        ):
            captured["path"] = str(output_path)

        monkeypatch.setattr("mcprojsim.cli.CSVExporter.export", fake_csv_export)
        runner = CliRunner()
        with runner.isolated_filesystem():
            pf = _write_project(None)
            result = runner.invoke(
                cli, ["simulate", pf, "-f", "csv", "-o", "out", "--quiet"]
            )
        assert result.exit_code == 0
        assert captured["path"].endswith(".csv")

    def test_unknown_format_warns(self, monkeypatch):
        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", _FakeEngine)
        runner = CliRunner()
        with runner.isolated_filesystem():
            pf = _write_project(None)
            result = runner.invoke(cli, ["simulate", pf, "-f", "xyz"])
        assert "Unknown format" in result.output

    def test_unsupported_file_extension(self, monkeypatch):
        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", _FakeEngine)
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("project.json").write_text("{}")
            result = runner.invoke(cli, ["simulate", "project.json"])
        assert "Unsupported file format" in result.output


class TestSimulateConfigLoading:
    """Config loading branch in simulate."""

    def test_simulate_with_config_file(self, monkeypatch):
        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", _FakeEngine)
        runner = CliRunner()
        with runner.isolated_filesystem():
            pf = _write_project(None)
            Path("cfg.yaml").write_text(yaml.safe_dump({}))
            result = runner.invoke(
                cli, ["simulate", pf, "--config", "cfg.yaml", "--verbose"]
            )
        assert result.exit_code == 0
        assert "Simulation Results" in result.output
