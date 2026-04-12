"""Shared fixtures, helpers, and project builders for probabilistic tests."""

from __future__ import annotations

import math
from datetime import date

import numpy as np
import pytest
from scipy import stats

from mcprojsim.config import Config, EffortUnit
from mcprojsim.models.project import (
    CalendarSpec,
    DistributionType,
    Project,
    ProjectMetadata,
    ResourceSpec,
    Risk,
    Task,
    TaskEstimate,
    UncertaintyFactors,
)
from mcprojsim.models.simulation import SimulationResults
from mcprojsim.simulation.distributions import fit_shifted_lognormal
from mcprojsim.simulation.engine import SimulationEngine

# ---------------------------------------------------------------------------
# Iteration counts
# ---------------------------------------------------------------------------
STAT_ITERATIONS_CI = 5_000
"""Fast: ~2s per test, for CI pipeline."""

STAT_ITERATIONS_FULL = 100_000
"""Thorough: ~30s per test, periodic verification."""

# ---------------------------------------------------------------------------
# Default significance level
# ---------------------------------------------------------------------------
ALPHA = 0.001
"""0.1% — one false positive per ~1000 tests."""

ALPHA_CI = 0.01
"""1% — looser threshold for the fast CI suite."""

# ---------------------------------------------------------------------------
# Default lognormal z-value (P95)
# ---------------------------------------------------------------------------
Z_95: float = Config.get_default().get_lognormal_high_z_value()

# ---------------------------------------------------------------------------
# Apply markers to every test in this package automatically
# ---------------------------------------------------------------------------
pytestmark = pytest.mark.probabilistic


# ===================================================================
# Statistical assertion helpers
# ===================================================================


def assert_within_bounds(
    samples: np.ndarray,
    lower: float,
    upper: float,
    label: str = "",
) -> None:
    """Assert every sample is within [lower, upper].

    Provides a detailed error message listing violation count, sample
    range, and the first few violating values.
    """
    below = samples < lower - 1e-9
    above = samples > upper + 1e-9
    violations = int(np.sum(below | above))
    if violations == 0:
        return
    bad_values = samples[below | above][:10]
    msg = (
        f"BOUNDARY VIOLATION{f' ({label})' if label else ''}: "
        f"{violations}/{len(samples)} samples outside [{lower}, {upper}]. "
        f"Sample range: [{float(samples.min()):.6f}, {float(samples.max()):.6f}]. "
        f"First violating values: {bad_values.tolist()}. "
        f"SUGGESTION: Check distribution sampling bounds, unit conversion, "
        f"or uncertainty-factor application."
    )
    raise AssertionError(msg)


def assert_ks_test(
    samples: np.ndarray,
    cdf_func: str | object,
    alpha: float = ALPHA,
    label: str = "",
) -> None:
    """Kolmogorov-Smirnov test: samples come from the given distribution.

    ``cdf_func`` can be a scipy frozen distribution or a string name
    accepted by ``scipy.stats.kstest``.
    """
    stat, p_value = stats.kstest(samples, cdf_func)
    if p_value > alpha:
        return
    msg = (
        f"KS TEST REJECTED{f' ({label})' if label else ''}: "
        f"D-statistic={stat:.6f}, p-value={p_value:.2e}, α={alpha}. "
        f"Sample size={len(samples)}, mean={float(np.mean(samples)):.4f}, "
        f"std={float(np.std(samples)):.4f}. "
        f"SUGGESTION: The sampled distribution does not match the expected "
        f"theoretical CDF.  Check distribution parameterisation "
        f"(fit_shifted_lognormal, triangular bounds) or whether uncertainty "
        f"factors / risks are accidentally applied."
    )
    raise AssertionError(msg)


def assert_mean_close(
    samples: np.ndarray,
    expected_mean: float,
    alpha: float = ALPHA,
    label: str = "",
) -> None:
    """Two-sided t-test: sample mean equals *expected_mean*."""
    t_stat, p_value = stats.ttest_1samp(samples, expected_mean)
    if p_value > alpha:
        return
    observed = float(np.mean(samples))
    msg = (
        f"MEAN TEST REJECTED{f' ({label})' if label else ''}: "
        f"observed_mean={observed:.6f}, expected_mean={expected_mean:.6f}, "
        f"t-stat={t_stat:.4f}, p-value={p_value:.2e}, α={alpha}, "
        f"n={len(samples)}. "
        f"Relative error = {abs(observed - expected_mean) / max(abs(expected_mean), 1e-9):.4%}. "
        f"SUGGESTION: Check whether sampling, unit conversion, or "
        f"multiplicative factors have shifted the distribution mean."
    )
    raise AssertionError(msg)


def assert_variance_close(
    samples: np.ndarray,
    expected_var: float,
    alpha: float = ALPHA,
    label: str = "",
) -> None:
    """Chi-squared test for variance: sample variance equals *expected_var*."""
    n = len(samples)
    s2 = float(np.var(samples, ddof=1))
    chi2_stat = (n - 1) * s2 / expected_var
    p_lower = stats.chi2.cdf(chi2_stat, df=n - 1)
    p_value = 2.0 * min(p_lower, 1.0 - p_lower)
    if p_value > alpha:
        return
    msg = (
        f"VARIANCE TEST REJECTED{f' ({label})' if label else ''}: "
        f"observed_var={s2:.4f}, expected_var={expected_var:.4f}, "
        f"χ²={chi2_stat:.4f}, p-value={p_value:.2e}, α={alpha}, n={n}. "
        f"SUGGESTION: Check distribution σ parameter, or whether "
        f"risk/uncertainty factors are adding unexpected variance."
    )
    raise AssertionError(msg)


def assert_proportion_close(
    observed_count: int,
    total: int,
    expected_prob: float,
    alpha: float = ALPHA,
    label: str = "",
) -> None:
    """Binomial test: observed proportion equals *expected_prob*."""
    result = stats.binomtest(observed_count, total, expected_prob)
    if result.pvalue > alpha:
        return
    observed_frac = observed_count / total
    msg = (
        f"PROPORTION TEST REJECTED{f' ({label})' if label else ''}: "
        f"observed={observed_count}/{total} = {observed_frac:.4f}, "
        f"expected_p={expected_prob:.4f}, p-value={result.pvalue:.2e}, "
        f"α={alpha}. "
        f"SUGGESTION: If testing risk trigger rate, check the probability "
        f"comparison in RiskEvaluator.  If testing percentile calibration, "
        f"check fit_shifted_lognormal z-value."
    )
    raise AssertionError(msg)


def assert_spearman_positive(
    x: np.ndarray,
    y: np.ndarray,
    min_rho: float = 0.0,
    label: str = "",
) -> None:
    """Assert Spearman correlation is positive and above *min_rho*."""
    rho_result = stats.spearmanr(x, y)
    rho = float(np.asarray(rho_result.statistic).item())
    pval = float(np.asarray(rho_result.pvalue).item())
    if rho > min_rho:
        return
    msg = (
        f"SPEARMAN CORRELATION TOO LOW{f' ({label})' if label else ''}: "
        f"ρ={rho:.4f}, min_ρ={min_rho}, p-value={pval:.2e}, n={len(x)}. "
        f"SUGGESTION: Check whether the expected structural relationship "
        f"exists (e.g. task on critical path should correlate with project "
        f"duration)."
    )
    raise AssertionError(msg)


# ===================================================================
# Analytical helpers
# ===================================================================


def shifted_lognormal_mean(
    low: float, expected: float, high: float, z: float = Z_95
) -> float:
    """Theoretical mean of the shifted lognormal: low + exp(μ + σ²/2)."""
    mu, sigma = fit_shifted_lognormal(low, expected, high, z)
    return low + math.exp(mu + sigma**2 / 2.0)


def shifted_lognormal_variance(
    low: float, expected: float, high: float, z: float = Z_95
) -> float:
    """Theoretical variance of the shifted lognormal."""
    mu, sigma = fit_shifted_lognormal(low, expected, high, z)
    return math.exp(2.0 * mu + sigma**2) * (math.exp(sigma**2) - 1.0)


def shifted_lognormal_cdf(low: float, mu: float, sigma: float) -> stats.rv_continuous:
    """Return a frozen scipy distribution for the shifted lognormal."""
    return stats.lognorm(s=sigma, scale=math.exp(mu), loc=low)


# ===================================================================
# Project builder helpers
# ===================================================================

_DEFAULT_START = date(2026, 1, 5)


def _meta(
    name: str = "Test Project",
    distribution: DistributionType = DistributionType.LOGNORMAL,
    start_date: date = _DEFAULT_START,
    hours_per_day: float = 8.0,
) -> ProjectMetadata:
    return ProjectMetadata(
        name=name,
        start_date=start_date,
        hours_per_day=hours_per_day,
        distribution=distribution,
    )


def make_single_task_project(
    low: float = 10.0,
    expected: float = 20.0,
    high: float = 50.0,
    unit: EffortUnit = EffortUnit.HOURS,
    distribution: DistributionType = DistributionType.LOGNORMAL,
    risks: list[Risk] | None = None,
    uncertainty_factors: UncertaintyFactors | None = None,
) -> Project:
    """Project with one task and no dependencies."""
    return Project(
        project=_meta(name="Single Task", distribution=distribution),
        tasks=[
            Task(
                id="t1",
                name="Task 1",
                estimate=TaskEstimate(low=low, expected=expected, high=high, unit=unit),
                risks=risks or [],
                uncertainty_factors=uncertainty_factors,
            ),
        ],
    )


def make_chain_project(
    estimates: list[tuple[float, float, float]] | None = None,
    n_tasks: int = 3,
    unit: EffortUnit = EffortUnit.HOURS,
    distribution: DistributionType = DistributionType.LOGNORMAL,
    risks_on_task: int | None = None,
    risk_probability: float = 0.3,
    risk_impact_hours: float = 20.0,
) -> Project:
    """Pure sequential chain: t1 → t2 → t3 → ..."""
    if estimates is None:
        estimates = [(10.0, 20.0, 50.0)] * n_tasks
    tasks = []
    for i, (low, exp, high) in enumerate(estimates):
        tid = f"t{i + 1}"
        deps = [f"t{i}"] if i > 0 else []
        risks: list[Risk] = []
        if risks_on_task is not None and i == risks_on_task:
            risks = [
                Risk(
                    id=f"risk_{tid}",
                    name=f"Risk on {tid}",
                    probability=risk_probability,
                    impact=risk_impact_hours,
                )
            ]
        tasks.append(
            Task(
                id=tid,
                name=f"Task {i + 1}",
                estimate=TaskEstimate(low=low, expected=exp, high=high, unit=unit),
                dependencies=deps,
                risks=risks,
            )
        )
    return Project(
        project=_meta(name="Chain Project", distribution=distribution),
        tasks=tasks,
    )


def make_parallel_project(
    estimates: list[tuple[float, float, float]] | None = None,
    n_parallel: int = 4,
    unit: EffortUnit = EffortUnit.HOURS,
    distribution: DistributionType = DistributionType.LOGNORMAL,
) -> Project:
    """Fully independent parallel tasks (no dependencies)."""
    if estimates is None:
        estimates = [(10.0, 20.0, 50.0)] * n_parallel
    tasks = [
        Task(
            id=f"t{i + 1}",
            name=f"Task {i + 1}",
            estimate=TaskEstimate(low=low, expected=exp, high=high, unit=unit),
        )
        for i, (low, exp, high) in enumerate(estimates)
    ]
    return Project(
        project=_meta(name="Parallel Project", distribution=distribution),
        tasks=tasks,
    )


def make_diamond_project(
    a_estimate: tuple[float, float, float] = (5.0, 10.0, 20.0),
    b_estimate: tuple[float, float, float] = (10.0, 20.0, 50.0),
    c_estimate: tuple[float, float, float] = (10.0, 20.0, 50.0),
    d_estimate: tuple[float, float, float] = (5.0, 10.0, 20.0),
    distribution: DistributionType = DistributionType.LOGNORMAL,
) -> Project:
    """Diamond DAG: A → {B, C} → D."""

    def _task(tid: str, est: tuple[float, float, float], deps: list[str]) -> Task:
        return Task(
            id=tid,
            name=f"Task {tid}",
            estimate=TaskEstimate(
                low=est[0], expected=est[1], high=est[2], unit=EffortUnit.HOURS
            ),
            dependencies=deps,
        )

    return Project(
        project=_meta(name="Diamond Project", distribution=distribution),
        tasks=[
            _task("A", a_estimate, []),
            _task("B", b_estimate, ["A"]),
            _task("C", c_estimate, ["A"]),
            _task("D", d_estimate, ["B", "C"]),
        ],
    )


def make_fan_out_project(
    n_parallel: int = 10,
    root_estimate: tuple[float, float, float] = (5.0, 10.0, 20.0),
    branch_estimate: tuple[float, float, float] = (10.0, 20.0, 50.0),
    sink_estimate: tuple[float, float, float] = (5.0, 10.0, 20.0),
    distribution: DistributionType = DistributionType.LOGNORMAL,
) -> Project:
    """Fan-out/fan-in: root → n parallel branches → sink."""
    tasks: list[Task] = [
        Task(
            id="root",
            name="Root",
            estimate=TaskEstimate(
                low=root_estimate[0],
                expected=root_estimate[1],
                high=root_estimate[2],
                unit=EffortUnit.HOURS,
            ),
        ),
    ]
    branch_ids = []
    for i in range(n_parallel):
        bid = f"branch_{i + 1}"
        branch_ids.append(bid)
        tasks.append(
            Task(
                id=bid,
                name=f"Branch {i + 1}",
                estimate=TaskEstimate(
                    low=branch_estimate[0],
                    expected=branch_estimate[1],
                    high=branch_estimate[2],
                    unit=EffortUnit.HOURS,
                ),
                dependencies=["root"],
            )
        )
    tasks.append(
        Task(
            id="sink",
            name="Sink",
            estimate=TaskEstimate(
                low=sink_estimate[0],
                expected=sink_estimate[1],
                high=sink_estimate[2],
                unit=EffortUnit.HOURS,
            ),
            dependencies=branch_ids,
        )
    )
    return Project(
        project=_meta(name="Fan-out Project", distribution=distribution),
        tasks=tasks,
    )


def make_constrained_parallel_project(
    n_parallel: int = 4,
    n_resources: int = 2,
    estimate: tuple[float, float, float] = (10.0, 20.0, 50.0),
    distribution: DistributionType = DistributionType.LOGNORMAL,
) -> Project:
    """Parallel tasks with a limited pool of resources."""
    resource_names = [f"res_{i + 1}" for i in range(n_resources)]
    resources = [ResourceSpec(name=name, experience_level=3) for name in resource_names]
    tasks = [
        Task(
            id=f"t{i + 1}",
            name=f"Task {i + 1}",
            estimate=TaskEstimate(
                low=estimate[0],
                expected=estimate[1],
                high=estimate[2],
                unit=EffortUnit.HOURS,
            ),
            resources=resource_names,
            max_resources=1,
        )
        for i in range(n_parallel)
    ]
    return Project(
        project=_meta(name="Constrained Parallel", distribution=distribution),
        tasks=tasks,
        resources=resources,
        calendars=[CalendarSpec(id="default")],
    )


# ===================================================================
# Simulation runner helper
# ===================================================================


def run_simulation(
    project: Project,
    iterations: int = STAT_ITERATIONS_CI,
    seed: int = 42,
    two_pass: bool = False,
) -> SimulationResults:
    """Run simulation with common defaults for probabilistic tests."""
    engine = SimulationEngine(
        iterations=iterations,
        random_seed=seed,
        show_progress=False,
        two_pass=two_pass,
    )
    result: SimulationResults = engine.run(project)
    return result
