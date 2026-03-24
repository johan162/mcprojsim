"""YAML parser for project definition files."""

from pathlib import Path
from typing import Any, Dict

import yaml

from mcprojsim.models.project import Project
from mcprojsim.parsers.error_reporting import (
    format_validation_error,
    format_validation_issues,
    format_yaml_parse_error,
    load_yaml_with_locations,
    validate_project_payload,
)
from mcprojsim.parsers.sprint_history_parser import load_external_sprint_history


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
            text = f.read()

        try:
            parsed = load_yaml_with_locations(text)
        except yaml.YAMLError as e:
            raise ValueError(format_yaml_parse_error(e, file_path)) from e

        return self.parse_dict(
            parsed.data,
            file_path=file_path,
            path_lines=parsed.path_lines,
        )

    def parse_dict(
        self,
        data: Dict[str, Any],
        *,
        file_path: Path | str | None = None,
        path_lines: dict[tuple[str | int, ...], int] | None = None,
    ) -> Project:
        """Parse project data from dictionary.

        Args:
            data: Project data dictionary

        Returns:
            Project object
        """
        file_path = Path(file_path) if file_path is not None else Path("<memory>.yaml")
        path_lines = path_lines or {(): 1}
        data = load_external_sprint_history(data, file_path=file_path)

        issues = validate_project_payload(data)
        if issues:
            raise ValueError(format_validation_issues(issues, path_lines, file_path))

        try:
            return Project(**data)
        except Exception as e:
            raise ValueError(
                format_validation_error(e, path_lines, data, file_path)
            ) from e

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
