"""Tests for parsers."""

from pathlib import Path
import shutil

import pytest
import yaml

from mcprojsim.parsers import YAMLParser, TOMLParser
from mcprojsim.models.project import Project


@pytest.fixture
def sample_project_dict():
    """Sample project data."""
    return {
        "project": {
            "name": "Test Project",
            "start_date": "2025-01-01",
        },
        "tasks": [
            {
                "id": "task_001",
                "name": "Task 1",
                "estimate": {
                    "low": 1,
                    "expected": 2,
                    "high": 5,
                },
            }
        ],
    }


@pytest.fixture
def sample_yaml_file(tmp_path, sample_project_dict):
    """Create a temporary YAML file."""
    file_path = tmp_path / "test_project.yaml"
    with open(file_path, "w") as f:
        yaml.dump(sample_project_dict, f)
    return file_path


class TestYAMLParser:
    """Tests for YAML parser."""

    def test_parse_dict(self, sample_project_dict):
        """Test parsing from dictionary."""
        parser = YAMLParser()
        project = parser.parse_dict(sample_project_dict)
        assert isinstance(project, Project)
        assert project.project.name == "Test Project"
        assert len(project.tasks) == 1

    def test_parse_file(self, sample_yaml_file):
        """Test parsing from file."""
        parser = YAMLParser()
        project = parser.parse_file(sample_yaml_file)
        assert isinstance(project, Project)
        assert project.project.name == "Test Project"

    def test_parse_yaml_project_t_shirt_default_category(self):
        """YAML project files should accept a project-level T-shirt default category."""
        parser = YAMLParser()
        project = parser.parse_dict(
            {
                "project": {
                    "name": "Test Project",
                    "start_date": "2025-01-01",
                    "t_shirt_size_default_category": "bug",
                },
                "tasks": [
                    {
                        "id": "task_001",
                        "name": "Task 1",
                        "estimate": {"t_shirt_size": "M"},
                    }
                ],
            }
        )

        assert project.project.t_shirt_size_default_category == "bug"

    def test_parse_examples_external_json_project_file(self, tmp_path):
        """Example project with external JSON history should parse successfully."""
        examples_dir = Path(__file__).resolve().parents[1] / "examples"

        project_fixture = examples_dir / "sprint_planning_external_json.yaml"
        history_fixture = examples_dir / "sprint_planning_history.json"

        project_file = tmp_path / "sprint_planning_external_json.yaml"
        history_file = tmp_path / "sprint_planning_history.json"

        shutil.copyfile(project_fixture, project_file)
        shutil.copyfile(history_fixture, history_file)

        parser = YAMLParser()
        project = parser.parse_file(project_file)

        assert project.sprint_planning is not None
        assert len(project.sprint_planning.history) == 3
        assert project.sprint_planning.history[0].sprint_id == "2026:Q1 Sprint 1"

    def test_parse_file_not_found(self):
        """Test parsing non-existent file."""
        parser = YAMLParser()
        with pytest.raises(FileNotFoundError):
            parser.parse_file("nonexistent.yaml")

    def test_parse_invalid_data(self):
        """Test parsing invalid data."""
        parser = YAMLParser()
        with pytest.raises(ValueError, match="Invalid project data"):
            parser.parse_dict({"invalid": "data"})

    def test_parse_resources_with_defaults(self):
        """Test parsing resource schema with defaults and generated names."""
        parser = YAMLParser()
        project = parser.parse_dict(
            {
                "project": {
                    "name": "Res Parser Project",
                    "start_date": "2025-01-01",
                    "team_size": 3,
                },
                "tasks": [
                    {
                        "id": "task_001",
                        "name": "Task 1",
                        "estimate": {
                            "low": 1,
                            "expected": 2,
                            "high": 5,
                        },
                        "resources": ["alice"],
                    }
                ],
                "resources": [
                    {"name": "alice", "experience_level": 3},
                    {"experience_level": 1},
                ],
            }
        )

        assert project.project.team_size == 3
        assert project.resources[0].name == "alice"
        assert project.resources[1].name == "resource_001"
        assert project.resources[1].productivity_level == 1.0

    def test_validate_file_valid(self, sample_yaml_file):
        """Test validating valid file."""
        parser = YAMLParser()
        is_valid, error = parser.validate_file(sample_yaml_file)
        assert is_valid
        assert error == ""

    def test_validate_file_invalid(self, tmp_path):
        """Test validating invalid file."""
        file_path = tmp_path / "invalid.yaml"
        with open(file_path, "w") as f:
            yaml.dump({"invalid": "data"}, f)

        parser = YAMLParser()
        is_valid, error = parser.validate_file(file_path)
        assert not is_valid
        assert len(error) > 0

    def test_validate_file_reports_duplicate_sprint_id_with_line_number(self, tmp_path):
        """Sprint history duplicate identifiers should report a source-aware error."""
        file_path = tmp_path / "duplicate_sprint_id.yaml"
        file_path.write_text("""
project:
    name: Example
    start_date: 2025-01-01
sprint_planning:
    enabled: true
    sprint_length_weeks: 2
    capacity_mode: story_points
    history:
        - sprint_id: SPR-001
          completed_story_points: 10
        - sprint_id: SPR-001
          completed_story_points: 8
tasks:
    - id: task_001
      name: Task 1
      estimate:
          low: 1
          expected: 2
          high: 5
      planning_story_points: 3
""".strip())

        parser = YAMLParser()
        is_valid, error = parser.validate_file(file_path)

        assert not is_valid
        assert "line 11" in error
        assert "Duplicate sprint_id 'SPR-001'" in error

    def test_validate_file_reports_yaml_line_numbers_and_field_suggestion(
        self, tmp_path
    ):
        """Validation errors should include YAML line numbers and likely field names."""
        file_path = tmp_path / "invalid_field.yaml"
        file_path.write_text("""
project:
  name: Example
  start_date: 2025-01-01
tasks:
  - id: task_001
    name: Example task
    estimate:
      low: 1
      mostlikely: 2
      high: 3
""".strip())

        parser = YAMLParser()
        is_valid, error = parser.validate_file(file_path)

        assert not is_valid
        assert "line 9" in error
        assert "mostlikely" in error

        def test_parse_file_reports_dependency_suggestion(self, tmp_path):
            """Dependency validation should point to the dependency line with a suggestion."""
            file_path = tmp_path / "invalid_dependency.yaml"
            file_path.write_text("""
project:
    name: Example
    start_date: 2025-01-01
tasks:
    - id: task_001
        name: First task
        estimate:
            low: 1
            expected: 2
            high: 3
    - id: task_002
        name: Second task
        estimate:
            low: 1
            expected: 2
            high: 3
        dependencies:
            - task_001_typo
""".strip())

            parser = YAMLParser()

            with pytest.raises(ValueError, match="task_001") as exc_info:
                parser.parse_file(file_path)

            assert "line 18" in str(exc_info.value)
            assert "task_001_typo" in str(exc_info.value)
            assert "task_001" in str(exc_info.value)

        def test_parse_file_loads_external_json_sprint_history(self, tmp_path):
            """YAML parser should load external JSON sprint history before validation."""
            fixture_file = (
                Path(__file__).resolve().parents[1]
                / "examples"
                / "sprint_planning_history.json"
            )
            history_file = tmp_path / "sprint_planning_history.json"
            shutil.copyfile(fixture_file, history_file)

            project_file = tmp_path / "project.yaml"
            project_file.write_text("""
project:
    name: Example
    start_date: 2025-01-01
sprint_planning:
    enabled: true
    sprint_length_weeks: 2
    capacity_mode: story_points
    history:
        format: json
        path: sprint_planning_history.json
tasks:
    - id: task_001
        name: Task 1
        planning_story_points: 3
        estimate:
            low: 1
            expected: 2
            high: 5
""".strip())

            parser = YAMLParser()
            project = parser.parse_file(project_file)

            assert project.sprint_planning is not None
            assert len(project.sprint_planning.history) == 3
            assert project.sprint_planning.history[0].sprint_id == "2026:Q1 Sprint 1"
            assert project.sprint_planning.history[0].completed_story_points == 78
            assert project.sprint_planning.history[1].added_story_points == 0
            assert project.sprint_planning.history[1].removed_story_points == 0
            assert project.sprint_planning.history[2].spillover_story_points == 4

    def test_parse_file_reports_missing_external_sprint_history(self, tmp_path):
        """YAML parser should fail clearly when external sprint history is missing."""
        project_file = tmp_path / "project.yaml"
        project_file.write_text("""
project:
  name: Example
  start_date: 2025-01-01
sprint_planning:
  enabled: true
  sprint_length_weeks: 2
  capacity_mode: story_points
  history:
    format: json
    path: missing_history.json
tasks:
  - id: task_001
    name: Task 1
    planning_story_points: 3
    estimate:
      low: 1
      expected: 2
      high: 5
""".strip())

        parser = YAMLParser()
        is_valid, error = parser.validate_file(project_file)

        assert not is_valid
        assert "external history file not found" in error


class TestTOMLParser:
    """Tests for TOML parser."""

    def test_parse_dict(self, sample_project_dict):
        """Test parsing from dictionary."""
        parser = TOMLParser()
        project = parser.parse_dict(sample_project_dict)
        assert isinstance(project, Project)
        assert project.project.name == "Test Project"

    def test_parse_toml_project_t_shirt_default_category(self, tmp_path):
        """TOML project files should accept a project-level T-shirt default category."""
        file_path = tmp_path / "project.toml"
        file_path.write_text(
            """
[project]
name = "Test Project"
start_date = "2025-01-01"
t_shirt_size_default_category = "bug"

[[tasks]]
id = "task_001"
name = "Task 1"

[tasks.estimate]
t_shirt_size = "M"
""".strip()
        )

        parser = TOMLParser()
        project = parser.parse_file(file_path)

        assert project.project.t_shirt_size_default_category == "bug"

    def test_parse_file_not_found(self):
        """Test parsing non-existent file."""
        parser = TOMLParser()
        with pytest.raises(FileNotFoundError):
            parser.parse_file("nonexistent.toml")

    def test_validate_file_reports_toml_line_numbers_and_field_suggestion(
        self, tmp_path
    ):
        """Validation errors should include TOML line numbers and likely field names."""
        file_path = tmp_path / "invalid.toml"
        file_path.write_text("""
[project]
name = "Example"
start_date = "2025-01-01"

[[tasks]]
id = "task_001"
name = "Task"

[tasks.estimate]
low = 1
mostlikely = 2
high = 3
""".strip())

        parser = TOMLParser()
        is_valid, error = parser.validate_file(file_path)

        assert not is_valid
        assert "line 11" in error
        assert "mostlikely" in error
        assert "Unknown field" in error

    def test_parse_file_reports_toml_syntax_line_numbers(self, tmp_path):
        """TOML syntax errors should include line and column information."""
        file_path = tmp_path / "syntax_error.toml"
        file_path.write_text("""
[project]
name = "Example"
start_date = "2025-01-01"

[[tasks]]
id = "task_001"
name = "Task"
[tasks.estimate
low = 1
expected = 2
high = 3
""".strip())

        parser = TOMLParser()

        with pytest.raises(ValueError, match="line 8") as exc_info:
            parser.parse_file(file_path)

        assert "column" in str(exc_info.value)

    def test_validate_file_rejects_mixed_sprint_history_units(self, tmp_path):
        """Sprint history rows should not mix story-point and task unit families."""
        file_path = tmp_path / "mixed_sprint_units.toml"
        file_path.write_text("""
[project]
name = "Example"
start_date = "2025-01-01"

[sprint_planning]
enabled = true
sprint_length_weeks = 2
capacity_mode = "story_points"

[[sprint_planning.history]]
sprint_id = "SPR-001"
completed_story_points = 10
spillover_tasks = 1

[[sprint_planning.history]]
sprint_id = "SPR-002"
completed_story_points = 8

[[tasks]]
id = "task_001"
name = "Task"
planning_story_points = 3

[tasks.estimate]
low = 1
expected = 2
high = 3
""".strip())

        parser = TOMLParser()
        is_valid, error = parser.validate_file(file_path)

        assert not is_valid
        assert (
            "completed_story_points" in error or "must not include task-based" in error
        )

    def test_parse_file_loads_external_csv_sprint_history(self, tmp_path):
        """TOML parser should load external CSV sprint history before validation."""
        history_file = tmp_path / "sprint_history.csv"
        history_file.write_text("""
sprintUniqueID,committed_StoryPoints,completed_StoryPoints,spilledOver_StoryPoints
SPR-001,8,4,1
SPR-002,9,5,0
""".strip())

        project_file = tmp_path / "project.toml"
        project_file.write_text("""
[project]
name = "Example"
start_date = "2025-01-01"

[sprint_planning]
enabled = true
sprint_length_weeks = 2
capacity_mode = "story_points"

[sprint_planning.history]
format = "csv"
path = "sprint_history.csv"

[[tasks]]
id = "task_001"
name = "Task"
planning_story_points = 3

[tasks.estimate]
low = 1
expected = 2
high = 5
""".strip())

        parser = TOMLParser()
        project = parser.parse_file(project_file)

        assert project.sprint_planning is not None
        assert len(project.sprint_planning.history) == 2
        assert project.sprint_planning.history[0].completed_story_points == 4
        assert project.sprint_planning.history[1].spillover_story_points == 0

    def test_validate_file_rejects_unsupported_external_history_format(self, tmp_path):
        """TOML parser should reject unsupported external sprint history formats."""
        project_file = tmp_path / "project.toml"
        project_file.write_text("""
[project]
name = "Example"
start_date = "2025-01-01"

[sprint_planning]
enabled = true
sprint_length_weeks = 2
capacity_mode = "tasks"

[sprint_planning.history]
format = "xml"
path = "sprint_history.xml"

[[tasks]]
id = "task_001"
name = "Task"

[tasks.estimate]
low = 1
expected = 2
high = 5
""".strip())

        parser = TOMLParser()
        is_valid, error = parser.validate_file(project_file)

        assert not is_valid
        assert "unsupported external history format" in error

    def test_validate_file_reports_unbounded_spillover_bracket_not_last(self, tmp_path):
        """TOML raw validation should flag size brackets after an unbounded bracket."""
        file_path = tmp_path / "invalid_spillover_brackets.toml"
        file_path.write_text("""
[project]
name = "Example"
start_date = "2025-01-01"

[sprint_planning]
enabled = true
sprint_length_weeks = 2
capacity_mode = "story_points"

[sprint_planning.spillover]
enabled = true

[[sprint_planning.spillover.size_brackets]]
probability = 0.2

[[sprint_planning.spillover.size_brackets]]
max_points = 5
probability = 0.3

[[sprint_planning.history]]
sprint_id = "SPR-001"
completed_story_points = 10

[[sprint_planning.history]]
sprint_id = "SPR-002"
completed_story_points = 8

[[tasks]]
id = "task_001"
name = "Task"
planning_story_points = 3

[tasks.estimate]
low = 1
expected = 2
high = 3
""".strip())

        parser = TOMLParser()
        is_valid, error = parser.validate_file(file_path)

        assert not is_valid
        assert "line 13" in error
        assert "unbounded bracket last" in error
