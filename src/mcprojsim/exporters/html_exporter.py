"""HTML exporter for simulation results."""

import base64
import math
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, TYPE_CHECKING

import numpy as np
from jinja2 import Template

from mcprojsim.analysis.staffing import StaffingAnalyzer
from mcprojsim.config import Config
from mcprojsim.config import DEFAULT_CONFIDENCE_LEVELS
from mcprojsim.models.simulation import SimulationResults
from mcprojsim.models.project import Project

if TYPE_CHECKING:
    import matplotlib.pyplot as plt

try:
    import matplotlib

    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.pyplot as plt  # noqa: F811

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False  # pyright: ignore[reportConstantRedefinition]


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
        .thermometer-row {
            display: flex;
            gap: 20px;
            align-items: flex-start;
            margin: 20px 0;
        }
        .thermometer-container {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            flex: 1;
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
        .stats-row {
            display: flex;
            gap: 20px;
            align-items: flex-start;
            margin: 20px 0;
        }
        .stats-row .section {
            flex: 1;
            margin: 0;
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
            font-size: 18px;
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
            font-size: 21px;
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
        .staffing-rec-marker {
            font-weight: bold;
            color: #2E7D32;
        }
        .staffing-meta {
            margin: 10px 0 0 0;
            font-size: 14px;
            color: #555;
        }
    </style>
</head>
<body>
    <h1>Monte Carlo Simulation Results</h1>
    <h2>{{ project_name }}</h2>

    <div class="section simulation-params">
        <h3>Simulation Parameters</h3>
        <table>
            <tr><td class="metric">Simulation Date</td><td class="value">{{ simulation_date }}</td></tr>
            <tr><td class="metric">Iterations</td><td class="value">{{ iterations }}</td></tr>
            <tr><td class="metric">Random Seed</td><td class="value">{{ random_seed }}</td></tr>
            <tr><td class="metric">Hours per Day</td><td class="value">{{ hours_per_day }}</td></tr>
        </table>
    </div>

    <div class="thermometer-row">
        <div class="thermometer-container">
            <div class="thermometer-title">Calendar Time Probability of Success</div>
            <div class="thermometer">
                <div class="thermometer-display">
                    <div class="thermometer-bar">
                        {% for segment in thermometer_segments %}
                        <div class="thermometer-segment" style="background-color: {{ segment.color }}; color: {{ segment.text_color }};" title="{{ segment.effort|round(0)|int }} hours: {{ segment.probability|round(0)|int }}% success">
                            {{ segment.probability|round(0)|int }}%
                        </div>
                        {% endfor %}
                    </div>
                    <div class="thermometer-labels">
                        {% for segment in thermometer_segments %}
                        <div class="thermometer-label">
                            {% if segment.delivery_date %}{{ segment.delivery_date }}, {% endif %}{{ segment.working_days }} days, ({{ segment.effort|round(0)|int }}h)
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
            <div style="margin-top: 15px; padding: 12px; background-color: #f8f9fa; border-left: 4px solid #2196F3; border-radius: 4px;">
                <p style="margin: 0; font-size: 14px; line-height: 1.5;">
                    <strong>Note:</strong> Calendar time assumes that all resources required for maximum parallelism
                    are available (Max Parallel Tasks: {{ max_parallel_tasks }}).
                </p>
            </div>
        </div>

        {% if effort_thermometer_segments %}
        <div class="thermometer-container">
            <div class="thermometer-title">Project Effort Probability of Success</div>
            <div class="thermometer">
                <div class="thermometer-display">
                    <div class="thermometer-bar">
                        {% for segment in effort_thermometer_segments %}
                        <div class="thermometer-segment" style="background-color: {{ segment.color }}; color: {{ segment.text_color }};" title="{{ segment.effort|round(0)|int }} person-hours: {{ segment.probability|round(0)|int }}% success">
                            {{ segment.probability|round(0)|int }}%
                        </div>
                        {% endfor %}
                    </div>
                    <div class="thermometer-labels">
                        {% for segment in effort_thermometer_segments %}
                        <div class="thermometer-label">
                            {{ segment.person_days }} man-days, ({{ segment.effort|round(0)|int }}h)
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
        {% endif %}
    </div>

    <div class="stats-row">
        <div class="section statistical-summary">
            <h3>Calendar Time Statistical Summary</h3>
            <table>
                <tr><td class="metric">Mean</td><td class="value">{{ mean|round(0)|int }} hours ({{ mean_working_days }} working days)</td></tr>
                <tr><td class="metric">Median</td><td class="value">{{ median|round(0)|int }} hours</td></tr>
                <tr><td class="metric">Standard Deviation</td><td class="value">{{ std_dev|round(0)|int }} hours</td></tr>
                <tr><td class="metric">Minimum</td><td class="value">{{ min_duration|round(0)|int }} hours</td></tr>
                <tr><td class="metric">Maximum</td><td class="value">{{ max_duration|round(0)|int }} hours</td></tr>
                <tr><td class="metric">Coefficient of Variation</td><td class="value">{{ "%.4f"|format(cv) }}</td></tr>
                <tr><td class="metric">Skewness</td><td class="value">{{ "%.4f"|format(skewness) }}</td></tr>
                <tr><td class="metric">Excess Kurtosis</td><td class="value">{{ "%.4f"|format(kurtosis) }}</td></tr>
                <tr><td class="metric">Max Parallel Tasks</td><td class="value">{{ max_parallel_tasks }}</td></tr>
            </table>
        </div>

        {% if effort_stats %}
        <div class="section statistical-summary">
            <h3>Project Effort Statistical Summary</h3>
            <table>
                <tr><td class="metric">Mean</td><td class="value">{{ effort_stats.mean|round(0)|int }} person-hours ({{ effort_stats.mean_working_days }} person-days)</td></tr>
                <tr><td class="metric">Median</td><td class="value">{{ effort_stats.median|round(0)|int }} person-hours</td></tr>
                <tr><td class="metric">Standard Deviation</td><td class="value">{{ effort_stats.std_dev|round(0)|int }} person-hours</td></tr>
                <tr><td class="metric">Minimum</td><td class="value">{{ effort_stats.min_val|round(0)|int }} person-hours</td></tr>
                <tr><td class="metric">Maximum</td><td class="value">{{ effort_stats.max_val|round(0)|int }} person-hours</td></tr>
                <tr><td class="metric">Coefficient of Variation</td><td class="value">{{ "%.4f"|format(effort_stats.cv) }}</td></tr>
                <tr><td class="metric">Skewness</td><td class="value">{{ "%.4f"|format(effort_stats.skewness) }}</td></tr>
                <tr><td class="metric">Excess Kurtosis</td><td class="value">{{ "%.4f"|format(effort_stats.kurtosis) }}</td></tr>
            </table>
        </div>
        {% endif %}
    </div>

    <div style="margin-top: 0; padding: 12px; background-color: #f8f9fa; border-left: 4px solid #2196F3; border-radius: 4px;">
        <p style="margin: 0; font-size: 14px; line-height: 1.5;">
            <strong>About these metrics:</strong><br> <strong>Coefficient of Variation</strong> is relative spread
            (standard deviation divided by mean); higher values mean more uncertainty relative to the expected duration.
            <br><strong>Skewness</strong> shows whether the distribution has a longer tail on the high side or low side;
            positive skew often means more risk of overruns than the mean alone suggests. <br><strong>Excess Kurtosis</strong>
            indicates tail heaviness and outlier-proneness; higher positive values mean more extreme outcomes may occur
            than in a normal distribution. <br><strong>Max Parallel Tasks</strong> is the peak number of tasks that can run at
            the same time in the schedule logic; watch out because achieving the calendar-time results may require enough
            people and skills to support that level of parallel execution.
            <br><strong>Project effort</strong> measures total person-hours across all tasks regardless of parallelism.
            Compare with calendar time to gauge how much work is happening concurrently.
        </p>
    </div>

    <div class="section">
        <h3>Calendar Time Confidence Intervals</h3>
        <table>
            <thead>
                <tr><th>Percentile</th><th>Hours</th><th>Working Days</th><th>Delivery Date</th></tr>
            </thead>
            <tbody>
                {% for p, value, working_days, delivery_date in percentiles %}
                <tr class="{% if p in highlighted_percentiles %}highlight{% endif %}">
                    <td>P{{ p }}</td>
                    <td class="value">{{ "%.2f"|format(value) }}</td>
                    <td class="value">{{ working_days }}</td>
                    <td class="value">{{ delivery_date }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    {% if effort_percentiles %}
    <div class="section">
        <h3>Effort Confidence Intervals</h3>
        <table>
            <thead>
                <tr><th>Percentile</th><th>Person-Hours</th><th>Person-Days</th></tr>
            </thead>
            <tbody>
                {% for p, person_hours, person_days in effort_percentiles %}
                <tr class="{% if p in highlighted_percentiles %}highlight{% endif %}">
                    <td>P{{ p }}</td>
                    <td class="value">{{ "%.2f"|format(person_hours) }}</td>
                    <td class="value">{{ person_days }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if histogram_image %}
    <div class="section">
        <h3>Calendar Time Distribution</h3>
        <div style="text-align: center;">
            <img src="data:image/png;base64,{{ histogram_image }}" alt="Calendar Time Distribution" style="max-width: 100%; height: auto;">
        </div>
    </div>
    {% endif %}

    {% if effort_histogram_image %}
    <div class="section">
        <h3>Project Effort Distribution</h3>
        <div style="text-align: center;">
            <img src="data:image/png;base64,{{ effort_histogram_image }}" alt="Project Effort Distribution" style="max-width: 100%; height: auto;">
        </div>
    </div>
    {% endif %}

    {% if sensitivity_image %}
    <div class="section">
        <h3>Sensitivity Analysis (Tornado Chart)</h3>
        <div style="text-align: center;">
            <img src="data:image/png;base64,{{ sensitivity_image }}" alt="Sensitivity Tornado Chart" style="max-width: 100%; height: auto;">
        </div>
        <div style="margin-top: 15px; padding: 12px; background-color: #f8f9fa; border-left: 4px solid #2196F3; border-radius: 4px;">
            <p style="margin: 0; font-size: 14px; line-height: 1.5;">
                <strong>About Sensitivity Analysis:</strong> Spearman rank correlation between each task's
                sampled duration and the total project duration. Higher absolute values indicate tasks
                whose duration variability has the greatest influence on project schedule uncertainty.
            </p>
        </div>
    </div>
    {% endif %}

    {% if schedule_slack %}
    <div class="section">
        <h3>Schedule Slack (Total Float)</h3>
        <table>
            <thead>
                <tr><th>Task ID</th><th class="header-center">Mean Slack (hours)</th><th class="header-center">Status</th></tr>
            </thead>
            <tbody>
                {% for task_id, slack_val in schedule_slack %}
                <tr>
                    <td>{{ task_id }}</td>
                    <td class="value-center">{{ "%.2f"|format(slack_val) }}</td>
                    <td class="value-center">{% if slack_val < 0.01 %}Critical{% else %}{{ "%.1f"|format(slack_val) }}h buffer{% endif %}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        <div style="margin-top: 15px; padding: 12px; background-color: #f8f9fa; border-left: 4px solid #FF9800; border-radius: 4px;">
            <p style="margin: 0; font-size: 14px; line-height: 1.5;">
                <strong>About Schedule Slack:</strong> Mean total float across all simulation iterations.
                Tasks with zero slack are on the critical path and any delay will extend the project.
                Tasks with positive slack have schedule buffer.
            </p>
        </div>
    </div>
    {% endif %}

    {% if risk_impact_data %}
    <div class="section">
        <h3>Risk Impact Analysis</h3>
        <table>
            <thead>
                <tr><th>Task ID</th><th class="header-center">Mean Impact (hours)</th><th class="header-center">Trigger Rate</th><th class="header-center">Mean When Triggered (hours)</th></tr>
            </thead>
            <tbody>
                {% for task_id, mean_impact, trigger_rate, mean_when_triggered in risk_impact_data %}
                <tr>
                    <td>{{ task_id }}</td>
                    <td class="value-center">{{ "%.2f"|format(mean_impact) }}</td>
                    <td class="value-center">{{ "%.1f"|format(trigger_rate * 100) }}%</td>
                    <td class="value-center">{{ "%.2f"|format(mean_when_triggered) }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    <div class="section">
        <h3>Critical Path Analysis</h3>
        <table>
            <thead>
                <tr><th>Task ID</th><th class="header-center">Effort (hours)</th><th class="header-center">Criticality Index</th><th class="header-center">Percentage</th></tr>
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

        {% if critical_path_sequences %}
        <h4>Most Frequent Critical Paths</h4>
        <table>
            <thead>
                <tr><th>Rank</th><th>Path</th><th class="header-center">Count</th><th class="header-center">Frequency</th><th class="header-center">Percentage</th></tr>
            </thead>
            <tbody>
                {% for rank, path_display, count, frequency in critical_path_sequences %}
                <tr>
                    <td class="value-center">{{ rank }}</td>
                    <td>{{ path_display }}</td>
                    <td class="value-center">{{ count }}</td>
                    <td class="value-center">{{ "%.4f"|format(frequency) }}</td>
                    <td class="value-center">{{ "%.1f"|format(frequency * 100) }}%</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% endif %}

        <div style="margin-top: 15px; padding: 12px; background-color: #f8f9fa; border-left: 4px solid #4CAF50; border-radius: 4px;">
            <p style="margin: 0; font-size: 14px; line-height: 1.5;">
                <strong>About Criticality Index:</strong> This metric represents the probability that a task lies on the critical path
                across all simulation iterations. A value of 1.0 (100%) means the task was always on the critical path,
                while 0.0 (0%) means it never was. Tasks with higher criticality indices are more likely to delay the project
                if their duration increases.
            </p>
        </div>
    </div>

    {% if staffing_recommendations %}
    <div class="section">
        <h3>Staffing Analysis</h3>
        <p class="staffing-meta">
            Effort basis: <strong>{{ staffing_effort_basis }}</strong>
            ({{ "%.0f"|format(staffing_effort_hours_used) }} person-hours,
            {{ "%.0f"|format(staffing_cp_hours) }} critical-path hours)
            | Max parallel tasks: {{ max_parallel_tasks }}
        </p>

        <h4>Recommended Team Size</h4>
        <table>
            <thead>
                <tr><th>Profile</th><th class="header-center">Team Size</th><th class="header-center">Working Days</th><th class="header-center">Delivery Date</th><th class="header-center">Efficiency</th><th class="header-center">Parallelism Ratio</th></tr>
            </thead>
            <tbody>
                {% for rec in staffing_recommendations %}
                <tr>
                    <td>{{ rec.profile }}</td>
                    <td class="value-center">{{ rec.recommended_team_size }}</td>
                    <td class="value-center">{{ rec.calendar_working_days }}</td>
                    <td class="value-center">{{ rec.delivery_date if rec.delivery_date else "" }}</td>
                    <td class="value-center">{{ "%.1f"|format(rec.efficiency * 100) }}%</td>
                    <td class="value-center">{{ "%.1f"|format(rec.parallelism_ratio) }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>

        {% for prof_name, prof_rows in staffing_table_by_profile %}
        <h4>{{ prof_name }} team</h4>
        <table>
            <thead>
                <tr><th class="header-center">Team Size</th><th class="header-center">Eff. Capacity</th><th class="header-center">Working Days</th><th class="header-center">Delivery Date</th><th class="header-center">Efficiency</th></tr>
            </thead>
            <tbody>
                {% for row in prof_rows %}
                <tr>
                    <td class="value-center">{% if row.is_recommended %}<span class="staffing-rec-marker">{{ row.team_size }} ★</span>{% else %}{{ row.team_size }}{% endif %}</td>
                    <td class="value-center">{{ "%.2f"|format(row.effective_capacity) }}</td>
                    <td class="value-center">{{ row.calendar_working_days }}</td>
                    <td class="value-center">{{ row.delivery_date if row.delivery_date else "" }}</td>
                    <td class="value-center">{{ "%.1f"|format(row.efficiency * 100) }}%</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% endfor %}

        <div style="margin-top: 15px; padding: 12px; background-color: #f8f9fa; border-left: 4px solid #9C27B0; border-radius: 4px;">
            <p style="margin: 0; font-size: 14px; line-height: 1.5;">
                <strong>About Staffing Analysis:</strong> Team-size recommendations use a
                Brooks's-Law communication-overhead model. <em>Eff. Capacity</em> is the
                number of person-equivalents after accounting for overhead.
                <em>Efficiency</em> is effective capacity divided by nominal team size.
                The ★ marker indicates the recommended team size for each profile.
            </p>
        </div>
    </div>
    {% endif %}

    <div class="section">
        <p><em>Report generated by Monte Carlo Project Simulator (mcprojsim)</em></p>
    </div>
</body>
</html>
"""


class HTMLExporter:
    """Exporter for HTML format."""

    @staticmethod
    def export(
        results: SimulationResults,
        output_path: Path | str,
        project: Project | None = None,
        config: Config | None = None,
        critical_path_limit: int | None = None,
    ) -> None:
        """Export results to HTML file.

        Args:
            results: Simulation results
            output_path: Path to output file
            project: Original project data (optional, for enhanced effort display)
            config: Active simulation configuration (optional, for T-shirt sizing display)
            critical_path_limit: Maximum number of critical path sequences to include
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        template = Template(HTML_TEMPLATE)
        effective_config = config if config is not None else Config.get_default()
        report_limit = (
            critical_path_limit or effective_config.output.critical_path_report_limit
        )

        # Prepare data
        cv = results.std_dev / results.mean if results.mean > 0 else 0
        critical_path = sorted(
            results.get_critical_path().items(), key=lambda x: x[1], reverse=True
        )

        # Calculate critical path with effort data
        critical_path_with_effort = []
        for task_id, criticality in critical_path:
            # Get original task estimate if project data is available
            effort_display = HTMLExporter._format_effort_display(
                task_id, results, project, config
            )
            critical_path_with_effort.append((task_id, criticality, effort_display))

        critical_path_sequences = [
            (index, record.format_path(), record.count, record.frequency)
            for index, record in enumerate(
                results.get_critical_path_sequences(report_limit),
                start=1,
            )
        ]

        percentiles = [
            (
                p,
                v,
                math.ceil(v / results.hours_per_day),
                (
                    dd.isoformat()
                    if (dd := results.delivery_date(v)) is not None
                    else ""
                ),
            )
            for p, v in sorted(results.percentiles.items())
        ]

        # Calculate thermometer data
        thermometer_segments = HTMLExporter._calculate_thermometer(results)

        # Generate histogram images
        histogram_image = HTMLExporter._generate_histogram_image(results)
        effort_histogram_image = HTMLExporter._generate_effort_histogram_image(results)

        # Generate sensitivity tornado chart
        sensitivity_image = HTMLExporter._generate_sensitivity_image(results)

        # Prepare schedule slack data (sorted by slack ascending)
        schedule_slack = (
            sorted(results.task_slack.items(), key=lambda x: x[1])
            if results.task_slack
            else []
        )

        # Prepare risk impact data (only tasks with triggered risks)
        risk_summary = results.get_risk_impact_summary()
        risk_impact_data = [
            (task_id, s["mean_impact"], s["trigger_rate"], s["mean_when_triggered"])
            for task_id, s in sorted(risk_summary.items())
            if s["trigger_rate"] > 0
        ]

        # Get current date and time for simulation timestamp
        simulation_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        html = template.render(
            project_name=results.project_name,
            simulation_date=simulation_date,
            iterations=results.iterations,
            random_seed=results.random_seed or "None",
            hours_per_day=results.hours_per_day,
            mean=results.mean,
            mean_working_days=math.ceil(results.mean / results.hours_per_day),
            median=results.median,
            std_dev=results.std_dev,
            min_duration=results.min_duration,
            max_duration=results.max_duration,
            cv=cv,
            skewness=results.skewness,
            kurtosis=results.kurtosis,
            percentiles=percentiles,
            effort_percentiles=[
                (
                    p,
                    v,
                    math.ceil(v / results.hours_per_day),
                )
                for p, v in sorted(results.effort_percentiles.items())
            ],
            highlighted_percentiles=DEFAULT_CONFIDENCE_LEVELS,
            critical_path=critical_path,
            critical_path_with_effort=critical_path_with_effort,
            critical_path_sequences=critical_path_sequences,
            thermometer_segments=thermometer_segments,
            effort_thermometer_segments=HTMLExporter._calculate_effort_thermometer(
                results
            ),
            histogram_image=histogram_image,
            effort_histogram_image=effort_histogram_image,
            sensitivity_image=sensitivity_image,
            schedule_slack=schedule_slack,
            risk_impact_data=risk_impact_data,
            max_parallel_tasks=results.max_parallel_tasks,
            effort_stats=HTMLExporter._compute_effort_stats(results),
            **HTMLExporter._prepare_staffing_context(results, effective_config),
        )

        with open(output_path, "w") as f:
            f.write(html)

    @staticmethod
    def _compute_effort_stats(
        results: SimulationResults,
    ) -> dict[str, Any] | None:
        """Compute descriptive statistics for total project effort.

        Returns a dict with mean, median, std_dev, min_val, max_val, cv,
        skewness, kurtosis and mean_working_days, or ``None`` when no
        per-iteration effort data is available.
        """
        if len(results.effort_durations) == 0:
            return None

        from scipy import stats as scipy_stats

        effort = results.effort_durations
        mean = float(np.mean(effort))
        std_dev = float(np.std(effort))
        return {
            "mean": mean,
            "median": float(np.median(effort)),
            "std_dev": std_dev,
            "min_val": float(np.min(effort)),
            "max_val": float(np.max(effort)),
            "cv": std_dev / mean if mean > 0 else 0.0,
            "skewness": float(scipy_stats.skew(effort)) if std_dev > 0 else 0.0,
            "kurtosis": float(scipy_stats.kurtosis(effort)) if std_dev > 0 else 0.0,
            "mean_working_days": math.ceil(mean / results.hours_per_day),
        }

    @staticmethod
    def _prepare_staffing_context(
        results: SimulationResults,
        config: Config,
    ) -> dict[str, Any]:
        """Build the template context dict for the staffing section.

        Returns keys: staffing_recommendations, staffing_table_by_profile,
        staffing_effort_basis, staffing_effort_hours_used, staffing_cp_hours.
        """
        recommendations = StaffingAnalyzer.recommend_team_size(results, config)
        if not recommendations:
            return {
                "staffing_recommendations": [],
                "staffing_table_by_profile": [],
                "staffing_effort_basis": "mean",
                "staffing_effort_hours_used": results.total_effort_hours(),
                "staffing_cp_hours": 0.0,
            }

        effort_basis = recommendations[0].effort_basis
        basis_label = (
            f"{effort_basis} effort"
            if effort_basis == "mean"
            else f"{effort_basis} effort percentile"
        )
        effort_hours_used = recommendations[0].total_effort_hours
        cp_hours = recommendations[0].critical_path_hours

        # Build per-profile tables with a recommended marker
        table_rows = StaffingAnalyzer.calculate_staffing_table(results, config)
        rec_sizes: dict[str, int] = {
            r.profile: r.recommended_team_size for r in recommendations
        }
        profiles_sorted = sorted({r.profile for r in recommendations})
        table_by_profile: list[tuple[str, list[dict[str, Any]]]] = []
        for prof in profiles_sorted:
            prof_rows = [r for r in table_rows if r.profile == prof]
            rec_n = rec_sizes.get(prof, 0)
            enriched = []
            for r in prof_rows:
                enriched.append(
                    {
                        "team_size": r.team_size,
                        "effective_capacity": r.effective_capacity,
                        "calendar_working_days": r.calendar_working_days,
                        "delivery_date": (
                            r.delivery_date.isoformat() if r.delivery_date else ""
                        ),
                        "efficiency": r.efficiency,
                        "is_recommended": r.team_size == rec_n,
                    }
                )
            table_by_profile.append((prof, enriched))

        return {
            "staffing_recommendations": recommendations,
            "staffing_table_by_profile": table_by_profile,
            "staffing_effort_basis": basis_label,
            "staffing_effort_hours_used": effort_hours_used,
            "staffing_cp_hours": cp_hours,
        }

    @staticmethod
    def _calculate_thermometer(
        results: SimulationResults, num_segments: int = 11
    ) -> list[dict[str, Any]]:
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
                    effort = lower_effort + (upper_effort - lower_effort) * (
                        percentile - lower_p
                    ) / (upper_p - lower_p)

            # Calculate color and text color based on probability
            color, text_color = HTMLExporter._get_probability_color_and_text(
                prob_target
            )

            working_days = math.ceil(effort / results.hours_per_day)
            dd = results.delivery_date(effort)
            segments.append(
                {
                    "effort": effort,
                    "probability": prob_target,
                    "color": color,
                    "text_color": text_color,
                    "working_days": working_days,
                    "delivery_date": dd.isoformat() if dd else "",
                }
            )

        return segments

    @staticmethod
    def _calculate_effort_thermometer(
        results: SimulationResults,
    ) -> list[dict[str, Any]]:
        """Calculate thermometer segments for total project effort.

        Uses ``effort_percentiles`` (person-hours) when per-iteration effort
        data is available. Returns an empty list otherwise so the template
        can skip rendering.
        """
        if len(results.effort_durations) == 0:
            return []

        probability_bins = [50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 99]
        segments: list[dict[str, Any]] = []

        for prob_target in probability_bins:
            # Ensure the percentile is computed
            effort = results.effort_percentile(prob_target)

            color, text_color = HTMLExporter._get_probability_color_and_text(
                prob_target
            )

            person_days = math.ceil(effort / results.hours_per_day)
            segments.append(
                {
                    "effort": effort,
                    "probability": prob_target,
                    "color": color,
                    "text_color": text_color,
                    "person_days": person_days,
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

        start_r, start_g, start_b = 204, 102, 0  # Dark orange
        end_r, end_g, end_b = 0, 102, 51  # Dark green

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
    def _format_effort_display(
        task_id: str,
        results: SimulationResults,
        project: Project | None,
        config: Config | None,
    ) -> str:
        """Format the effort display for a task.

        Args:
            task_id: Task identifier
            results: Simulation results
            project: Original project data (optional)
            config: Active simulation configuration (optional)

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

        effective_config = config if config is not None else Config.get_default()

        # Check if it's a T-shirt size estimate
        if hasattr(task.estimate, "t_shirt_size") and task.estimate.t_shirt_size:
            # T-shirt size format: "M (2, 5, 8)"
            t_shirt = task.estimate.t_shirt_size

            size_config = effective_config.get_t_shirt_size(t_shirt)
            if size_config is not None:
                return (
                    f"{t_shirt} ({size_config.min}, "
                    f"{size_config.most_likely}, {size_config.max})"
                )
            return f"{t_shirt} (unknown)"

        # Check if it's a Story Point estimate
        if hasattr(task.estimate, "story_points") and task.estimate.story_points:
            story_points = task.estimate.story_points

            points_config = effective_config.get_story_point(story_points)
            if points_config is not None:
                return (
                    f"SP {story_points} ({points_config.min}, "
                    f"{points_config.most_likely}, {points_config.max})"
                )
            return f"SP {story_points} (unknown)"

        # Check if it's a triangular distribution (min, most_likely, max)
        elif (
            hasattr(task.estimate, "min")
            and hasattr(task.estimate, "most_likely")
            and hasattr(task.estimate, "max")
        ):
            if (
                task.estimate.min is not None
                and task.estimate.most_likely is not None
                and task.estimate.max is not None
            ):
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
            # matplotlib.pyplot is already imported at module level as plt
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
                color="#4CAF50",
                alpha=0.7,
                edgecolor="#2E7D32",
                linewidth=1.5,
            )

            # Add mean and median lines
            ax.axvline(
                results.mean,
                color="#FF5722",
                linestyle="--",
                linewidth=2,
                label=f"Mean: {results.mean:.1f} hours",
            )
            ax.axvline(
                results.median,
                color="#2196F3",
                linestyle="--",
                linewidth=2,
                label=f"Median: {results.median:.1f} hours",
            )

            # Add percentile lines
            for p in [80, 90, 95]:
                if p in results.percentiles:
                    ax.axvline(
                        results.percentiles[p],
                        color="#9E9E9E",
                        linestyle=":",
                        linewidth=1.5,
                        alpha=0.7,
                        label=f"P{p}: {results.percentiles[p]:.1f} hours",
                    )

            # Styling
            ax.set_xlabel("Duration (hours)", fontsize=12, fontweight="bold")
            ax.set_ylabel("Frequency", fontsize=12, fontweight="bold")
            ax.set_title(
                f"Calendar Time Distribution ({results.iterations:,} simulations)",
                fontsize=14,
                fontweight="bold",
                pad=20,
            )
            ax.legend(loc="upper right", framealpha=0.9, fontsize=10)
            ax.grid(True, alpha=0.3, linestyle="--")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)

            # Tight layout
            plt.tight_layout()

            # Save to BytesIO
            buffer = BytesIO()
            plt.savefig(buffer, format="png", dpi=100, bbox_inches="tight")
            plt.close(fig)
            buffer.seek(0)

            # Encode to base64
            img_base64 = base64.b64encode(buffer.read()).decode("utf-8")
            return img_base64

        except Exception:
            # If anything goes wrong, return empty string
            return ""

    @staticmethod
    def _generate_effort_histogram_image(results: SimulationResults) -> str:
        """Generate a base64-encoded histogram of per-iteration total effort.

        Args:
            results: Simulation results

        Returns:
            Base64-encoded PNG image string, or empty string if unavailable
        """
        if not MATPLOTLIB_AVAILABLE or len(results.effort_durations) == 0:
            return ""

        try:
            effort = results.effort_durations
            counts, bin_edges = np.histogram(effort, bins=50)
            bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

            fig, ax = plt.subplots(figsize=(10, 6))

            ax.bar(
                bin_centers,
                counts,
                width=np.diff(bin_edges),
                color="#2196F3",
                alpha=0.7,
                edgecolor="#1565C0",
                linewidth=1.5,
            )

            effort_mean = float(np.mean(effort))
            effort_median = float(np.median(effort))

            ax.axvline(
                effort_mean,
                color="#FF5722",
                linestyle="--",
                linewidth=2,
                label=f"Mean: {effort_mean:.1f} person-hours",
            )
            ax.axvline(
                effort_median,
                color="#4CAF50",
                linestyle="--",
                linewidth=2,
                label=f"Median: {effort_median:.1f} person-hours",
            )

            for p in [80, 90, 95]:
                if p in results.effort_percentiles:
                    ax.axvline(
                        results.effort_percentiles[p],
                        color="#9E9E9E",
                        linestyle=":",
                        linewidth=1.5,
                        alpha=0.7,
                        label=f"P{p}: {results.effort_percentiles[p]:.1f} person-hours",
                    )

            ax.set_xlabel("Effort (person-hours)", fontsize=12, fontweight="bold")
            ax.set_ylabel("Frequency", fontsize=12, fontweight="bold")
            ax.set_title(
                f"Project Effort Distribution ({results.iterations:,} simulations)",
                fontsize=14,
                fontweight="bold",
                pad=20,
            )
            ax.legend(loc="upper right", framealpha=0.9, fontsize=10)
            ax.grid(True, alpha=0.3, linestyle="--")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)

            plt.tight_layout()

            buffer = BytesIO()
            plt.savefig(buffer, format="png", dpi=100, bbox_inches="tight")
            plt.close(fig)
            buffer.seek(0)

            return base64.b64encode(buffer.read()).decode("utf-8")

        except Exception:
            return ""

    @staticmethod
    def _generate_sensitivity_image(results: SimulationResults) -> str:
        """Generate a base64-encoded tornado chart for sensitivity analysis.

        Args:
            results: Simulation results

        Returns:
            Base64-encoded PNG image string, or empty string if unavailable
        """
        if not MATPLOTLIB_AVAILABLE or not results.sensitivity:
            return ""

        try:
            # Sort by absolute correlation, take top 15
            sorted_items = sorted(
                results.sensitivity.items(),
                key=lambda x: abs(x[1]),
            )
            # Show at most 15 tasks
            if len(sorted_items) > 15:
                sorted_items = sorted_items[-15:]

            task_ids = [item[0] for item in sorted_items]
            correlations = [item[1] for item in sorted_items]

            fig, ax = plt.subplots(figsize=(10, max(4, len(task_ids) * 0.4 + 1)))

            colors = ["#4CAF50" if c >= 0 else "#FF5722" for c in correlations]
            y_pos = range(len(task_ids))
            ax.barh(y_pos, correlations, color=colors, edgecolor="#333", linewidth=0.5)

            ax.set_yticks(y_pos)
            ax.set_yticklabels(task_ids, fontsize=10)
            ax.set_xlabel("Spearman Rank Correlation", fontsize=12, fontweight="bold")
            ax.set_title(
                "Sensitivity Analysis — Task Impact on Project Duration",
                fontsize=14,
                fontweight="bold",
                pad=20,
            )
            ax.axvline(0, color="#333", linewidth=0.8)
            ax.grid(True, axis="x", alpha=0.3, linestyle="--")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)

            plt.tight_layout()

            buffer = BytesIO()
            plt.savefig(buffer, format="png", dpi=100, bbox_inches="tight")
            plt.close(fig)
            buffer.seek(0)

            return base64.b64encode(buffer.read()).decode("utf-8")

        except Exception:
            return ""
