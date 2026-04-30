"""Test 2: Moment validation — mean and variance match analytical formulas.

For triangular and lognormal distributions, we know the theoretical mean
and variance. When the engine applies no uncertainty multipliers and no
risks, the task duration distribution should match these exactly (within
statistical tolerance).

This validates: distribution sampling, unit conversion, and the absence
of unintended multiplicative factors.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy import stats

from mcprojsim.models.project import DistributionType

from .conftest import (
    ALPHA,
    N_ITERATIONS,
    N_ITERATIONS_HEAVY,
    assert_mean_within_ci,
    assert_variance_within_ci,
    lognormal_mean,
    lognormal_variance,
    run_sim,
    single_task_project,
    triangular_mean,
    triangular_variance,
)


class TestTriangularMoments:
    """Verify triangular distribution produces correct mean and variance."""

    @pytest.mark.parametrize(
        "low,mode,high",
        [
            (0.0, 10.0, 30.0),
            (5.0, 5.0, 20.0),  # mode == low (left-skewed)
            (5.0, 20.0, 20.0),  # mode == high (right-skewed)
            (10.0, 50.0, 100.0),
            (1.0, 2.0, 3.0),  # symmetric
            (100.0, 200.0, 500.0),  # large values
        ],
    )
    def test_mean(self, low: float, mode: float, high: float):
        """Sample mean matches (low + mode + high) / 3."""
        project = single_task_project(low, mode, high, distribution=DistributionType.TRIANGULAR)
        results = run_sim(project, iterations=N_ITERATIONS, seed=77)
        samples = results.task_durations["t1"]

        expected = triangular_mean(low, mode, high)
        assert_mean_within_ci(samples, expected, label=f"Tri({low},{mode},{high})")

    @pytest.mark.parametrize(
        "low,mode,high",
        [
            (0.0, 10.0, 30.0),
            (10.0, 50.0, 100.0),
            (1.0, 2.0, 3.0),
            (100.0, 200.0, 500.0),
        ],
    )
    def test_variance(self, low: float, mode: float, high: float):
        """Sample variance matches triangular variance formula."""
        project = single_task_project(low, mode, high, distribution=DistributionType.TRIANGULAR)
        results = run_sim(project, iterations=N_ITERATIONS, seed=88)
        samples = results.task_durations["t1"]

        expected = triangular_variance(low, mode, high)
        assert_variance_within_ci(samples, expected, label=f"Tri({low},{mode},{high})")

    def test_bounds_respected(self):
        """All samples must be within [low, high]."""
        low, mode, high = 5.0, 15.0, 40.0
        project = single_task_project(low, mode, high, distribution=DistributionType.TRIANGULAR)
        results = run_sim(project, iterations=N_ITERATIONS, seed=100)
        samples = results.task_durations["t1"]

        assert float(samples.min()) >= low
        assert float(samples.max()) <= high


class TestLognormalMoments:
    """Verify shifted lognormal produces correct mean and variance."""

    @pytest.mark.parametrize(
        "low,expected_val,high",
        [
            (10.0, 20.0, 50.0),
            (5.0, 15.0, 40.0),
            (0.0, 10.0, 30.0),
            (50.0, 100.0, 300.0),
            (1.0, 3.0, 10.0),
        ],
    )
    def test_mean(self, low: float, expected_val: float, high: float):
        """Sample mean matches theoretical shifted lognormal mean."""
        project = single_task_project(
            low, expected_val, high, distribution=DistributionType.LOGNORMAL
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=55)
        samples = results.task_durations["t1"]

        expected = lognormal_mean(low, expected_val, high)
        assert_mean_within_ci(samples, expected, label=f"LN({low},{expected_val},{high})")

    @pytest.mark.parametrize(
        "low,expected_val,high",
        [
            (10.0, 20.0, 50.0),
            (5.0, 15.0, 40.0),
            (50.0, 100.0, 300.0),
        ],
    )
    def test_variance(self, low: float, expected_val: float, high: float):
        """Sample variance matches theoretical shifted lognormal variance."""
        project = single_task_project(
            low, expected_val, high, distribution=DistributionType.LOGNORMAL
        )
        # Lognormal variance is harder to pin down — use more iterations
        results = run_sim(project, iterations=N_ITERATIONS_HEAVY, seed=66)
        samples = results.task_durations["t1"]

        expected = lognormal_variance(low, expected_val, high)
        observed = float(np.var(samples, ddof=1))
        # For lognormal (heavy-tailed), chi-squared test is unreliable due to
        # high kurtosis. Use relative tolerance instead: within 3% is excellent
        # for a distribution with excess kurtosis.
        relative_error = abs(observed - expected) / expected
        assert relative_error < 0.03, (
            f"LN({low},{expected_val},{high}): observed_var={observed:.4f}, "
            f"expected_var={expected:.4f}, relative_error={relative_error:.4f}"
        )

    def test_lower_bound_respected(self):
        """Shifted lognormal samples must be >= low."""
        low, expected_val, high = 10.0, 25.0, 60.0
        project = single_task_project(
            low, expected_val, high, distribution=DistributionType.LOGNORMAL
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=77)
        samples = results.task_durations["t1"]

        assert float(samples.min()) >= low - 1e-9


class TestProjectDurationMoments:
    """Verify project-level duration statistics for known topologies."""

    def test_chain_mean_is_sum_of_task_means(self):
        """For a sequential chain, E[project] = sum(E[task_i])."""
        estimates = [
            (5.0, 10.0, 20.0),
            (10.0, 20.0, 40.0),
            (3.0, 8.0, 15.0),
        ]
        from .conftest import chain_project

        project = chain_project(estimates, distribution=DistributionType.TRIANGULAR)
        results = run_sim(project, iterations=N_ITERATIONS, seed=42)

        expected_mean = sum(triangular_mean(*e) for e in estimates)
        assert_mean_within_ci(
            results.durations, expected_mean, label="Chain project mean"
        )

    def test_chain_variance_is_sum_of_task_variances(self):
        """For independent sequential tasks, Var[project] = sum(Var[task_i])."""
        estimates = [
            (5.0, 10.0, 20.0),
            (10.0, 20.0, 40.0),
            (3.0, 8.0, 15.0),
        ]
        from .conftest import chain_project

        project = chain_project(estimates, distribution=DistributionType.TRIANGULAR)
        results = run_sim(project, iterations=N_ITERATIONS, seed=42)

        expected_var = sum(triangular_variance(*e) for e in estimates)
        assert_variance_within_ci(
            results.durations, expected_var, label="Chain project variance"
        )

    def test_effort_mean_equals_sum_regardless_of_topology(self):
        """Effort (person-hours) mean = sum of task means for any DAG."""
        from .conftest import diamond_project

        a, b, c, d = (5.0, 10.0, 20.0), (10.0, 20.0, 40.0), (8.0, 15.0, 30.0), (3.0, 6.0, 12.0)
        project = diamond_project(a, b, c, d, distribution=DistributionType.TRIANGULAR)
        results = run_sim(project, iterations=N_ITERATIONS, seed=42)

        expected_effort_mean = sum(triangular_mean(*e) for e in [a, b, c, d])
        assert_mean_within_ci(
            results.effort_durations, expected_effort_mean, label="Diamond effort mean"
        )
