"""Category 10: Cross-validation tests.

Compare results across scheduling modes and configurations to catch
inconsistencies between code paths.
"""

from __future__ import annotations

import numpy as np
import pytest

from mcprojsim.analysis.sensitivity import SensitivityAnalyzer

from .conftest import (
    STAT_ITERATIONS_CI,
    STAT_ITERATIONS_FULL,
    make_chain_project,
    make_constrained_parallel_project,
    make_parallel_project,
    run_simulation,
)

pytestmark = pytest.mark.probabilistic


# ------------------------------------------------------------------
# 10.1  Two-pass vs single-pass without resources
# ------------------------------------------------------------------
class TestTwoPassVsSinglePass:
    """Without resources, two-pass scheduling should produce identical
    results to single-pass because there are no resources to
    re-prioritize.
    """

    @pytest.mark.probabilistic_full
    def test_no_resources_identical(self):
        project = make_chain_project(n_tasks=5)

        r_single = run_simulation(
            project, iterations=STAT_ITERATIONS_FULL, seed=42, two_pass=False
        )
        r_two = run_simulation(
            project, iterations=STAT_ITERATIONS_FULL, seed=42, two_pass=True
        )

        assert np.array_equal(r_single.durations, r_two.durations), (
            "TWO-PASS CROSS-VALIDATION: without resources, two-pass "
            "should produce identical durations to single-pass. "
            "SUGGESTION: Check that the two-pass codepath falls back "
            "to the same scheduling logic when no resources are active."
        )

    @pytest.mark.probabilistic_full
    def test_parallel_no_resources_identical(self):
        project = make_parallel_project(n_parallel=6)

        r_single = run_simulation(
            project, iterations=STAT_ITERATIONS_FULL, seed=42, two_pass=False
        )
        r_two = run_simulation(
            project, iterations=STAT_ITERATIONS_FULL, seed=42, two_pass=True
        )

        assert np.array_equal(r_single.durations, r_two.durations), (
            "TWO-PASS CROSS-VALIDATION: parallel project without "
            "resources should give identical results."
        )


# ------------------------------------------------------------------
# 10.2  Effort consistency across scheduling modes
# ------------------------------------------------------------------
class TestEffortConsistencyAcrossModes:
    """Total effort should be statistically similar regardless of
    scheduling mode, because scheduling affects *when* tasks run
    but not *how long* they take.
    """

    @pytest.mark.probabilistic_full
    def test_effort_independent_of_scheduling(self):
        """Effort mean should be similar between dependency-only
        and resource-constrained modes.
        """
        proj_dep = make_parallel_project(n_parallel=4)
        proj_con = make_constrained_parallel_project(n_parallel=4, n_resources=2)

        res_dep = run_simulation(proj_dep, iterations=STAT_ITERATIONS_FULL, seed=42)
        res_con = run_simulation(proj_con, iterations=STAT_ITERATIONS_FULL, seed=42)
        effort_dep = float(np.mean(res_dep.effort_durations))
        effort_con = float(np.mean(res_con.effort_durations))
        rel_diff = abs(effort_dep - effort_con) / effort_dep

        assert rel_diff < 0.10, (
            f"EFFORT CROSS-VALIDATION: dependency-only effort mean "
            f"({effort_dep:.2f}) vs constrained ({effort_con:.2f}), "
            f"rel_diff={rel_diff:.4f}. Should be < 10%. "
            f"SUGGESTION: Task durations should be independent of "
            f"scheduling mode; only elapsed time changes."
        )


# ------------------------------------------------------------------
# 10.3  Constrained duration ≥ unconstrained duration
# ------------------------------------------------------------------
class TestConstrainedVsUnconstrained:
    """Resource constraints can only increase (or equal) project
    duration relative to dependency-only scheduling.
    """

    @pytest.mark.probabilistic_full
    def test_constrained_mean_ge_unconstrained(self):
        proj_dep = make_parallel_project(n_parallel=6)
        proj_con = make_constrained_parallel_project(n_parallel=6, n_resources=2)

        res_dep = run_simulation(proj_dep, iterations=STAT_ITERATIONS_FULL, seed=42)
        res_con = run_simulation(proj_con, iterations=STAT_ITERATIONS_FULL, seed=42)

        assert res_con.mean >= res_dep.mean - 2.0, (
            f"CROSS-VALIDATION: constrained mean ({res_con.mean:.2f}) "
            f"should not be significantly less than unconstrained "
            f"({res_dep.mean:.2f}). Resource contention can only add "
            f"delay."
        )


# ------------------------------------------------------------------
# 10.4  Sensitivity ranking stability across seeds
# ------------------------------------------------------------------
class TestSensitivityRankingStability:
    """For a project with clearly differentiated task variances, the
    top-3 most sensitive tasks should overlap across different seeds.
    """

    @pytest.mark.probabilistic_full
    def test_top3_overlap(self):
        from mcprojsim.models.project import Project, Task, TaskEstimate

        from .conftest import _meta

        # 6 parallel tasks with vastly different variance
        tasks = [
            Task(
                id="huge",
                name="Huge variance",
                estimate=TaskEstimate(low=10.0, expected=50.0, high=300.0),
            ),
            Task(
                id="large",
                name="Large variance",
                estimate=TaskEstimate(low=10.0, expected=40.0, high=150.0),
            ),
            Task(
                id="medium",
                name="Medium variance",
                estimate=TaskEstimate(low=10.0, expected=25.0, high=60.0),
            ),
            Task(
                id="small1",
                name="Small 1",
                estimate=TaskEstimate(low=9.0, expected=10.0, high=12.0),
            ),
            Task(
                id="small2",
                name="Small 2",
                estimate=TaskEstimate(low=9.0, expected=10.0, high=12.0),
            ),
            Task(
                id="small3",
                name="Small 3",
                estimate=TaskEstimate(low=9.0, expected=10.0, high=12.0),
            ),
        ]
        project = Project(project=_meta(name="DiffVariance"), tasks=tasks)

        top_sets = []
        for seed in [10, 20, 30]:
            results = run_simulation(
                project, iterations=STAT_ITERATIONS_FULL, seed=seed
            )
            top = SensitivityAnalyzer.get_top_contributors(results, n=3)
            top_sets.append({tid for tid, _ in top})

        for i in range(len(top_sets)):
            for j in range(i + 1, len(top_sets)):
                overlap = len(top_sets[i] & top_sets[j])
                assert overlap >= 2, (
                    f"SENSITIVITY STABILITY: seeds {i} and {j} share "
                    f"only {overlap}/3 top tasks. "
                    f"Sets: {top_sets[i]}, {top_sets[j]}."
                )


# ------------------------------------------------------------------
# 10.5  Critical path frequency sums
# ------------------------------------------------------------------
class TestCriticalPathFrequencySum:
    """In a chain, every task is always on the critical path, so the
    sum of frequencies should equal n_tasks × iterations.
    """

    def test_chain_cp_freq_sum(self):
        n_tasks = 5
        project = make_chain_project(n_tasks=n_tasks)
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        total_freq = sum(results.critical_path_frequency.values())
        expected = n_tasks * results.iterations

        assert total_freq == expected, (
            f"CP FREQ SUM: chain total={total_freq}, "
            f"expected {n_tasks}×{results.iterations}={expected}."
        )
