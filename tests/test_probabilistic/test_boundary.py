"""Category 1: Boundary invariant tests.

These tests verify hard constraints that must hold for every single
iteration, regardless of randomness.  A single violation is a
definitive bug.
"""

from __future__ import annotations

import numpy as np
import pytest

from mcprojsim.models.project import (
    DistributionType,
    Risk,
)

from .conftest import (
    STAT_ITERATIONS_CI,
    assert_within_bounds,
    make_chain_project,
    make_diamond_project,
    make_fan_out_project,
    make_parallel_project,
    make_single_task_project,
    run_simulation,
)

pytestmark = pytest.mark.probabilistic


# ------------------------------------------------------------------
# 1.1  Task duration never below shifted lower bound
# ------------------------------------------------------------------
class TestDurationLowerBound:
    """No task duration should fall below its shifted lognormal lower bound."""

    def test_single_task_above_low(self):
        """Task duration ≥ low estimate (lognormal shift parameter)."""
        low = 10.0
        project = make_single_task_project(low=low, expected=30.0, high=80.0)
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        samples = results.task_durations["t1"]
        assert_within_bounds(
            samples,
            lower=low - 1e-9,
            upper=float("inf"),
            label="Single task ≥ low estimate",
        )

    def test_triangular_within_bounds(self):
        """Triangular samples must stay within [low, high]."""
        low, high = 5.0, 100.0
        project = make_single_task_project(
            low=low,
            expected=20.0,
            high=high,
            distribution=DistributionType.TRIANGULAR,
        )
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)
        samples = results.task_durations["t1"]
        assert_within_bounds(
            samples,
            lower=low,
            upper=high,
            label="Triangular bounds [low, high]",
        )


# ------------------------------------------------------------------
# 1.2  Project duration ≥ critical chain lower bound
# ------------------------------------------------------------------
class TestProjectDurationLowerBound:
    """Project duration ≥ sum of minimums along the longest chain."""

    def test_chain_project_above_chain_minimum(self):
        lows = [10.0, 20.0, 30.0]
        estimates = [
            (lows[0], 20.0, 50.0),
            (lows[1], 40.0, 80.0),
            (lows[2], 50.0, 90.0),
        ]
        project = make_chain_project(estimates=estimates)
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        chain_minimum = sum(lows)
        assert float(np.min(results.durations)) >= chain_minimum - 1e-9, (
            f"BOUNDARY VIOLATION: min project duration "
            f"{float(np.min(results.durations)):.4f} < chain minimum "
            f"{chain_minimum:.4f}.  SUGGESTION: Check scheduling forward pass "
            f"or distribution lower bound."
        )


# ------------------------------------------------------------------
# 1.3  Effort ≥ duration (always)
# ------------------------------------------------------------------
class TestEffortDurationRelationship:
    """Total effort ≥ elapsed project duration in every iteration."""

    def test_parallel_effort_ge_duration(self):
        """With parallel tasks, effort must exceed duration."""
        project = make_parallel_project(n_parallel=5)
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        violations = int(np.sum(results.effort_durations < results.durations - 1e-6))
        assert violations == 0, (
            f"EFFORT < DURATION in {violations}/{results.iterations} iterations. "
            f"Effort range: [{float(results.effort_durations.min()):.2f}, "
            f"{float(results.effort_durations.max()):.2f}]. "
            f"Duration range: [{float(results.durations.min()):.2f}, "
            f"{float(results.durations.max()):.2f}]. "
            f"SUGGESTION: Check effort_durations aggregation in "
            f"SimulationEngine._build_results — effort is the sum of ALL "
            f"task durations, duration is the max end time."
        )

    def test_chain_effort_equals_duration(self):
        """For a pure chain, effort == duration (no parallelism)."""
        project = make_chain_project(n_tasks=4)
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        # Chain: no project-level risks, so effort should equal duration
        assert np.allclose(results.effort_durations, results.durations, atol=1e-6), (
            f"CHAIN EFFORT ≠ DURATION: "
            f"max |effort - duration| = "
            f"{float(np.max(np.abs(results.effort_durations - results.durations))):.6f}. "
            f"SUGGESTION: For a chain with no project-level risks, effort "
            f"and duration should be identical.  Check whether project risks "
            f"are being applied to duration but not to effort."
        )


# ------------------------------------------------------------------
# 1.4  Risk impact non-negative
# ------------------------------------------------------------------
class TestRiskImpactBounds:
    """Risk impacts must be non-negative."""

    def test_task_risk_impacts_non_negative(self):
        project = make_single_task_project(
            low=10.0,
            expected=30.0,
            high=80.0,
            risks=[
                Risk(id="r1", name="Risk 1", probability=0.5, impact=20.0),
                Risk(id="r2", name="Risk 2", probability=0.3, impact=40.0),
            ],
        )
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        for task_id, impacts in results.risk_impacts.items():
            neg_count = int(np.sum(impacts < -1e-9))
            assert neg_count == 0, (
                f"NEGATIVE RISK IMPACT for task {task_id}: "
                f"{neg_count} negative values, min={float(impacts.min()):.6f}. "
                f"SUGGESTION: Check RiskEvaluator — impacts should always "
                f"be ≥ 0 (risks add duration, never subtract)."
            )

    def test_project_risk_impacts_non_negative(self):
        project = make_chain_project(n_tasks=2)
        project.project_risks = [
            Risk(id="pr1", name="Project Risk", probability=0.4, impact=50.0),
        ]
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        neg_count = int(np.sum(results.project_risk_impacts < -1e-9))
        assert neg_count == 0, (
            f"NEGATIVE PROJECT RISK IMPACT: {neg_count} negative values. "
            f"SUGGESTION: Check project-level risk evaluation in engine."
        )


# ------------------------------------------------------------------
# 1.5  Dependency ordering holds
# ------------------------------------------------------------------
class TestDependencyOrdering:
    """No task starts before its dependencies complete.

    We verify this indirectly: for a chain, the project duration must
    equal the sum of task durations (since each depends on the
    previous).  If scheduling violated ordering, the duration would be
    less than the sum.
    """

    def test_chain_duration_equals_task_sum(self):
        project = make_chain_project(n_tasks=5)
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        task_sum = np.zeros(results.iterations)
        for durations in results.task_durations.values():
            task_sum += durations

        assert np.allclose(results.durations, task_sum, atol=1e-6), (
            f"DEPENDENCY ORDERING VIOLATION: chain project duration ≠ sum "
            f"of task durations.  Max absolute difference: "
            f"{float(np.max(np.abs(results.durations - task_sum))):.6f}. "
            f"SUGGESTION: Check scheduler forward pass — tasks must not "
            f"start before their dependencies end."
        )


# ------------------------------------------------------------------
# 1.6  Percentile ordering (hard invariant)
# ------------------------------------------------------------------
class TestPercentileOrdering:
    """Percentiles must be monotonically non-decreasing."""

    def test_duration_percentile_ordering(self):
        project = make_diamond_project()
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        levels = [10, 25, 50, 75, 80, 85, 90, 95, 99]
        values = [results.percentile(p) for p in levels]
        for i in range(1, len(values)):
            assert values[i] >= values[i - 1] - 1e-9, (
                f"PERCENTILE ORDER VIOLATION: "
                f"P{levels[i]}={values[i]:.4f} < "
                f"P{levels[i - 1]}={values[i - 1]:.4f}. "
                f"SUGGESTION: Check SimulationResults.percentile — should "
                f"use np.percentile on the durations array."
            )

    def test_effort_percentile_ordering(self):
        project = make_parallel_project(n_parallel=5)
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        levels = [10, 25, 50, 75, 90, 95]
        values = [results.effort_percentile(p) for p in levels]
        for i in range(1, len(values)):
            assert values[i] >= values[i - 1] - 1e-9, (
                f"EFFORT PERCENTILE ORDER VIOLATION: "
                f"P{levels[i]}={values[i]:.4f} < "
                f"P{levels[i - 1]}={values[i - 1]:.4f}."
            )


# ------------------------------------------------------------------
# 1.7  Statistics sanity
# ------------------------------------------------------------------
class TestStatisticsSanity:
    """Basic statistical properties that must hold."""

    def test_mean_between_min_and_max(self):
        project = make_diamond_project()
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        assert results.min_duration <= results.mean <= results.max_duration, (
            f"MEAN OUT OF RANGE: mean={results.mean:.4f} not in "
            f"[{results.min_duration:.4f}, {results.max_duration:.4f}]."
        )

    def test_median_between_min_and_max(self):
        project = make_diamond_project()
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        assert results.min_duration <= results.median <= results.max_duration, (
            f"MEDIAN OUT OF RANGE: median={results.median:.4f} not in "
            f"[{results.min_duration:.4f}, {results.max_duration:.4f}]."
        )

    def test_std_dev_non_negative(self):
        project = make_diamond_project()
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        assert results.std_dev >= 0, f"NEGATIVE STD DEV: {results.std_dev}"

    def test_no_nan_or_inf(self):
        project = make_diamond_project()
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        assert not np.any(np.isnan(results.durations)), "NaN in durations"
        assert not np.any(np.isinf(results.durations)), "Inf in durations"
        assert not np.any(np.isnan(results.effort_durations)), "NaN in effort_durations"
        assert not np.any(np.isinf(results.effort_durations)), "Inf in effort_durations"

    def test_all_durations_positive(self):
        project = make_fan_out_project(n_parallel=10)
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        assert float(np.min(results.durations)) > 0, (
            f"NON-POSITIVE DURATION: min={float(np.min(results.durations)):.6f}. "
            f"SUGGESTION: Check whether tasks with low > 0 always produce "
            f"positive durations."
        )
