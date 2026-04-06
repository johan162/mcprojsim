
## Validation Utilities

### `Validator`

Convenience utility for validating project files by extension.

Import:

```python
from mcprojsim.utils import Validator
```

**Method:**

- **`validate_file(file_path: str | Path) -> tuple[bool, str]`** — Returns (is_valid, error_message). Auto-selects parser based on file extension.

**Example:**

```python
is_valid, error = Validator.validate_file("project.yaml")
if not is_valid:
    print(f"Validation failed: {error}")
else:
    print("Project is valid!")
```

### `setup_logging`

Configure logging verbosity and output for library usage.

Import:

```python
from mcprojsim.utils import setup_logging
```

**Method:**

- **`setup_logging(level: str = "INFO") -> logging.Logger`** — Returns configured logger with specified level (`"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`, `"CRITICAL"`)

**Example:**

```python
logger = setup_logging(level="INFO")
# Library logging now routes to this logger
```

