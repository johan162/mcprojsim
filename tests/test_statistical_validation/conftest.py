"""Shared fixtures and statistical utilities for validation tests.

This module provides project builders and assertion helpers tailored
for end-to-end validation of the simulation engine against known
analytical results.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Callable

import numpy as np
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
from mcprojsim.models.simulation import SimulationResults
from mcprojsim.simulation.distributions import fit_shifted_lognormal
from mcprojsim.simulation.engine import SimulationEngine

# ---------------------------------------------------------------------------
# Iteration counts — use high counts for statistical power
# ---------------------------------------------------------------------------
N_ITERATIONS = 50_000
"""Default iterations for validation tests — balances power vs speed."""

N_ITERATIONS_HEAVY = 200_000
"""High-confidence tests needing very tight bounds."""

# ---------------------------------------------------------------------------
# Significance level — very strict to avoid false positives
# ---------------------------------------------------------------------------
ALPHA = 0.001
"""0.1% significance: one false positive per 1000 tests."""

# ---------------------------------------------------------------------------
# Standard start date and config constants
# ---------------------------------------------------------------------------
START_DATE = date(2026, 1, 5)
Z_95: float = Config.get_default().get_lognormal_high_z_value()


# ---------------------------------------------------------------------------
# Simulation runner
# ---------------------------------------------------------------------------


def run_sim(
    project: Project,
    iterations: int = N_ITERATIONS,
    seed: int = 42,
    config: Config | None = None,
) -> SimulationResults:
    """Run a simulation with deterministic seed and no progress output."""
    engine = SimulationEngine(
        iterations=iterations,
        random_seed=seed,
        config=config,
        show_progress=False,
    )
    return engine.run(project)


# ---------------------------------------------------------------------------
# Project builders
# ---------------------------------------------------------------------------


def _meta(
    name: str = "Validation",
    distribution: DistributionType = DistributionType.TRIANGULAR,
    hours_per_day: float = 8.0,
) -> ProjectMetadata:
    return ProjectMetadata(
        name=name,
        start_date=START_DATE,
        hours_per_day=hours_per_day,
        distribution=distribution,
    )


def single_task_project(
    low: float,
    expected: float,
    high: float,
    distribution: DistributionType = DistributionType.TRIANGULAR,
    risks: list[Risk] | None = None,
) -> Project:
    """One task, no dependencies."""
    return Project(
        project=_meta(distribution=distribution),
        tasks=[
            Task(
                id="t1",
                name="Task 1",
                estimate=TaskEstimate(
                    low=low, expected=expected, high=high, unit=EffortUnit.HOURS
                ),
                risks=risks or [],
            )
        ],
    )


def chain_project(
    estimates: list[tuple[float, float, float]],
    distribution: DistributionType = DistributionType.TRIANGULAR,
) -> Project:
    """Sequential chain: t1 → t2 → t3 → ..."""
    tasks = []
    for i, (low, exp, high) in enumerate(estimates):
        tid = f"t{i + 1}"
        deps = [f"t{i}"] if i > 0 else []
        tasks.append(
            Task(
                id=tid,
                name=f"Task {i + 1}",
                estimate=TaskEstimate(
                    low=low, expected=exp, high=high, unit=EffortUnit.HOURS
                ),
                dependencies=deps,
            )
        )
    return Project(
        project=_meta(distribution=distribution),
        tasks=tasks,
    )


def parallel_project(
    estimates: list[tuple[float, float, float]],
    distribution: DistributionType = DistributionType.TRIANGULAR,
) -> Project:
    """All tasks independent (no dependencies)."""
    tasks = [
        Task(
            id=f"t{i + 1}",
            name=f"Task {i + 1}",
            estimate=TaskEstimate(
                low=low, expected=exp, high=high, unit=EffortUnit.HOURS
            ),
        )
        for i, (low, exp, high) in enumerate(estimates)
    ]
    return Project(
        project=_meta(distribution=distribution),
        tasks=tasks,
    )


def diamond_project(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
    c: tuple[float, float, float],
    d: tuple[float, float, float],
    distribution: DistributionType = DistributionType.TRIANGULAR,
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
        project=_meta(distribution=distribution),
        tasks=[
            _task("A", a, []),
            _task("B", b, ["A"]),
            _task("C", c, ["A"]),
            _task("D", d, ["B", "C"]),
        ],
    )


# ---------------------------------------------------------------------------
# Analytical formulas
# ---------------------------------------------------------------------------


def triangular_mean(low: float, mode: float, high: float) -> float:
    """Mean of Triangular(low, mode, high)."""
    return (low + mode + high) / 3.0


def triangular_variance(low: float, mode: float, high: float) -> float:
    """Variance of Triangular(low, mode, high)."""
    a, b, c = low, high, mode
    return (a**2 + b**2 + c**2 - a * b - a * c - b * c) / 18.0


def lognormal_mean(low: float, expected: float, high: float) -> float:
    """Mean of the shifted lognormal used by the engine."""
    mu, sigma = fit_shifted_lognormal(low, expected, high, Z_95)
    return low + math.exp(mu + sigma**2 / 2.0)


def lognormal_variance(low: float, expected: float, high: float) -> float:
    """Variance of the shifted lognormal used by the engine."""
    mu, sigma = fit_shifted_lognormal(low, expected, high, Z_95)
    return math.exp(2 * mu + sigma**2) * (math.exp(sigma**2) - 1.0)


# ---------------------------------------------------------------------------
# Statistical assertion helpers
# ---------------------------------------------------------------------------


def assert_mean_within_ci(
    samples: np.ndarray,
    expected_mean: float,
    alpha: float = ALPHA,
    label: str = "",
) -> None:
    """Assert sample mean is consistent with expected_mean (two-sided t-test)."""
    t_stat, p_value = stats.ttest_1samp(samples, expected_mean)
    if p_value > alpha:
        return
    obs = float(np.mean(samples))
    n = len(samples)
    se = float(np.std(samples, ddof=1)) / math.sqrt(n)
    msg = (
        f"MEAN VALIDATION FAILED{f' ({label})' if label else ''}: "
        f"observed={obs:.6f} ± {1.96*se:.6f}, expected={expected_mean:.6f}, "
        f"t={t_stat:.4f}, p={p_value:.2e}, α={alpha}, n={n}"
    )
    raise AssertionError(msg)


def assert_variance_within_ci(
    samples: np.ndarray,
    expected_var: float,
    alpha: float = ALPHA,
    label: str = "",
) -> None:
    """Assert sample variance is consistent with expected (chi-squared test)."""
    n = len(samples)
    s2 = float(np.var(samples, ddof=1))
    chi2_stat = (n - 1) * s2 / expected_var
    p_lower = stats.chi2.cdf(chi2_stat, df=n - 1)
    p_value = 2.0 * min(p_lower, 1.0 - p_lower)
    if p_value > alpha:
        return
    msg = (
        f"VARIANCE VALIDATION FAILED{f' ({label})' if label else ''}: "
        f"observed_var={s2:.4f}, expected_var={expected_var:.4f}, "
        f"χ²={chi2_stat:.2f}, p={p_value:.2e}, α={alpha}, n={n}"
    )
    raise AssertionError(msg)


def assert_proportion(
    count: int,
    total: int,
    expected_p: float,
    alpha: float = ALPHA,
    label: str = "",
) -> None:
    """Binomial test for proportion."""
    result = stats.binomtest(count, total, expected_p)
    if result.pvalue > alpha:
        return
    obs_p = count / total
    msg = (
        f"PROPORTION VALIDATION FAILED{f' ({label})' if label else ''}: "
        f"observed={count}/{total}={obs_p:.4f}, expected_p={expected_p:.4f}, "
        f"p={result.pvalue:.2e}, α={alpha}"
    )
    raise AssertionError(msg)


def assert_ks_fit(
    samples: np.ndarray,
    cdf: Callable[[np.ndarray], np.ndarray],
    alpha: float = ALPHA,
    label: str = "",
) -> None:
    """Kolmogorov-Smirnov goodness-of-fit test."""
    stat, p_value = stats.kstest(samples, cdf)
    if p_value > alpha:
        return
    msg = (
        f"KS TEST FAILED{f' ({label})' if label else ''}: "
        f"D={stat:.6f}, p={p_value:.2e}, α={alpha}, n={len(samples)}"
    )
    raise AssertionError(msg)


def assert_samples_bounded(
    samples: np.ndarray,
    lower: float,
    upper: float,
    label: str = "",
) -> None:
    """Assert all samples fall within [lower, upper]."""
    violations = int(np.sum((samples < lower - 1e-9) | (samples > upper + 1e-9)))
    if violations == 0:
        return
    msg = (
        f"BOUNDARY VIOLATION{f' ({label})' if label else ''}: "
        f"{violations}/{len(samples)} outside [{lower}, {upper}], "
        f"range=[{float(samples.min()):.4f}, {float(samples.max()):.4f}]"
    )
    raise AssertionError(msg)
