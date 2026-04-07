
# Validation Utilities

## Overview

This module provides two lightweight utilities for integrating mcprojsim into scripts and pipelines. `Validator` offers a single static method that auto-detects a project file's format from its extension (`.yaml`/`.yml` or `.toml`), delegates to the appropriate parser, and returns a structured `(bool, str)` result — no parser knowledge required. `setup_logging` configures the named `mcprojsim` logger for library consumers, directing output to stdout with a timestamped format and a configurable log level.

**When to use this module:** Use `Validator` for pre-flight checks in CI/CD pipelines before running a simulation, and `setup_logging` when embedding mcprojsim as a library to control log verbosity without touching the root logger.

| Capability | Description |
|---|---|
| Format auto-detection | Chooses `YAMLParser` or `TOMLParser` based on file extension |
| File existence check | Returns a clear error if the file path does not exist |
| Structured result | Returns `(True, "")` on success or `(False, error_message)` on failure |
| Logger configuration | Configures the `mcprojsim` named logger with a stdout handler and formatter |
| Configurable log level | Accepts `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` as a string |

**Imports:**
```python
from mcprojsim.utils import Validator
from mcprojsim.utils.logging import setup_logging
```

## `Validator`

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

## `setup_logging`

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

