"""Validation utilities."""

from pathlib import Path

from mcprojsim.parsers import YAMLParser, TOMLParser


class Validator:
    """Validator for project files."""

    @staticmethod
    def validate_file(file_path: Path | str) -> tuple[bool, str]:
        """Validate a project definition file.

        Args:
            file_path: Path to project file

        Returns:
            Tuple of (is_valid, error_message)
        """
        file_path = Path(file_path)

        if not file_path.exists():
            return False, f"File not found: {file_path}"

        # Determine parser based on extension
        if file_path.suffix in [".yaml", ".yml"]:
            parser = YAMLParser()
        elif file_path.suffix == ".toml":
            parser = TOMLParser()
        else:
            return False, f"Unsupported file format: {file_path.suffix}"

        # Validate
        return parser.validate_file(file_path)
