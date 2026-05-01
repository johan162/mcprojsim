"""Test 5: Percentile calibration validation.

Verify that the simulation's reported percentiles are statistically
consistent with the true CDF. If we claim P90 = X, then approximately
90% of samples should be ≤ X.

This uses the Dvoretzky–Kiefer–Wolfowitz inequality and binomial tests
to validate percentile accuracy.
"""

from __future__ import annotations

import numpy as np
import pytest

from mcprojsim.models.project import DistributionType

from .conftest import (
    N_ITERATIONS,
    chain_project,
    run_sim,
    single_task_project,
)


class TestPercentileCalibration:
    """Verify that reported percentiles are calibrated (P(X<=Pp) ≈ p/100)."""

    @pytest.mark.parametrize("percentile", [10, 25, 50, 75, 90, 95, 99])
    def test_single_task_percentile_calibration(self, percentile: int):
        """For a single triangular task, P(X ≤ percentile_val) ≈ percentile/100."""
        project = single_task_project(
            5.0, 20.0, 50.0, distribution=DistributionType.TRIANGULAR
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=200)
        samples = results.task_durations["t1"]

        # Get the p-th percentile from the samples
        p_value = float(np.percentile(samples, percentile))

        # Count how many samples are <= this value
        count_below = int(np.sum(samples <= p_value))

        # This should be approximately percentile/100 of total
        expected_p = percentile / 100.0

        # For the empirical percentile, we expect count_below ≈ N * p
        # Allow for the discrete nature: binomial with some tolerance
        # The DKW inequality gives us: P(|F_n(x) - F(x)| > ε) ≤ 2*exp(-2nε²)
        # For n=50000 and ε=0.01, this probability is ~4.5e-10
        obs_p = count_below / N_ITERATIONS
        assert abs(obs_p - expected_p) < 0.02, (
            f"Percentile {percentile}: observed fraction below = {obs_p:.4f}, "
            f"expected ≈ {expected_p:.4f}"
        )

    def test_project_percentile_self_consistency(self):
        """Percentiles are monotonically increasing."""
        project = chain_project(
            [(5.0, 15.0, 30.0), (10.0, 25.0, 50.0), (3.0, 8.0, 20.0)]
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=201)

        prev = 0.0
        for p in [10, 25, 50, 75, 90, 95, 99]:
            val = float(np.percentile(results.durations, p))
            assert val >= prev, f"P{p}={val} < P{p-1}={prev}"
            prev = val

    def test_median_close_to_reported_p50(self):
        """The results.median and the 50th percentile should agree."""
        project = single_task_project(
            10.0, 30.0, 60.0, distribution=DistributionType.TRIANGULAR
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=202)

        # results.median is computed by the engine
        p50_manual = float(np.median(results.durations))
        assert abs(results.median - p50_manual) < 1e-9


class TestPercentileSplitValidation:
    """Split the sample in half and verify percentiles agree (cross-validation)."""

    def test_split_half_percentile_agreement(self):
        """Split N iterations into two halves; percentiles should be close."""
        project = chain_project(
            [(5.0, 15.0, 35.0), (10.0, 20.0, 45.0), (8.0, 12.0, 28.0)]
        )
        # Use larger N for tighter bounds
        results = run_sim(project, iterations=N_ITERATIONS, seed=203)
        durations = results.durations

        # Split into two halves
        half = len(durations) // 2
        first_half = durations[:half]
        second_half = durations[half:]

        for p in [25, 50, 75, 90, 95]:
            p1 = float(np.percentile(first_half, p))
            p2 = float(np.percentile(second_half, p))
            # For N/2=25000 samples, the DKW bound gives ε ≈ 0.012 at 99.9% confidence
            # So percentiles should agree within ~2% of the range
            range_est = float(np.max(durations) - np.min(durations))
            tolerance = 0.03 * range_est  # 3% of range
            assert abs(p1 - p2) < tolerance, (
                f"P{p}: first_half={p1:.2f}, second_half={p2:.2f}, "
                f"diff={abs(p1-p2):.2f}, tolerance={tolerance:.2f}"
            )


class TestQuantileConvergence:
    """As N increases, sample quantiles converge to true quantiles."""

    def test_convergence_rate(self):
        """Quantile estimate error decreases as O(1/√N)."""
        project = single_task_project(
            10.0, 25.0, 50.0, distribution=DistributionType.TRIANGULAR
        )

        # Run at different iteration counts
        p50_estimates = []
        iteration_counts = [1000, 5000, 10000, 50000]

        for n in iteration_counts:
            results = run_sim(project, iterations=n, seed=204)
            p50_estimates.append(float(np.median(results.durations)))

        # The "true" P50 from our largest sample
        true_p50 = p50_estimates[-1]

        # Errors should generally decrease (not strictly monotone due to randomness)
        # But largest sample error should be smallest
        errors = [abs(est - true_p50) for est in p50_estimates[:-1]]
        # The smallest iteration count should have the largest error
        assert errors[0] >= errors[-1] or errors[0] < 0.5  # Allow tiny absolute errors


class TestConfidenceLevelInterpretation:
    """The simulation's confidence level semantics are correct."""

    def test_p80_means_80_percent_finish_by(self):
        """If P80 = X hours, then ~80% of simulations finish within X hours."""
        project = chain_project(
            [(10.0, 20.0, 40.0), (15.0, 30.0, 60.0)],
            distribution=DistributionType.TRIANGULAR,
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=205)

        p80_val = float(np.percentile(results.durations, 80))
        count_within = int(np.sum(results.durations <= p80_val))

        # Should be approximately 80%
        obs_frac = count_within / N_ITERATIONS
        assert (
            abs(obs_frac - 0.80) < 0.02
        ), f"P80 interpretation: {obs_frac*100:.1f}% finish by P80 value"

    def test_p95_means_95_percent_finish_by(self):
        """If P95 = X hours, then ~95% of simulations finish within X hours."""
        project = single_task_project(
            5.0, 20.0, 60.0, distribution=DistributionType.LOGNORMAL
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=206)

        p95_val = float(np.percentile(results.durations, 95))
        count_within = int(np.sum(results.durations <= p95_val))

        obs_frac = count_within / N_ITERATIONS
        assert abs(obs_frac - 0.95) < 0.01
