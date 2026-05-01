"""Test 7: Reproducibility and seed determinism.

Verify that:
- Same seed produces identical results
- Different seeds produce different results
- Results are independent of iteration ordering artifacts
"""

from __future__ import annotations

import numpy as np

from mcprojsim.models.project import DistributionType

from .conftest import (
    N_ITERATIONS,
    chain_project,
    parallel_project,
    run_sim,
    single_task_project,
)


class TestSeedDeterminism:
    """Same seed → identical results, bit-for-bit."""

    def test_same_seed_same_results(self):
        """Two runs with same seed produce identical duration arrays."""
        project = chain_project(
            [(5.0, 15.0, 30.0), (10.0, 25.0, 50.0), (8.0, 20.0, 40.0)]
        )
        results1 = run_sim(project, iterations=10_000, seed=42)
        results2 = run_sim(project, iterations=10_000, seed=42)

        assert np.array_equal(results1.durations, results2.durations)

    def test_same_seed_same_task_durations(self):
        """Per-task duration arrays are also identical."""
        project = chain_project([(5.0, 15.0, 30.0), (10.0, 25.0, 50.0)])
        results1 = run_sim(project, iterations=10_000, seed=99)
        results2 = run_sim(project, iterations=10_000, seed=99)

        for tid in ["t1", "t2"]:
            assert np.array_equal(
                results1.task_durations[tid], results2.task_durations[tid]
            )

    def test_different_seeds_different_results(self):
        """Different seeds produce statistically different results."""
        project = single_task_project(
            5.0, 20.0, 50.0, distribution=DistributionType.TRIANGULAR
        )
        results1 = run_sim(project, iterations=10_000, seed=1)
        results2 = run_sim(project, iterations=10_000, seed=2)

        # Arrays should not be identical (probability of this is negligible)
        assert not np.array_equal(results1.durations, results2.durations)

    def test_seed_independence_from_iteration_count(self):
        """First K iterations with seed S are identical whether N=K or N>K."""
        project = single_task_project(
            10.0, 30.0, 60.0, distribution=DistributionType.TRIANGULAR
        )
        results_short = run_sim(project, iterations=1000, seed=77)
        results_long = run_sim(project, iterations=5000, seed=77)

        # First 1000 iterations should be identical
        assert np.array_equal(results_short.durations, results_long.durations[:1000])


class TestStatisticalIndependence:
    """Verify that iterations are statistically independent (no serial correlation)."""

    def test_no_autocorrelation_in_durations(self):
        """Lag-1 autocorrelation of project durations should be ≈ 0."""
        project = single_task_project(
            5.0, 20.0, 50.0, distribution=DistributionType.TRIANGULAR
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=400)

        # Compute lag-1 autocorrelation
        durations = results.durations
        x = durations[:-1]
        y = durations[1:]
        correlation = float(np.corrcoef(x, y)[0, 1])

        # Should be very close to 0 (within statistical noise)
        # For N=50000, the standard error of r under H0 is ~1/√N ≈ 0.0045
        assert (
            abs(correlation) < 0.02
        ), f"Lag-1 autocorrelation = {correlation:.6f}, expected ≈ 0"

    def test_no_trend_in_iterations(self):
        """No systematic trend across iterations (first half ≈ second half)."""
        project = chain_project([(10.0, 25.0, 50.0), (5.0, 15.0, 30.0)])
        results = run_sim(project, iterations=N_ITERATIONS, seed=401)

        durations = results.durations
        half = len(durations) // 2
        first_mean = float(np.mean(durations[:half]))
        second_mean = float(np.mean(durations[half:]))

        # Means should be very close (within standard error)
        se = float(np.std(durations)) / np.sqrt(half)
        diff = abs(first_mean - second_mean)
        # 3 standard errors is already very conservative
        assert diff < 4 * se, (
            f"Trend detected: first_half_mean={first_mean:.4f}, "
            f"second_half_mean={second_mean:.4f}, 4*SE={4*se:.4f}"
        )

    def test_task_durations_independent_across_tasks(self):
        """For parallel tasks, durations should be uncorrelated."""
        project = parallel_project(
            [(10.0, 25.0, 50.0), (8.0, 20.0, 45.0), (12.0, 30.0, 60.0)]
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=402)

        # Check pairwise correlations between task durations
        for i in range(3):
            for j in range(i + 1, 3):
                ti = f"t{i+1}"
                tj = f"t{j+1}"
                corr = float(
                    np.corrcoef(
                        results.task_durations[ti],
                        results.task_durations[tj],
                    )[0, 1]
                )
                assert (
                    abs(corr) < 0.02
                ), f"Tasks {ti},{tj} correlated: r={corr:.4f}, expected ≈ 0"


class TestReproducibilityAcrossProjects:
    """Different project structures with same seed produce consistent behavior."""

    def test_task_samples_same_regardless_of_topology(self):
        """The per-task samples should be the same whether chain or parallel.

        This verifies the engine samples tasks in a consistent order
        determined by task list, not by scheduling topology.
        """
        estimates = [(5.0, 15.0, 30.0), (10.0, 25.0, 50.0), (8.0, 20.0, 40.0)]

        chain = chain_project(estimates)
        par = parallel_project(estimates)

        chain_results = run_sim(chain, iterations=5000, seed=500)
        par_results = run_sim(par, iterations=5000, seed=500)

        # Task samples should be identical
        for i in range(3):
            tid = f"t{i+1}"
            assert np.array_equal(
                chain_results.task_durations[tid],
                par_results.task_durations[tid],
            ), f"Task {tid} samples differ between chain and parallel"
