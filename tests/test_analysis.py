"""Tests for analysis components."""

import pytest
import numpy as np

from mcprojsim.analysis.statistics import StatisticalAnalyzer
from mcprojsim.analysis.sensitivity import SensitivityAnalyzer
from mcprojsim.analysis.critical_path import CriticalPathAnalyzer
from mcprojsim.models.simulation import SimulationResults


class TestStatisticalAnalyzer:
    """Tests for statistical analyzer."""

    def test_calculate_statistics(self):
        """Test calculating statistics."""
        durations = np.array([10.0, 12.0, 15.0, 18.0, 20.0])
        stats = StatisticalAnalyzer.calculate_statistics(durations)
        
        assert stats["mean"] == 15.0
        assert stats["median"] == 15.0
        assert stats["min"] == 10.0
        assert stats["max"] == 20.0
        assert stats["range"] == 10.0
        assert stats["variance"] > 0

    def test_calculate_percentiles(self):
        """Test calculating percentiles."""
        durations = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
        percentiles = StatisticalAnalyzer.calculate_percentiles(durations, [50, 90])
        
        assert 50 in percentiles
        assert 90 in percentiles
        assert percentiles[50] == 5.5
        assert percentiles[90] > 9.0

    def test_confidence_interval(self):
        """Test confidence interval calculation."""
        durations = np.array([10.0, 12.0, 15.0, 18.0, 20.0] * 10)
        lower, upper = StatisticalAnalyzer.confidence_interval(durations, 0.95)
        
        assert lower < np.mean(durations)
        assert upper > np.mean(durations)


class TestSensitivityAnalyzer:
    """Tests for sensitivity analyzer."""

    @pytest.fixture
    def sample_results(self):
        """Create sample simulation results."""
        durations = np.array([10.0, 12.0, 15.0, 18.0, 20.0])
        task_durations = {
            "task_001": np.array([2.0, 3.0, 4.0, 5.0, 6.0]),
            "task_002": np.array([8.0, 9.0, 11.0, 13.0, 14.0]),
        }
        
        results = SimulationResults(
            iterations=5,
            project_name="Test",
            durations=durations,
            task_durations=task_durations,
        )
        results.calculate_statistics()
        return results

    def test_calculate_correlations(self, sample_results):
        """Test calculating correlations."""
        correlations = SensitivityAnalyzer.calculate_correlations(sample_results)
        
        assert "task_001" in correlations
        assert "task_002" in correlations
        assert -1.0 <= correlations["task_001"] <= 1.0
        assert -1.0 <= correlations["task_002"] <= 1.0

    def test_get_top_contributors(self, sample_results):
        """Test getting top contributors."""
        top_tasks = SensitivityAnalyzer.get_top_contributors(sample_results, n=1)
        
        assert len(top_tasks) == 1
        assert isinstance(top_tasks[0], tuple)
        assert isinstance(top_tasks[0][0], str)
        assert isinstance(top_tasks[0][1], float)


class TestCriticalPathAnalyzer:
    """Tests for critical path analyzer."""

    @pytest.fixture
    def sample_results(self):
        """Create sample simulation results with critical path data."""
        durations = np.array([10.0, 12.0, 15.0])
        results = SimulationResults(
            iterations=3,
            project_name="Test",
            durations=durations,
            critical_path_frequency={"task_001": 3, "task_002": 2, "task_003": 1},
        )
        results.calculate_statistics()
        return results

    def test_get_criticality_index(self, sample_results):
        """Test getting criticality index."""
        criticality = CriticalPathAnalyzer.get_criticality_index(sample_results)
        
        assert criticality["task_001"] == 1.0
        assert criticality["task_002"] == pytest.approx(0.667, abs=0.01)
        assert criticality["task_003"] == pytest.approx(0.333, abs=0.01)

    def test_get_most_critical_tasks(self, sample_results):
        """Test getting most critical tasks."""
        critical_tasks = CriticalPathAnalyzer.get_most_critical_tasks(
            sample_results, threshold=0.5
        )
        
        assert "task_001" in critical_tasks
        assert "task_002" in critical_tasks
        assert "task_003" not in critical_tasks
