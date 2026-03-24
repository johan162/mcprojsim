"""Tests for exporters."""

from datetime import date
import pytest
import json
import csv

from mcprojsim.exporters import JSONExporter, CSVExporter, HTMLExporter
from mcprojsim.config import Config
from mcprojsim.models.project import Project, ProjectMetadata, Task, TaskEstimate
from mcprojsim.models.simulation import CriticalPathRecord, SimulationResults
from mcprojsim.models.sprint_simulation import SprintPlanningResults
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
        critical_path_sequences=[
            CriticalPathRecord(
                path=("task_001", "task_002"),
                count=3,
                frequency=0.6,
            ),
            CriticalPathRecord(
                path=("task_001", "task_003"),
                count=2,
                frequency=0.4,
            ),
        ],
        random_seed=42,
    )
    results.calculate_statistics()
    results.percentile(25)
    results.percentile(50)
    results.percentile(90)
    results.percentile(99)
    results.schedule_mode = "resource_constrained"
    results.resource_constraints_active = True
    results.resource_wait_time_hours = 1.25
    results.resource_utilization = 0.72
    results.calendar_delay_time_hours = 3.5
    return results


@pytest.fixture
def sample_sprint_results():
    """Create sample sprint-planning results."""
    results = SprintPlanningResults(
        iterations=5,
        project_name="Test Project",
        sprint_length_weeks=2,
        sprint_counts=np.array([2.0, 2.0, 3.0, 3.0, 4.0]),
        random_seed=42,
        start_date=date(2025, 1, 6),
        planning_confidence_level=0.8,
        removed_work_treatment="churn_only",
        historical_diagnostics={
            "sampling_mode": "matching_cadence",
            "observation_count": 3,
            "series_statistics": {
                "completed_units": {
                    "mean": 6.0,
                    "median": 6.0,
                    "std_dev": 0.82,
                    "min": 5.0,
                    "max": 7.0,
                },
                "spillover_units": {
                    "mean": 0.67,
                    "median": 1.0,
                    "std_dev": 0.47,
                    "min": 0.0,
                    "max": 1.0,
                },
            },
            "ratios": {
                "spillover_ratio": {
                    "mean": 0.1111,
                    "median": 0.1000,
                    "std_dev": 0.0500,
                    "min": 0.0,
                    "max": 0.2,
                    "percentiles": {50: 0.1, 80: 0.15, 90: 0.18},
                },
                "scope_addition_ratio": {
                    "mean": 0.0600,
                    "median": 0.0500,
                    "std_dev": 0.0300,
                    "min": 0.0,
                    "max": 0.1,
                    "percentiles": {50: 0.05, 80: 0.08, 90: 0.09},
                },
            },
            "correlations": {
                "completed_units|spillover_units": -0.4200,
                "completed_units|added_units": 0.3300,
            },
        },
        planned_commitment_guidance=4.5,
        carryover_statistics={"mean": 1.2, "p80": 2.0, "p90": 2.5, "max": 3.0},
        spillover_statistics={
            "aggregate_spillover_rate": {
                "mean": 0.3,
                "median": 0.25,
                "p80": 0.5,
                "p90": 0.6,
                "max": 0.8,
            }
        },
        disruption_statistics={
            "enabled": True,
            "configured_probability": 0.1,
            "observed_frequency": 0.2,
        },
        burnup_percentiles=[
            {"sprint_number": 1.0, "p50": 4.0, "p80": 5.0, "p90": 6.0},
            {"sprint_number": 2.0, "p50": 8.0, "p80": 9.0, "p90": 10.0},
        ],
    )
    results.calculate_statistics()
    for percentile in (50, 80, 90):
        results.percentile(percentile)
        results.date_percentile(percentile)
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
        assert "calendar_time_confidence_intervals" in data
        assert "25" in data["calendar_time_confidence_intervals"]
        assert "99" in data["calendar_time_confidence_intervals"]
        assert "critical_path" in data
        assert "critical_path_sequences" in data
        assert data["schedule"]["mode"] == "resource_constrained"
        assert data["schedule"]["resource_constraints_active"] is True

    def test_json_contains_constrained_diagnostics(self, sample_results, tmp_path):
        """Test that JSON includes constrained schedule diagnostics."""
        output_file = tmp_path / "results.json"
        JSONExporter.export(sample_results, output_file)

        with open(output_file, "r") as f:
            data = json.load(f)

        diagnostics = data["constrained_diagnostics"]
        assert diagnostics["resource_wait_time_hours"] == pytest.approx(1.25)
        assert diagnostics["resource_utilization"] == pytest.approx(0.72)
        assert diagnostics["calendar_delay_time_hours"] == pytest.approx(3.5)

    def test_json_contains_statistics(self, sample_results, tmp_path):
        """Test that JSON contains statistics."""
        output_file = tmp_path / "results.json"
        JSONExporter.export(sample_results, output_file)

        with open(output_file, "r") as f:
            data = json.load(f)

        stats = data["statistics"]
        assert "mean_hours" in stats
        assert "median_hours" in stats
        assert "std_dev_hours" in stats
        assert "min_hours" in stats
        assert "max_hours" in stats

    def test_json_contains_sprint_planning_section(
        self, sample_results, sample_sprint_results, tmp_path
    ):
        """Test that JSON export includes sprint-planning data when provided."""
        output_file = tmp_path / "results.json"
        JSONExporter.export(
            sample_results,
            output_file,
            sprint_results=sample_sprint_results,
        )

        with open(output_file, "r") as f:
            data = json.load(f)

        sprint_data = data["sprint_planning"]
        assert sprint_data["sprint_length_weeks"] == 2
        assert sprint_data["planned_commitment_guidance"] == pytest.approx(4.5)
        assert (
            sprint_data["historical_diagnostics"]["sampling_mode"] == "matching_cadence"
        )
        assert "80" in sprint_data["sprint_count_confidence_intervals"]
        assert "spillover_ratio" in sprint_data["ratio_summaries"]
        assert sprint_data["carryover_statistics"]["mean"] == pytest.approx(1.2)
        assert sprint_data["burnup_percentiles"][0]["p80"] == pytest.approx(5.0)
        assert sprint_data["historical_correlations"][
            "completed_units|spillover_units"
        ] == pytest.approx(-0.42)

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
        assert "P25" in content
        assert "P99" in content

    def test_csv_contains_critical_path_sequences(self, sample_results, tmp_path):
        """Test that CSV contains full critical path sequence reporting."""
        output_file = tmp_path / "results.csv"
        CSVExporter.export(sample_results, output_file)

        with open(output_file, "r") as f:
            content = f.read()

        assert "Critical Path Sequences" in content
        assert "task_001 -> task_002" in content

    def test_csv_contains_histogram(self, sample_results, tmp_path):
        """Test that CSV contains histogram data."""
        output_file = tmp_path / "results.csv"
        CSVExporter.export(sample_results, output_file)

        with open(output_file, "r") as f:
            content = f.read()

        assert "Histogram Data" in content
        assert "Bin Edge (hours)" in content
        assert "Count" in content
        assert "Cumulative %" in content

        # Verify we have histogram data rows
        lines = content.split("\n")
        histogram_section = False
        histogram_data_rows = 0

        for line in lines:
            if "Histogram Data" in line:
                histogram_section = True
            elif histogram_section and line and not line.startswith("Bin Edge"):
                # Count data rows (should have numeric values)
                parts = line.split(",")
                if len(parts) >= 3:
                    try:
                        float(parts[0])
                        histogram_data_rows += 1
                    except ValueError, IndexError:
                        pass

        # Should have at least some histogram bins
        assert histogram_data_rows > 0

    def test_csv_contains_constrained_diagnostics(self, sample_results, tmp_path):
        """Test that CSV includes constrained schedule diagnostics section."""
        output_file = tmp_path / "results.csv"
        CSVExporter.export(sample_results, output_file)

        with open(output_file, "r") as f:
            content = f.read()

        assert "Schedule Mode" in content
        assert "resource_constrained" in content
        assert "Constrained Schedule Diagnostics" in content
        assert "Average Resource Wait (hours)" in content
        assert "Effective Resource Utilization" in content
        assert "Calendar Delay Contribution (hours)" in content

    def test_csv_contains_sprint_planning_section(
        self, sample_results, sample_sprint_results, tmp_path
    ):
        """Test that CSV export includes sprint-planning data when provided."""
        output_file = tmp_path / "results.csv"
        CSVExporter.export(
            sample_results,
            output_file,
            sprint_results=sample_sprint_results,
        )

        with open(output_file, "r") as f:
            content = f.read()

        assert "Sprint Planning" in content
        assert "Sprint Count Confidence Intervals" in content
        assert "Historical Series Statistics" in content
        assert "completed_units" in content
        assert "Historical Ratio Summaries" in content
        assert "spillover_ratio" in content
        assert "Historical Correlations" in content
        assert "completed_units|spillover_units" in content
        assert "Carryover Diagnostics" in content
        assert "Burn-up Percentiles" in content


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
        assert "P25" in content
        assert "P99" in content

    def test_html_contains_thermometer(self, sample_results, tmp_path):
        """Test that HTML contains thermometer visualization."""
        output_file = tmp_path / "results.html"
        HTMLExporter.export(sample_results, output_file)

        with open(output_file, "r") as f:
            content = f.read()

        assert "thermometer" in content.lower()
        assert "Probability of Success" in content
        assert "thermometer-segment" in content

    def test_html_contains_critical_path_sequences(self, sample_results, tmp_path):
        """Test that HTML contains full critical path sequence reporting."""
        output_file = tmp_path / "results.html"
        HTMLExporter.export(sample_results, output_file)

        with open(output_file, "r") as f:
            content = f.read()

        assert "Most Frequent Critical Paths" in content
        assert "task_001 -&gt; task_002" in content or "task_001 -> task_002" in content

    def test_html_contains_sprint_planning_section(
        self, sample_results, sample_sprint_results, tmp_path
    ):
        """Test that HTML export includes sprint-planning data when provided."""
        output_file = tmp_path / "results.html"
        HTMLExporter.export(
            sample_results,
            output_file,
            sprint_results=sample_sprint_results,
        )

        with open(output_file, "r") as f:
            content = f.read()

        assert "Sprint Planning Summary" in content
        assert "Sprint Count Confidence Intervals" in content
        assert "matching_cadence" in content
        assert "completed_units" in content
        assert "Historical Ratio Summaries" in content
        assert "spillover_ratio" in content
        assert "Historical Correlations" in content
        assert "completed_units|spillover_units" in content
        assert "Burn-up Percentiles" in content
        assert "Observed Disruption Frequency" in content

    def test_json_critical_path_limit(self, sample_results, tmp_path):
        """Test JSON export respects critical path report limits."""
        output_file = tmp_path / "results.json"
        JSONExporter.export(sample_results, output_file, critical_path_limit=1)

        with open(output_file, "r") as f:
            data = json.load(f)

        assert len(data["critical_path_sequences"]) == 1

    def test_html_uses_active_config_for_tshirt_display(self, tmp_path):
        """Test that HTML uses the provided config for T-shirt size effort display."""
        results = SimulationResults(
            iterations=3,
            project_name="T-Shirt Project",
            durations=np.array([10.0, 11.0, 12.0]),
            task_durations={"task_001": np.array([4.0, 5.0, 6.0])},
            critical_path_frequency={"task_001": 3},
        )
        results.calculate_statistics()
        results.percentile(50)

        project = Project(
            project=ProjectMetadata(
                name="T-Shirt Project", start_date=date(2025, 1, 1)
            ),
            tasks=[
                Task(
                    id="task_001",
                    name="Sized Task",
                    estimate=TaskEstimate(t_shirt_size="M"),
                )
            ],
        )

        config = Config.model_validate(
            {"t_shirt_sizes": {"M": {"low": 10, "expected": 20, "high": 30}}}
        )

        output_file = tmp_path / "results.html"
        HTMLExporter.export(results, output_file, project=project, config=config)

        with open(output_file, "r") as f:
            content = f.read()

        assert "M (10.0, 20.0, 30.0)" in content

    def test_html_uses_default_config_for_tshirt_display_when_none_provided(
        self, tmp_path
    ):
        """Test that HTML falls back to Config defaults when no config is provided."""
        results = SimulationResults(
            iterations=3,
            project_name="T-Shirt Project",
            durations=np.array([10.0, 11.0, 12.0]),
            task_durations={"task_001": np.array([4.0, 5.0, 6.0])},
            critical_path_frequency={"task_001": 3},
        )
        results.calculate_statistics()
        results.percentile(50)

        project = Project(
            project=ProjectMetadata(
                name="T-Shirt Project", start_date=date(2025, 1, 1)
            ),
            tasks=[
                Task(
                    id="task_001",
                    name="Sized Task",
                    estimate=TaskEstimate(t_shirt_size="M"),
                )
            ],
        )

        output_file = tmp_path / "results.html"
        HTMLExporter.export(results, output_file, project=project)

        with open(output_file, "r") as f:
            content = f.read()

        assert "M (40.0, 60.0, 120.0)" in content

    def test_html_uses_active_config_for_story_point_display(self, tmp_path):
        """Test that HTML uses the provided config for Story Point effort display."""
        results = SimulationResults(
            iterations=3,
            project_name="Story Point Project",
            durations=np.array([10.0, 11.0, 12.0]),
            task_durations={"task_001": np.array([4.0, 5.0, 6.0])},
            critical_path_frequency={"task_001": 3},
        )
        results.calculate_statistics()
        results.percentile(50)

        project = Project(
            project=ProjectMetadata(
                name="Story Point Project", start_date=date(2025, 1, 1)
            ),
            tasks=[
                Task(
                    id="task_001",
                    name="Sized Task",
                    estimate=TaskEstimate(story_points=5),
                )
            ],
        )

        config = Config.model_validate(
            {"story_points": {5: {"low": 10, "expected": 20, "high": 30}}}
        )

        output_file = tmp_path / "story-points.html"
        HTMLExporter.export(results, output_file, project=project, config=config)

        with open(output_file, "r") as f:
            content = f.read()

        assert "SP 5 (10.0, 20.0, 30.0)" in content

    def test_html_uses_default_config_for_story_point_display_when_none_provided(
        self, tmp_path
    ):
        """Test that HTML falls back to default Story Point mappings."""
        results = SimulationResults(
            iterations=3,
            project_name="Story Point Project",
            durations=np.array([10.0, 11.0, 12.0]),
            task_durations={"task_001": np.array([4.0, 5.0, 6.0])},
            critical_path_frequency={"task_001": 3},
        )
        results.calculate_statistics()
        results.percentile(50)

        project = Project(
            project=ProjectMetadata(
                name="Story Point Project", start_date=date(2025, 1, 1)
            ),
            tasks=[
                Task(
                    id="task_001",
                    name="Sized Task",
                    estimate=TaskEstimate(story_points=5),
                )
            ],
        )

        output_file = tmp_path / "story-points-default.html"
        HTMLExporter.export(results, output_file, project=project)

        with open(output_file, "r") as f:
            content = f.read()

        assert "SP 5 (3.0, 5.0, 8.0)" in content

    def test_html_contains_max_parallel_tasks(self, sample_results, tmp_path):
        """Test that HTML contains Max Parallel Tasks in the overview."""
        output_file = tmp_path / "results.html"
        HTMLExporter.export(sample_results, output_file)

        with open(output_file, "r") as f:
            content = f.read()

        assert "Max Parallel Tasks" in content
        assert "Schedule Mode" in content

    def test_html_contains_constrained_diagnostics(self, sample_results, tmp_path):
        """Test that HTML contains constrained schedule diagnostics section."""
        output_file = tmp_path / "results.html"
        HTMLExporter.export(sample_results, output_file)

        with open(output_file, "r") as f:
            content = f.read()

        assert "Constrained Schedule Diagnostics" in content
        assert "Average Resource Wait (hours)" in content
        assert "Effective Resource Utilization" in content
        assert "Calendar Delay Contribution (hours)" in content

    def test_html_contains_staffing_section(self, sample_results, tmp_path):
        """Test that HTML contains staffing recommendations and table."""
        output_file = tmp_path / "results.html"
        HTMLExporter.export(sample_results, output_file)

        with open(output_file, "r") as f:
            content = f.read()

        assert "Staffing Analysis" in content
        assert "Recommended Team Size" in content
        assert "Eff. Capacity" in content
        assert "Efficiency" in content
        # Should contain at least one profile table
        assert "team" in content.lower()

    def test_html_staffing_shows_effort_basis(self, tmp_path):
        """Test that HTML staffing section shows effort basis and hours."""
        results = SimulationResults(
            iterations=5,
            project_name="Staffing Test",
            durations=np.array([100.0, 120.0, 150.0, 180.0, 200.0]),
            task_durations={
                "task_a": np.array([50.0, 60.0, 75.0, 90.0, 100.0]),
                "task_b": np.array([50.0, 60.0, 75.0, 90.0, 100.0]),
            },
            critical_path_frequency={"task_a": 5, "task_b": 3},
        )
        results.calculate_statistics()
        results.percentile(50)
        results.percentile(80)

        config = Config.model_validate({"staffing": {"effort_percentile": 80}})

        output_file = tmp_path / "staffing.html"
        HTMLExporter.export(results, output_file, config=config)

        with open(output_file, "r") as f:
            content = f.read()

        assert "80 effort percentile" in content
        assert "person-hours" in content
        assert "critical-path hours" in content
