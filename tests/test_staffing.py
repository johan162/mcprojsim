"""Tests for the staffing analysis module."""

from datetime import date
from pathlib import Path

import numpy as np
import yaml
from click.testing import CliRunner

from mcprojsim.analysis.staffing import (
    StaffingAnalyzer,
    StaffingRecommendation,
    StaffingRow,
)
from mcprojsim.cli import cli
from mcprojsim.config import Config
from mcprojsim.models.simulation import SimulationResults


def _make_results(
    *,
    mean: float = 100.0,
    task_means: dict[str, float] | None = None,
    max_parallel: int = 3,
    hours_per_day: float = 8.0,
    start_date: date | None = date(2026, 1, 5),
) -> SimulationResults:
    """Build a minimal SimulationResults for staffing tests."""
    if task_means is None:
        task_means = {"t1": 80.0, "t2": 60.0, "t3": 40.0}

    durations = np.array([mean] * 10)
    task_durations = {tid: np.array([v] * 10) for tid, v in task_means.items()}

    results = SimulationResults(
        iterations=10,
        project_name="Staffing Test",
        durations=durations,
        task_durations=task_durations,
        max_parallel_tasks=max_parallel,
        hours_per_day=hours_per_day,
        start_date=start_date,
    )
    results.mean = mean
    results.percentiles = {50: mean}
    return results


class TestIndividualProductivity:
    """Tests for the per-person productivity formula."""

    def test_single_person_has_full_productivity(self) -> None:
        assert StaffingAnalyzer.individual_productivity(1, 0.06, 0.25) == 1.0

    def test_two_people_lose_one_overhead_unit(self) -> None:
        result = StaffingAnalyzer.individual_productivity(2, 0.06, 0.25)
        assert abs(result - 0.94) < 1e-9

    def test_large_team_hits_floor(self) -> None:
        # With c=0.08, at n=11: 1 - 0.08*10 = 0.20, should clamp to 0.25
        result = StaffingAnalyzer.individual_productivity(11, 0.08, 0.25)
        assert result == 0.25

    def test_floor_is_respected_for_huge_teams(self) -> None:
        result = StaffingAnalyzer.individual_productivity(100, 0.10, 0.25)
        assert result == 0.25


class TestEffectiveCapacity:
    """Tests for combined team capacity."""

    def test_single_senior(self) -> None:
        cap = StaffingAnalyzer.effective_capacity(1, 0.04, 1.0, 0.25)
        assert abs(cap - 1.0) < 1e-9

    def test_two_junior(self) -> None:
        # ip = max(0.25, 1 - 0.08*1) = 0.92
        # cap = 2 * 0.92 * 0.65 = 1.196
        cap = StaffingAnalyzer.effective_capacity(2, 0.08, 0.65, 0.25)
        assert abs(cap - 1.196) < 1e-9

    def test_capacity_with_floor(self) -> None:
        cap = StaffingAnalyzer.effective_capacity(100, 0.10, 1.0, 0.25)
        assert abs(cap - 100 * 0.25 * 1.0) < 1e-9


class TestCalendarHours:
    """Tests for calendar-duration computation."""

    def test_single_person_gets_full_effort(self) -> None:
        cal = StaffingAnalyzer.calendar_hours(
            total_effort=200.0,
            critical_path_hours=100.0,
            team_size=1,
            communication_overhead=0.06,
            productivity_factor=1.0,
            min_productivity=0.25,
            hours_per_day=8.0,
        )
        assert abs(cal - 200.0) < 1e-9

    def test_critical_path_is_floor(self) -> None:
        """Even with a huge team, calendar time cannot beat the CP."""
        cal = StaffingAnalyzer.calendar_hours(
            total_effort=200.0,
            critical_path_hours=100.0,
            team_size=50,
            communication_overhead=0.04,
            productivity_factor=1.0,
            min_productivity=0.25,
            hours_per_day=8.0,
        )
        assert cal >= 100.0

    def test_two_people_reduces_time(self) -> None:
        cal_1 = StaffingAnalyzer.calendar_hours(200, 80, 1, 0.06, 1.0, 0.25, 8)
        cal_2 = StaffingAnalyzer.calendar_hours(200, 80, 2, 0.06, 1.0, 0.25, 8)
        assert cal_2 < cal_1


class TestTotalEffortHours:
    """Tests for SimulationResults.total_effort_hours()."""

    def test_sum_of_task_means(self) -> None:
        results = _make_results(
            mean=100.0,
            task_means={"a": 40.0, "b": 30.0, "c": 20.0},
        )
        assert abs(results.total_effort_hours() - 90.0) < 1e-9

    def test_fallback_to_mean_when_no_tasks(self) -> None:
        results = _make_results(mean=50.0, task_means={})
        results.task_durations = {}
        assert abs(results.total_effort_hours() - 50.0) < 1e-9


class TestRecommendTeamSize:
    """Tests for StaffingAnalyzer.recommend_team_size()."""

    def test_returns_one_recommendation_per_profile(self) -> None:
        results = _make_results()
        config = Config.get_default()
        recs = StaffingAnalyzer.recommend_team_size(results, config)
        profiles = {r.profile for r in recs}
        assert profiles == {"senior", "mixed", "junior"}

    def test_recommended_size_does_not_exceed_max_parallel(self) -> None:
        results = _make_results(max_parallel=3)
        config = Config.get_default()
        recs = StaffingAnalyzer.recommend_team_size(results, config)
        for rec in recs:
            assert rec.recommended_team_size <= 3

    def test_serial_project_recommends_one(self) -> None:
        """When max_parallel=1, only one person is ever useful."""
        results = _make_results(max_parallel=1)
        config = Config.get_default()
        recs = StaffingAnalyzer.recommend_team_size(results, config)
        for rec in recs:
            assert rec.recommended_team_size == 1

    def test_parallelism_ratio_matches(self) -> None:
        results = _make_results(mean=100.0, task_means={"a": 80.0, "b": 60.0})
        config = Config.get_default()
        recs = StaffingAnalyzer.recommend_team_size(results, config)
        for rec in recs:
            expected_ratio = 140.0 / 100.0
            assert abs(rec.parallelism_ratio - expected_ratio) < 0.01

    def test_recommendation_has_delivery_date(self) -> None:
        results = _make_results(start_date=date(2026, 3, 1))
        config = Config.get_default()
        recs = StaffingAnalyzer.recommend_team_size(results, config)
        for rec in recs:
            assert rec.delivery_date is not None


class TestStaffingTable:
    """Tests for StaffingAnalyzer.calculate_staffing_table()."""

    def test_table_length(self) -> None:
        results = _make_results(max_parallel=4)
        config = Config.get_default()
        table = StaffingAnalyzer.calculate_staffing_table(results, config)
        num_profiles = len(config.staffing.experience_profiles)
        assert len(table) == 4 * num_profiles

    def test_efficiency_decreases_with_team_size(self) -> None:
        results = _make_results(
            mean=100.0,
            task_means={"a": 120.0, "b": 100.0, "c": 80.0},
            max_parallel=5,
        )
        config = Config.get_default()
        table = StaffingAnalyzer.calculate_staffing_table(results, config)
        mixed_rows = [r for r in table if r.profile == "mixed"]
        for i in range(1, len(mixed_rows)):
            assert mixed_rows[i].efficiency <= mixed_rows[i - 1].efficiency + 1e-9

    def test_calendar_days_decrease_with_team_size(self) -> None:
        results = _make_results(
            mean=100.0,
            task_means={"a": 120.0, "b": 100.0, "c": 80.0},
            max_parallel=5,
        )
        config = Config.get_default()
        table = StaffingAnalyzer.calculate_staffing_table(results, config)
        senior_rows = [r for r in table if r.profile == "senior"]
        for i in range(1, len(senior_rows)):
            assert (
                senior_rows[i].calendar_working_days
                <= senior_rows[i - 1].calendar_working_days
            )


class TestExperienceProfilesDiffer:
    """Verify that different profiles produce different recommendations."""

    def test_profiles_differ(self) -> None:
        results = _make_results(
            mean=200.0,
            task_means={"a": 300.0, "b": 200.0, "c": 100.0},
            max_parallel=6,
        )
        config = Config.get_default()
        table = StaffingAnalyzer.calculate_staffing_table(results, config)

        # For team_size=3, senior should have lower calendar days than junior
        senior_3 = next(r for r in table if r.profile == "senior" and r.team_size == 3)
        junior_3 = next(r for r in table if r.profile == "junior" and r.team_size == 3)
        assert senior_3.calendar_working_days <= junior_3.calendar_working_days


class TestStaffingRowSerialization:
    """Test to_dict round-trip for data classes."""

    def test_staffing_row_to_dict(self) -> None:
        row = StaffingRow(
            team_size=3,
            profile="mixed",
            individual_productivity=0.88,
            effective_capacity=2.244,
            calendar_hours=120.0,
            calendar_working_days=15,
            delivery_date=date(2026, 4, 1),
            efficiency=0.9,
        )
        d = row.to_dict()
        assert d["team_size"] == 3
        assert d["profile"] == "mixed"
        assert d["delivery_date"] == "2026-04-01"

    def test_staffing_recommendation_to_dict(self) -> None:
        rec = StaffingRecommendation(
            profile="senior",
            recommended_team_size=2,
            calendar_working_days=20,
            delivery_date=None,
            efficiency=0.95,
            total_effort_hours=300.0,
            critical_path_hours=200.0,
            parallelism_ratio=1.5,
        )
        d = rec.to_dict()
        assert d["recommended_team_size"] == 2
        assert d["delivery_date"] is None


class TestStaffingCLI:
    """CLI integration tests for the staffing feature."""

    def test_staffing_advisory_always_shown(self, monkeypatch) -> None:
        """The staffing advisory line should appear without --staffing flag."""
        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", _FakeStaffingEngine)
        runner = CliRunner()
        with runner.isolated_filesystem():
            pf = _write_project()
            result = runner.invoke(cli, ["simulate", pf])
        assert result.exit_code == 0
        assert "Staffing:" in result.output
        assert "recommended" in result.output
        assert "Total effort:" in result.output

    def test_staffing_flag_shows_table(self, monkeypatch) -> None:
        """--staffing flag should show the full staffing analysis table."""
        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", _FakeStaffingEngine)
        runner = CliRunner()
        with runner.isolated_filesystem():
            pf = _write_project()
            result = runner.invoke(cli, ["simulate", pf, "--staffing"])
        assert result.exit_code == 0
        assert "Staffing Analysis" in result.output
        assert "senior" in result.output
        assert "mixed" in result.output
        assert "junior" in result.output

    def test_staffing_table_format(self, monkeypatch) -> None:
        """--staffing --table should use ASCII table formatting."""
        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", _FakeStaffingEngine)
        runner = CliRunner()
        with runner.isolated_filesystem():
            pf = _write_project()
            result = runner.invoke(cli, ["simulate", pf, "--staffing", "--table"])
        assert result.exit_code == 0
        assert "Eff. Capacity" in result.output


# --- Helpers for CLI tests ---


class _FakeStaffingResults:
    project_name = "Staffing CLI Test"
    mean = 40.0
    median = 38.0
    std_dev = 6.0
    skewness = 0.5
    kurtosis = 0.3
    iterations = 100
    hours_per_day = 8.0
    start_date = date(2026, 1, 5)
    sensitivity = {"task_001": 0.85}
    task_slack = {"task_001": 0.0, "task_002": 4.5}
    percentiles = {50: 38.0, 80: 44.0, 90: 48.0}
    max_parallel_tasks = 3

    def total_effort_hours(self):
        return 80.0

    def delivery_date(self, hours):
        import math
        from datetime import timedelta

        if self.start_date is None:
            return None
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
        return {}

    def probability_of_completion(self, target_hours):
        return 0.8


class _FakeStaffingEngine:
    def __init__(self, iterations, random_seed, config, show_progress):
        pass

    def run(self, project):
        return _FakeStaffingResults()


def _write_project() -> str:
    p = Path("project.yaml")
    p.write_text(
        yaml.safe_dump(
            {
                "project": {
                    "name": "Staffing CLI Test",
                    "start_date": "2026-01-05",
                },
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
        )
    )
    return str(p)
