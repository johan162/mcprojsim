"""Category 3: Moment convergence tests.

Verify that sample statistics converge to analytically derivable values.
"""

from __future__ import annotations

import numpy as np
import pytest

from mcprojsim.models.project import UncertaintyFactors

from .conftest import (
    STAT_ITERATIONS_CI,
    STAT_ITERATIONS_FULL,
    assert_mean_close,
    assert_variance_close,
    make_chain_project,
    make_parallel_project,
    make_single_task_project,
    run_simulation,
    shifted_lognormal_mean,
    shifted_lognormal_variance,
)

pytestmark = pytest.mark.probabilistic


# ------------------------------------------------------------------
# 3.1  Single task mean convergence
# ------------------------------------------------------------------
class TestSingleTaskMean:
    """Sample mean should converge to theoretical shifted lognormal mean.

    E[Y] = low + exp(μ + σ²/2)
    """

    @pytest.mark.probabilistic_full
    def test_mean_converges_to_theoretical(self):
        low, expected, high = 8.0, 20.0, 55.0
        theoretical_mean = shifted_lognormal_mean(low, expected, high)

        project = make_single_task_project(low=low, expected=expected, high=high)
        results = run_simulation(project, iterations=STAT_ITERATIONS_FULL, seed=42)

        assert_mean_close(
            results.task_durations["t1"],
            theoretical_mean,
            label=(f"Single task mean (theoretical={theoretical_mean:.4f})"),
        )

    @pytest.mark.parametrize(
        "low,expected,high",
        [(5.0, 15.0, 40.0), (1.0, 3.0, 10.0), (50.0, 100.0, 250.0)],
    )
    @pytest.mark.probabilistic_full
    def test_mean_various_estimates(self, low, expected, high):
        theoretical_mean = shifted_lognormal_mean(low, expected, high)

        project = make_single_task_project(low=low, expected=expected, high=high)
        results = run_simulation(project, iterations=STAT_ITERATIONS_FULL, seed=77)

        assert_mean_close(
            results.task_durations["t1"],
            theoretical_mean,
            label=f"Mean ({low}, {expected}, {high})",
        )


# ------------------------------------------------------------------
# 3.2  Single task variance convergence
# ------------------------------------------------------------------
class TestSingleTaskVariance:
    """Sample variance should converge to theoretical shifted lognormal variance.

    Var[Y] = exp(2μ + σ²) · (exp(σ²) - 1)
    """

    @pytest.mark.probabilistic_full
    def test_variance_converges_to_theoretical(self):
        low, expected, high = 8.0, 20.0, 55.0
        theoretical_var = shifted_lognormal_variance(low, expected, high)

        project = make_single_task_project(low=low, expected=expected, high=high)
        results = run_simulation(project, iterations=STAT_ITERATIONS_FULL, seed=42)

        assert_variance_close(
            results.task_durations["t1"],
            theoretical_var,
            label=(f"Single task variance (theoretical={theoretical_var:.4f})"),
        )


# ------------------------------------------------------------------
# 3.3  Effort mean = sum of task means (independent tasks)
# ------------------------------------------------------------------
class TestEffortMeanConvergence:
    """Mean effort should equal sum of individual task means."""

    @pytest.mark.probabilistic_full
    def test_effort_mean_equals_sum_of_task_means(self):
        task_specs = [
            (5.0, 10.0, 25.0),
            (10.0, 20.0, 50.0),
            (3.0, 8.0, 20.0),
            (15.0, 30.0, 70.0),
            (8.0, 15.0, 40.0),
        ]
        expected_means = [
            shifted_lognormal_mean(low, exp, high) for low, exp, high in task_specs
        ]
        total_expected_mean = sum(expected_means)

        project = make_parallel_project(estimates=task_specs)
        results = run_simulation(project, iterations=STAT_ITERATIONS_FULL, seed=42)

        assert_mean_close(
            results.effort_durations,
            total_expected_mean,
            label=f"Effort mean = Σ task means ({total_expected_mean:.2f})",
        )


# ------------------------------------------------------------------
# 3.4  Uncertainty factor scales mean exactly
# ------------------------------------------------------------------
class TestUncertaintyFactorScaling:
    """Applying a multiplicative uncertainty factor m should scale
    the task mean by m.  With the same seed, the ratio should be
    exact (not statistical).
    """

    def test_requirements_maturity_low_scales_by_1_40(self):
        """requirements_maturity='low' has multiplier 1.40."""
        project_base = make_single_task_project(low=10.0, expected=30.0, high=80.0)
        project_scaled = make_single_task_project(
            low=10.0,
            expected=30.0,
            high=80.0,
            uncertainty_factors=UncertaintyFactors(requirements_maturity="low"),
        )

        results_base = run_simulation(
            project_base, iterations=STAT_ITERATIONS_CI, seed=42
        )
        results_scaled = run_simulation(
            project_scaled, iterations=STAT_ITERATIONS_CI, seed=42
        )

        mean_base = float(np.mean(results_base.task_durations["t1"]))
        mean_scaled = float(np.mean(results_scaled.task_durations["t1"]))
        ratio = mean_scaled / mean_base

        # Same seed → same base samples → exact ratio
        assert abs(ratio - 1.40) < 0.01, (
            f"UNCERTAINTY SCALING ERROR: "
            f"mean_base={mean_base:.4f}, mean_scaled={mean_scaled:.4f}, "
            f"ratio={ratio:.6f}, expected=1.40. "
            f"SUGGESTION: Check Config.get_uncertainty_multiplier for "
            f"'requirements_maturity' level 'low'.  Value should be 1.40."
        )

    def test_team_experience_high_scales_by_0_90(self):
        """team_experience='high' has multiplier 0.90."""
        project_base = make_single_task_project(low=10.0, expected=30.0, high=80.0)
        project_scaled = make_single_task_project(
            low=10.0,
            expected=30.0,
            high=80.0,
            uncertainty_factors=UncertaintyFactors(team_experience="high"),
        )

        results_base = run_simulation(
            project_base, iterations=STAT_ITERATIONS_CI, seed=42
        )
        results_scaled = run_simulation(
            project_scaled, iterations=STAT_ITERATIONS_CI, seed=42
        )

        mean_base = float(np.mean(results_base.task_durations["t1"]))
        mean_scaled = float(np.mean(results_scaled.task_durations["t1"]))
        ratio = mean_scaled / mean_base

        assert (
            abs(ratio - 0.90) < 0.01
        ), f"UNCERTAINTY SCALING ERROR: ratio={ratio:.6f}, expected=0.90."


# ------------------------------------------------------------------
# 3.5  Chain duration mean = sum of task means
# ------------------------------------------------------------------
class TestChainMean:
    """For a pure chain, E[project_duration] = Σ E[task_i]."""

    @pytest.mark.probabilistic_full
    def test_chain_mean_equals_sum(self):
        estimates = [(5.0, 15.0, 40.0), (10.0, 25.0, 60.0), (8.0, 20.0, 50.0)]
        expected_total = sum(
            shifted_lognormal_mean(low, exp, high) for low, exp, high in estimates
        )

        project = make_chain_project(estimates=estimates)
        results = run_simulation(project, iterations=STAT_ITERATIONS_FULL, seed=42)

        assert_mean_close(
            results.durations,
            expected_total,
            label=f"Chain mean = Σ task means ({expected_total:.2f})",
        )


# ------------------------------------------------------------------
# 3.6  Parallel duration bounds: max(E[Ti]) ≤ E[max] < Σ E[Ti]
# ------------------------------------------------------------------
class TestParallelDurationBounds:
    """For parallel tasks, E[max] is between max(E[Ti]) and Σ E[Ti]."""

    def test_parallel_mean_bounds(self):
        estimates = [
            (5.0, 15.0, 40.0),
            (10.0, 25.0, 60.0),
            (8.0, 20.0, 50.0),
        ]
        task_means = [
            shifted_lognormal_mean(low, exp, high) for low, exp, high in estimates
        ]

        project = make_parallel_project(estimates=estimates)
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)
        duration_mean = float(np.mean(results.durations))

        max_task_mean = max(task_means)
        sum_task_means = sum(task_means)

        assert duration_mean > max_task_mean - 1.0, (
            f"PARALLEL MEAN TOO LOW: E[max]={duration_mean:.2f} but "
            f"max(E[Ti])={max_task_mean:.2f}. "
            f"E[max(T1,...,Tn)] must be ≥ max(E[Ti])."
        )
        assert duration_mean < sum_task_means + 1.0, (
            f"PARALLEL MEAN TOO HIGH: E[max]={duration_mean:.2f} but "
            f"Σ E[Ti]={sum_task_means:.2f}. "
            f"Parallel execution should be shorter than sequential."
        )
