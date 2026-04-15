"""Tests for simulation components."""

import pytest
import numpy as np
from datetime import date
from typing import Any, cast

from mcprojsim.simulation.distributions import (
    DistributionSampler,
    fit_shifted_lognormal,
)
from mcprojsim.simulation.risk_evaluator import RiskEvaluator
from mcprojsim.simulation.scheduler import TaskScheduler
from mcprojsim.simulation.engine import SimulationCancelled, SimulationEngine
from mcprojsim.models.project import (
    Project,
    ProjectMetadata,
    Task,
    TaskEstimate,
    Risk,
    DistributionType,
    ResourceSpec,
    UncertaintyFactors,
)
from mcprojsim.config import Config
from mcprojsim.models.project import (
    SprintCapacityMode,
    SprintHistoryEntry,
    SprintPlanningSpec,
    SprintSicknessSpec,
    SprintVelocityModel,
)
from mcprojsim.planning.sprint_capacity import SprintCapacitySampler
from mcprojsim.planning.sprint_planner import SprintPlanner
from mcprojsim.planning.sprint_engine import SprintSimulationEngine


class TestDistributionSampler:
    """Tests for distribution sampler."""

    def test_sample_triangular(self):
        """Test sampling from triangular distribution."""
        sampler = DistributionSampler(np.random.RandomState(42))
        estimate = TaskEstimate(
            distribution=DistributionType.TRIANGULAR,
            low=1.0,
            expected=2.0,
            high=5.0,
        )

        samples = [sampler.sample(estimate) for _ in range(100)]
        assert all(1.0 <= s <= 5.0 for s in samples)
        assert np.mean(samples) > 1.0
        assert np.mean(samples) < 5.0

    def test_sample_lognormal(self):
        """Test sampling from lognormal distribution."""
        sampler = DistributionSampler(np.random.RandomState(42))
        estimate = TaskEstimate(
            distribution=DistributionType.LOGNORMAL,
            low=2.0,
            expected=5.0,
            high=16.0,
        )

        samples = [sampler.sample(estimate) for _ in range(100)]
        assert all(s > 2.0 for s in samples)

    def test_fit_shifted_lognormal_matches_mode_and_percentile(self):
        """The fitted shifted-lognormal should honor mode and chosen percentile."""
        low = 2.0
        expected = 5.0
        high = 16.0
        z95 = 1.6448536269514722

        mu, sigma = fit_shifted_lognormal(low, expected, high, z95)
        shifted_mode = np.exp(mu - sigma**2)
        shifted_p95 = np.exp(mu + z95 * sigma)

        assert shifted_mode == pytest.approx(expected - low)
        assert shifted_p95 == pytest.approx(high - low)

    def test_sample_reproducibility(self):
        """Test that sampling is reproducible with same seed."""
        estimate = TaskEstimate(low=1, expected=2, high=5)

        sampler1 = DistributionSampler(np.random.RandomState(42))
        samples1 = [sampler1.sample(estimate) for _ in range(10)]

        sampler2 = DistributionSampler(np.random.RandomState(42))
        samples2 = [sampler2.sample(estimate) for _ in range(10)]

        assert np.allclose(samples1, samples2)

    def test_sample_unknown_distribution(self):
        """Test that unknown distribution type raises error."""
        # from mcprojsim.models.project import DistributionType

        sampler = DistributionSampler(np.random.RandomState(42))

        # Create an estimate with an invalid distribution type
        estimate = TaskEstimate(low=1, expected=2, high=5)
        estimate.distribution = "invalid_distribution"  # type: ignore

        with pytest.raises(ValueError, match="Unknown distribution type"):
            sampler.sample(estimate)

    def test_sample_triangular_missing_values_raises(self):
        """Missing triangular parameters should raise a clear ValueError."""
        sampler = DistributionSampler(np.random.RandomState(42))
        estimate = TaskEstimate.model_construct(
            distribution=DistributionType.TRIANGULAR,
            low=None,
            expected=2.0,
            high=5.0,
            t_shirt_size=None,
            story_points=None,
            unit=None,
        )

        with pytest.raises(ValueError, match="Triangular distribution requires"):
            sampler.sample(estimate)

    def test_sample_lognormal_missing_values_raises(self):
        """Missing lognormal parameters should raise a clear ValueError."""
        sampler = DistributionSampler(np.random.RandomState(42))
        estimate = TaskEstimate.model_construct(
            distribution=DistributionType.LOGNORMAL,
            low=1.0,
            expected=None,
            high=5.0,
            t_shirt_size=None,
            story_points=None,
            unit=None,
        )

        with pytest.raises(ValueError, match="Lognormal distribution requires"):
            sampler.sample(estimate)


class TestRiskEvaluator:
    """Tests for risk evaluator."""

    def test_evaluate_risk_not_triggered(self):
        """Test risk that doesn't trigger."""
        evaluator = RiskEvaluator(np.random.RandomState(42))
        risk = Risk(
            id="risk_001",
            name="Test Risk",
            probability=0.0,  # Never triggers
            impact=10.0,
        )

        impact = evaluator.evaluate_risk(risk)
        assert impact == 0.0

    def test_evaluate_risk_always_triggered(self):
        """Test risk that always triggers."""
        evaluator = RiskEvaluator(np.random.RandomState(42))
        risk = Risk(
            id="risk_001",
            name="Test Risk",
            probability=1.0,  # Always triggers
            impact=10.0,
        )

        impact = evaluator.evaluate_risk(risk)
        assert impact == 10.0

    def test_evaluate_multiple_risks(self):
        """Test evaluating multiple risks."""
        evaluator = RiskEvaluator(np.random.RandomState(42))
        risks = [
            Risk(id="r1", name="Risk 1", probability=1.0, impact=5.0),
            Risk(id="r2", name="Risk 2", probability=1.0, impact=3.0),
        ]

        total_impact = evaluator.evaluate_risks(risks)
        assert total_impact == 8.0


class TestSprintCapacitySampler:
    """Tests for historical sprint normalization and sampling."""

    def test_sampler_holiday_normalizes_delivery_side_only(self):
        """Completed and spillover should be holiday-normalized; churn stays raw."""
        spec = SprintPlanningSpec(
            enabled=True,
            sprint_length_weeks=2,
            capacity_mode=SprintCapacityMode.STORY_POINTS,
            history=[
                SprintHistoryEntry(
                    sprint_id="SPR-001",
                    sprint_length_weeks=2,
                    completed_story_points=8,
                    spillover_story_points=4,
                    added_story_points=2,
                    removed_story_points=1,
                    holiday_factor=0.5,
                ),
                SprintHistoryEntry(
                    sprint_id="SPR-002",
                    sprint_length_weeks=2,
                    completed_story_points=10,
                    spillover_story_points=0,
                    added_story_points=0,
                    removed_story_points=0,
                ),
            ],
        )

        sampler = SprintCapacitySampler(spec, np.random.RandomState(42))
        first_row = sampler.normalized_rows[0]

        assert first_row.completed_units == pytest.approx(16.0)
        assert first_row.spillover_units == pytest.approx(8.0)
        assert first_row.added_units == pytest.approx(2.0)
        assert first_row.removed_units == pytest.approx(1.0)

    def test_sampler_resamples_matching_cadence_rows(self):
        """Matching sprint cadence should sample whole normalized rows."""
        spec = SprintPlanningSpec(
            enabled=True,
            sprint_length_weeks=2,
            capacity_mode=SprintCapacityMode.STORY_POINTS,
            history=[
                SprintHistoryEntry(
                    sprint_id="SPR-001",
                    sprint_length_weeks=1,
                    completed_story_points=3,
                ),
                SprintHistoryEntry(
                    sprint_id="SPR-002",
                    sprint_length_weeks=2,
                    completed_story_points=10,
                    spillover_story_points=1,
                ),
                SprintHistoryEntry(
                    sprint_id="SPR-003",
                    sprint_length_weeks=2,
                    completed_story_points=8,
                    spillover_story_points=2,
                ),
            ],
        )

        sampler = SprintCapacitySampler(spec, np.random.RandomState(7))
        samples = [sampler.sample() for _ in range(10)]

        assert sampler.uses_weekly_fallback is False
        assert {sample.sampling_mode for sample in samples} == {"matching_cadence"}
        assert {sample.completed_units for sample in samples}.issubset({10.0, 8.0})
        assert {sample.spillover_units for sample in samples}.issubset({1.0, 2.0})

    def test_sampler_uses_weekly_fallback_for_missing_cadence(self):
        """Missing target cadence should trigger weekly normalization fallback."""
        spec = SprintPlanningSpec(
            enabled=True,
            sprint_length_weeks=3,
            capacity_mode=SprintCapacityMode.TASKS,
            history=[
                SprintHistoryEntry(
                    sprint_id="SPR-001",
                    sprint_length_weeks=1,
                    completed_tasks=4,
                    spillover_tasks=1,
                    added_tasks=2,
                    removed_tasks=0,
                ),
                SprintHistoryEntry(
                    sprint_id="SPR-002",
                    sprint_length_weeks=2,
                    completed_tasks=12,
                    spillover_tasks=2,
                    added_tasks=4,
                    removed_tasks=2,
                ),
            ],
        )

        sampler = SprintCapacitySampler(spec, np.random.RandomState(7))
        sample = sampler.sample()

        weekly_rows = sampler._build_weekly_rows()
        expected_rng = np.random.RandomState(7)
        expected_indices = [expected_rng.randint(0, len(weekly_rows)) for _ in range(3)]
        expected_completed = sum(
            weekly_rows[index].completed_units for index in expected_indices
        )
        expected_spillover = sum(
            weekly_rows[index].spillover_units for index in expected_indices
        )
        expected_added = sum(
            weekly_rows[index].added_units for index in expected_indices
        )
        expected_removed = sum(
            weekly_rows[index].removed_units for index in expected_indices
        )

        assert sampler.uses_weekly_fallback is True
        assert sample.sampling_mode == "weekly_fallback"
        assert sample.completed_units == pytest.approx(expected_completed)
        assert sample.spillover_units == pytest.approx(expected_spillover)
        assert sample.added_units == pytest.approx(expected_added)
        assert sample.removed_units == pytest.approx(expected_removed)

    def test_sampler_reports_historical_diagnostics(self):
        """Historical diagnostics should include stats, ratios, and correlations."""
        spec = SprintPlanningSpec(
            enabled=True,
            sprint_length_weeks=2,
            capacity_mode=SprintCapacityMode.STORY_POINTS,
            history=[
                SprintHistoryEntry(
                    sprint_id="SPR-001",
                    sprint_length_weeks=2,
                    completed_story_points=10,
                    spillover_story_points=2,
                    added_story_points=1,
                    removed_story_points=1,
                ),
                SprintHistoryEntry(
                    sprint_id="SPR-002",
                    sprint_length_weeks=2,
                    completed_story_points=8,
                    spillover_story_points=4,
                    added_story_points=2,
                    removed_story_points=0,
                ),
            ],
        )

        sampler = SprintCapacitySampler(spec, np.random.RandomState(42))
        diagnostics = sampler.get_historical_diagnostics()

        assert diagnostics["sampling_mode"] == "matching_cadence"
        assert diagnostics["observation_count"] == 2
        assert diagnostics["series_statistics"]["completed_units"][
            "mean"
        ] == pytest.approx(9.0)
        assert diagnostics["ratios"]["spillover_ratio"]["percentiles"][50] >= 0
        assert "completed_units|spillover_units" in diagnostics["correlations"]

    def test_sampler_applies_volatility_and_future_override_to_completed_units(self):
        """Volatility and future overrides should scale deliverable capacity only."""
        spec = SprintPlanningSpec(
            enabled=True,
            sprint_length_weeks=2,
            capacity_mode=SprintCapacityMode.STORY_POINTS,
            history=[
                SprintHistoryEntry(
                    sprint_id="SPR-001",
                    sprint_length_weeks=2,
                    completed_story_points=10,
                    added_story_points=4,
                ),
                SprintHistoryEntry(
                    sprint_id="SPR-002",
                    sprint_length_weeks=2,
                    completed_story_points=10,
                    added_story_points=2,
                ),
            ],
            volatility_overlay={
                "enabled": True,
                "disruption_probability": 1.0,
                "disruption_multiplier_low": 0.5,
                "disruption_multiplier_expected": 0.5,
                "disruption_multiplier_high": 0.5,
            },
            future_sprint_overrides=[
                {
                    "sprint_number": 1,
                    "holiday_factor": 0.8,
                    "capacity_multiplier": 0.5,
                }
            ],
        )

        sampler = SprintCapacitySampler(spec, np.random.RandomState(42))
        sample = sampler.sample(sprint_number=1, sprint_start_date=date(2025, 1, 1))

        assert sample.nominal_completed_units == pytest.approx(10.0)
        assert sample.completed_units == pytest.approx(2.0)
        assert sample.added_units in {4.0, 2.0}
        assert sample.disruption_applied is True

    def test_sickness_multiplier_is_1_when_disabled(self):
        """Disabled sickness model should produce multiplier of 1.0."""
        spec = SprintPlanningSpec(
            enabled=True,
            sprint_length_weeks=2,
            capacity_mode=SprintCapacityMode.STORY_POINTS,
            history=[
                SprintHistoryEntry(sprint_id="S1", completed_story_points=10),
                SprintHistoryEntry(sprint_id="S2", completed_story_points=12),
            ],
        )
        sampler = SprintCapacitySampler(spec, np.random.RandomState(42))
        sample = sampler.sample()
        assert sample.sickness_multiplier == 1.0

    def test_sickness_multiplier_is_1_when_team_size_is_none(self):
        """Enabled sickness without team_size should produce multiplier of 1.0."""
        spec = SprintPlanningSpec(
            enabled=True,
            sprint_length_weeks=2,
            capacity_mode=SprintCapacityMode.STORY_POINTS,
            sickness=SprintSicknessSpec(enabled=True, team_size=None),
            history=[
                SprintHistoryEntry(sprint_id="S1", completed_story_points=10),
                SprintHistoryEntry(sprint_id="S2", completed_story_points=12),
            ],
        )
        sampler = SprintCapacitySampler(spec, np.random.RandomState(42))
        sample = sampler.sample()
        assert sample.sickness_multiplier == 1.0

    def test_sickness_multiplier_reduces_capacity(self):
        """Enabled sickness with high probability should visibly reduce capacity."""
        spec = SprintPlanningSpec(
            enabled=True,
            sprint_length_weeks=2,
            capacity_mode=SprintCapacityMode.STORY_POINTS,
            sickness=SprintSicknessSpec(
                enabled=True,
                team_size=8,
                probability_per_person_per_week=0.5,
                duration_log_mu=1.5,
                duration_log_sigma=0.3,
            ),
            history=[
                SprintHistoryEntry(sprint_id="S1", completed_story_points=10),
                SprintHistoryEntry(sprint_id="S2", completed_story_points=12),
            ],
        )
        sampler = SprintCapacitySampler(spec, np.random.RandomState(42))
        multipliers = [sampler.sample().sickness_multiplier for _ in range(50)]
        mean_multiplier = sum(multipliers) / len(multipliers)
        assert mean_multiplier < 0.95
        assert all(0.0 <= m <= 1.0 for m in multipliers)

    def test_sickness_multiplier_is_reproducible_with_seed(self):
        """Two samplers with the same seed should produce identical sickness draws."""
        spec = SprintPlanningSpec(
            enabled=True,
            sprint_length_weeks=2,
            capacity_mode=SprintCapacityMode.STORY_POINTS,
            sickness=SprintSicknessSpec(
                enabled=True,
                team_size=6,
            ),
            history=[
                SprintHistoryEntry(sprint_id="S1", completed_story_points=10),
                SprintHistoryEntry(sprint_id="S2", completed_story_points=12),
            ],
        )
        sampler_a = SprintCapacitySampler(spec, np.random.RandomState(99))
        sampler_b = SprintCapacitySampler(spec, np.random.RandomState(99))
        samples_a = [sampler_a.sample().sickness_multiplier for _ in range(20)]
        samples_b = [sampler_b.sample().sickness_multiplier for _ in range(20)]
        assert samples_a == samples_b

    def test_sickness_multiplier_scales_completed_units(self):
        """Sickness multiplier should reduce completed_units in the sample."""
        spec_no_sickness = SprintPlanningSpec(
            enabled=True,
            sprint_length_weeks=2,
            capacity_mode=SprintCapacityMode.STORY_POINTS,
            history=[
                SprintHistoryEntry(
                    sprint_id="S1",
                    sprint_length_weeks=2,
                    completed_story_points=10,
                ),
                SprintHistoryEntry(
                    sprint_id="S2",
                    sprint_length_weeks=2,
                    completed_story_points=10,
                ),
            ],
        )
        spec_with_sickness = SprintPlanningSpec(
            enabled=True,
            sprint_length_weeks=2,
            capacity_mode=SprintCapacityMode.STORY_POINTS,
            sickness=SprintSicknessSpec(
                enabled=True,
                team_size=8,
                probability_per_person_per_week=0.5,
                duration_log_mu=1.5,
                duration_log_sigma=0.3,
            ),
            history=[
                SprintHistoryEntry(
                    sprint_id="S1",
                    sprint_length_weeks=2,
                    completed_story_points=10,
                ),
                SprintHistoryEntry(
                    sprint_id="S2",
                    sprint_length_weeks=2,
                    completed_story_points=10,
                ),
            ],
        )
        sampler_clean = SprintCapacitySampler(
            spec_no_sickness, np.random.RandomState(42)
        )
        sampler_sick = SprintCapacitySampler(
            spec_with_sickness, np.random.RandomState(42)
        )
        clean_total = sum(sampler_clean.sample().completed_units for _ in range(50))
        sick_total = sum(sampler_sick.sample().completed_units for _ in range(50))
        assert sick_total < clean_total

    def test_sickness_diagnostics_appear_in_output(self):
        """Diagnostics should include sickness configuration."""
        spec = SprintPlanningSpec(
            enabled=True,
            sprint_length_weeks=2,
            capacity_mode=SprintCapacityMode.STORY_POINTS,
            sickness=SprintSicknessSpec(enabled=True, team_size=5),
            history=[
                SprintHistoryEntry(sprint_id="S1", completed_story_points=10),
                SprintHistoryEntry(sprint_id="S2", completed_story_points=12),
            ],
        )
        sampler = SprintCapacitySampler(spec, np.random.RandomState(42))
        diag = sampler.get_historical_diagnostics()
        assert diag["sickness"]["enabled"] is True
        assert diag["sickness"]["team_size"] == 5
        assert diag["sickness"]["probability_per_person_per_week"] == pytest.approx(
            0.058
        )

    def test_neg_binomial_fit_overdispersed(self):
        """NB fit on overdispersed data should give finite dispersion k."""
        spec = SprintPlanningSpec(
            enabled=True,
            sprint_length_weeks=2,
            capacity_mode=SprintCapacityMode.STORY_POINTS,
            velocity_model=SprintVelocityModel.NEG_BINOMIAL,
            history=[
                SprintHistoryEntry(
                    sprint_id=f"S{i}",
                    sprint_length_weeks=2,
                    completed_story_points=v,
                )
                for i, v in enumerate([5, 12, 7, 15, 6, 14, 8], start=1)
            ],
        )
        sampler = SprintCapacitySampler(spec, np.random.RandomState(42))
        diag = sampler.get_historical_diagnostics()
        nb = diag["neg_binomial_params"]
        assert nb["mu"] > 0
        assert nb["k"] is not None
        assert nb["overdispersed"] is True

    def test_neg_binomial_fit_underdispersed_falls_back_to_poisson(self):
        """NB fit when variance <= mean should give k=None (Poisson fallback)."""
        spec = SprintPlanningSpec(
            enabled=True,
            sprint_length_weeks=2,
            capacity_mode=SprintCapacityMode.STORY_POINTS,
            velocity_model=SprintVelocityModel.NEG_BINOMIAL,
            history=[
                SprintHistoryEntry(
                    sprint_id=f"S{i}",
                    sprint_length_weeks=2,
                    completed_story_points=v,
                )
                for i, v in enumerate([10, 10, 10, 10], start=1)
            ],
        )
        sampler = SprintCapacitySampler(spec, np.random.RandomState(42))
        diag = sampler.get_historical_diagnostics()
        nb = diag["neg_binomial_params"]
        assert nb["mu"] == pytest.approx(10.0)
        assert nb["k"] is None
        assert nb["overdispersed"] is False

    def test_neg_binomial_sampling_produces_reasonable_values(self):
        """NB sampling should produce positive values near historical mean."""
        spec = SprintPlanningSpec(
            enabled=True,
            sprint_length_weeks=2,
            capacity_mode=SprintCapacityMode.STORY_POINTS,
            velocity_model=SprintVelocityModel.NEG_BINOMIAL,
            history=[
                SprintHistoryEntry(
                    sprint_id=f"S{i}",
                    sprint_length_weeks=2,
                    completed_story_points=v,
                )
                for i, v in enumerate([8, 10, 12, 9, 11], start=1)
            ],
        )
        sampler = SprintCapacitySampler(spec, np.random.RandomState(42))
        samples = [sampler.sample() for _ in range(100)]
        completed_values = [s.completed_units for s in samples]
        mean_completed = sum(completed_values) / len(completed_values)
        assert 5.0 < mean_completed < 20.0
        assert all(s.sampling_mode == "neg_binomial" for s in samples)

    def test_neg_binomial_is_reproducible_with_seed(self):
        """Two NB samplers with the same seed should produce identical draws."""
        spec = SprintPlanningSpec(
            enabled=True,
            sprint_length_weeks=2,
            capacity_mode=SprintCapacityMode.STORY_POINTS,
            velocity_model=SprintVelocityModel.NEG_BINOMIAL,
            history=[
                SprintHistoryEntry(
                    sprint_id=f"S{i}",
                    sprint_length_weeks=2,
                    completed_story_points=v,
                )
                for i, v in enumerate([8, 10, 12, 9, 11], start=1)
            ],
        )
        sampler_a = SprintCapacitySampler(spec, np.random.RandomState(42))
        sampler_b = SprintCapacitySampler(spec, np.random.RandomState(42))
        a = [sampler_a.sample().completed_units for _ in range(20)]
        b = [sampler_b.sample().completed_units for _ in range(20)]
        assert a == b

    def test_neg_binomial_diagnostics_report_velocity_model(self):
        """Diagnostics should report neg_binomial velocity model and params."""
        spec = SprintPlanningSpec(
            enabled=True,
            sprint_length_weeks=2,
            capacity_mode=SprintCapacityMode.STORY_POINTS,
            velocity_model=SprintVelocityModel.NEG_BINOMIAL,
            history=[
                SprintHistoryEntry(sprint_id="S1", completed_story_points=10),
                SprintHistoryEntry(sprint_id="S2", completed_story_points=12),
            ],
        )
        sampler = SprintCapacitySampler(spec, np.random.RandomState(42))
        diag = sampler.get_historical_diagnostics()
        assert diag["velocity_model"] == "neg_binomial"
        assert "neg_binomial_params" in diag
        assert "mu" in diag["neg_binomial_params"]
        assert "k" in diag["neg_binomial_params"]

    def test_neg_binomial_weekly_fallback_sums_weekly_draws(self):
        """NB with weekly fallback should sum weekly draws for longer sprints."""
        spec = SprintPlanningSpec(
            enabled=True,
            sprint_length_weeks=3,
            capacity_mode=SprintCapacityMode.STORY_POINTS,
            velocity_model=SprintVelocityModel.NEG_BINOMIAL,
            history=[
                SprintHistoryEntry(
                    sprint_id="S1",
                    sprint_length_weeks=1,
                    completed_story_points=5,
                ),
                SprintHistoryEntry(
                    sprint_id="S2",
                    sprint_length_weeks=1,
                    completed_story_points=4,
                ),
            ],
        )
        sampler = SprintCapacitySampler(spec, np.random.RandomState(42))
        assert sampler.uses_weekly_fallback is True
        sample = sampler.sample()
        assert sample.sampling_mode == "neg_binomial"
        assert sample.completed_units >= 0


class TestTaskScheduler:
    """Tests for task scheduler."""

    @pytest.fixture
    def simple_project(self):
        """Create a simple project."""
        return Project(
            project=ProjectMetadata(name="Test", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=2, high=5),
                    dependencies=[],
                ),
                Task(
                    id="task_002",
                    name="Task 2",
                    estimate=TaskEstimate(low=1, expected=2, high=5),
                    dependencies=["task_001"],
                ),
            ],
        )

    def test_schedule_tasks_no_dependencies(self):
        """Test scheduling tasks with no dependencies."""
        project = Project(
            project=ProjectMetadata(name="Test", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=2, high=5),
                )
            ],
        )

        scheduler = TaskScheduler(project)
        schedule = scheduler.schedule_tasks({"task_001": 5.0})

        assert schedule["task_001"]["start"] == 0.0
        assert schedule["task_001"]["end"] == 5.0
        assert schedule["task_001"]["duration"] == 5.0

    def test_schedule_tasks_with_dependencies(self, simple_project):
        """Test scheduling tasks with dependencies."""
        scheduler = TaskScheduler(simple_project)
        schedule = scheduler.schedule_tasks({"task_001": 3.0, "task_002": 4.0})

        assert schedule["task_001"]["start"] == 0.0
        assert schedule["task_001"]["end"] == 3.0
        assert schedule["task_002"]["start"] == 3.0
        assert schedule["task_002"]["end"] == 7.0

    def test_topological_sort(self, simple_project):
        """Test topological sort."""
        scheduler = TaskScheduler(simple_project)
        sorted_tasks = scheduler._topological_sort()

        # task_001 should come before task_002
        assert sorted_tasks.index("task_001") < sorted_tasks.index("task_002")

    def test_get_critical_path(self, simple_project):
        """Test critical path identification."""
        scheduler = TaskScheduler(simple_project)
        schedule = scheduler.schedule_tasks({"task_001": 3.0, "task_002": 4.0})
        critical_path = scheduler.get_critical_path(schedule)

        # Both tasks should be on critical path
        assert "task_001" in critical_path
        assert "task_002" in critical_path

    def test_schedule_tasks_with_resource_constraints_serializes_work(self):
        """Resource-constrained mode should serialize work with one shared member."""
        project = Project(
            project=ProjectMetadata(name="Res Test", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                ),
                Task(
                    id="task_002",
                    name="Task 2",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                ),
            ],
            resources=[
                {"name": "res_a", "experience_level": 2, "productivity_level": 1.0}
            ],
        )

        scheduler = TaskScheduler(project)
        unconstrained = scheduler.schedule_tasks(
            {"task_001": 4.0, "task_002": 4.0},
            use_resource_constraints=False,
        )
        constrained = scheduler.schedule_tasks(
            {"task_001": 4.0, "task_002": 4.0},
            use_resource_constraints=True,
        )

        unconstrained_end = max(info["end"] for info in unconstrained.values())
        constrained_end = max(info["end"] for info in constrained.values())

        assert unconstrained_end == 4.0
        assert constrained_end == 8.0

    def test_resource_scheduler_fallback_emits_warning(self, caplog):
        """When constrained scheduling stalls, fallback should emit a warning."""
        project = Project(
            project=ProjectMetadata(name="Fallback", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=2, high=5),
                ),
                Task(
                    id="task_002",
                    name="Task 2",
                    estimate=TaskEstimate(low=1, expected=2, high=5),
                    dependencies=["task_001"],
                ),
            ],
            resources=[
                ResourceSpec(name="dev_1", experience_level=2, productivity_level=1.0)
            ],
        )
        scheduler = TaskScheduler(project)

        scheduler._find_next_time_with_capacity = (  # type: ignore[method-assign]
            lambda *args, **kwargs: None
        )

        with caplog.at_level("WARNING"):
            schedule = scheduler.schedule_tasks(
                {"task_001": 3.0, "task_002": 4.0},
                use_resource_constraints=True,
            )

        assert "task_001" in schedule
        assert "task_002" in schedule
        assert any(
            "falling back to dependency-only scheduling" in message
            for message in caplog.messages
        )

    def test_sickness_absence_uses_configured_duration_parameters(self):
        """Resource sickness absences should use configured lognormal params."""
        project = Project(
            project=ProjectMetadata(name="Sickness", start_date=date(2025, 1, 6)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                )
            ],
            resources=[
                ResourceSpec(
                    name="dev_1",
                    experience_level=2,
                    productivity_level=1.0,
                    sickness_prob=1.0,
                )
            ],
        )
        config = Config.model_validate(
            {
                "sprint_defaults": {
                    "sickness": {
                        "duration_log_mu": 1.5,
                        "duration_log_sigma": 0.3,
                    }
                }
            }
        )

        class StubRandomState:
            def __init__(self) -> None:
                self.lognormal_calls: list[tuple[float, float]] = []

            def random(self) -> float:
                return 0.0

            def lognormal(self, mu: float, sigma: float) -> float:
                self.lognormal_calls.append((mu, sigma))
                return 2.4

        stub_random = StubRandomState()
        scheduler = TaskScheduler(
            project,
            cast(Any, stub_random),
            config,
        )

        absences = scheduler._generate_sickness_absence(
            {"dev_1": project.resources[0]},
            date(2025, 1, 6),
            2,
            {},
            None,
        )

        assert stub_random.lognormal_calls == [(1.5, 0.3)]
        assert absences["dev_1"] == {date(2025, 1, 6), date(2025, 1, 7)}

    def test_sickness_absence_uses_default_config_parameters_when_unspecified(self):
        """Resource sickness absences should fall back to shared config defaults."""
        project = Project(
            project=ProjectMetadata(name="Sickness", start_date=date(2025, 1, 6)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                )
            ],
            resources=[
                ResourceSpec(
                    name="dev_1",
                    experience_level=2,
                    productivity_level=1.0,
                    sickness_prob=1.0,
                )
            ],
        )

        class StubRandomState:
            def __init__(self) -> None:
                self.lognormal_calls: list[tuple[float, float]] = []

            def random(self) -> float:
                return 0.0

            def lognormal(self, mu: float, sigma: float) -> float:
                self.lognormal_calls.append((mu, sigma))
                return 1.0

        stub_random = StubRandomState()
        scheduler = TaskScheduler(project, cast(Any, stub_random))

        scheduler._generate_sickness_absence(
            {"dev_1": project.resources[0]},
            date(2025, 1, 6),
            1,
            {},
            None,
        )

        defaults = Config.get_default().sprint_defaults.sickness
        assert stub_random.lognormal_calls == [
            (defaults.duration_log_mu, defaults.duration_log_sigma)
        ]

    def test_resource_sickness_prob_uses_config_default_when_unspecified(self):
        """Resource sickness_prob should use constrained_scheduling default when unset."""
        project = Project(
            project=ProjectMetadata(name="Sickness", start_date=date(2025, 1, 6)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                )
            ],
            resources=[
                {
                    "name": "dev_1",
                    "experience_level": 2,
                    "productivity_level": 1.0,
                }
            ],
        )
        config = Config.model_validate(
            {"constrained_scheduling": {"sickness_prob": 0.05}}
        )
        scheduler = TaskScheduler(project, config=config)

        assert scheduler._resource_sickness_probability(project.resources[0]) == 0.05

    def test_resource_sickness_prob_in_resource_overrides_config_default(self):
        """Explicit resource sickness_prob should override config default."""
        project = Project(
            project=ProjectMetadata(name="Sickness", start_date=date(2025, 1, 6)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                )
            ],
            resources=[
                {
                    "name": "dev_1",
                    "experience_level": 2,
                    "productivity_level": 1.0,
                    "sickness_prob": 0.0,
                }
            ],
        )
        config = Config.model_validate(
            {"constrained_scheduling": {"sickness_prob": 0.2}}
        )
        scheduler = TaskScheduler(project, config=config)

        assert scheduler._resource_sickness_probability(project.resources[0]) == 0.0


class TestSprintPlanner:
    """Tests for dependency-aware sprint planning."""

    def test_planner_orders_ready_tasks_by_priority_then_id(self):
        """Ready queue ordering should prefer lower priority values then task ID."""
        project = Project(
            project=ProjectMetadata(name="Sprint", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_b",
                    name="Task B",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                    planning_story_points=2,
                    priority=2,
                ),
                Task(
                    id="task_a",
                    name="Task A",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                    planning_story_points=2,
                    priority=1,
                ),
                Task(
                    id="task_c",
                    name="Task C",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                    planning_story_points=2,
                ),
            ],
            sprint_planning=SprintPlanningSpec(
                enabled=True,
                sprint_length_weeks=2,
                capacity_mode=SprintCapacityMode.STORY_POINTS,
                history=[
                    SprintHistoryEntry(sprint_id="SPR-001", completed_story_points=10),
                    SprintHistoryEntry(sprint_id="SPR-002", completed_story_points=8),
                ],
            ),
        )

        planner = SprintPlanner(project)
        result = planner.plan_sprint(
            completed_task_ids=set(),
            sampled_outcome=sampled_outcome(6, 0, 0, 0),
        )

        assert result.ready_task_ids == ["task_a", "task_b", "task_c"]
        assert result.completed_task_ids == ["task_a", "task_b", "task_c"]

    def test_planner_unlocks_dependent_tasks_across_sprints(self):
        """Tasks should become ready after dependencies complete in earlier sprints."""
        project = Project(
            project=ProjectMetadata(name="Sprint", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                    planning_story_points=2,
                ),
                Task(
                    id="task_002",
                    name="Task 2",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                    planning_story_points=2,
                    dependencies=["task_001"],
                ),
            ],
            sprint_planning=SprintPlanningSpec(
                enabled=True,
                sprint_length_weeks=2,
                capacity_mode=SprintCapacityMode.STORY_POINTS,
                history=[
                    SprintHistoryEntry(sprint_id="SPR-001", completed_story_points=10),
                    SprintHistoryEntry(sprint_id="SPR-002", completed_story_points=8),
                ],
            ),
        )

        planner = SprintPlanner(project)
        sprint_one = planner.plan_sprint(set(), sampled_outcome(2, 0, 0, 0))
        sprint_two = planner.plan_sprint(
            set(sprint_one.completed_task_ids),
            sampled_outcome(2, 0, 0, 0),
        )

        assert sprint_one.completed_task_ids == ["task_001"]
        assert sprint_two.ready_task_ids == ["task_002"]
        assert sprint_two.completed_task_ids == ["task_002"]

    def test_planner_defers_non_fitting_tasks_without_capacity_charge(self):
        """A non-fitting task should be deferred with remaining capacity preserved."""
        project = Project(
            project=ProjectMetadata(name="Sprint", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                    planning_story_points=3,
                ),
                Task(
                    id="task_002",
                    name="Task 2",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                    planning_story_points=4,
                ),
            ],
            sprint_planning=SprintPlanningSpec(
                enabled=True,
                sprint_length_weeks=2,
                capacity_mode=SprintCapacityMode.STORY_POINTS,
                history=[
                    SprintHistoryEntry(sprint_id="SPR-001", completed_story_points=10),
                    SprintHistoryEntry(sprint_id="SPR-002", completed_story_points=8),
                ],
            ),
        )

        planner = SprintPlanner(project)
        result = planner.plan_sprint(set(), sampled_outcome(5, 0, 0, 0))

        assert result.completed_task_ids == ["task_001"]
        assert result.deferred_task_ids == ["task_002"]
        assert result.delivered_units == pytest.approx(3.0)
        assert result.remaining_capacity == pytest.approx(2.0)

    def test_planner_records_added_and_removed_scope_in_ledger(self):
        """Added and removed work should be represented as explicit backlog entries."""
        project = Project(
            project=ProjectMetadata(name="Sprint", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                )
            ],
            sprint_planning=SprintPlanningSpec(
                enabled=True,
                sprint_length_weeks=2,
                capacity_mode=SprintCapacityMode.TASKS,
                removed_work_treatment="churn_only",
                history=[
                    SprintHistoryEntry(sprint_id="SPR-001", completed_tasks=3),
                    SprintHistoryEntry(sprint_id="SPR-002", completed_tasks=2),
                ],
            ),
        )

        planner = SprintPlanner(project)
        result = planner.plan_sprint(set(), sampled_outcome(1, 0, 2, 1))

        assert [(entry.entry_type, entry.units) for entry in result.ledger_entries] == [
            ("added_scope", 2.0),
            ("removed_scope", 1.0),
        ]
        assert result.ledger_entries[0].affects_remaining_backlog is True
        assert result.ledger_entries[1].affects_remaining_backlog is False

    def test_planner_creates_remainder_when_spillover_occurs(self):
        """A pulled item that spills should consume capacity but earn no throughput."""
        project = Project(
            project=ProjectMetadata(name="Sprint", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                    planning_story_points=5,
                    spillover_probability_override=1.0,
                )
            ],
            sprint_planning=SprintPlanningSpec(
                enabled=True,
                sprint_length_weeks=2,
                capacity_mode=SprintCapacityMode.STORY_POINTS,
                history=[
                    SprintHistoryEntry(sprint_id="SPR-001", completed_story_points=10),
                    SprintHistoryEntry(sprint_id="SPR-002", completed_story_points=8),
                ],
                spillover={
                    "enabled": True,
                    "consumed_fraction_alpha": 2.0,
                    "consumed_fraction_beta": 2.0,
                },
            ),
        )

        planner = SprintPlanner(project, np.random.RandomState(3))
        result = planner.plan_sprint(set(), sampled_outcome(5, 0, 0, 0))

        assert result.completed_task_ids == []
        assert result.spillover_event_count == 1
        assert result.delivered_units == pytest.approx(0.0)
        assert result.carryover_items[0].task_id == "task_001"
        assert 0.0 < result.carryover_records[0].remaining_points < 5.0


def sampled_outcome(
    completed_units: float,
    spillover_units: float,
    added_units: float,
    removed_units: float,
):
    """Build a sprint outcome sample for planner tests."""
    from mcprojsim.planning.sprint_capacity import SprintOutcomeSample

    return SprintOutcomeSample(
        completed_units=completed_units,
        spillover_units=spillover_units,
        added_units=added_units,
        removed_units=removed_units,
        sampling_mode="test",
    )


class TestSprintSimulationEngine:
    """Tests for sprint-planning engine iteration behavior."""

    def test_engine_is_reproducible_with_fixed_seed(self):
        """Two engines with the same seed should produce identical sprint counts."""
        project = Project(
            project=ProjectMetadata(name="Sprint", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                    planning_story_points=5,
                )
            ],
            sprint_planning=SprintPlanningSpec(
                enabled=True,
                sprint_length_weeks=2,
                capacity_mode=SprintCapacityMode.STORY_POINTS,
                history=[
                    SprintHistoryEntry(sprint_id="SPR-001", completed_story_points=3),
                    SprintHistoryEntry(sprint_id="SPR-002", completed_story_points=6),
                ],
            ),
        )

        engine_one = SprintSimulationEngine(iterations=6, random_seed=42)
        engine_two = SprintSimulationEngine(iterations=6, random_seed=42)

        results_one = engine_one.run(project)
        results_two = engine_two.run(project)

        assert np.array_equal(results_one.sprint_counts, results_two.sprint_counts)

    def test_engine_completes_simple_task_mode_project(self):
        """Task-count sprint mode should complete a one-task project in one sprint."""
        project = Project(
            project=ProjectMetadata(name="Sprint", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                )
            ],
            sprint_planning=SprintPlanningSpec(
                enabled=True,
                sprint_length_weeks=2,
                capacity_mode=SprintCapacityMode.TASKS,
                history=[
                    SprintHistoryEntry(sprint_id="SPR-001", completed_tasks=2),
                    SprintHistoryEntry(sprint_id="SPR-002", completed_tasks=1),
                ],
            ),
        )

        results = SprintSimulationEngine(iterations=5, random_seed=7).run(project)

        assert np.all(results.sprint_counts == 1)
        assert results.percentile(50) == pytest.approx(1.0)

    def test_engine_calculates_planned_commitment_guidance(self):
        """Planned-load guidance should be computed from historical diagnostics."""
        project = Project(
            project=ProjectMetadata(name="Sprint", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                    planning_story_points=3,
                )
            ],
            sprint_planning=SprintPlanningSpec(
                enabled=True,
                sprint_length_weeks=2,
                capacity_mode=SprintCapacityMode.STORY_POINTS,
                planning_confidence_level=0.80,
                history=[
                    SprintHistoryEntry(
                        sprint_id="SPR-001",
                        completed_story_points=10,
                        spillover_story_points=2,
                        added_story_points=1,
                        removed_story_points=1,
                    ),
                    SprintHistoryEntry(
                        sprint_id="SPR-002",
                        completed_story_points=8,
                        spillover_story_points=4,
                        added_story_points=2,
                        removed_story_points=0,
                    ),
                ],
            ),
        )

        results = SprintSimulationEngine(iterations=4, random_seed=5).run(project)

        assert results.planned_commitment_guidance > 0
        assert results.historical_diagnostics["sampling_mode"] == "matching_cadence"

    def test_engine_reports_carryover_spillover_and_burnup_outputs(self):
        """Spillover-enabled runs should emit carryover and burn-up diagnostics."""
        project = Project(
            project=ProjectMetadata(name="Sprint", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                    planning_story_points=5,
                    spillover_probability_override=1.0,
                )
            ],
            sprint_planning=SprintPlanningSpec(
                enabled=True,
                sprint_length_weeks=2,
                capacity_mode=SprintCapacityMode.STORY_POINTS,
                history=[
                    SprintHistoryEntry(sprint_id="SPR-001", completed_story_points=10),
                    SprintHistoryEntry(sprint_id="SPR-002", completed_story_points=10),
                ],
                spillover={
                    "enabled": True,
                    "consumed_fraction_alpha": 2.0,
                    "consumed_fraction_beta": 2.0,
                },
                volatility_overlay={
                    "enabled": True,
                    "disruption_probability": 1.0,
                    "disruption_multiplier_low": 1.0,
                    "disruption_multiplier_expected": 1.0,
                    "disruption_multiplier_high": 1.0,
                },
            ),
        )

        results = SprintSimulationEngine(iterations=3, random_seed=2).run(project)

        assert results.carryover_statistics["mean"] > 0
        assert results.spillover_statistics["aggregate_spillover_rate"]["mean"] > 0
        assert results.disruption_statistics["observed_frequency"] == pytest.approx(1.0)
        assert results.burnup_percentiles
        assert {point["sprint_number"] for point in results.burnup_percentiles} >= {1.0}

    def test_schedule_tasks_with_productivity_and_max_resources(self):
        """Resource-constrained mode should scale elapsed duration by capacity."""
        project = Project(
            project=ProjectMetadata(name="Cap Test", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                    max_resources=2,
                    min_experience_level=2,
                )
            ],
            resources=[
                {"name": "res_a", "experience_level": 2, "productivity_level": 1.0},
                {"name": "res_b", "experience_level": 3, "productivity_level": 1.0},
            ],
        )

        scheduler = TaskScheduler(project)
        effort_hours = 2 * TaskScheduler.MIN_EFFORT_PER_ASSIGNEE_HOURS
        constrained = scheduler.schedule_tasks(
            {"task_001": effort_hours},
            use_resource_constraints=True,
            hours_per_day=24.0,
        )

        assert constrained["task_001"]["start"] == 0.0
        assert constrained["task_001"]["end"] == effort_hours / 2


class TestSimulationEngineDistributionResolution:
    """Tests for project/task distribution default resolution."""

    def test_project_default_lognormal_applies_to_explicit_estimates(self):
        project = Project(
            project=ProjectMetadata(
                name="Default Lognormal",
                start_date=date(2025, 1, 1),
                distribution=DistributionType.LOGNORMAL,
            ),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=2, expected=5, high=16),
                )
            ],
        )

        engine = SimulationEngine(
            iterations=20, random_seed=42, config=Config.get_default()
        )
        results = engine.run(project)

        assert np.all(results.task_durations["task_001"] > 2.0)

    def test_task_distribution_overrides_project_default(self):
        project = Project(
            project=ProjectMetadata(
                name="Override Default",
                start_date=date(2025, 1, 1),
                distribution=DistributionType.LOGNORMAL,
            ),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(
                        distribution=DistributionType.TRIANGULAR,
                        low=2,
                        expected=5,
                        high=16,
                    ),
                )
            ],
        )

        engine = SimulationEngine(
            iterations=50, random_seed=42, config=Config.get_default()
        )
        resolved = engine._resolve_estimate(
            project.tasks[0], project.project.distribution
        )

        assert resolved.distribution == DistributionType.TRIANGULAR
        assert resolved.low == 2.0
        assert resolved.expected == 5.0
        assert resolved.high == 16.0

    def test_schedule_tasks_practical_cap_limits_over_assignment(self):
        """Auto-cap should prevent assigning too many resources to small tasks."""
        project = Project(
            project=ProjectMetadata(
                name="Practical Cap Test", start_date=date(2025, 1, 1)
            ),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                    max_resources=8,
                )
            ],
            resources=[
                {"name": "res_a", "experience_level": 2, "productivity_level": 1.0},
                {"name": "res_b", "experience_level": 2, "productivity_level": 1.0},
                {"name": "res_c", "experience_level": 2, "productivity_level": 1.0},
                {"name": "res_d", "experience_level": 2, "productivity_level": 1.0},
                {"name": "res_e", "experience_level": 2, "productivity_level": 1.0},
                {"name": "res_f", "experience_level": 2, "productivity_level": 1.0},
                {"name": "res_g", "experience_level": 2, "productivity_level": 1.0},
                {"name": "res_h", "experience_level": 2, "productivity_level": 1.0},
            ],
        )

        scheduler = TaskScheduler(project)
        effort_hours = 8.0
        expected_cap = TaskScheduler._practical_task_resource_cap(effort_hours)
        constrained = scheduler.schedule_tasks(
            {"task_001": effort_hours},
            use_resource_constraints=True,
        )

        assert expected_cap == 1
        assert constrained["task_001"]["end"] == effort_hours / expected_cap

    def test_practical_task_resource_cap_applies_coordination_ceiling(self):
        """Auto-cap should not exceed the global per-task coordination ceiling."""
        assert (
            TaskScheduler._practical_task_resource_cap(400.0)
            == TaskScheduler.MAX_ASSIGNEES_PER_TASK
        )

    def test_schedule_tasks_resource_constraints_are_calendar_aware(self):
        """Constrained mode should skip weekend non-working days."""
        project = Project(
            project=ProjectMetadata(name="Calendar Test", start_date=date(2025, 1, 3)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                    resources=["res_a"],
                )
            ],
            resources=[
                {"name": "res_a", "experience_level": 2, "productivity_level": 1.0}
            ],
        )

        scheduler = TaskScheduler(project)
        schedule = scheduler.schedule_tasks(
            {"task_001": 16.0},
            use_resource_constraints=True,
            start_date=project.project.start_date,
            hours_per_day=8.0,
        )

        # Friday 8h + weekend gap + Monday 8h => end at hour 80 from Friday 00:00
        assert schedule["task_001"]["end"] == 80.0

    def test_schedule_tasks_resource_constraints_respect_planned_absence(self):
        """Constrained mode should treat planned_absence dates as non-working."""
        project = Project(
            project=ProjectMetadata(name="Absence Test", start_date=date(2025, 1, 6)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                    resources=["res_a"],
                )
            ],
            resources=[
                {
                    "name": "res_a",
                    "experience_level": 2,
                    "productivity_level": 1.0,
                    "planned_absence": ["2025-01-06"],
                }
            ],
        )

        scheduler = TaskScheduler(project)
        schedule = scheduler.schedule_tasks(
            {"task_001": 8.0},
            use_resource_constraints=True,
            start_date=project.project.start_date,
            hours_per_day=8.0,
        )

        # Monday absent; task runs Tuesday 00:00-08:00 => end at hour 32
        assert schedule["task_001"]["start"] == 24.0
        assert schedule["task_001"]["end"] == 32.0

    def test_schedule_tasks_resource_constraints_use_custom_calendar_windows(self):
        """Constrained mode should honor custom work hours and holidays."""
        project = Project(
            project=ProjectMetadata(
                name="Custom Calendar",
                start_date=date(2025, 1, 6),
            ),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                    resources=["res_a"],
                )
            ],
            resources=[
                {
                    "name": "res_a",
                    "experience_level": 2,
                    "productivity_level": 1.0,
                    "calendar": "short_week",
                }
            ],
            calendars=[
                {
                    "id": "short_week",
                    "work_hours_per_day": 6.0,
                    "work_days": [1, 2, 3, 4, 5],
                    "holidays": ["2025-01-07"],
                }
            ],
        )

        scheduler = TaskScheduler(project)
        schedule = scheduler.schedule_tasks(
            {"task_001": 12.0},
            use_resource_constraints=True,
            start_date=project.project.start_date,
            hours_per_day=8.0,
        )

        # Monday 6h + Tuesday holiday + Wednesday 6h => end at hour 54.
        assert schedule["task_001"]["start"] == 0.0
        assert schedule["task_001"]["end"] == 54.0

    def test_get_critical_paths_returns_full_sequences(self):
        """Test tracing all full critical path sequences in a branching schedule."""
        project = Project(
            project=ProjectMetadata(name="Branching", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="Start",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                ),
                Task(
                    id="task_002",
                    name="Branch A",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                    dependencies=["task_001"],
                ),
                Task(
                    id="task_003",
                    name="Branch B",
                    estimate=TaskEstimate(low=1, expected=1, high=1),
                    dependencies=["task_001"],
                ),
            ],
        )

        scheduler = TaskScheduler(project)
        schedule = scheduler.schedule_tasks(
            {"task_001": 1.0, "task_002": 1.0, "task_003": 1.0}
        )

        critical_paths = scheduler.get_critical_paths(schedule)

        assert critical_paths == [
            ("task_001", "task_002"),
            ("task_001", "task_003"),
        ]

    def test_get_critical_path_empty_schedule(self):
        """Test critical path with empty schedule."""
        project = Project(
            project=ProjectMetadata(name="Test", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=2, high=5),
                )
            ],
        )
        scheduler = TaskScheduler(project)
        critical_path = scheduler.get_critical_path({})
        assert len(critical_path) == 0

    def test_topological_sort_circular_dependency(self):
        """Test that circular dependency is detected in topological sort."""
        # Note: Circular dependencies are caught during Project validation
        # This test verifies the scheduler's own circular dependency detection
        # We can't easily create a project with circular dependencies through
        # normal means, so we test that the project validation catches it
        from mcprojsim.models.project import (
            Project,
            ProjectMetadata,
            Task,
            TaskEstimate,
        )
        from datetime import date

        # Try to create a project with circular dependency - should fail at validation
        with pytest.raises(ValueError, match="Circular dependency"):
            Project(
                project=ProjectMetadata(name="Test", start_date=date(2025, 1, 1)),
                tasks=[
                    Task(
                        id="task_001",
                        name="Task 1",
                        estimate=TaskEstimate(low=1, expected=2, high=5),
                        dependencies=["task_002"],
                    ),
                    Task(
                        id="task_002",
                        name="Task 2",
                        estimate=TaskEstimate(low=1, expected=2, high=5),
                        dependencies=["task_001"],
                    ),
                ],
            )


class TestSimulationEngine:
    """Tests for simulation engine."""

    @pytest.fixture
    def simple_project(self):
        """Create a simple project."""
        return Project(
            project=ProjectMetadata(name="Test", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=2, high=5),
                )
            ],
        )

    def test_engine_initialization(self):
        """Test engine initialization."""
        engine = SimulationEngine(iterations=100, random_seed=42)
        assert engine.iterations == 100
        assert engine.random_seed == 42

    def test_run_simulation(self, simple_project):
        """Test running simulation."""
        engine = SimulationEngine(iterations=10, random_seed=42, show_progress=False)
        results = engine.run(simple_project)

        assert results.iterations == 10
        assert results.project_name == "Test"
        assert len(results.durations) == 10
        assert results.mean > 0
        assert results.median > 0

    def test_run_simulation_populates_constrained_diagnostics(self):
        """Resource-constrained runs should include constrained diagnostics."""
        project = Project(
            project=ProjectMetadata(name="Constrained", start_date=date(2025, 1, 6)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=8, expected=9, high=10),
                    resources=["res_a"],
                ),
                Task(
                    id="task_002",
                    name="Task 2",
                    estimate=TaskEstimate(low=8, expected=9, high=10),
                    resources=["res_a"],
                ),
            ],
            resources=[
                {
                    "name": "res_a",
                    "experience_level": 2,
                    "productivity_level": 1.0,
                }
            ],
        )

        engine = SimulationEngine(iterations=5, random_seed=42, show_progress=False)
        results = engine.run(project)

        assert results.resource_constraints_active is True
        assert results.schedule_mode == "resource_constrained"
        assert results.resource_wait_time_hours >= 0.0
        assert results.calendar_delay_time_hours >= 0.0
        assert 0.0 <= results.resource_utilization <= 1.0

    def test_engine_passes_config_to_task_scheduler(self, monkeypatch, simple_project):
        """SimulationEngine should pass its active config into TaskScheduler."""
        captured: dict[str, Config] = {}

        class FakeTaskScheduler:
            def __init__(self, project, random_state, config) -> None:
                captured["config"] = config

            def schedule_tasks(
                self,
                task_durations,
                *,
                use_resource_constraints=False,
                return_diagnostics=False,
                start_date=None,
                hours_per_day=8.0,
                task_priority=None,
            ):
                return {"task_001": {"start": 0.0, "end": 1.0, "duration": 1.0}}, {
                    "resource_wait_time_hours": 0.0,
                    "resource_utilization": 0.0,
                    "calendar_delay_time_hours": 0.0,
                }

            def max_parallel_tasks(self, schedule):
                return 1

            def calculate_slack(self, schedule):
                return {"task_001": 0.0}

            def get_critical_paths(self, schedule):
                return [("task_001",)]

        config = Config.model_validate(
            {
                "sprint_defaults": {
                    "sickness": {
                        "duration_log_mu": 1.2,
                        "duration_log_sigma": 0.2,
                    }
                }
            }
        )
        engine = SimulationEngine(
            iterations=1,
            random_seed=42,
            config=config,
            show_progress=False,
        )

        monkeypatch.setattr(
            "mcprojsim.simulation.engine.TaskScheduler", FakeTaskScheduler
        )

        engine.run(simple_project)

        assert captured["config"] is config

    def test_run_simulation_computes_updated_default_percentiles(self, simple_project):
        """Test simulation computes P25 and P99 for projects using default levels."""
        engine = SimulationEngine(iterations=10, random_seed=42, show_progress=False)
        results = engine.run(simple_project)

        assert 25 in results.percentiles
        assert 99 in results.percentiles
        assert results.percentiles[25] == pytest.approx(
            float(np.percentile(results.durations, 25))
        )
        assert results.percentiles[99] == pytest.approx(
            float(np.percentile(results.durations, 99))
        )

    def test_run_simulation_caches_static_task_inputs(self, monkeypatch):
        """Static estimate resolution and uncertainty lookup happen once per task."""
        config = Config.get_default().model_copy(deep=True)
        call_counts = {
            "resolve_t_shirt_size": 0,
            "get_story_point": 0,
            "get_uncertainty_multiplier": 0,
        }

        original_resolve_t_shirt_size = Config.resolve_t_shirt_size
        original_get_story_point = Config.get_story_point
        original_get_uncertainty_multiplier = Config.get_uncertainty_multiplier

        def counting_resolve_t_shirt_size(self, size):
            call_counts["resolve_t_shirt_size"] += 1
            return original_resolve_t_shirt_size(self, size)

        def counting_get_story_point(self, points):
            call_counts["get_story_point"] += 1
            return original_get_story_point(self, points)

        def counting_get_uncertainty_multiplier(self, factor_name, level):
            call_counts["get_uncertainty_multiplier"] += 1
            return original_get_uncertainty_multiplier(self, factor_name, level)

        monkeypatch.setattr(
            Config, "resolve_t_shirt_size", counting_resolve_t_shirt_size
        )
        monkeypatch.setattr(Config, "get_story_point", counting_get_story_point)
        monkeypatch.setattr(
            Config,
            "get_uncertainty_multiplier",
            counting_get_uncertainty_multiplier,
        )

        project = Project(
            project=ProjectMetadata(name="Cached Inputs", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="T-shirt task",
                    estimate=TaskEstimate(t_shirt_size="M"),
                    uncertainty_factors=UncertaintyFactors(
                        team_experience="high",
                        requirements_maturity=None,
                        technical_complexity=None,
                        team_distribution=None,
                        integration_complexity=None,
                    ),
                ),
                Task(
                    id="task_002",
                    name="Story-point task",
                    estimate=TaskEstimate(story_points=5),
                    uncertainty_factors=UncertaintyFactors(
                        team_experience="medium",
                        requirements_maturity=None,
                        technical_complexity=None,
                        team_distribution=None,
                        integration_complexity=None,
                    ),
                ),
            ],
        )

        engine = SimulationEngine(
            iterations=6,
            random_seed=42,
            config=config,
            show_progress=False,
        )
        engine.run(project)

        assert call_counts["resolve_t_shirt_size"] == 1
        assert call_counts["get_story_point"] == 1
        assert call_counts["get_uncertainty_multiplier"] == 2

    def test_simulation_reproducibility(self, simple_project):
        """Test simulation reproducibility with same seed."""
        engine1 = SimulationEngine(iterations=10, random_seed=42, show_progress=False)
        results1 = engine1.run(simple_project)

        engine2 = SimulationEngine(iterations=10, random_seed=42, show_progress=False)
        results2 = engine2.run(simple_project)

        assert np.allclose(results1.durations, results2.durations)

    def test_simulation_reproducibility_with_constrained_sickness(self):
        """Constrained scheduling should also be reproducible with the same seed."""
        project = Project(
            project=ProjectMetadata(
                name="Seeded Constrained", start_date=date(2025, 1, 6)
            ),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=8, expected=10, high=12),
                    resources=["res_a"],
                ),
                Task(
                    id="task_002",
                    name="Task 2",
                    estimate=TaskEstimate(low=8, expected=10, high=12),
                    resources=["res_a"],
                    dependencies=["task_001"],
                ),
            ],
            resources=[
                {
                    "name": "res_a",
                    "experience_level": 2,
                    "productivity_level": 1.0,
                    "sickness_prob": 0.2,
                }
            ],
        )

        engine1 = SimulationEngine(iterations=25, random_seed=42, show_progress=False)
        results1 = engine1.run(project)

        engine2 = SimulationEngine(iterations=25, random_seed=42, show_progress=False)
        results2 = engine2.run(project)

        assert np.allclose(results1.durations, results2.durations)

    def test_run_simulation_stores_full_critical_paths(self, monkeypatch):
        """Test that simulation stores aggregated critical path sequences."""
        project = Project(
            project=ProjectMetadata(name="Branching", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="Start",
                    estimate=TaskEstimate(low=1, expected=2, high=3),
                ),
                Task(
                    id="task_002",
                    name="Branch A",
                    estimate=TaskEstimate(low=1, expected=2, high=3),
                    dependencies=["task_001"],
                ),
                Task(
                    id="task_003",
                    name="Branch B",
                    estimate=TaskEstimate(low=1, expected=2, high=3),
                    dependencies=["task_001"],
                ),
            ],
        )

        config = Config(simulation={"max_stored_critical_paths": 1})
        engine = SimulationEngine(
            iterations=5,
            random_seed=42,
            config=config,
            show_progress=False,
        )
        monkeypatch.setattr(engine.sampler, "sample", lambda estimate: 1.0)

        results = engine.run(project)

        assert len(results.critical_path_sequences) == 1
        assert results.critical_path_sequences[0].path == (
            "task_001",
            "task_002",
        )
        assert results.critical_path_sequences[0].count == 5

    def test_apply_uncertainty_factors(self):
        """Test applying uncertainty factors."""
        # Use empty config for no uncertainty factors
        config = Config()
        engine = SimulationEngine(config=config, show_progress=False)

        task = Task(
            id="task_001",
            name="Task 1",
            estimate=TaskEstimate(low=1, expected=2, high=5),
        )

        # No uncertainty factors should not change duration
        adjusted = engine._apply_uncertainty_factors(task, 10.0)
        assert adjusted == 10.0

        # Test with uncertainty factors
        config_with_factors = Config(
            uncertainty_factors={
                "team_experience": {"high": 0.90, "medium": 1.0, "low": 1.30}
            }
        )
        engine2 = SimulationEngine(config=config_with_factors, show_progress=False)
        task_with_factors = Task(
            id="task_002",
            name="Task 2",
            estimate=TaskEstimate(low=1, expected=2, high=5),
            uncertainty_factors=UncertaintyFactors(team_experience="low"),
        )

        # Should multiply by 1.30
        adjusted2 = engine2._apply_uncertainty_factors(task_with_factors, 10.0)
        assert adjusted2 == 13.0

    def test_simulation_with_risks(self):
        """Test simulation with risks."""
        project = Project(
            project=ProjectMetadata(name="Test", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=2, high=5),
                    risks=[
                        Risk(
                            id="risk_001",
                            name="Risk",
                            probability=1.0,  # Always triggers
                            impact=5.0,
                        )
                    ],
                )
            ],
        )

        engine = SimulationEngine(iterations=10, random_seed=42, show_progress=False)
        results = engine.run(project)

        # Mean should be higher due to risk
        assert results.mean > 2.0


class TestProgressCallback:
    """Tests for the progress_callback parameter (P1-01)."""

    @pytest.fixture
    def three_task_project(self):
        return Project(
            project=ProjectMetadata(name="Progress Test", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=2, high=5),
                ),
                Task(
                    id="task_002",
                    name="Task 2",
                    estimate=TaskEstimate(low=2, expected=3, high=6),
                    dependencies=["task_001"],
                ),
                Task(
                    id="task_003",
                    name="Task 3",
                    estimate=TaskEstimate(low=1, expected=2, high=4),
                    dependencies=["task_002"],
                ),
            ],
        )

    def test_callback_invoked_with_correct_totals(self, three_task_project):
        """progress_callback should be called with (completed, total) at least once,
        and the last invocation should have completed == total."""
        calls: list[tuple[int, int]] = []

        def recorder(completed: int, total: int) -> None:
            calls.append((completed, total))

        engine = SimulationEngine(
            iterations=50,
            random_seed=42,
            show_progress=True,
            progress_callback=recorder,
        )
        engine.run(three_task_project)

        assert len(calls) > 0, "callback was never invoked"
        # Every call should report the correct total
        assert all(total == 50 for _, total in calls)
        # Final call should have completed == total
        assert calls[-1][0] == 50

    def test_callback_completed_increases_monotonically(self, three_task_project):
        """Completed count should never decrease between calls."""
        calls: list[tuple[int, int]] = []

        engine = SimulationEngine(
            iterations=50,
            random_seed=42,
            show_progress=True,
            progress_callback=lambda c, t: calls.append((c, t)),
        )
        engine.run(three_task_project)

        completed_values = [c for c, _ in calls]
        assert completed_values == sorted(completed_values)

    def test_callback_suppresses_stdout(self, three_task_project, capsys):
        """When a callback is provided, nothing should be written to stdout."""
        engine = SimulationEngine(
            iterations=50,
            random_seed=42,
            show_progress=True,
            progress_callback=lambda c, t: None,
        )
        engine.run(three_task_project)

        captured = capsys.readouterr()
        assert "Progress:" not in captured.out

    def test_no_callback_is_default(self):
        """Without progress_callback, engine should behave exactly as before."""
        engine = SimulationEngine(iterations=10, random_seed=42)
        assert engine._progress_callback is None

    def test_callback_with_show_progress_false(self, three_task_project):
        """With show_progress=False and no callback, no callback is invoked."""
        calls: list[tuple[int, int]] = []

        engine = SimulationEngine(
            iterations=50,
            random_seed=42,
            show_progress=False,
            progress_callback=lambda c, t: calls.append((c, t)),
        )
        engine.run(three_task_project)

        # show_progress=False suppresses the progress-reporting code path,
        # so the callback should not be invoked.
        assert len(calls) == 0

    def test_results_unchanged_with_callback(self, three_task_project):
        """Results should be identical whether or not a callback is used."""
        engine_no_cb = SimulationEngine(
            iterations=100, random_seed=42, show_progress=False
        )
        results_no_cb = engine_no_cb.run(three_task_project)

        engine_cb = SimulationEngine(
            iterations=100,
            random_seed=42,
            show_progress=True,
            progress_callback=lambda c, t: None,
        )
        results_cb = engine_cb.run(three_task_project)

        assert results_no_cb.mean == pytest.approx(results_cb.mean)
        assert results_no_cb.median == pytest.approx(results_cb.median)
        np.testing.assert_array_almost_equal(
            results_no_cb.durations, results_cb.durations
        )


class TestSimulationCancellation:
    """Tests for the cancellation flag (P1-02)."""

    @pytest.fixture
    def three_task_project(self):
        return Project(
            project=ProjectMetadata(name="Cancel Test", start_date=date(2025, 1, 1)),
            tasks=[
                Task(
                    id="task_001",
                    name="Task 1",
                    estimate=TaskEstimate(low=1, expected=2, high=5),
                ),
                Task(
                    id="task_002",
                    name="Task 2",
                    estimate=TaskEstimate(low=2, expected=3, high=6),
                    dependencies=["task_001"],
                ),
                Task(
                    id="task_003",
                    name="Task 3",
                    estimate=TaskEstimate(low=1, expected=2, high=4),
                    dependencies=["task_002"],
                ),
            ],
        )

    def test_cancel_before_run_raises(self, three_task_project):
        """Calling cancel() before run() should raise on the very first iteration."""
        engine = SimulationEngine(iterations=10000, random_seed=42, show_progress=False)
        engine.cancel()

        with pytest.raises(SimulationCancelled):
            engine.run(three_task_project)

    def test_cancel_from_callback_raises(self, three_task_project):
        """Cancelling from inside a progress callback should stop the simulation."""
        engine = SimulationEngine(
            iterations=10000,
            random_seed=42,
            show_progress=True,
            progress_callback=lambda c, t: engine.cancel() if c >= 10 else None,
        )

        with pytest.raises(SimulationCancelled):
            engine.run(three_task_project)

    def test_cancel_from_thread(self, three_task_project):
        """Cancelling from another thread should stop a long-running simulation."""
        import threading

        engine = SimulationEngine(
            iterations=100_000, random_seed=42, show_progress=False
        )

        exc_holder: list[BaseException | None] = [None]

        def run_engine():
            try:
                engine.run(three_task_project)
            except SimulationCancelled as e:
                exc_holder[0] = e

        t = threading.Thread(target=run_engine)
        t.start()

        # Give the simulation a moment to start iterating, then cancel.
        import time

        time.sleep(0.05)
        engine.cancel()
        t.join(timeout=5.0)

        assert not t.is_alive(), "Simulation thread did not stop in time"
        assert isinstance(exc_holder[0], SimulationCancelled)

    def test_cancellation_is_not_set_by_default(self):
        """A freshly created engine should not be cancelled."""
        engine = SimulationEngine(iterations=10, random_seed=42, show_progress=False)
        assert engine._cancelled is False

    def test_exception_is_simulation_cancelled(self):
        """SimulationCancelled should be a subclass of Exception."""
        assert issubclass(SimulationCancelled, Exception)
