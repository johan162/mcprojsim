"""Category 7: Composition and scaling tests.

Verify monotonicity, percentile ordering, and scaling behaviour
when project parameters change.
"""

from __future__ import annotations

import numpy as np
import pytest

from mcprojsim.models.project import (
    Project,
    Risk,
    Task,
    TaskEstimate,
)

from .conftest import (
    STAT_ITERATIONS_CI,
    _meta,
    make_constrained_parallel_project,
    make_parallel_project,
    run_simulation,
)

pytestmark = pytest.mark.probabilistic


def _single_task(
    low: float = 10.0,
    expected: float = 30.0,
    high: float = 80.0,
    risks: list[Risk] | None = None,
) -> Project:
    return Project(
        project=_meta(name="SingleComp"),
        tasks=[
            Task(
                id="T",
                name="Task",
                estimate=TaskEstimate(low=low, expected=expected, high=high),
                risks=risks or [],
            ),
        ],
    )


# ------------------------------------------------------------------
# 7.1  Adding risk increases mean
# ------------------------------------------------------------------
class TestRiskIncreasesMean:
    """Projects with risks should have higher mean duration."""

    def test_risk_raises_mean(self):
        proj_no = _single_task()
        proj_risk = _single_task(
            risks=[Risk(id="R", name="Risk", probability=0.5, impact=40.0)]
        )

        res_no = run_simulation(proj_no, iterations=STAT_ITERATIONS_CI, seed=42)
        res_risk = run_simulation(proj_risk, iterations=STAT_ITERATIONS_CI, seed=42)

        assert res_risk.mean > res_no.mean, (
            f"COMPOSITION: mean with risk ({res_risk.mean:.2f}) should "
            f"exceed mean without ({res_no.mean:.2f}).  "
            f"SUGGESTION: Check risk application in the engine."
        )


# ------------------------------------------------------------------
# 7.2  Wider estimate increases variance
# ------------------------------------------------------------------
class TestWiderEstimateIncreasesVariance:
    """A wider [low, high] range should produce higher variance."""

    def test_variance_monotonicity(self):
        proj_narrow = _single_task(low=25.0, expected=30.0, high=40.0)
        proj_wide = _single_task(low=5.0, expected=30.0, high=150.0)

        res_narrow = run_simulation(proj_narrow, iterations=STAT_ITERATIONS_CI, seed=42)
        res_wide = run_simulation(proj_wide, iterations=STAT_ITERATIONS_CI, seed=42)

        var_narrow = float(np.var(res_narrow.durations))
        var_wide = float(np.var(res_wide.durations))

        assert var_wide > var_narrow, (
            f"COMPOSITION: wider estimate var={var_wide:.2f} should "
            f"exceed narrow var={var_narrow:.2f}."
        )


# ------------------------------------------------------------------
# 7.3  Uncertainty factor scaling
# ------------------------------------------------------------------
class TestUncertaintyMonotonicity:
    """Applying larger uncertainty factors should increase mean."""

    def test_higher_uncertainty_higher_mean(self):
        from mcprojsim.models.project import UncertaintyFactors

        proj_base = _single_task()
        proj_unc = Project(
            project=_meta(name="UncComp"),
            tasks=[
                Task(
                    id="T",
                    name="Task",
                    estimate=TaskEstimate(low=10.0, expected=30.0, high=80.0),
                    uncertainty_factors=UncertaintyFactors(
                        technical_complexity="high",
                        requirements_maturity="low",
                        team_experience="low",
                    ),
                ),
            ],
        )

        res_base = run_simulation(proj_base, iterations=STAT_ITERATIONS_CI, seed=42)
        res_unc = run_simulation(proj_unc, iterations=STAT_ITERATIONS_CI, seed=42)

        assert res_unc.mean > res_base.mean * 1.1, (
            f"UNCERTAINTY SCALING: high-uncertainty mean ({res_unc.mean:.2f}) "
            f"should significantly exceed base mean ({res_base.mean:.2f})."
        )


# ------------------------------------------------------------------
# 7.4  Percentile ordering
# ------------------------------------------------------------------
class TestPercentileOrdering:
    """P10 ≤ P25 ≤ P50 ≤ P75 ≤ P90 for any project."""

    def test_ordered_percentiles(self):
        proj = _single_task()
        results = run_simulation(proj, iterations=STAT_ITERATIONS_CI, seed=42)

        pcts = [10, 25, 50, 75, 90]
        vals = [float(np.percentile(results.durations, p)) for p in pcts]

        for i in range(len(vals) - 1):
            assert vals[i] <= vals[i + 1] + 1e-9, (
                f"PERCENTILE ORDER: P{pcts[i]}={vals[i]:.2f} > "
                f"P{pcts[i+1]}={vals[i+1]:.2f}."
            )


# ------------------------------------------------------------------
# 7.5  P50 ≈ median
# ------------------------------------------------------------------
class TestP50IsMedian:
    """P50 should equal the numpy median of simulation results."""

    def test_p50_equals_median(self):
        proj = _single_task()
        results = run_simulation(proj, iterations=STAT_ITERATIONS_CI, seed=42)

        p50 = float(np.percentile(results.durations, 50))
        median = float(np.median(results.durations))

        assert abs(p50 - median) < 1e-9, f"P50={p50:.6f} ≠ median={median:.6f}."


# ------------------------------------------------------------------
# 7.6  Adding tasks increases duration
# ------------------------------------------------------------------
class TestAddingTasksIncreasesDuration:
    """Adding tasks to a chain should increase mean duration."""

    def test_longer_chain_longer_duration(self):
        from .conftest import make_chain_project

        proj_short = make_chain_project(n_tasks=2)
        proj_long = make_chain_project(n_tasks=6)

        res_short = run_simulation(proj_short, iterations=STAT_ITERATIONS_CI, seed=42)
        res_long = run_simulation(proj_long, iterations=STAT_ITERATIONS_CI, seed=42)

        assert res_long.mean > res_short.mean, (
            f"COMPOSITION: 6-task chain mean ({res_long.mean:.2f}) should "
            f"exceed 2-task chain mean ({res_short.mean:.2f})."
        )


# ------------------------------------------------------------------
# 7.7  Higher risk probability increases mean more
# ------------------------------------------------------------------
class TestRiskProbabilityScaling:
    """Higher P(risk) should yield higher mean duration."""

    def test_higher_prob_higher_mean(self):
        proj_low = _single_task(
            risks=[Risk(id="R", name="R", probability=0.1, impact=50.0)]
        )
        proj_high = _single_task(
            risks=[Risk(id="R", name="R", probability=0.8, impact=50.0)]
        )

        res_low = run_simulation(proj_low, iterations=STAT_ITERATIONS_CI, seed=42)
        res_high = run_simulation(proj_high, iterations=STAT_ITERATIONS_CI, seed=42)

        assert res_high.mean > res_low.mean, (
            f"RISK SCALING: high-prob mean ({res_high.mean:.2f}) should "
            f"exceed low-prob mean ({res_low.mean:.2f})."
        )


# ------------------------------------------------------------------
# 7.8  More resources reduces constrained duration
# ------------------------------------------------------------------
class TestMoreResourcesReducesDuration:
    """Adding more resources to a constrained parallel project should
    reduce (or at least not increase) mean duration.
    """

    def test_more_resources_faster(self):
        proj_2 = make_constrained_parallel_project(n_parallel=6, n_resources=2)
        proj_4 = make_constrained_parallel_project(n_parallel=6, n_resources=4)

        res_2 = run_simulation(proj_2, iterations=STAT_ITERATIONS_CI, seed=42)
        res_4 = run_simulation(proj_4, iterations=STAT_ITERATIONS_CI, seed=42)

        assert res_4.mean <= res_2.mean + 1.0, (
            f"RESOURCE SCALING: 4-resource mean ({res_4.mean:.2f}) should "
            f"not exceed 2-resource mean ({res_2.mean:.2f}). "
            f"More resources should reduce contention."
        )


# ------------------------------------------------------------------
# 7.9  Effort percentile ordering
# ------------------------------------------------------------------
class TestEffortPercentileOrdering:
    """Effort percentiles should be non-decreasing."""

    def test_effort_percentiles_ordered(self):
        proj = make_parallel_project(n_parallel=5)
        results = run_simulation(proj, iterations=STAT_ITERATIONS_CI, seed=42)

        pcts = [10, 25, 50, 75, 90]
        vals = [float(np.percentile(results.effort_durations, p)) for p in pcts]

        for i in range(len(vals) - 1):
            assert vals[i] <= vals[i + 1] + 1e-9, (
                f"EFFORT PERCENTILE ORDER: P{pcts[i]}={vals[i]:.2f} > "
                f"P{pcts[i+1]}={vals[i+1]:.2f}."
            )


# ------------------------------------------------------------------
# 7.10  Parallel benefit: duration < effort for parallel projects
# ------------------------------------------------------------------
class TestParallelBenefit:
    """Parallel tasks: mean duration < mean effort (parallelism
    reduces elapsed time vs total effort).
    """

    def test_duration_less_than_effort(self):
        proj = make_parallel_project(n_parallel=5)
        results = run_simulation(proj, iterations=STAT_ITERATIONS_CI, seed=42)

        assert results.mean < float(np.mean(results.effort_durations)), (
            f"PARALLEL BENEFIT: mean duration ({results.mean:.2f}) should "
            f"be less than mean effort "
            f"({float(np.mean(results.effort_durations)):.2f})."
        )
