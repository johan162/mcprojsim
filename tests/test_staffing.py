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
from mcprojsim.config import Config, ExperienceProfileConfig
from mcprojsim.models.simulation import CriticalPathRecord, SimulationResults


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
        # cap(50)=12.5, 200/12.5=16 < 100 → clamped to CP = 100 exactly
        assert abs(cal - 100.0) < 1e-9

    def test_two_people_reduces_time(self) -> None:
        cal_1 = StaffingAnalyzer.calendar_hours(200, 80, 1, 0.06, 1.0, 0.25, 8)
        cal_2 = StaffingAnalyzer.calendar_hours(200, 80, 2, 0.06, 1.0, 0.25, 8)
        # n=1: cap=1.0, 200/1=200, max(80,200)=200
        assert abs(cal_1 - 200.0) < 1e-9
        # n=2: ip=0.94, cap=1.88, 200/1.88≈106.383
        assert abs(cal_2 - 200.0 / 1.88) < 1e-9
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
        # Verify exact dates (effort=180, CP=100, start=2026-03-01 Sun)
        by_prof = {r.profile: r for r in recs}
        # Senior: n=2, wd=13 → 2026-03-18 (Wed)
        assert by_prof["senior"].delivery_date == date(2026, 3, 18)
        # Mixed: n=3, wd=13  → 2026-03-18 (Wed)
        assert by_prof["mixed"].delivery_date == date(2026, 3, 18)
        # Junior: n=3, wd=14 → 2026-03-19 (Thu)
        assert by_prof["junior"].delivery_date == date(2026, 3, 19)


class TestStaffingTable:
    """Tests for StaffingAnalyzer.calculate_staffing_table()."""

    def test_table_length(self) -> None:
        results = _make_results(max_parallel=4)
        config = Config.get_default()
        table = StaffingAnalyzer.calculate_staffing_table(results, config)
        num_profiles = len(config.staffing.experience_profiles)
        assert len(table) == 4 * num_profiles

    def test_efficiency_increases_toward_optimal(self) -> None:
        """Efficiency (calendar optimality) rises as team approaches the minimum.

        With effort=300, CP=100, max_parallel=5, mixed profile:
        n=1..4 are effort-bound with decreasing cal_hours;
        n=5 is CP-bound (cal=100, the minimum) and must reach 100 %.
        """
        results = _make_results(
            mean=100.0,
            task_means={"a": 120.0, "b": 100.0, "c": 80.0},
            max_parallel=5,
        )
        config = Config.get_default()
        table = StaffingAnalyzer.calculate_staffing_table(results, config)
        mixed_rows = [r for r in table if r.profile == "mixed"]
        # Efficiency must be non-decreasing as team grows toward the optimal.
        for i in range(1, len(mixed_rows)):
            assert mixed_rows[i].efficiency >= mixed_rows[i - 1].efficiency - 1e-9
        # Last row (n=5, CP-bound) achieves the minimum calendar → 100 % efficiency.
        assert abs(mixed_rows[-1].efficiency - 1.0) < 1e-9
        # First row (n=1, effort-bound, worst schedule) has the lowest efficiency.
        assert mixed_rows[0].efficiency < mixed_rows[-1].efficiency

    def test_calendar_days_decrease_with_team_size(self) -> None:
        results = _make_results(
            mean=100.0,
            task_means={"a": 120.0, "b": 100.0, "c": 80.0},
            max_parallel=5,
        )
        config = Config.get_default()
        table = StaffingAnalyzer.calculate_staffing_table(results, config)
        senior_rows = [r for r in table if r.profile == "senior"]
        # n=1 senior: cal=300/1.0=300, wd=ceil(300/8)=38
        assert senior_rows[0].calendar_working_days == 38
        for i in range(1, len(senior_rows)):
            assert (
                senior_rows[i].calendar_working_days
                <= senior_rows[i - 1].calendar_working_days
            )
        # First four rows strictly decrease: 38, 20, 14, 13
        for i in range(1, 4):
            assert (
                senior_rows[i].calendar_working_days
                < senior_rows[i - 1].calendar_working_days
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
        assert senior_3.calendar_working_days < junior_3.calendar_working_days
        # Senior n=3: cap=2.76, cal=max(200,600/2.76)=217.39, wd=28
        assert senior_3.calendar_working_days == 28
        # Junior n=3: cap=1.638, cal=max(200,600/1.638)=366.30, wd=46
        assert junior_3.calendar_working_days == 46


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
        assert d["individual_productivity"] == 0.88
        assert d["effective_capacity"] == 2.24  # round(2.244, 2)
        assert d["calendar_hours"] == 120.0
        assert d["calendar_working_days"] == 15
        assert d["delivery_date"] == "2026-04-01"
        assert d["efficiency"] == 0.9

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
        assert d["profile"] == "senior"
        assert d["recommended_team_size"] == 2
        assert d["calendar_working_days"] == 20
        assert d["delivery_date"] is None
        assert d["efficiency"] == 0.95
        assert d["total_effort_hours"] == 300.0
        assert d["critical_path_hours"] == 200.0
        assert d["parallelism_ratio"] == 1.5
        assert d["effort_basis"] == "mean"


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
        assert "Staffing (based on" in result.output
        assert "recommended" in result.output
        assert "mixed team" in result.output
        assert "Total effort:" in result.output
        assert "person-hours" in result.output
        assert "Parallelism ratio:" in result.output
        assert "mean effort" in result.output

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
        # Effort basis subtitle should appear under each profile header
        assert "Effort basis: mean" in result.output
        assert "person-hours" in result.output
        assert "critical-path hours" in result.output

    def test_staffing_table_format(self, monkeypatch) -> None:
        """--staffing --table should use ASCII table formatting."""
        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", _FakeStaffingEngine)
        runner = CliRunner()
        with runner.isolated_filesystem():
            pf = _write_project()
            result = runner.invoke(cli, ["simulate", pf, "--staffing", "--table"])
        assert result.exit_code == 0
        assert "Eff. Capacity" in result.output
        assert "Working Days" in result.output
        assert "Delivery Date" in result.output
        assert "Efficiency" in result.output
        # The recommended team size should be marked with *
        assert "*" in result.output

    def test_quiet_suppresses_staffing_advisory(self, monkeypatch) -> None:
        """--quiet should suppress the staffing advisory."""
        monkeypatch.setattr("mcprojsim.cli.SimulationEngine", _FakeStaffingEngine)
        runner = CliRunner()
        with runner.isolated_filesystem():
            pf = _write_project()
            result = runner.invoke(cli, ["simulate", pf, "--quiet"])
        assert result.exit_code == 0
        assert "Staffing:" not in result.output
        assert "Total effort:" not in result.output


class TestRecommendExactValues:
    """Verify exact recommended team sizes and metrics for known inputs."""

    def test_exact_values_default_profiles(self) -> None:
        """Hand-computed expectations for effort=180, CP=100, max_parallel=3."""
        results = _make_results()  # effort=180, CP=100, max=3
        config = Config.get_default()
        recs = StaffingAnalyzer.recommend_team_size(results, config)
        by_prof = {r.profile: r for r in recs}

        # Parallelism ratio: 180/100 = 1.8
        for rec in recs:
            assert abs(rec.parallelism_ratio - 1.8) < 1e-9

        # Senior (c=0.04, f=1.0): n=2, wd=13
        # n=2 first hits CP floor (cal=100), which is the minimum → eff=1.0
        sr = by_prof["senior"]
        assert sr.recommended_team_size == 2
        assert sr.calendar_working_days == 13
        assert abs(sr.efficiency - 1.0) < 1e-9

        # Mixed (c=0.06, f=0.85): n=3, wd=13
        # n=3 first hits CP floor (cal=100) → eff=1.0
        mx = by_prof["mixed"]
        assert mx.recommended_team_size == 3
        assert mx.calendar_working_days == 13
        assert abs(mx.efficiency - 1.0) < 1e-9

        # Junior (c=0.08, f=0.65): n=3, wd=14 (still effort-bound, cal≈109.9)
        # n=3 is the minimum within max_parallel=3 → eff=1.0 by definition
        jr = by_prof["junior"]
        assert jr.recommended_team_size == 3
        assert jr.calendar_working_days == 14
        assert abs(jr.efficiency - 1.0) < 1e-9


class TestThresholdBoundary:
    """Verify the minimum-calendar stopping logic."""

    def test_stops_at_minimum_calendar_team(self) -> None:
        """With effort=1000, CP=50, c=0.06, f=0.85: optimal is n=9.

        Effective capacity peaks around n=9 (formula maximum for c=0.06):
          n=9:  cap≈3.978, cal≈251.4 h (minimum)
          n=10: cap≈3.910, cal≈255.8 h (worse → algorithm stops)
        The algorithm stops at the first local minimum, not at a fixed
        percentage threshold.

        max_parallel=12 keeps all rows below the productivity floor (floor
        kicks in at n≥14 for c=0.06), so the first local minimum at n=9
        is also the global minimum within the table.
        """
        results = _make_results(
            mean=50.0,
            task_means={"big": 1000.0},
            max_parallel=12,
        )
        # Use a single-profile config to isolate the test
        config = Config.get_default()
        config.staffing.experience_profiles = {
            "test": ExperienceProfileConfig(
                productivity_factor=0.85,
                communication_overhead=0.06,
            ),
        }
        recs = StaffingAnalyzer.recommend_team_size(results, config)
        assert len(recs) == 1
        assert recs[0].profile == "test"
        assert recs[0].recommended_team_size == 9
        # All team sizes should have efficiency = min_cal / cal_hours
        table = StaffingAnalyzer.calculate_staffing_table(results, config)
        test_rows = sorted(
            [r for r in table if r.profile == "test"], key=lambda r: r.team_size
        )
        # n=9 has the minimum calendar hours and must have efficiency=1.0
        row_9 = next(r for r in test_rows if r.team_size == 9)
        assert abs(row_9.efficiency - 1.0) < 1e-9
        # n=1 has a long schedule → efficiency much less than 1.0
        assert test_rows[0].efficiency < 0.5


class TestEdgeCases:
    """Edge cases for staffing analysis."""

    def test_start_date_none(self) -> None:
        """All delivery dates should be None when start_date is missing."""
        results = _make_results(start_date=None)
        config = Config.get_default()
        recs = StaffingAnalyzer.recommend_team_size(results, config)
        for rec in recs:
            assert rec.delivery_date is None
        table = StaffingAnalyzer.calculate_staffing_table(results, config)
        for row in table:
            assert row.delivery_date is None

    def test_non_standard_hours_per_day(self) -> None:
        """hours_per_day=6.0 should produce more working days than 8.0."""
        results_6 = _make_results(hours_per_day=6.0)
        results_8 = _make_results(hours_per_day=8.0)
        config = Config.get_default()
        recs_6 = StaffingAnalyzer.recommend_team_size(results_6, config)
        recs_8 = StaffingAnalyzer.recommend_team_size(results_8, config)
        for r6, r8 in zip(
            sorted(recs_6, key=lambda r: r.profile),
            sorted(recs_8, key=lambda r: r.profile),
        ):
            assert r6.calendar_working_days >= r8.calendar_working_days

    def test_efficiency_optimal_row_is_one(self) -> None:
        """The row with minimum calendar hours per profile must have efficiency=1.0.

        With effort=180, CP=100, max_parallel=3:
        - senior: n=2 is CP-bound (cal=100), n=3 also CP-bound → min=100, n=2 first
        - mixed:  n=3 is CP-bound (cal=100) → min=100
        - junior: n=3 is effort-bound (cal≈109.9) → min≈109.9
        All optimal rows must have efficiency=1.0; n=1 must have efficiency<1.0.
        """
        results = _make_results()  # effort=180, CP=100, max_parallel=3
        config = Config.get_default()
        table = StaffingAnalyzer.calculate_staffing_table(results, config)
        for profile in ("senior", "mixed", "junior"):
            prof_rows = sorted(
                [r for r in table if r.profile == profile],
                key=lambda r: r.team_size,
            )
            min_cal = min(r.calendar_hours for r in prof_rows)
            for row in prof_rows:
                expected_eff = min_cal / row.calendar_hours
                assert abs(row.efficiency - expected_eff) < 1e-9, (
                    f"{profile} n={row.team_size}: expected {expected_eff:.6f}, "
                    f"got {row.efficiency:.6f}"
                )
            # n=1 is always effort-bound and slower than the optimal → eff < 1.0
            assert (
                prof_rows[0].efficiency < 1.0 - 1e-9
            ), f"{profile} n=1 should be sub-optimal but got eff={prof_rows[0].efficiency}"

    def test_max_parallel_tasks_zero(self) -> None:
        """max_parallel_tasks=0 should be clamped to 1."""
        results = _make_results(max_parallel=0)
        config = Config.get_default()
        recs = StaffingAnalyzer.recommend_team_size(results, config)
        for rec in recs:
            assert rec.recommended_team_size == 1
        table = StaffingAnalyzer.calculate_staffing_table(results, config)
        # Should produce exactly 1 row per profile
        assert len(table) == len(config.staffing.experience_profiles)
        for row in table:
            assert row.team_size == 1


class TestStaffingExporters:
    """Verify staffing data appears in JSON and CSV exports."""

    def test_json_export_includes_staffing(self, tmp_path) -> None:
        """JSON export should contain a 'staffing' key with all fields."""
        import json

        from mcprojsim.exporters import JSONExporter

        results = _make_export_results()
        output_file = tmp_path / "test_results.json"
        JSONExporter.export(results, output_file)
        with open(output_file) as f:
            data = json.load(f)
        assert "staffing" in data
        staffing = data["staffing"]
        assert "total_effort_hours" in staffing
        assert "max_parallel_tasks" in staffing
        assert "recommendations" in staffing
        assert "table" in staffing
        assert len(staffing["recommendations"]) == 3  # 3 default profiles
        # Each recommendation has all expected keys
        rec = staffing["recommendations"][0]
        for key in (
            "profile",
            "recommended_team_size",
            "calendar_working_days",
            "delivery_date",
            "efficiency",
            "total_effort_hours",
            "critical_path_hours",
            "parallelism_ratio",
            "effort_basis",
        ):
            assert key in rec, f"Missing key '{key}' in recommendation"
        assert staffing["effort_basis"] == "mean"
        assert "effort_hours_used" in staffing
        assert staffing["effort_hours_used"] == staffing["total_effort_hours"]

    def test_csv_export_includes_staffing(self, tmp_path) -> None:
        """CSV export should contain staffing section headers."""
        from mcprojsim.exporters import CSVExporter

        results = _make_export_results()
        output_file = tmp_path / "test_results.csv"
        CSVExporter.export(results, output_file)
        content = output_file.read_text()
        assert "Staffing Recommendations" in content
        assert "Staffing Table" in content
        # Profile names should appear
        assert "senior" in content
        assert "mixed" in content
        assert "junior" in content
        # Effort basis metadata rows
        assert "Staffing Effort Basis" in content
        assert "Staffing Effort Hours Used" in content


class TestCustomProfile:
    """Test with user-defined experience profiles."""

    def test_custom_profile_appears_in_results(self) -> None:
        """A 4th profile should appear in both recommendations and table."""
        results = _make_results(max_parallel=4)
        config = Config.get_default()
        config.staffing.experience_profiles["contractor"] = ExperienceProfileConfig(
            productivity_factor=0.75,
            communication_overhead=0.05,
        )
        recs = StaffingAnalyzer.recommend_team_size(results, config)
        profiles = {r.profile for r in recs}
        assert "contractor" in profiles
        assert len(recs) == 4
        table = StaffingAnalyzer.calculate_staffing_table(results, config)
        # 4 profiles × 4 team sizes = 16 rows
        assert len(table) == 16
        contractor_rows = [r for r in table if r.profile == "contractor"]
        assert len(contractor_rows) == 4


class TestEffortPercentileConfig:
    """Tests for the configurable effort_percentile parameter."""

    @staticmethod
    def _make_varied_results(max_parallel: int = 3) -> SimulationResults:
        """Build SimulationResults with varying durations so percentiles differ."""
        # 100 values linearly spaced so P50 < P80 < P90 < max
        durations = np.linspace(60.0, 140.0, 100)
        task_durations = {
            "t1": np.linspace(30.0, 70.0, 100),
            "t2": np.linspace(20.0, 50.0, 100),
            "t3": np.linspace(10.0, 30.0, 100),
        }
        results = SimulationResults(
            iterations=100,
            project_name="Percentile Test",
            durations=durations,
            task_durations=task_durations,
            max_parallel_tasks=max_parallel,
            hours_per_day=8.0,
            start_date=date(2026, 1, 5),
        )
        results.calculate_statistics()
        return results

    def test_default_uses_mean(self) -> None:
        """Without effort_percentile the basis should be 'mean'."""
        results = self._make_varied_results()
        config = Config.get_default()
        assert config.staffing.effort_percentile is None
        recs = StaffingAnalyzer.recommend_team_size(results, config)
        for rec in recs:
            assert rec.effort_basis == "mean"

    def test_percentile_80_sets_basis(self) -> None:
        """Setting effort_percentile=80 should label basis as 'P80'."""
        results = self._make_varied_results()
        config = Config.get_default()
        config.staffing.effort_percentile = 80
        recs = StaffingAnalyzer.recommend_team_size(results, config)
        for rec in recs:
            assert rec.effort_basis == "P80"

    def test_percentile_produces_higher_effort(self) -> None:
        """P80 effort should be >= mean effort for a right-skewed-ish spread."""
        results = self._make_varied_results()
        config_mean = Config.get_default()
        config_p80 = Config.get_default()
        config_p80.staffing.effort_percentile = 80

        recs_mean = StaffingAnalyzer.recommend_team_size(results, config_mean)
        recs_p80 = StaffingAnalyzer.recommend_team_size(results, config_p80)

        for rm, rp in zip(recs_mean, recs_p80):
            assert rp.total_effort_hours >= rm.total_effort_hours

    def test_table_uses_percentile_effort(self) -> None:
        """Staffing table rows should reflect the higher P80 effort."""
        results = self._make_varied_results()
        config_mean = Config.get_default()
        config_p80 = Config.get_default()
        config_p80.staffing.effort_percentile = 80

        table_mean = StaffingAnalyzer.calculate_staffing_table(results, config_mean)
        table_p80 = StaffingAnalyzer.calculate_staffing_table(results, config_p80)

        # Same number of rows
        assert len(table_mean) == len(table_p80)
        # For the same profile/team-size combos, P80 rows should have >= calendar hours
        for rm, rp in zip(table_mean, table_p80):
            assert rp.calendar_hours >= rm.calendar_hours

    def test_recommendation_to_dict_with_percentile(self) -> None:
        """Recommendation to_dict should include the correct effort_basis."""
        results = self._make_varied_results()
        config = Config.get_default()
        config.staffing.effort_percentile = 90
        recs = StaffingAnalyzer.recommend_team_size(results, config)
        d = recs[0].to_dict()
        assert d["effort_basis"] == "P90"


# --- Helpers for CLI tests ---


def _make_export_results() -> SimulationResults:
    """Build a SimulationResults suitable for exporter tests."""
    durations = np.array([80.0, 90.0, 100.0, 110.0, 120.0])
    task_durations = {
        "task_001": np.array([30.0, 35.0, 40.0, 45.0, 50.0]),
        "task_002": np.array([50.0, 55.0, 60.0, 65.0, 70.0]),
    }
    results = SimulationResults(
        iterations=5,
        project_name="Exporter Test",
        durations=durations,
        task_durations=task_durations,
        critical_path_frequency={"task_001": 5, "task_002": 3},
        critical_path_sequences=[
            CriticalPathRecord(
                path=("task_001", "task_002"),
                count=5,
                frequency=1.0,
            ),
        ],
        max_parallel_tasks=2,
        hours_per_day=8.0,
        start_date=date(2026, 1, 5),
    )
    results.calculate_statistics()
    results.percentile(50)
    results.percentile(90)
    return results


class _FakeStaffingResults:
    project_name = "Staffing CLI Test"
    mean = 40.0
    median = 38.0
    std_dev = 6.0
    skewness = 0.5
    kurtosis = 0.3
    iterations = 100
    hours_per_day = 8.0
    start_date: date | None = date(2026, 1, 5)
    sensitivity = {"task_001": 0.85}
    task_slack = {"task_001": 0.0, "task_002": 4.5}
    percentiles = {50: 38.0, 80: 44.0, 90: 48.0}
    effort_percentiles: dict[int, float] = {}
    max_parallel_tasks = 3

    def total_effort_hours(self):
        return 80.0

    def effort_percentile(self, p):
        return self.effort_percentiles.get(p, self.total_effort_hours())

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
