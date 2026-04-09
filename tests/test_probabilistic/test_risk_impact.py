"""Category 4: Risk impact proportionality tests.

Verify that the risk evaluation system correctly applies probabilistic
impacts with the declared probability and magnitude.
"""

from __future__ import annotations

import numpy as np
import pytest

from mcprojsim.models.project import (
    ImpactType,
    Risk,
    RiskImpact,
)

from .conftest import (
    STAT_ITERATIONS_CI,
    STAT_ITERATIONS_FULL,
    assert_proportion_close,
    make_chain_project,
    make_single_task_project,
    run_simulation,
)

pytestmark = pytest.mark.probabilistic


# ------------------------------------------------------------------
# 4.1  Risk trigger rate matches declared probability
# ------------------------------------------------------------------
class TestRiskTriggerRate:
    """A risk with probability p should trigger in ~p×N iterations."""

    @pytest.mark.probabilistic_full
    def test_trigger_rate_30_percent(self):
        probability = 0.30
        project = make_single_task_project(
            low=10.0,
            expected=30.0,
            high=80.0,
            risks=[
                Risk(
                    id="r1",
                    name="Test Risk",
                    probability=probability,
                    impact=100.0,
                )
            ],
        )
        results = run_simulation(project, iterations=STAT_ITERATIONS_FULL, seed=42)
        impacts = results.risk_impacts["t1"]
        trigger_count = int(np.sum(impacts > 0))

        assert_proportion_close(
            trigger_count,
            len(impacts),
            probability,
            label="Risk trigger rate (p=0.30)",
        )

    @pytest.mark.probabilistic_full
    def test_trigger_rate_70_percent(self):
        probability = 0.70
        project = make_single_task_project(
            low=10.0,
            expected=30.0,
            high=80.0,
            risks=[
                Risk(
                    id="r1",
                    name="Test Risk",
                    probability=probability,
                    impact=50.0,
                )
            ],
        )
        results = run_simulation(project, iterations=STAT_ITERATIONS_FULL, seed=42)
        impacts = results.risk_impacts["t1"]
        trigger_count = int(np.sum(impacts > 0))

        assert_proportion_close(
            trigger_count,
            len(impacts),
            probability,
            label="Risk trigger rate (p=0.70)",
        )


# ------------------------------------------------------------------
# 4.2  Absolute risk impact is exact when triggered
# ------------------------------------------------------------------
class TestAbsoluteRiskImpact:
    """Absolute risk impact should be exactly the declared value."""

    def test_absolute_impact_exact_with_p1(self):
        impact_hours = 40.0
        project = make_single_task_project(
            low=10.0,
            expected=30.0,
            high=80.0,
            risks=[
                Risk(
                    id="r1",
                    name="Certain Risk",
                    probability=1.0,
                    impact=impact_hours,
                )
            ],
        )
        results = run_simulation(project, iterations=200, seed=42)
        impacts = results.risk_impacts["t1"]

        assert np.allclose(impacts, impact_hours, atol=1e-6), (
            f"ABSOLUTE RISK IMPACT MISMATCH: expected all impacts = "
            f"{impact_hours}, got range "
            f"[{float(impacts.min()):.6f}, {float(impacts.max()):.6f}]. "
            f"SUGGESTION: Check RiskEvaluator.evaluate_risk — for p=1.0 "
            f"absolute impact, every iteration should add exactly "
            f"{impact_hours} hours."
        )


# ------------------------------------------------------------------
# 4.3  Percentage risk impact proportional to base duration
# ------------------------------------------------------------------
class TestPercentageRiskImpact:
    """A percentage risk should add base_duration × (value/100)."""

    def test_percentage_impact_proportional(self):
        pct = 25.0
        project = make_single_task_project(
            low=10.0,
            expected=30.0,
            high=80.0,
            risks=[
                Risk(
                    id="r1",
                    name="Percentage Risk",
                    probability=1.0,
                    impact=RiskImpact(type=ImpactType.PERCENTAGE, value=pct),
                )
            ],
        )
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        task_durations = results.task_durations["t1"]
        impacts = results.risk_impacts["t1"]

        # final_duration = base + impact, where impact = base * pct/100
        # => base = final / (1 + pct/100)
        base_durations = task_durations / (1.0 + pct / 100.0)
        expected_impacts = base_durations * (pct / 100.0)

        assert np.allclose(impacts, expected_impacts, rtol=1e-4), (
            f"PERCENTAGE RISK NOT PROPORTIONAL: "
            f"max |impact - expected| = "
            f"{float(np.max(np.abs(impacts - expected_impacts))):.6f}. "
            f"SUGGESTION: Check RiskImpact.get_impact_value for "
            f"type='percentage' — should return base_duration * value/100."
        )


# ------------------------------------------------------------------
# 4.4  Mean duration increase from risk ≈ p × I
# ------------------------------------------------------------------
class TestRiskMeanIncrease:
    """Adding a risk with probability p and absolute impact I increases
    mean task duration by approximately p × I.
    """

    @pytest.mark.probabilistic_full
    def test_mean_increase_matches_expected_value(self):
        p, impact = 0.40, 50.0
        expected_increase = p * impact

        project_no_risk = make_single_task_project(low=20.0, expected=40.0, high=80.0)
        project_with_risk = make_single_task_project(
            low=20.0,
            expected=40.0,
            high=80.0,
            risks=[
                Risk(
                    id="r1",
                    name="Test Risk",
                    probability=p,
                    impact=impact,
                )
            ],
        )

        # Use different seeds because risk evaluation changes RNG state
        results_no = run_simulation(
            project_no_risk, iterations=STAT_ITERATIONS_FULL, seed=42
        )
        results_yes = run_simulation(
            project_with_risk, iterations=STAT_ITERATIONS_FULL, seed=99
        )

        mean_no = float(np.mean(results_no.task_durations["t1"]))
        mean_yes = float(np.mean(results_yes.task_durations["t1"]))
        observed_increase = mean_yes - mean_no

        # Use a generous tolerance because different seeds produce
        # different base samples; we check the increase is close to p*I
        rel_error = abs(observed_increase - expected_increase) / expected_increase
        assert rel_error < 0.15, (
            f"RISK MEAN INCREASE ERROR: "
            f"observed_increase={observed_increase:.2f}, "
            f"expected_increase (p×I)={expected_increase:.2f}, "
            f"rel_error={rel_error:.2%}. "
            f"SUGGESTION: Check that risk impacts are correctly added "
            f"to task durations in the simulation loop."
        )


# ------------------------------------------------------------------
# 4.5  Multiple risk accumulation
# ------------------------------------------------------------------
class TestMultipleRiskAccumulation:
    """Multiple risks on a single task should accumulate independently."""

    def test_two_risks_accumulate(self):
        """Two certain risks with known impacts should add up."""
        project = make_single_task_project(
            low=10.0,
            expected=30.0,
            high=80.0,
            risks=[
                Risk(
                    id="r1",
                    name="Risk 1",
                    probability=1.0,
                    impact=20.0,
                ),
                Risk(
                    id="r2",
                    name="Risk 2",
                    probability=1.0,
                    impact=30.0,
                ),
            ],
        )
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)
        impacts = results.risk_impacts["t1"]

        # Both risks always trigger, so total impact should be 50.0
        assert np.allclose(impacts, 50.0, atol=0.01), (
            f"MULTI-RISK ACCUMULATION: expected total impact 50.0 in "
            f"every iteration, got mean={float(np.mean(impacts)):.4f}, "
            f"std={float(np.std(impacts)):.4f}. "
            f"SUGGESTION: Check that multiple risks on a single task "
            f"accumulate additively."
        )

    @pytest.mark.probabilistic_full
    def test_mixed_probability_risks_mean(self):
        """Multiple probabilistic risks: mean impact ≈ Σ(p_i × I_i)."""
        p1, i1 = 0.3, 40.0
        p2, i2 = 0.6, 20.0
        expected_mean_impact = p1 * i1 + p2 * i2  # 12 + 12 = 24

        project = make_single_task_project(
            low=10.0,
            expected=30.0,
            high=80.0,
            risks=[
                Risk(id="r1", name="R1", probability=p1, impact=i1),
                Risk(id="r2", name="R2", probability=p2, impact=i2),
            ],
        )
        results = run_simulation(project, iterations=STAT_ITERATIONS_FULL, seed=42)
        impacts = results.risk_impacts["t1"]
        observed_mean = float(np.mean(impacts))

        rel_error = abs(observed_mean - expected_mean_impact) / expected_mean_impact
        assert rel_error < 0.10, (
            f"MULTI-RISK MEAN: observed={observed_mean:.2f}, "
            f"expected Σ(p·I)={expected_mean_impact:.2f}, "
            f"rel_error={rel_error:.2%}. "
            f"SUGGESTION: Check that each risk is evaluated independently."
        )


# ------------------------------------------------------------------
# 4.6  Zero-probability risk has no effect
# ------------------------------------------------------------------
class TestZeroProbabilityRisk:
    """Risk with p=0 should never trigger."""

    def test_zero_prob_no_impact(self):
        project = make_single_task_project(
            low=10.0,
            expected=30.0,
            high=80.0,
            risks=[
                Risk(
                    id="r1",
                    name="Impossible Risk",
                    probability=0.0,
                    impact=1000.0,
                )
            ],
        )
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)
        impacts = results.risk_impacts["t1"]

        trigger_count = int(np.sum(impacts > 0))
        assert trigger_count == 0, (
            f"ZERO-PROBABILITY RISK TRIGGERED: {trigger_count} times. "
            f"SUGGESTION: Check RiskEvaluator probability comparison — "
            f"a risk with p=0.0 should never trigger."
        )


# ------------------------------------------------------------------
# 4.6  Certain risk always triggers
# ------------------------------------------------------------------
class TestCertainRisk:
    """Risk with p=1.0 should trigger in every iteration."""

    def test_certain_risk_always_triggers(self):
        project = make_single_task_project(
            low=10.0,
            expected=30.0,
            high=80.0,
            risks=[
                Risk(
                    id="r1",
                    name="Certain Risk",
                    probability=1.0,
                    impact=25.0,
                )
            ],
        )
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)
        impacts = results.risk_impacts["t1"]

        non_triggered = int(np.sum(impacts == 0))
        assert non_triggered == 0, (
            f"CERTAIN RISK DID NOT TRIGGER: missed {non_triggered} "
            f"iterations.  SUGGESTION: Check RiskEvaluator — p=1.0 "
            f"should always trigger."
        )


# ------------------------------------------------------------------
# 4.7  Project-level risk adds to project duration
# ------------------------------------------------------------------
class TestProjectLevelRisk:
    """Project-level risks should shift the project duration distribution."""

    def test_project_risk_increases_mean(self):
        project_no = make_chain_project(n_tasks=3)
        project_yes = make_chain_project(n_tasks=3)
        project_yes.project_risks = [
            Risk(
                id="pr1",
                name="Project Risk",
                probability=1.0,
                impact=100.0,
            ),
        ]

        results_no = run_simulation(project_no, iterations=STAT_ITERATIONS_CI, seed=42)
        results_yes = run_simulation(
            project_yes, iterations=STAT_ITERATIONS_CI, seed=42
        )

        # With p=1.0 impact=100h, mean should increase by exactly 100h
        increase = results_yes.mean - results_no.mean
        assert abs(increase - 100.0) < 1.0, (
            f"PROJECT RISK MEAN INCREASE: expected ~100h, "
            f"got {increase:.2f}h. "
            f"SUGGESTION: Check that project-level risks are applied "
            f"to the final project duration in _run_iteration."
        )
