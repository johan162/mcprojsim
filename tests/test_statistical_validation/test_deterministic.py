"""Test 1: Near-deterministic and low-variance validation cases.

When variance is extremely small (near-zero spread), the simulation should
produce results extremely close to the known analytical values. This validates
the engine correctly handles the base cases and topological computations.

Note: numpy's triangular distribution requires left < right, so we use
a tiny spread (±0.001) to simulate near-deterministic behavior.
"""

from __future__ import annotations

import numpy as np

from mcprojsim.config import EffortUnit
from mcprojsim.models.project import (
    DistributionType,
    Project,
    ProjectMetadata,
    Task,
    TaskEstimate,
)

from .conftest import START_DATE, run_sim

# Use tiny spread to simulate near-deterministic behavior
# numpy.random.triangular requires left < right
EPS = 0.001


def _det_estimate(value: float) -> TaskEstimate:
    """Create a near-deterministic estimate (tiny spread around value)."""
    return TaskEstimate(
        low=value - EPS, expected=value, high=value + EPS, unit=EffortUnit.HOURS
    )


class TestNearDeterministicSingleTask:
    """Single task with near-zero variance → result ≈ exact known duration."""

    def test_triangular_near_point_mass(self):
        """Triangular with tiny spread produces values very close to expected."""
        project = Project(
            project=ProjectMetadata(
                name="Near-Deterministic",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
            ),
            tasks=[Task(id="t1", name="Task 1", estimate=_det_estimate(24.0))],
        )
        results = run_sim(project, iterations=1000, seed=99)

        # Every iteration should be within EPS of 24.0
        assert np.all(np.abs(results.durations - 24.0) <= EPS)
        assert abs(results.mean - 24.0) < EPS
        assert results.std_dev < EPS
        assert abs(results.min_duration - 24.0) <= EPS
        assert abs(results.max_duration - 24.0) <= EPS

    def test_near_deterministic_chain(self):
        """Sequential chain with near-deterministic tasks sums correctly."""
        durations = [10.0, 20.0, 30.0, 40.0]
        tasks = []
        for i, d in enumerate(durations):
            tid = f"t{i + 1}"
            deps = [f"t{i}"] if i > 0 else []
            tasks.append(
                Task(
                    id=tid,
                    name=f"Task {i + 1}",
                    estimate=_det_estimate(d),
                    dependencies=deps,
                )
            )
        project = Project(
            project=ProjectMetadata(
                name="Det Chain",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
            ),
            tasks=tasks,
        )
        results = run_sim(project, iterations=500)
        expected_total = sum(durations)  # 100 hours

        assert np.all(
            np.abs(results.durations - expected_total) <= len(durations) * EPS
        )
        assert abs(results.mean - expected_total) < len(durations) * EPS

    def test_near_deterministic_parallel_max(self):
        """Parallel tasks with near-zero variance → duration ≈ max of all."""
        task_hours = [10.0, 25.0, 15.0, 20.0]
        tasks = [
            Task(
                id=f"t{i + 1}",
                name=f"Task {i + 1}",
                estimate=_det_estimate(d),
            )
            for i, d in enumerate(task_hours)
        ]
        project = Project(
            project=ProjectMetadata(
                name="Det Parallel",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
            ),
            tasks=tasks,
        )
        results = run_sim(project, iterations=500)
        expected_duration = max(task_hours)  # 25 hours

        assert np.all(np.abs(results.durations - expected_duration) <= EPS)

    def test_near_deterministic_diamond(self):
        """Diamond DAG: duration ≈ max(A+B, A+C) + D."""
        # A=10, B=30, C=20, D=5 → max(10+30, 10+20) + 5 = 45
        tasks = [
            Task(id="A", name="A", estimate=_det_estimate(10.0)),
            Task(id="B", name="B", estimate=_det_estimate(30.0), dependencies=["A"]),
            Task(id="C", name="C", estimate=_det_estimate(20.0), dependencies=["A"]),
            Task(
                id="D", name="D", estimate=_det_estimate(5.0), dependencies=["B", "C"]
            ),
        ]
        project = Project(
            project=ProjectMetadata(
                name="Det Diamond",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
            ),
            tasks=tasks,
        )
        results = run_sim(project, iterations=500)
        # Critical path: A → B → D = 10 + 30 + 5 = 45
        assert np.all(np.abs(results.durations - 45.0) <= 4 * EPS)


class TestNearDeterministicCriticalPath:
    """With near-zero variance and clear dominance, critical path is known."""

    def test_chain_all_tasks_critical(self):
        """In a serial chain, every task is on the critical path 100%."""
        tasks = [
            Task(
                id=f"t{i + 1}",
                name=f"T{i + 1}",
                estimate=_det_estimate(10.0),
                dependencies=[f"t{i}"] if i > 0 else [],
            )
            for i in range(5)
        ]
        project = Project(
            project=ProjectMetadata(
                name="Chain CP",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
            ),
            tasks=tasks,
        )
        results = run_sim(project, iterations=200)

        # Every task should be on critical path in every iteration
        for tid in ["t1", "t2", "t3", "t4", "t5"]:
            assert results.critical_path_frequency[tid] == 200

    def test_diamond_clear_dominant_branch(self):
        """In diamond with B >> C, only A-B-D is the critical path."""
        # B's lowest possible value (50 - EPS) >> C's highest (10 + EPS)
        tasks = [
            Task(id="A", name="A", estimate=_det_estimate(10.0)),
            Task(
                id="B",
                name="B",
                estimate=_det_estimate(50.0),
                dependencies=["A"],
            ),
            Task(
                id="C",
                name="C",
                estimate=_det_estimate(10.0),
                dependencies=["A"],
            ),
            Task(
                id="D",
                name="D",
                estimate=_det_estimate(5.0),
                dependencies=["B", "C"],
            ),
        ]
        project = Project(
            project=ProjectMetadata(
                name="Diamond CP",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
            ),
            tasks=tasks,
        )
        results = run_sim(project, iterations=200)

        # A and D are always critical (both paths go through them)
        assert results.critical_path_frequency["A"] == 200
        assert results.critical_path_frequency["D"] == 200
        # B is the longer branch → always critical
        assert results.critical_path_frequency["B"] == 200
        # C is never critical (shorter branch)
        assert results.critical_path_frequency["C"] == 0


class TestNearDeterministicEffort:
    """Effort (total person-hours) is always sum of all tasks, regardless of scheduling."""

    def test_effort_equals_sum_of_tasks(self):
        """For near-deterministic tasks, effort ≈ sum of all task durations."""
        durations = [10.0, 20.0, 30.0]
        tasks = [
            Task(
                id=f"t{i + 1}",
                name=f"T{i + 1}",
                estimate=_det_estimate(d),
            )
            for i, d in enumerate(durations)
        ]
        project = Project(
            project=ProjectMetadata(
                name="Effort",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
            ),
            tasks=tasks,
        )
        results = run_sim(project, iterations=500)
        expected_effort = sum(durations)  # 60 hours total work

        # Effort should be approximately the sum (parallel tasks still take individual effort)
        assert np.all(
            np.abs(results.effort_durations - expected_effort) <= len(durations) * EPS
        )
        # Elapsed duration ≈ max(parallel tasks) = 30
        assert np.all(np.abs(results.durations - max(durations)) <= EPS)
