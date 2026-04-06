
## Validation Utilities

### `Validator`

Convenience utility for validating project files by extension.

Import:

```python
from mcprojsim.utils import Validator
```

**Method:**

- **`validate_file(file_path: Path | str) -> tuple[bool, str]`** — Returns `(True, "")` on success or `(False, error_message)` on failure. Selects the parser automatically based on file extension (`.yaml`/`.yml` or `.toml`). Returns an error for unsupported extensions or missing files.

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

- **`setup_logging(level: str = "INFO") -> logging.Logger`** — Configure and return the `mcprojsim` named logger at the specified level. Accepted levels: `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`, `"CRITICAL"`.

**Example:**

```python
logger = setup_logging(level="DEBUG")
logger.debug("Simulation started")
```

