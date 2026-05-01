"""Test 4: Risk impact validation.

These tests verify that:
- Risks fire at their stated probability
- Risk impacts are correctly added to task durations
- Cost impacts correlate with time impacts (same trigger roll)
- Multiple risks on a task combine correctly
"""

from __future__ import annotations

import numpy as np
import pytest

from mcprojsim.config import EffortUnit
from mcprojsim.models.project import (
    DistributionType,
    Project,
    ProjectMetadata,
    Risk,
    RiskImpact,
    Task,
    TaskEstimate,
)

from .conftest import (
    N_ITERATIONS,
    START_DATE,
    assert_mean_within_ci,
    assert_proportion,
    run_sim,
    single_task_project,
    triangular_mean,
)

# numpy triangular requires left < right; use tiny spread for "deterministic"
EPS = 0.001


def _det_estimate(
    value: float,
) -> TaskEstimate:
    return TaskEstimate(
        low=value - EPS, expected=value, high=value + EPS, unit=EffortUnit.HOURS
    )


class TestRiskTriggerProbability:
    """Risk fires at exactly the stated probability."""

    @pytest.mark.parametrize("prob", [0.1, 0.25, 0.5, 0.75, 0.9])
    def test_risk_trigger_rate(self, prob: float):
        """Count iterations where risk fired and verify against binomial."""
        base_duration = 20.0  # Near-deterministic task
        risk_impact = 10.0

        project = Project(
            project=ProjectMetadata(
                name="Risk Rate",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
            ),
            tasks=[
                Task(
                    id="t1",
                    name="Task 1",
                    estimate=_det_estimate(base_duration),
                    risks=[
                        Risk(
                            id="r1",
                            name="Risk 1",
                            probability=prob,
                            impact=risk_impact,
                        )
                    ],
                )
            ],
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=42)

        # Task duration is either ~base_duration or ~base_duration + risk_impact
        samples = results.task_durations["t1"]
        fired_count = int(np.sum(samples > base_duration + 0.1))

        assert_proportion(
            fired_count,
            N_ITERATIONS,
            prob,
            label=f"Risk p={prob}",
        )

    def test_risk_never_fires_at_zero(self):
        """Risk with probability=0 never fires."""
        project = Project(
            project=ProjectMetadata(
                name="No Risk",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
            ),
            tasks=[
                Task(
                    id="t1",
                    name="Task 1",
                    estimate=_det_estimate(20.0),
                    risks=[Risk(id="r1", name="Never", probability=0.0, impact=100.0)],
                )
            ],
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=50)
        # No risk fires, all values close to 20
        assert np.all(np.abs(results.task_durations["t1"] - 20.0) <= EPS)

    def test_risk_always_fires_at_one(self):
        """Risk with probability=1 always fires."""
        project = Project(
            project=ProjectMetadata(
                name="Always Risk",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
            ),
            tasks=[
                Task(
                    id="t1",
                    name="Task 1",
                    estimate=_det_estimate(20.0),
                    risks=[Risk(id="r1", name="Always", probability=1.0, impact=15.0)],
                )
            ],
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=51)
        # Every iteration: ~20 + 15 = ~35
        assert np.all(np.abs(results.task_durations["t1"] - 35.0) <= EPS)


class TestRiskImpactOnMean:
    """Risk impacts shift the mean duration by p * impact."""

    def test_mean_shift_from_risk(self):
        """E[duration] = E[base] + probability * impact for absolute risk."""
        base_low, base_mode, base_high = 10.0, 20.0, 30.0
        risk_prob = 0.4
        risk_impact = 12.0

        project = single_task_project(
            base_low,
            base_mode,
            base_high,
            distribution=DistributionType.TRIANGULAR,
            risks=[Risk(id="r1", name="R1", probability=risk_prob, impact=risk_impact)],
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=60)

        expected_mean = (
            triangular_mean(base_low, base_mode, base_high) + risk_prob * risk_impact
        )
        assert_mean_within_ci(
            results.task_durations["t1"], expected_mean, label="Mean with risk"
        )

    def test_two_independent_risks_mean(self):
        """Two risks: E[duration] = E[base] + p1*i1 + p2*i2."""
        base = 20.0  # Near-deterministic
        p1, i1 = 0.3, 10.0
        p2, i2 = 0.5, 8.0

        project = Project(
            project=ProjectMetadata(
                name="Two Risks",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
            ),
            tasks=[
                Task(
                    id="t1",
                    name="Task 1",
                    estimate=_det_estimate(base),
                    risks=[
                        Risk(id="r1", name="R1", probability=p1, impact=i1),
                        Risk(id="r2", name="R2", probability=p2, impact=i2),
                    ],
                )
            ],
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=61)

        expected_mean = base + p1 * i1 + p2 * i2
        assert_mean_within_ci(
            results.task_durations["t1"], expected_mean, label="Two risks mean"
        )


class TestRiskImpactVariance:
    """Risk triggers add variance to the duration distribution."""

    def test_bernoulli_risk_variance(self):
        """Near-deterministic task + single risk: Var ≈ p*(1-p)*impact^2."""
        base = 50.0
        prob = 0.3
        impact = 20.0

        project = Project(
            project=ProjectMetadata(
                name="Risk Var",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
            ),
            tasks=[
                Task(
                    id="t1",
                    name="Task 1",
                    estimate=_det_estimate(base),
                    risks=[Risk(id="r1", name="R1", probability=prob, impact=impact)],
                )
            ],
        )
        results = run_sim(project, iterations=N_ITERATIONS, seed=70)

        # Duration is: ~base + Bernoulli(p) * impact
        # Var ≈ p * (1-p) * impact^2 (tiny base variance negligible)
        expected_var = prob * (1 - prob) * impact**2
        samples = results.task_durations["t1"]
        obs_var = float(np.var(samples, ddof=1))

        # Check variance is close (relative tolerance since base adds tiny noise)
        assert (
            abs(obs_var - expected_var) / expected_var < 0.05
        ), f"observed_var={obs_var:.4f}, expected_var={expected_var:.4f}"


class TestPercentageRiskImpact:
    """Percentage-based risk impacts are correctly computed."""

    def test_percentage_risk_impact(self):
        """Percentage risk: impact = fraction * base_duration."""
        base = 40.0  # Near-deterministic
        prob = 1.0  # Always fires for easy verification
        pct = 25  # 25% increase (value is in percent)

        project = Project(
            project=ProjectMetadata(
                name="Pct Risk",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
            ),
            tasks=[
                Task(
                    id="t1",
                    name="Task 1",
                    estimate=_det_estimate(base),
                    risks=[
                        Risk(
                            id="r1",
                            name="R1",
                            probability=prob,
                            impact=RiskImpact(type="percentage", value=pct),
                        )
                    ],
                )
            ],
        )
        results = run_sim(project, iterations=1000, seed=80)
        # Expected: ~base + 25% of ~base ≈ 50
        expected = base * (1 + pct / 100.0)
        assert np.all(np.abs(results.task_durations["t1"] - expected) < 0.1)


class TestRiskOnProjectDuration:
    """Risk impacts propagate to project-level duration correctly."""

    def test_risk_on_critical_path_affects_project(self):
        """A risk on the critical-path task increases project duration mean."""
        # Chain: t1(~10) → t2(~20, risk p=1 impact=15) → t3(~10)
        # Project duration without risk: ~40, with risk (always): ~55
        project = Project(
            project=ProjectMetadata(
                name="CP Risk",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
            ),
            tasks=[
                Task(
                    id="t1",
                    name="T1",
                    estimate=_det_estimate(10.0),
                ),
                Task(
                    id="t2",
                    name="T2",
                    estimate=_det_estimate(20.0),
                    dependencies=["t1"],
                    risks=[Risk(id="r1", name="R", probability=1.0, impact=15.0)],
                ),
                Task(
                    id="t3",
                    name="T3",
                    estimate=_det_estimate(10.0),
                    dependencies=["t2"],
                ),
            ],
        )
        results = run_sim(project, iterations=500, seed=81)
        assert np.all(np.abs(results.durations - 55.0) <= 4 * EPS)

    def test_risk_on_noncritical_path_mostly_irrelevant(self):
        """A risk on a non-critical task rarely affects project duration."""
        # Parallel: t1(~100) and t2(~10, risk p=0.5 impact=5)
        # t1 is always critical since 100 >> 10+5=15
        project = Project(
            project=ProjectMetadata(
                name="NC Risk",
                start_date=START_DATE,
                hours_per_day=8.0,
                distribution=DistributionType.TRIANGULAR,
            ),
            tasks=[
                Task(
                    id="t1",
                    name="T1",
                    estimate=_det_estimate(100.0),
                ),
                Task(
                    id="t2",
                    name="T2",
                    estimate=_det_estimate(10.0),
                    risks=[Risk(id="r1", name="R", probability=0.5, impact=5.0)],
                ),
            ],
        )
        results = run_sim(project, iterations=1000, seed=82)
        # Project duration should always be ~100 (t1 dominates even if t2 risk fires)
        assert np.all(np.abs(results.durations - 100.0) <= EPS)
