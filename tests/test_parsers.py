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
