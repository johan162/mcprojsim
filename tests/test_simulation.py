"""Tests for simulation components."""

import pytest
import numpy as np
from datetime import date

from mcprojsim.simulation.distributions import (
    DistributionSampler,
    fit_shifted_lognormal,
)
from mcprojsim.simulation.risk_evaluator import RiskEvaluator
from mcprojsim.simulation.scheduler import TaskScheduler
from mcprojsim.simulation.engine import SimulationEngine
from mcprojsim.models.project import (
    Project,
    ProjectMetadata,
    Task,
    TaskEstimate,
    Risk,
    DistributionType,
    UncertaintyFactors,
)
from mcprojsim.config import Config


class TestDistributionSampler:
    """Tests for distribution sampler."""

    def test_sample_triangular(self):
        """Test sampling from triangular distribution."""
        sampler = DistributionSampler(np.random.RandomState(42))
        estimate = TaskEstimate(
            distribution=DistributionType.TRIANGULAR,
            low=1.0,
            expected=2.0,
            high=5.0,
        )

        samples = [sampler.sample(estimate) for _ in range(100)]
        assert all(1.0 <= s <= 5.0 for s in samples)
        assert np.mean(samples) > 1.0
        assert np.mean(samples) < 5.0

    def test_sample_lognormal(self):
        """Test sampling from lognormal distribution."""
        sampler = DistributionSampler(np.random.RandomState(42))
        estimate = TaskEstimate(
            distribution=DistributionType.LOGNORMAL,
            low=2.0,
            expected=5.0,
            high=16.0,
        )

        samples = [sampler.sample(estimate) for _ in range(100)]
        assert all(s > 2.0 for s in samples)

    def test_fit_shifted_lognormal_matches_mode_and_percentile(self):
        """The fitted shifted-lognormal should honor mode and chosen percentile."""
        low = 2.0
        expected = 5.0
        high = 16.0
        z95 = 1.6448536269514722

        mu, sigma = fit_shifted_lognormal(low, expected, high, z95)
        shifted_mode = np.exp(mu - sigma**2)
        shifted_p95 = np.exp(mu + z95 * sigma)

        assert shifted_mode == pytest.approx(expected - low)
        assert shifted_p95 == pytest.approx(high - low)

    def test_sample_reproducibility(self):
        """Test that sampling is reproducible with same seed."""
        estimate = TaskEstimate(low=1, expected=2, high=5)

        sampler1 = DistributionSampler(np.random.RandomState(42))
        samples1 = [sampler1.sample(estimate) for _ in range(10)]

        sampler2 = DistributionSampler(np.random.RandomState(42))
        samples2 = [sampler2.sample(estimate) for _ in range(10)]

        assert np.allclose(samples1, samples2)

    def test_sample_unknown_distribution(self):
        """Test that unknown distribution type raises error."""
        # from mcprojsim.models.project import DistributionType

        sampler = DistributionSampler(np.random.RandomState(42))

        # Create an estimate with an invalid distribution type
        estimate = TaskEstimate(low=1, expected=2, high=5)
        estimate.distribution = "invalid_distribution"  # type: ignore

        with pytest.raises(ValueError, match="Unknown distribution type"):
            sampler.sample(estimate)


class TestRiskEvaluator:
    """Tests for risk evaluator."""

    def test_evaluate_risk_not_triggered(self):
        """Test risk that doesn't trigger."""
        evaluator = RiskEvaluator(np.random.RandomState(42))
        risk = Risk(
            id="risk_001",
            name="Test Risk",
            probability=0.0,  # Never triggers
            impact=10.0,
        )

        impact = evaluator.evaluate_risk(risk)
        assert impact == 0.0

    def test_evaluate_risk_always_triggered(self):
        """Test risk that always triggers."""
        evaluator = RiskEvaluator(np.random.RandomState(42))
        risk = Risk(
            id="risk_001",
            name="Test Risk",
            probability=1.0,  # Always triggers
            impact=10.0,
        )

        impact = evaluator.evaluate_risk(risk)
        assert impact == 10.0

    def test_evaluate_multiple_risks(self):
        """Test evaluating multiple risks."""
        evaluator = RiskEvaluator(np.random.RandomState(42))
        risks = [
            Risk(id="r1", name="Risk 1", probability=1.0, impact=5.0),
            Risk(id="r2", name="Risk 2", probability=1.0, impact=3.0),
        ]

        total_impact = evaluator.evaluate_risks(risks)
        assert total_impact == 8.0


class TestTaskScheduler:
    """Tests for task scheduler."""

    @pytest.fixture
    def simple_project(self):
        """Create a simple project."""
        return Project(
            project=ProjectMetadata(name="Test", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=2, high=5),
                    dependencies=[],
                ),
                Task(
                    id="task_002",
                    name="Task 2",
                    estimate=TaskEstimate(low=1, expected=2, high=5),
                    dependencies=["task_001"],
                ),
            ],
        )

    def test_schedule_tasks_no_dependencies(self):
        """Test scheduling tasks with no dependencies."""
        project = Project(
            project=ProjectMetadata(name="Test", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=2, high=5),
                )
            ],
        )

        scheduler = TaskScheduler(project)
        schedule = scheduler.schedule_tasks({"task_001": 5.0})

        assert schedule["task_001"]["start"] == 0.0
        assert schedule["task_001"]["end"] == 5.0
        assert schedule["task_001"]["duration"] == 5.0

    def test_schedule_tasks_with_dependencies(self, simple_project):
        """Test scheduling tasks with dependencies."""
        scheduler = TaskScheduler(simple_project)
        schedule = scheduler.schedule_tasks({"task_001": 3.0, "task_002": 4.0})

        assert schedule["task_001"]["start"] == 0.0
        assert schedule["task_001"]["end"] == 3.0
        assert schedule["task_002"]["start"] == 3.0
        assert schedule["task_002"]["end"] == 7.0

    def test_topological_sort(self, simple_project):
        """Test topological sort."""
        scheduler = TaskScheduler(simple_project)
        sorted_tasks = scheduler._topological_sort()

        # task_001 should come before task_002
        assert sorted_tasks.index("task_001") < sorted_tasks.index("task_002")

    def test_get_critical_path(self, simple_project):
        """Test critical path identification."""
        scheduler = TaskScheduler(simple_project)
        schedule = scheduler.schedule_tasks({"task_001": 3.0, "task_002": 4.0})
        critical_path = scheduler.get_critical_path(schedule)

        # Both tasks should be on critical path
        assert "task_001" in critical_path
        assert "task_002" in critical_path

    def test_schedule_tasks_with_resource_constraints_serializes_work(self):
        """Resource-constrained mode should serialize work with one shared member."""
        project = Project(
            project=ProjectMetadata(name="Res Test", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                ),
                Task(
                    id="task_002",
                    name="Task 2",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                ),
            ],
            resources=[
                {"name": "res_a", "experience_level": 2, "productivity_level": 1.0}
            ],
        )

        scheduler = TaskScheduler(project)
        unconstrained = scheduler.schedule_tasks(
            {"task_001": 4.0, "task_002": 4.0},
            use_resource_constraints=False,
        )
        constrained = scheduler.schedule_tasks(
            {"task_001": 4.0, "task_002": 4.0},
            use_resource_constraints=True,
        )

        unconstrained_end = max(info["end"] for info in unconstrained.values())
        constrained_end = max(info["end"] for info in constrained.values())

        assert unconstrained_end == 4.0
        assert constrained_end == 8.0

    def test_schedule_tasks_with_productivity_and_max_resources(self):
        """Resource-constrained mode should scale elapsed duration by capacity."""
        project = Project(
            project=ProjectMetadata(name="Cap Test", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                    max_resources=2,
                    min_experience_level=2,
                )
            ],
            resources=[
                {"name": "res_a", "experience_level": 2, "productivity_level": 1.0},
                {"name": "res_b", "experience_level": 3, "productivity_level": 1.0},
            ],
        )

        scheduler = TaskScheduler(project)
        effort_hours = 2 * TaskScheduler.MIN_EFFORT_PER_ASSIGNEE_HOURS
        constrained = scheduler.schedule_tasks(
            {"task_001": effort_hours},
            use_resource_constraints=True,
            hours_per_day=24.0,
        )

        assert constrained["task_001"]["start"] == 0.0
        assert constrained["task_001"]["end"] == effort_hours / 2


class TestSimulationEngineDistributionResolution:
    """Tests for project/task distribution default resolution."""

    def test_project_default_lognormal_applies_to_explicit_estimates(self):
        project = Project(
            project=ProjectMetadata(
                name="Default Lognormal",
                start_date=date(2025, 1, 1),
                distribution=DistributionType.LOGNORMAL,
            ),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=2, expected=5, high=16),
                )
            ],
        )

        engine = SimulationEngine(
            iterations=20, random_seed=42, config=Config.get_default()
        )
        results = engine.run(project)

        assert np.all(results.task_durations["task_001"] > 2.0)

    def test_task_distribution_overrides_project_default(self):
        project = Project(
            project=ProjectMetadata(
                name="Override Default",
                start_date=date(2025, 1, 1),
                distribution=DistributionType.LOGNORMAL,
            ),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(
                        distribution=DistributionType.TRIANGULAR,
                        low=2,
                        expected=5,
                        high=16,
                    ),
                )
            ],
        )

        engine = SimulationEngine(
            iterations=50, random_seed=42, config=Config.get_default()
        )
        resolved = engine._resolve_estimate(
            project.tasks[0], project.project.distribution
        )

        assert resolved.distribution == DistributionType.TRIANGULAR
        assert resolved.low == 2.0
        assert resolved.expected == 5.0
        assert resolved.high == 16.0

    def test_schedule_tasks_practical_cap_limits_over_assignment(self):
        """Auto-cap should prevent assigning too many resources to small tasks."""
        project = Project(
            project=ProjectMetadata(
                name="Practical Cap Test", start_date=date(2025, 1, 1)
            ),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                    max_resources=8,
                )
            ],
            resources=[
                {"name": "res_a", "experience_level": 2, "productivity_level": 1.0},
                {"name": "res_b", "experience_level": 2, "productivity_level": 1.0},
                {"name": "res_c", "experience_level": 2, "productivity_level": 1.0},
                {"name": "res_d", "experience_level": 2, "productivity_level": 1.0},
                {"name": "res_e", "experience_level": 2, "productivity_level": 1.0},
                {"name": "res_f", "experience_level": 2, "productivity_level": 1.0},
                {"name": "res_g", "experience_level": 2, "productivity_level": 1.0},
                {"name": "res_h", "experience_level": 2, "productivity_level": 1.0},
            ],
        )

        scheduler = TaskScheduler(project)
        effort_hours = 8.0
        expected_cap = TaskScheduler._practical_task_resource_cap(effort_hours)
        constrained = scheduler.schedule_tasks(
            {"task_001": effort_hours},
            use_resource_constraints=True,
        )

        assert expected_cap == 1
        assert constrained["task_001"]["end"] == effort_hours / expected_cap

    def test_practical_task_resource_cap_applies_coordination_ceiling(self):
        """Auto-cap should not exceed the global per-task coordination ceiling."""
        assert (
            TaskScheduler._practical_task_resource_cap(400.0)
            == TaskScheduler.MAX_ASSIGNEES_PER_TASK
        )

    def test_schedule_tasks_resource_constraints_are_calendar_aware(self):
        """Constrained mode should skip weekend non-working days."""
        project = Project(
            project=ProjectMetadata(name="Calendar Test", start_date=date(2025, 1, 3)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                    resources=["res_a"],
                )
            ],
            resources=[
                {"name": "res_a", "experience_level": 2, "productivity_level": 1.0}
            ],
        )

        scheduler = TaskScheduler(project)
        schedule = scheduler.schedule_tasks(
            {"task_001": 16.0},
            use_resource_constraints=True,
            start_date=project.project.start_date,
            hours_per_day=8.0,
        )

        # Friday 8h + weekend gap + Monday 8h => end at hour 80 from Friday 00:00
        assert schedule["task_001"]["end"] == 80.0

    def test_schedule_tasks_resource_constraints_respect_planned_absence(self):
        """Constrained mode should treat planned_absence dates as non-working."""
        project = Project(
            project=ProjectMetadata(name="Absence Test", start_date=date(2025, 1, 6)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                    resources=["res_a"],
                )
            ],
            resources=[
                {
                    "name": "res_a",
                    "experience_level": 2,
                    "productivity_level": 1.0,
                    "planned_absence": ["2025-01-06"],
                }
            ],
        )

        scheduler = TaskScheduler(project)
        schedule = scheduler.schedule_tasks(
            {"task_001": 8.0},
            use_resource_constraints=True,
            start_date=project.project.start_date,
            hours_per_day=8.0,
        )

        # Monday absent; task runs Tuesday 00:00-08:00 => end at hour 32
        assert schedule["task_001"]["start"] == 24.0
        assert schedule["task_001"]["end"] == 32.0

    def test_get_critical_paths_returns_full_sequences(self):
        """Test tracing all full critical path sequences in a branching schedule."""
        project = Project(
            project=ProjectMetadata(name="Branching", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="Start",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                ),
                Task(
                    id="task_002",
                    name="Branch A",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                    dependencies=["task_001"],
                ),
                Task(
                    id="task_003",
                    name="Branch B",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                    dependencies=["task_001"],
                ),
            ],
        )

        scheduler = TaskScheduler(project)
        schedule = scheduler.schedule_tasks(
            {"task_001": 1.0, "task_002": 1.0, "task_003": 1.0}
        )

        critical_paths = scheduler.get_critical_paths(schedule)

        assert critical_paths == [
            ("task_001", "task_002"),
            ("task_001", "task_003"),
        ]

    def test_get_critical_path_empty_schedule(self):
        """Test critical path with empty schedule."""
        project = Project(
            project=ProjectMetadata(name="Test", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=2, high=5),
                )
            ],
        )
        scheduler = TaskScheduler(project)
        critical_path = scheduler.get_critical_path({})
        assert len(critical_path) == 0

    def test_topological_sort_circular_dependency(self):
        """Test that circular dependency is detected in topological sort."""
        # Note: Circular dependencies are caught during Project validation
        # This test verifies the scheduler's own circular dependency detection
        # We can't easily create a project with circular dependencies through
        # normal means, so we test that the project validation catches it
        from mcprojsim.models.project import (
            Project,
            ProjectMetadata,
            Task,
            TaskEstimate,
        )
        from datetime import date

        # Try to create a project with circular dependency - should fail at validation
        with pytest.raises(ValueError, match="Circular dependency"):
            Project(
                project=ProjectMetadata(name="Test", start_date=date(2025, 1, 1)),
                tasks=[
                    Task(
                        id="task_001",
                        name="Task 1",
                        estimate=TaskEstimate(low=1, expected=2, high=5),
                        dependencies=["task_002"],
                    ),
                    Task(
                        id="task_002",
                        name="Task 2",
                        estimate=TaskEstimate(low=1, expected=2, high=5),
                        dependencies=["task_001"],
                    ),
                ],
            )


class TestSimulationEngine:
    """Tests for simulation engine."""

    @pytest.fixture
    def simple_project(self):
        """Create a simple project."""
        return Project(
            project=ProjectMetadata(name="Test", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=2, high=5),
                )
            ],
        )

    def test_engine_initialization(self):
        """Test engine initialization."""
        engine = SimulationEngine(iterations=100, random_seed=42)
        assert engine.iterations == 100
        assert engine.random_seed == 42

    def test_run_simulation(self, simple_project):
        """Test running simulation."""
        engine = SimulationEngine(iterations=10, random_seed=42, show_progress=False)
        results = engine.run(simple_project)

        assert results.iterations == 10
        assert results.project_name == "Test"
        assert len(results.durations) == 10
        assert results.mean > 0
        assert results.median > 0

    def test_run_simulation_populates_constrained_diagnostics(self):
        """Resource-constrained runs should include constrained diagnostics."""
        project = Project(
            project=ProjectMetadata(name="Constrained", start_date=date(2025, 1, 6)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=8, expected=9, high=10),
                    resources=["res_a"],
                ),
                Task(
                    id="task_002",
                    name="Task 2",
                    estimate=TaskEstimate(low=8, expected=9, high=10),
                    resources=["res_a"],
                ),
            ],
            resources=[
                {
                    "name": "res_a",
                    "experience_level": 2,
                    "productivity_level": 1.0,
                }
            ],
        )

        engine = SimulationEngine(iterations=5, random_seed=42, show_progress=False)
        results = engine.run(project)

        assert results.resource_constraints_active is True
        assert results.schedule_mode == "resource_constrained"
        assert results.resource_wait_time_hours >= 0.0
        assert results.calendar_delay_time_hours >= 0.0
        assert 0.0 <= results.resource_utilization <= 1.0

    def test_run_simulation_computes_updated_default_percentiles(self, simple_project):
        """Test simulation computes P25 and P99 for projects using default levels."""
        engine = SimulationEngine(iterations=10, random_seed=42, show_progress=False)
        results = engine.run(simple_project)

        assert 25 in results.percentiles
        assert 99 in results.percentiles
        assert results.percentiles[25] == pytest.approx(
            float(np.percentile(results.durations, 25))
        )
        assert results.percentiles[99] == pytest.approx(
            float(np.percentile(results.durations, 99))
        )

    def test_simulation_reproducibility(self, simple_project):
        """Test simulation reproducibility with same seed."""
        engine1 = SimulationEngine(iterations=10, random_seed=42, show_progress=False)
        results1 = engine1.run(simple_project)

        engine2 = SimulationEngine(iterations=10, random_seed=42, show_progress=False)
        results2 = engine2.run(simple_project)

        assert np.allclose(results1.durations, results2.durations)

    def test_simulation_reproducibility_with_constrained_sickness(self):
        """Constrained scheduling should also be reproducible with the same seed."""
        project = Project(
            project=ProjectMetadata(
                name="Seeded Constrained", start_date=date(2025, 1, 6)
            ),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=8, expected=10, high=12),
                    resources=["res_a"],
                ),
                Task(
                    id="task_002",
                    name="Task 2",
                    estimate=TaskEstimate(low=8, expected=10, high=12),
                    resources=["res_a"],
                    dependencies=["task_001"],
                ),
            ],
            resources=[
                {
                    "name": "res_a",
                    "experience_level": 2,
                    "productivity_level": 1.0,
                    "sickness_prob": 0.2,
                }
            ],
        )

        engine1 = SimulationEngine(iterations=25, random_seed=42, show_progress=False)
        results1 = engine1.run(project)

        engine2 = SimulationEngine(iterations=25, random_seed=42, show_progress=False)
        results2 = engine2.run(project)

        assert np.allclose(results1.durations, results2.durations)

    def test_run_simulation_stores_full_critical_paths(self, monkeypatch):
        """Test that simulation stores aggregated critical path sequences."""
        project = Project(
            project=ProjectMetadata(name="Branching", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="Start",
                    estimate=TaskEstimate(low=1, expected=2, high=3),
                ),
                Task(
                    id="task_002",
                    name="Branch A",
                    estimate=TaskEstimate(low=1, expected=2, high=3),
                    dependencies=["task_001"],
                ),
                Task(
                    id="task_003",
                    name="Branch B",
                    estimate=TaskEstimate(low=1, expected=2, high=3),
                    dependencies=["task_001"],
                ),
            ],
        )

        config = Config(simulation={"max_stored_critical_paths": 1})
        engine = SimulationEngine(
            iterations=5,
            random_seed=42,
            config=config,
            show_progress=False,
        )
        monkeypatch.setattr(engine.sampler, "sample", lambda estimate: 1.0)

        results = engine.run(project)

        assert len(results.critical_path_sequences) == 1
        assert results.critical_path_sequences[0].path == (
            "task_001",
            "task_002",
        )
        assert results.critical_path_sequences[0].count == 5

    def test_apply_uncertainty_factors(self):
        """Test applying uncertainty factors."""
        # Use empty config for no uncertainty factors
        config = Config()
        engine = SimulationEngine(config=config, show_progress=False)

        task = Task(
            id="task_001",
            name="Task 1",
            estimate=TaskEstimate(low=1, expected=2, high=5),
        )

        # No uncertainty factors should not change duration
        adjusted = engine._apply_uncertainty_factors(task, 10.0)
        assert adjusted == 10.0

        # Test with uncertainty factors
        config_with_factors = Config(
            uncertainty_factors={
                "team_experience": {"high": 0.90, "medium": 1.0, "low": 1.30}
            }
        )
        engine2 = SimulationEngine(config=config_with_factors, show_progress=False)
        task_with_factors = Task(
            id="task_002",
            name="Task 2",
            estimate=TaskEstimate(low=1, expected=2, high=5),
            uncertainty_factors=UncertaintyFactors(team_experience="low"),
        )

        # Should multiply by 1.30
        adjusted2 = engine2._apply_uncertainty_factors(task_with_factors, 10.0)
        assert adjusted2 == 13.0

    def test_simulation_with_risks(self):
        """Test simulation with risks."""
        project = Project(
            project=ProjectMetadata(name="Test", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=2, high=5),
                    risks=[
                        Risk(
                            id="risk_001",
                            name="Risk",
                            probability=1.0,  # Always triggers
                            impact=5.0,
                        )
                    ],
                )
            ],
        )

        engine = SimulationEngine(iterations=10, random_seed=42, show_progress=False)
        results = engine.run(project)

        # Mean should be higher due to risk
        assert results.mean > 2.0
