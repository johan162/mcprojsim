"""Category 6: Sensitivity and correlation tests.

Verify that Spearman correlation-based sensitivity analysis correctly
identifies which tasks dominate schedule variance.
"""

from __future__ import annotations

import pytest

from mcprojsim.analysis.sensitivity import SensitivityAnalyzer
from mcprojsim.models.project import (
    Project,
    Task,
    TaskEstimate,
)

from .conftest import (
    STAT_ITERATIONS_CI,
    _meta,
    make_chain_project,
    make_diamond_project,
    make_parallel_project,
    run_simulation,
)

pytestmark = pytest.mark.probabilistic


def _make_one_dominant_project() -> Project:
    """3 parallel tasks: one very noisy, two nearly deterministic."""
    return Project(
        project=_meta(name="DominantSensitivity"),
        tasks=[
            Task(
                id="big",
                name="Dominant task",
                estimate=TaskEstimate(low=10.0, expected=50.0, high=200.0),
            ),
            Task(
                id="tiny1",
                name="Near-deterministic 1",
                estimate=TaskEstimate(low=9.5, expected=10.0, high=10.5),
            ),
            Task(
                id="tiny2",
                name="Near-deterministic 2",
                estimate=TaskEstimate(low=9.5, expected=10.0, high=10.5),
            ),
        ],
    )


def _make_chain_with_zero_variance_task() -> Project:
    """Chain where one task is nearly deterministic (tiny spread)."""
    return Project(
        project=_meta(name="ZeroVarChain"),
        tasks=[
            Task(
                id="A",
                name="Variable task",
                estimate=TaskEstimate(low=10.0, expected=30.0, high=80.0),
            ),
            Task(
                id="B",
                name="Near-deterministic task",
                estimate=TaskEstimate(low=19.99, expected=20.0, high=20.01),
                dependencies=["A"],
            ),
            Task(
                id="C",
                name="Variable task 2",
                estimate=TaskEstimate(low=5.0, expected=15.0, high=40.0),
                dependencies=["B"],
            ),
        ],
    )


# ------------------------------------------------------------------
# 6.1  Dominant task has highest correlation
# ------------------------------------------------------------------
class TestDominantSensitivity:
    """When one task is vastly more variable, it should have the
    highest absolute Spearman correlation.
    """

    def test_most_variable_task_dominates(self):
        project = _make_one_dominant_project()
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        correlations = SensitivityAnalyzer.calculate_correlations(results)
        big_corr = abs(correlations["big"])
        tiny1_corr = abs(correlations.get("tiny1", 0))
        tiny2_corr = abs(correlations.get("tiny2", 0))

        assert big_corr > tiny1_corr, (
            f"SENSITIVITY: dominant task corr={big_corr:.3f} should "
            f"exceed tiny1 corr={tiny1_corr:.3f}."
        )
        assert big_corr > tiny2_corr, (
            f"SENSITIVITY: dominant task corr={big_corr:.3f} should "
            f"exceed tiny2 corr={tiny2_corr:.3f}."
        )

    def test_top_contributor_is_dominant(self):
        project = _make_one_dominant_project()
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)
        top = SensitivityAnalyzer.get_top_contributors(results, n=1)
        assert top[0][0] == "big", (
            f"SENSITIVITY: top contributor should be 'big', " f"got '{top[0][0]}'."
        )


# ------------------------------------------------------------------
# 6.2  Zero-variance task has zero/near-zero correlation
# ------------------------------------------------------------------
class TestZeroVarianceSensitivity:
    """A task with nearly identical low/expected/high should have ~0 correlation."""

    def test_deterministic_task_zero_corr(self):
        project = _make_chain_with_zero_variance_task()
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        correlations = SensitivityAnalyzer.calculate_correlations(results)
        b_corr = abs(correlations.get("B", 0))

        assert b_corr < 0.10, (
            f"SENSITIVITY: near-deterministic task B has corr={b_corr:.3f}, "
            f"expected ~0. A task with near-zero variance should barely "
            f"contribute to schedule variance."
        )


# ------------------------------------------------------------------
# 6.3  Effort-duration positive correlation
# ------------------------------------------------------------------
class TestEffortDurationCorrelation:
    """Effort and duration should be positively correlated."""

    def test_positive_correlation(self):
        project = make_chain_project(n_tasks=5)
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        from scipy import stats

        corr, _ = stats.spearmanr(results.durations, results.effort_durations)

        assert float(corr) > 0.5, (
            f"EFFORT-DURATION correlation = {float(corr):.3f}, expected "
            f"strongly positive.  Longer projects consume more effort."
        )

    def test_parallel_weaker_than_chain(self):
        """Parallel tasks should have weaker effort-duration
        correlation than chains (parallel effort doesn't map 1:1
        to duration).
        """
        from scipy import stats

        proj_chain = make_chain_project(n_tasks=4)
        proj_par = make_parallel_project(n_parallel=4)
        res_chain = run_simulation(proj_chain, iterations=STAT_ITERATIONS_CI, seed=42)
        res_par = run_simulation(proj_par, iterations=STAT_ITERATIONS_CI, seed=42)

        corr_chain, _ = stats.spearmanr(res_chain.durations, res_chain.effort_durations)
        corr_par, _ = stats.spearmanr(res_par.durations, res_par.effort_durations)

        assert float(corr_chain) > float(corr_par), (
            f"CHAIN effort-duration corr={float(corr_chain):.3f} should "
            f"exceed PARALLEL corr={float(corr_par):.3f}."
        )


# ------------------------------------------------------------------
# 6.4  All chain tasks have positive correlation
# ------------------------------------------------------------------
class TestChainAllPositive:
    """In a pure chain, every task should have positive correlation
    with project duration because every task is on the critical path.
    """

    def test_all_positive(self):
        project = make_chain_project(n_tasks=5)
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)

        correlations = SensitivityAnalyzer.calculate_correlations(results)
        for task_id, corr in correlations.items():
            assert corr > 0.0, (
                f"CHAIN SENSITIVITY: task {task_id} has corr={corr:.3f}. "
                f"All chain tasks should have positive correlation."
            )


# ------------------------------------------------------------------
# 6.5  Off-critical-path task has low sensitivity
# ------------------------------------------------------------------
class TestOffCriticalPathLowSensitivity:
    """In a diamond A → {B, C} → D where C is much smaller than B,
    C (rarely on critical path) should have low sensitivity.
    """

    def test_small_branch_low_sensitivity(self):
        project = make_diamond_project(
            b_estimate=(40.0, 80.0, 200.0),
            c_estimate=(1.0, 2.0, 4.0),
        )
        results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=42)
        correlations = SensitivityAnalyzer.calculate_correlations(results)

        corr_b = abs(correlations.get("B", 0))
        corr_c = abs(correlations.get("C", 0))

        assert corr_c < corr_b, (
            f"OFF-PATH SENSITIVITY: small branch C corr={corr_c:.3f} "
            f"should be less than dominant branch B corr={corr_b:.3f}."
        )
        assert corr_c < 0.20, (
            f"OFF-PATH SENSITIVITY: C corr={corr_c:.3f} should be < 0.20 "
            f"since it is almost never on the critical path."
        )


# ------------------------------------------------------------------
# 6.6  Sensitivity stability across seeds
# ------------------------------------------------------------------
class TestSensitivityStability:
    """Top contributors should be consistent across different seeds."""

    def test_top_contributor_stable(self):
        project = _make_one_dominant_project()
        top_ids = set()
        for seed in [10, 20, 30]:
            results = run_simulation(project, iterations=STAT_ITERATIONS_CI, seed=seed)
            top = SensitivityAnalyzer.get_top_contributors(results, n=1)
            top_ids.add(top[0][0])

        assert len(top_ids) == 1 and "big" in top_ids, (
            f"SENSITIVITY STABILITY: top contributor varied across seeds: "
            f"{top_ids}. Expected consistently 'big'."
        )
