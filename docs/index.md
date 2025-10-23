# Welcome to Monte Carlo Project Simulator

## Overview

Monte Carlo Project Simulator (mcprojsim) is a powerful tool for probabilistic software project estimation. Instead of giving you a single, often unreliable deadline, it provides a range of possible outcomes with confidence levels.

## Key Features

- **Triangular & Log-Normal Distributions** for realistic task duration modeling
- **Risk Analysis** at both project and task levels
- **Dependency Management** with automatic critical path identification
- **Uncertainty Factors** to account for team experience, requirements maturity, and more
- **Multiple Output Formats** including JSON, CSV, and HTML reports
- **Reproducible Results** with random seed support

## Why Monte Carlo Simulation?

Traditional project estimation often fails because it provides a single point estimate that doesn't account for uncertainty. Monte Carlo simulation:

1. **Acknowledges Uncertainty** - Uses probability distributions instead of single values
2. **Quantifies Risk** - Shows the probability of meeting different deadlines
3. **Identifies Critical Paths** - Highlights which tasks most impact the schedule
4. **Improves Communication** - Provides stakeholders with realistic expectations

## Quick Example

```yaml
# project.yaml
project:
  name: "My Project"
  start_date: "2025-11-01"

tasks:
  - id: "task_001"
    name: "Backend API"
    estimate:
      min: 5
      most_likely: 8
      max: 15
      unit: "days"
    dependencies: []
    uncertainty_factors:
      team_experience: "medium"
      technical_complexity: "high"
```

```bash
# Run simulation
mc-estimate simulate project.yaml --iterations 10000

# Output
Mean: 42.3 days
P50 (Median): 40.5 days
P80: 48.2 days
P90: 52.7 days
```

## Installation

```bash
pip install mcprojsim
```

Or install from source:

```bash
git clone https://github.com/yourusername/mcprojsim.git
cd mcprojsim
pip install -e .
```

## Next Steps

- [Getting Started Guide](getting_started.md) - Learn how to create your first project
- [Configuration](configuration.md) - Customize uncertainty factors
- [API Reference](api_reference.md) - Integrate into your tools

## License

MIT License - see LICENSE file for details.
