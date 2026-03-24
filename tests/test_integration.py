"""Integration tests."""

import pytest
import yaml

from mcprojsim import SimulationEngine
from mcprojsim.parsers import YAMLParser
from mcprojsim.exporters import JSONExporter, CSVExporter, HTMLExporter
from mcprojsim.config import Config
from mcprojsim.planning.sprint_engine import SprintSimulationEngine


class TestEndToEnd:
    """End-to-end integration tests."""

    @pytest.fixture
    def project_file(self, tmp_path):
        """Create a test project file."""
        data = {
            "project": {
                "name": "Integration Test Project",
                "start_date": "2025-01-01",
                "confidence_levels": [50, 80, 90],
            },
            "tasks": [
                {
                    "id": "task_001",
                    "name": "Design",
                    "estimate": {"low": 2, "expected": 3, "high": 5},
                    "dependencies": [],
                },
                {
                    "id": "task_002",
                    "name": "Implementation",
                    "estimate": {"low": 5, "expected": 8, "high": 12},
                    "dependencies": ["task_001"],
                    "uncertainty_factors": {
                        "team_experience": "medium",
                        "technical_complexity": "high",
                    },
                },
                {
                    "id": "task_003",
                    "name": "Testing",
                    "estimate": {"low": 2, "expected": 4, "high": 6},
                    "dependencies": ["task_002"],
                    "risks": [
                        {
                            "id": "test_risk",
                            "name": "Testing delays",
                            "probability": 0.3,
                            "impact": 2,
                        }
                    ],
                },
            ],
            "project_risks": [
                {
                    "id": "proj_risk",
                    "name": "Resource unavailable",
                    "probability": 0.2,
                    "impact": {"type": "absolute", "value": 5},
                }
            ],
        }

        file_path = tmp_path / "project.yaml"
        with open(file_path, "w") as f:
            yaml.dump(data, f)
        return file_path

    @pytest.fixture
    def sprint_project_file(self, tmp_path):
        """Create a sprint-planning test project file."""
        data = {
            "project": {
                "name": "Sprint Integration Test Project",
                "start_date": "2025-01-06",
                "confidence_levels": [50, 80, 90],
            },
            "tasks": [
                {
                    "id": "task_001",
                    "name": "Design",
                    "estimate": {"low": 2, "expected": 3, "high": 5},
                    "planning_story_points": 3,
                    "priority": 1,
                },
                {
                    "id": "task_002",
                    "name": "Implementation",
                    "estimate": {"low": 5, "expected": 8, "high": 12},
                    "dependencies": ["task_001"],
                    "planning_story_points": 5,
                    "priority": 2,
                },
                {
                    "id": "task_003",
                    "name": "Testing",
                    "estimate": {"low": 2, "expected": 4, "high": 6},
                    "dependencies": ["task_002"],
                    "planning_story_points": 2,
                    "priority": 3,
                },
            ],
            "sprint_planning": {
                "enabled": True,
                "sprint_length_weeks": 2,
                "capacity_mode": "story_points",
                "planning_confidence_level": 0.8,
                "history": [
                    {
                        "sprint_id": "S1",
                        "completed_story_points": 6,
                        "spillover_story_points": 1,
                        "added_story_points": 0,
                        "removed_story_points": 0,
                        "holiday_factor": 1.0,
                    },
                    {
                        "sprint_id": "S2",
                        "completed_story_points": 5,
                        "spillover_story_points": 0,
                        "added_story_points": 1,
                        "removed_story_points": 0,
                        "holiday_factor": 1.0,
                    },
                    {
                        "sprint_id": "S3",
                        "completed_story_points": 7,
                        "spillover_story_points": 1,
                        "added_story_points": 0,
                        "removed_story_points": 1,
                        "holiday_factor": 1.0,
                    },
                ],
            },
        }

        file_path = tmp_path / "sprint_project.yaml"
        with open(file_path, "w") as f:
            yaml.dump(data, f)
        return file_path

    def test_full_workflow(self, project_file, tmp_path):
        """Test complete workflow from file to results."""
        # Parse project
        parser = YAMLParser()
        project = parser.parse_file(project_file)

        assert project.project.name == "Integration Test Project"
        assert len(project.tasks) == 3
        assert len(project.project_risks) == 1

        # Run simulation
        config = Config.get_default()
        engine = SimulationEngine(
            iterations=100,
            random_seed=42,
            config=config,
            show_progress=False,
        )
        results = engine.run(project)

        assert results.iterations == 100
        assert results.mean > 0
        assert results.median > 0

        # Export results
        json_file = tmp_path / "results.json"
        csv_file = tmp_path / "results.csv"
        html_file = tmp_path / "results.html"

        JSONExporter.export(results, json_file)
        CSVExporter.export(results, csv_file)
        HTMLExporter.export(results, html_file)

        assert json_file.exists()
        assert csv_file.exists()
        assert html_file.exists()

    def test_simulation_with_dependencies(self, project_file):
        """Test simulation respects dependencies."""
        parser = YAMLParser()
        project = parser.parse_file(project_file)

        engine = SimulationEngine(iterations=10, random_seed=42, show_progress=False)
        results = engine.run(project)

        # Task 001 should be on critical path
        critical_path = results.get_critical_path()
        assert "task_001" in critical_path
        assert critical_path["task_001"] > 0

    def test_simulation_with_risks(self, project_file):
        """Test simulation with risks."""
        parser = YAMLParser()
        project = parser.parse_file(project_file)

        # Run multiple times to check variability
        engine1 = SimulationEngine(iterations=100, random_seed=42, show_progress=False)
        results1 = engine1.run(project)

        engine2 = SimulationEngine(iterations=100, random_seed=43, show_progress=False)
        results2 = engine2.run(project)

        # Results should be different with different seeds
        assert results1.mean != results2.mean

    def test_validation_before_simulation(self, tmp_path):
        """Test validation catches errors before simulation."""
        # Create invalid project
        invalid_data = {
            "project": {"name": "Invalid", "start_date": "2025-01-01"},
            "tasks": [
                {
                    "id": "task_001",
                    "name": "Task",
                    "estimate": {"low": 10, "expected": 5, "high": 15},  # Invalid
                }
            ],
        }

        file_path = tmp_path / "invalid.yaml"
        with open(file_path, "w") as f:
            yaml.dump(invalid_data, f)

        parser = YAMLParser()
        with pytest.raises(ValueError):
            parser.parse_file(file_path)

    def test_sprint_planning_workflow(self, sprint_project_file, tmp_path):
        """Test sprint-planning workflow from file to sprint results and exports."""
        parser = YAMLParser()
        project = parser.parse_file(sprint_project_file)

        sprint_engine = SprintSimulationEngine(iterations=50, random_seed=42)
        sprint_results = sprint_engine.run(project)

        assert sprint_results.project_name == "Sprint Integration Test Project"
        assert sprint_results.iterations == 50
        assert len(sprint_results.sprint_counts) == 50
        assert sprint_results.mean > 0
        assert sprint_results.percentiles[80] > 0
        assert sprint_results.date_percentiles[80] is not None
        assert sprint_results.historical_diagnostics["observation_count"] == 3

        duration_engine = SimulationEngine(
            iterations=50,
            random_seed=42,
            config=Config.get_default(),
            show_progress=False,
        )
        duration_results = duration_engine.run(project)

        json_file = tmp_path / "sprint_results.json"
        csv_file = tmp_path / "sprint_results.csv"
        html_file = tmp_path / "sprint_results.html"

        JSONExporter.export(duration_results, json_file, sprint_results=sprint_results)
        CSVExporter.export(duration_results, csv_file, sprint_results=sprint_results)
        HTMLExporter.export(duration_results, html_file, sprint_results=sprint_results)

        assert json_file.exists()
        assert csv_file.exists()
        assert html_file.exists()

        assert '"sprint_planning"' in json_file.read_text()
        assert "Sprint Planning" in csv_file.read_text()
        assert "Sprint Planning Summary" in html_file.read_text()


class TestCLIIntegration:
    """Integration tests for CLI-like workflows."""

    def test_parse_and_simulate(self, tmp_path):
        """Test parsing and simulating a project."""
        # Create project
        data = {
            "project": {"name": "CLI Test", "start_date": "2025-01-01"},
            "tasks": [
                {
                    "id": "task_001",
                    "name": "Task",
                    "estimate": {"low": 1, "expected": 2, "high": 3},
                }
            ],
        }

        file_path = tmp_path / "project.yaml"
        with open(file_path, "w") as f:
            yaml.dump(data, f)

        # Parse
        parser = YAMLParser()
        is_valid, error = parser.validate_file(file_path)
        assert is_valid

        # Load and simulate
        project = parser.parse_file(file_path)
        engine = SimulationEngine(iterations=50, show_progress=False)
        results = engine.run(project)

        assert results.project_name == "CLI Test"
        assert len(results.durations) == 50

    def test_tshirt_sizing_simulation(self, tmp_path):
        """Test simulation with T-shirt size estimates."""
        # Create project with T-shirt sizes
        data = {
            "project": {
                "name": "T-Shirt Test",
                "start_date": "2025-01-01",
                "confidence_levels": [50, 90],
            },
            "tasks": [
                {
                    "id": "task_xs",
                    "name": "Extra Small Task",
                    "estimate": {"t_shirt_size": "XS"},
                    "dependencies": [],
                },
                {
                    "id": "task_m",
                    "name": "Medium Task",
                    "estimate": {"t_shirt_size": "M"},
                    "dependencies": ["task_xs"],
                },
                {
                    "id": "task_l",
                    "name": "Large Task",
                    "estimate": {"t_shirt_size": "L"},
                    "dependencies": ["task_m"],
                },
            ],
        }

        file_path = tmp_path / "tshirt_project.yaml"
        with open(file_path, "w") as f:
            yaml.dump(data, f)

        # Parse and validate
        parser = YAMLParser()
        is_valid, error = parser.validate_file(file_path)
        assert is_valid, f"Validation failed: {error}"

        # Load and simulate
        project = parser.parse_file(file_path)
        config = Config.get_default()
        engine = SimulationEngine(
            iterations=100, random_seed=42, config=config, show_progress=False
        )
        results = engine.run(project)

        # Verify results
        assert results.project_name == "T-Shirt Test"
        assert len(results.durations) == 100
        assert results.mean > 0
        assert results.std_dev > 0

        # Check that task durations are reasonable for their sizes
        # XS: 3-15 hours, M: 40-120 hours, L: 160-500 hours
        task_xs_durations = results.task_durations["task_xs"]
        task_m_durations = results.task_durations["task_m"]
        task_l_durations = results.task_durations["task_l"]

        # XS should be smallest on average
        assert task_xs_durations.mean() < task_m_durations.mean()
        assert task_m_durations.mean() < task_l_durations.mean()

        # Check reasonable ranges
        assert 3.0 <= task_xs_durations.min() <= 15.0
        assert 40.0 <= task_m_durations.min() <= 120.0
        assert 160.0 <= task_l_durations.min() <= 500.0

    def test_story_point_sizing_simulation(self, tmp_path):
        """Test simulation with Story Point estimates."""
        data = {
            "project": {
                "name": "Story Point Test",
                "start_date": "2025-01-01",
                "confidence_levels": [50, 90],
            },
            "tasks": [
                {
                    "id": "task_sp1",
                    "name": "Small Story",
                    "estimate": {"story_points": 1},
                    "dependencies": [],
                },
                {
                    "id": "task_sp5",
                    "name": "Medium Story",
                    "estimate": {"story_points": 5},
                    "dependencies": ["task_sp1"],
                },
                {
                    "id": "task_sp13",
                    "name": "Large Story",
                    "estimate": {"story_points": 13},
                    "dependencies": ["task_sp5"],
                },
            ],
        }

        file_path = tmp_path / "story_points_project.yaml"
        with open(file_path, "w") as f:
            yaml.dump(data, f)

        parser = YAMLParser()
        is_valid, error = parser.validate_file(file_path)
        assert is_valid, f"Validation failed: {error}"

        project = parser.parse_file(file_path)
        config = Config.get_default()
        engine = SimulationEngine(
            iterations=100, random_seed=42, config=config, show_progress=False
        )
        results = engine.run(project)

        assert results.project_name == "Story Point Test"
        assert len(results.durations) == 100
        assert results.mean > 0
        assert results.std_dev > 0

        task_sp1_durations = results.task_durations["task_sp1"]
        task_sp5_durations = results.task_durations["task_sp5"]
        task_sp13_durations = results.task_durations["task_sp13"]

        assert task_sp1_durations.mean() < task_sp5_durations.mean()
        assert task_sp5_durations.mean() < task_sp13_durations.mean()

        # Durations are now in hours (story points default to days, converted at 8 hours/day)
        assert 0.5 * 8 <= task_sp1_durations.min() <= 3.0 * 8
        assert 3.0 * 8 <= task_sp5_durations.min() <= 8.0 * 8
        assert 8.0 * 8 <= task_sp13_durations.min() <= 21.0 * 8
