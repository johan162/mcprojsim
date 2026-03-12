# Welcome to Monte Carlo Project Simulator

## Overview

Monte Carlo Project Simulator (mcprojsim) is a powerful tool for probabilistic software project estimation. Instead of giving you a single, often unreliable deadline, it provides a range of possible outcomes with confidence levels.

## Key Features

- **Natural Language Project Input** — generate valid project files from plain-text descriptions with `mcprojsim generate`
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
% mcprojsim simulate examples/sample_project.yaml --iterations 10000 --table

# Output
mcprojsim, version 0.4.4
Progress: 100.0% (10000/10000)

=== Simulation Results ===
┌──────────────────────────┬────────────────────────────────┐
│ Parameter                │ Value                          │
├──────────────────────────┼────────────────────────────────┤
│ Project                  │ Customer Portal Redesign       │
│ Hours per Day            │ 8.0                            │
│ Mean                     │ 579.93 hours (73 working days) │
│ Median (P50)             │ 572.84 hours                   │
│ Std Dev                  │ 78.50 hours                    │
│ Coefficient of Variation │ 0.1354                         │
│ Skewness                 │ 0.5283                         │
│ Excess Kurtosis          │ 0.3507                         │
└──────────────────────────┴────────────────────────────────┘

Confidence Intervals:
┌──────────────┬─────────┬────────────────┬────────────┐
│ Percentile   │   Hours │   Working Days │ Date       │
├──────────────┼─────────┼────────────────┼────────────┤
│ P25          │  524.8  │             66 │ 2026-02-02 │
│ P50          │  572.84 │             72 │ 2026-02-10 │
│ P75          │  628.3  │             79 │ 2026-02-19 │
│ P80          │  642.91 │             81 │ 2026-02-23 │
│ P85          │  660    │             83 │ 2026-02-25 │
│ P90          │  684.51 │             86 │ 2026-03-02 │
│ P95          │  721.71 │             91 │ 2026-03-09 │
│ P99          │  791.99 │             99 │ 2026-03-19 │
└──────────────┴─────────┴────────────────┴────────────┘

Sensitivity Analysis (top contributors):
┌──────────┬───────────────┐
│ Task     │ Correlation   │
├──────────┼───────────────┤
│ task_004 │ +0.4268       │
│ task_008 │ +0.3250       │
│ task_002 │ +0.2914       │
│ task_006 │ +0.2904       │
│ task_001 │ +0.1686       │
│ task_005 │ +0.1649       │
│ task_007 │ -0.0098       │
│ task_003 │ -0.0031       │
└──────────┴───────────────┘

Schedule Slack:
┌──────────┬─────────────────┬───────────────┐
│ Task     │   Slack (hours) │ Status        │
├──────────┼─────────────────┼───────────────┤
│ task_008 │            0    │ Critical      │
│ task_006 │            0    │ Critical      │
│ task_005 │            0    │ Critical      │
│ task_004 │            0    │ Critical      │
│ task_001 │            0    │ Critical      │
│ task_002 │            0    │ Critical      │
│ task_003 │          165.14 │ 165.1h buffer │
│ task_007 │          356.32 │ 356.3h buffer │
└──────────┴─────────────────┴───────────────┘

Risk Impact Analysis:
┌──────────┬────────────────┬────────────────┬───────────────────────────────┐
│ Task     │   Mean (hours) │ Trigger Rate   │   Mean When Triggered (hours) │
├──────────┼────────────────┼────────────────┼───────────────────────────────┤
│ task_001 │           3.33 │ 20.8%          │                            16 │
│ task_003 │           5.97 │ 24.9%          │                            24 │
│ task_004 │          12.08 │ 30.2%          │                            40 │
│ task_006 │          11.25 │ 35.1%          │                            32 │
│ task_008 │           4.89 │ 20.4%          │                            24 │
└──────────┴────────────────┴────────────────┴───────────────────────────────┘

Most Frequent Critical Paths:
  1. task_001 -> task_002 -> task_004 -> task_005 -> task_006 -> task_008 (10000/10000, 100.0%)

```

## Installation

The easiest way is to intall from PyPi repository with:

```bash
pipx install mcprojsim
```

Or install from source:

```bash
git clone https://github.com/johan162/mcprojsim.git
cd mcprojsim
pip install -e .
```

## Next Steps

- [Getting Started](user_guide/getting_started.md) - Install and run your first simulation
- [Examples](examples.md) - Working examples and use cases
- [Configuration](configuration.md) - Customize uncertainty factors
- [API Reference](api_reference.md) - Integrate into your tools
- [Formal Grammar](grammar.md) - Complete specification in EBNF notation

## Development

For more details how to setup a development environment,use containers, build documentation and architecture description see

- [Development](development.md)

## License

MIT License - see LICENSE file for details.
