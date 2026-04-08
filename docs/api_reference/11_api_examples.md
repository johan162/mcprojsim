
# API Examples

## Overview

This page contains complete, runnable code examples that show end-to-end usage of the mcprojsim public API. Each example is self-contained and covers a distinct integration pattern — from single-project simulation to portfolio batch processing and web dashboard embedding. They are designed to serve as integration test templates or as starting points for custom tooling built on top of mcprojsim.

For parameter details, consult the API reference pages for [`SimulationEngine`](./02_core.md), [`Config`](./06_configuration.md), [`YAMLParser`](./05_parsers.md), the [analysis modules](./08_analysis_helpers.md), and [exporters](./07_exporters.md).

| Example | What it demonstrates |
|---|---|
| 1 — Programmatic Simulation with Full Analysis | Load a YAML project, run a simulation, run critical-path / sensitivity / staffing analysis, export JSON and HTML |
| 2 — Resource-Constrained and Two-Pass Scheduling | Build a `Project` model in code, enable two-pass scheduling, inspect resource utilisation metrics |
| 3 — Dashboard Integration | Embed mcprojsim in a Flask API endpoint; parse a project file and return percentile results as JSON |
| 4 — Sprint Planning with Forecast | Run `SprintSimulationEngine` on a sprint-enabled project and build a sprint-by-sprint delivery forecast |
| 5 — Batch Processing Multiple Projects | Scan a directory of YAML files, simulate each project, and aggregate results into a pandas DataFrame |
| 6 — Configuration-Driven Customization | Load a `Config` from file and apply programmatic overrides before running a simulation |

---

## Example 1: Programmatic Simulation with Full Analysis

This example shows how an external tool can load a project, run a simulation, and perform comprehensive analysis:

```python
from mcprojsim import SimulationEngine
from mcprojsim.config import Config
from mcprojsim.parsers import YAMLParser
from mcprojsim.analysis.critical_path import CriticalPathAnalyzer
from mcprojsim.analysis.staffing import StaffingAnalyzer
from mcprojsim.analysis.sensitivity import SensitivityAnalyzer
from mcprojsim.exporters import HTMLExporter, JSONExporter

def run_comprehensive_analysis(project_file: str, output_dir: str):
    """Load, simulate, analyze, and export a complete project report."""
    
    # Step 1: Load project and configuration
    project = YAMLParser().parse_file(project_file)
    config = Config.get_default()
    
    # Step 2: Run simulation
    engine = SimulationEngine(
        iterations=10000,
        random_seed=42,
        config=config,
        show_progress=True
    )
    results = engine.run(project)
    
    # Step 3: Critical path analysis
    cp_analyzer = CriticalPathAnalyzer()
    critical_tasks = cp_analyzer.get_most_critical_tasks(results, threshold=0.7)
    print(f"Critical tasks (>70% frequency): {critical_tasks}")
    
    # Step 4: Sensitivity analysis
    sens_analyzer = SensitivityAnalyzer()
    top_risks = sens_analyzer.get_top_contributors(results, n=5)
    print("\nTop 5 sensitivity contributors:")
    for task_id, correlation in top_risks:
        print(f"  {task_id}: {correlation:.3f}")
    
    # Step 5: Staffing recommendations
    staff_analyzer = StaffingAnalyzer()
    recommendations = staff_analyzer.recommend_team_size(results, config)
    for rec in recommendations:
        print(f"Staffing ({rec.profile}): {rec.recommended_team_size} people, "
              f"{rec.calendar_working_days} days, {rec.efficiency*100:.0f}% efficiency")
    
    # Step 6: Export all formats
    base_path = f"{output_dir}/analysis"
    JSONExporter.export(results, f"{base_path}.json", config=config, project=project)
    HTMLExporter.export(results, f"{base_path}.html", project=project, config=config)
    
    return results

# Usage
results = run_comprehensive_analysis("project.yaml", "reports/")
print(f"\nSimulation complete. Mean duration: {results.mean:.0f} hours")
```

## Example 2: Resource-Constrained and Two-Pass Scheduling

This example shows how to enable resource-constrained scheduling and two-pass mode:

```python
from datetime import date
from mcprojsim import SimulationEngine
from mcprojsim.config import Config
from mcprojsim.models.project import (
    Project, ProjectMetadata, Task, TaskEstimate,
    ResourceSpec, CalendarSpec,
)

# Define resources and calendars
project = Project(
    project=ProjectMetadata(
        name="Constrained Project",
        start_date=date(2026, 6, 1),
    ),
    tasks=[
        Task(
            id="task_a",
            name="Backend work",
            estimate=TaskEstimate(low=20, expected=40, high=80),
            resources=["dev_team"],
        ),
        Task(
            id="task_b",
            name="Frontend work",
            estimate=TaskEstimate(low=16, expected=32, high=64),
            resources=["dev_team"],
        ),
        Task(
            id="task_c",
            name="Integration",
            estimate=TaskEstimate(low=8, expected=16, high=32),
            dependencies=["task_a", "task_b"],
            resources=["dev_team"],
        ),
    ],
    resources=[
        ResourceSpec(name="dev_team", availability=1.0, experience_level=3),
        ResourceSpec(name="dev_team", availability=0.8, experience_level=2),
    ],
    calendars=[
        CalendarSpec(
            id="default",
            work_hours_per_day=8.0,
            work_days=[1, 2, 3, 4, 5],
            holidays=[date(2026, 7, 4)],
        ),
    ],
)

config = Config.get_default()

# Run with two-pass scheduling for better resource prioritization
engine = SimulationEngine(
    iterations=10000,
    random_seed=42,
    config=config,
    two_pass=True,
    pass1_iterations=2000,
)
results = engine.run(project)

print(f"Schedule mode: {results.schedule_mode}")
print(f"Resource utilization: {results.resource_utilization*100:.1f}%")
print(f"Resource wait time: {results.resource_wait_time_hours:.1f} hours")

if results.two_pass_trace and results.two_pass_trace.enabled:
    delta = results.two_pass_trace
    print(f"Two-pass P50 improvement: {delta.delta_p50_hours:+.1f} hours")
```

## Example 3: Dashboard Integration

This example demonstrates integrating mcprojsim into a web dashboard:

```python
from flask import Flask, request, jsonify
from mcprojsim import SimulationEngine
from mcprojsim.config import Config
from mcprojsim.models.project import Project
from pathlib import Path
import json

app = Flask(__name__)

@app.route('/api/simulate', methods=['POST'])
def simulate_project():
    """API endpoint for running simulations."""
    
    # Parse request
    data = request.json
    project_file = data.get('project_file')
    iterations = data.get('iterations', 5000)
    
    # Load and validate
    from mcprojsim.parsers import YAMLParser
    try:
        project = YAMLParser().parse_file(project_file)
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    
    # Run simulation
    config = Config.get_default()
    engine = SimulationEngine(iterations=iterations, config=config)
    results = engine.run(project)
    
    # Build response with key metrics
    return jsonify({
        'project_name': results.project_name,
        'iterations': results.iterations,
        'mean_hours': float(results.mean),
        'mean_days': float(results.mean / results.hours_per_day),
        'percentiles': {
            'p50': float(results.percentile(50)),
            'p80': float(results.percentile(80)),
            'p95': float(results.percentile(95)),
        },
        'critical_tasks': list(results.get_critical_path().keys())[:10],
        'success_at_500h': float(results.probability_of_completion(500)),
    })

@app.route('/api/config', methods=['GET'])
def get_config():
    """Return active configuration."""
    config = Config.get_default()
    return jsonify({
        't_shirt_categories': config.get_t_shirt_categories(),
        'uncertainty_factors': {
            'team_experience': ['high', 'medium', 'low'],
            'requirements_maturity': ['high', 'medium', 'low'],
        }
    })
```

## Example 4: Sprint Planning with Forecast

This example shows sprint-planning integration:

```python
from mcprojsim.parsers import YAMLParser
from mcprojsim.planning.sprint_engine import SprintSimulationEngine

def forecast_project_completion(project_file: str) -> dict:
    """Forecast sprint-by-sprint delivery timeline."""
    
    project = YAMLParser().parse_file(project_file)
    
    # Sprint planning must be enabled
    if not project.sprint_planning or not project.sprint_planning.enabled:
        raise ValueError("Sprint planning not enabled in project")
    
    # Run sprint simulation
    engine = SprintSimulationEngine(iterations=5000, random_seed=42)
    results = engine.run(project)
    
    # Build forecast
    forecast = {
        'project_name': results.project_name,
        'sprint_length_weeks': results.sprint_length_weeks,
        'forecasts': {
            'p50_sprints': results.percentile(50),
            'p80_sprints': results.percentile(80),
            'p50_date': results.date_percentile(50),
            'p80_date': results.date_percentile(80),
        },
        'guidance': {
            'recommended_capacity': results.planned_commitment_guidance,
            'historical_velocity': results.historical_diagnostics.get('series_statistics', {}).get('completed_units', {}).get('mean', 0),
            'risk_level': 'low' if results.std_dev < results.mean * 0.2 else 'high',
        }
    }
    
    return forecast

# Usage
forecast = forecast_project_completion("sprint_project.yaml")
print(f"P80 completion: {forecast['forecasts']['p80_date']}")
```

## Example 5: Batch Processing Multiple Projects

This example processes multiple projects and generates a portfolio view:

```python
from pathlib import Path
from mcprojsim import SimulationEngine
from mcprojsim.config import Config
from mcprojsim.parsers import YAMLParser
import pandas as pd

def analyze_portfolio(project_dir: str) -> pd.DataFrame:
    """Run simulations for all projects in a directory and create summary."""
    
    results_list = []
    config = Config.get_default()
    
    for project_file in Path(project_dir).glob("*.yaml"):
        print(f"Processing {project_file.name}...")
        
        try:
            project = YAMLParser().parse_file(str(project_file))
            engine = SimulationEngine(iterations=5000, config=config, show_progress=False)
            results = engine.run(project)
            
            results_list.append({
                'project': project.project.name,
                'tasks': len(project.tasks),
                'mean_hours': results.mean,
                'mean_days': results.mean / results.hours_per_day,
                'p80_hours': results.percentile(80),
                'p95_hours': results.percentile(95),
                'risk_high': len([t for t in results.get_critical_path().items() 
                                 if t[1] > 0.8]),
            })
        except Exception as e:
            print(f"  Error: {e}")
    
    # Create DataFrame
    df = pd.DataFrame(results_list)
    df = df.sort_values('mean_days', ascending=False)
    
    print("\n=== Portfolio Summary ===")
    print(df.to_string(index=False))
    print(f"\nTotal projected effort: {df['mean_hours'].sum():.0f} hours")
    
    return df

# Usage
portfolio = analyze_portfolio("projects/")
```

## Example 6: Configuration-Driven Customization

This example shows how to customize the simulation via configuration:

```python
from mcprojsim.config import Config
from mcprojsim import SimulationEngine
from mcprojsim.parsers import YAMLParser
import yaml

def simulate_with_custom_config(project_file: str, config_file: str, overrides: dict):
    """Run simulation with config file + programmatic overrides."""
    
    # Load config from file
    config = Config.load_from_file(config_file)
    
    # Apply programmatic overrides
    if 'histogram_bins' in overrides:
        config.output.histogram_bins = overrides['histogram_bins']
    
    if 'iterations' in overrides:
        iterations = overrides['iterations']
    else:
        iterations = config.simulation.default_iterations
    
    if 'staffing_percentile' in overrides:
        config.staffing.effort_percentile = overrides['staffing_percentile']
    
    # Run simulation with customized config
    project = YAMLParser().parse_file(project_file)
    engine = SimulationEngine(
        iterations=iterations,
        random_seed=42,
        config=config
    )
    results = engine.run(project)
    
    return results

# Usage - override histogram bins to 100 and use P80 for staffing
results = simulate_with_custom_config(
    'project.yaml',
    'config.yaml',
    {
        'histogram_bins': 100,
        'staffing_percentile': 80,
        'iterations': 20000,
    }
)
```

