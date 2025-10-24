"""Tests for exporters."""

import pytest
import json
import csv
from pathlib import Path

from mcprojsim.exporters import JSONExporter, CSVExporter, HTMLExporter
from mcprojsim.models.simulation import SimulationResults
import numpy as np


@pytest.fixture
def sample_results():
    """Create sample simulation results."""
    durations = np.array([10.0, 12.0, 15.0, 18.0, 20.0])
    task_durations = {
        "task_001": np.array([2.0, 3.0, 4.0, 5.0, 6.0]),
        "task_002": np.array([8.0, 9.0, 11.0, 13.0, 14.0]),
    }
    
    results = SimulationResults(
        iterations=5,
        project_name="Test Project",
        durations=durations,
        task_durations=task_durations,
        critical_path_frequency={"task_001": 5, "task_002": 3},
        random_seed=42,
    )
    results.calculate_statistics()
    results.percentile(50)
    results.percentile(90)
    return results


class TestJSONExporter:
    """Tests for JSON exporter."""

    def test_export_json(self, sample_results, tmp_path):
        """Test exporting to JSON."""
        output_file = tmp_path / "results.json"
        JSONExporter.export(sample_results, output_file)
        
        assert output_file.exists()
        
        with open(output_file, "r") as f:
            data = json.load(f)
        
        assert data["project"]["name"] == "Test Project"
        assert data["simulation"]["iterations"] == 5
        assert "statistics" in data
        assert "percentiles" in data
        assert "critical_path" in data

    def test_json_contains_statistics(self, sample_results, tmp_path):
        """Test that JSON contains statistics."""
        output_file = tmp_path / "results.json"
        JSONExporter.export(sample_results, output_file)
        
        with open(output_file, "r") as f:
            data = json.load(f)
        
        stats = data["statistics"]
        assert "mean" in stats
        assert "median" in stats
        assert "std_dev" in stats
        assert "min" in stats
        assert "max" in stats

    def test_numpy_encoder_integer(self):
        """Test NumpyEncoder handles numpy integers."""
        from mcprojsim.exporters.json_exporter import NumpyEncoder
        encoder = NumpyEncoder()
        result = encoder.default(np.int64(42))
        assert result == 42
        assert isinstance(result, int)

    def test_numpy_encoder_float(self):
        """Test NumpyEncoder handles numpy floats."""
        from mcprojsim.exporters.json_exporter import NumpyEncoder
        encoder = NumpyEncoder()
        result = encoder.default(np.float64(3.14))
        assert result == 3.14
        assert isinstance(result, float)

    def test_numpy_encoder_array(self):
        """Test NumpyEncoder handles numpy arrays."""
        from mcprojsim.exporters.json_exporter import NumpyEncoder
        encoder = NumpyEncoder()
        arr = np.array([1, 2, 3])
        result = encoder.default(arr)
        assert result == [1, 2, 3]
        assert isinstance(result, list)


class TestCSVExporter:
    """Tests for CSV exporter."""

    def test_export_csv(self, sample_results, tmp_path):
        """Test exporting to CSV."""
        output_file = tmp_path / "results.csv"
        CSVExporter.export(sample_results, output_file)
        
        assert output_file.exists()
        
        with open(output_file, "r") as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        assert len(rows) > 0
        assert any("Test Project" in str(row) for row in rows)

    def test_csv_contains_metrics(self, sample_results, tmp_path):
        """Test that CSV contains metrics."""
        output_file = tmp_path / "results.csv"
        CSVExporter.export(sample_results, output_file)
        
        with open(output_file, "r") as f:
            content = f.read()
        
        assert "Mean" in content
        assert "Median" in content
        assert "Percentile" in content or "P50" in content

    def test_csv_contains_histogram(self, sample_results, tmp_path):
        """Test that CSV contains histogram data."""
        output_file = tmp_path / "results.csv"
        CSVExporter.export(sample_results, output_file)
        
        with open(output_file, "r") as f:
            content = f.read()
        
        assert "Histogram Data" in content
        assert "Bin Edge (days)" in content
        assert "Count" in content
        assert "Cumulative %" in content
        
        # Verify we have histogram data rows
        lines = content.split('\n')
        histogram_section = False
        histogram_data_rows = 0
        
        for line in lines:
            if "Histogram Data" in line:
                histogram_section = True
            elif histogram_section and line and not line.startswith("Bin Edge"):
                # Count data rows (should have numeric values)
                parts = line.split(',')
                if len(parts) >= 3:
                    try:
                        float(parts[0])
                        histogram_data_rows += 1
                    except (ValueError, IndexError):
                        pass
        
        # Should have at least some histogram bins
        assert histogram_data_rows > 0


class TestHTMLExporter:
    """Tests for HTML exporter."""

    def test_export_html(self, sample_results, tmp_path):
        """Test exporting to HTML."""
        output_file = tmp_path / "results.html"
        HTMLExporter.export(sample_results, output_file)
        
        assert output_file.exists()
        
        with open(output_file, "r") as f:
            content = f.read()
        
        assert "Test Project" in content
        assert "<!DOCTYPE html>" in content
        assert "<html" in content

    def test_html_contains_statistics(self, sample_results, tmp_path):
        """Test that HTML contains statistics."""
        output_file = tmp_path / "results.html"
        HTMLExporter.export(sample_results, output_file)
        
        with open(output_file, "r") as f:
            content = f.read()
        
        assert "Mean" in content or "mean" in content
        assert "Median" in content or "median" in content

    def test_html_contains_thermometer(self, sample_results, tmp_path):
        """Test that HTML contains thermometer visualization."""
        output_file = tmp_path / "results.html"
        HTMLExporter.export(sample_results, output_file)
        
        with open(output_file, "r") as f:
            content = f.read()
        
        assert "thermometer" in content.lower()
        assert "Probability of Success" in content
        assert "thermometer-segment" in content
