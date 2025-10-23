# Examples

This page provides practical examples of project definitions. For complete specification details, see the [Formal Grammar](grammar.md).

## Basic Web Application

A simple web application project with frontend and backend tasks.

```yaml
project:
  name: "Simple Web App"
  start_date: "2025-11-01"

tasks:
  - id: "backend"
    name: "Backend API"
    estimate:
      min: 5
      most_likely: 7
      max: 12
      unit: "days"
    dependencies: []
    uncertainty_factors:
      team_experience: "medium"
      technical_complexity: "medium"

  - id: "frontend"
    name: "Frontend UI"
    estimate:
      min: 4
      most_likely: 6
      max: 10
      unit: "days"
    dependencies: []
    uncertainty_factors:
      team_experience: "high"
      technical_complexity: "low"

  - id: "integration"
    name: "Integration Testing"
    estimate:
      min: 2
      most_likely: 3
      max: 5
      unit: "days"
    dependencies: ["backend", "frontend"]
    uncertainty_factors:
      team_experience: "medium"
      integration_complexity: "medium"
```

## Project with Risks

Example showing task-level and project-level risks.

```yaml
project:
  name: "Risky Project"
  start_date: "2025-11-01"

project_risks:
  - id: "resource_loss"
    name: "Team member leaves"
    probability: 0.20
    impact:
      type: "percentage"
      value: 25

tasks:
  - id: "development"
    name: "Development"
    estimate:
      min: 10
      most_likely: 15
      max: 25
      unit: "days"
    dependencies: []
    risks:
      - id: "tech_debt"
        name: "Technical debt discovered"
        probability: 0.30
        impact: 5
```

## Complex Project with Dependencies

A more realistic project with multiple dependencies.

See `examples/sample_project.yaml` in the repository for a complete example with:
- 8 tasks with complex dependencies
- Multiple uncertainty factors
- Task-level and project-level risks
- Distributed team considerations

## Using Log-Normal Distribution

For tasks where extreme values are more likely:

```yaml
tasks:
  - id: "research"
    name: "Research new technology"
    estimate:
      distribution: "lognormal"
      most_likely: 5
      standard_deviation: 2
      unit: "days"
    dependencies: []
```

## Running Examples

```bash
# Run the sample project
mc-estimate simulate examples/sample_project.yaml

# With custom config
mc-estimate simulate examples/sample_project.yaml \
  --config examples/sample_config.yaml

# With specific seed for reproducibility
mc-estimate simulate examples/sample_project.yaml --seed 42

# More iterations for higher accuracy
mc-estimate simulate examples/sample_project.yaml --iterations 50000
```
