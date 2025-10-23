# Getting Started

This guide will walk you through creating and running your first Monte Carlo simulation.

## Installation

### From PyPI

```bash
pip install mcprojsim
```

### From Source

```bash
git clone https://github.com/yourusername/mcprojsim.git
cd mcprojsim
pip install -e .
```

### Verify Installation

```bash
mc-estimate --version
```

## Your First Project

### Step 1: Create a Project File

Create a file called `my_project.yaml`:

```yaml
project:
  name: "Website Redesign"
  description: "Complete redesign of company website"
  start_date: "2025-11-01"
  confidence_levels: [50, 75, 80, 85, 90, 95]

tasks:
  - id: "task_001"
    name: "Design mockups"
    estimate:
      min: 2
      most_likely: 3
      max: 5
      unit: "days"
    dependencies: []
    uncertainty_factors:
      team_experience: "high"
      requirements_maturity: "medium"
      technical_complexity: "low"

  - id: "task_002"
    name: "Frontend implementation"
    estimate:
      min: 5
      most_likely: 8
      max: 12
      unit: "days"
    dependencies: ["task_001"]
    uncertainty_factors:
      team_experience: "medium"
      technical_complexity: "medium"

  - id: "task_003"
    name: "Testing and deployment"
    estimate:
      min: 2
      most_likely: 3
      max: 6
      unit: "days"
    dependencies: ["task_002"]
    uncertainty_factors:
      team_experience: "high"
      technical_complexity: "low"
```

### Step 2: Validate the Project File

```bash
mc-estimate validate my_project.yaml
```

You should see: `✓ Project file is valid!`

### Step 3: Run the Simulation

```bash
mc-estimate simulate my_project.yaml
```

This will run 10,000 iterations and display results like:

```
Loading project from my_project.yaml...
Running simulation with 10000 iterations...
Progress: 10.0% (1000/10000)
Progress: 20.0% (2000/10000)
...
Progress: 100.0% (10000/10000)

=== Simulation Results ===
Project: Website Redesign
Mean: 14.2 days
Median (P50): 13.8 days
Std Dev: 2.3 days

Confidence Intervals:
  P50: 13.8 days
  P80: 16.5 days
  P90: 17.9 days
  P95: 19.2 days

Results exported to Website_Redesign_results.json
Results exported to Website_Redesign_results.csv
Results exported to Website_Redesign_results.html
```

### Step 4: View the Results

Open the HTML file in your browser to see a detailed report with:
- Statistical summary
- Confidence intervals
- Critical path analysis

## Understanding the Output

### Percentiles

- **P50 (Median)**: 50% chance of completing by this date
- **P75**: 75% chance of completing by this date
- **P80**: 80% chance of completing by this date 
- **P85**: 85% chance of completing by this date (recommended for commitments)
- **P90**: 90% chance of completing by this date (high confidence)
- **P95**: 95% chance of completing by this date (very high confidence)

### Critical Path

Tasks with high criticality (e.g., >0.5) appear on the critical path frequently and should be monitored closely.

## Next Steps

- Learn about [Configuration](configuration.md) to customize uncertainty factors
- Explore the [examples directory](examples.md) for more complex projects
- Read the [API Reference](api_reference.md) to integrate mcprojsim into your tools
