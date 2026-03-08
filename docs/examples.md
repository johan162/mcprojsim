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

## Using T-Shirt Sizing

For quick estimation using relative sizes (XS, S, M, L, XL, XXL):

```yaml
project:
  name: "Mobile App Development"
  start_date: "2025-11-01"

tasks:
  - id: "ui_design"
    name: "UI/UX Design"
    estimate:
      t_shirt_size: "M"
      unit: "days"
    dependencies: []
    uncertainty_factors:
      team_experience: "high"

  - id: "backend"
    name: "Backend Development"
    estimate:
      t_shirt_size: "XL"
      unit: "days"
    dependencies: []
    uncertainty_factors:
      technical_complexity: "high"

  - id: "mobile_app"
    name: "Mobile App"
    estimate:
      t_shirt_size: "XXL"
      unit: "days"
    dependencies: ["ui_design", "backend"]

  - id: "deployment"
    name: "Deploy to Store"
    estimate:
      t_shirt_size: "S"
      unit: "days"
    dependencies: ["mobile_app"]
```

T-shirt sizes map to default effort ranges (configurable):
- **XS**: 0.5-2 days (most likely: 1 day)
- **S**: 1-4 days (most likely: 2 days)
- **M**: 3-8 days (most likely: 5 days)
- **L**: 5-13 days (most likely: 8 days)
- **XL**: 8-21 days (most likely: 13 days)
- **XXL**: 13-34 days (most likely: 21 days)

See `examples/tshirt_sizing_project.yaml` for a complete example.

## Using Story Points

For agile-style relative estimation using calibrated Story Point mappings:

```yaml
project:
  name: "Sprint Backlog"
  start_date: "2025-11-01"

tasks:
  - id: "story_001"
    name: "Login flow"
    estimate:
      story_points: 3
      unit: "storypoint"
    dependencies: []

  - id: "story_002"
    name: "Profile page"
    estimate:
      story_points: 5
      unit: "storypoint"
    dependencies: ["story_001"]
```

Default Story Point mappings (configurable) are:

- `1`: 0.5-3 days (most likely: 1 day)
- `2`: 1-4 days (most likely: 2 days)
- `3`: 1.5-5 days (most likely: 3 days)
- `5`: 3-8 days (most likely: 5 days)
- `8`: 5-15 days (most likely: 8 days)
- `13`: 8-21 days (most likely: 13 days)
- `21`: 13-34 days (most likely: 21 days)

See `examples/story_points_walkthrough_project.yaml` for a complete example.

## Running Examples

```bash
# Run the sample project
mcprojsim simulate examples/sample_project.yaml

# With custom config
mcprojsim simulate examples/sample_project.yaml \
  --config examples/sample_config.yaml

# With specific seed for reproducibility
mcprojsim simulate examples/sample_project.yaml --seed 42

# More iterations for higher accuracy
mcprojsim simulate examples/sample_project.yaml --iterations 50000
```
