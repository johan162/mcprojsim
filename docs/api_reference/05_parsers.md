
# Parsers

## Overview

The `mcprojsim.parsers` module translates YAML and TOML project definition files into validated [`Project`](03_project_model.md) model objects. `YAMLParser` and `TOMLParser` share an identical public interface — `parse_file`, `parse_dict`, and `validate_file` — so they are interchangeable given a file format. Both parsers use `error_reporting.py` to preserve file-and-line context when surfacing validation errors, so error messages point to the exact source location rather than generic Pydantic output.

**When to use this module:** Use the parsers when loading a project from disk in a script or tool integration; use `validate_file` for non-raising pre-flight checks before a simulation run.

| Capability | Description |
|---|---|
| YAML loading | `YAMLParser.parse_file` reads and parses a `.yaml` project file into a `Project` |
| TOML loading | `TOMLParser.parse_file` reads and parses a `.toml` project file into a `Project` |
| In-memory parsing | `parse_dict` constructs a `Project` from an already-loaded dictionary |
| Non-raising validation | `validate_file` returns `(bool, error_message)` without raising an exception |
| Line-aware errors | All errors include the file path and source line number via `error_reporting.py` |

**Imports:**
```python
from mcprojsim.parsers import YAMLParser, TOMLParser
```

---

## `YAMLParser`

Parses YAML project files into `Project` objects.

| Method | Signature | Description |
|--------|-----------|-------------|
| `parse_file` | `(file_path: Path \| str) -> Project` | Load and parse a YAML file. Raises `FileNotFoundError` if the file is missing, `ValueError` on invalid content. |
| `parse_dict` | `(data: dict[str, Any]) -> Project` | Parse project data from a dictionary. Raises `ValueError` on invalid data. |
| `validate_file` | `(file_path: Path \| str) -> tuple[bool, str]` | Validate without constructing a `Project`. Returns `(True, "")` on success or `(False, error_message)` on failure. |

```python
from mcprojsim.parsers import YAMLParser

parser = YAMLParser()

# Parse directly
project = parser.parse_file("project.yaml")

# Validate without raising
is_valid, error = parser.validate_file("project.yaml")
if not is_valid:
    print(f"Validation error: {error}")
```

## `TOMLParser`

Identical interface to `YAMLParser`, but for TOML project files.

| Method | Signature | Description |
|--------|-----------|-------------|
| `parse_file` | `(file_path: Path \| str) -> Project` | Load and parse a TOML file. Raises `FileNotFoundError` if the file is missing, `ValueError` on invalid content. |
| `parse_dict` | `(data: dict[str, Any]) -> Project` | Parse project data from a dictionary. Raises `ValueError` on invalid data. |
| `validate_file` | `(file_path: Path \| str) -> tuple[bool, str]` | Validate without constructing a `Project`. Returns `(True, "")` on success or `(False, error_message)` on failure. |

```python
from mcprojsim.parsers import TOMLParser

parser = TOMLParser()
project = parser.parse_file("project.toml")
is_valid, error = parser.validate_file("project.toml")
```
