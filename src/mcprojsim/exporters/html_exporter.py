"""HTML exporter for simulation results."""

from pathlib import Path

import numpy as np
from jinja2 import Template

from mcprojsim.models.simulation import SimulationResults


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
        }
        .section {
            background: white;
            padding: 20px;
            margin: 20px 0;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
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
            color: white;
            font-size: 11px;
            font-weight: bold;
            text-shadow: 0 0 3px rgba(0,0,0,0.5);
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
            <div class="section">
                <h3>Simulation Parameters</h3>
                <table>
                    <tr><td class="metric">Iterations</td><td class="value">{{ iterations }}</td></tr>
                    <tr><td class="metric">Random Seed</td><td class="value">{{ random_seed }}</td></tr>
                </table>
            </div>

            <div class="section">
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

            <div class="section">
                <h3>Critical Path Analysis</h3>
                <table>
                    <thead>
                        <tr><th>Task ID</th><th>Criticality Index</th><th>Percentage</th></tr>
                    </thead>
                    <tbody>
                        {% for task_id, criticality in critical_path %}
                        <tr>
                            <td>{{ task_id }}</td>
                            <td class="value">{{ "%.4f"|format(criticality) }}</td>
                            <td class="value">{{ "%.1f"|format(criticality * 100) }}%</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
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
                        <div class="thermometer-segment" style="background-color: {{ segment.color }};" title="{{ segment.effort|round(1) }} days: {{ segment.probability|round(1) }}% success">
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
                    <div class="legend-color" style="background-color: #ff0000;"></div>
                    <span>&lt; {{ (red_threshold * 100)|round(0)|int }}% (High Risk)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background-color: #ffaa00;"></div>
                    <span>{{ (red_threshold * 100)|round(0)|int }}% - {{ (green_threshold * 100)|round(0)|int }}% (Medium Risk)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background-color: #00ff00;"></div>
                    <span>&gt; {{ (green_threshold * 100)|round(0)|int }}% (Low Risk)</span>
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
    def export(results: SimulationResults, output_path: Path | str) -> None:
        """Export results to HTML file.

        Args:
            results: Simulation results
            output_path: Path to output file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        template = Template(HTML_TEMPLATE)

        # Prepare data
        cv = results.std_dev / results.mean if results.mean > 0 else 0
        critical_path = sorted(
            results.get_critical_path().items(), key=lambda x: x[1], reverse=True
        )
        percentiles = sorted(results.percentiles.items())

        # Calculate thermometer data
        thermometer_segments = HTMLExporter._calculate_thermometer(results)

        html = template.render(
            project_name=results.project_name,
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
            thermometer_segments=thermometer_segments,
            red_threshold=results.probability_red_threshold,
            green_threshold=results.probability_green_threshold,
        )

        with open(output_path, "w") as f:
            f.write(html)

    @staticmethod
    def _calculate_thermometer(
        results: SimulationResults, num_segments: int = 10
    ) -> list[dict]:
        """Calculate thermometer segments with effort levels and success probabilities.

        Args:
            results: Simulation results
            num_segments: Number of segments in the thermometer

        Returns:
            List of segment dictionaries with effort, probability, and color
        """
        # Create effort bins from min to max duration
        min_effort = results.min_duration
        max_effort = results.max_duration
        effort_bins = np.linspace(min_effort, max_effort, num_segments + 1)

        segments = []
        for i in range(num_segments):
            effort = effort_bins[i + 1]  # Upper bound of the bin

            # Calculate probability of success (completing within this effort)
            probability = np.mean(results.durations <= effort) * 100

            # Calculate color based on probability and thresholds
            color = HTMLExporter._get_probability_color(
                probability / 100,
                results.probability_red_threshold,
                results.probability_green_threshold,
            )

            segments.append(
                {
                    "effort": effort,
                    "probability": probability,
                    "color": color,
                }
            )

        return segments

    @staticmethod
    def _get_probability_color(
        probability: float, red_threshold: float, green_threshold: float
    ) -> str:
        """Get RGB color for a given probability using gradient.

        Args:
            probability: Probability value (0.0 to 1.0)
            red_threshold: Threshold below which is bright red
            green_threshold: Threshold above which is bright green

        Returns:
            RGB color string
        """
        if probability < red_threshold:
            # Below red threshold: bright red
            return "#ff0000"
        elif probability > green_threshold:
            # Above green threshold: bright green
            return "#00ff00"
        else:
            # In between: gradient from red to yellow to green
            # Normalize to 0-1 range within the threshold range
            normalized = (probability - red_threshold) / (
                green_threshold - red_threshold
            )

            # Create gradient: red -> yellow -> green
            if normalized < 0.5:
                # Red to yellow (first half)
                mix = normalized * 2
                r = 255
                g = int(255 * mix)
                b = 0
            else:
                # Yellow to green (second half)
                mix = (normalized - 0.5) * 2
                r = int(255 * (1 - mix))
                g = 255
                b = 0

            return f"#{r:02x}{g:02x}{b:02x}"
