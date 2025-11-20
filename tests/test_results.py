"""Tests for simulation results model."""

import pytest
import numpy as np

from mcprojsim.models.simulation import SimulationResults


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
