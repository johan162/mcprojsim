"""Tests for simulation results model."""

import pytest
import numpy as np
from datetime import date

from mcprojsim.models.simulation import CriticalPathRecord, SimulationResults
from mcprojsim.models.sprint_simulation import SprintPlanningResults


class TestSimulationResults:
    """Tests for simulation results."""

    @pytest.fixture
    def sample_results(self):
        """Create sample simulation results."""
        durations = np.array(
            [10.0, 12.0, 15.0, 18.0, 20.0, 22.0, 25.0, 28.0, 30.0, 35.0]
        )
        task_durations = {
            "task_001": np.array([2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0]),
            "task_002": np.array(
                [8.0, 9.0, 11.0, 13.0, 14.0, 15.0, 17.0, 19.0, 20.0, 24.0]
            ),
        }

        results = SimulationResults(
            iterations=10,
            project_name="Test Project",
            durations=durations,
            task_durations=task_durations,
            critical_path_frequency={"task_001": 10, "task_002": 7, "task_003": 3},
            critical_path_sequences=[
                CriticalPathRecord(
                    path=("task_001", "task_002"),
                    count=7,
                    frequency=0.7,
                ),
                CriticalPathRecord(
                    path=("task_001", "task_003"),
                    count=3,
                    frequency=0.3,
                ),
            ],
            random_seed=42,
        )
        return results

    def test_calculate_statistics(self, sample_results):
        """Test calculating statistics."""
        sample_results.calculate_statistics()

        assert sample_results.mean == pytest.approx(21.5, abs=0.1)
        assert sample_results.median == pytest.approx(21.0, abs=0.1)
        assert sample_results.std_dev > 0
        assert sample_results.min_duration == 10.0
        assert sample_results.max_duration == 35.0

    def test_percentile(self, sample_results):
        """Test getting percentile."""
        p50 = sample_results.percentile(50)
        p90 = sample_results.percentile(90)

        assert p50 > 0
        assert p90 > p50

    def test_percentile_caching(self, sample_results):
        """Test that percentiles are cached."""
        p50_1 = sample_results.percentile(50)
        p50_2 = sample_results.percentile(50)

        assert p50_1 == p50_2
        assert 50 in sample_results.percentiles

    def test_get_critical_path(self, sample_results):
        """Test getting critical path."""
        critical_path = sample_results.get_critical_path()

        assert critical_path["task_001"] == 1.0
        assert critical_path["task_002"] == 0.7
        assert critical_path["task_003"] == 0.3

    def test_get_histogram_data(self, sample_results):
        """Test getting histogram data."""
        bin_edges, counts = sample_results.get_histogram_data(bins=5)

        assert len(bin_edges) == 6  # bins + 1
        assert len(counts) == 5
        assert np.sum(counts) == len(sample_results.durations)

    def test_to_dict(self, sample_results):
        """Test converting to dictionary."""
        sample_results.calculate_statistics()
        sample_results.percentile(50)
        sample_results.percentile(90)

        data = sample_results.to_dict()

        assert data["project_name"] == "Test Project"
        assert data["iterations"] == 10
        assert data["random_seed"] == 42
        assert "statistics" in data
        assert "percentiles" in data
        assert "critical_path" in data

    def test_coefficient_of_variation(self, sample_results):
        """Test coefficient of variation in dict."""
        sample_results.calculate_statistics()
        data = sample_results.to_dict()

        cv = data["statistics"]["coefficient_of_variation"]
        expected_cv = sample_results.std_dev / sample_results.mean
        assert cv == pytest.approx(expected_cv, abs=0.01)

    def test_get_critical_path_sequences(self, sample_results):
        """Test retrieving stored critical path sequences."""
        paths = sample_results.get_critical_path_sequences()

        assert len(paths) == 2
        assert paths[0].path == ("task_001", "task_002")
        assert paths[0].count == 7

    def test_get_critical_path_sequences_with_limit(self, sample_results):
        """Test limiting the number of reported critical path sequences."""
        paths = sample_results.get_critical_path_sequences(top_n=1)

        assert len(paths) == 1
        assert paths[0].path == ("task_001", "task_002")

    def test_get_most_frequent_critical_path(self, sample_results):
        """Test retrieving the most frequent critical path sequence."""
        record = sample_results.get_most_frequent_critical_path()

        assert record is not None
        assert record.path == ("task_001", "task_002")

    def test_to_dict_includes_critical_path_sequences(self, sample_results):
        """Test critical path sequences are included in the exported dictionary."""
        sample_results.calculate_statistics()
        data = sample_results.to_dict()

        assert "critical_path_sequences" in data
        assert data["critical_path_sequences"][0]["path"] == ["task_001", "task_002"]

    def test_to_dict_includes_constrained_diagnostics(self, sample_results):
        """Test constrained scheduling metadata is included in dictionary export."""
        sample_results.schedule_mode = "resource_constrained"
        sample_results.resource_constraints_active = True
        sample_results.resource_wait_time_hours = 2.0
        sample_results.resource_utilization = 0.66
        sample_results.calendar_delay_time_hours = 5.0

        data = sample_results.to_dict()

        assert data["schedule_mode"] == "resource_constrained"
        assert data["resource_constraints_active"] is True
        diagnostics = data["constrained_diagnostics"]
        assert diagnostics["resource_wait_time_hours"] == pytest.approx(2.0)
        assert diagnostics["resource_utilization"] == pytest.approx(0.66)
        assert diagnostics["calendar_delay_time_hours"] == pytest.approx(5.0)


class TestSprintPlanningResults:
    """Tests for sprint-planning results."""

    @pytest.fixture
    def sample_sprint_results(self):
        """Create sample sprint-planning results."""
        results = SprintPlanningResults(
            iterations=5,
            project_name="Sprint Project",
            sprint_length_weeks=2,
            sprint_counts=np.array([2.0, 3.0, 3.0, 4.0, 5.0]),
            random_seed=42,
            start_date=date(2025, 1, 6),
            planning_confidence_level=0.80,
            removed_work_treatment="churn_only",
            historical_diagnostics={"sampling_mode": "matching_cadence"},
            planned_commitment_guidance=4.5,
            carryover_statistics={"mean": 1.2},
            spillover_statistics={"aggregate_spillover_rate": {"mean": 0.3}},
            disruption_statistics={"observed_frequency": 0.1},
            burnup_percentiles=[{"sprint_number": 1.0, "p50": 3.0}],
        )
        return results

    def test_calculate_statistics(self, sample_sprint_results):
        """Sprint results should calculate basic descriptive statistics."""
        sample_sprint_results.calculate_statistics()

        assert sample_sprint_results.mean == pytest.approx(3.4)
        assert sample_sprint_results.median == pytest.approx(3.0)
        assert sample_sprint_results.std_dev > 0
        assert sample_sprint_results.min_sprints == 2.0
        assert sample_sprint_results.max_sprints == 5.0

    def test_date_percentile_uses_sprint_boundaries(self, sample_sprint_results):
        """Date projection should move by whole sprint boundaries."""
        projected = sample_sprint_results.date_percentile(50)

        assert projected == date(2025, 2, 3)

    def test_to_dict(self, sample_sprint_results):
        """Sprint results should serialize cleanly for exporters."""
        sample_sprint_results.calculate_statistics()
        sample_sprint_results.percentile(80)
        sample_sprint_results.date_percentile(80)

        data = sample_sprint_results.to_dict()

        assert data["project_name"] == "Sprint Project"
        assert data["sprint_length_weeks"] == 2
        assert data["planned_commitment_guidance"] == pytest.approx(4.5)
        assert data["carryover_statistics"]["mean"] == pytest.approx(1.2)
        assert data["burnup_percentiles"][0]["p50"] == pytest.approx(3.0)
        assert "statistics" in data
        assert "date_percentiles" in data
