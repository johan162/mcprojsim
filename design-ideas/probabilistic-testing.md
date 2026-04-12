Version: 0.1.0

Date: 2026-04-09

Status: Design and Research Proposal

# Probabilistic Simulation Verification

## Executive Summary

Monte Carlo simulation correctness cannot be verified by comparing a single output against a hand-computed expected value. The stochastic nature of the engine means every run produces different numbers, and the internal algorithms (shifted lognormal sampling, multiplicative uncertainty factors, probabilistic risk triggers, dependency/resource scheduling, critical-path tracing) interact in ways that make closed-form analytical solutions intractable for realistic projects.

This document proposes a **probabilistic verification framework** — a suite of statistical tests that run the simulation engine with controlled inputs and verify that the outputs satisfy mathematical properties that *must* hold if the implementation is correct. Each test is designed so that a correct implementation passes with probability ≥ 99.9% and a buggy implementation fails with high probability.

The framework is organized into eight verification categories:

1. **Boundary invariant tests** — outputs stay within theoretical min/max bounds.
2. **Distribution shape tests** — sampled distributions match their theoretical forms.
3. **Moment convergence tests** — sample means and variances converge to known analytical values.
4. **Risk impact proportionality tests** — risks add effort proportional to probability × impact.
5. **Scheduling invariant tests** — dependency ordering, critical-path, and slack properties hold.
6. **Sensitivity and correlation tests** — Spearman correlations reflect known structural relationships.
7. **Composition and scaling tests** — adding tasks, resources, or risks changes results in predictable directions.
8. **Reproducibility and seed tests** — identical seeds produce identical results; different seeds diverge.

Each category contains multiple concrete test cases with explicit pass/fail criteria. The tests are designed to be run as part of CI (with moderate iteration counts for speed) and periodically as a full verification suite (with high iteration counts for statistical power).

## Problem Statement

The simulation engine chains multiple stochastic and algorithmic steps:

```
estimate resolution → distribution sampling → unit conversion
    → uncertainty factor multiplication → risk impact addition
    → dependency/resource scheduling → critical-path identification
    → statistics aggregation → sensitivity analysis
```

A bug in any step could produce plausible-looking but incorrect results. Traditional unit tests verify individual components in isolation but cannot catch emergent errors in the full pipeline — for example, a unit conversion error that shifts all durations by 8× would still produce valid-looking distributions, just with wrong magnitudes.

The key insight is that while we cannot predict exact Monte Carlo outputs, we *can* derive **statistical properties** that the outputs must satisfy. If a test checks a property that holds with probability > 99.99% under correct implementation, and we observe a violation, we have strong evidence of a bug.

## Current Testing State

The existing test suite covers:

- `test_simulation.py`: Unit tests for `DistributionSampler` (bounds, reproducibility), `RiskEvaluator` (trigger/no-trigger), basic simulation flow.
- `test_staffing.py`: Productivity model, effective capacity, team-size recommendations.
- `test_two_pass_simulation.py`: Duration cache, two-pass delta traceability.
- `test_integration.py`, `test_e2e_combinations.py`: End-to-end YAML-to-results flows.

What is missing:

- No tests verify that sampled distributions have the correct shape, moments, or percentiles.
- No tests verify that risk impacts scale correctly with probability and impact size.
- No tests verify scheduling invariants (e.g., no task starts before its dependencies finish).
- No tests verify that sensitivity correlations reflect known structural relationships.
- No tests verify monotonicity properties (e.g., adding a risk never reduces mean duration).
- No large-scale statistical convergence tests.

## Test Framework Design

### Infrastructure

#### Test Configuration

```python
# tests/conftest.py additions

# Standard iteration counts
STAT_ITERATIONS_CI = 5_000       # Fast: ~2s per test, for CI pipeline
STAT_ITERATIONS_FULL = 100_000   # Thorough: ~30s per test, periodic verification

# Significance level for statistical tests
ALPHA = 0.001  # 0.1% — one false positive per 1000 tests

# Tolerance for moment comparisons (relative)
MOMENT_RTOL = 0.05  # 5% relative tolerance on means/variances at 100k iterations
```

#### Pytest Markers

```python
# pyproject.toml
[tool.pytest.ini_options]
markers = [
    "probabilistic: statistical verification tests (may be slow)",
    "probabilistic_full: full verification suite (very slow, run periodically)",
]
```

Tests are marked `@pytest.mark.probabilistic` and excluded from the default fast suite. A CI job runs them nightly or on release branches. The `probabilistic_full` marker identifies the highest-iteration tests for periodic deep verification.

#### Test File Structure

```
tests/
  test_probabilistic/
    __init__.py
    conftest.py              # Shared fixtures, iteration counts, helpers
    test_boundary.py         # Category 1: Boundary invariants
    test_distributions.py    # Category 2: Distribution shape
    test_moments.py          # Category 3: Moment convergence
    test_risk_impact.py      # Category 4: Risk proportionality
    test_scheduling.py       # Category 5: Scheduling invariants
    test_sensitivity.py      # Category 6: Sensitivity/correlation
    test_composition.py      # Category 7: Composition and scaling
    test_reproducibility.py  # Category 8: Reproducibility
    fixtures/                # Complex YAML project files for tests
      chain_project.yaml
      diamond_project.yaml
      parallel_project.yaml
      constrained_project.yaml
      risk_heavy_project.yaml
      ...
```

#### Statistical Test Helpers

```python
# tests/test_probabilistic/conftest.py

import numpy as np
from scipy import stats

def assert_within_bounds(samples: np.ndarray, lower: float, upper: float, label: str = ""):
    """Assert every sample is within [lower, upper]."""
    violations = np.sum((samples < lower - 1e-9) | (samples > upper + 1e-9))
    assert violations == 0, (
        f"{label}: {violations}/{len(samples)} samples outside [{lower}, {upper}]. "
        f"Range: [{samples.min()}, {samples.max()}]"
    )

def assert_ks_test(samples: np.ndarray, cdf_func, alpha: float = 0.001, label: str = ""):
    """Kolmogorov-Smirnov test: samples come from the given distribution."""
    stat, p_value = stats.kstest(samples, cdf_func)
    assert p_value > alpha, (
        f"{label}: KS test rejected (stat={stat:.4f}, p={p_value:.6f}, α={alpha})"
    )

def assert_chi2_test(
    samples: np.ndarray, expected_freq: np.ndarray, alpha: float = 0.001, label: str = ""
):
    """Chi-squared goodness-of-fit test."""
    stat, p_value = stats.chisquare(samples, f_exp=expected_freq)
    assert p_value > alpha, (
        f"{label}: χ² test rejected (stat={stat:.4f}, p={p_value:.6f}, α={alpha})"
    )

def assert_mean_close(
    samples: np.ndarray, expected_mean: float, alpha: float = 0.001, label: str = ""
):
    """Two-sided t-test: sample mean equals expected_mean."""
    t_stat, p_value = stats.ttest_1samp(samples, expected_mean)
    assert p_value > alpha, (
        f"{label}: Mean test rejected. Observed={np.mean(samples):.4f}, "
        f"expected={expected_mean:.4f}, t={t_stat:.4f}, p={p_value:.6f}"
    )

def assert_variance_close(
    samples: np.ndarray, expected_var: float, alpha: float = 0.001, label: str = ""
):
    """Chi-squared test for variance: sample variance equals expected_var."""
    n = len(samples)
    s2 = np.var(samples, ddof=1)
    chi2_stat = (n - 1) * s2 / expected_var
    # Two-sided test
    p_lower = stats.chi2.cdf(chi2_stat, df=n - 1)
    p_value = 2 * min(p_lower, 1 - p_lower)
    assert p_value > alpha, (
        f"{label}: Variance test rejected. Observed={s2:.4f}, "
        f"expected={expected_var:.4f}, χ²={chi2_stat:.4f}, p={p_value:.6f}"
    )

def assert_proportion_close(
    observed_count: int, total: int, expected_prob: float,
    alpha: float = 0.001, label: str = ""
):
    """Binomial test: observed proportion equals expected probability."""
    result = stats.binomtest(observed_count, total, expected_prob)
    assert result.pvalue > alpha, (
        f"{label}: Proportion test rejected. Observed={observed_count}/{total}="
        f"{observed_count/total:.4f}, expected={expected_prob:.4f}, p={result.pvalue:.6f}"
    )

def assert_spearman_positive(x: np.ndarray, y: np.ndarray, min_rho: float = 0.0, label: str = ""):
    """Assert Spearman correlation is positive and above a minimum."""
    rho, p_value = stats.spearmanr(x, y)
    assert rho > min_rho, (
        f"{label}: Expected Spearman ρ > {min_rho}, got ρ={rho:.4f}, p={p_value:.6f}"
    )

def assert_stochastic_dominance(
    samples_a: np.ndarray, samples_b: np.ndarray, alpha: float = 0.001, label: str = ""
):
    """One-sided Mann-Whitney U test: A stochastically dominates B (A ≥ B)."""
    stat, p_value = stats.mannwhitneyu(samples_a, samples_b, alternative="greater")
    assert p_value < alpha, (
        f"{label}: Stochastic dominance not confirmed. "
        f"mean_A={np.mean(samples_a):.2f}, mean_B={np.mean(samples_b):.2f}, p={p_value:.6f}"
    )
```

---

## Category 1: Boundary Invariant Tests

These tests verify hard constraints that must hold for every single iteration, regardless of randomness. A single violation is a definitive bug.

### 1.1 Duration Lower Bound

**Property:** Every task duration ≥ `low` estimate (before uncertainty/risk). After uncertainty factors (all ≥ 0.9 in default config) and risk (additive, ≥ 0), the final duration must be ≥ `low × min_uncertainty_product`.

**Test:** Run simulation with known estimates. Verify `min(task_durations[task_id]) ≥ low × 0.9^5` (worst-case all five factors at their lowest multiplier). For the shifted lognormal, the theoretical lower bound is `low` (the shift parameter), so with default uncertainty factors the per-task minimum is `low × product_of_all_uncertainty_multipliers`.

```python
def test_task_duration_never_below_shifted_lower_bound():
    """No task duration should fall below its shifted lognormal lower bound
    times the minimum possible uncertainty factor product."""
    # Project with known estimates, no risks
    project = make_project(tasks=[
        Task(id="t1", estimate={"low": 10, "expected": 20, "high": 50, "unit": "hours"}),
    ])
    results = simulate(project, iterations=STAT_ITERATIONS_CI, seed=42)

    min_uncertainty = 0.90  # team_experience=high is 0.90, the lowest single factor
    # Default levels: all at 1.0 except possibly overridden
    # With default config, product = 1.0 (all factors at default)
    theoretical_lower = 10.0 * 1.0  # low × uncertainty_product (defaults = 1.0)
    assert np.min(results.task_durations["t1"]) >= theoretical_lower - 1e-9
```

### 1.2 Project Duration ≥ Critical Path Lower Bound

**Property:** Project elapsed duration ≥ longest dependency chain sum of minimum task durations.

**Test:**

```python
def test_project_duration_ge_critical_chain_minimum():
    """Project duration must be at least the sum of minimums along
    the longest dependency chain."""
    # Chain: A(low=10) -> B(low=20) -> C(low=30)
    project = make_chain_project(lows=[10, 20, 30])
    results = simulate(project, iterations=STAT_ITERATIONS_CI, seed=42)

    chain_minimum = 10 + 20 + 30  # hours
    assert np.min(results.durations) >= chain_minimum - 1e-9
```

### 1.3 Effort ≥ Duration

**Property:** Total effort (sum of all task durations) ≥ project elapsed duration, because effort counts person-hours across all parallel tasks while duration only counts the critical path.

```python
def test_effort_ge_duration_every_iteration():
    """Total person-effort must be ≥ elapsed project duration in every iteration."""
    project = make_parallel_project(n_parallel=5)
    results = simulate(project, iterations=STAT_ITERATIONS_CI, seed=42)
    assert np.all(results.effort_durations >= results.durations - 1e-9)
```

### 1.4 Duration ≤ Effort (No Resource Constraints)

**Property:** Without resource constraints, the project can parallelize freely, so duration ≤ effort. With resource constraints this may not hold (resource waiting inflates elapsed time).

### 1.5 No Task Starts Before Dependencies Complete

**Property:** For every iteration, every task's start time ≥ max(end times of its dependencies). This is a scheduling invariant.

**Test:** Requires access to per-iteration schedule data. The test should instrument the scheduler or run a single iteration and inspect the schedule dict.

```python
def test_dependency_ordering_holds():
    """No task should start before all its dependencies have ended."""
    project = make_diamond_project()  # A -> B, A -> C, B -> D, C -> D
    engine = SimulationEngine(iterations=1, random_seed=42)
    # Run single iteration, inspect schedule
    results = engine.run(project)
    # Access internal schedule from last iteration (needs test hook or re-run)
    schedule = run_single_iteration_and_get_schedule(project, seed=42)
    for task in project.tasks:
        for dep_id in task.dependencies:
            assert schedule[task.id]["start"] >= schedule[dep_id]["end"] - 1e-9, (
                f"Task {task.id} starts at {schedule[task.id]['start']} "
                f"but dependency {dep_id} ends at {schedule[dep_id]['end']}"
            )
```

### 1.6 Risk Impact Non-Negative

**Property:** Risk impacts are always ≥ 0 (risks add duration, never subtract).

```python
def test_risk_impacts_non_negative():
    """Risk impacts should never be negative."""
    project = make_project_with_risks(n_risks=10, probability=0.5)
    results = simulate(project, iterations=STAT_ITERATIONS_CI, seed=42)
    for task_id, impacts in results.risk_impacts.items():
        assert np.all(impacts >= -1e-9), f"Negative risk impact for {task_id}"
```

### 1.7 Slack Non-Negative

**Property:** Total float (slack) is ≥ 0 for all tasks. Negative slack would indicate a scheduling algorithm error.

### 1.8 Critical Path Tasks Have Zero Slack

**Property:** Tasks on the critical path in any iteration should have slack ≈ 0 in that iteration. Mean slack across iterations should be low for high-criticality tasks.

---

## Category 2: Distribution Shape Tests

These tests verify that sampled distributions match their theoretical forms using goodness-of-fit tests.

### 2.1 Shifted Lognormal Distribution Shape

**Property:** For a task with estimate `(low, expected, high)` and no uncertainty factors or risks, the sampled durations should follow a shifted lognormal distribution: `Y = low + X` where `X ~ Lognormal(μ, σ)`, with μ and σ fitted from the mode and percentile constraints.

**Test:** Run simulation with a single zero-dependency task, no risks, default uncertainty factors (all = 1.0). Collect task durations. Apply KS test against the theoretical shifted lognormal CDF.

```python
def test_shifted_lognormal_shape():
    """Task durations should follow the theoretical shifted lognormal."""
    low, expected, high = 10.0, 30.0, 80.0
    project = make_single_task_project(low=low, expected=expected, high=high)
    results = simulate(project, iterations=STAT_ITERATIONS_FULL, seed=42)

    samples = results.task_durations["t1"]

    # Compute theoretical parameters
    mu, sigma = fit_shifted_lognormal(low, expected, high, z_95)

    # Shifted lognormal CDF: P(Y ≤ y) = P(X ≤ y - low) = Φ((ln(y-low) - μ) / σ)
    def shifted_lognormal_cdf(y):
        if y <= low:
            return 0.0
        return stats.lognorm.cdf(y - low, s=sigma, scale=np.exp(mu))

    assert_ks_test(samples, shifted_lognormal_cdf, label="Shifted lognormal shape")
```

### 2.2 Triangular Distribution Shape

**Property:** When configured to use triangular distribution, task durations follow `Triangular(low, expected, high)`.

**Test:** Same structure as 2.1, but configure the sampler for triangular mode and test against `stats.triang` CDF.

### 2.3 Mode Location

**Property:** The mode (peak) of the sampled distribution should be near `expected`. For shifted lognormal, the theoretical mode is `low + exp(μ - σ²) = expected` (by construction of the fit).

**Test:** Estimate the sample mode via kernel density estimation and verify it is within a tolerance of `expected`.

```python
def test_sample_mode_near_expected():
    """The empirical mode should be close to the 'expected' estimate."""
    low, expected, high = 5.0, 20.0, 60.0
    project = make_single_task_project(low=low, expected=expected, high=high)
    results = simulate(project, iterations=STAT_ITERATIONS_FULL, seed=42)

    samples = results.task_durations["t1"]
    # KDE mode estimation
    kde = stats.gaussian_kde(samples)
    x_grid = np.linspace(low, high * 1.5, 1000)
    mode_estimate = x_grid[np.argmax(kde(x_grid))]

    # Allow 15% tolerance on mode location
    assert abs(mode_estimate - expected) / expected < 0.15, (
        f"Mode {mode_estimate:.2f} too far from expected {expected:.2f}"
    )
```

### 2.4 High Percentile Calibration

**Property:** The `high` estimate should correspond to the configured high percentile (default P95). Approximately 5% of samples should exceed `high`.

```python
def test_high_percentile_calibration():
    """~5% of samples should exceed the 'high' estimate (P95 calibration)."""
    low, expected, high = 10.0, 25.0, 60.0
    project = make_single_task_project(low=low, expected=expected, high=high)
    results = simulate(project, iterations=STAT_ITERATIONS_FULL, seed=42)

    samples = results.task_durations["t1"]
    exceedance_count = np.sum(samples > high)
    expected_exceedance = 0.05  # 5% for P95

    assert_proportion_close(
        exceedance_count, len(samples), expected_exceedance,
        alpha=0.001, label="P95 calibration"
    )
```

### 2.5 Right Skew

**Property:** Shifted lognormal distributions are right-skewed (skewness > 0). The project duration distribution, being the max of dependent paths, should also be right-skewed.

```python
def test_duration_distribution_right_skewed():
    """Project duration should be right-skewed (positive skewness)."""
    project = make_sample_project()
    results = simulate(project, iterations=STAT_ITERATIONS_CI, seed=42)
    assert results.skewness > 0, f"Expected positive skewness, got {results.skewness}"
```

### 2.6 Effort Distribution Shape for Parallel Tasks

**Property:** For *n* independent parallel tasks with identical estimates, the effort distribution (sum) should approximate a scaled version of the single-task distribution by the Central Limit Theorem. As *n* grows, the normalized effort should approach Normal.

```python
def test_effort_normality_for_many_parallel_tasks():
    """With many independent parallel tasks, effort should approach Normal."""
    project = make_parallel_project(n_parallel=30, same_estimates=True)
    results = simulate(project, iterations=STAT_ITERATIONS_CI, seed=42)

    # Normalize effort
    effort = results.effort_durations
    normalized = (effort - np.mean(effort)) / np.std(effort)

    # Anderson-Darling test for normality
    stat, critical_values, significance_levels = stats.anderson(normalized, dist="norm")
    # At 1% significance level
    assert stat < critical_values[3], (  # index 3 = 1% level
        f"Anderson-Darling rejected normality: stat={stat:.4f}, "
        f"critical={critical_values[3]:.4f} at 1%"
    )
```

---

## Category 3: Moment Convergence Tests

These tests verify that sample statistics converge to analytically derivable values.

### 3.1 Single Task Mean

**Property:** For a shifted lognormal with parameters `(low, μ, σ)`, the theoretical mean is:

$$E[Y] = \text{low} + e^{\mu + \sigma^2/2}$$

The sample mean should converge to this value.

```python
def test_single_task_mean_converges():
    """Sample mean should converge to theoretical shifted lognormal mean."""
    low, expected, high = 8.0, 20.0, 55.0
    mu, sigma = fit_shifted_lognormal(low, expected, high, z_95)
    theoretical_mean = low + np.exp(mu + sigma**2 / 2)

    project = make_single_task_project(low=low, expected=expected, high=high)
    results = simulate(project, iterations=STAT_ITERATIONS_FULL, seed=42)

    assert_mean_close(
        results.task_durations["t1"], theoretical_mean,
        label="Single task mean convergence"
    )
```

### 3.2 Single Task Variance

**Property:** Theoretical variance of shifted lognormal:

$$\text{Var}[Y] = e^{2\mu + \sigma^2}(e^{\sigma^2} - 1)$$

```python
def test_single_task_variance_converges():
    """Sample variance should converge to theoretical shifted lognormal variance."""
    low, expected, high = 8.0, 20.0, 55.0
    mu, sigma = fit_shifted_lognormal(low, expected, high, z_95)
    theoretical_var = np.exp(2 * mu + sigma**2) * (np.exp(sigma**2) - 1)

    project = make_single_task_project(low=low, expected=expected, high=high)
    results = simulate(project, iterations=STAT_ITERATIONS_FULL, seed=42)

    assert_variance_close(
        results.task_durations["t1"], theoretical_var,
        label="Single task variance convergence"
    )
```

### 3.3 Effort Mean for Independent Tasks

**Property:** For *n* independent tasks, `E[effort] = Σ E[task_i]`. The sum of individual theoretical means should equal the mean of the effort distribution.

```python
def test_effort_mean_equals_sum_of_task_means():
    """Mean effort should equal sum of individual task means."""
    # 5 tasks with different estimates, no dependencies
    tasks = [
        (5, 10, 25), (10, 20, 50), (3, 8, 20), (15, 30, 70), (8, 15, 40)
    ]
    expected_means = []
    for low, exp, high in tasks:
        mu, sigma = fit_shifted_lognormal(low, exp, high, z_95)
        expected_means.append(low + np.exp(mu + sigma**2 / 2))

    total_expected_mean = sum(expected_means)

    project = make_parallel_project_from_estimates(tasks)
    results = simulate(project, iterations=STAT_ITERATIONS_FULL, seed=42)

    assert_mean_close(
        results.effort_durations, total_expected_mean,
        label="Effort mean = sum of task means"
    )
```

### 3.4 Uncertainty Factor Scales Mean

**Property:** Applying a multiplicative uncertainty factor *m* should scale the task mean by *m*: `E[m·Y] = m·E[Y]`.

**Test:** Run two simulations with the same seed — one with default factors (product=1.0), one with a known factor (e.g., `requirements_maturity=low` → 1.40). The ratio of means should be 1.40.

```python
def test_uncertainty_factor_scales_mean():
    """Uncertainty factor should multiplicatively scale the task mean."""
    project_base = make_single_task_project(low=10, expected=30, high=80)
    project_scaled = make_single_task_project(
        low=10, expected=30, high=80,
        uncertainty_factors={"requirements_maturity": "low"}  # 1.40 multiplier
    )

    results_base = simulate(project_base, iterations=STAT_ITERATIONS_CI, seed=42)
    results_scaled = simulate(project_scaled, iterations=STAT_ITERATIONS_CI, seed=42)

    mean_base = np.mean(results_base.task_durations["t1"])
    mean_scaled = np.mean(results_scaled.task_durations["t1"])

    # Same seed, same samples, just multiplied by 1.40
    ratio = mean_scaled / mean_base
    assert abs(ratio - 1.40) < 0.001, f"Expected ratio 1.40, got {ratio:.4f}"
```

**Note:** With the same seed, the base samples are identical, so the ratio should be exactly 1.40 (within floating-point precision), not just approximately. This is a deterministic check, not a statistical one.

### 3.5 Chain Duration Mean ≥ Max Individual Mean

**Property:** For a chain A → B → C, the project duration mean ≥ max(E[A], E[B], E[C]) and in fact equals E[A] + E[B] + E[C] (since they execute sequentially).

```python
def test_chain_duration_mean_equals_sum():
    """For a pure chain, project duration mean ≈ sum of task means."""
    tasks = [(5, 15, 40), (10, 25, 60), (8, 20, 50)]
    expected_total = 0
    for low, exp, high in tasks:
        mu, sigma = fit_shifted_lognormal(low, exp, high, z_95)
        expected_total += low + np.exp(mu + sigma**2 / 2)

    project = make_chain_project_from_estimates(tasks)
    results = simulate(project, iterations=STAT_ITERATIONS_FULL, seed=42)

    assert_mean_close(results.durations, expected_total, label="Chain mean = sum of task means")
```

### 3.6 Parallel Duration Mean: Max-of-N

**Property:** For *n* independent parallel tasks, the project duration = max(T₁, ..., Tₙ). The mean of the max is analytically complex for lognormals, but we can verify:
- `E[max] > E[any individual task]`
- `E[max] < sum(E[task_i])` (strictly less)
- For identical tasks, `E[max]` follows the known order-statistic formula.

```python
def test_parallel_duration_bounds():
    """For parallel tasks, E[max] should be between max(E[task_i]) and sum(E[task_i])."""
    tasks = [(5, 15, 40), (10, 25, 60), (8, 20, 50)]
    task_means = []
    for low, exp, high in tasks:
        mu, sigma = fit_shifted_lognormal(low, exp, high, z_95)
        task_means.append(low + np.exp(mu + sigma**2 / 2))

    project = make_parallel_project_from_estimates(tasks)
    results = simulate(project, iterations=STAT_ITERATIONS_FULL, seed=42)

    duration_mean = np.mean(results.durations)
    assert duration_mean > max(task_means) - 1.0  # Allow small tolerance
    assert duration_mean < sum(task_means) + 1.0
```

---

## Category 4: Risk Impact Proportionality Tests

These tests verify that the risk evaluation system correctly applies probabilistic impacts.

### 4.1 Risk Trigger Rate

**Property:** A risk with probability *p* should trigger in approximately *p × N* out of *N* iterations.

```python
def test_risk_trigger_rate():
    """Risk should trigger at the declared probability."""
    probability = 0.30
    project = make_project_with_single_risk(probability=probability, impact_hours=100)
    results = simulate(project, iterations=STAT_ITERATIONS_FULL, seed=42)

    impacts = results.risk_impacts["t1"]
    trigger_count = np.sum(impacts > 0)

    assert_proportion_close(
        trigger_count, len(impacts), probability,
        label="Risk trigger rate"
    )
```

### 4.2 Risk Impact Magnitude When Triggered

**Property:** When an absolute risk triggers, its impact should be exactly the declared value (in hours, after unit conversion).

```python
def test_absolute_risk_impact_exact():
    """Absolute risk impact should be exactly the declared value when triggered."""
    impact_hours = 40.0
    project = make_project_with_single_risk(probability=1.0, impact_hours=impact_hours)
    results = simulate(project, iterations=100, seed=42)

    impacts = results.risk_impacts["t1"]
    # All should trigger (p=1.0) and all should be exactly impact_hours
    assert np.allclose(impacts, impact_hours), (
        f"Expected all impacts = {impact_hours}, got range [{impacts.min()}, {impacts.max()}]"
    )
```

### 4.3 Percentage Risk Impact Proportional to Base Duration

**Property:** A percentage risk should add `base_duration × percentage / 100` when triggered.

```python
def test_percentage_risk_proportional():
    """Percentage risk impact should scale with base task duration."""
    project = make_project_with_percentage_risk(percentage=25.0, probability=1.0)
    results = simulate(project, iterations=STAT_ITERATIONS_CI, seed=42)

    task_durations = results.task_durations["t1"]
    impacts = results.risk_impacts["t1"]

    # impact ≈ (task_duration - impact) × 0.25
    # Since final_duration = base + impact, base = final - impact
    base_durations = task_durations - impacts
    expected_impacts = base_durations * 0.25

    assert np.allclose(impacts, expected_impacts, rtol=1e-6), (
        "Percentage risk impact not proportional to base duration"
    )
```

### 4.4 Mean Duration Increase from Risk

**Property:** Adding a risk with probability *p* and absolute impact *I* increases the mean task duration by approximately *p × I*.

```python
def test_risk_increases_mean_by_expected_value():
    """Mean duration increase from risk ≈ probability × impact."""
    p, impact = 0.40, 50.0
    expected_increase = p * impact

    project_no_risk = make_single_task_project(low=20, expected=40, high=80)
    project_with_risk = make_single_task_project(
        low=20, expected=40, high=80,
        risks=[{"probability": p, "impact": impact}]
    )

    results_no = simulate(project_no_risk, iterations=STAT_ITERATIONS_FULL, seed=42)
    results_yes = simulate(project_with_risk, iterations=STAT_ITERATIONS_FULL, seed=42)

    mean_increase = np.mean(results_yes.task_durations["t1"]) - np.mean(results_no.task_durations["t1"])

    assert_mean_close(
        results_yes.task_durations["t1"] - results_no.task_durations["t1"],
        expected_increase,
        label="Risk mean increase ≈ p × I"
    )
```

**Note:** This test uses different seeds for the two runs because risk evaluation consumes additional random draws, which shifts the RNG state and makes same-seed comparison invalid for task durations. The statistical test (`assert_mean_close`) handles this by testing convergence rather than exact equality.

### 4.5 Multiple Risk Accumulation

**Property:** Multiple independent risks should accumulate additively. With risks (p₁, I₁) and (p₂, I₂), the expected total impact ≈ p₁I₁ + p₂I₂.

### 4.6 Zero-Probability Risk Has No Effect

**Property:** A risk with `probability: 0.0` should never trigger. Duration distributions with and without it should be identical (same seed).

```python
def test_zero_probability_risk_no_effect():
    """Risk with p=0 should never trigger."""
    project = make_project_with_single_risk(probability=0.0, impact_hours=1000)
    results = simulate(project, iterations=STAT_ITERATIONS_CI, seed=42)
    impacts = results.risk_impacts["t1"]
    assert np.all(impacts == 0.0), "Zero-probability risk triggered!"
```

### 4.7 Certain Risk Always Triggers

**Property:** A risk with `probability: 1.0` should trigger in every iteration.

### 4.8 Project-Level Risk Independence

**Property:** Project-level risks are evaluated on the final project duration and added after scheduling. Their expected value (p × I) should appear as a shift in the project duration distribution.

---

## Category 5: Scheduling Invariant Tests

These tests verify structural properties of the scheduling algorithms.

### 5.1 Chain Project Duration = Sum of Task Durations

**Property:** For a pure chain (A → B → C → ...), project duration = sum of all task durations in every iteration, because no parallelism is possible.

```python
def test_chain_duration_equals_sum():
    """For a pure chain, project duration = sum of task durations per iteration."""
    project = make_chain_project(n_tasks=5)
    results = simulate(project, iterations=STAT_ITERATIONS_CI, seed=42)

    task_sum = np.zeros(results.iterations)
    for task_id, durations in results.task_durations.items():
        task_sum += durations

    assert np.allclose(results.durations, task_sum, atol=1e-6), (
        "Chain project duration ≠ sum of task durations"
    )
```

**Note:** This also implicitly validates that project-level risks with probability 0 are properly excluded. If the project has project-level risks, account for them separately.

### 5.2 Parallel Project Duration = Max of Task Durations

**Property:** For fully parallel tasks (no dependencies), project duration = max of task durations per iteration.

```python
def test_parallel_duration_equals_max():
    """For independent parallel tasks, project duration = max(task durations)."""
    project = make_parallel_project(n_parallel=4)
    results = simulate(project, iterations=STAT_ITERATIONS_CI, seed=42)

    task_max = np.zeros(results.iterations)
    for task_id, durations in results.task_durations.items():
        task_max = np.maximum(task_max, durations)

    assert np.allclose(results.durations, task_max, atol=1e-6), (
        "Parallel project duration ≠ max of task durations"
    )
```

### 5.3 Diamond DAG Critical Path

**Property:** For a diamond graph (A → B, A → C, B → D, C → D), the critical path goes through whichever of B or C takes longer. Over many iterations, if B has a much larger expected duration than C, B should appear on the critical path more often.

```python
def test_diamond_critical_path_frequency():
    """In a diamond DAG, the longer branch should be on the critical path more often."""
    # B: large task, C: small task
    project = make_diamond_project(
        b_estimate=(40, 80, 150),  # Large
        c_estimate=(5, 10, 20),    # Small
    )
    results = simulate(project, iterations=STAT_ITERATIONS_CI, seed=42)

    freq_b = results.critical_path_frequency.get("B", 0) / results.iterations
    freq_c = results.critical_path_frequency.get("C", 0) / results.iterations

    # B should dominate the critical path
    assert freq_b > 0.80, f"Expected B critical path freq > 0.80, got {freq_b:.3f}"
    assert freq_b > freq_c, "Longer branch B should be critical more often than shorter branch C"
```

### 5.4 Effort = Duration for Chain, Effort > Duration for Parallel

**Property:**
- Chain: `effort[i] == duration[i]` for every iteration.
- Parallel (≥2 tasks): `effort[i] > duration[i]` for most iterations.

### 5.5 Resource Constraint Increases Duration

**Property:** Adding resource constraints to a project with parallel tasks should increase (or not decrease) the mean project duration compared to unconstrained scheduling, because resource contention forces serialization.

```python
def test_resource_constraint_increases_duration():
    """Resource constraints should not decrease mean project duration."""
    project_unconstrained = make_parallel_project(n_parallel=4)  # No resources
    project_constrained = make_constrained_parallel_project(
        n_parallel=4, n_resources=2  # 4 tasks but only 2 resources
    )

    results_unc = simulate(project_unconstrained, iterations=STAT_ITERATIONS_CI, seed=42)
    results_con = simulate(project_constrained, iterations=STAT_ITERATIONS_CI, seed=42)

    assert np.mean(results_con.durations) >= np.mean(results_unc.durations) - 1.0
```

### 5.6 Slack Sum Property

**Property:** For dependency-only scheduling, the sum of slack values across all tasks should be consistent: non-critical tasks have positive slack, critical tasks have zero slack.

### 5.7 Peak Parallelism Bounds

**Property:** For a project with *n* independent tasks, `max_parallel_tasks` should be *n* (dependency-only). For a pure chain, `max_parallel_tasks` should be 1.

```python
def test_peak_parallelism_chain_is_one():
    """Pure chain should have peak parallelism = 1."""
    project = make_chain_project(n_tasks=5)
    results = simulate(project, iterations=100, seed=42)
    assert results.max_parallel_tasks == 1

def test_peak_parallelism_parallel_equals_n():
    """Fully parallel tasks should have peak parallelism = n."""
    n = 6
    project = make_parallel_project(n_parallel=n)
    results = simulate(project, iterations=100, seed=42)
    assert results.max_parallel_tasks == n
```

### 5.8 Calendar Delays Are Non-Negative

**Property:** `calendar_delay_time_hours ≥ 0` always.

### 5.9 Resource Wait Time Zero Without Constraints

**Property:** `resource_wait_time_hours == 0` when `schedule_mode == "dependency_only"`.

---

## Category 6: Sensitivity and Correlation Tests

These tests verify that sensitivity analysis correctly identifies structural relationships.

### 6.1 Single Critical Task Has Highest Sensitivity

**Property:** In a project where one task dominates the critical path and has the widest variance, it should have the highest Spearman correlation with project duration.

```python
def test_dominant_task_has_highest_sensitivity():
    """The task with highest variance on the critical path should have highest sensitivity."""
    # Task A: small and certain (low=9, expected=10, high=11)
    # Task B: large and uncertain (low=20, expected=60, high=200)
    # Chain: A -> B
    project = make_chain_project_from_estimates([
        (9, 10, 11),     # A: narrow
        (20, 60, 200),   # B: wide
    ])
    results = simulate(project, iterations=STAT_ITERATIONS_CI, seed=42)

    assert results.sensitivity["t2"] > results.sensitivity["t1"], (
        "Wide-variance task should have higher sensitivity than narrow-variance task"
    )
    assert results.sensitivity["t2"] > 0.8, (
        f"Dominant task should have very high sensitivity, got {results.sensitivity['t2']:.3f}"
    )
```

### 6.2 Independent Parallel Task Sensitivity

**Property:** For independent parallel tasks of similar size, all should have moderate positive sensitivity. None should dominate.

### 6.3 Zero-Variance Task Has Zero Sensitivity

**Property:** A task with `low == expected == high` (degenerate distribution) produces constant durations and should have sensitivity = 0.

```python
def test_constant_task_zero_sensitivity():
    """A deterministic task should have zero sensitivity."""
    project = make_chain_project_from_estimates([
        (10, 10, 10),    # Constant — no variance
        (20, 60, 200),   # Variable
    ])
    results = simulate(project, iterations=STAT_ITERATIONS_CI, seed=42)
    assert abs(results.sensitivity["t1"]) < 0.05, (
        f"Constant task should have ~0 sensitivity, got {results.sensitivity['t1']:.3f}"
    )
```

### 6.4 Effort-Duration Correlation Is Positive

**Property:** Total effort and project duration should be positively correlated (Spearman ρ > 0), because longer tasks increase both.

```python
def test_effort_duration_positive_correlation():
    """Effort and duration should be positively correlated."""
    project = make_sample_project()
    results = simulate(project, iterations=STAT_ITERATIONS_CI, seed=42)
    assert_spearman_positive(
        results.effort_durations, results.durations, min_rho=0.3,
        label="Effort-duration correlation"
    )
```

### 6.5 Off-Critical-Path Task Has Low Sensitivity

**Property:** A task that is never on the critical path (because a parallel branch always dominates) should have near-zero sensitivity to project duration.

---

## Category 7: Composition and Scaling Tests

These tests verify that changes to project structure produce predictable directional effects.

### 7.1 Adding a Risk Increases Mean Duration

**Property:** Adding a risk with p > 0 and impact > 0 to any task should increase (or not decrease) the mean project duration.

```python
def test_adding_risk_increases_mean():
    """Adding a risk should weakly increase mean project duration."""
    project_no_risk = make_chain_project_from_estimates([(10, 20, 50), (15, 30, 70)])
    project_with_risk = make_chain_project_from_estimates(
        [(10, 20, 50), (15, 30, 70)],
        risks_on_task=1,  # Add risk to task 1
        risk_probability=0.4,
        risk_impact_hours=20,
    )

    results_no = simulate(project_no_risk, iterations=STAT_ITERATIONS_FULL, seed=42)
    results_yes = simulate(project_with_risk, iterations=STAT_ITERATIONS_FULL, seed=42)

    # Mean should increase by approximately p * I = 0.4 * 20 = 8 hours
    assert np.mean(results_yes.durations) > np.mean(results_no.durations) - 1.0
```

### 7.2 Adding a Parallel Task Does Not Increase Effort Mean (Much)

Wait — adding any task increases effort. Let me restate:

### 7.2 Adding a Parallel Task Increases Effort But Not Duration Proportionally

**Property:** Adding an independent parallel task with a small estimate should:
- Increase mean effort by approximately the task's expected effort.
- Increase mean duration by less than the task's expected duration (because it runs in parallel).

### 7.3 Increasing `high` Estimate Increases Variance

**Property:** Widening the estimate range (increasing `high` while keeping `low` and `expected` constant) should increase the variance of the duration distribution.

```python
def test_wider_estimate_increases_variance():
    """Widening the high estimate should increase duration variance."""
    project_narrow = make_single_task_project(low=10, expected=30, high=60)
    project_wide = make_single_task_project(low=10, expected=30, high=120)

    results_narrow = simulate(project_narrow, iterations=STAT_ITERATIONS_CI, seed=42)
    results_wide = simulate(project_wide, iterations=STAT_ITERATIONS_CI, seed=42)

    var_narrow = np.var(results_narrow.durations)
    var_wide = np.var(results_wide.durations)
    assert var_wide > var_narrow, (
        f"Wider estimate should have higher variance: narrow={var_narrow:.2f}, wide={var_wide:.2f}"
    )
```

### 7.4 More Resources Reduces Constrained Duration

**Property:** For a resource-constrained project, adding more resources (with sufficient tasks to benefit) should reduce or maintain mean project duration.

### 7.5 Uncertainty Factor Monotonicity

**Property:** A "worse" uncertainty factor level (e.g., `requirements_maturity: low` vs `high`) should produce higher mean duration.

```python
def test_uncertainty_factor_monotonicity():
    """Worse uncertainty levels should increase mean duration."""
    results = {}
    for level in ["high", "medium", "low"]:
        project = make_single_task_project(
            low=10, expected=30, high=80,
            uncertainty_factors={"requirements_maturity": level}
        )
        results[level] = simulate(project, iterations=STAT_ITERATIONS_CI, seed=42)

    mean_high = np.mean(results["high"].durations)
    mean_medium = np.mean(results["medium"].durations)
    mean_low = np.mean(results["low"].durations)

    # high (best) < medium < low (worst) for requirements_maturity
    assert mean_high <= mean_medium + 0.1
    assert mean_medium <= mean_low + 0.1
```

### 7.6 Chain Length Scaling

**Property:** Doubling the number of tasks in a chain should approximately double the mean project duration (assuming similar estimates).

### 7.7 Percentile Ordering

**Property:** Percentiles must be monotonically non-decreasing: P10 ≤ P25 ≤ P50 ≤ P75 ≤ P90 ≤ P95 ≤ P99. Always.

```python
def test_percentile_ordering():
    """Percentiles must be monotonically non-decreasing."""
    project = make_sample_project()
    results = simulate(project, iterations=STAT_ITERATIONS_CI, seed=42)

    levels = [10, 25, 50, 75, 80, 85, 90, 95, 99]
    values = [results.percentile(p) for p in levels]
    for i in range(1, len(values)):
        assert values[i] >= values[i-1] - 1e-9, (
            f"P{levels[i]}={values[i]:.2f} < P{levels[i-1]}={values[i-1]:.2f}"
        )
```

### 7.8 Effort Percentile Ordering

Same as 7.7 but for effort percentiles.

### 7.9 P50 Close to Median, Mean Between P40 and P60

**Property:** The 50th percentile should equal the median. For right-skewed distributions, the mean should be above the median.

---

## Category 8: Reproducibility and Seed Tests

### 8.1 Same Seed Produces Identical Results

```python
def test_same_seed_identical_results():
    """Same seed must produce bit-identical results."""
    project = make_sample_project()
    results1 = simulate(project, iterations=1000, seed=12345)
    results2 = simulate(project, iterations=1000, seed=12345)

    assert np.array_equal(results1.durations, results2.durations)
    assert np.array_equal(results1.effort_durations, results2.effort_durations)
    for task_id in results1.task_durations:
        assert np.array_equal(
            results1.task_durations[task_id],
            results2.task_durations[task_id]
        )
```

### 8.2 Different Seeds Produce Different Results

```python
def test_different_seeds_produce_different_results():
    """Different seeds should produce different duration arrays."""
    project = make_sample_project()
    results1 = simulate(project, iterations=1000, seed=42)
    results2 = simulate(project, iterations=1000, seed=43)

    assert not np.array_equal(results1.durations, results2.durations)
```

### 8.3 Results Stable Across Iterations

**Property:** Running with 5,000 vs 10,000 iterations should produce similar statistics (means within CI, percentiles within tolerance). This tests that results don't depend on the iteration count in unexpected ways.

### 8.4 Two-Pass Reproducibility

**Property:** Two-pass scheduling with the same seed should produce identical results.

---

## Category 9: Complex Project Stress Tests

These tests use realistic multi-task projects with mixed features.

### 9.1 Large Project Convergence

**Property:** A 100-task project should produce finite, non-degenerate results. Mean should be reasonable given the estimates. No NaN or Inf values.

```python
def test_large_project_no_degenerate_output():
    """100-task project should produce valid results."""
    project = load_project("examples/large_project_100_tasks.yaml")
    results = simulate(project, iterations=STAT_ITERATIONS_CI, seed=42)

    assert not np.any(np.isnan(results.durations))
    assert not np.any(np.isinf(results.durations))
    assert results.mean > 0
    assert results.std_dev > 0
    assert results.std_dev < results.mean * 10  # Sanity: std_dev not absurdly large
```

### 9.2 Mixed Estimate Types

**Property:** A project mixing t-shirt sizes, story points, and explicit estimates should produce valid results. All estimate types are resolved to hours before sampling.

### 9.3 Full Feature Project

**Property:** A project with all features enabled (resources, calendars, holidays, sickness, risks, uncertainty factors, two-pass scheduling) should produce valid results with all diagnostics populated.

```python
def test_full_feature_project():
    """Project with every feature should produce complete results."""
    project = load_project("tests/test_probabilistic/fixtures/full_feature.yaml")
    results = simulate(project, iterations=STAT_ITERATIONS_CI, seed=42, two_pass=True)

    # Basic validity
    assert results.mean > 0
    assert results.iterations == STAT_ITERATIONS_CI

    # Resource diagnostics populated
    assert results.resource_constraints_active is True
    assert results.resource_utilization > 0
    assert results.resource_wait_time_hours >= 0
    assert results.calendar_delay_time_hours >= 0

    # Two-pass trace populated
    assert results.two_pass_trace is not None
    assert results.two_pass_trace.enabled is True

    # Sensitivity populated for all tasks
    for task in project.tasks:
        assert task.id in results.sensitivity

    # Critical path makes sense
    total_cp_freq = sum(results.critical_path_frequency.values())
    assert total_cp_freq > 0
```

### 9.4 Sprint Planning Convergence

**Property:** Sprint simulation should produce finite sprint counts with reasonable statistics.

---

## Category 10: Cross-Validation Tests

These tests compare results across different modes to catch inconsistencies.

### 10.1 Dependency-Only vs Resource-Constrained (Single Resource, Sequential Tasks)

**Property:** With exactly one resource and sequential tasks, resource-constrained scheduling should produce the same duration as dependency-only scheduling (the single resource doesn't create additional contention beyond what dependencies already enforce).

```python
def test_single_resource_matches_dependency_only():
    """With one resource and a chain, constrained ≈ dependency-only."""
    chain_project = make_chain_project(n_tasks=4)
    constrained_project = make_chain_project(n_tasks=4, resources=["alice"])

    results_dep = simulate(chain_project, iterations=STAT_ITERATIONS_CI, seed=42)
    results_con = simulate(constrained_project, iterations=STAT_ITERATIONS_CI, seed=42)

    # Means should be very close (calendar effects may add small difference)
    assert abs(results_dep.mean - results_con.mean) / results_dep.mean < 0.05
```

### 10.2 Two-Pass vs Single-Pass (No Resources)

**Property:** Without resources, two-pass scheduling should produce identical results to single-pass, because there are no resources to re-prioritize.

### 10.3 Effort Consistency Across Modes

**Property:** Total effort (sum of task durations) should be independent of scheduling mode, because scheduling affects *when* tasks execute but not *how long* they take.

```python
def test_effort_independent_of_scheduling_mode():
    """Effort should be the same regardless of scheduling mode."""
    project_dep = make_parallel_project(n_parallel=4)
    project_con = make_constrained_parallel_project(n_parallel=4, n_resources=2)

    results_dep = simulate(project_dep, iterations=STAT_ITERATIONS_CI, seed=42)
    results_con = simulate(project_con, iterations=STAT_ITERATIONS_CI, seed=42)

    # Effort means should be statistically indistinguishable
    # (different scheduling, same task durations)
    assert abs(np.mean(results_dep.effort_durations) - np.mean(results_con.effort_durations)) / \
           np.mean(results_dep.effort_durations) < 0.05
```

**Note:** This test uses different seeds implicitly (different RNG consumption patterns due to resource scheduling), so it checks statistical closeness rather than exact equality.

### 10.4 Sensitivity Stability

**Property:** Running the same project twice with different seeds should produce sensitivity rankings that are broadly consistent (top-3 tasks should overlap between runs for a well-structured project).

---

## Category 11: Adversarial and Edge Case Tests

### 11.1 Single Task Project

**Property:** With one task and no risks, project duration = task duration in every iteration.

### 11.2 All Tasks Zero Duration

**Property:** If all estimates are (0, 0, 0) (degenerate), the project should complete instantly. *(Check if the model allows this or requires positive estimates.)*

### 11.3 Maximum Risk Impact

**Property:** A project where every task has a 100% probability risk with a large impact should still produce finite results with duration = base + impact.

### 11.4 Deeply Nested Chain

**Property:** A chain of 50 tasks should complete without stack overflow in critical-path tracing, and produce valid results.

### 11.5 Wide Fan-Out / Fan-In

**Property:** A project with one root task, 20 parallel tasks depending on it, and one final task depending on all 20 should produce valid results with `max_parallel_tasks = 20`.

### 11.6 All Tasks on Critical Path

**Property:** For a pure chain, every task should have criticality index = 1.0 (on the critical path in 100% of iterations).

```python
def test_chain_all_tasks_critical():
    """In a pure chain, every task should always be on the critical path."""
    project = make_chain_project(n_tasks=5)
    results = simulate(project, iterations=STAT_ITERATIONS_CI, seed=42)

    for task in project.tasks:
        freq = results.critical_path_frequency.get(task.id, 0) / results.iterations
        assert freq > 0.99, f"Task {task.id} critical path freq = {freq:.3f}, expected ~1.0"
```

---

## Mathematical Appendix: Analytical References

### Shifted Lognormal Moments

For $Y = \text{low} + X$ where $X \sim \text{Lognormal}(\mu, \sigma)$:

$$E[Y] = \text{low} + e^{\mu + \sigma^2/2}$$

$$\text{Var}[Y] = e^{2\mu + \sigma^2}(e^{\sigma^2} - 1)$$

$$\text{Skewness}[Y] = (e^{\sigma^2} + 2)\sqrt{e^{\sigma^2} - 1}$$

$$\text{Mode}[Y] = \text{low} + e^{\mu - \sigma^2}$$

$$P(Y \le y) = \Phi\!\left(\frac{\ln(y - \text{low}) - \mu}{\sigma}\right) \quad \text{for } y > \text{low}$$

### Triangular Distribution Moments

For $Y \sim \text{Triangular}(a, c, b)$ where $a = \text{low}$, $c = \text{expected}$, $b = \text{high}$:

$$E[Y] = \frac{a + b + c}{3}$$

$$\text{Var}[Y] = \frac{a^2 + b^2 + c^2 - ab - ac - bc}{18}$$

### Risk Impact Expected Value

For a risk with probability $p$ and absolute impact $I$:

$$E[\text{impact}] = p \cdot I$$

$$\text{Var}[\text{impact}] = p \cdot I^2 - (p \cdot I)^2 = p(1-p) \cdot I^2$$

For a percentage risk with factor $f$ applied to base duration $D$:

$$E[\text{impact}] = p \cdot f \cdot E[D]$$

### Sum of Independent Random Variables (Effort)

For independent tasks $T_1, T_2, \ldots, T_n$:

$$E\!\left[\sum T_i\right] = \sum E[T_i]$$

$$\text{Var}\!\left[\sum T_i\right] = \sum \text{Var}[T_i]$$

### Maximum of Independent Random Variables (Parallel Duration)

For $M = \max(T_1, \ldots, T_n)$:

$$P(M \le t) = \prod_{i=1}^{n} P(T_i \le t)$$

$$E[M] \ge \max_i E[T_i] \quad \text{(always)}$$

No closed-form for $E[M]$ with lognormal variables, but Monte Carlo estimation is exact in the limit.

---

## Implementation Considerations

### CI Integration

- **Fast suite** (`@pytest.mark.probabilistic`): 5,000 iterations, ~2 minutes total. Run on every PR.
- **Full suite** (`@pytest.mark.probabilistic_full`): 100,000 iterations, ~30 minutes. Run nightly and on release branches.
- **Seed pinning**: All tests use fixed seeds for reproducibility. A test that fails intermittently indicates either a real bug or insufficient iterations — both warrant investigation.

### False Positive Rate Management

With α = 0.001 per test and ~80 tests:

$$P(\text{≥1 false positive}) = 1 - (1 - 0.001)^{80} \approx 0.077$$

An ~8% chance of at least one false positive per full run is acceptable — a failing test should be investigated but may occasionally be a statistical fluke. If a test fails, re-running with a different seed will distinguish a true bug (fails again) from a fluke (passes).

For the CI fast suite (lower iterations), consider using α = 0.01 and looser tolerances to reduce intermittent failures while maintaining high sensitivity to real bugs.

### Test Project Fixtures

Create dedicated YAML fixtures in `tests/test_probabilistic/fixtures/` rather than reusing example files. This ensures test projects are purpose-built with known analytical properties:

- `chain_3.yaml`: Pure 3-task chain with explicit hour estimates.
- `chain_10.yaml`: Longer chain for scaling tests.
- `parallel_5.yaml`: Five independent parallel tasks.
- `diamond.yaml`: Classic diamond dependency graph.
- `fan_out_20.yaml`: One root → 20 parallel → one sink.
- `constrained_4_tasks_2_resources.yaml`: Resource contention scenario.
- `risk_heavy.yaml`: Multiple risks on every task.
- `mixed_estimates.yaml`: T-shirt sizes, story points, and explicit estimates.
- `full_feature.yaml`: Every feature enabled.

### Shared Helper Functions

Build project-construction helpers that make it trivial to create test projects programmatically:

```python
def make_chain_project(n_tasks: int, estimate=(10, 20, 50), unit="hours") -> Project: ...
def make_parallel_project(n_parallel: int, estimate=(10, 20, 50)) -> Project: ...
def make_diamond_project(b_estimate=(10, 20, 50), c_estimate=(10, 20, 50)) -> Project: ...
def make_single_task_project(low, expected, high, risks=None, uncertainty_factors=None) -> Project: ...
def make_constrained_parallel_project(n_parallel, n_resources, estimate=(10, 20, 50)) -> Project: ...
```

These helpers construct `Project` objects directly (not via YAML parsing) to isolate simulation logic from parser logic.

### Runtime Performance

At 100,000 iterations, a 10-task project simulation takes ~10-30 seconds. The full test suite with ~80 tests at 5,000 iterations each should complete in ~3 minutes. The full verification suite at 100,000 iterations should complete in ~40 minutes.

Parallelization via `pytest-xdist` (`-n auto`) is safe because each test uses its own seed and `SimulationEngine` instance.

## Future Work

- **Mutation testing**: Automatically introduce small bugs (e.g., change `+` to `-` in risk impact, swap `min`/`max` in scheduling) and verify that the probabilistic test suite detects them. This validates the sensitivity of the tests themselves.
- **Property-based testing with Hypothesis**: Use the Hypothesis library to generate random project structures and verify invariants hold for arbitrary inputs.
- **Regression baselines**: Store golden statistics (mean, P50, P90) for reference projects at a fixed seed. Any change to the engine that shifts these values beyond a tolerance triggers a review, ensuring unintentional behavioral changes are caught.
- **Coverage-guided fuzzing**: Generate edge-case project inputs (extreme estimate ratios, many risks, deep DAGs) to stress-test the engine.
