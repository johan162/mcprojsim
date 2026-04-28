
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
| 7 — Progress Callback and Cancellation | Use `progress_callback` to receive live progress updates and `cancel()` to abort a running simulation from another thread |
| 8 — Cost Estimation and Budget Analysis | Enable cost tracking, query budget confidence, and identify cost drivers |

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
    if 'number_bins' in overrides:
        config.output.number_bins = overrides['number_bins']
    
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
        'number_bins': 100,
        'staffing_percentile': 80,
        'iterations': 20000,
    }
)
```

## Example 7: Progress Callback and Cancellation

This example demonstrates two features added to `SimulationEngine`:

1. **`progress_callback`** — receive live `(completed, total)` updates during a simulation instead of progress being printed to stdout.
2. **`cancel()`** — abort a running simulation from any thread, causing `run()` to raise `SimulationCancelled`.

### 7a — Progress callback (basic usage)

```python
from datetime import date
from mcprojsim import SimulationEngine
from mcprojsim.models.project import Project, ProjectMetadata, Task, TaskEstimate


def on_progress(completed: int, total: int) -> None:
    pct = 100 * completed / total
    print(f"\r  Simulating… {pct:5.1f}%  ({completed}/{total})", end="", flush=True)


project = Project(
    project=ProjectMetadata(name="Callback Demo", start_date=date(2026, 5, 1)),
    tasks=[
        Task(id="t1", name="Design",  estimate=TaskEstimate(low=2, expected=5, high=10)),
        Task(id="t2", name="Build",   estimate=TaskEstimate(low=5, expected=10, high=20),
             dependencies=["t1"]),
        Task(id="t3", name="Test",    estimate=TaskEstimate(low=3, expected=6, high=12),
             dependencies=["t2"]),
    ],
)

engine = SimulationEngine(
    iterations=10000,
    random_seed=42,
    show_progress=True,          # would normally print to stdout …
    progress_callback=on_progress,  # … but the callback takes over instead
)
results = engine.run(project)
print(f"\nDone — P80: {results.percentile(80):.1f} hours")
```

When `progress_callback` is set, all stdout progress output is suppressed. The callback
receives `(completed_iterations, total_iterations)` updates from the engine even when
`show_progress=False`. In single-pass mode the total is just `iterations`. In two-pass
mode the total is `pass1_iterations + iterations`, so progress keeps moving forward
across both phases. Sequential runs report at the built-in 10 % cadence, while parallel
runs report as chunks complete, so update frequency can be higher on larger worker counts.

!!! note
    `show_progress` only controls stdout progress rendering. It does not disable the
    callback itself.

### 7b — Cancellation from another thread

```python
import threading
from datetime import date
from mcprojsim import SimulationEngine
from mcprojsim.simulation.engine import SimulationCancelled
from mcprojsim.models.project import Project, ProjectMetadata, Task, TaskEstimate

project = Project(
    project=ProjectMetadata(name="Cancel Demo", start_date=date(2026, 5, 1)),
    tasks=[
        Task(id="t1", name="Design",  estimate=TaskEstimate(low=2, expected=5, high=10)),
        Task(id="t2", name="Build",   estimate=TaskEstimate(low=5, expected=10, high=20),
             dependencies=["t1"]),
        Task(id="t3", name="Test",    estimate=TaskEstimate(low=3, expected=6, high=12),
             dependencies=["t2"]),
    ],
)

engine = SimulationEngine(iterations=500_000, random_seed=42, show_progress=False)


def run_in_background():
    try:
        results = engine.run(project)
        print(f"Finished: mean = {results.mean:.1f} hours")
    except SimulationCancelled:
        print("Simulation was cancelled.")


worker = threading.Thread(target=run_in_background)
worker.start()

# Cancel after a brief delay (e.g. user clicks "Stop")
import time
time.sleep(0.1)
engine.cancel()

worker.join(timeout=5.0)
assert not worker.is_alive(), "Worker should have stopped"
```

The `cancel()` method sets an internal flag that is checked at the top of every
iteration.  Because the check happens per-iteration, the engine finishes the
current iteration before raising `SimulationCancelled`.

### 7c — Combining callback with cancellation (GUI pattern)

A common GUI integration pattern is to use the callback for progress bar updates
and cancel from a UI button:

```python
import threading
from datetime import date
from mcprojsim import SimulationEngine
from mcprojsim.simulation.engine import SimulationCancelled
from mcprojsim.models.project import Project, ProjectMetadata, Task, TaskEstimate

project = Project(
    project=ProjectMetadata(name="GUI Pattern", start_date=date(2026, 5, 1)),
    tasks=[
        Task(id="t1", name="Design",  estimate=TaskEstimate(low=2, expected=5, high=10)),
        Task(id="t2", name="Build",   estimate=TaskEstimate(low=5, expected=10, high=20),
             dependencies=["t1"]),
        Task(id="t3", name="Test",    estimate=TaskEstimate(low=3, expected=6, high=12),
             dependencies=["t2"]),
    ],
)


# --- Simulate a GUI progress bar ---
progress_pct = 0


def update_progress_bar(completed: int, total: int) -> None:
    global progress_pct
    progress_pct = int(100 * completed / total)


engine = SimulationEngine(
    iterations=200_000,
    random_seed=42,
    show_progress=True,
    progress_callback=update_progress_bar,
)


def worker_fn():
    try:
        results = engine.run(project)
        print(f"Done — mean {results.mean:.1f} h, P80 {results.percentile(80):.1f} h")
    except SimulationCancelled:
        print(f"Cancelled at {progress_pct}%")


worker = threading.Thread(target=worker_fn)
worker.start()

# Simulate the user pressing "Cancel" after a short delay
import time
time.sleep(0.05)
engine.cancel()

worker.join(timeout=5.0)
print(f"Last reported progress: {progress_pct}%")
```

---

## Example 8 — Cost Estimation and Budget Analysis

Enable cost tracking by setting `default_hourly_rate` on the project metadata. The engine computes per-iteration costs (effort × rate + fixed costs + risk cost impacts), and `SimulationResults` exposes budget-analysis helpers.

```python
from datetime import date
from mcprojsim.models.project import (
    Project, ProjectMetadata, Task, TaskEstimate, Risk, RiskImpact, ResourceSpec,
)
from mcprojsim.simulation.engine import SimulationEngine

project = Project(
    project=ProjectMetadata(
        name="Payment Gateway",
        start_date=date(2026, 6, 1),
        default_hourly_rate=120.0,
        overhead_rate=0.15,
        currency="USD",
    ),
    tasks=[
        Task(
            id="design",
            name="API Design",
            estimate=TaskEstimate(low=16, expected=24, high=40),
            fixed_cost=2000.0,  # licensing fee
        ),
        Task(
            id="impl",
            name="Implementation",
            estimate=TaskEstimate(low=80, expected=120, high=200),
            dependencies=["design"],
            risks=[
                Risk(
                    id="impl_vendor",
                    name="Vendor API instability",
                    probability=0.25,
                    impact=RiskImpact(type="absolute", value=40, unit="hours"),
                    cost_impact=8000.0,
                ),
            ],
        ),
        Task(
            id="qa",
            name="QA & Certification",
            estimate=TaskEstimate(low=40, expected=60, high=100),
            dependencies=["impl"],
        ),
    ],
    resources=[
        ResourceSpec(name="Alice", hourly_rate=150.0),
        ResourceSpec(name="Bob"),  # uses default_hourly_rate
    ],
)

engine = SimulationEngine(iterations=10_000, random_seed=42)
results = engine.run(project)

# --- Budget queries ---
print(f"Mean cost: ${results.cost_mean:,.0f} {results.currency}")
print(f"P80 cost:  ${results.cost_percentile(80):,.0f}")
print(f"P95 cost:  ${results.cost_percentile(95):,.0f}")

# What budget covers the project 90% of the time?
budget_90 = results.budget_for_confidence(0.90)
print(f"Budget for 90% confidence: ${budget_90:,.0f}")

# Probability of finishing within a $50k budget
prob = results.probability_within_budget(50_000)
print(f"Probability within $50k: {prob*100:.1f}%")

# Joint probability: within budget AND on schedule
joint = results.joint_probability(target_hours=250, target_budget=50_000)
print(f"Joint probability ($50k & 250h): {joint*100:.1f}%")

# --- Cost drivers ---
if results.cost_analysis:
    ca = results.cost_analysis
    print(f"\nCost–duration correlation: {ca.duration_correlation:.3f}")
    for task_id, sens in sorted(
        ca.sensitivity.items(), key=lambda x: abs(x[1]), reverse=True
    ):
        print(f"  {task_id}: cost sensitivity = {sens:.3f}")
```

