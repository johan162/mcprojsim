"""Tests for monetary cost estimation feature."""

import warnings
from datetime import date

import numpy as np
import pytest

from mcprojsim.config import CostConfig
from mcprojsim.models.project import (
    Project,
    ProjectMetadata,
    Risk,
    ResourceSpec,
    Task,
    TaskEstimate,
)
from mcprojsim.models.simulation import SimulationResults
from mcprojsim.simulation.engine import SimulationEngine
from mcprojsim.simulation.risk_evaluator import RiskEvaluator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_single_task_project(
    *,
    default_hourly_rate=None,
    overhead_rate=0.0,
    currency=None,
    fixed_cost=None,
    task_risks=None,
    project_risks=None,
    resources=None,
    task_resource_names=None,
    estimate_low=8.0,
    estimate_expected=8.0,
    estimate_high=8.001,  # slightly above expected to satisfy numpy triangular left<right
):
    """Return a minimal one-task project with configurable cost fields."""
    task = Task(
        id="t1",
        name="Task 1",
        estimate=TaskEstimate(
            low=estimate_low, expected=estimate_expected, high=estimate_high
        ),
        fixed_cost=fixed_cost,
        risks=task_risks or [],
        resources=task_resource_names or [],
    )
    return Project(
        project=ProjectMetadata(
            name="CostTest",
            start_date=date(2025, 1, 6),
            default_hourly_rate=default_hourly_rate,
            overhead_rate=overhead_rate,
            currency=currency,
        ),
        tasks=[task],
        project_risks=project_risks or [],
        resources=resources or [],
    )


def make_results_with_costs(costs_array: np.ndarray) -> SimulationResults:
    """Build a minimal SimulationResults with a given cost array."""
    n = len(costs_array)
    durations = np.random.RandomState(42).uniform(80, 120, n)
    r = SimulationResults(
        iterations=n,
        project_name="test",
        durations=durations,
        costs=costs_array,
        cost_percentiles={},
    )
    r.calculate_statistics()
    r.calculate_cost_statistics()
    return r


def _run(
    project: Project, *, iterations: int = 500, seed: int = 42
) -> SimulationResults:
    engine = SimulationEngine(
        iterations=iterations, random_seed=seed, show_progress=False
    )
    return engine.run(project)


# ---------------------------------------------------------------------------
# TestCostModelValidation
# ---------------------------------------------------------------------------


class TestCostModelValidation:
    """Pydantic field validation for all new cost fields."""

    # --- ProjectMetadata.default_hourly_rate ---

    def test_default_hourly_rate_none_ok(self):
        meta = ProjectMetadata(
            name="P", start_date=date(2025, 1, 1), default_hourly_rate=None
        )
        assert meta.default_hourly_rate is None

    def test_default_hourly_rate_zero_ok(self):
        meta = ProjectMetadata(
            name="P", start_date=date(2025, 1, 1), default_hourly_rate=0
        )
        assert meta.default_hourly_rate == 0.0

    def test_default_hourly_rate_positive_ok(self):
        meta = ProjectMetadata(
            name="P", start_date=date(2025, 1, 1), default_hourly_rate=150.0
        )
        assert meta.default_hourly_rate == 150.0

    def test_default_hourly_rate_negative_raises(self):
        with pytest.raises(Exception):
            ProjectMetadata(
                name="P", start_date=date(2025, 1, 1), default_hourly_rate=-1.0
            )

    # --- ProjectMetadata.overhead_rate ---

    def test_overhead_rate_zero_ok(self):
        meta = ProjectMetadata(name="P", start_date=date(2025, 1, 1), overhead_rate=0.0)
        assert meta.overhead_rate == 0.0

    def test_overhead_rate_max_ok(self):
        meta = ProjectMetadata(name="P", start_date=date(2025, 1, 1), overhead_rate=3.0)
        assert meta.overhead_rate == 3.0

    def test_overhead_rate_negative_raises(self):
        with pytest.raises(Exception):
            ProjectMetadata(name="P", start_date=date(2025, 1, 1), overhead_rate=-0.01)

    def test_overhead_rate_above_max_raises(self):
        with pytest.raises(Exception):
            ProjectMetadata(name="P", start_date=date(2025, 1, 1), overhead_rate=3.01)

    # --- ProjectMetadata.currency ---

    def test_currency_valid_iso_ok(self):
        meta = ProjectMetadata(name="P", start_date=date(2025, 1, 1), currency="USD")
        assert meta.currency == "USD"

    def test_currency_none_ok(self):
        meta = ProjectMetadata(name="P", start_date=date(2025, 1, 1), currency=None)
        assert meta.currency is None

    def test_currency_invalid_warns_not_raises(self):
        # Non-[A-Z]{3} format should warn, not raise
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            meta = ProjectMetadata(
                name="P", start_date=date(2025, 1, 1), currency="eur"
            )
        assert meta.currency == "eur"
        assert any(issubclass(w.category, UserWarning) for w in caught)

    def test_currency_numeric_string_warns_not_raises(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            meta = ProjectMetadata(
                name="P", start_date=date(2025, 1, 1), currency="123"
            )
        assert meta.currency == "123"
        assert any(issubclass(w.category, UserWarning) for w in caught)

    # --- ResourceSpec.hourly_rate ---

    def test_resource_hourly_rate_none_ok(self):
        r = ResourceSpec(name="Alice", hourly_rate=None)
        assert r.hourly_rate is None

    def test_resource_hourly_rate_zero_ok(self):
        r = ResourceSpec(name="Alice", hourly_rate=0)
        assert r.hourly_rate == 0.0

    def test_resource_hourly_rate_positive_ok(self):
        r = ResourceSpec(name="Alice", hourly_rate=200.0)
        assert r.hourly_rate == 200.0

    def test_resource_hourly_rate_negative_raises(self):
        with pytest.raises(Exception):
            ResourceSpec(name="Alice", hourly_rate=-50.0)

    # --- Task.fixed_cost ---

    def test_task_fixed_cost_none_ok(self):
        t = Task(id="t1", name="T", estimate=TaskEstimate(low=1, expected=2, high=3))
        assert t.fixed_cost is None

    def test_task_fixed_cost_positive_ok(self):
        t = Task(
            id="t1",
            name="T",
            estimate=TaskEstimate(low=1, expected=2, high=3),
            fixed_cost=1000.0,
        )
        assert t.fixed_cost == 1000.0

    def test_task_fixed_cost_zero_ok(self):
        t = Task(
            id="t1",
            name="T",
            estimate=TaskEstimate(low=1, expected=2, high=3),
            fixed_cost=0.0,
        )
        assert t.fixed_cost == 0.0

    def test_task_fixed_cost_negative_ok(self):
        # Negative fixed_cost = subsidy/credit — allowed
        t = Task(
            id="t1",
            name="T",
            estimate=TaskEstimate(low=1, expected=2, high=3),
            fixed_cost=-500.0,
        )
        assert t.fixed_cost == -500.0

    # --- Risk.cost_impact ---

    def test_risk_cost_impact_none_ok(self):
        r = Risk(id="r1", name="R", probability=0.1, impact=8.0)
        assert r.cost_impact is None

    def test_risk_cost_impact_positive_ok(self):
        r = Risk(id="r1", name="R", probability=0.1, impact=8.0, cost_impact=5000.0)
        assert r.cost_impact == 5000.0

    def test_risk_cost_impact_negative_ok(self):
        # Negative = cost saving
        r = Risk(id="r1", name="R", probability=0.1, impact=8.0, cost_impact=-1000.0)
        assert r.cost_impact == -1000.0

    def test_risk_cost_impact_zero_ok(self):
        r = Risk(id="r1", name="R", probability=0.1, impact=8.0, cost_impact=0.0)
        assert r.cost_impact == 0.0

    # --- CostConfig defaults ---

    def test_cost_config_defaults(self):
        cfg = CostConfig()
        assert cfg.default_hourly_rate is None
        assert cfg.overhead_rate == 0.0
        assert cfg.currency == "EUR"
        assert cfg.include_in_output is True

    def test_cost_config_negative_overhead_raises(self):
        with pytest.raises(Exception):
            CostConfig(overhead_rate=-0.1)

    def test_cost_config_overhead_above_max_raises(self):
        with pytest.raises(Exception):
            CostConfig(overhead_rate=3.01)

    def test_cost_config_negative_hourly_rate_raises(self):
        with pytest.raises(Exception):
            CostConfig(default_hourly_rate=-10.0)


# ---------------------------------------------------------------------------
# TestRiskEvaluatorWithCost
# ---------------------------------------------------------------------------


class TestRiskEvaluatorWithCost:
    """Tests for evaluate_risk_with_cost and evaluate_risks_with_cost."""

    def _make_risk(self, probability, time_impact=8.0, cost_impact=None):
        return Risk(
            id="r1",
            name="Risk",
            probability=probability,
            impact=time_impact,
            cost_impact=cost_impact,
        )

    def test_risk_not_triggered_returns_zero_time_and_cost(self):
        evaluator = RiskEvaluator(np.random.RandomState(0))
        risk = self._make_risk(probability=0.0, cost_impact=1000.0)
        time_impact, cost_impact = evaluator.evaluate_risk_with_cost(risk)
        assert time_impact == 0.0
        assert cost_impact == 0.0

    def test_risk_always_triggered_returns_both_impacts(self):
        evaluator = RiskEvaluator(np.random.RandomState(0))
        risk = self._make_risk(probability=1.0, time_impact=16.0, cost_impact=5000.0)
        time_impact, cost_impact = evaluator.evaluate_risk_with_cost(risk)
        assert time_impact == pytest.approx(16.0)
        assert cost_impact == pytest.approx(5000.0)

    def test_risk_triggered_no_cost_impact_returns_zero_cost(self):
        evaluator = RiskEvaluator(np.random.RandomState(0))
        risk = self._make_risk(probability=1.0, time_impact=8.0, cost_impact=None)
        time_impact, cost_impact = evaluator.evaluate_risk_with_cost(risk)
        assert time_impact == pytest.approx(8.0)
        assert cost_impact == 0.0

    def test_risk_negative_cost_impact_returns_negative_when_triggered(self):
        evaluator = RiskEvaluator(np.random.RandomState(0))
        risk = self._make_risk(probability=1.0, time_impact=0.0, cost_impact=-2000.0)
        time_impact, cost_impact = evaluator.evaluate_risk_with_cost(risk)
        assert cost_impact == pytest.approx(-2000.0)

    def test_same_seed_gives_same_trigger_outcome(self):
        risk = self._make_risk(probability=0.5, time_impact=8.0, cost_impact=500.0)
        e1 = RiskEvaluator(np.random.RandomState(99))
        e2 = RiskEvaluator(np.random.RandomState(99))
        results1 = [e1.evaluate_risk_with_cost(risk) for _ in range(20)]
        results2 = [e2.evaluate_risk_with_cost(risk) for _ in range(20)]
        assert results1 == results2

    def test_time_and_cost_are_correlated_same_roll(self):
        # Both time and cost must be zero together or nonzero together,
        # never one without the other. Test over many rolls.
        risk = self._make_risk(probability=0.5, time_impact=8.0, cost_impact=500.0)
        evaluator = RiskEvaluator(np.random.RandomState(7))
        for _ in range(200):
            t, c = evaluator.evaluate_risk_with_cost(risk)
            assert (t == 0.0) == (c == 0.0), "time and cost must trigger together"

    def test_evaluate_risks_with_cost_accumulates_across_multiple_risks(self):
        risks = [
            self._make_risk(probability=1.0, time_impact=4.0, cost_impact=100.0),
            self._make_risk(probability=1.0, time_impact=8.0, cost_impact=200.0),
            self._make_risk(probability=0.0, time_impact=16.0, cost_impact=9999.0),
        ]
        evaluator = RiskEvaluator(np.random.RandomState(0))
        total_time, total_cost = evaluator.evaluate_risks_with_cost(risks)
        assert total_time == pytest.approx(12.0)
        assert total_cost == pytest.approx(300.0)

    def test_evaluate_risks_with_cost_empty_list_returns_zeros(self):
        evaluator = RiskEvaluator(np.random.RandomState(0))
        total_time, total_cost = evaluator.evaluate_risks_with_cost([])
        assert total_time == 0.0
        assert total_cost == 0.0


# ---------------------------------------------------------------------------
# TestCostEstimationActivation
# ---------------------------------------------------------------------------


class TestCostEstimationActivation:
    """Test _cost_estimation_active via full simulation results."""

    def test_no_cost_inputs_costs_is_none(self):
        project = make_single_task_project()
        results = _run(project)
        assert results.costs is None

    def test_default_hourly_rate_activates_cost(self):
        project = make_single_task_project(default_hourly_rate=100.0)
        results = _run(project)
        assert results.costs is not None

    def test_task_fixed_cost_activates_cost(self):
        project = make_single_task_project(fixed_cost=500.0)
        results = _run(project)
        assert results.costs is not None

    def test_resource_hourly_rate_activates_cost(self):
        project = make_single_task_project(
            resources=[ResourceSpec(name="dev", hourly_rate=150.0)],
            task_resource_names=["dev"],
        )
        results = _run(project)
        assert results.costs is not None

    def test_task_risk_cost_impact_activates_cost(self):
        risk = Risk(id="r1", name="R", probability=0.5, impact=4.0, cost_impact=1000.0)
        project = make_single_task_project(task_risks=[risk])
        results = _run(project)
        assert results.costs is not None

    def test_project_risk_cost_impact_activates_cost(self):
        risk = Risk(id="r1", name="R", probability=0.5, impact=4.0, cost_impact=1000.0)
        project = make_single_task_project(project_risks=[risk])
        results = _run(project)
        assert results.costs is not None

    def test_default_hourly_rate_zero_does_not_activate_cost(self):
        # Rate 0 means no cost data — should stay None
        project = make_single_task_project(default_hourly_rate=0.0)
        results = _run(project)
        assert results.costs is None


# ---------------------------------------------------------------------------
# TestCostComputation
# ---------------------------------------------------------------------------


class TestCostComputation:
    """Verify cost values are computed correctly with known seeds."""

    def test_single_task_cost_equals_duration_times_rate(self):
        # Near-deterministic estimate (low=expected=8, high=8.001h), rate=100
        project = make_single_task_project(default_hourly_rate=100.0)
        results = _run(project)
        assert results.costs is not None
        # All durations ≈ 8h → all costs ≈ 800
        np.testing.assert_allclose(results.costs, 800.0, atol=0.1)
        assert results.cost_mean == pytest.approx(800.0, abs=0.1)

    def test_cost_mean_proportional_to_effort_mean(self):
        # With a triangular estimate, cost_mean ≈ effort_mean * rate
        project = make_single_task_project(
            default_hourly_rate=100.0,
            estimate_low=40.0,
            estimate_expected=80.0,
            estimate_high=160.0,
        )
        results = _run(project, iterations=2000, seed=42)
        assert results.costs is not None
        assert results.cost_mean is not None
        # For a single task, effort_mean == duration_mean
        expected_cost_mean = results.mean * 100.0
        assert results.cost_mean == pytest.approx(expected_cost_mean, rel=0.01)

    def test_fixed_cost_added_to_labor(self):
        # ≈8h at rate 100 + 500 fixed ≈ 1300 per iteration
        project = make_single_task_project(
            default_hourly_rate=100.0,
            fixed_cost=500.0,
        )
        results = _run(project)
        assert results.costs is not None
        np.testing.assert_allclose(results.costs, 1300.0, atol=0.1)

    def test_overhead_applied_to_labor_only(self):
        # ≈8h * 100 = ≈800 labor, 500 fixed. overhead 20% on labor → ≈800*1.2 + 500 = ≈1460
        project = make_single_task_project(
            default_hourly_rate=100.0,
            overhead_rate=0.20,
            fixed_cost=500.0,
        )
        results = _run(project)
        assert results.costs is not None
        np.testing.assert_allclose(results.costs, 1460.0, atol=0.2)

    def test_overhead_rate_zero_no_markup(self):
        project = make_single_task_project(
            default_hourly_rate=100.0,
            overhead_rate=0.0,
        )
        results = _run(project)
        assert results.costs is not None
        np.testing.assert_allclose(results.costs, 800.0, atol=0.1)

    def test_multi_task_per_task_costs_sum_to_labor_plus_fixed(self):
        # Two tasks, no overhead. sum(per_task) == total_cost
        task1 = Task(
            id="t1",
            name="T1",
            estimate=TaskEstimate(low=8, expected=8, high=8.001),
            fixed_cost=200.0,
        )
        task2 = Task(
            id="t2",
            name="T2",
            estimate=TaskEstimate(low=4, expected=4, high=4.001),
        )
        project = Project(
            project=ProjectMetadata(
                name="Multi",
                start_date=date(2025, 1, 6),
                default_hourly_rate=100.0,
                overhead_rate=0.0,
            ),
            tasks=[task1, task2],
        )
        results = _run(project)
        assert results.costs is not None
        assert results.task_costs is not None
        per_task_sum = sum(np.mean(v) for v in results.task_costs.values())
        # With no overhead, total cost = labor + fixed = per_task sum
        assert per_task_sum == pytest.approx(results.cost_mean, rel=1e-6)

    def test_multi_task_overhead_not_in_per_task_costs(self):
        # With overhead, sum(per_task) < total_cost by exactly overhead amount
        task1 = Task(
            id="t1",
            name="T1",
            estimate=TaskEstimate(low=8, expected=8, high=8.001),
        )
        task2 = Task(
            id="t2",
            name="T2",
            estimate=TaskEstimate(low=4, expected=4, high=4.001),
        )
        overhead_rate = 0.25
        project = Project(
            project=ProjectMetadata(
                name="Overhead",
                start_date=date(2025, 1, 6),
                default_hourly_rate=100.0,
                overhead_rate=overhead_rate,
            ),
            tasks=[task1, task2],
        )
        results = _run(project)
        assert results.costs is not None
        assert results.task_costs is not None
        # total_labor ≈ (8+4) * 100 = 1200, overhead ≈ 1200 * 0.25 = 300
        # per_task sum ≈ 1200 (no overhead), total ≈ 1500
        per_task_sum = sum(np.mean(v) for v in results.task_costs.values())
        total_labor = 1200.0
        expected_overhead = total_labor * overhead_rate
        assert results.cost_mean == pytest.approx(
            total_labor + expected_overhead, abs=1.0
        )
        assert per_task_sum == pytest.approx(total_labor, abs=1.0)

    def test_currency_from_project_propagated_to_results(self):
        project = make_single_task_project(default_hourly_rate=100.0, currency="GBP")
        results = _run(project)
        assert results.currency == "GBP"

    def test_currency_fallback_to_config_default(self):
        # No currency on project → falls back to config default (EUR)
        project = make_single_task_project(default_hourly_rate=100.0, currency=None)
        results = _run(project)
        assert results.currency == "EUR"

    def test_cost_std_dev_populated(self):
        project = make_single_task_project(
            default_hourly_rate=100.0,
            estimate_low=40.0,
            estimate_expected=80.0,
            estimate_high=160.0,
        )
        results = _run(project, iterations=500, seed=7)
        assert results.cost_std_dev is not None
        assert results.cost_std_dev > 0.0

    def test_cost_percentiles_populated(self):
        project = make_single_task_project(
            default_hourly_rate=100.0,
            estimate_low=40.0,
            estimate_expected=80.0,
            estimate_high=160.0,
        )
        results = _run(project, iterations=500, seed=7)
        assert results.cost_percentiles is not None
        assert len(results.cost_percentiles) > 0


# ---------------------------------------------------------------------------
# TestCostWithResources
# ---------------------------------------------------------------------------


class TestCostWithResources:
    """Cost in resource-constrained mode."""

    def test_resource_hourly_rate_overrides_project_default(self):
        # Resource rate 200 > project default 100. Assigned task should use 200.
        project = Project(
            project=ProjectMetadata(
                name="ResRate",
                start_date=date(2025, 1, 6),
                default_hourly_rate=100.0,
            ),
            tasks=[
                Task(
                    id="t1",
                    name="T1",
                    estimate=TaskEstimate(low=8, expected=8, high=8.001),
                    resources=["senior"],
                )
            ],
            resources=[ResourceSpec(name="senior", hourly_rate=200.0)],
        )
        results = _run(project)
        assert results.costs is not None
        # Duration≈8h, rate=200 → cost≈1600
        np.testing.assert_allclose(results.costs, 1600.0, atol=0.2)

    def test_resource_without_rate_falls_back_to_project_default(self):
        project = Project(
            project=ProjectMetadata(
                name="Fallback",
                start_date=date(2025, 1, 6),
                default_hourly_rate=120.0,
            ),
            tasks=[
                Task(
                    id="t1",
                    name="T1",
                    estimate=TaskEstimate(low=8, expected=8, high=8.001),
                    resources=["dev"],
                )
            ],
            resources=[ResourceSpec(name="dev", hourly_rate=None)],
        )
        results = _run(project)
        assert results.costs is not None
        # Duration≈8h, rate=120 (fallback) → cost≈960
        np.testing.assert_allclose(results.costs, 960.0, atol=0.2)

    def test_multi_resource_task_uses_assigned_resource_rate(self):
        # When two resources with different rates are available and a task
        # specifies both, the scheduler assigns them and uses their rates.
        # Verify that the project default rate (50) is not used.
        project = Project(
            project=ProjectMetadata(
                name="MultiRes",
                start_date=date(2025, 1, 6),
                default_hourly_rate=50.0,
            ),
            tasks=[
                Task(
                    id="t1",
                    name="T1",
                    estimate=TaskEstimate(low=8, expected=8, high=8.001),
                    resources=["junior", "senior"],
                )
            ],
            resources=[
                ResourceSpec(name="junior", hourly_rate=100.0),
                ResourceSpec(name="senior", hourly_rate=200.0),
            ],
        )
        results = _run(project)
        assert results.costs is not None
        # Cost must use resource rates (100 or 200), not the project default (50)
        # At minimum: 8h * 100 = 800; at maximum: 8h * 200 = 1600
        assert results.cost_mean is not None
        assert results.cost_mean > 8.0 * 50.0  # definitely above default rate
        assert results.cost_mean <= 8.001 * 200.0 + 1.0  # at most max rate

    def test_cost_mean_positive_with_resources(self):
        project = Project(
            project=ProjectMetadata(
                name="ResCost",
                start_date=date(2025, 1, 6),
            ),
            tasks=[
                Task(
                    id="t1",
                    name="T1",
                    estimate=TaskEstimate(low=4, expected=8, high=16),
                    resources=["dev"],
                )
            ],
            resources=[ResourceSpec(name="dev", hourly_rate=150.0)],
        )
        results = _run(project, iterations=500, seed=42)
        assert results.costs is not None
        assert results.cost_mean is not None
        assert results.cost_mean > 0.0


# ---------------------------------------------------------------------------
# TestSimulationResultsCostMethods
# ---------------------------------------------------------------------------


class TestSimulationResultsCostMethods:
    """Tests for budget/confidence methods on SimulationResults."""

    @pytest.fixture
    def uniform_results(self):
        """1000 costs uniformly distributed in [100, 200]."""
        costs = np.linspace(100.0, 200.0, 1000)
        return make_results_with_costs(costs)

    # --- probability_within_budget ---

    def test_probability_within_budget_midpoint(self, uniform_results):
        p = uniform_results.probability_within_budget(150.0)
        assert p == pytest.approx(0.50, abs=0.02)

    def test_probability_within_budget_lower_bound(self, uniform_results):
        p = uniform_results.probability_within_budget(100.0)
        assert p == pytest.approx(0.001, abs=0.005)

    def test_probability_within_budget_upper_bound(self, uniform_results):
        p = uniform_results.probability_within_budget(200.0)
        assert p == 1.0

    def test_probability_within_budget_raises_when_costs_none(self):
        r = SimulationResults(
            iterations=10,
            project_name="no-cost",
            durations=np.ones(10),
        )
        with pytest.raises(ValueError, match="Cost estimation is not active"):
            r.probability_within_budget(100.0)

    # --- budget_for_confidence ---

    def test_budget_for_confidence_80pct(self, uniform_results):
        # Uniform [100,200]: p80 = 100 + 0.80 * 100 = 180
        b = uniform_results.budget_for_confidence(0.80)
        assert b == pytest.approx(180.0, abs=1.0)

    def test_budget_for_confidence_100pct(self, uniform_results):
        b = uniform_results.budget_for_confidence(1.0)
        assert b == pytest.approx(200.0, abs=0.1)

    def test_budget_for_confidence_0pct(self, uniform_results):
        b = uniform_results.budget_for_confidence(0.0)
        assert b == pytest.approx(100.0, abs=0.1)

    def test_budget_for_confidence_raises_above_one(self, uniform_results):
        with pytest.raises(ValueError):
            uniform_results.budget_for_confidence(1.01)

    def test_budget_for_confidence_raises_below_zero(self, uniform_results):
        with pytest.raises(ValueError):
            uniform_results.budget_for_confidence(-0.01)

    def test_budget_for_confidence_raises_when_costs_none(self):
        r = SimulationResults(
            iterations=10,
            project_name="no-cost",
            durations=np.ones(10),
        )
        with pytest.raises(ValueError):
            r.budget_for_confidence(0.80)

    # --- budget_confidence_interval ---

    def test_budget_confidence_interval_returns_three_floats(self, uniform_results):
        result = uniform_results.budget_confidence_interval(150.0)
        assert len(result) == 3
        p_hat, lower, upper = result
        assert isinstance(p_hat, float)
        assert isinstance(lower, float)
        assert isinstance(upper, float)

    def test_budget_confidence_interval_ordering(self, uniform_results):
        p_hat, lower, upper = uniform_results.budget_confidence_interval(150.0)
        assert lower <= p_hat <= upper

    def test_budget_confidence_interval_in_unit_range(self, uniform_results):
        _, lower, upper = uniform_results.budget_confidence_interval(150.0)
        assert 0.0 <= lower <= 1.0
        assert 0.0 <= upper <= 1.0

    def test_budget_confidence_interval_wilson_fallback_small_n(self):
        # n=10, all costs=50 → p_hat=1.0, (1-p_hat)*n=0 < 5 → Wilson branch
        costs = np.full(10, 50.0)
        r = make_results_with_costs(costs)
        p_hat, lower, upper = r.budget_confidence_interval(100.0)
        assert p_hat == 1.0
        assert lower <= p_hat
        assert upper <= 1.0

    def test_budget_confidence_interval_raises_when_costs_none(self):
        r = SimulationResults(
            iterations=10,
            project_name="no-cost",
            durations=np.ones(10),
        )
        with pytest.raises(ValueError):
            r.budget_confidence_interval(100.0)

    # --- joint_probability ---

    def test_joint_probability_bounded_by_marginals(self, uniform_results):
        # P(T≤t AND C≤b) ≤ min(P(T≤t), P(C≤b))
        target_hours = float(np.median(uniform_results.durations))
        target_budget = 150.0
        joint = uniform_results.joint_probability(target_hours, target_budget)
        p_time = uniform_results.probability_of_completion(target_hours)
        p_cost = uniform_results.probability_within_budget(target_budget)
        assert joint <= min(p_time, p_cost) + 1e-9

    def test_joint_probability_non_negative(self, uniform_results):
        joint = uniform_results.joint_probability(100.0, 150.0)
        assert joint >= 0.0

    def test_joint_probability_at_most_one(self, uniform_results):
        joint = uniform_results.joint_probability(1e9, 1e9)
        assert joint <= 1.0

    def test_joint_probability_raises_when_costs_none(self):
        r = SimulationResults(
            iterations=10,
            project_name="no-cost",
            durations=np.ones(10),
        )
        with pytest.raises(ValueError):
            r.joint_probability(100.0, 100.0)

    # --- cost_percentile ---

    def test_cost_percentile_p50_near_midpoint(self, uniform_results):
        p50 = uniform_results.cost_percentile(50)
        assert p50 == pytest.approx(150.0, abs=1.0)

    def test_cost_percentile_raises_when_costs_none(self):
        r = SimulationResults(
            iterations=10,
            project_name="no-cost",
            durations=np.ones(10),
        )
        with pytest.raises(ValueError):
            r.cost_percentile(80)


# ---------------------------------------------------------------------------
# TestCostRiskIntegration
# ---------------------------------------------------------------------------


class TestCostRiskIntegration:
    """Risk cost_impact integrates correctly with time impact in simulations."""

    def test_task_risk_cost_and_time_correlated(self):
        # With prob=1, every iteration triggers: both impacts should always appear
        risk = Risk(
            id="r1",
            name="Always",
            probability=1.0,
            impact=8.0,
            cost_impact=500.0,
        )
        project = make_single_task_project(
            default_hourly_rate=100.0,
            task_risks=[risk],
        )
        results = _run(project)
        assert results.costs is not None
        # Duration ≈ 8h + 8h risk = 16h at rate 100 = 1600, plus 500 fixed risk cost = 2100
        assert np.all(results.costs > 0)
        assert results.cost_mean == pytest.approx(2100.0, abs=0.2)

    def test_task_risk_never_triggered_no_cost_impact(self):
        risk = Risk(
            id="r1",
            name="Never",
            probability=0.0,
            impact=8.0,
            cost_impact=5000.0,
        )
        project = make_single_task_project(
            default_hourly_rate=100.0,
            task_risks=[risk],
        )
        results = _run(project)
        assert results.costs is not None
        # No risk triggered → cost ≈ 8 * 100 = 800
        np.testing.assert_allclose(results.costs, 800.0, atol=0.1)

    def test_project_risk_cost_impact_accumulates(self):
        # Project-level risk with prob=1 and cost_impact=1000 should always add 1000
        risk = Risk(
            id="pr1",
            name="ProjectRisk",
            probability=1.0,
            impact=0.0,
            cost_impact=1000.0,
        )
        project = make_single_task_project(
            default_hourly_rate=100.0,
            project_risks=[risk],
        )
        results = _run(project)
        assert results.costs is not None
        # Labor≈800, proj risk cost=1000 → total≈1800
        np.testing.assert_allclose(results.costs, 1800.0, atol=0.1)

    def test_task_risk_negative_cost_impact_reduces_cost(self):
        risk = Risk(
            id="r1",
            name="Saving",
            probability=1.0,
            impact=0.0,
            cost_impact=-300.0,
        )
        project = make_single_task_project(
            default_hourly_rate=100.0,
            task_risks=[risk],
        )
        results = _run(project)
        assert results.costs is not None
        # Labor≈800, risk saving=-300 → total≈500
        np.testing.assert_allclose(results.costs, 500.0, atol=0.1)

    def test_risk_correlation_verified_with_seed(self):
        # With a stochastic risk (0 < p < 1), time and cost must trigger
        # in the same iterations. Verify over 1000 iterations with a fixed seed.
        risk = Risk(
            id="r1",
            name="Partial",
            probability=0.4,
            impact=8.0,
            cost_impact=400.0,
        )
        evaluator = RiskEvaluator(np.random.RandomState(2025))
        time_results = []
        cost_results = []
        for _ in range(1000):
            t, c = evaluator.evaluate_risk_with_cost(risk)
            time_results.append(t)
            cost_results.append(c)
        # Wherever time != 0, cost must also != 0, and vice versa
        for t, c in zip(time_results, cost_results):
            assert (t > 0) == (c > 0)


# ---------------------------------------------------------------------------
# TestNoRegression
# ---------------------------------------------------------------------------


class TestNoRegression:
    """Projects with no cost fields must not have costs populated."""

    def test_existing_project_costs_remain_none(self):
        project = Project(
            project=ProjectMetadata(name="Legacy", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="t1",
                    name="T1",
                    estimate=TaskEstimate(low=2, expected=4, high=8),
                ),
                Task(
                    id="t2",
                    name="T2",
                    estimate=TaskEstimate(low=1, expected=2, high=4),
                    dependencies=["t1"],
                ),
            ],
        )
        results = _run(project, iterations=200, seed=99)
        assert results.costs is None
        assert results.task_costs is None
        assert results.cost_mean is None
        assert results.cost_std_dev is None
        assert results.cost_percentiles is None
        assert results.currency is None

    def test_known_seed_simulation_mean_unchanged(self):
        # Verify that adding cost fields does NOT alter duration results.
        project_no_cost = make_single_task_project(
            estimate_low=10.0,
            estimate_expected=20.0,
            estimate_high=40.0,
        )
        project_with_cost = make_single_task_project(
            default_hourly_rate=100.0,
            estimate_low=10.0,
            estimate_expected=20.0,
            estimate_high=40.0,
        )
        r_no = _run(project_no_cost, iterations=1000, seed=1234)
        r_with = _run(project_with_cost, iterations=1000, seed=1234)
        # Duration statistics must be identical
        assert r_no.mean == pytest.approx(r_with.mean, rel=1e-6)
        assert r_no.std_dev == pytest.approx(r_with.std_dev, rel=1e-6)
        assert r_no.percentile(80) == pytest.approx(r_with.percentile(80), rel=1e-6)

    def test_duration_results_unaffected_by_risk_cost_impact(self):
        # A risk with only cost_impact (impact=0) must not change durations
        risk = Risk(
            id="r1", name="CostOnly", probability=0.5, impact=0.0, cost_impact=1000.0
        )
        project_base = make_single_task_project(
            default_hourly_rate=100.0,
            estimate_low=10.0,
            estimate_expected=20.0,
            estimate_high=40.0,
        )
        project_risk = make_single_task_project(
            default_hourly_rate=100.0,
            task_risks=[risk],
            estimate_low=10.0,
            estimate_expected=20.0,
            estimate_high=40.0,
        )
        r_base = _run(project_base, iterations=1000, seed=77)
        r_risk = _run(project_risk, iterations=1000, seed=77)
        # Note: random state advances differently due to risk roll, so we test
        # only that durations are in the same ballpark (same distribution shape)
        assert r_base.mean == pytest.approx(r_risk.mean, rel=0.05)


# ---------------------------------------------------------------------------
# TestTwoPassCost
# ---------------------------------------------------------------------------


def _run_two_pass(project: Project, *, iterations: int = 500, seed: int = 42):
    from mcprojsim.config import Config

    cfg = Config.get_default()
    engine = SimulationEngine(
        iterations=iterations,
        random_seed=seed,
        show_progress=False,
        config=cfg,
        two_pass=True,
        pass1_iterations=min(100, iterations),
    )
    return engine.run(project)


class TestTwoPassCost:
    """Two-pass simulation must correctly replay cost risk impacts from pass-1."""

    def _make_project(self, cost_impact: float) -> Project:
        """A single-task, single-resource project with a certain-trigger risk."""
        risk = Risk(
            id="r1",
            name="AlwaysTriggered",
            probability=1.0,
            impact=0.0,  # no schedule impact — pure cost risk
            cost_impact=cost_impact,
        )
        return Project(
            project=ProjectMetadata(
                name="TwoPassCost",
                start_date=date(2026, 1, 5),
                default_hourly_rate=100.0,
            ),
            tasks=[
                Task(
                    id="t1",
                    name="Work",
                    estimate=TaskEstimate(low=8, expected=8, high=8.001),
                    risks=[risk],
                ),
                Task(
                    id="t2",
                    name="Review",
                    estimate=TaskEstimate(low=4, expected=4, high=4.001),
                    dependencies=["t1"],
                ),
            ],
            resources=[ResourceSpec(name="alice", hourly_rate=100.0)],
        )

    def test_task_risk_cost_always_triggered_in_two_pass(self):
        # probability=1 means the risk ALWAYS triggers. After the two-pass fix,
        # cost risk impacts must appear in every iteration (not just the
        # non-cached ones).
        project = self._make_project(cost_impact=1000.0)
        results = _run_two_pass(project, iterations=200, seed=42)
        assert results.costs is not None
        # t1: 8h * $100 = 800, t2: 4h * $100 = 400; risk cost = 1000 → total = 2200
        np.testing.assert_allclose(results.costs, 2200.0, atol=1.0)

    def test_task_risk_cost_zero_when_probability_zero(self):
        risk = Risk(
            id="r1",
            name="NeverTriggered",
            probability=0.0,
            impact=0.0,
            cost_impact=5000.0,
        )
        project = Project(
            project=ProjectMetadata(
                name="TwoPassNoCost",
                start_date=date(2026, 1, 5),
                default_hourly_rate=100.0,
            ),
            tasks=[
                Task(
                    id="t1",
                    name="Work",
                    estimate=TaskEstimate(low=8, expected=8, high=8.001),
                    risks=[risk],
                )
            ],
            resources=[ResourceSpec(name="alice", hourly_rate=100.0)],
        )
        results = _run_two_pass(project, iterations=200, seed=42)
        assert results.costs is not None
        # No risk triggered → only labor cost
        np.testing.assert_allclose(results.costs, 800.0, atol=1.0)

    def test_two_pass_cost_matches_single_pass_statistics(self):
        # Without risk cost impacts, both modes should produce similar cost
        # distributions from the same project (same expected cost).
        project = Project(
            project=ProjectMetadata(
                name="Comparison",
                start_date=date(2026, 1, 5),
                default_hourly_rate=100.0,
            ),
            tasks=[
                Task(
                    id="t1",
                    name="Work",
                    estimate=TaskEstimate(low=10, expected=20, high=40),
                ),
            ],
        )
        r_single = _run(project, iterations=2000, seed=99)
        r_two = _run_two_pass(project, iterations=2000, seed=99)
        assert r_single.cost_mean is not None
        assert r_two.cost_mean is not None
        # Means should be within 5% of each other (different schedulers, same distribution)
        assert r_single.cost_mean == pytest.approx(r_two.cost_mean, rel=0.05)


# ---------------------------------------------------------------------------
# TestCostComputationInvariants
# ---------------------------------------------------------------------------


class TestCostComputationInvariants:
    """Structural invariants of the per-iteration cost computation."""

    def test_per_task_costs_sum_less_than_total_when_overhead(self):
        # per_task costs exclude overhead (design decision). When overhead_rate > 0,
        # sum(per_task) < total_cost.
        project = Project(
            project=ProjectMetadata(
                name="OverheadGap",
                start_date=date(2026, 1, 6),
                default_hourly_rate=100.0,
                overhead_rate=0.20,
            ),
            tasks=[
                Task(
                    id="t1",
                    name="Work",
                    estimate=TaskEstimate(low=10, expected=10, high=10.001),
                ),
            ],
        )
        results = _run(project, iterations=200, seed=1)
        assert results.costs is not None
        assert results.task_costs is not None
        # Total cost = labor * 1.20; per_task = labor only
        # So sum(per_task) ≈ total / 1.20 < total
        per_task_sum = np.array([results.task_costs["t1"]]).sum(axis=0)
        assert np.all(per_task_sum < results.costs * 0.99)

    def test_multi_resource_mean_rate_approximation(self):
        # With 2 resources at $100 and $200, and a task large enough to warrant
        # both (≥32 hours so the practical-cap heuristic assigns 2 people),
        # the mean rate is $150 and cost ≈ 32h × $150 = $4800.
        # (Equal-effort-split Phase 1 approximation — documented limitation.)
        project = Project(
            project=ProjectMetadata(
                name="MeanRate",
                start_date=date(2026, 1, 6),
                default_hourly_rate=0.0,
            ),
            tasks=[
                Task(
                    id="t1",
                    name="Shared",
                    estimate=TaskEstimate(low=32, expected=32, high=32.001),
                    resources=["cheap", "expensive"],
                    max_resources=2,
                )
            ],
            resources=[
                ResourceSpec(name="cheap", hourly_rate=100.0),
                ResourceSpec(name="expensive", hourly_rate=200.0),
            ],
        )
        results = _run(project, iterations=200, seed=7)
        assert results.cost_mean is not None
        # Mean rate = (100+200)/2 = 150; cost ≈ 32 * 150 = 4800
        assert results.cost_mean == pytest.approx(4800.0, abs=10.0)

    def test_overhead_not_applied_to_fixed_cost(self):
        # Overhead is applied to labor only. A fixed_cost task with no labor
        # should have total_cost == fixed_cost exactly (no overhead markup).
        project = Project(
            project=ProjectMetadata(
                name="FixedOnly",
                start_date=date(2026, 1, 6),
                overhead_rate=0.50,  # 50% overhead — would double if applied
            ),
            tasks=[
                Task(
                    id="t1",
                    name="License",
                    estimate=TaskEstimate(low=0.01, expected=0.01, high=0.02),
                    fixed_cost=5000.0,
                ),
            ],
        )
        results = _run(project, iterations=200, seed=3)
        assert results.costs is not None
        # labor ≈ 0 → overhead ≈ 0; total ≈ fixed_cost = 5000
        np.testing.assert_allclose(results.costs, 5000.0, atol=1.0)
