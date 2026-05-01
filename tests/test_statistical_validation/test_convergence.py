"""Test 10: Convergence and Central Limit Theorem validation.

These tests verify that:
1. Sample statistics converge as iterations increase
2. The sampling distribution of the mean follows the CLT
3. Confidence intervals have correct coverage
"""

from __future__ import annotations

import math

import numpy as np
from scipy import stats

from mcprojsim.models.project import DistributionType

from .conftest import (
    run_sim,
    single_task_project,
    triangular_mean,
    triangular_variance,
)


class TestConvergenceOfMean:
    """As N increases, sample mean converges to population mean."""

    def test_mean_converges(self):
        """Mean error decreases approximately as 1/√N."""
        low, mode, high = 10.0, 25.0, 50.0
        true_mean = triangular_mean(low, mode, high)

        project = single_task_project(
            low, mode, high, distribution=DistributionType.TRIANGULAR
        )

        iteration_counts = [100, 500, 2000, 10000, 50000]
        errors = []

        for n in iteration_counts:
            results = run_sim(project, iterations=n, seed=800)
            obs_mean = float(np.mean(results.durations))
            errors.append(abs(obs_mean - true_mean))

        # Error should generally decrease
        # With these specific seeds, the trend should be clear
        # The key insight: error at N=50000 should be much less than at N=100
        assert errors[-1] < errors[0] * 0.5, (
            f"Mean error did not converge: N=100 error={errors[0]:.4f}, "
            f"N=50000 error={errors[-1]:.4f}"
        )

    def test_standard_error_formula(self):
        """SE = σ/√N should predict the actual estimation error magnitude."""
        low, mode, high = 5.0, 20.0, 40.0
        true_var = triangular_variance(low, mode, high)
        project = single_task_project(
            low, mode, high, distribution=DistributionType.TRIANGULAR
        )

        # Run many independent replications and check SE
        n = 10_000
        n_replications = 20
        sample_means = []
        for rep_seed in range(n_replications):
            results = run_sim(project, iterations=n, seed=801 + rep_seed)
            sample_means.append(float(np.mean(results.durations)))

        # Empirical SE of sample means
        empirical_se = float(np.std(sample_means, ddof=1))
        theoretical_se = math.sqrt(true_var / n)

        # Should be within factor of 2 (very conservative)
        ratio = empirical_se / theoretical_se
        assert 0.5 < ratio < 2.0, (
            f"SE ratio = {ratio:.3f}: empirical={empirical_se:.6f}, "
            f"theoretical={theoretical_se:.6f}"
        )


class TestCLTNormality:
    """Central Limit Theorem: sample mean is approximately normal."""

    def test_mean_distribution_normal(self):
        """Distribution of sample means across replications is approximately normal."""
        low, mode, high = 8.0, 20.0, 45.0
        project = single_task_project(
            low, mode, high, distribution=DistributionType.TRIANGULAR
        )

        n = 5000
        n_replications = 50
        sample_means = []
        for rep_seed in range(n_replications):
            results = run_sim(project, iterations=n, seed=810 + rep_seed)
            sample_means.append(float(np.mean(results.durations)))

        # Test normality of the sample means
        # With 50 replications, Shapiro-Wilk is appropriate
        stat, p_value = stats.shapiro(sample_means)
        # We don't need p > 0.05 strictly, but it shouldn't be extremely small
        assert p_value > 0.01, f"Sample means not normal: Shapiro-Wilk p={p_value:.4f}"


class TestConfidenceIntervalCoverage:
    """Verify that confidence intervals have correct coverage probability."""

    def test_95_ci_coverage(self):
        """A 95% CI should contain the true mean ~95% of the time."""
        low, mode, high = 10.0, 25.0, 50.0
        true_mean = triangular_mean(low, mode, high)
        project = single_task_project(
            low, mode, high, distribution=DistributionType.TRIANGULAR
        )

        n = 5000
        n_replications = 200
        coverage_count = 0

        for rep_seed in range(n_replications):
            results = run_sim(project, iterations=n, seed=820 + rep_seed)
            samples = results.durations
            sample_mean = float(np.mean(samples))
            se = float(np.std(samples, ddof=1)) / math.sqrt(n)

            # 95% CI: mean ± 1.96 * SE
            ci_lower = sample_mean - 1.96 * se
            ci_upper = sample_mean + 1.96 * se

            if ci_lower <= true_mean <= ci_upper:
                coverage_count += 1

        # Coverage should be approximately 95%
        coverage_rate = coverage_count / n_replications
        # Binomial test: is coverage consistent with 0.95?
        result = stats.binomtest(coverage_count, n_replications, 0.95)
        assert result.pvalue > 0.01, (
            f"95% CI coverage = {coverage_rate*100:.1f}% ({coverage_count}/{n_replications}), "
            f"p-value = {result.pvalue:.4f}"
        )

    def test_99_ci_coverage(self):
        """A 99% CI should contain the true mean ~99% of the time."""
        low, mode, high = 5.0, 15.0, 35.0
        true_mean = triangular_mean(low, mode, high)
        project = single_task_project(
            low, mode, high, distribution=DistributionType.TRIANGULAR
        )

        n = 5000
        n_replications = 200
        coverage_count = 0

        for rep_seed in range(n_replications):
            results = run_sim(project, iterations=n, seed=830 + rep_seed)
            samples = results.durations
            sample_mean = float(np.mean(samples))
            se = float(np.std(samples, ddof=1)) / math.sqrt(n)

            # 99% CI: mean ± 2.576 * SE
            ci_lower = sample_mean - 2.576 * se
            ci_upper = sample_mean + 2.576 * se

            if ci_lower <= true_mean <= ci_upper:
                coverage_count += 1

        coverage_rate = coverage_count / n_replications
        # Should be ≥ 97% (allowing some slack for discrete N)
        assert (
            coverage_rate >= 0.96
        ), f"99% CI coverage = {coverage_rate*100:.1f}% ({coverage_count}/{n_replications})"


class TestVarianceConvergence:
    """Sample variance also converges correctly."""

    def test_variance_unbiased(self):
        """Sample variance (ddof=1) is unbiased for the population variance."""
        low, mode, high = 10.0, 30.0, 60.0
        true_var = triangular_variance(low, mode, high)
        project = single_task_project(
            low, mode, high, distribution=DistributionType.TRIANGULAR
        )

        n = 10_000
        n_replications = 30
        sample_variances = []

        for rep_seed in range(n_replications):
            results = run_sim(project, iterations=n, seed=840 + rep_seed)
            s2 = float(np.var(results.durations, ddof=1))
            sample_variances.append(s2)

        # Mean of sample variances should be close to true variance (unbiasedness)
        mean_s2 = float(np.mean(sample_variances))
        relative_error = abs(mean_s2 - true_var) / true_var
        assert relative_error < 0.05, (
            f"Sample variance biased: mean(s²)={mean_s2:.4f}, "
            f"true σ²={true_var:.4f}, relative error={relative_error:.4f}"
        )
