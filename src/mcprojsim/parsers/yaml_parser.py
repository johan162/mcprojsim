"""YAML parser for project definition files."""

from pathlib import Path
from typing import Any, Dict

import yaml

from mcprojsim.models.project import Project


class YAMLParser:
    """Parser for YAML project definition files."""

    def parse_file(self, file_path: Path | str) -> Project:
        """Parse a YAML project file.

        Args:
            file_path: Path to YAML file

        Returns:
            Project object

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file content is invalid
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Project file not found: {file_path}")

        with open(file_path, "r") as f:
            data = yaml.safe_load(f)

        return self.parse_dict(data)

    def parse_dict(self, data: Dict[str, Any]) -> Project:
        """Parse project data from dictionary.

        Args:
            data: Project data dictionary

        Returns:
            Project object
        """
        try:
            return Project(**data)
        except Exception as e:
            raise ValueError(f"Invalid project data: {e}") from e

    def validate_file(self, file_path: Path | str) -> tuple[bool, str]:
        """Validate a project file without creating Project object.

        Args:
            file_path: Path to project file

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            self.parse_file(file_path)
            return True, ""
        except Exception as e:
            return False, str(e)
