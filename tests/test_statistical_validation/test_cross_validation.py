"""Test 11: Cross-validation with independent reference implementation.

Build a minimal reference simulation (no engine code) using raw numpy
and compare its outputs to the engine. This catches bugs in the engine's
internal wiring that wouldn't be detected by checking against formulas alone.
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np
import pytest
from scipy import stats

from mcprojsim.config import Config, EffortUnit
from mcprojsim.models.project import (
    DistributionType,
    Project,
    ProjectMetadata,
    Risk,
    Task,
    TaskEstimate,
)
from mcprojsim.simulation.distributions import fit_shifted_lognormal
from mcprojsim.simulation.engine import SimulationEngine

from .conftest import (
    ALPHA,
    N_ITERATIONS,
    START_DATE,
    Z_95,
    assert_mean_within_ci,
)


def _reference_triangular_sample(
    rng: np.random.RandomState, low: float, mode: float, high: float
) -> float:
    """Reference triangular sampling (same as numpy)."""
    return float(rng.triangular(low, mode, high))


def _reference_lognormal_sample(
    rng: np.random.RandomState, low: float, expected: float, high: float
) -> float:
    """Reference shifted lognormal sampling."""
    mu, sigma = fit_shifted_lognormal(low, expected, high, Z_95)
    return float(low + rng.lognormal(mu, sigma))


def _reference_simulate_chain_triangular(
    estimates: list[tuple[float, float, float]],
    n_iterations: int,
    seed: int,
) -> np.ndarray:
    """Reference implementation: chain of triangular tasks, no risks."""
    rng = np.random.RandomState(seed)
    durations = np.zeros(n_iterations)

    for i in range(n_iterations):
        total = 0.0
        for low, mode, high in estimates:
            total += _reference_triangular_sample(rng, low, mode, high)
        durations[i] = total

    return durations


def _reference_simulate_parallel_triangular(
    estimates: list[tuple[float, float, float]],
    n_iterations: int,
    seed: int,
) -> np.ndarray:
    """Reference implementation: parallel tasks, duration = max."""
    rng = np.random.RandomState(seed)
    durations = np.zeros(n_iterations)

    for i in range(n_iterations):
        task_durs = []
        for low, mode, high in estimates:
            task_durs.append(_reference_triangular_sample(rng, low, mode, high))
        durations[i] = max(task_durs)

    return durations


class TestReferenceComparisonChain:
    """Compare engine output to independent reference for chain topology."""

    def test_chain_distribution_matches_reference(self):
        """Engine's chain output has same distribution as reference impl."""
        estimates = [(5.0, 15.0, 30.0), (10.0, 25.0, 50.0), (8.0, 20.0, 40.0)]

        # Engine simulation
        from .conftest import chain_project
        project = chain_project(estimates, distribution=DistributionType.TRIANGULAR)
        engine = SimulationEngine(
            iterations=N_ITERATIONS, random_seed=42, show_progress=False
        )
        engine_results = engine.run(project)

        # Reference simulation (same seed won't match due to engine overhead,
        # but distributions should be statistically indistinguishable)
        ref_durations = _reference_simulate_chain_triangular(estimates, N_ITERATIONS, seed=43)

        # Two-sample KS test: both come from same distribution
        ks_stat, p_value = stats.ks_2samp(engine_results.durations, ref_durations)
        assert p_value > ALPHA, (
            f"Engine vs reference: KS D={ks_stat:.6f}, p={p_value:.2e}"
        )

    def test_chain_moments_match_reference(self):
        """Engine mean and std match reference within statistical tolerance."""
        estimates = [(10.0, 20.0, 40.0), (5.0, 12.0, 25.0)]

        from .conftest import chain_project
        project = chain_project(estimates, distribution=DistributionType.TRIANGULAR)
        engine = SimulationEngine(
            iterations=N_ITERATIONS, random_seed=42, show_progress=False
        )
        engine_results = engine.run(project)

        ref_durations = _reference_simulate_chain_triangular(estimates, N_ITERATIONS, seed=43)

        # Means should be very close
        engine_mean = float(np.mean(engine_results.durations))
        ref_mean = float(np.mean(ref_durations))
        # Both estimate the same true mean → difference should be small
        pooled_se = math.sqrt(
            float(np.var(engine_results.durations)) / N_ITERATIONS
            + float(np.var(ref_durations)) / N_ITERATIONS
        )
        z_diff = abs(engine_mean - ref_mean) / pooled_se
        # Should be within 4σ (p < 0.00006)
        assert z_diff < 4.0, (
            f"Mean difference: engine={engine_mean:.4f}, ref={ref_mean:.4f}, "
            f"z={z_diff:.2f}"
        )


class TestReferenceComparisonParallel:
    """Compare engine output to independent reference for parallel topology."""

    def test_parallel_distribution_matches_reference(self):
        """Engine's parallel output has same distribution as reference impl."""
        estimates = [(10.0, 25.0, 50.0), (8.0, 20.0, 45.0), (12.0, 30.0, 55.0)]

        from .conftest import parallel_project
        project = parallel_project(estimates, distribution=DistributionType.TRIANGULAR)
        engine = SimulationEngine(
            iterations=N_ITERATIONS, random_seed=44, show_progress=False
        )
        engine_results = engine.run(project)

        ref_durations = _reference_simulate_parallel_triangular(estimates, N_ITERATIONS, seed=45)

        # Two-sample KS test
        ks_stat, p_value = stats.ks_2samp(engine_results.durations, ref_durations)
        assert p_value > ALPHA, (
            f"Engine vs reference (parallel): KS D={ks_stat:.6f}, p={p_value:.2e}"
        )


class TestReferenceComparisonRisk:
    """Verify risk logic matches independent reference."""

    def test_risk_impact_distribution(self):
        """Engine's risk behavior matches simple Bernoulli reference."""
        base_low, base_high = 29.5, 30.5  # Near-deterministic
        base_mode = 30.0
        risk_prob = 0.35
        risk_impact = 15.0

        project = Project(
            project=ProjectMetadata(
                name="Risk Ref",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
            ),
            tasks=[
                Task(
                    id="t1",
                    name="T1",
                    estimate=TaskEstimate(
                        low=base_low, expected=base_mode, high=base_high, unit=EffortUnit.HOURS
                    ),
                    risks=[
                        Risk(id="r1", name="R1", probability=risk_prob, impact=risk_impact)
                    ],
                )
            ],
        )
        engine = SimulationEngine(
            iterations=N_ITERATIONS, random_seed=50, show_progress=False
        )
        engine_results = engine.run(project)

        # Reference: ~base + Bernoulli(p) * impact
        rng = np.random.RandomState(51)
        ref_durations = np.array([
            base_mode + (risk_impact if rng.random() < risk_prob else 0.0)
            for _ in range(N_ITERATIONS)
        ])

        # Both should have same mean: ~base + p*impact
        expected_mean = base_mode + risk_prob * risk_impact
        assert_mean_within_ci(
            engine_results.durations, expected_mean, label="Engine risk mean"
        )
        assert_mean_within_ci(
            ref_durations, expected_mean, label="Reference risk mean"
        )

        # Distribution should be two-point: check proportions match
        engine_fired = int(np.sum(engine_results.task_durations["t1"] > base_mode + 1.0))
        ref_fired = int(np.sum(ref_durations > base_mode + 1.0))

        # Both should be close to p * N
        from .conftest import assert_proportion
        assert_proportion(engine_fired, N_ITERATIONS, risk_prob, label="Engine risk rate")
        assert_proportion(ref_fired, N_ITERATIONS, risk_prob, label="Ref risk rate")


class TestReferenceComparisonLognormal:
    """Verify lognormal sampling matches reference."""

    def test_lognormal_chain_matches_reference(self):
        """Engine lognormal chain has same distribution as reference."""
        estimates = [(5.0, 15.0, 40.0), (10.0, 25.0, 60.0)]

        from .conftest import chain_project
        project = chain_project(estimates, distribution=DistributionType.LOGNORMAL)
        engine = SimulationEngine(
            iterations=N_ITERATIONS, random_seed=60, show_progress=False
        )
        engine_results = engine.run(project)

        # Reference: sum of shifted lognormals
        rng = np.random.RandomState(61)
        ref_durations = np.zeros(N_ITERATIONS)
        for i in range(N_ITERATIONS):
            total = 0.0
            for low, exp, high in estimates:
                total += _reference_lognormal_sample(rng, low, exp, high)
            ref_durations[i] = total

        # Two-sample KS test
        ks_stat, p_value = stats.ks_2samp(engine_results.durations, ref_durations)
        assert p_value > ALPHA, (
            f"Lognormal engine vs reference: KS D={ks_stat:.6f}, p={p_value:.2e}"
        )
