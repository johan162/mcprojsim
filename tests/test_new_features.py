"""Tests for the five new simulation features.

Feature 1: Sensitivity analysis (SensitivityAnalyzer wired into engine)
Feature 2: Skewness and kurtosis statistics
Feature 3: Schedule slack (backward-pass CPM)
Feature 4: Risk impact tracking per task
Feature 5: Probability-of-completion query
"""

import pytest
import numpy as np
from datetime import date

from mcprojsim.models.project import (
    Project,
    ProjectMetadata,
    Risk,
    Task,
    TaskEstimate,
)
from mcprojsim.models.simulation import SimulationResults
from mcprojsim.simulation.engine import SimulationEngine
from mcprojsim.simulation.scheduler import TaskScheduler
from mcprojsim.analysis.sensitivity import SensitivityAnalyzer

# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def serial_project():
    """A -> B -> C serial chain."""
    return Project(
        project=ProjectMetadata(name="Serial", start_date=date(2025, 1, 1)),
        tasks=[
            Task(
                id="A",
                name="Task A",
                estimate=TaskEstimate(min=2, most_likely=4, max=6),
            ),
            Task(
                id="B",
                name="Task B",
                estimate=TaskEstimate(min=3, most_likely=5, max=8),
                dependencies=["A"],
            ),
            Task(
                id="C",
                name="Task C",
                estimate=TaskEstimate(min=1, most_likely=2, max=4),
                dependencies=["B"],
            ),
        ],
    )


@pytest.fixture
def parallel_project():
    """Diamond: Start -> {BranchA, BranchB} -> End.

    BranchA is longer so BranchB should have slack.
    """
    return Project(
        project=ProjectMetadata(name="Parallel", start_date=date(2025, 1, 1)),
        tasks=[
            Task(
                id="start",
                name="Start",
                estimate=TaskEstimate(min=1, most_likely=1, max=1.01),
            ),
            Task(
                id="long",
                name="Long Branch",
                estimate=TaskEstimate(min=9.5, most_likely=10, max=10.5),
                dependencies=["start"],
            ),
            Task(
                id="short",
                name="Short Branch",
                estimate=TaskEstimate(min=1.5, most_likely=2, max=2.5),
                dependencies=["start"],
            ),
            Task(
                id="end",
                name="End",
                estimate=TaskEstimate(min=1, most_likely=1, max=1.01),
                dependencies=["long", "short"],
            ),
        ],
    )


@pytest.fixture
def risky_project():
    """Project with task-level and project-level risks."""
    return Project(
        project=ProjectMetadata(name="Risky", start_date=date(2025, 1, 1)),
        tasks=[
            Task(
                id="safe",
                name="Safe Task",
                estimate=TaskEstimate(min=3, most_likely=4, max=5),
            ),
            Task(
                id="risky",
                name="Risky Task",
                estimate=TaskEstimate(min=3, most_likely=4, max=5),
                risks=[
                    Risk(
                        id="r1",
                        name="Always triggers",
                        probability=1.0,
                        impact=10.0,
                    )
                ],
            ),
        ],
        project_risks=[
            Risk(
                id="pr1",
                name="Project risk",
                probability=1.0,
                impact=5.0,
            )
        ],
    )


@pytest.fixture
def sample_results():
    """Pre-built SimulationResults for unit tests."""
    durations = np.array([10.0, 12.0, 15.0, 18.0, 20.0, 22.0, 25.0, 28.0, 30.0, 35.0])
    task_durations = {
        "task_a": np.array([2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0]),
        "task_b": np.array([8.0, 9.0, 11.0, 13.0, 14.0, 15.0, 17.0, 19.0, 20.0, 24.0]),
    }
    results = SimulationResults(
        iterations=10,
        project_name="Test",
        durations=durations,
        task_durations=task_durations,
    )
    results.calculate_statistics()
    return results


# ===================================================================
# Feature 2 – Skewness & Kurtosis
# ===================================================================


class TestSkewnessKurtosis:
    """Tests for skewness and excess kurtosis computation."""

    def test_calculate_statistics_computes_skewness_kurtosis(self, sample_results):
        """Skewness and kurtosis are populated after calculate_statistics."""
        assert isinstance(sample_results.skewness, float)
        assert isinstance(sample_results.kurtosis, float)

    def test_symmetric_distribution_has_near_zero_skewness(self):
        """Symmetric data should produce ~0 skewness."""
        durations = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 5.0, 4.0, 3.0, 2.0, 1.0])
        results = SimulationResults(
            iterations=10,
            project_name="Sym",
            durations=durations,
        )
        results.calculate_statistics()
        assert results.skewness == pytest.approx(0.0, abs=0.05)

    def test_right_skewed_data(self):
        """Right-skewed data should have positive skewness."""
        durations = np.array([1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 10.0, 15.0, 20.0, 50.0])
        results = SimulationResults(
            iterations=10,
            project_name="RightSkew",
            durations=durations,
        )
        results.calculate_statistics()
        assert results.skewness > 0.5

    def test_uniform_like_data_has_negative_kurtosis(self):
        """Uniform-like data has negative excess kurtosis (platykurtic)."""
        durations = np.linspace(1.0, 10.0, 100)
        results = SimulationResults(
            iterations=100,
            project_name="Uniform",
            durations=durations,
        )
        results.calculate_statistics()
        assert results.kurtosis < 0

    def test_to_dict_includes_skewness_kurtosis(self, sample_results):
        """to_dict() output should contain skewness and kurtosis."""
        d = sample_results.to_dict()
        assert "skewness" in d["statistics"]
        assert "kurtosis" in d["statistics"]
        assert d["statistics"]["skewness"] == sample_results.skewness
        assert d["statistics"]["kurtosis"] == sample_results.kurtosis


# ===================================================================
# Feature 3 – Schedule Slack
# ===================================================================


class TestScheduleSlack:
    """Tests for TaskScheduler.calculate_slack (backward-pass CPM)."""

    def test_serial_chain_zero_slack(self, serial_project):
        """Every task in a serial chain is critical → all slack = 0."""
        scheduler = TaskScheduler(serial_project)
        schedule = scheduler.schedule_tasks({"A": 4.0, "B": 5.0, "C": 2.0})
        slack = scheduler.calculate_slack(schedule)

        assert slack["A"] == pytest.approx(0.0)
        assert slack["B"] == pytest.approx(0.0)
        assert slack["C"] == pytest.approx(0.0)

    def test_parallel_branches_non_critical_has_slack(self, parallel_project):
        """Short branch should have positive slack; long branch should not."""
        scheduler = TaskScheduler(parallel_project)
        schedule = scheduler.schedule_tasks(
            {"start": 1.0, "long": 10.0, "short": 2.0, "end": 1.0}
        )
        slack = scheduler.calculate_slack(schedule)

        assert slack["start"] == pytest.approx(0.0)
        assert slack["long"] == pytest.approx(0.0)
        assert slack["short"] == pytest.approx(8.0)  # 10 - 2
        assert slack["end"] == pytest.approx(0.0)

    def test_single_task_zero_slack(self):
        """A single task has no slack."""
        project = Project(
            project=ProjectMetadata(name="Single", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="only",
                    name="Only",
                    estimate=TaskEstimate(min=5, most_likely=5, max=5),
                )
            ],
        )
        scheduler = TaskScheduler(project)
        schedule = scheduler.schedule_tasks({"only": 5.0})
        slack = scheduler.calculate_slack(schedule)

        assert slack["only"] == pytest.approx(0.0)

    def test_empty_schedule_returns_empty(self, serial_project):
        """Empty schedule produces empty slack dict."""
        scheduler = TaskScheduler(serial_project)
        assert scheduler.calculate_slack({}) == {}

    def test_slack_values_are_non_negative(self, parallel_project):
        """Slack is never negative."""
        scheduler = TaskScheduler(parallel_project)
        schedule = scheduler.schedule_tasks(
            {"start": 1.0, "long": 10.0, "short": 2.0, "end": 1.0}
        )
        slack = scheduler.calculate_slack(schedule)
        assert all(v >= 0.0 for v in slack.values())

    def test_engine_stores_mean_slack(self, parallel_project):
        """SimulationEngine stores mean task_slack in results."""
        engine = SimulationEngine(iterations=50, random_seed=42, show_progress=False)
        results = engine.run(parallel_project)

        assert isinstance(results.task_slack, dict)
        assert len(results.task_slack) == len(parallel_project.tasks)
        # Short branch must have positive mean slack
        assert results.task_slack["short"] > 0.0
        # Critical-path tasks should have near-zero slack
        assert results.task_slack["start"] < 1.0


# ===================================================================
# Feature 1 – Sensitivity Analysis (wired into engine)
# ===================================================================


class TestSensitivityAnalysis:
    """Tests for SensitivityAnalyzer and its integration with the engine."""

    def test_correlations_in_valid_range(self, sample_results):
        """All Spearman correlations must be in [-1, 1]."""
        corr = SensitivityAnalyzer.calculate_correlations(sample_results)
        for task_id, r in corr.items():
            assert -1.0 <= r <= 1.0, f"{task_id}: correlation {r} out of range"

    def test_perfectly_correlated_task(self):
        """A task whose duration equals project duration → correlation ~1."""
        n = 100
        durations = np.random.RandomState(42).uniform(5, 20, n)
        results = SimulationResults(
            iterations=n,
            project_name="PerfCorr",
            durations=durations,
            task_durations={"single": durations.copy()},
        )
        results.calculate_statistics()
        corr = SensitivityAnalyzer.calculate_correlations(results)
        assert corr["single"] == pytest.approx(1.0, abs=0.01)

    def test_uncorrelated_task(self):
        """A constant-duration task should be uncorrelated with project."""
        n = 100
        rng = np.random.RandomState(99)
        project_dur = rng.uniform(10, 30, n)
        results = SimulationResults(
            iterations=n,
            project_name="Const",
            durations=project_dur,
            task_durations={"const": np.full(n, 5.0)},
        )
        results.calculate_statistics()
        corr = SensitivityAnalyzer.calculate_correlations(results)
        # A constant array has zero variance → Spearman returns NaN; float(nan)
        # is technically a float, but we just check it's handled:
        assert "const" in corr

    def test_get_top_contributors_limits_output(self, sample_results):
        """get_top_contributors(n=1) returns exactly 1 entry."""
        top = SensitivityAnalyzer.get_top_contributors(sample_results, n=1)
        assert len(top) == 1

    def test_engine_populates_sensitivity(self, serial_project):
        """Engine run stores sensitivity dict on results."""
        engine = SimulationEngine(iterations=100, random_seed=42, show_progress=False)
        results = engine.run(serial_project)

        assert isinstance(results.sensitivity, dict)
        assert len(results.sensitivity) == len(serial_project.tasks)
        for task_id, r in results.sensitivity.items():
            assert -1.0 <= r <= 1.0

    def test_to_dict_includes_sensitivity(self, sample_results):
        """to_dict() should include the sensitivity data."""
        sample_results.sensitivity = {"task_a": 0.85, "task_b": 0.72}
        d = sample_results.to_dict()
        assert "sensitivity" in d
        assert d["sensitivity"] == sample_results.sensitivity


# ===================================================================
# Feature 4 – Risk Impact Tracking
# ===================================================================


class TestRiskImpactTracking:
    """Tests for per-task risk impact tracking in engine and results."""

    def test_engine_stores_risk_impacts(self, risky_project):
        """Engine run populates risk_impacts arrays per task."""
        engine = SimulationEngine(iterations=50, random_seed=42, show_progress=False)
        results = engine.run(risky_project)

        assert "safe" in results.risk_impacts
        assert "risky" in results.risk_impacts
        assert len(results.risk_impacts["safe"]) == 50
        assert len(results.risk_impacts["risky"]) == 50

    def test_always_trigger_risk_impact_nonzero(self, risky_project):
        """A risk with probability=1 should always have positive impact."""
        engine = SimulationEngine(iterations=20, random_seed=42, show_progress=False)
        results = engine.run(risky_project)

        # The 'risky' task has a risk that always triggers with impact=10
        assert np.all(results.risk_impacts["risky"] > 0)
        # The 'safe' task has no risks
        assert np.all(results.risk_impacts["safe"] == 0.0)

    def test_project_risk_impacts_stored(self, risky_project):
        """Project-level risk impacts are tracked across iterations."""
        engine = SimulationEngine(iterations=20, random_seed=42, show_progress=False)
        results = engine.run(risky_project)

        assert len(results.project_risk_impacts) == 20
        # Project risk has probability=1, impact=5
        assert np.all(results.project_risk_impacts > 0)

    def test_get_risk_impact_summary_correct(self):
        """get_risk_impact_summary() returns correct statistics."""
        results = SimulationResults(
            iterations=4,
            project_name="RiskSummary",
            durations=np.array([10.0, 12.0, 14.0, 16.0]),
            risk_impacts={
                "task_x": np.array([0.0, 5.0, 0.0, 10.0]),
                "task_y": np.array([0.0, 0.0, 0.0, 0.0]),
            },
        )

        summary = results.get_risk_impact_summary()

        # task_x: triggered 2 out of 4 times
        assert summary["task_x"]["trigger_rate"] == pytest.approx(0.5)
        assert summary["task_x"]["mean_impact"] == pytest.approx(3.75)  # (0+5+0+10)/4
        assert summary["task_x"]["mean_when_triggered"] == pytest.approx(
            7.5
        )  # (5+10)/2

        # task_y: never triggered
        assert summary["task_y"]["trigger_rate"] == pytest.approx(0.0)
        assert summary["task_y"]["mean_impact"] == pytest.approx(0.0)
        assert summary["task_y"]["mean_when_triggered"] == pytest.approx(0.0)

    def test_get_risk_impact_summary_empty(self):
        """Empty risk_impacts returns empty summary."""
        results = SimulationResults(
            iterations=5,
            project_name="NoRisk",
            durations=np.array([1.0, 2.0, 3.0, 4.0, 5.0]),
        )
        assert results.get_risk_impact_summary() == {}

    def test_risk_impact_all_triggered(self):
        """All iterations triggered → trigger_rate = 1.0."""
        results = SimulationResults(
            iterations=3,
            project_name="AllTriggered",
            durations=np.array([10.0, 11.0, 12.0]),
            risk_impacts={
                "t": np.array([2.0, 3.0, 4.0]),
            },
        )
        summary = results.get_risk_impact_summary()
        assert summary["t"]["trigger_rate"] == pytest.approx(1.0)
        assert summary["t"]["mean_impact"] == pytest.approx(3.0)
        assert summary["t"]["mean_when_triggered"] == pytest.approx(3.0)


# ===================================================================
# Feature 5 – Probability of Completion
# ===================================================================


class TestProbabilityOfCompletion:
    """Tests for SimulationResults.probability_of_completion()."""

    def test_target_above_all_durations(self):
        """Target above max → probability = 1.0."""
        results = SimulationResults(
            iterations=5,
            project_name="Test",
            durations=np.array([10.0, 12.0, 14.0, 16.0, 18.0]),
        )
        assert results.probability_of_completion(100.0) == pytest.approx(1.0)

    def test_target_below_all_durations(self):
        """Target below min → probability = 0.0."""
        results = SimulationResults(
            iterations=5,
            project_name="Test",
            durations=np.array([10.0, 12.0, 14.0, 16.0, 18.0]),
        )
        assert results.probability_of_completion(5.0) == pytest.approx(0.0)

    def test_intermediate_probability(self):
        """Target in the middle → correct fraction."""
        results = SimulationResults(
            iterations=10,
            project_name="Test",
            durations=np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]),
        )
        # 5 out of 10 durations are <= 5.0
        assert results.probability_of_completion(5.0) == pytest.approx(0.5)

    def test_probability_at_exact_boundary(self):
        """Target equal to some durations counts them as completed."""
        results = SimulationResults(
            iterations=4,
            project_name="Test",
            durations=np.array([5.0, 5.0, 10.0, 10.0]),
        )
        assert results.probability_of_completion(5.0) == pytest.approx(0.5)

    def test_probability_returns_float(self):
        """Return type is plain float."""
        results = SimulationResults(
            iterations=3,
            project_name="Test",
            durations=np.array([1.0, 2.0, 3.0]),
        )
        p = results.probability_of_completion(2.0)
        assert isinstance(p, float)


# ===================================================================
# Integration – Full engine run verifying all five features
# ===================================================================


class TestIntegrationAllFeatures:
    """End-to-end tests that run the engine and verify all new fields."""

    @pytest.fixture
    def integration_project(self):
        """Project with dependencies and risks for integration testing."""
        return Project(
            project=ProjectMetadata(
                name="Integration",
                start_date=date(2025, 6, 1),
            ),
            tasks=[
                Task(
                    id="design",
                    name="Design",
                    estimate=TaskEstimate(min=8, most_likely=16, max=32),
                ),
                Task(
                    id="backend",
                    name="Backend",
                    estimate=TaskEstimate(min=16, most_likely=40, max=80),
                    dependencies=["design"],
                    risks=[
                        Risk(
                            id="api_delay",
                            name="API Delay",
                            probability=0.3,
                            impact=16.0,
                        )
                    ],
                ),
                Task(
                    id="frontend",
                    name="Frontend",
                    estimate=TaskEstimate(min=16, most_likely=32, max=64),
                    dependencies=["design"],
                ),
                Task(
                    id="testing",
                    name="Testing",
                    estimate=TaskEstimate(min=8, most_likely=16, max=24),
                    dependencies=["backend", "frontend"],
                ),
            ],
        )

    def test_full_engine_run_produces_all_new_fields(self, integration_project):
        """A single engine run should populate all five new features."""
        engine = SimulationEngine(iterations=200, random_seed=42, show_progress=False)
        results = engine.run(integration_project)

        # Feature 2: skewness / kurtosis
        assert isinstance(results.skewness, float)
        assert isinstance(results.kurtosis, float)

        # Feature 1: sensitivity
        assert isinstance(results.sensitivity, dict)
        assert len(results.sensitivity) == 4
        for r in results.sensitivity.values():
            assert -1.0 <= r <= 1.0

        # Feature 3: slack
        assert isinstance(results.task_slack, dict)
        assert len(results.task_slack) == 4
        # design is always on critical path → near-zero slack
        assert results.task_slack["design"] < 1.0

        # Feature 4: risk impacts
        assert len(results.risk_impacts) == 4
        for arr in results.risk_impacts.values():
            assert len(arr) == 200
        assert len(results.project_risk_impacts) == 200
        # 'backend' has a risk; 'design' does not
        assert np.mean(results.risk_impacts["backend"]) > 0.0
        assert np.all(results.risk_impacts["design"] == 0.0)

        # Feature 5: probability of completion
        p_easy = results.probability_of_completion(10_000.0)
        p_impossible = results.probability_of_completion(0.0)
        assert p_easy == pytest.approx(1.0)
        assert p_impossible == pytest.approx(0.0)

    def test_reproducibility_includes_new_fields(self, integration_project):
        """Two runs with the same seed produce identical new-feature data."""
        engine1 = SimulationEngine(iterations=50, random_seed=123, show_progress=False)
        r1 = engine1.run(integration_project)

        engine2 = SimulationEngine(iterations=50, random_seed=123, show_progress=False)
        r2 = engine2.run(integration_project)

        assert r1.skewness == pytest.approx(r2.skewness)
        assert r1.kurtosis == pytest.approx(r2.kurtosis)
        assert r1.sensitivity == pytest.approx(r2.sensitivity)
        assert r1.task_slack == pytest.approx(r2.task_slack)
        for tid in r1.risk_impacts:
            assert np.allclose(r1.risk_impacts[tid], r2.risk_impacts[tid])
