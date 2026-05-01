"""Test 8: Distribution shape validation using goodness-of-fit tests.

Use Kolmogorov-Smirnov tests to verify that sampled distributions match
their theoretical CDFs exactly.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy import stats

from mcprojsim.models.project import DistributionType
from mcprojsim.simulation.distributions import fit_shifted_lognormal

from .conftest import (
    N_ITERATIONS,
    Z_95,
    assert_ks_fit,
    assert_samples_bounded,
    run_sim,
    single_task_project,
)


class TestTriangularDistributionShape:
    """Verify triangular samples match the theoretical triangular CDF."""

    @pytest.mark.parametrize(
        "low,mode,high",
        [
            (0.0, 10.0, 30.0),
            (5.0, 5.0, 20.0),  # left-edge mode
            (5.0, 20.0, 20.0),  # right-edge mode
            (10.0, 50.0, 100.0),
            (1.0, 1.5, 3.0),  # tight range
        ],
    )
    def test_ks_triangular(self, low: float, mode: float, high: float):
        """KS test against scipy triangular CDF."""
        project = single_task_project(
            low, mode, high, distribution=DistributionType.TRIANGULAR
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=600)
        samples = results.task_durations["t1"]

        # scipy triangular: c = (mode - low) / (high - low), loc=low, scale=high-low
        c = (mode - low) / (high - low)
        frozen = stats.triang(c, loc=low, scale=high - low)

        assert_ks_fit(samples, frozen.cdf, label=f"Triangular({low},{mode},{high})")

    @pytest.mark.parametrize(
        "low,mode,high",
        [
            (0.0, 10.0, 30.0),
            (10.0, 50.0, 100.0),
        ],
    )
    def test_triangular_bounds(self, low: float, mode: float, high: float):
        """All triangular samples within [low, high]."""
        project = single_task_project(
            low, mode, high, distribution=DistributionType.TRIANGULAR
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=601)
        samples = results.task_durations["t1"]

        assert_samples_bounded(samples, low, high, label="Triangular bounds")


class TestLognormalDistributionShape:
    """Verify shifted lognormal samples match the theoretical CDF."""

    @pytest.mark.parametrize(
        "low,expected,high",
        [
            (10.0, 20.0, 50.0),
            (5.0, 15.0, 40.0),
            (0.0, 10.0, 30.0),
            (50.0, 100.0, 300.0),
        ],
    )
    def test_ks_shifted_lognormal(self, low: float, expected: float, high: float):
        """KS test against the shifted lognormal CDF."""
        project = single_task_project(
            low, expected, high, distribution=DistributionType.LOGNORMAL
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=602)
        samples = results.task_durations["t1"]

        mu, sigma = fit_shifted_lognormal(low, expected, high, Z_95)
        # Shifted lognormal: X = low + Lognormal(mu, sigma)
        # scipy lognorm: s=sigma, scale=exp(mu), loc=low
        frozen = stats.lognorm(s=sigma, scale=math.exp(mu), loc=low)

        assert_ks_fit(samples, frozen.cdf, label=f"ShiftedLN({low},{expected},{high})")

    def test_lognormal_lower_bound(self):
        """Shifted lognormal always >= low."""
        low, expected, high = 15.0, 30.0, 80.0
        project = single_task_project(
            low, expected, high, distribution=DistributionType.LOGNORMAL
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=603)
        samples = results.task_durations["t1"]

        assert float(samples.min()) >= low - 1e-9

    def test_lognormal_right_skew(self):
        """Shifted lognormal is right-skewed: mean > median > mode."""
        low, expected, high = 5.0, 20.0, 60.0
        project = single_task_project(
            low, expected, high, distribution=DistributionType.LOGNORMAL
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=604)
        samples = results.task_durations["t1"]

        mean = float(np.mean(samples))
        median = float(np.median(samples))
        # Mode of shifted lognormal = low + exp(mu - sigma^2)
        mu, sigma = fit_shifted_lognormal(low, expected, high, Z_95)
        theoretical_mode = low + math.exp(mu - sigma**2)

        # Right-skewed property
        assert mean > median, f"mean={mean:.2f} should > median={median:.2f}"
        assert (
            median > theoretical_mode
        ), f"median={median:.2f} should > mode={theoretical_mode:.2f}"

    def test_lognormal_high_percentile_calibrated(self):
        """The 'high' value should be approximately the 95th percentile."""
        low, expected, high = 10.0, 25.0, 60.0
        project = single_task_project(
            low, expected, high, distribution=DistributionType.LOGNORMAL
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=605)
        samples = results.task_durations["t1"]

        # By construction, 'high' is the 95th percentile of the shifted lognormal
        empirical_p95 = float(np.percentile(samples, 95))
        # Should be close to 'high'
        relative_error = abs(empirical_p95 - high) / high
        assert relative_error < 0.03, (
            f"P95={empirical_p95:.2f} vs high={high:.2f}, "
            f"relative error={relative_error:.4f}"
        )


class TestChainDistributionShape:
    """For a chain of independent tasks, verify sum-distribution properties."""

    def test_chain_of_triangular_normality(self):
        """Sum of many independent triangular RVs should be approximately normal (CLT)."""
        # 10 identical tasks in a chain → CLT applies
        est = (5.0, 15.0, 30.0)
        n_tasks = 10
        from .conftest import chain_project

        project = chain_project(
            [est] * n_tasks, distribution=DistributionType.TRIANGULAR
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=606)

        # By CLT, the sum should be approximately normal
        # Test normality with Shapiro-Wilk on a subset (too slow for full sample)
        # Use Anderson-Darling instead which handles larger samples
        # Actually, use D'Agostino and Pearson's test
        subsample = results.durations[:5000]  # Subset for speed
        stat, p_value = stats.normaltest(subsample)

        # For 10 triangular RVs, the CLT approximation should be decent
        # We don't require perfect normality (p > 0.05), but skewness/kurtosis
        # should be close to normal
        skew = float(stats.skew(results.durations))
        kurt = float(stats.kurtosis(results.durations))

        # Skewness should be small (normal = 0)
        assert abs(skew) < 0.3, f"Skewness={skew:.4f}, expected close to 0"
        # Excess kurtosis should be small (normal = 0)
        assert abs(kurt) < 0.3, f"Kurtosis={kurt:.4f}, expected close to 0"
