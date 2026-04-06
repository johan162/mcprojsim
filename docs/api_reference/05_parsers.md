
## Parsers

### `YAMLParser`

Parses YAML project files into `Project` objects.

Methods:

- `parse_file(file_path) -> Project`
- `parse_dict(data) -> Project`
- `validate_file(file_path) -> tuple[bool, str]`

```python
from mcprojsim.parsers import YAMLParser

parser = YAMLParser()
project = parser.parse_file("project.yaml")
is_valid, error = parser.validate_file("project.yaml")
```

### `TOMLParser`

Same interface as `YAMLParser`, but for TOML project files.

```python
from mcprojsim.parsers import TOMLParser

parser = TOMLParser()
project = parser.parse_file("project.toml")
```
