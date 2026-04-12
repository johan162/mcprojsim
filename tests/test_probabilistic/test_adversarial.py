"""Category 11: Adversarial and edge case tests.

Push the engine to its limits with extreme parameters to verify
robustness and correctness under degenerate conditions.
"""

from __future__ import annotations

import numpy as np
import pytest

from mcprojsim.models.project import (
    Project,
    Risk,
    Task,
    TaskEstimate,
)

from .conftest import (
    STAT_ITERATIONS_CI,
    STAT_ITERATIONS_FULL,
    _meta,
    make_chain_project,
    make_fan_out_project,
    make_single_task_project,
    run_simulation,
)

pytestmark = pytest.mark.probabilistic


# ------------------------------------------------------------------
# 11.1  Single task project
# ------------------------------------------------------------------
class TestSingleTaskProject:
    """With one task and no risks, project duration = task duration
    in every iteration.
    """

    def test_single_task_duration_equals_task_duration(self):
        project = make_single_task_project(low=10.0, expected=30.0, high=80.0)
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        task_dur = results.task_durations["t1"]
        assert np.array_equal(results.durations, task_dur), (
            "SINGLE TASK: project duration should exactly equal task "
            "duration in every iteration."
        )

    def test_single_task_effort_equals_duration(self):
        project = make_single_task_project(low=10.0, expected=30.0, high=80.0)
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        assert np.array_equal(
            results.durations, results.effort_durations
        ), "SINGLE TASK: effort should equal duration (only 1 task)."


# ------------------------------------------------------------------
# 11.2  Maximum risk impact
# ------------------------------------------------------------------
class TestMaximumRiskImpact:
    """Every task has a 100% probability risk with a large impact.
    Results should still be finite and duration = base + impact.
    """

    def test_certain_risk_every_task(self):
        impact = 500.0
        tasks = []
        for i in range(5):
            deps = [f"t{i-1}"] if i > 0 else []
            tasks.append(
                Task(
                    id=f"t{i}",
                    name=f"Task {i}",
                    estimate=TaskEstimate(low=5.0, expected=10.0, high=20.0),
                    dependencies=deps,
                    risks=[
                        Risk(
                            id=f"r{i}",
                            name=f"Certain Risk {i}",
                            probability=1.0,
                            impact=impact,
                        )
                    ],
                )
            )

        project = Project(project=_meta(name="MaxRisk"), tasks=tasks)
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        assert not np.any(np.isnan(results.durations))
        assert not np.any(np.isinf(results.durations))

        # Each task has a certain risk adding 500h, so total risk = 2500h
        # Base durations are ~10h each (expected), so total is ~2550h
        # Mean should be at least 5 × 500 = 2500h
        assert results.mean >= 2500.0, (
            f"MAX RISK: mean={results.mean:.2f}, expected ≥ 2500.0 "
            f"(5 tasks × 500h certain risk each)."
        )


# ------------------------------------------------------------------
# 11.3  Deeply nested chain
# ------------------------------------------------------------------
class TestDeeplyNestedChain:
    """A chain of 50 tasks should complete without stack overflow
    in critical-path tracing.
    """

    @pytest.mark.probabilistic_full
    def test_50_task_chain(self):
        project = make_chain_project(n_tasks=50)
        results = run_simulation(project, iterations=STAT_ITERATIONS_FULL, seed=42)

        assert results.mean > 0
        assert not np.any(np.isnan(results.durations))
        assert len(results.task_durations) == 50

        # All tasks should be on critical path
        for task in project.tasks:
            freq = results.critical_path_frequency.get(task.id, 0)
            assert freq == results.iterations, (
                f"DEEP CHAIN: task {task.id} not always on critical path "
                f"(freq={freq}/{results.iterations})."
            )


# ------------------------------------------------------------------
# 11.4  Wide fan-out / fan-in
# ------------------------------------------------------------------
class TestWideFanOutFanIn:
    """Root → 20 parallel → sink.  Peak parallelism = 20 and
    project duration should be valid.
    """

    def test_20_branch_fan_out(self):
        project = make_fan_out_project(n_parallel=20)
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        assert results.max_parallel_tasks == 20, (
            f"FAN-OUT: expected peak parallelism 20, "
            f"got {results.max_parallel_tasks}."
        )
        assert results.mean > 0
        assert not np.any(np.isnan(results.durations))

    @pytest.mark.probabilistic_full
    def test_40_branch_fan_out(self):
        """Stress test with 40 parallel branches."""
        project = make_fan_out_project(n_parallel=40)
        results = run_simulation(project, iterations=STAT_ITERATIONS_FULL, seed=42)

        assert results.max_parallel_tasks == 40
        assert results.mean > 0
        assert len(results.task_durations) == 42  # root + 40 + sink


# ------------------------------------------------------------------
# 11.5  All tasks on critical path (chain)
# ------------------------------------------------------------------
class TestAllTasksOnCriticalPath:
    """For a pure chain, every task should have criticality = 1.0."""

    def test_chain_criticality_index_1(self):
        project = make_chain_project(n_tasks=8)
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        for task in project.tasks:
            freq = results.critical_path_frequency.get(task.id, 0)
            ratio = freq / results.iterations
            assert ratio > 0.99, (
                f"CHAIN CRITICALITY: task {task.id} "
                f"criticality={ratio:.4f}, expected ~1.0."
            )


# ------------------------------------------------------------------
# 11.6  Minimal estimate spread
# ------------------------------------------------------------------
class TestMinimalEstimateSpread:
    """Tasks with very tight estimates (low ≈ expected ≈ high) should
    produce near-deterministic results with very low variance.
    """

    def test_tight_estimates_low_variance(self):
        tasks = [
            Task(
                id=f"t{i}",
                name=f"Task {i}",
                estimate=TaskEstimate(low=9.99, expected=10.0, high=10.01),
                dependencies=[f"t{i-1}"] if i > 0 else [],
            )
            for i in range(5)
        ]

        project = Project(project=_meta(name="TightEstimates"), tasks=tasks)
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        # 5 tasks × 10h ≈ 50h total
        assert (
            abs(results.mean - 50.0) < 1.0
        ), f"TIGHT ESTIMATES: mean={results.mean:.4f}, expected ~50.0."
        assert results.std_dev < 1.0, (
            f"TIGHT ESTIMATES: std_dev={results.std_dev:.4f}, expected < 1.0 "
            f"for near-deterministic tasks."
        )


# ------------------------------------------------------------------
# 11.7  Risk with very large impact
# ------------------------------------------------------------------
class TestVeryLargeRiskImpact:
    """A risk with enormous impact should still produce finite results
    without overflow.
    """

    def test_large_impact_no_overflow(self):
        project = make_single_task_project(
            low=10.0,
            expected=30.0,
            high=80.0,
            risks=[
                Risk(
                    id="r1",
                    name="Catastrophe",
                    probability=1.0,
                    impact=1_000_000.0,
                ),
            ],
        )
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        assert not np.any(np.isnan(results.durations))
        assert not np.any(np.isinf(results.durations))
        assert (
            results.mean > 1_000_000.0
        ), f"LARGE IMPACT: mean={results.mean:.2f}, expected > 1M."


# ------------------------------------------------------------------
# 11.8  Many risks on one task
# ------------------------------------------------------------------
class TestManyRisksOneTask:
    """A task with 20 independent risks should accumulate them
    correctly without errors.
    """

    def test_20_risks_accumulate(self):
        risks = [
            Risk(
                id=f"r{i}",
                name=f"Risk {i}",
                probability=0.5,
                impact=10.0,
            )
            for i in range(20)
        ]
        project = make_single_task_project(
            low=10.0, expected=30.0, high=80.0, risks=risks
        )
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        # Expected total risk impact ≈ 20 × 0.5 × 10 = 100h
        impacts = results.risk_impacts["t1"]
        mean_impact = float(np.mean(impacts))

        assert 70.0 < mean_impact < 130.0, (
            f"MANY RISKS: mean impact={mean_impact:.2f}, expected ~100.0 "
            f"(20 risks × 0.5 × 10h). "
            f"SUGGESTION: Check that the engine evaluates all risks "
            f"independently."
        )
