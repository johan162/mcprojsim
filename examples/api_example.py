"""Example Python API usage for mcprojsim."""

from mcprojsim import SimulationEngine
from mcprojsim.parsers import YAMLParser
from mcprojsim.exporters import JSONExporter, HTMLExporter
from mcprojsim.config import Config

# Load project
print("Loading project...")
parser = YAMLParser()
project = parser.parse_file("examples/sample_project.yaml")
print(f"Project: {project.project.name}")
print(f"Tasks: {len(project.tasks)}")
print(f"Project risks: {len(project.project_risks)}")

# Load custom configuration (optional)
config = Config.load_from_file("examples/sample_config.yaml")

# Run simulation
print("\nRunning simulation (1000 iterations)...")
engine = SimulationEngine(
    iterations=1000,
    random_seed=42,
    config=config,
    show_progress=False
)
results = engine.run(project)

# Display results
print("\n=== Results ===")
print(f"Mean: {results.mean:.2f} hours")
print(f"Median (P50): {results.median:.2f} hours")
print(f"Std Dev: {results.std_dev:.2f} hours")
print(f"\nConfidence Intervals:")
print(f"  P25: {results.percentile(25):.2f} hours")
print(f"  P50: {results.percentile(50):.2f} hours")
print(f"  P75: {results.percentile(75):.2f} hours")
print(f"  P80: {results.percentile(80):.2f} hours")
print(f"  P90: {results.percentile(90):.2f} hours")
print(f"  P95: {results.percentile(95):.2f} hours")
print(f"  P99: {results.percentile(99):.2f} hours")

# Critical path
print(f"\nCritical Path Analysis:")
critical_path = results.get_critical_path()
for task_id, criticality in sorted(critical_path.items(), key=lambda x: x[1], reverse=True):
    if criticality > 0.5:
        print(f"  {task_id}: {criticality*100:.1f}% critical")

# Delivery dates
print(f"\nDelivery Date Projections:")
for p in [50, 80, 90, 95]:
    hours = results.percentile(p)
    delivery = results.delivery_date(hours)
    if delivery:
        print(f"  P{p}: {delivery.isoformat()} ({results.hours_to_working_days(hours)} working days)")

# Export results
print("\nExporting results...")
JSONExporter.export(results, "api_example_results.json")
HTMLExporter.export(results, "api_example_results.html", project=project, config=config)
print("  ✓ api_example_results.json")
print("  ✓ api_example_results.html")

print("\nDone!")
