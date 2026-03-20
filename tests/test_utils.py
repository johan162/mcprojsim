"""Tests for utilities."""

import pytest
import yaml

from mcprojsim.utils.validation import Validator
from mcprojsim.utils.logging import setup_logging


class TestValidator:
    """Tests for validator."""

    @pytest.fixture
    def valid_project_file(self, tmp_path):
        """Create a valid project file."""
        data = {
            "project": {"name": "Test", "start_date": "2025-01-01"},
            "tasks": [
                {
                    "id": "task_001",
                    "name": "Task 1",
                    "estimate": {"low": 1, "expected": 2, "high": 5},
                }
            ],
        }
        file_path = tmp_path / "project.yaml"
        with open(file_path, "w") as f:
            yaml.dump(data, f)
        return file_path

    @pytest.fixture
    def invalid_project_file(self, tmp_path):
        """Create an invalid project file."""
        data = {"invalid": "data"}
        file_path = tmp_path / "invalid.yaml"
        with open(file_path, "w") as f:
            yaml.dump(data, f)
        return file_path

    def test_validate_valid_file(self, valid_project_file):
        """Test validating a valid file."""
        is_valid, error = Validator.validate_file(valid_project_file)
        assert is_valid
        assert error == ""

    def test_validate_invalid_file(self, invalid_project_file):
        """Test validating an invalid file."""
        is_valid, error = Validator.validate_file(invalid_project_file)
        assert not is_valid
        assert len(error) > 0

    def test_validate_nonexistent_file(self):
        """Test validating a non-existent file."""
        is_valid, error = Validator.validate_file("nonexistent.yaml")
        assert not is_valid
        assert "not found" in error.lower()

    def test_validate_unsupported_format(self, tmp_path):
        """Test validating unsupported file format."""
        file_path = tmp_path / "project.txt"
        file_path.write_text("some content")

        is_valid, error = Validator.validate_file(file_path)
        assert not is_valid
        assert "Unsupported" in error

    def test_validate_toml_file(self, tmp_path):
        """Test validating a TOML file."""
        import tomli_w

        data = {
            "project": {"name": "Test", "start_date": "2025-01-01"},
            "tasks": [
                {
                    "id": "task_001",
                    "name": "Task 1",
                    "estimate": {"low": 1, "expected": 2, "high": 5},
                }
            ],
        }
        file_path = tmp_path / "project.toml"
        with open(file_path, "wb") as f:
            tomli_w.dump(data, f)

        is_valid, error = Validator.validate_file(file_path)
        assert is_valid
        assert error == ""


class TestLogging:
    """Tests for logging utilities."""

    def test_setup_logging(self):
        """Test setting up logging."""
        logger = setup_logging()
        assert logger is not None
        assert logger.name == "mcprojsim"

    def test_setup_logging_with_level(self):
        """Test setting up logging with custom level."""
        logger = setup_logging("DEBUG")
        assert logger.level == 10  # DEBUG level

    def test_setup_logging_default_level(self):
        """Test setting up logging with default level."""
        logger = setup_logging()
        assert logger.level == 20  # INFO level
