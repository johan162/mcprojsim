"""Acceptance tests for the two-pass criticality-aware constrained scheduling feature."""

from pathlib import Path

import numpy as np
import pydantic
import pytest

from mcprojsim.config import (
    Config,
    ConstrainedSchedulingAssignmentMode,
)
from mcprojsim.models.project import (
    Project,
    ProjectMetadata,
    ResourceSpec,
    Task,
    TaskEstimate,
)
from mcprojsim.models.simulation import TwoPassDelta
from mcprojsim.parsers import YAMLParser
from mcprojsim.simulation.engine import DurationCache, SimulationEngine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).parent / "fixtures"


def _make_config(
    mode: str = "criticality_two_pass",
    pass1_iterations: int = 200,
) -> Config:
    """Return a config with the requested constrained-scheduling mode."""
    cfg = Config.get_default()
    cfg.constrained_scheduling.assignment_mode = ConstrainedSchedulingAssignmentMode(
        mode
    )
    cfg.constrained_scheduling.pass1_iterations = pass1_iterations
    return cfg


def _load_fixture(name: str) -> Project:
    """Parse a YAML fixture by filename."""
    return YAMLParser().parse_file(str(FIXTURES / name))


# ---------------------------------------------------------------------------
# DurationCache unit tests
# ---------------------------------------------------------------------------


class TestDurationCache:
    """Unit tests for the DurationCache helper class."""

    def test_store_and_retrieve(self):
        """Stored durations are retrievable by (iteration, task_id)."""
        cache = DurationCache()
        cache.store(0, "task_a", 10.0)
        cache.store(0, "task_b", 20.0)
        cache.store(1, "task_a", 11.5)

        assert cache.retrieve(0, "task_a") == pytest.approx(10.0)
        assert cache.retrieve(0, "task_b") == pytest.approx(20.0)
        assert cache.retrieve(1, "task_a") == pytest.approx(11.5)

    def test_missing_key_raises(self):
        """Retrieving a non-existent key raises KeyError."""
        cache = DurationCache()
        with pytest.raises(KeyError, match="task_z"):
            cache.retrieve(0, "task_z")

    def test_len(self):
        """__len__ reports the number of stored entries."""
        cache = DurationCache()
        assert len(cache) == 0
        cache.store(0, "t1", 5.0)
        cache.store(0, "t2", 6.0)
        assert len(cache) == 2

    def test_overwrite(self):
        """Storing the same key twice updates the value."""
        cache = DurationCache()
        cache.store(0, "t", 1.0)
        cache.store(0, "t", 99.0)
        assert cache.retrieve(0, "t") == pytest.approx(99.0)


# ---------------------------------------------------------------------------
# TwoPassDelta unit tests
# ---------------------------------------------------------------------------


class TestTwoPassDelta:
    """Unit tests for the TwoPassDelta traceability model."""

    def test_to_dict_structure(self):
        """to_dict returns a dictionary with the expected top-level keys."""
        delta = TwoPassDelta(
            enabled=True,
            pass1_iterations=500,
            pass2_iterations=1000,
            ranking_method="criticality_index",
            pass1_mean_hours=100.0,
            pass2_mean_hours=95.0,
            delta_mean_hours=-5.0,
            task_criticality_index={"t1": 0.8, "t2": 0.3},
        )
        d = delta.to_dict()
        assert d["enabled"] is True
        assert d["pass1_iterations"] == 500
        assert d["pass2_iterations"] == 1000
        assert d["ranking_method"] == "criticality_index"
        assert "pass1" in d
        assert "pass2" in d
        assert "delta" in d
        assert "task_criticality_index" in d
        assert d["pass1"]["mean_hours"] == pytest.approx(100.0)
        assert d["pass2"]["mean_hours"] == pytest.approx(95.0)
        assert d["delta"]["mean_hours"] == pytest.approx(-5.0)
        assert d["task_criticality_index"]["t1"] == pytest.approx(0.8)

    def test_disabled_payload(self):
        """A default TwoPassDelta with enabled=False returns that state."""
        delta = TwoPassDelta()
        assert delta.enabled is False
        assert delta.to_dict()["enabled"] is False


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


class TestConstrainedSchedulingConfig:
    """Tests for the two-pass additions to ConstrainedSchedulingConfig."""

    def test_default_assignment_mode_is_greedy(self):
        """Default assignment mode should be greedy_single_pass."""
        cfg = Config.get_default()
        assert (
            cfg.constrained_scheduling.assignment_mode
            == ConstrainedSchedulingAssignmentMode.GREEDY_SINGLE_PASS
        )

    def test_criticality_two_pass_mode_accepted(self):
        """criticality_two_pass is a valid assignment_mode value."""
        cfg = Config.get_default()
        cfg.constrained_scheduling.assignment_mode = (
            ConstrainedSchedulingAssignmentMode.CRITICALITY_TWO_PASS
        )
        assert (
            cfg.constrained_scheduling.assignment_mode
            == ConstrainedSchedulingAssignmentMode.CRITICALITY_TWO_PASS
        )

    def test_default_pass1_iterations(self):
        """Default pass1_iterations should be 1000."""
        cfg = Config.get_default()
        assert cfg.constrained_scheduling.pass1_iterations == 1000

    def test_pass1_iterations_must_be_positive(self):
        """pass1_iterations must be > 0."""
        with pytest.raises((pydantic.ValidationError, ValueError)):
            Config.model_validate(
                {
                    "constrained_scheduling": {
                        "pass1_iterations": 0,
                    }
                }
            )

    def test_load_from_yaml(self, tmp_path):
        """Config loaded from YAML correctly parses the two-pass fields."""
        cfg_yaml = tmp_path / "cfg.yaml"
        cfg_yaml.write_text(
            "constrained_scheduling:\n"
            "  assignment_mode: criticality_two_pass\n"
            "  pass1_iterations: 500\n"
        )
        cfg = Config.load_from_file(cfg_yaml)
        assert (
            cfg.constrained_scheduling.assignment_mode
            == ConstrainedSchedulingAssignmentMode.CRITICALITY_TWO_PASS
        )
        assert cfg.constrained_scheduling.pass1_iterations == 500


# ---------------------------------------------------------------------------
# Engine two-pass integration tests
# ---------------------------------------------------------------------------


class TestTwoPassEngine:
    """Integration tests for the SimulationEngine in two-pass mode."""

    def test_two_pass_produces_two_pass_trace(self):
        """Engine in two-pass mode attaches a TwoPassDelta to results."""
        project = _load_fixture("test_fixture_contention.yaml")
        cfg = _make_config(pass1_iterations=200)
        engine = SimulationEngine(
            iterations=300,
            random_seed=42,
            config=cfg,
            show_progress=False,
        )
        results = engine.run(project)
        assert results.two_pass_trace is not None
        assert results.two_pass_trace.enabled is True

    def test_two_pass_trace_has_correct_iteration_counts(self):
        """TwoPassDelta records the actual iteration counts."""
        project = _load_fixture("test_fixture_contention.yaml")
        cfg = _make_config(pass1_iterations=100)
        engine = SimulationEngine(
            iterations=200,
            random_seed=7,
            config=cfg,
            show_progress=False,
        )
        results = engine.run(project)
        tp = results.two_pass_trace
        assert tp is not None
        assert tp.pass1_iterations == 100
        assert tp.pass2_iterations == 200

    def test_pass1_iterations_capped_to_total_iterations(self):
        """When pass1_iterations > iterations, it is capped to iterations."""
        project = _load_fixture("test_fixture_contention.yaml")
        cfg = _make_config(pass1_iterations=5000)
        engine = SimulationEngine(
            iterations=100,
            random_seed=99,
            config=cfg,
            show_progress=False,
        )
        results = engine.run(project)
        tp = results.two_pass_trace
        assert tp is not None
        assert tp.pass1_iterations == 100  # capped

    def test_task_criticality_index_in_range(self):
        """All task criticality indices from pass-1 are in [0.0, 1.0]."""
        project = _load_fixture("test_fixture_contention.yaml")
        cfg = _make_config(pass1_iterations=200)
        engine = SimulationEngine(
            iterations=300,
            random_seed=42,
            config=cfg,
            show_progress=False,
        )
        results = engine.run(project)
        tp = results.two_pass_trace
        assert tp is not None
        for task_id, ci in tp.task_criticality_index.items():
            assert 0.0 <= ci <= 1.0, f"CI out of range for {task_id}: {ci}"

    def test_criticality_index_keys_match_project_tasks(self):
        """Pass-1 criticality index has an entry for every task in the project."""
        project = _load_fixture("test_fixture_contention.yaml")
        cfg = _make_config(pass1_iterations=200)
        engine = SimulationEngine(
            iterations=300,
            random_seed=42,
            config=cfg,
            show_progress=False,
        )
        results = engine.run(project)
        tp = results.two_pass_trace
        assert tp is not None
        expected_ids = {t.id for t in project.tasks}
        assert set(tp.task_criticality_index.keys()) == expected_ids

    def test_single_pass_produces_no_trace(self):
        """Engine in default single-pass mode has two_pass_trace = None."""
        project = _load_fixture("test_fixture_contention.yaml")
        engine = SimulationEngine(
            iterations=200,
            random_seed=42,
            show_progress=False,
        )
        results = engine.run(project)
        assert results.two_pass_trace is None

    def test_two_pass_result_has_standard_statistics(self):
        """Two-pass results have the same standard statistics as single-pass."""
        project = _load_fixture("test_fixture_contention.yaml")
        cfg = _make_config(pass1_iterations=200)
        engine = SimulationEngine(
            iterations=300,
            random_seed=5,
            config=cfg,
            show_progress=False,
        )
        results = engine.run(project)
        assert results.mean > 0
        assert results.std_dev >= 0
        assert results.percentiles
        assert results.sensitivity is not None

    def test_two_pass_no_contention_near_zero_delta(self):
        """With no contention (all tasks have dedicated resources), the two-pass
        delta on the mean should be small relative to project duration."""
        project = _load_fixture("test_fixture_abundant_resources.yaml")
        cfg = _make_config(pass1_iterations=300)
        engine = SimulationEngine(
            iterations=300,
            random_seed=77,
            config=cfg,
            show_progress=False,
        )
        results = engine.run(project)
        tp = results.two_pass_trace
        assert tp is not None
        # No contention: reordering has minimal effect; delta should be
        # within ±20% of the single-pass mean.
        relative_delta = abs(tp.delta_mean_hours) / tp.pass1_mean_hours
        assert relative_delta < 0.20, (
            f"Expected small delta for no-contention project, got "
            f"{tp.delta_mean_hours:.2f}h ({relative_delta:.1%})"
        )

    def test_two_pass_cli_flag_overrides_config(self):
        """SimulationEngine(two_pass=True) sets criticality_two_pass in config."""
        engine = SimulationEngine(
            iterations=50,
            random_seed=1,
            two_pass=True,
            show_progress=False,
        )
        assert (
            engine.config.constrained_scheduling.assignment_mode
            == ConstrainedSchedulingAssignmentMode.CRITICALITY_TWO_PASS
        )

    def test_two_pass_pass1_iterations_override(self):
        """SimulationEngine(pass1_iterations=42) updates config."""
        engine = SimulationEngine(
            iterations=50,
            random_seed=1,
            two_pass=True,
            pass1_iterations=42,
            show_progress=False,
        )
        assert engine.config.constrained_scheduling.pass1_iterations == 42

    def test_two_pass_without_resources_stays_single_pass(self):
        """Two-pass mode is silently ignored when no resources are defined."""
        project = Project(
            project=ProjectMetadata(name="no-resources", start_date="2025-01-06"),
            tasks=[
                Task(
                    id="t1",
                    name="Only task",
                    estimate=TaskEstimate(low=1, expected=2, high=5),
                )
            ],
        )
        cfg = _make_config(pass1_iterations=50)
        engine = SimulationEngine(
            iterations=100,
            random_seed=11,
            config=cfg,
            show_progress=False,
        )
        results = engine.run(project)
        assert results.two_pass_trace is None

    def test_delta_fields_are_consistent(self):
        """Delta fields equal pass2 - pass1 for each reported metric."""
        project = _load_fixture("test_fixture_contention.yaml")
        cfg = _make_config(pass1_iterations=200)
        engine = SimulationEngine(
            iterations=300,
            random_seed=42,
            config=cfg,
            show_progress=False,
        )
        results = engine.run(project)
        tp = results.two_pass_trace
        assert tp is not None

        assert tp.delta_mean_hours == pytest.approx(
            tp.pass2_mean_hours - tp.pass1_mean_hours, abs=1e-6
        )
        assert tp.delta_p80_hours == pytest.approx(
            tp.pass2_p80_hours - tp.pass1_p80_hours, abs=1e-6
        )
        assert tp.delta_p95_hours == pytest.approx(
            tp.pass2_p95_hours - tp.pass1_p95_hours, abs=1e-6
        )
        assert tp.delta_resource_wait_hours == pytest.approx(
            tp.pass2_resource_wait_hours - tp.pass1_resource_wait_hours, abs=1e-6
        )

    def test_two_pass_results_reproducible(self):
        """Same seed produces the same two-pass results on both runs."""
        project = _load_fixture("test_fixture_contention.yaml")
        cfg = _make_config(pass1_iterations=150)

        engine1 = SimulationEngine(
            iterations=200,
            random_seed=9001,
            config=cfg,
            show_progress=False,
        )
        r1 = engine1.run(project)

        cfg2 = _make_config(pass1_iterations=150)
        engine2 = SimulationEngine(
            iterations=200,
            random_seed=9001,
            config=cfg2,
            show_progress=False,
        )
        r2 = engine2.run(project)

        assert r1.mean == pytest.approx(r2.mean, rel=1e-6)
        assert r1.two_pass_trace is not None
        assert r2.two_pass_trace is not None
        assert r1.two_pass_trace.pass1_mean_hours == pytest.approx(
            r2.two_pass_trace.pass1_mean_hours, rel=1e-6
        )

    def test_two_pass_to_dict_includes_traceability(self):
        """SimulationResults.to_dict() includes the two_pass_traceability block."""
        project = _load_fixture("test_fixture_contention.yaml")
        cfg = _make_config(pass1_iterations=100)
        engine = SimulationEngine(
            iterations=150,
            random_seed=3,
            config=cfg,
            show_progress=False,
        )
        results = engine.run(project)
        d = results.to_dict()
        assert "two_pass_traceability" in d
        tpt = d["two_pass_traceability"]
        assert tpt is not None
        assert tpt["enabled"] is True
        assert "pass1" in tpt
        assert "pass2" in tpt
        assert "delta" in tpt


# ---------------------------------------------------------------------------
# Scheduler priority hook tests
# ---------------------------------------------------------------------------


class TestSchedulerPriorityHook:
    """Verify the task_priority parameter in TaskScheduler.schedule_tasks."""

    def _make_two_task_project_with_resources(self) -> Project:
        """Return a minimal two-task project with one shared resource."""
        return Project(
            project=ProjectMetadata(name="p", start_date="2025-01-06"),
            tasks=[
                Task(
                    id="high",
                    name="High priority",
                    estimate=TaskEstimate(low=8, expected=8, high=8),
                    resources=["r1"],
                ),
                Task(
                    id="low",
                    name="Low priority",
                    estimate=TaskEstimate(low=8, expected=8, high=8),
                    resources=["r1"],
                ),
            ],
            resources=[ResourceSpec(name="r1", experience_level=2)],
        )

    def test_no_priority_uses_id_order(self):
        """Without task_priority, tasks with the same earliest start are dispatched
        in ascending task-ID order (greedy default)."""
        from mcprojsim.simulation.scheduler import TaskScheduler

        project = self._make_two_task_project_with_resources()
        scheduler = TaskScheduler(project, np.random.RandomState(0))
        durations = {"high": 8.0, "low": 8.0}
        schedule = scheduler.schedule_tasks(
            durations,
            use_resource_constraints=True,
        )
        # 'high' comes before 'low' alphabetically → 'high' should start first
        assert schedule["high"]["start"] < schedule["low"]["start"] or (
            schedule["high"]["start"] == 0.0
        )

    def test_priority_map_changes_dispatch_order(self):
        """With task_priority giving 'low' a higher score, 'low' is dispatched first."""
        from mcprojsim.simulation.scheduler import TaskScheduler

        project = self._make_two_task_project_with_resources()
        scheduler = TaskScheduler(project, np.random.RandomState(0))
        durations = {"high": 8.0, "low": 8.0}
        priority = {"high": 0.1, "low": 0.9}
        schedule = scheduler.schedule_tasks(
            durations,
            use_resource_constraints=True,
            task_priority=priority,
        )
        # 'low' has higher priority so it should be dispatched first
        assert schedule["low"]["start"] == pytest.approx(0.0)
        assert schedule["high"]["start"] > 0.0


# ---------------------------------------------------------------------------
# CLI integration tests for --two-pass flag
# ---------------------------------------------------------------------------


class TestTwoPassCLI:
    """CLI-level acceptance tests for the --two-pass flag."""

    def test_simulate_two_pass_flag_accepted(self, tmp_path):
        """The --two-pass flag is accepted and produces a valid result."""
        from click.testing import CliRunner

        from mcprojsim.cli import cli

        fixture = Path(__file__).parent / "fixtures" / "test_fixture_contention.yaml"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "simulate",
                str(fixture),
                "--two-pass",
                "--pass1-iterations",
                "50",
                "-n",
                "100",
                "-qq",
            ],
        )
        assert result.exit_code == 0, result.output

    def test_simulate_two_pass_shows_traceability_section(self, tmp_path):
        """The --two-pass flag causes a Two-Pass Scheduling Traceability section
        to appear in the CLI output."""
        from click.testing import CliRunner

        from mcprojsim.cli import cli

        fixture = Path(__file__).parent / "fixtures" / "test_fixture_contention.yaml"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "simulate",
                str(fixture),
                "--two-pass",
                "--pass1-iterations",
                "50",
                "-n",
                "100",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "Two-Pass" in result.output

    def test_simulate_no_two_pass_no_traceability(self, tmp_path):
        """Without --two-pass, no traceability section appears in output."""
        from click.testing import CliRunner

        from mcprojsim.cli import cli

        fixture = Path(__file__).parent / "fixtures" / "test_fixture_contention.yaml"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "simulate",
                str(fixture),
                "-n",
                "50",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "Two-Pass" not in result.output

    def test_simulate_two_pass_json_output(self, tmp_path):
        """--two-pass with JSON export includes two_pass_traceability key."""
        import json

        from click.testing import CliRunner

        from mcprojsim.cli import cli

        fixture = Path(__file__).parent / "fixtures" / "test_fixture_contention.yaml"
        output_base = tmp_path / "out"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "simulate",
                str(fixture),
                "--two-pass",
                "--pass1-iterations",
                "50",
                "-n",
                "100",
                "-f",
                "json",
                "-o",
                str(output_base),
                "-qq",
            ],
        )
        assert result.exit_code == 0, result.output
        out_file = output_base.with_suffix(".json")
        assert out_file.exists()
        data = json.loads(out_file.read_text())
        assert "two_pass_traceability" in data
        tpt = data["two_pass_traceability"]
        assert tpt is not None
        assert tpt["enabled"] is True

    def test_simulate_two_pass_csv_output(self, tmp_path):
        """--two-pass with CSV export includes two-pass section."""
        from click.testing import CliRunner

        from mcprojsim.cli import cli

        fixture = Path(__file__).parent / "fixtures" / "test_fixture_contention.yaml"
        output_base = tmp_path / "out"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "simulate",
                str(fixture),
                "--two-pass",
                "--pass1-iterations",
                "50",
                "-n",
                "100",
                "-f",
                "csv",
                "-o",
                str(output_base),
                "-qq",
            ],
        )
        assert result.exit_code == 0, result.output
        out_file = output_base.with_suffix(".csv")
        assert out_file.exists()
        content = out_file.read_text()
        assert "Two-Pass Scheduling" in content

    def test_simulate_two_pass_html_output(self, tmp_path):
        """--two-pass with HTML export includes Two-Pass Scheduling Traceability section."""
        from click.testing import CliRunner

        from mcprojsim.cli import cli

        fixture = Path(__file__).parent / "fixtures" / "test_fixture_contention.yaml"
        output_base = tmp_path / "out"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "simulate",
                str(fixture),
                "--two-pass",
                "--pass1-iterations",
                "50",
                "-n",
                "100",
                "-f",
                "html",
                "-o",
                str(output_base),
                "-qq",
            ],
        )
        assert result.exit_code == 0, result.output
        out_file = output_base.with_suffix(".html")
        assert out_file.exists()
        html = out_file.read_text()
        assert "Two-Pass Scheduling Traceability" in html

    def test_pass1_iterations_cli_override(self, tmp_path):
        """--pass1-iterations is used by the engine."""
        from click.testing import CliRunner

        from mcprojsim.cli import cli

        fixture = Path(__file__).parent / "fixtures" / "test_fixture_contention.yaml"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "simulate",
                str(fixture),
                "--two-pass",
                "--pass1-iterations",
                "75",
                "-n",
                "100",
                "-qq",
            ],
        )
        assert result.exit_code == 0, result.output
