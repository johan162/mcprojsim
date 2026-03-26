"""Integration tests."""

import json
import math
import random
import statistics
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from mcprojsim import SimulationEngine
from mcprojsim.cli import cli
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

    @pytest.mark.heavy
    def test_large_project_100_tasks_example_simulation(self):
        """Large 100-task example simulation should run successfully."""
        project_file = (
            Path(__file__).resolve().parents[1]
            / "examples"
            / "large_project_100_tasks.yaml"
        )

        parser = YAMLParser()
        project = parser.parse_file(project_file)

        assert len(project.tasks) == 100

        engine = SimulationEngine(
            iterations=100,
            random_seed=42,
            config=Config.get_default(),
            show_progress=False,
        )
        results = engine.run(project)

        assert results.iterations == 100
        assert results.mean > 0

    @pytest.fixture
    def sprint_nb_sickness_project_file(self, tmp_path):
        """Create a 60-task sprint project with external historical metrics."""
        history_source = (
            Path(__file__).resolve().parent / "sprint_historic_metrics.json"
        )
        history_target = tmp_path / "sprint_historic_metrics.json"
        with open(history_source, "r", encoding="utf-8") as source_file:
            history_payload = json.load(source_file)

        for sprint in history_payload.get("sprints", []):
            end_date = sprint.get("endDate")
            if isinstance(end_date, str) and "T" in end_date:
                sprint["endDate"] = end_date.split("T", maxsplit=1)[0]

        with open(history_target, "w", encoding="utf-8") as target_file:
            json.dump(history_payload, target_file, indent=2)

        rng = random.Random(20260324)
        story_point_sizes = [3, 5, 8, 12]
        task_count = 60
        independent_tasks = task_count // 2

        tasks = []
        for index in range(1, task_count + 1):
            task_id = f"task_{index:03d}"
            story_points = rng.choice(story_point_sizes)

            dependencies: list[str] = []
            if index > independent_tasks:
                candidate_ids = [f"task_{value:03d}" for value in range(1, index)]
                dependency_count = rng.randint(1, min(3, len(candidate_ids)))
                dependencies = sorted(rng.sample(candidate_ids, dependency_count))

            tasks.append(
                {
                    "id": task_id,
                    "name": f"Task {index:03d}",
                    "estimate": {
                        "distribution": "lognormal",
                        "low": round(story_points * 0.55, 2),
                        "expected": float(story_points),
                        "high": round(story_points * 1.9, 2),
                    },
                    "planning_story_points": story_points,
                    "dependencies": dependencies,
                }
            )

        data = {
            "project": {
                "name": "Sprint NB Sickness Integration Project",
                "start_date": "2026-01-05",
                "team_size": 8,
                "confidence_levels": [50, 80, 90],
            },
            "tasks": tasks,
            "sprint_planning": {
                "enabled": True,
                "sprint_length_weeks": 2,
                "capacity_mode": "story_points",
                "velocity_model": "neg_binomial",
                "planning_confidence_level": 0.8,
                "history": {
                    "format": "json",
                    "path": "sprint_historic_metrics.json",
                },
                "sickness": {
                    "enabled": True,
                    "team_size": 8,
                    "probability_per_person_per_week": 0.35,
                    "duration_log_mu": 1.1,
                    "duration_log_sigma": 0.9,
                },
            },
        }

        file_path = tmp_path / "sprint_nb_sickness_project.yaml"
        with open(file_path, "w") as f:
            yaml.dump(data, f, sort_keys=False)
        return file_path

    @pytest.mark.heavy
    def test_sprint_nb_sickness_statistically_increases_sprints(
        self,
        sprint_nb_sickness_project_file,
    ):
        """High sickness should statistically increase sprint count vs disabled sickness."""
        parser = YAMLParser()
        project = parser.parse_file(sprint_nb_sickness_project_file)

        assert len(project.tasks) == 60
        without_dependencies = sum(1 for task in project.tasks if not task.dependencies)
        with_dependencies = len(project.tasks) - without_dependencies
        assert without_dependencies == 30
        assert with_dependencies == 30
        assert project.sprint_planning is not None
        assert project.sprint_planning.velocity_model.value == "neg_binomial"

        sickness_enabled_means: list[float] = []
        sickness_disabled_means: list[float] = []

        for run_index in range(10):
            seed = 9000 + run_index

            with_sickness_engine = SprintSimulationEngine(
                iterations=250, random_seed=seed
            )
            with_sickness_results = with_sickness_engine.run(project)
            sickness_enabled_means.append(float(with_sickness_results.mean))

            without_sickness_project = project.model_copy(deep=True)
            assert without_sickness_project.sprint_planning is not None
            without_sickness_project.sprint_planning.sickness.enabled = False

            without_sickness_engine = SprintSimulationEngine(
                iterations=250,
                random_seed=seed,
            )
            without_sickness_results = without_sickness_engine.run(
                without_sickness_project
            )
            sickness_disabled_means.append(float(without_sickness_results.mean))

        deltas = [
            with_sickness - without_sickness
            for with_sickness, without_sickness in zip(
                sickness_enabled_means,
                sickness_disabled_means,
            )
        ]

        assert statistics.mean(sickness_enabled_means) > statistics.mean(
            sickness_disabled_means
        )
        assert sum(delta > 0 for delta in deltas) >= 8

    @pytest.mark.heavy
    def test_cli_no_sickness_flag_reduces_sprint_mean(
        self,
        sprint_nb_sickness_project_file,
        tmp_path,
    ):
        """CLI --no-sickness should reduce sprint-planning mean in this heavy scenario."""
        runner = CliRunner()
        with_sickness_output = tmp_path / "with_sickness.json"
        without_sickness_output = tmp_path / "without_sickness.json"

        base_args = [
            "simulate",
            str(sprint_nb_sickness_project_file),
            "--iterations",
            "1200",
            "--seed",
            "24680",
            "--output-format",
            "json",
            "--quiet",
        ]

        with_sickness_result = runner.invoke(
            cli,
            [
                *base_args,
                "--output",
                str(with_sickness_output),
            ],
        )
        assert with_sickness_result.exit_code == 0, with_sickness_result.output

        without_sickness_result = runner.invoke(
            cli,
            [
                *base_args,
                "--no-sickness",
                "--output",
                str(without_sickness_output),
            ],
        )
        assert without_sickness_result.exit_code == 0, without_sickness_result.output

        with open(with_sickness_output, "r", encoding="utf-8") as with_file:
            with_sickness_data = json.load(with_file)
        with open(without_sickness_output, "r", encoding="utf-8") as without_file:
            without_sickness_data = json.load(without_file)

        with_sickness_sprint = with_sickness_data["sprint_planning"]
        without_sickness_sprint = without_sickness_data["sprint_planning"]

        with_sickness_mean = with_sickness_sprint["statistics"]["mean"]
        without_sickness_mean = without_sickness_sprint["statistics"]["mean"]

        assert with_sickness_mean > without_sickness_mean
        assert (
            with_sickness_sprint["historical_diagnostics"]["sickness"]["enabled"]
            is True
        )
        assert (
            without_sickness_sprint["historical_diagnostics"]["sickness"]["enabled"]
            is False
        )


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
        is_valid, _ = parser.validate_file(file_path)
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

        task_xs_durations = results.task_durations["task_xs"]
        task_m_durations = results.task_durations["task_m"]
        task_l_durations = results.task_durations["task_l"]
        xs_config = config.resolve_t_shirt_size("XS")
        m_config = config.resolve_t_shirt_size("M")
        l_config = config.resolve_t_shirt_size("L")

        # XS should be smallest on average
        assert task_xs_durations.mean() < task_m_durations.mean()
        assert task_m_durations.mean() < task_l_durations.mean()

        # Check reasonable ranges
        assert xs_config.low <= task_xs_durations.min() <= xs_config.high
        assert m_config.low <= task_m_durations.min() <= m_config.high
        assert l_config.low <= task_l_durations.min() <= l_config.high

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

    def test_mixed_bare_and_qualified_tshirt_values(self, tmp_path):
        """A project may mix bare and qualified T-shirt values."""
        data = {
            "project": {"name": "Mixed T-Shirt", "start_date": "2025-01-01"},
            "tasks": [
                {
                    "id": "task_story",
                    "name": "Story Task",
                    "estimate": {"t_shirt_size": "M"},
                    "dependencies": [],
                },
                {
                    "id": "task_epic",
                    "name": "Epic Task",
                    "estimate": {"t_shirt_size": "epic.M"},
                    "dependencies": [],
                },
            ],
        }

        file_path = tmp_path / "mixed_tshirt.yaml"
        with open(file_path, "w") as f:
            yaml.dump(data, f)

        parser = YAMLParser()
        project = parser.parse_file(file_path)
        config = Config.get_default()
        config.t_shirt_size_default_category = "story"
        results = SimulationEngine(
            iterations=200,
            random_seed=42,
            config=config,
            show_progress=False,
        ).run(project)

        assert results.mean > 0
        assert (
            results.task_durations["task_epic"].mean()
            > results.task_durations["task_story"].mean()
        )

    def test_unknown_tshirt_category_reports_valid_categories(self, tmp_path):
        """Unknown category errors should include the available categories."""
        data = {
            "project": {"name": "Bad Category", "start_date": "2025-01-01"},
            "tasks": [
                {
                    "id": "task_001",
                    "name": "Task",
                    "estimate": {"t_shirt_size": "foo.M"},
                    "dependencies": [],
                }
            ],
        }

        file_path = tmp_path / "bad_category.yaml"
        with open(file_path, "w") as f:
            yaml.dump(data, f)

        parser = YAMLParser()
        project = parser.parse_file(file_path)

        with pytest.raises(ValueError, match="Valid categories"):
            SimulationEngine(
                iterations=10,
                random_seed=42,
                config=Config.get_default(),
                show_progress=False,
            ).run(project)

    def test_unknown_tshirt_size_reports_valid_sizes(self, tmp_path):
        """Unknown size errors should list valid sizes for that category."""
        data = {
            "project": {"name": "Bad Size", "start_date": "2025-01-01"},
            "tasks": [
                {
                    "id": "task_001",
                    "name": "Task",
                    "estimate": {"t_shirt_size": "epic.HUGE"},
                    "dependencies": [],
                }
            ],
        }

        file_path = tmp_path / "bad_size.yaml"
        with open(file_path, "w") as f:
            yaml.dump(data, f)

        parser = YAMLParser()
        project = parser.parse_file(file_path)

        with pytest.raises(ValueError, match="Valid sizes for category 'epic'"):
            SimulationEngine(
                iterations=10,
                random_seed=42,
                config=Config.get_default(),
                show_progress=False,
            ).run(project)

    def test_story_category_finishes_faster_than_epic_for_large_tshirt_project(
        self, tmp_path
    ):
        """Story-category symbolic sizing should complete faster than epic sizing."""
        size_cycle = ["XS", "S", "M", "L", "XL", "XXL"]
        tasks: list[dict[str, object]] = []

        for index in range(30):
            task_id = f"task_{index + 1:03d}"
            size = size_cycle[index % len(size_cycle)]

            if index < 10:
                dependencies: list[str] = []
            else:
                dependency_count = ((index - 10) % 3) + 1
                dependency_start = max(0, index - dependency_count - 2)
                dependencies = [
                    f"task_{dep_index + 1:03d}"
                    for dep_index in range(
                        dependency_start, dependency_start + dependency_count
                    )
                ]

            tasks.append(
                {
                    "id": task_id,
                    "name": f"Task {index + 1}",
                    "estimate": {"t_shirt_size": size},
                    "dependencies": dependencies,
                }
            )

        project_data = {
            "project": {
                "name": "Large T-Shirt Category Comparison",
                "start_date": "2026-01-05",
                "confidence_levels": [50, 80, 90],
            },
            "tasks": tasks,
        }

        project_file = tmp_path / "large_tshirt_category_project.yaml"
        with open(project_file, "w") as f:
            yaml.dump(project_data, f, sort_keys=False)

        parser = YAMLParser()
        project = parser.parse_file(project_file)

        independent_tasks = [task for task in project.tasks if not task.dependencies]
        dependent_tasks = [task for task in project.tasks if task.dependencies]

        assert len(project.tasks) == 30
        assert len(independent_tasks) == 10
        assert len(dependent_tasks) == 20
        assert all(1 <= len(task.dependencies) <= 3 for task in dependent_tasks)

        story_config = Config.get_default()
        story_config.t_shirt_size_default_category = "story"

        epic_config = Config.get_default()
        epic_config.t_shirt_size_default_category = "epic"

        story_results = SimulationEngine(
            iterations=400,
            random_seed=4242,
            config=story_config,
            show_progress=False,
        ).run(project)
        epic_results = SimulationEngine(
            iterations=400,
            random_seed=4242,
            config=epic_config,
            show_progress=False,
        ).run(project)

        story_output = tmp_path / "story_category_results.json"
        epic_output = tmp_path / "epic_category_results.json"
        JSONExporter.export(story_results, story_output, config=story_config)
        JSONExporter.export(epic_results, epic_output, config=epic_config)

        assert story_output.exists()
        assert epic_output.exists()

        with open(story_output, "r") as f:
            story_data = json.load(f)
        with open(epic_output, "r") as f:
            epic_data = json.load(f)

        assert story_data["statistics"]["mean_hours"] == pytest.approx(
            story_results.mean
        )
        assert epic_data["statistics"]["mean_hours"] == pytest.approx(
            epic_results.mean
        )
        assert story_results.mean < epic_results.mean

        story_means: list[float] = []
        epic_means: list[float] = []
        paired_deltas: list[float] = []

        for run_index in range(10):
            seed = 7000 + run_index
            story_run = SimulationEngine(
                iterations=250,
                random_seed=seed,
                config=story_config,
                show_progress=False,
            ).run(project)
            epic_run = SimulationEngine(
                iterations=250,
                random_seed=seed,
                config=epic_config,
                show_progress=False,
            ).run(project)

            story_means.append(float(story_run.mean))
            epic_means.append(float(epic_run.mean))
            paired_deltas.append(float(epic_run.mean - story_run.mean))

        mean_delta = statistics.mean(paired_deltas)
        stdev_delta = statistics.stdev(paired_deltas)
        lower_bound_95 = mean_delta - 1.96 * (stdev_delta / math.sqrt(len(paired_deltas)))

        assert statistics.mean(story_means) < statistics.mean(epic_means)
        assert all(delta > 0 for delta in paired_deltas)
        assert lower_bound_95 > 0
