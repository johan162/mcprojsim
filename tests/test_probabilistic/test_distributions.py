"""Category 2: Distribution shape tests.

Verify that sampled distributions match their theoretical forms using
goodness-of-fit tests.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy import stats

from mcprojsim.config import Config
from mcprojsim.models.project import DistributionType
from mcprojsim.simulation.distributions import fit_shifted_lognormal

from .conftest import (
    STAT_ITERATIONS_CI,
    STAT_ITERATIONS_FULL,
    Z_95,
    assert_ks_test,
    assert_proportion_close,
    make_chain_project,
    make_parallel_project,
    make_single_task_project,
    run_simulation,
    shifted_lognormal_cdf,
)

pytestmark = pytest.mark.probabilistic


# ------------------------------------------------------------------
# 2.1  Shifted lognormal distribution shape (KS test)
# ------------------------------------------------------------------
class TestShiftedLognormalShape:
    """Task durations should follow the theoretical shifted lognormal."""

    @pytest.mark.probabilistic_full
    def test_ks_shifted_lognormal(self):
        low, expected, high = 10.0, 30.0, 80.0
        project = make_single_task_project(low=low, expected=expected, high=high)
        results = run_simulation(project, iterations=STAT_ITERATIONS_FULL, seed=42)
        samples = results.task_durations["t1"]

        mu, sigma = fit_shifted_lognormal(low, expected, high, Z_95)
        frozen = shifted_lognormal_cdf(low, mu, sigma)
        assert_ks_test(
            samples,
            frozen.cdf,
            label=(
                f"Shifted lognormal KS (low={low}, expected={expected}, "
                f"high={high}, μ={mu:.4f}, σ={sigma:.4f})"
            ),
        )

    @pytest.mark.parametrize(
        "low,expected,high",
        [
            (5.0, 15.0, 40.0),
            (1.0, 3.0, 10.0),
            (50.0, 100.0, 250.0),
        ],
    )
    @pytest.mark.probabilistic_full
    def test_ks_various_estimates(self, low, expected, high):
        project = make_single_task_project(low=low, expected=expected, high=high)
        results = run_simulation(project, iterations=STAT_ITERATIONS_FULL, seed=123)
        samples = results.task_durations["t1"]

        mu, sigma = fit_shifted_lognormal(low, expected, high, Z_95)
        frozen = shifted_lognormal_cdf(low, mu, sigma)
        assert_ks_test(
            samples,
            frozen.cdf,
            label=f"Shifted lognormal KS ({low}, {expected}, {high})",
        )


# ------------------------------------------------------------------
# 2.2  Triangular distribution shape (KS test)
# ------------------------------------------------------------------
class TestTriangularShape:
    """Triangular-mode samples should follow scipy.stats.triang."""

    @pytest.mark.probabilistic_full
    def test_ks_triangular(self):
        low, expected, high = 5.0, 20.0, 60.0
        project = make_single_task_project(
            low=low,
            expected=expected,
            high=high,
            distribution=DistributionType.TRIANGULAR,
        )
        results = run_simulation(project, iterations=STAT_ITERATIONS_FULL, seed=42)
        samples = results.task_durations["t1"]

        # scipy.stats.triang parameterisation: c = (mode - low) / (high - low)
        c = (expected - low) / (high - low)
        frozen = stats.triang(c, loc=low, scale=high - low)
        assert_ks_test(
            samples,
            frozen.cdf,
            label=f"Triangular KS (low={low}, mode={expected}, high={high})",
        )


# ------------------------------------------------------------------
# 2.3  Mode location (empirical mode near 'expected')
# ------------------------------------------------------------------
class TestModeLocation:
    """The empirical mode should be close to the 'expected' estimate."""

    @pytest.mark.probabilistic_full
    def test_lognormal_mode_near_expected(self):
        low, expected, high = 5.0, 20.0, 60.0
        project = make_single_task_project(low=low, expected=expected, high=high)
        results = run_simulation(project, iterations=STAT_ITERATIONS_FULL, seed=42)
        samples = results.task_durations["t1"]

        # KDE mode estimation
        kde = stats.gaussian_kde(samples)
        x_grid = np.linspace(float(samples.min()), float(samples.max()), 2000)
        mode_estimate = float(x_grid[np.argmax(kde(x_grid))])

        # Allow 15% relative tolerance on mode location
        rel_error = abs(mode_estimate - expected) / expected
        assert rel_error < 0.15, (
            f"MODE LOCATION ERROR: KDE mode={mode_estimate:.2f}, "
            f"expected={expected:.2f}, relative error={rel_error:.2%}. "
            f"SUGGESTION: Check fit_shifted_lognormal — the mode of the "
            f"shifted lognormal should be low + exp(μ - σ²) = expected."
        )


# ------------------------------------------------------------------
# 2.4  High percentile calibration (P95)
# ------------------------------------------------------------------
class TestHighPercentileCalibration:
    """~5% of samples should exceed the 'high' estimate (P95 config)."""

    @pytest.mark.probabilistic_full
    def test_p95_exceedance_rate(self):
        low, expected, high = 10.0, 25.0, 60.0
        project = make_single_task_project(low=low, expected=expected, high=high)
        results = run_simulation(project, iterations=STAT_ITERATIONS_FULL, seed=42)
        samples = results.task_durations["t1"]

        exceedance_count = int(np.sum(samples > high))
        # Default config: high_percentile = 95, so ~5% should exceed
        expected_exceedance = (
            1.0 - Config.get_default().lognormal.high_percentile / 100.0
        )

        assert_proportion_close(
            exceedance_count,
            len(samples),
            expected_exceedance,
            alpha=0.001,
            label="P95 calibration — exceedance rate",
        )


# ------------------------------------------------------------------
# 2.5  Right skew
# ------------------------------------------------------------------
class TestSkewness:
    """Shifted lognormal and project duration should be right-skewed."""

    def test_single_task_positive_skewness(self):
        project = make_single_task_project(low=5.0, expected=20.0, high=80.0)
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        assert results.skewness > 0, (
            f"EXPECTED POSITIVE SKEWNESS, got {results.skewness:.4f}. "
            f"Shifted lognormal distributions are inherently right-skewed. "
            f"SUGGESTION: Check skewness calculation in "
            f"SimulationResults.calculate_statistics."
        )

    def test_chain_positive_skewness(self):
        """Sum of right-skewed variables is right-skewed."""
        project = make_chain_project(n_tasks=5)
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)
        assert (
            results.skewness > 0
        ), f"EXPECTED POSITIVE SKEWNESS for chain, got {results.skewness:.4f}."


# ------------------------------------------------------------------
# 2.6  Effort normality for many parallel tasks (CLT)
# ------------------------------------------------------------------
class TestEffortNormality:
    """With many independent parallel tasks, effort approaches Normal."""

    @pytest.mark.probabilistic_full
    def test_effort_skewness_decreases_with_more_tasks(self):
        """CLT convergence: skewness of effort sum should decrease
        as more independent tasks are added.

        NOTE: A strict normality test (e.g. Anderson-Darling) fails
        because with 100k samples the test has extreme power to detect
        residual non-normality in sums of skewed lognormals.  Instead
        we verify the CLT *trend*: skewness must shrink monotonically
        as n grows, which is the core CLT guarantee.
        """
        skewness_values = []
        for n_tasks in [5, 15, 50]:
            project = make_parallel_project(n_parallel=n_tasks)
            results = run_simulation(project, iterations=STAT_ITERATIONS_FULL, seed=42)
            effort = results.effort_durations
            skew = float(stats.skew(effort))
            skewness_values.append((n_tasks, skew))

        for i in range(len(skewness_values) - 1):
            n1, s1 = skewness_values[i]
            n2, s2 = skewness_values[i + 1]
            assert abs(s2) < abs(s1), (
                f"CLT CONVERGENCE FAILURE: skewness should decrease "
                f"as tasks increase.  n={n1} skew={s1:.4f}, "
                f"n={n2} skew={s2:.4f}. "
                f"SUGGESTION: Check that parallel tasks are truly "
                f"independent and their effort is summed correctly."
            )
