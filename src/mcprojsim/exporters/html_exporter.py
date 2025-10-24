"""HTML exporter for simulation results."""

import base64
from datetime import datetime
from io import BytesIO
from pathlib import Path

import numpy as np
from jinja2 import Template

from mcprojsim.models.simulation import SimulationResults
from mcprojsim.models.project import Project

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ project_name }} - Simulation Results</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        h1, h2 { color: #333; }
        .container {
            display: flex;
            gap: 20px;
            align-items: flex-start;
        }
        .main-content {
            flex: 1;
        }
        .thermometer-container {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            min-width: 300px;
            margin: 20px 0;
            display: flex;
            flex-direction: column;
        }
        .section {
            background: white;
            padding: 20px;
            margin: 20px 0;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .section.simulation-params {
            margin-bottom: 20px;
        }
        .section.statistical-summary {
            margin-top: 0px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #4CAF50;
            color: white;
        }
        tr:hover { background-color: #f5f5f5; }
        .metric { font-weight: bold; }
        .value { text-align: right; }
        .value-center { text-align: center; }
        .header-center { text-align: center; }
        .highlight { background-color: #fff3cd; }
        
        /* Thermometer styles */
        .thermometer {
            margin: 20px 0;
        }
        .thermometer-bar {
            display: flex;
            flex-direction: column-reverse;
            height: 400px;
            width: 60px;
            border: 2px solid #333;
            border-radius: 8px;
            overflow: hidden;
            margin: 0 auto;
        }
        .thermometer-segment {
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 11px;
            font-weight: bold;
            border-top: 1px solid rgba(255,255,255,0.2);
        }
        .thermometer-labels {
            display: flex;
            flex-direction: column-reverse;
            height: 400px;
            margin-left: 10px;
        }
        .thermometer-label {
            flex: 1;
            display: flex;
            align-items: center;
            font-size: 12px;
            padding-left: 5px;
        }
        .thermometer-legend {
            margin-top: 20px;
            font-size: 12px;
        }
        .thermometer-title {
            text-align: center;
            font-weight: bold;
            margin-bottom: 10px;
            font-size: 14px;
        }
        .thermometer-display {
            display: flex;
            align-items: stretch;
            flex: 1;
        }
        .legend-item {
            margin: 5px 0;
            display: flex;
            align-items: center;
        }
        .legend-color {
            width: 20px;
            height: 20px;
            margin-right: 8px;
            border: 1px solid #ccc;
            border-radius: 3px;
        }
    </style>
</head>
<body>
    <h1>Monte Carlo Simulation Results</h1>
    <h2>{{ project_name }}</h2>
    
    <div class="container">
        <div class="main-content">
            <div class="section simulation-params">
                <h3>Simulation Parameters</h3>
                <table>
                    <tr><td class="metric">Simulation Date</td><td class="value">{{ simulation_date }}</td></tr>
                    <tr><td class="metric">Iterations</td><td class="value">{{ iterations }}</td></tr>
                    <tr><td class="metric">Random Seed</td><td class="value">{{ random_seed }}</td></tr>
                </table>
            </div>

            <div class="section statistical-summary">
                <h3>Statistical Summary</h3>
                <table>
                    <tr><td class="metric">Mean</td><td class="value">{{ "%.2f"|format(mean) }} days</td></tr>
                    <tr><td class="metric">Median</td><td class="value">{{ "%.2f"|format(median) }} days</td></tr>
                    <tr><td class="metric">Standard Deviation</td><td class="value">{{ "%.2f"|format(std_dev) }} days</td></tr>
                    <tr><td class="metric">Minimum</td><td class="value">{{ "%.2f"|format(min_duration) }} days</td></tr>
                    <tr><td class="metric">Maximum</td><td class="value">{{ "%.2f"|format(max_duration) }} days</td></tr>
                    <tr><td class="metric">Coefficient of Variation</td><td class="value">{{ "%.4f"|format(cv) }}</td></tr>
                </table>
            </div>

            <div class="section">
                <h3>Confidence Intervals</h3>
                <table>
                    <thead>
                        <tr><th>Percentile</th><th>Duration (days)</th></tr>
                    </thead>
                    <tbody>
                        {% for p, value in percentiles %}
                        <tr class="{% if p in [50, 75, 80, 85, 90, 95] %}highlight{% endif %}">
                            <td>P{{ p }}</td>
                            <td class="value">{{ "%.2f"|format(value) }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>

            {% if histogram_image %}
            <div class="section">
                <h3>Duration Distribution</h3>
                <div style="text-align: center;">
                    <img src="data:image/png;base64,{{ histogram_image }}" alt="Duration Histogram" style="max-width: 100%; height: auto;">
                </div>
            </div>
            {% endif %}

            <div class="section">
                <h3>Critical Path Analysis</h3>
                <table>
                    <thead>
                        <tr><th>Task ID</th><th class="header-center">Effort (days)</th><th class="header-center">Criticality Index</th><th class="header-center">Percentage</th></tr>
                    </thead>
                    <tbody>
                        {% for task_id, criticality, effort in critical_path_with_effort %}
                        <tr>
                            <td>{{ task_id }}</td>
                            <td class="value-center">{{ effort }}</td>
                            <td class="value-center">{{ "%.4f"|format(criticality) }}</td>
                            <td class="value-center">{{ "%.1f"|format(criticality * 100) }}%</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                
                <div style="margin-top: 15px; padding: 12px; background-color: #f8f9fa; border-left: 4px solid #4CAF50; border-radius: 4px;">
                    <p style="margin: 0; font-size: 14px; line-height: 1.5;">
                        <strong>About Criticality Index:</strong> This metric represents the probability that a task lies on the critical path 
                        across all simulation iterations. A value of 1.0 (100%) means the task was always on the critical path, 
                        while 0.0 (0%) means it never was. Tasks with higher criticality indices are more likely to delay the project 
                        if their duration increases.
                    </p>
                </div>
            </div>

            <div class="section">
                <p><em>Report generated by Monte Carlo Project Simulator (mcprojsim)</em></p>
            </div>
        </div>
        
        <div class="thermometer-container">
            <div class="thermometer-title">Probability of Success</div>
            <div class="thermometer">
                <div class="thermometer-display">
                    <div class="thermometer-bar">
                        {% for segment in thermometer_segments %}
                        <div class="thermometer-segment" style="background-color: {{ segment.color }}; color: {{ segment.text_color }};" title="{{ segment.effort|round(1) }} days: {{ segment.probability|round(0)|int }}% success">
                            {{ segment.probability|round(0)|int }}%
                        </div>
                        {% endfor %}
                    </div>
                    <div class="thermometer-labels">
                        {% for segment in thermometer_segments %}
                        <div class="thermometer-label">
                            {{ segment.effort|round(1) }} days
                        </div>
                        {% endfor %}
                    </div>
                </div>
            </div>
            <div class="thermometer-legend">
                <div class="legend-item">
                    <div class="legend-color" style="background-color: #CC6600;"></div>
                    <span>50% (Dark Orange - Higher Risk)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background-color: #996633;"></div>
                    <span>~75% (Medium Risk)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background-color: #006633;"></div>
                    <span>95%+ (Dark Green - Lower Risk)</span>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""


class HTMLExporter:
    """Exporter for HTML format."""

    @staticmethod
    def export(results: SimulationResults, output_path: Path | str, project: Project | None = None) -> None:
        """Export results to HTML file.

        Args:
            results: Simulation results
            output_path: Path to output file
            project: Original project data (optional, for enhanced effort display)
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        template = Template(HTML_TEMPLATE)

        # Prepare data
        cv = results.std_dev / results.mean if results.mean > 0 else 0
        critical_path = sorted(
            results.get_critical_path().items(), key=lambda x: x[1], reverse=True
        )
        
        # Calculate critical path with effort data
        critical_path_with_effort = []
        for task_id, criticality in critical_path:
            # Get original task estimate if project data is available
            effort_display = HTMLExporter._format_effort_display(task_id, results, project)
            critical_path_with_effort.append((task_id, criticality, effort_display))
        
        percentiles = sorted(results.percentiles.items())

        # Calculate thermometer data
        thermometer_segments = HTMLExporter._calculate_thermometer(results)

        # Generate histogram image
        histogram_image = HTMLExporter._generate_histogram_image(results)

        # Get current date and time for simulation timestamp
        simulation_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        html = template.render(
            project_name=results.project_name,
            simulation_date=simulation_date,
            iterations=results.iterations,
            random_seed=results.random_seed or "None",
            mean=results.mean,
            median=results.median,
            std_dev=results.std_dev,
            min_duration=results.min_duration,
            max_duration=results.max_duration,
            cv=cv,
            percentiles=percentiles,
            critical_path=critical_path,
            critical_path_with_effort=critical_path_with_effort,
            thermometer_segments=thermometer_segments,
            histogram_image=histogram_image,
        )

        with open(output_path, "w") as f:
            f.write(html)

    @staticmethod
    def _calculate_thermometer(
        results: SimulationResults, num_segments: int = 11
    ) -> list[dict]:
        """Calculate thermometer segments with fixed probability bins.

        Args:
            results: Simulation results
            num_segments: Number of segments in the thermometer (ignored, fixed at 11)

        Returns:
            List of segment dictionaries with effort, probability, and color
        """
        # Fixed probability bins: 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 99
        probability_bins = [50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 99]
        
        segments = []
        for prob_target in probability_bins:
            # Find the effort level that corresponds to this probability
            # This is the percentile that gives us this success probability
            percentile = prob_target
            if percentile in results.percentiles:
                effort = results.percentiles[percentile]
            else:
                # Interpolate if exact percentile not available
                available_percentiles = sorted(results.percentiles.keys())
                if percentile < min(available_percentiles):
                    effort = results.min_duration
                elif percentile > max(available_percentiles):
                    effort = results.max_duration
                else:
                    # Linear interpolation
                    lower_p = max(p for p in available_percentiles if p < percentile)
                    upper_p = min(p for p in available_percentiles if p > percentile)
                    lower_effort = results.percentiles[lower_p]
                    upper_effort = results.percentiles[upper_p]
                    effort = lower_effort + (upper_effort - lower_effort) * (percentile - lower_p) / (upper_p - lower_p)

            # Calculate color and text color based on probability
            color, text_color = HTMLExporter._get_probability_color_and_text(prob_target)

            segments.append(
                {
                    "effort": effort,
                    "probability": prob_target,
                    "color": color,
                    "text_color": text_color,
                }
            )

        return segments

    @staticmethod
    def _get_probability_color_and_text(probability: float) -> tuple[str, str]:
        """Get RGB color and text color for a given probability percentage.

        Creates a gradient from dark orange (50%) to dark green (>95%).

        Args:
            probability: Probability percentage (50.0 to 99.0)

        Returns:
            Tuple of (background_color, text_color) as RGB strings
        """
        # Clamp probability to our range
        prob = max(50.0, min(99.0, probability))
        
        # Normalize to 0-1 range (50% = 0, 99% = 1)
        normalized = (prob - 50.0) / (99.0 - 50.0)
        
        # Create gradient from dark orange to dark green
        # Dark orange: RGB(204, 102, 0) = #CC6600
        # Dark green: RGB(0, 102, 51) = #006633
        
        start_r, start_g, start_b = 204, 102, 0   # Dark orange
        end_r, end_g, end_b = 0, 102, 51          # Dark green
        
        # Interpolate colors
        r = int(start_r + (end_r - start_r) * normalized)
        g = int(start_g + (end_g - start_g) * normalized)
        b = int(start_b + (end_b - start_b) * normalized)
        
        background_color = f"#{r:02x}{g:02x}{b:02x}"
        
        # Determine text color based on brightness
        # Calculate perceived brightness using the luminance formula
        brightness = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        
        # Use black text for bright colors, white text for dark colors
        text_color = "#000000" if brightness > 0.5 else "#ffffff"
        
        return background_color, text_color

    @staticmethod
    def _format_effort_display(task_id: str, results: SimulationResults, project: Project | None) -> str:
        """Format the effort display for a task.

        Args:
            task_id: Task identifier
            results: Simulation results
            project: Original project data (optional)

        Returns:
            Formatted effort string
        """
        if project is None:
            # Fallback to mean simulated effort if no project data
            if task_id in results.task_durations:
                mean_effort = float(np.mean(results.task_durations[task_id]))
                return f"{mean_effort:.2f}"
            else:
                return "N/A"

        # Find the task in the original project
        task = None
        for t in project.tasks:
            if t.id == task_id:
                task = t
                break

        if task is None:
            # Task not found, fallback to mean simulated effort
            if task_id in results.task_durations:
                mean_effort = float(np.mean(results.task_durations[task_id]))
                return f"{mean_effort:.2f}"
            else:
                return "N/A"

        # Check if it's a T-shirt size estimate
        if hasattr(task.estimate, 't_shirt_size') and task.estimate.t_shirt_size:
            # T-shirt size format: "M (2, 5, 8)"
            t_shirt = task.estimate.t_shirt_size
            
            # Use the default T-shirt size mappings from the system
            tshirt_mappings = {
                "XS": (0.5, 1, 2),
                "S": (1, 2, 4),
                "M": (3, 5, 8),
                "L": (5, 8, 13),
                "XL": (8, 13, 21),
                "XXL": (13, 21, 34)
            }
            
            if t_shirt in tshirt_mappings:
                low, nominal, high = tshirt_mappings[t_shirt]
                return f"{t_shirt} ({low}, {nominal}, {high})"
            else:
                return f"{t_shirt} (unknown)"
        
        # Check if it's a triangular distribution (min, most_likely, max)
        elif hasattr(task.estimate, 'min') and hasattr(task.estimate, 'most_likely') and hasattr(task.estimate, 'max'):
            if task.estimate.min is not None and task.estimate.most_likely is not None and task.estimate.max is not None:
                return f"({task.estimate.min}, {task.estimate.most_likely}, {task.estimate.max})"
        
        # Fallback to mean simulated effort
        if task_id in results.task_durations:
            mean_effort = float(np.mean(results.task_durations[task_id]))
            return f"{mean_effort:.2f}"
        else:
            return "N/A"

    @staticmethod
    def _generate_histogram_image(results: SimulationResults) -> str:
        """Generate a base64-encoded histogram image.

        Args:
            results: Simulation results

        Returns:
            Base64-encoded PNG image string, or empty string if matplotlib unavailable
        """
        if not MATPLOTLIB_AVAILABLE:
            return ""

        try:
            import matplotlib.pyplot as plt
            # Get histogram data
            bin_edges, counts = results.get_histogram_data(bins=50)
            bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

            # Create figure with nice styling
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # Plot histogram as bars
            ax.bar(
                bin_centers,
                counts,
                width=np.diff(bin_edges),
                color='#4CAF50',
                alpha=0.7,
                edgecolor='#2E7D32',
                linewidth=1.5,
            )

            # Add mean and median lines
            ax.axvline(
                results.mean,
                color='#FF5722',
                linestyle='--',
                linewidth=2,
                label=f'Mean: {results.mean:.1f} days',
            )
            ax.axvline(
                results.median,
                color='#2196F3',
                linestyle='--',
                linewidth=2,
                label=f'Median: {results.median:.1f} days',
            )

            # Add percentile lines
            for p in [80, 90, 95]:
                if p in results.percentiles:
                    ax.axvline(
                        results.percentiles[p],
                        color='#9E9E9E',
                        linestyle=':',
                        linewidth=1.5,
                        alpha=0.7,
                        label=f'P{p}: {results.percentiles[p]:.1f} days',
                    )

            # Styling
            ax.set_xlabel('Duration (days)', fontsize=12, fontweight='bold')
            ax.set_ylabel('Frequency', fontsize=12, fontweight='bold')
            ax.set_title(
                f'Project Duration Distribution ({results.iterations:,} simulations)',
                fontsize=14,
                fontweight='bold',
                pad=20,
            )
            ax.legend(loc='upper right', framealpha=0.9, fontsize=10)
            ax.grid(True, alpha=0.3, linestyle='--')
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)

            # Tight layout
            plt.tight_layout()

            # Save to BytesIO
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
            plt.close(fig)
            buffer.seek(0)

            # Encode to base64
            img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
            return img_base64

        except Exception:
            # If anything goes wrong, return empty string
            return ""
