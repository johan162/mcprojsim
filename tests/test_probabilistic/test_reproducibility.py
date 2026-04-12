"""Category 8: Reproducibility and seed tests.

Verify that identical seeds produce identical results and different
seeds produce statistically different results.
"""

from __future__ import annotations

import numpy as np
import pytest

from .conftest import (
    STAT_ITERATIONS_CI,
    make_chain_project,
    make_constrained_parallel_project,
    make_diamond_project,
    make_parallel_project,
    run_simulation,
)

pytestmark = pytest.mark.probabilistic


# ------------------------------------------------------------------
# 8.1  Same seed → identical results
# ------------------------------------------------------------------
class TestSameSeedIdentical:
    """Two runs with the same seed must produce bit-identical arrays."""

    def test_chain_same_seed(self):
        project = make_chain_project(n_tasks=5)
        r1 = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=123)
        r2 = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=123)

        assert np.array_equal(r1.durations, r2.durations), (
            "REPRODUCIBILITY: same seed produced different durations. "
            "SUGGESTION: Check that SimulationEngine uses the seed "
            "to initialise a fresh RandomState each time."
        )

    def test_parallel_same_seed(self):
        project = make_parallel_project(n_parallel=4)
        r1 = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=456)
        r2 = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=456)

        assert np.array_equal(r1.durations, r2.durations)
        for tid in r1.task_durations:
            assert np.array_equal(
                r1.task_durations[tid], r2.task_durations[tid]
            ), f"Task {tid} durations differ with same seed."

    def test_diamond_same_seed(self):
        project = make_diamond_project()
        r1 = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=789)
        r2 = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=789)

        assert np.array_equal(r1.durations, r2.durations)
        assert r1.critical_path_frequency == r2.critical_path_frequency

    def test_effort_same_seed(self):
        project = make_chain_project(n_tasks=3)
        r1 = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)
        r2 = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        assert np.array_equal(r1.effort_durations, r2.effort_durations)


# ------------------------------------------------------------------
# 8.2  Different seeds → different results
# ------------------------------------------------------------------
class TestDifferentSeedsDiverge:
    """Two runs with different seeds should produce different arrays."""

    def test_different_seeds_differ(self):
        project = make_chain_project(n_tasks=5)
        r1 = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=100)
        r2 = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=200)

        assert not np.array_equal(r1.durations, r2.durations), (
            "REPRODUCIBILITY: different seeds produced identical "
            "durations. This is astronomically unlikely unless the "
            "engine ignores the seed."
        )

    def test_different_seeds_similar_statistics(self):
        """Despite different arrays, statistics should be close."""
        project = make_chain_project(n_tasks=5)
        r1 = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=100)
        r2 = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=200)

        # Means should be within ~5% of each other
        rel_diff = abs(r1.mean - r2.mean) / r1.mean
        assert rel_diff < 0.10, (
            f"REPRODUCIBILITY: means differ too much between seeds. "
            f"mean1={r1.mean:.2f}, mean2={r2.mean:.2f}, "
            f"rel_diff={rel_diff:.4f}."
        )


# ------------------------------------------------------------------
# 8.3  Two-pass reproducibility
# ------------------------------------------------------------------
class TestTwoPassReproducibility:
    """Two-pass mode should also be reproducible with same seed."""

    def test_two_pass_same_seed(self):
        project = make_constrained_parallel_project(n_parallel=4, n_resources=2)
        r1 = run_simulation(
            project,
            iterations=STAT_ITERATIONS_CI,
            seed=42,
            two_pass=True,
        )
        r2 = run_simulation(
            project,
            iterations=STAT_ITERATIONS_CI,
            seed=42,
            two_pass=True,
        )

        assert np.array_equal(r1.durations, r2.durations), (
            "TWO-PASS REPRODUCIBILITY: same seed produced different "
            "durations in two-pass mode."
        )


# ------------------------------------------------------------------
# 8.4  Iteration count does not affect per-iteration values
# ------------------------------------------------------------------
class TestIterationPrefix:
    """Running N+M iterations with the same seed should have the
    first N values identical to running N iterations alone (the
    engine should draw from the same PRNG sequence).
    """

    def test_prefix_property(self):
        project = make_chain_project(n_tasks=3)
        n_small = 500
        n_large = 2000

        r_small = run_simulation(project, iterations=n_small, seed=42)
        r_large = run_simulation(project, iterations=n_large, seed=42)

        assert np.array_equal(r_small.durations, r_large.durations[:n_small]), (
            "PREFIX PROPERTY: first N iterations of a larger run "
            "should match a standalone N-iteration run with the "
            "same seed. SUGGESTION: The engine may be consuming "
            "PRNG values in a non-deterministic order or doing "
            "pre-processing that advances the RNG state."
        )


# ------------------------------------------------------------------
# 8.5  Statistics stability across seeds
# ------------------------------------------------------------------
class TestStatisticsStability:
    """Run with multiple seeds; verify that key statistics converge
    to similar values (law of large numbers).
    """

    def test_mean_stable_across_seeds(self):
        project = make_chain_project(n_tasks=4)
        means = []
        for seed in range(10):
            r = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=seed)
            means.append(r.mean)

        mean_arr = np.array(means)
        cv = float(np.std(mean_arr) / np.mean(mean_arr))

        assert cv < 0.05, (
            f"STABILITY: coefficient of variation of means across "
            f"10 seeds = {cv:.4f}, expected < 0.05. "
            f"SUGGESTION: means should converge with 5000 iterations."
        )
