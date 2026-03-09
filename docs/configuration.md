# Configuration

## Configuration File

Create a `config.yaml` file to customize uncertainty factors, symbolic estimate mappings, and simulation settings:

```yaml
uncertainty_factors:
  team_experience:
    high: 0.90
    medium: 1.0
    low: 1.30
  
  requirements_maturity:
    high: 1.0
    medium: 1.15
    low: 1.40
  
  technical_complexity:
    low: 1.0
    medium: 1.20
    high: 1.50
  
  team_distribution:
    colocated: 1.0
    distributed: 1.25
  
  integration_complexity:
    low: 1.0
    medium: 1.15
    high: 1.35

t_shirt_sizes:
  XS:
    min: 0.5
    most_likely: 1
    max: 2
  M:
    min: 3
    most_likely: 5
    max: 8

story_points:
  1:
    min: 0.5
    most_likely: 1
    max: 3
  5:
    min: 3
    most_likely: 5
    max: 8
  8:
    min: 5
    most_likely: 8
    max: 15

simulation:
  default_iterations: 10000
  random_seed: 42  # For reproducibility
  max_stored_critical_paths: 20  # Keep the 20 most common full critical paths

output:
  formats: ["json", "csv", "html"]
  include_histogram: true
  histogram_bins: 50
  critical_path_report_limit: 2  # Show the two most common paths in reports by default
```

## Uncertainty Factors

Uncertainty factors are multipliers applied to base task estimates. A value of 1.0 is baseline, values less than 1.0 speed up tasks, and values greater than 1.0 slow them down.

### Team Experience

- **high (0.90)**: Experienced team, 10% faster than baseline
- **medium (1.0)**: Average experience, baseline speed
- **low (1.30)**: Inexperienced team, 30% slower than baseline

### Requirements Maturity

- **high (1.0)**: Well-defined, stable requirements
- **medium (1.15)**: Some ambiguity, minor changes expected
- **low (1.40)**: High ambiguity, significant changes likely

### Technical Complexity

- **low (1.0)**: Simple, well-understood technology
- **medium (1.20)**: Moderate complexity
- **high (1.50)**: Cutting-edge or complex technology

### Team Distribution

- **colocated (1.0)**: Team in same location
- **distributed (1.25)**: Distributed team with communication overhead

### Integration Complexity

- **low (1.0)**: Minimal integration with other systems
- **medium (1.15)**: Moderate integration
- **high (1.35)**: Complex integration with multiple systems

## Using Configuration

If you provide only a subset of `t_shirt_sizes` or `story_points`, the built-in defaults remain available for the values you did not override.

### Command Line

```bash
mcprojsim simulate project.yaml --config config.yaml
```

### Python API

```python
from mcprojsim import SimulationEngine
from mcprojsim.config import Config

config = Config.load_from_file("config.yaml")
engine = SimulationEngine(iterations=10000, config=config)
```

### Critical path reporting

The simulation can now keep track of full critical path sequences, not just task-level criticality.

- `simulation.max_stored_critical_paths` controls how many of the most common full paths are retained in the results object.
- `output.critical_path_report_limit` controls how many of those stored paths are shown in CLI summaries and exports by default.

Example:

```yaml
simulation:
  default_iterations: 10000
  random_seed: null
  max_stored_critical_paths: 50

output:
  formats: ["json", "html"]
  include_histogram: true
  histogram_bins: 50
  critical_path_report_limit: 3
```

With that configuration, the simulation stores up to 50 unique full critical path sequences and shows the top 3 most common ones in the CLI, JSON, CSV, and HTML outputs.

You can override the report count from the CLI:

```bash
mcprojsim simulate project.yaml --config config.yaml --critical-paths 5
```

This affects reporting only. Storage remains controlled by `simulation.max_stored_critical_paths`.

## Viewing Current Configuration

```bash
mcprojsim config show
mcprojsim config show --config-file config.yaml
```

The `config show` output now includes:

- default iteration count
- random seed
- max stored critical paths
- output histogram settings
- critical path report limit

## Symbolic Estimate Mappings

### T-shirt sizes

Tasks may use `t_shirt_size` instead of an explicit numeric range. Those labels are resolved through the `t_shirt_sizes` section in the active configuration. The unit for T-shirt size values is controlled by `t_shirt_size_unit` in the configuration (default: `"hours"`).

Default built-in mappings:

- `XS`: `(0.5, 1, 2)`
- `S`: `(1, 2, 4)`
- `M`: `(3, 5, 8)`
- `L`: `(5, 8, 13)`
- `XL`: `(8, 13, 21)`
- `XXL`: `(13, 21, 34)`

### Story Points

Tasks may also use `story_points` for agile-style relative sizing. Story Points are resolved to numeric ranges through the `story_points` section in the active configuration. The unit for story point values is controlled by `story_point_unit` in the configuration (default: `"days"`).

Default built-in mappings:

- `1`: `(0.5, 1, 3)`
- `2`: `(1, 2, 4)`
- `3`: `(1.5, 3, 5)`
- `5`: `(3, 5, 8)`
- `8`: `(5, 8, 15)`
- `13`: `(8, 13, 21)`
- `21`: `(13, 21, 34)`

Example Story Point override:

```yaml
story_points:
  5:
    min: 4
    most_likely: 6
    max: 9
  8:
    min: 6
    most_likely: 9
    max: 16
```

Story point estimates must **not** include a `unit` field in the project file. The unit is determined by `story_point_unit` in the configuration. Similarly, T-shirt size estimates must not include a `unit` field — the unit is determined by `t_shirt_size_unit` (default: `"hours"`).

## Probability Thresholds for Thermometer Visualization

Configure color thresholds for the HTML thermometer visualization in your project file:

```yaml
project:
  name: "My Project"
  start_date: "2025-01-01"
  # Probability thresholds for visual risk indicators
  probability_red_threshold: 0.50    # Below 50%: High risk (red)
  probability_green_threshold: 0.90  # Above 90%: Low risk (green)
                                     # Between: Medium risk (gradient red→yellow→green)
```

### Default Values

- **probability_red_threshold**: 0.50 (50%)
- **probability_green_threshold**: 0.90 (90%)

### Custom Thresholds

Adjust thresholds based on project risk tolerance:

**Conservative (low-risk tolerance)**:
```yaml
probability_red_threshold: 0.70    # Below 70%: red
probability_green_threshold: 0.95  # Above 95%: green
```

**Aggressive (high-risk tolerance)**:
```yaml
probability_red_threshold: 0.30    # Below 30%: red
probability_green_threshold: 0.80  # Above 80%: green
```

### Thermometer Visualization

The HTML export displays a vertical thermometer showing:
- **Effort levels** (in hours) on the right
- **Probability of success** for each effort level in colored segments
- **Color gradient**:
  - 🔴 **Bright Red**: Probability below red threshold (high risk)
  - 🟡 **Yellow/Orange**: Between thresholds (medium risk)
  - 🟢 **Bright Green**: Above green threshold (low risk)

This helps stakeholders quickly understand:
- What effort level gives desired probability of success
- Risk levels at different commitment levels
- Where the project falls on the risk spectrum

## Calibrating Uncertainty Factors

To calibrate factors for your organization:

1. **Collect Historical Data**: Gather actual vs. estimated durations
2. **Calculate Multipliers**: Compare teams/projects with different characteristics
3. **Update Configuration**: Adjust factors based on observed differences
4. **Iterate**: Refine over multiple projects

Example:
- Projects with experienced teams took 85% of estimated time → set high to 0.85
- Projects with distributed teams took 30% longer → set distributed to 1.30
