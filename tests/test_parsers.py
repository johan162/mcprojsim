"""Tests for parsers."""

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
                    "min": 1,
                    "most_likely": 2,
                    "max": 5,
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

        def test_validate_file_reports_yaml_line_numbers_and_field_suggestion(self, tmp_path):
                """Validation errors should include YAML line numbers and likely field names."""
                file_path = tmp_path / "invalid_field.yaml"
                file_path.write_text(
                        """
project:
    name: Example
    start_date: 2025-01-01
tasks:
    - id: task_001
        name: Example task
        estimate:
            min: 1
            mostlikely: 2
            max: 3
""".strip()
                )

                parser = YAMLParser()
                is_valid, error = parser.validate_file(file_path)

                assert not is_valid
                assert "line 9" in error
                assert "mostlikely" in error
                assert "most_likely" in error

        def test_parse_file_reports_dependency_suggestion(self, tmp_path):
                """Dependency validation should point to the dependency line with a suggestion."""
                file_path = tmp_path / "invalid_dependency.yaml"
                file_path.write_text(
                        """
project:
    name: Example
    start_date: 2025-01-01
tasks:
    - id: task_001
        name: First task
        estimate:
            min: 1
            most_likely: 2
            max: 3
    - id: task_002
        name: Second task
        estimate:
            min: 1
            most_likely: 2
            max: 3
        dependencies:
            - task_001_typo
""".strip()
                )

                parser = YAMLParser()

                with pytest.raises(ValueError, match="task_001") as exc_info:
                        parser.parse_file(file_path)

                assert "line 17" in str(exc_info.value)
                assert "task_001_typo" in str(exc_info.value)
                assert "task_001" in str(exc_info.value)


class TestTOMLParser:
    """Tests for TOML parser."""

    def test_parse_dict(self, sample_project_dict):
        """Test parsing from dictionary."""
        parser = TOMLParser()
        project = parser.parse_dict(sample_project_dict)
        assert isinstance(project, Project)
        assert project.project.name == "Test Project"

    def test_parse_file_not_found(self):
        """Test parsing non-existent file."""
        parser = TOMLParser()
        with pytest.raises(FileNotFoundError):
            parser.parse_file("nonexistent.toml")

    def test_validate_file_reports_toml_line_numbers_and_field_suggestion(self, tmp_path):
        """Validation errors should include TOML line numbers and likely field names."""
        file_path = tmp_path / "invalid.toml"
        file_path.write_text(
            """
[project]
name = "Example"
start_date = "2025-01-01"

[[tasks]]
id = "task_001"
name = "Task"

[tasks.estimate]
min = 1
mostlikely = 2
max = 3
""".strip()
        )

        parser = TOMLParser()
        is_valid, error = parser.validate_file(file_path)

        assert not is_valid
        assert "line 11" in error
        assert "mostlikely" in error
        assert "most_likely" in error

    def test_parse_file_reports_toml_syntax_line_numbers(self, tmp_path):
        """TOML syntax errors should include line and column information."""
        file_path = tmp_path / "syntax_error.toml"
        file_path.write_text(
            """
[project]
name = "Example"
start_date = "2025-01-01"

[[tasks]]
id = "task_001"
name = "Task"
[tasks.estimate
min = 1
most_likely = 2
max = 3
""".strip()
        )

        parser = TOMLParser()

        with pytest.raises(ValueError, match="line 8") as exc_info:
            parser.parse_file(file_path)

        assert "column" in str(exc_info.value)
