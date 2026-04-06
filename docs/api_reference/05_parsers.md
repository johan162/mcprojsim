
## Parsers

Both parsers translate project definition files into [`Project`](03_project_model.md) model objects. They share an identical public interface and emit file-and-line-aware error messages on invalid input.

```python
from mcprojsim.parsers import YAMLParser, TOMLParser
```

### `YAMLParser`

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

### `TOMLParser`

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
