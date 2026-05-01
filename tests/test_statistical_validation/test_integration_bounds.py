"""Test 9: End-to-end integration validation with known analytical bounds.

These tests construct complete projects where we can compute tight analytical
bounds on the result distribution, then verify the simulation honors them.
This catches integration bugs where individual components are correct but
their composition is wrong.
"""

from __future__ import annotations

import math

import numpy as np

from mcprojsim.config import EffortUnit
from mcprojsim.models.project import (
    DistributionType,
    Project,
    ProjectMetadata,
    Risk,
    Task,
    TaskEstimate,
)

from .conftest import (
    N_ITERATIONS,
    START_DATE,
    assert_mean_within_ci,
    run_sim,
    triangular_mean,
    triangular_variance,
)

# numpy triangular requires left < right; use tiny spread for "deterministic"
EPS = 0.001


def _det_estimate(value: float) -> TaskEstimate:
    return TaskEstimate(
        low=value - EPS, expected=value, high=value + EPS, unit=EffortUnit.HOURS
    )


class TestAnalyticalBoundsChain:
    """Known bounds for sequential chains of triangular tasks."""

    def test_chebyshev_bound_holds(self):
        """P(|X - μ| ≥ kσ) ≤ 1/k² (Chebyshev) should hold empirically."""
        estimates = [(5.0, 15.0, 30.0), (10.0, 25.0, 50.0), (8.0, 20.0, 40.0)]
        from .conftest import chain_project

        project = chain_project(estimates, distribution=DistributionType.TRIANGULAR)
        results = run_sim(project, iterations=N_ITERATIONS, seed=700)

        mu = sum(triangular_mean(*e) for e in estimates)
        var = sum(triangular_variance(*e) for e in estimates)
        sigma = math.sqrt(var)

        # For k=3: P(|X-μ| ≥ 3σ) ≤ 1/9 ≈ 0.111
        k = 3
        violations = int(np.sum(np.abs(results.durations - mu) >= k * sigma))
        obs_rate = violations / N_ITERATIONS

        assert obs_rate <= 1 / k**2 + 0.01, (
            f"Chebyshev violation: P(|X-μ| ≥ {k}σ) = {obs_rate:.4f}, "
            f"bound = {1/k**2:.4f}"
        )

    def test_markov_bound_holds(self):
        """P(X ≥ a) ≤ E[X]/a (Markov) for non-negative durations."""
        estimates = [(10.0, 20.0, 40.0), (5.0, 15.0, 30.0)]
        from .conftest import chain_project

        project = chain_project(estimates, distribution=DistributionType.TRIANGULAR)
        results = run_sim(project, iterations=N_ITERATIONS, seed=701)

        mu = sum(triangular_mean(*e) for e in estimates)
        # Test at a = 2μ
        a = 2 * mu
        violations = int(np.sum(results.durations >= a))
        obs_rate = violations / N_ITERATIONS

        markov_bound = mu / a  # = 0.5
        assert obs_rate <= markov_bound + 0.01, (
            f"Markov violation: P(X ≥ {a:.1f}) = {obs_rate:.4f}, "
            f"bound = {markov_bound:.4f}"
        )


class TestAnalyticalBoundsParallel:
    """Known bounds for max of parallel tasks."""

    def test_max_always_ge_each_task(self):
        """Project duration ≥ every individual task duration (every iteration)."""
        from .conftest import parallel_project

        estimates = [(5.0, 15.0, 30.0), (10.0, 25.0, 50.0), (8.0, 20.0, 40.0)]
        project = parallel_project(estimates)
        results = run_sim(project, iterations=N_ITERATIONS, seed=702)

        for i, tid in enumerate(["t1", "t2", "t3"]):
            diffs = results.durations - results.task_durations[tid]
            assert np.all(
                diffs >= -1e-9
            ), f"Project duration < task {tid} in some iteration"

    def test_max_bounded_by_sum(self):
        """max(T1,...,Tn) ≤ T1 + T2 + ... + Tn always."""
        from .conftest import parallel_project

        estimates = [(5.0, 15.0, 30.0), (10.0, 25.0, 50.0), (8.0, 20.0, 40.0)]
        project = parallel_project(estimates)
        results = run_sim(project, iterations=N_ITERATIONS, seed=703)

        task_sum = sum(results.task_durations[f"t{i+1}"] for i in range(3))
        assert np.all(results.durations <= task_sum + 1e-9)


class TestUncertaintyMultiplierValidation:
    """Verify uncertainty multipliers scale durations correctly."""

    def test_no_uncertainty_gives_raw_distribution(self):
        """Default uncertainty factors for this config produce multiplier = 1.0.

        The default config has: team_experience=medium(1.0), requirements=high(1.0),
        tech_complexity=low(1.0), team_distribution=colocated(1.0),
        integration=low(1.0). Product = 1.0.
        """
        project = Project(
            project=ProjectMetadata(
                name="No Uncertainty",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
            ),
            tasks=[
                Task(
                    id="t1",
                    name="T1",
                    estimate=TaskEstimate(
                        low=10.0, expected=20.0, high=30.0, unit=EffortUnit.HOURS
                    ),
                )
            ],
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=710)

        # With default uncertainty (multiplier=1.0), mean = triangular mean
        expected_mean = triangular_mean(10.0, 20.0, 30.0)
        assert_mean_within_ci(
            results.task_durations["t1"], expected_mean, label="No uncertainty"
        )


class TestCostValidation:
    """Verify cost estimation integrates correctly with duration sampling."""

    def test_deterministic_cost_calculation(self):
        """With near-deterministic task and hourly rate, cost is near-exact."""
        project = Project(
            project=ProjectMetadata(
                name="Cost Det",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
                default_hourly_rate=100.0,
            ),
            tasks=[
                Task(
                    id="t1",
                    name="T1",
                    estimate=_det_estimate(40.0),
                )
            ],
        )
        results = run_sim(project, iterations=500, seed=720)

        # Cost ≈ hours * rate ≈ 40 * 100 = 4000
        assert results.costs is not None
        assert np.allclose(results.costs, 4000.0, atol=1.0)

    def test_cost_mean_with_stochastic_duration(self):
        """E[cost] = E[hours] * rate for a single task."""
        low, mode, high = 10.0, 25.0, 50.0
        rate = 150.0

        project = Project(
            project=ProjectMetadata(
                name="Cost Stoch",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
                default_hourly_rate=rate,
            ),
            tasks=[
                Task(
                    id="t1",
                    name="T1",
                    estimate=TaskEstimate(
                        low=low, expected=mode, high=high, unit=EffortUnit.HOURS
                    ),
                )
            ],
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=721)

        expected_cost_mean = triangular_mean(low, mode, high) * rate
        assert results.costs is not None
        assert_mean_within_ci(results.costs, expected_cost_mean, label="Cost mean")

    def test_risk_cost_impact_mean(self):
        """Risk with cost_impact: E[cost] includes probability * cost_impact."""
        base_hours = 20.0
        rate = 100.0
        risk_prob = 0.4
        cost_impact = 5000.0

        project = Project(
            project=ProjectMetadata(
                name="Risk Cost",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
                default_hourly_rate=rate,
            ),
            tasks=[
                Task(
                    id="t1",
                    name="T1",
                    estimate=_det_estimate(base_hours),
                    risks=[
                        Risk(
                            id="r1",
                            name="R1",
                            probability=risk_prob,
                            impact=10.0,  # 10 hours time impact
                            cost_impact=cost_impact,
                        )
                    ],
                )
            ],
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=722)

        # E[cost] = E[hours] * rate + p * cost_impact
        # E[hours] ≈ base + p * time_impact = 20 + 0.4 * 10 = 24
        expected_hours_mean = base_hours + risk_prob * 10.0
        expected_cost_mean = expected_hours_mean * rate + risk_prob * cost_impact
        assert results.costs is not None
        assert_mean_within_ci(results.costs, expected_cost_mean, label="Risk cost mean")


class TestSlackValidation:
    """Verify schedule slack calculations are correct."""

    def test_deterministic_parallel_slack(self):
        """In parallel tasks, shorter task has slack ≈ longer - shorter."""
        # t1: ~50 hours (long), t2: ~20 hours (short) → t2 slack ≈ 30
        project = Project(
            project=ProjectMetadata(
                name="Slack",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
            ),
            tasks=[
                Task(
                    id="t1",
                    name="T1 (long)",
                    estimate=_det_estimate(50.0),
                ),
                Task(
                    id="t2",
                    name="T2 (short)",
                    estimate=_det_estimate(20.0),
                ),
            ],
        )
        results = run_sim(project, iterations=500, seed=730)

        # t1 is critical → slack ≈ 0
        assert abs(results.task_slack["t1"]) < EPS
        # t2 has slack ≈ 50 - 20 = 30
        assert abs(results.task_slack["t2"] - 30.0) < 0.1

    def test_chain_zero_slack(self):
        """All tasks in a serial chain have zero slack."""
        from .conftest import chain_project

        estimates = [(9.0, 10.0, 11.0), (19.0, 20.0, 21.0), (14.0, 15.0, 16.0)]
        project = chain_project(estimates, distribution=DistributionType.TRIANGULAR)
        results = run_sim(project, iterations=5000, seed=731)

        for tid in ["t1", "t2", "t3"]:
            assert abs(results.task_slack[tid]) < 0.1


class TestLargeProjectConsistency:
    """Verify simulation consistency with a realistically-sized project."""

    def test_20_task_chain_moments(self):
        """Mean and variance of 20-task chain match analytical prediction."""
        rng = np.random.RandomState(42)
        estimates = []
        for _ in range(20):
            low = float(rng.uniform(5, 20))
            mode = float(rng.uniform(low + 1, low + 30))
            high = float(rng.uniform(mode + 1, mode + 40))
            estimates.append((low, mode, high))

        from .conftest import chain_project

        project = chain_project(estimates, distribution=DistributionType.TRIANGULAR)
        results = run_sim(project, iterations=N_ITERATIONS, seed=740)

        expected_mean = sum(triangular_mean(*e) for e in estimates)
        expected_var = sum(triangular_variance(*e) for e in estimates)

        assert_mean_within_ci(
            results.durations, expected_mean, label="20-task chain mean"
        )
        from .conftest import assert_variance_within_ci

        assert_variance_within_ci(
            results.durations, expected_var, label="20-task chain variance"
        )

    def test_10_parallel_tasks_mean_bound(self):
        """E[max of 10 tasks] lies between max(means) and sum(means)."""
        estimates = [
            (5.0, 15.0, 30.0),
            (10.0, 20.0, 40.0),
            (8.0, 18.0, 35.0),
            (3.0, 10.0, 25.0),
            (12.0, 25.0, 50.0),
            (7.0, 14.0, 28.0),
            (6.0, 12.0, 24.0),
            (9.0, 22.0, 45.0),
            (4.0, 11.0, 22.0),
            (15.0, 30.0, 60.0),
        ]
        from .conftest import parallel_project

        project = parallel_project(estimates, distribution=DistributionType.TRIANGULAR)
        results = run_sim(project, iterations=N_ITERATIONS, seed=741)

        means = [triangular_mean(*e) for e in estimates]
        obs_mean = float(np.mean(results.durations))

        # max(individual means) ≤ E[max] ≤ sum(means) [loose upper bound]
        assert obs_mean >= max(means) - 1.0
        assert obs_mean <= sum(means) + 1.0
