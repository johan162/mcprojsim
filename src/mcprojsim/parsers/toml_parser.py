"""TOML parser for project definition files."""

import sys
from pathlib import Path
from typing import Any, Dict

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from mcprojsim.models.project import Project


class TOMLParser:
    """Parser for TOML project definition files."""

    def parse_file(self, file_path: Path | str) -> Project:
        """Parse a TOML project file.

        Args:
            file_path: Path to TOML file

        Returns:
            Project object

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file content is invalid
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Project file not found: {file_path}")

        with open(file_path, "rb") as f:
            data = tomllib.load(f)

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
