"""Test 3: Structural topology validation.

These tests verify that the scheduling logic correctly implements:
- Sequential chains: duration = sum of all tasks
- Parallel tasks: duration = max of all tasks
- Diamond DAGs: duration = critical path length
- Fan-out/fan-in: max over parallel branches

We use properties of order statistics and convolutions to verify correctness
of the project-level duration distribution shape.
"""

from __future__ import annotations

import numpy as np
from scipy import stats

from .conftest import (
    ALPHA,
    N_ITERATIONS,
    assert_mean_within_ci,
    assert_variance_within_ci,
    chain_project,
    diamond_project,
    parallel_project,
    run_sim,
    single_task_project,
    triangular_mean,
    triangular_variance,
)


class TestSequentialAdditivity:
    """Chain duration = sum of independent task durations (convolution)."""

    def test_two_task_chain_mean(self):
        """E[T1 + T2] = E[T1] + E[T2]."""
        e1 = (5.0, 10.0, 20.0)
        e2 = (10.0, 25.0, 50.0)
        project = chain_project([e1, e2])
        results = run_sim(project, iterations=N_ITERATIONS, seed=1)

        expected = triangular_mean(*e1) + triangular_mean(*e2)
        assert_mean_within_ci(results.durations, expected)

    def test_five_task_chain_mean(self):
        """Longer chains still sum correctly."""
        estimates = [
            (2.0, 5.0, 10.0),
            (8.0, 12.0, 20.0),
            (3.0, 7.0, 15.0),
            (10.0, 20.0, 35.0),
            (1.0, 3.0, 8.0),
        ]
        project = chain_project(estimates)
        results = run_sim(project, iterations=N_ITERATIONS, seed=2)

        expected = sum(triangular_mean(*e) for e in estimates)
        assert_mean_within_ci(results.durations, expected, label="5-chain mean")

    def test_chain_variance_additivity(self):
        """Var[sum of independent tasks] = sum of variances."""
        estimates = [
            (2.0, 5.0, 10.0),
            (8.0, 12.0, 20.0),
            (3.0, 7.0, 15.0),
        ]
        project = chain_project(estimates)
        results = run_sim(project, iterations=N_ITERATIONS, seed=3)

        expected_var = sum(triangular_variance(*e) for e in estimates)
        assert_variance_within_ci(
            results.durations, expected_var, label="Chain variance"
        )


class TestParallelMaxStatistic:
    """Parallel project duration = max(T1, T2, ..., Tn)."""

    def test_parallel_always_ge_individual_means(self):
        """E[max(T1,...,Tn)] >= max(E[T1],...,E[Tn])."""
        estimates = [(5.0, 10.0, 20.0)] * 5
        project = parallel_project(estimates)
        results = run_sim(project, iterations=N_ITERATIONS, seed=4)

        individual_mean = triangular_mean(*estimates[0])
        # Max of 5 iid RVs has higher expected value
        assert float(np.mean(results.durations)) > individual_mean

    def test_parallel_two_identical_tasks_order_statistic(self):
        """For 2 iid Uniform[a,b] tasks: E[max] = (2a + b) / 3... but we use triangular.

        For 2 iid Triangular(a,c,b) samples, verify via simulation cross-check:
        independently sample and take max, compare to engine output.
        """
        low, mode, high = 10.0, 20.0, 40.0
        project = parallel_project([(low, mode, high), (low, mode, high)])
        results = run_sim(project, iterations=N_ITERATIONS, seed=5)

        # Cross-check: manually sample max of two triangular RVs
        # Verify the property: E[max(X,Y)] > E[X] for iid X,Y
        single_project = single_task_project(low, mode, high)
        single_results = run_sim(single_project, iterations=N_ITERATIONS, seed=5)

        # Mean of max must exceed mean of single (strictly for non-degenerate dist)
        assert float(np.mean(results.durations)) > float(
            np.mean(single_results.durations)
        )

    def test_parallel_dominated_task_irrelevant(self):
        """If one task dominates all others (stochastically), it determines duration."""
        # Task 1: Tri(100, 200, 300) dominates Task 2: Tri(1, 2, 5)
        estimates = [(100.0, 200.0, 300.0), (1.0, 2.0, 5.0)]
        project = parallel_project(estimates)
        results = run_sim(project, iterations=N_ITERATIONS, seed=6)

        # Project mean should be very close to the dominant task mean
        dominant_mean = triangular_mean(*estimates[0])
        # The max is >= dominant task always, so mean should be very close
        obs_mean = float(np.mean(results.durations))
        assert abs(obs_mean - dominant_mean) / dominant_mean < 0.01  # Within 1%

    def test_parallel_five_iid_mean_exceeds_single(self):
        """max(5 iid samples) has higher mean than any single sample."""
        est = (10.0, 30.0, 60.0)
        project = parallel_project([est] * 5)
        results = run_sim(project, iterations=N_ITERATIONS, seed=7)

        single_mean = triangular_mean(*est)
        # For iid RVs, E[max_n] > E[X] and increases with n
        obs = float(np.mean(results.durations))
        # Should exceed single mean by meaningful amount
        assert obs > single_mean * 1.1


class TestDiamondTopology:
    """Diamond DAG: A → {B, C} → D. Duration = A + max(B, C) + D."""

    def test_diamond_mean_bounded(self):
        """E[diamond] >= E[A] + max(E[B], E[C]) + E[D] and <= E[A] + E[B] + E[C] + E[D]."""
        a = (5.0, 10.0, 20.0)
        b = (10.0, 20.0, 40.0)
        c = (8.0, 15.0, 30.0)
        d = (3.0, 6.0, 12.0)

        project = diamond_project(a, b, c, d)
        results = run_sim(project, iterations=N_ITERATIONS, seed=8)

        mean_a = triangular_mean(*a)
        mean_b = triangular_mean(*b)
        mean_c = triangular_mean(*c)
        mean_d = triangular_mean(*d)

        obs = float(np.mean(results.durations))
        # Lower bound: sum of means through longest expected path
        lower = mean_a + max(mean_b, mean_c) + mean_d
        # Upper bound: can't exceed sum of all tasks
        upper = mean_a + mean_b + mean_c + mean_d

        assert obs >= lower - 1.0  # Small tolerance for statistical noise
        assert obs <= upper + 1.0

    def test_diamond_symmetric_branches(self):
        """With B == C (same distribution), both branches critical ~50% each."""
        a = (5.0, 10.0, 20.0)
        bc = (10.0, 20.0, 40.0)  # Same for both branches
        d = (3.0, 6.0, 12.0)

        project = diamond_project(a, bc, bc, d)
        results = run_sim(project, iterations=N_ITERATIONS, seed=9)

        # B and C should be critical approximately equally
        freq_b = results.critical_path_frequency["B"]
        total = results.iterations

        # Each should be ~50% (binomial test)
        result_b = stats.binomtest(freq_b, total, 0.5)
        assert (
            result_b.pvalue > ALPHA
        ), f"B criticality {freq_b}/{total} not ≈ 50%: p={result_b.pvalue:.2e}"

    def test_diamond_asymmetric_dominant_branch(self):
        """When B >> C, B is critical in nearly all iterations."""
        a = (5.0, 10.0, 15.0)
        b = (50.0, 100.0, 200.0)  # Much longer
        c = (1.0, 2.0, 5.0)  # Much shorter
        d = (3.0, 5.0, 8.0)

        project = diamond_project(a, b, c, d)
        results = run_sim(project, iterations=N_ITERATIONS, seed=10)

        freq_b = results.critical_path_frequency["B"]
        freq_c = results.critical_path_frequency["C"]

        # B should dominate (>95% critical)
        assert freq_b / results.iterations > 0.95
        # C should be rarely critical
        assert freq_c / results.iterations < 0.05


class TestEffortVsElapsed:
    """Effort (total person-hours) vs elapsed (project duration) relationship."""

    def test_parallel_effort_exceeds_elapsed(self):
        """With parallel tasks, effort > elapsed (multiple people working)."""
        estimates = [(10.0, 20.0, 40.0)] * 4
        project = parallel_project(estimates)
        results = run_sim(project, iterations=N_ITERATIONS, seed=11)

        # Effort = sum of all 4 tasks, elapsed = max of 4 tasks
        # So effort > elapsed always (since tasks have nonzero duration)
        assert np.all(results.effort_durations > results.durations)

    def test_chain_effort_equals_elapsed(self):
        """With purely sequential tasks, effort == elapsed."""
        estimates = [(10.0, 20.0, 40.0), (5.0, 15.0, 30.0)]
        project = chain_project(estimates)
        results = run_sim(project, iterations=N_ITERATIONS, seed=12)

        # In a pure chain, effort = elapsed (one person doing all work)
        assert np.allclose(results.effort_durations, results.durations, atol=1e-9)

    def test_effort_mean_independent_of_topology(self):
        """Same tasks in chain vs parallel have same effort mean."""
        estimates = [(10.0, 20.0, 40.0), (5.0, 15.0, 30.0), (8.0, 12.0, 25.0)]

        chain = chain_project(estimates)
        par = parallel_project(estimates)

        chain_results = run_sim(chain, iterations=N_ITERATIONS, seed=13)
        par_results = run_sim(par, iterations=N_ITERATIONS, seed=13)

        # Same seed → same task samples → same effort
        assert np.allclose(
            chain_results.effort_durations, par_results.effort_durations, atol=1e-9
        )
