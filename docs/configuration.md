# Configuration

## Configuration File

Create a `config.yaml` file to customize uncertainty factors and simulation settings:

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

simulation:
  default_iterations: 10000
  random_seed: 42  # For reproducibility

output:
  formats: ["json", "csv", "html"]
  include_histogram: true
  histogram_bins: 50
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

### Command Line

```bash
mc-estimate simulate project.yaml --config config.yaml
```

### Python API

```python
from mcprojsim import SimulationEngine
from mcprojsim.config import Config

config = Config.load_from_file("config.yaml")
engine = SimulationEngine(iterations=10000, config=config)
```

## Viewing Current Configuration

```bash
mc-estimate config show
mc-estimate config show --config-file config.yaml
```

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
- **Effort levels** (in days) on the right
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
