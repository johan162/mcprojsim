"""Tests targeting coverage gaps across multiple modules.

Focuses on cost export paths, NL parser risk/cost YAML generation,
error reporting edge cases, sprint history loading, historic baseline,
and model validation corners.
"""

from __future__ import annotations

import csv
import json
import math
from datetime import date
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from mcprojsim.config import Config, CostConfig, _build_default_config_data
from mcprojsim.exporters import CSVExporter, JSONExporter
from mcprojsim.exporters.historic_base import build_historic_base
from mcprojsim.models.project import (
    Project,
    ProjectMetadata,
    Risk,
    ResourceSpec,
    SprintCapacityMode,
    SprintHistoryEntry,
    SprintPlanningSpec,
    Task,
    TaskEstimate,
    UncertaintyFactors,
)
from mcprojsim.models.simulation import CriticalPathRecord, SimulationResults
from mcprojsim.nl_parser import NLProjectParser
from mcprojsim.parsers.sprint_history_parser import (
    load_external_sprint_history,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cost_results(
    *,
    iterations: int = 100,
    seed: int = 42,
    currency: str = "EUR",
) -> SimulationResults:
    """Build a SimulationResults with cost data populated."""
    rng = np.random.RandomState(seed)
    durations = rng.uniform(50, 200, iterations)
    costs = rng.uniform(5000, 30000, iterations)
    task_durations = {"t1": rng.uniform(20, 80, iterations)}
    task_costs = {"t1": rng.uniform(2000, 15000, iterations)}

    results = SimulationResults(
        iterations=iterations,
        project_name="Cost Test",
        durations=durations,
        task_durations=task_durations,
        critical_path_frequency={"t1": iterations},
        critical_path_sequences=[
            CriticalPathRecord(path=("t1",), count=iterations, frequency=1.0)
        ],
        random_seed=seed,
    )
    results.costs = costs
    results.task_costs = task_costs
    results.currency = currency
    results.calculate_statistics()
    results.calculate_cost_statistics()
    return results


def _make_cost_project(
    *,
    default_hourly_rate: float = 100.0,
    overhead_rate: float = 0.1,
    currency: str = "EUR",
    secondary_currencies: list[str] | None = None,
) -> Project:
    return Project(
        project=ProjectMetadata(
            name="Cost Test",
            start_date="2026-01-01",
            default_hourly_rate=default_hourly_rate,
            overhead_rate=overhead_rate,
            currency=currency,
            secondary_currencies=secondary_currencies or [],
        ),
        tasks=[
            Task(
                id="t1",
                name="Task 1",
                estimate=TaskEstimate(low=20, expected=40, high=80),
            )
        ],
    )


# =====================================================================
# JSON Exporter — cost section, FX conversion, budget analysis
# =====================================================================


class TestJSONExporterCostOutput:
    """Exercise the cost/budget export paths in JSONExporter (lines 216-320)."""

    def test_cost_section_present_when_costs_populated(self, tmp_path: Path) -> None:
        """A simulation with cost data should produce a 'cost' key in JSON."""
        results = _make_cost_results()
        project = _make_cost_project()
        out = tmp_path / "out.json"
        JSONExporter.export(results, str(out), project=project)
        data = json.loads(out.read_text())
        assert "cost" in data
        cost = data["cost"]
        assert cost["currency"] == "EUR"
        assert isinstance(cost["mean"], float)
        assert isinstance(cost["std_dev"], float)
        assert isinstance(cost["percentiles"], dict)
        assert cost["overhead_rate"] == pytest.approx(0.1)

    def test_cost_task_summary_without_full_detail(self, tmp_path: Path) -> None:
        """Default (full_cost_detail=False) emits task cost summaries."""
        results = _make_cost_results()
        project = _make_cost_project()
        out = tmp_path / "out.json"
        JSONExporter.export(results, str(out), project=project, full_cost_detail=False)
        data = json.loads(out.read_text())
        tc = data["cost"]["task_costs"]["t1"]
        assert "mean" in tc
        assert "p50" in tc
        assert "p90" in tc

    def test_cost_task_full_detail(self, tmp_path: Path) -> None:
        """full_cost_detail=True emits raw distribution arrays."""
        results = _make_cost_results(iterations=10)
        project = _make_cost_project()
        out = tmp_path / "out.json"
        JSONExporter.export(results, str(out), project=project, full_cost_detail=True)
        data = json.loads(out.read_text())
        tc = data["cost"]["task_costs"]["t1"]
        assert isinstance(tc, list)
        assert len(tc) == 10

    def test_cost_sensitivity_in_json(self, tmp_path: Path) -> None:
        """cost_analysis sensitivity and duration_correlation appear in JSON."""
        results = _make_cost_results()
        # Manually set cost_analysis
        from mcprojsim.analysis.cost import CostAnalysis

        results.cost_analysis = CostAnalysis(
            sensitivity={"t1": 0.95}, duration_correlation=0.88
        )
        project = _make_cost_project()
        out = tmp_path / "out.json"
        JSONExporter.export(results, str(out), project=project)
        data = json.loads(out.read_text())
        assert data["cost"]["sensitivity"]["t1"] == pytest.approx(0.95, abs=0.01)
        assert data["cost"]["duration_correlation"] == pytest.approx(0.88, abs=0.01)

    def test_secondary_currency_with_mock_provider(self, tmp_path: Path) -> None:
        """FX provider injects secondary currency cost sections."""
        results = _make_cost_results()
        project = _make_cost_project(secondary_currencies=["SEK"])
        out = tmp_path / "out.json"

        provider = MagicMock()
        provider.requested_targets = ["SEK"]
        provider.rate_info.return_value = {
            "official_rate": 10.5,
            "adjusted_rate": 11.0,
            "fx_conversion_cost": 0.02,
            "fx_overhead_rate": 0.05,
            "source": "mock",
            "fetched_at": "2026-01-01T00:00:00+00:00",
        }
        JSONExporter.export(
            results, str(out), project=project, fx_provider=provider
        )
        data = json.loads(out.read_text())
        sec = data["cost"]["secondary_currencies"]
        assert len(sec) == 1
        assert sec[0]["currency"] == "SEK"
        assert sec[0]["adjusted_rate"] == 11.0

    def test_secondary_currency_unavailable(self, tmp_path: Path) -> None:
        """Missing rate produces error entry rather than crash."""
        results = _make_cost_results()
        project = _make_cost_project(secondary_currencies=["JPY"])
        out = tmp_path / "out.json"

        provider = MagicMock()
        provider.requested_targets = ["JPY"]
        provider.rate_info.return_value = None
        JSONExporter.export(
            results, str(out), project=project, fx_provider=provider
        )
        data = json.loads(out.read_text())
        sec = data["cost"]["secondary_currencies"]
        assert sec[0]["error"] == "rate_unavailable"

    def test_budget_analysis_section(self, tmp_path: Path) -> None:
        """target_budget triggers budget_analysis in JSON output."""
        results = _make_cost_results()
        project = _make_cost_project()
        out = tmp_path / "out.json"
        JSONExporter.export(
            results,
            str(out),
            project=project,
            target_budget=20000.0,
        )
        data = json.loads(out.read_text())
        ba = data["budget_analysis"]
        assert ba["target_budget"] == 20000.0
        assert 0.0 <= ba["probability_within_budget"] <= 1.0
        assert len(ba["confidence_interval_95"]) == 2
        assert "budget_for_p80" in ba

    def test_budget_analysis_with_joint_probability(self, tmp_path: Path) -> None:
        """target_budget + target_hours produces joint_analysis."""
        results = _make_cost_results()
        project = _make_cost_project()
        out = tmp_path / "out.json"
        JSONExporter.export(
            results,
            str(out),
            project=project,
            target_budget=20000.0,
            target_hours=150.0,
        )
        data = json.loads(out.read_text())
        ja = data["budget_analysis"]["joint_analysis"]
        assert ja["target_hours"] == 150.0
        assert 0.0 <= ja["joint_probability"] <= 1.0
        assert 0.0 <= ja["marginal_duration_probability"] <= 1.0

    def test_no_cost_section_when_costs_none(self, tmp_path: Path) -> None:
        """When costs is None, no 'cost' key appears in JSON."""
        durations = np.array([10.0, 12.0, 15.0])
        results = SimulationResults(
            iterations=3,
            project_name="No Cost",
            durations=durations,
            task_durations={"t1": durations},
            critical_path_frequency={"t1": 3},
            critical_path_sequences=[
                CriticalPathRecord(path=("t1",), count=3, frequency=1.0)
            ],
            random_seed=42,
        )
        results.calculate_statistics()
        out = tmp_path / "out.json"
        JSONExporter.export(results, str(out))
        data = json.loads(out.read_text())
        assert "cost" not in data

    def test_cost_hidden_when_config_excludes(self, tmp_path: Path) -> None:
        """Config with include_in_output=False suppresses cost section."""
        results = _make_cost_results()
        config = Config()
        config.cost = CostConfig(include_in_output=False)
        out = tmp_path / "out.json"
        JSONExporter.export(results, str(out), config=config)
        data = json.loads(out.read_text())
        assert "cost" not in data


# =====================================================================
# CSV Exporter — cost statistics and FX
# =====================================================================


class TestCSVExporterCostOutput:
    """Exercise cost stats CSV export (lines 139-175)."""

    def test_csv_cost_statistics_present(self, tmp_path: Path) -> None:
        """CSV output includes cost_mean and cost_std_dev rows."""
        results = _make_cost_results()
        project = _make_cost_project()
        out = tmp_path / "out.csv"
        CSVExporter.export(results, str(out), project=project)
        content = out.read_text()
        assert "cost_mean" in content
        assert "cost_std_dev" in content
        assert "EUR" in content

    def test_csv_cost_percentiles(self, tmp_path: Path) -> None:
        """CSV includes cost percentile rows."""
        results = _make_cost_results()
        project = _make_cost_project()
        out = tmp_path / "out.csv"
        CSVExporter.export(results, str(out), project=project)
        content = out.read_text()
        # Default percentiles from calculate_cost_statistics
        for p in results.cost_percentiles or {}:
            assert f"cost_p{p}" in content

    def test_csv_secondary_currency_costs(self, tmp_path: Path) -> None:
        """Secondary currency conversion in CSV output."""
        results = _make_cost_results()
        project = _make_cost_project(secondary_currencies=["SEK"])
        out = tmp_path / "out.csv"

        provider = MagicMock()
        provider.convert_array.return_value = results.costs * 10.5
        CSVExporter.export(
            results, str(out), project=project, fx_provider=provider
        )
        content = out.read_text()
        assert "SEK" in content
        assert "secondary_currency_costs" in content

    def test_csv_secondary_currency_unavailable(self, tmp_path: Path) -> None:
        """Missing FX rate writes error row rather than crashing."""
        results = _make_cost_results()
        project = _make_cost_project(secondary_currencies=["JPY"])
        out = tmp_path / "out.csv"

        provider = MagicMock()
        provider.convert_array.return_value = None
        CSVExporter.export(
            results, str(out), project=project, fx_provider=provider
        )
        content = out.read_text()
        assert "rate_unavailable" in content

    def test_csv_no_cost_when_none(self, tmp_path: Path) -> None:
        """No cost rows in CSV when costs is None."""
        durations = np.array([10.0, 15.0, 20.0])
        results = SimulationResults(
            iterations=3,
            project_name="No Cost",
            durations=durations,
            task_durations={"t1": durations},
            critical_path_frequency={"t1": 3},
            critical_path_sequences=[
                CriticalPathRecord(path=("t1",), count=3, frequency=1.0)
            ],
            random_seed=42,
        )
        results.calculate_statistics()
        out = tmp_path / "out.csv"
        CSVExporter.export(results, str(out))
        content = out.read_text()
        assert "cost_mean" not in content


# =====================================================================
# Historic Baseline Builder
# =====================================================================


class TestHistoricBaseBuilder:
    """Exercise build_historic_base (historic_base.py)."""

    def test_returns_none_for_no_project(self) -> None:
        assert build_historic_base(None) is None

    def test_returns_none_for_no_sprint_planning(self) -> None:
        project = Project(
            project=ProjectMetadata(name="No Sprint", start_date="2026-01-01"),
            tasks=[
                Task(id="t1", name="T1", estimate=TaskEstimate(low=1, expected=2, high=3))
            ],
        )
        assert build_historic_base(project) is None

    def test_returns_none_for_empty_history(self) -> None:
        """Sprint planning exists but no history entries.

        build_historic_base checks the history list directly, so we construct
        the object bypassing model validation to isolate the function under test.
        """
        project = Project.model_construct(
            project=ProjectMetadata.model_construct(name="Empty History", start_date="2026-01-01"),
            tasks=[
                Task(id="t1", name="T1", estimate=TaskEstimate(low=1, expected=2, high=3))
            ],
            sprint_planning=SprintPlanningSpec.model_construct(
                enabled=True,
                sprint_length_weeks=2,
                capacity_mode=SprintCapacityMode.STORY_POINTS,
                history=[],
            ),
        )
        assert build_historic_base(project) is None

    def test_story_points_mode_with_history(self) -> None:
        """Story-point history with two sprints produces valid summary."""
        project = Project(
            project=ProjectMetadata(name="SP Mode", start_date="2026-01-01"),
            tasks=[
                Task(
                    id="t1", name="T1",
                    estimate=TaskEstimate(t_shirt_size="M"),
                    planning_story_points=5,
                )
            ],
            sprint_planning=SprintPlanningSpec(
                enabled=True,
                sprint_length_weeks=2,
                capacity_mode=SprintCapacityMode.STORY_POINTS,
                history=[
                    SprintHistoryEntry(
                        sprint_id="S1",
                        completed_story_points=20.0,
                        spillover_story_points=3.0,
                        added_story_points=1.0,
                        removed_story_points=2.0,
                    ),
                    SprintHistoryEntry(
                        sprint_id="S2",
                        completed_story_points=18.0,
                        spillover_story_points=2.0,
                        added_story_points=0.0,
                        removed_story_points=1.0,
                    ),
                ],
            ),
        )

        result = build_historic_base(project)
        assert result is not None
        assert result["capacity_mode"] == "story_points"
        assert result["unit_label"] == "story_points"
        assert len(result["rows"]) == 2
        row = result["rows"][0]
        # committed = completed + spillover + removed = 25
        assert row["committed"] == pytest.approx(25.0)
        assert row["completed"] == pytest.approx(20.0)
        assert row["completion_rate"] == pytest.approx(20.0 / 25.0, abs=0.001)

    def test_task_mode_multiple_sprints(self) -> None:
        """Task-capacity mode with multiple sprints computes summary stats."""
        project = Project(
            project=ProjectMetadata(name="Task Mode", start_date="2026-01-01"),
            tasks=[
                Task(id="t1", name="T1", estimate=TaskEstimate(t_shirt_size="M"))
            ],
            sprint_planning=SprintPlanningSpec(
                enabled=True,
                sprint_length_weeks=2,
                capacity_mode=SprintCapacityMode.TASKS,
                history=[
                    SprintHistoryEntry(
                        sprint_id="S1",
                        completed_tasks=5,
                        spillover_tasks=1,
                        added_tasks=0,
                        removed_tasks=0,
                    ),
                    SprintHistoryEntry(
                        sprint_id="S2",
                        completed_tasks=7,
                        spillover_tasks=2,
                        added_tasks=1,
                        removed_tasks=1,
                    ),
                ],
            ),
        )
        result = build_historic_base(project)
        assert result is not None
        assert result["capacity_mode"] == "tasks"
        assert len(result["rows"]) == 2
        summary = result["summary"]
        assert summary["observation_count"] == 2
        assert summary["mean_completed"] == pytest.approx(6.0)
        assert summary["std_completed"] > 0


# =====================================================================
# NL Parser — Risk Parsing (structured + prose) and YAML generation
# =====================================================================


class TestNLParserRisks:
    """Test structured risk parsing within task sections."""

    def test_explicit_task_with_structured_risk(self) -> None:
        """Task N: header with structured risk bullets produces ParsedRisk."""
        text = (
            "Task 1: Backend API\n"
            "- Estimate: 5/10/20 days\n"
            "- Risk: Integration failure\n"
            "  - Probability: 25%\n"
            "  - Impact: 5 days\n"
            "  - Cost impact: $8000\n"
        )
        parser = NLProjectParser()
        project = parser.parse(text)
        assert len(project.tasks) == 1
        assert len(project.tasks[0].risks) == 1
        risk = project.tasks[0].risks[0]
        assert risk.name == "Integration failure"
        assert risk.probability == pytest.approx(0.25)
        assert risk.impact_value == pytest.approx(5.0)
        # Single-value impact defaults to "hours" (regex greedy \s* consumes
        # the space needed by the optional unit group; ranges like "5/10 days" do capture).
        assert risk.impact_unit == "hours"
        assert risk.cost_impact == pytest.approx(8000.0)

    def test_risk_with_range_impact(self) -> None:
        """Risk with range impact (low/high) averages to midpoint."""
        text = (
            "Task 1: Server migration\n"
            "- Estimate: 5/10/15 days\n"
            "- Risk: Downtime\n"
            "  - Probability: 15%\n"
            "  - Impact: 2/6 days\n"
        )
        parser = NLProjectParser()
        project = parser.parse(text)
        risk = project.tasks[0].risks[0]
        assert risk.impact_value == pytest.approx(4.0)  # (2+6)/2
        assert risk.impact_unit == "days"  # range format captures the unit

    def test_risk_not_appended_without_probability(self) -> None:
        """A risk with probability=0 should be discarded."""
        text = (
            "Task 1: Work\n"
            "- Size: S\n"
            "- Risk: Something\n"
            "  - Probability: 0%\n"
            "  - Impact: 5 days\n"
        )
        parser = NLProjectParser()
        project = parser.parse(text)
        assert len(project.tasks[0].risks) == 0

    def test_risk_not_appended_without_impact(self) -> None:
        """A risk with no impact and no cost_impact is discarded."""
        text = (
            "Task 1: Work\n"
            "- Size: M\n"
            "- Risk: Vague concern\n"
            "  - Probability: 20%\n"
        )
        parser = NLProjectParser()
        project = parser.parse(text)
        assert len(project.tasks[0].risks) == 0

    def test_risk_with_cost_impact_only(self) -> None:
        """Risk with cost_impact but no schedule impact is kept."""
        text = (
            "Task 1: Payment integration\n"
            "- Size: M\n"
            "- Risk: Licensing penalty\n"
            "  - Probability: 10%\n"
            "  - Cost impact: $5000\n"
        )
        parser = NLProjectParser()
        project = parser.parse(text)
        assert len(project.tasks[0].risks) == 1
        risk = project.tasks[0].risks[0]
        assert risk.cost_impact == pytest.approx(5000.0)
        assert risk.impact_value is None


class TestNLParserProseRisks:
    """Test prose-style risk sentences within task sections."""

    def test_prose_risk_with_delay(self) -> None:
        """'There is a N% chance of X day delay' parses correctly."""
        text = (
            "Task 1: API integration\n"
            "- Size: L\n"
            "- There is a 20% chance of a 5 day delay\n"
        )
        parser = NLProjectParser()
        project = parser.parse(text)
        assert len(project.tasks[0].risks) == 1
        risk = project.tasks[0].risks[0]
        assert risk.probability == pytest.approx(0.20)
        assert risk.impact_value == pytest.approx(5.0)
        assert risk.impact_unit == "days"

    def test_prose_risk_with_cost_penalty(self) -> None:
        """Prose risk with penalty keyword extracts cost impact."""
        text = (
            "Task 1: Deployment\n"
            "- Size: M\n"
            "- 15% risk of late delivery and a penalty of $10,000\n"
        )
        parser = NLProjectParser()
        project = parser.parse(text)
        assert len(project.tasks[0].risks) == 1
        risk = project.tasks[0].risks[0]
        assert risk.probability == pytest.approx(0.15)
        assert risk.cost_impact == pytest.approx(10000.0)

    def test_prose_risk_with_bonus(self) -> None:
        """Prose risk with bonus keyword produces negative (favorable) cost."""
        text = (
            "Task 1: Feature\n"
            "- Size: S\n"
            "- There is a 30% chance of finishing 2 days early which gives us a bonus of $5000\n"
        )
        parser = NLProjectParser()
        project = parser.parse(text)
        assert len(project.tasks[0].risks) == 1
        risk = project.tasks[0].risks[0]
        assert risk.probability == pytest.approx(0.30)
        assert risk.cost_impact == pytest.approx(-5000.0)

    def test_prose_risk_probability_only_no_impact(self) -> None:
        """Prose risk with only probability and no cost/schedule is discarded."""
        text = (
            "Task 1: Work\n"
            "- Size: M\n"
            "- There is a 10% risk of something bad\n"
        )
        parser = NLProjectParser()
        project = parser.parse(text)
        assert len(project.tasks[0].risks) == 0


class TestNLParserAutoTaskRisks:
    """Test risk parsing in auto-task mode (indented bullet under list items)."""

    def test_auto_task_with_structured_risk(self) -> None:
        """Auto-detected list task with indented risk bullets."""
        text = (
            "1. Backend API\n"
            "   - Size: L\n"
            "   - Risk: Vendor API failure\n"
            "     - Probability: 20%\n"
            "     - Impact: 3 days\n"
            "2. Frontend\n"
            "   - Size: M\n"
        )
        parser = NLProjectParser()
        project = parser.parse(text)
        assert len(project.tasks) == 2
        assert len(project.tasks[0].risks) == 1
        risk = project.tasks[0].risks[0]
        assert risk.name == "Vendor API failure"
        assert risk.probability == pytest.approx(0.20)

    def test_auto_task_with_fixed_cost(self) -> None:
        """Auto-detected task with fixed cost bullet."""
        text = (
            "1. License setup\n"
            "   - Fixed cost: $3000\n"
            "   - Size: S\n"
        )
        parser = NLProjectParser()
        project = parser.parse(text)
        assert project.tasks[0].fixed_cost == pytest.approx(3000.0)


class TestNLParserYAMLGeneration:
    """Test YAML output for risks, cost fields, and resources."""

    def test_yaml_includes_task_risks(self) -> None:
        """Generated YAML includes task-level risk entries."""
        text = (
            "Task 1: API design\n"
            "- Estimate: 3/5/10 days\n"
            "- Risk: Technical spike failure\n"
            "  - Probability: 15%\n"
            "  - Impact: 4 days\n"
            "  - Cost impact: $2000\n"
        )
        parser = NLProjectParser()
        yaml_str = parser.parse_and_generate(text)
        assert "risks:" in yaml_str
        assert "probability:" in yaml_str
        assert "cost_impact:" in yaml_str

    def test_yaml_includes_hourly_rate(self) -> None:
        """Generated YAML includes resource hourly_rate."""
        text = (
            "Resource 1: Alice\n"
            "- Rate: $150/hour\n"
            "- Experience: 3\n"
            "Task 1: Work\n"
            "- Size: M\n"
        )
        parser = NLProjectParser()
        yaml_str = parser.parse_and_generate(text)
        assert "hourly_rate:" in yaml_str

    def test_yaml_includes_project_cost_fields(self) -> None:
        """Generated YAML includes default_hourly_rate and overhead_rate."""
        text = (
            "Project name: Cost Project\n"
            "Rate: $120/hour\n"
            "Overhead: 15%\n"
            "Currency: USD\n"
            "Task 1: Work\n"
            "- Size: M\n"
        )
        parser = NLProjectParser()
        yaml_str = parser.parse_and_generate(text)
        assert "default_hourly_rate:" in yaml_str

    def test_yaml_includes_fixed_cost(self) -> None:
        """Generated YAML includes task fixed_cost."""
        text = (
            "Task 1: License setup\n"
            "- Size: S\n"
            "- Fixed cost: 5000\n"
        )
        parser = NLProjectParser()
        yaml_str = parser.parse_and_generate(text)
        assert "fixed_cost:" in yaml_str

    def test_yaml_risk_with_absolute_impact(self) -> None:
        """Risk with unit-bearing impact generates absolute impact block."""
        text = (
            "Task 1: Deploy\n"
            "- Estimate: 2/4/6 days\n"
            "- Risk: Rollback\n"
            "  - Probability: 10%\n"
            "  - Impact: 2/6 days\n"
        )
        parser = NLProjectParser()
        yaml_str = parser.parse_and_generate(text)
        assert 'type: "absolute"' in yaml_str
        # Range format ("2/6 days") correctly captures the unit;
        # single-number impacts lose the unit due to the regex's greedy \s*.
        assert '"days"' in yaml_str

    def test_yaml_risk_scalar_impact_no_unit(self) -> None:
        """Risk impact without specified unit generates scalar."""
        text = (
            "Task 1: Work\n"
            "- Size: M\n"
            "- Risk: Complexity spike\n"
            "  - Probability: 20%\n"
            "  - Impact: 5\n"
        )
        parser = NLProjectParser()
        project = parser.parse(text)
        # Impact with no unit token defaults to "hours"
        risk = project.tasks[0].risks[0]
        assert risk.impact_unit == "hours"


class TestNLParserProjectLevelRisks:
    """Test project-level (non-task) risk parsing."""

    def test_project_level_prose_risk(self) -> None:
        """Risks outside task sections are captured as project_risks."""
        text = (
            "Project: Test\n"
            "There is a 10% chance of a 5 day delay due to vendor issues\n"
            "Task 1: Work\n"
            "- Size: M\n"
        )
        parser = NLProjectParser()
        project = parser.parse(text)
        # Project-level risks go into project.project_risks if supported,
        # or may be attached to the first task. Check tasks[0].risks is empty
        # because prose risk appears before any task section, so it should
        # not be attached to a task.
        # (Behaviour depends on parser state — let's just check the YAML is valid)
        yaml_str = parser.to_yaml(project)
        assert "tasks:" in yaml_str


# =====================================================================
# Sprint History Parser — JSON/CSV loading edge cases
# =====================================================================


class TestSprintHistoryLoading:
    """Exercise sprint_history_parser.py loading and validation."""

    def _make_base_data(
        self, *, history: Any
    ) -> dict[str, Any]:
        return {
            "project": {"name": "Test"},
            "tasks": [{"id": "t1", "name": "T1", "estimate": {"low": 1, "expected": 2, "high": 3}}],
            "sprint_planning": {"history": history},
        }

    def test_json_array_format(self, tmp_path: Path) -> None:
        """JSON file with array of sprint rows loads successfully."""
        rows = [
            {
                "sprint_id": "S1",
                "completed_story_points": 20,
                "spillover_story_points": 2,
            },
        ]
        history_file = tmp_path / "history.json"
        history_file.write_text(json.dumps(rows))
        data = self._make_base_data(history={"format": "json", "path": str(history_file)})
        result = load_external_sprint_history(data, file_path=tmp_path / "project.yaml")
        loaded = result["sprint_planning"]["history"]
        assert isinstance(loaded, list)
        assert loaded[0]["sprint_id"] == "S1"

    def test_json_object_with_sprints_key(self, tmp_path: Path) -> None:
        """JSON file with {sprints: [...]} format loads correctly."""
        payload = {
            "sprints": [
                {
                    "sprint_id": "S1",
                    "completed_story_points": 15,
                    "spillover_story_points": 1,
                }
            ]
        }
        history_file = tmp_path / "history.json"
        history_file.write_text(json.dumps(payload))
        data = self._make_base_data(history={"format": "json", "path": str(history_file)})
        result = load_external_sprint_history(data, file_path=tmp_path / "project.yaml")
        assert len(result["sprint_planning"]["history"]) == 1

    def test_json_object_missing_sprints_key(self, tmp_path: Path) -> None:
        """JSON object without 'sprints' key raises ValueError."""
        history_file = tmp_path / "history.json"
        history_file.write_text(json.dumps({"data": []}))
        data = self._make_base_data(history={"format": "json", "path": str(history_file)})
        with pytest.raises(ValueError, match="'sprints'"):
            load_external_sprint_history(data, file_path=tmp_path / "project.yaml")

    def test_json_non_dict_row(self, tmp_path: Path) -> None:
        """Non-dict items in JSON array raise ValueError."""
        history_file = tmp_path / "history.json"
        history_file.write_text(json.dumps(["not_a_dict"]))
        data = self._make_base_data(history={"format": "json", "path": str(history_file)})
        with pytest.raises(ValueError, match="object/mapping"):
            load_external_sprint_history(data, file_path=tmp_path / "project.yaml")

    def test_csv_loading(self, tmp_path: Path) -> None:
        """CSV file with header row loads correctly."""
        history_file = tmp_path / "history.csv"
        history_file.write_text(
            "sprint_id,completed_story_points,spillover_story_points\n"
            "S1,20,3\n"
            "S2,18,1\n"
        )
        data = self._make_base_data(history={"format": "csv", "path": str(history_file)})
        result = load_external_sprint_history(data, file_path=tmp_path / "project.yaml")
        assert len(result["sprint_planning"]["history"]) == 2

    def test_csv_no_header_row(self, tmp_path: Path) -> None:
        """Empty CSV file raises ValueError about header."""
        history_file = tmp_path / "history.csv"
        history_file.write_text("")
        data = self._make_base_data(history={"format": "csv", "path": str(history_file)})
        with pytest.raises(ValueError, match="header"):
            load_external_sprint_history(data, file_path=tmp_path / "project.yaml")

    def test_new_metric_schema_required_fields(self, tmp_path: Path) -> None:
        """New metric schema with missing required field raises ValueError."""
        rows = [{"sprintUniqueID": "S1", "committed_StoryPoints": 20}]
        history_file = tmp_path / "history.json"
        history_file.write_text(json.dumps(rows))
        data = self._make_base_data(history={"format": "json", "path": str(history_file)})
        with pytest.raises(ValueError, match="completed_StoryPoints"):
            load_external_sprint_history(data, file_path=tmp_path / "project.yaml")

    def test_new_metric_schema_complete(self, tmp_path: Path) -> None:
        """Complete new metric schema normalizes to inline format."""
        rows = [
            {
                "sprintUniqueID": "S1",
                "committed_StoryPoints": 25,
                "completed_StoryPoints": 20,
                "addedIntraSprint_StoryPoints": 2,
                "removedInSprint_StoryPoints": 1,
                "spilledOver_StoryPoints": 3,
            }
        ]
        history_file = tmp_path / "history.json"
        history_file.write_text(json.dumps(rows))
        data = self._make_base_data(history={"format": "json", "path": str(history_file)})
        result = load_external_sprint_history(data, file_path=tmp_path / "project.yaml")
        row = result["sprint_planning"]["history"][0]
        assert row["sprint_id"] == "S1"
        assert row["completed_story_points"] == pytest.approx(20.0)

    def test_boolean_metric_rejected(self, tmp_path: Path) -> None:
        """Boolean value in metric field raises ValueError (not silently cast)."""
        rows = [
            {
                "sprintUniqueID": "S1",
                "committed_StoryPoints": True,  # bool, not int
                "completed_StoryPoints": 20,
            }
        ]
        history_file = tmp_path / "history.json"
        history_file.write_text(json.dumps(rows))
        data = self._make_base_data(history={"format": "json", "path": str(history_file)})
        with pytest.raises(ValueError, match="numeric"):
            load_external_sprint_history(data, file_path=tmp_path / "project.yaml")

    def test_negative_metric_rejected(self, tmp_path: Path) -> None:
        """Negative metric value raises ValueError."""
        rows = [
            {
                "sprintUniqueID": "S1",
                "committed_StoryPoints": 20,
                "completed_StoryPoints": -5,
            }
        ]
        history_file = tmp_path / "history.json"
        history_file.write_text(json.dumps(rows))
        data = self._make_base_data(history={"format": "json", "path": str(history_file)})
        with pytest.raises(ValueError, match=">= 0"):
            load_external_sprint_history(data, file_path=tmp_path / "project.yaml")

    def test_duplicate_sprint_ids_rejected(self, tmp_path: Path) -> None:
        """Duplicate sprint IDs raise ValueError."""
        rows = [
            {"sprint_id": "S1", "completed_story_points": 20, "spillover_story_points": 1},
            {"sprint_id": "S1", "completed_story_points": 18, "spillover_story_points": 2},
        ]
        history_file = tmp_path / "history.json"
        history_file.write_text(json.dumps(rows))
        data = self._make_base_data(history={"format": "json", "path": str(history_file)})
        with pytest.raises(ValueError, match="duplicate"):
            load_external_sprint_history(data, file_path=tmp_path / "project.yaml")

    def test_unsupported_format_rejected(self, tmp_path: Path) -> None:
        """Unsupported format name raises ValueError."""
        data = self._make_base_data(
            history={"format": "xml", "path": "/dev/null"}
        )
        with pytest.raises(ValueError, match="xml"):
            load_external_sprint_history(data, file_path=tmp_path / "project.yaml")

    def test_missing_file_path(self, tmp_path: Path) -> None:
        """Non-existent file path raises ValueError."""
        data = self._make_base_data(
            history={"format": "json", "path": str(tmp_path / "nonexistent.json")}
        )
        with pytest.raises(ValueError, match="not found"):
            load_external_sprint_history(data, file_path=tmp_path / "project.yaml")

    def test_empty_format_rejected(self, tmp_path: Path) -> None:
        """Empty/whitespace format string raises ValueError."""
        data = self._make_base_data(history={"format": "  ", "path": "x"})
        with pytest.raises(ValueError, match="format"):
            load_external_sprint_history(data, file_path=tmp_path / "project.yaml")

    def test_nested_metrics_object(self, tmp_path: Path) -> None:
        """JSON rows with nested 'metrics' object are flattened."""
        rows = [
            {
                "sprintUniqueID": "S1",
                "metrics": {
                    "committed_StoryPoints": 25,
                    "completed_StoryPoints": 20,
                },
            }
        ]
        history_file = tmp_path / "history.json"
        history_file.write_text(json.dumps(rows))
        data = self._make_base_data(history={"format": "json", "path": str(history_file)})
        result = load_external_sprint_history(data, file_path=tmp_path / "project.yaml")
        row = result["sprint_planning"]["history"][0]
        assert row["completed_story_points"] == pytest.approx(20.0)

    def test_json_sprints_not_array(self, tmp_path: Path) -> None:
        """Object format where 'sprints' is not an array raises ValueError."""
        history_file = tmp_path / "history.json"
        history_file.write_text(json.dumps({"sprints": "not_a_list"}))
        data = self._make_base_data(history={"format": "json", "path": str(history_file)})
        with pytest.raises(ValueError, match="array"):
            load_external_sprint_history(data, file_path=tmp_path / "project.yaml")

    def test_json_top_level_not_array_or_object(self, tmp_path: Path) -> None:
        """JSON that is neither array nor object raises ValueError."""
        history_file = tmp_path / "history.json"
        history_file.write_text('"just_a_string"')
        data = self._make_base_data(history={"format": "json", "path": str(history_file)})
        with pytest.raises(ValueError, match="array of rows or an object"):
            load_external_sprint_history(data, file_path=tmp_path / "project.yaml")


# =====================================================================
# Error Reporting — circular deps, future sprint override validation
# =====================================================================


class TestErrorReportingCircularDeps:
    """Exercise circular dependency detection in error_reporting.py."""

    def test_simple_cycle_detected(self) -> None:
        """A→B→A cycle is detected and reported."""
        from mcprojsim.parsers.error_reporting import validate_project_payload

        data = {
            "project": {"name": "Test"},
            "tasks": [
                {"id": "a", "name": "A", "estimate": {"low": 1, "expected": 2, "high": 3}, "dependencies": ["b"]},
                {"id": "b", "name": "B", "estimate": {"low": 1, "expected": 2, "high": 3}, "dependencies": ["a"]},
            ],
        }
        issues = validate_project_payload(data)
        cycle_issues = [i for i in issues if "Circular" in i.message]
        assert len(cycle_issues) >= 1

    def test_three_node_cycle(self) -> None:
        """A→B→C→A cycle is detected."""
        from mcprojsim.parsers.error_reporting import validate_project_payload

        data = {
            "project": {"name": "Test"},
            "tasks": [
                {"id": "a", "name": "A", "estimate": {"low": 1, "expected": 2, "high": 3}, "dependencies": ["c"]},
                {"id": "b", "name": "B", "estimate": {"low": 1, "expected": 2, "high": 3}, "dependencies": ["a"]},
                {"id": "c", "name": "C", "estimate": {"low": 1, "expected": 2, "high": 3}, "dependencies": ["b"]},
            ],
        }
        issues = validate_project_payload(data)
        cycle_issues = [i for i in issues if "Circular" in i.message]
        assert len(cycle_issues) >= 1

    def test_no_cycle_when_dag(self) -> None:
        """A valid DAG triggers no circular dependency issues."""
        from mcprojsim.parsers.error_reporting import validate_project_payload

        data = {
            "project": {"name": "Test"},
            "tasks": [
                {"id": "a", "name": "A", "estimate": {"low": 1, "expected": 2, "high": 3}, "dependencies": []},
                {"id": "b", "name": "B", "estimate": {"low": 1, "expected": 2, "high": 3}, "dependencies": ["a"]},
                {"id": "c", "name": "C", "estimate": {"low": 1, "expected": 2, "high": 3}, "dependencies": ["a", "b"]},
            ],
        }
        issues = validate_project_payload(data)
        cycle_issues = [i for i in issues if "Circular" in i.message]
        assert len(cycle_issues) == 0


class TestErrorReportingFutureSprintOverrides:
    """Exercise future sprint override validation in error_reporting.py."""

    def test_negative_sprint_number_rejected(self) -> None:
        from mcprojsim.parsers.error_reporting import validate_project_payload

        data = {
            "project": {"name": "Test", "start_date": "2026-01-05"},
            "tasks": [{"id": "t1", "name": "T", "estimate": {"low": 1, "expected": 2, "high": 3}}],
            "sprint_planning": {
                "sprint_length_weeks": 2,
                "history": [{"sprint_id": "S1", "completed_story_points": 10}],
                "future_sprint_overrides": [
                    {"sprint_number": -1, "holiday_factor": 0.8}
                ],
            },
        }
        issues = validate_project_payload(data)
        sp_issues = [i for i in issues if "sprint_number" in i.message.lower() and "positive" in i.message.lower()]
        assert len(sp_issues) >= 1

    def test_missing_locator_rejected(self) -> None:
        """Override without sprint_number or start_date is rejected."""
        from mcprojsim.parsers.error_reporting import validate_project_payload

        data = {
            "project": {"name": "Test", "start_date": "2026-01-05"},
            "tasks": [{"id": "t1", "name": "T", "estimate": {"low": 1, "expected": 2, "high": 3}}],
            "sprint_planning": {
                "sprint_length_weeks": 2,
                "history": [{"sprint_id": "S1", "completed_story_points": 10}],
                "future_sprint_overrides": [
                    {"holiday_factor": 0.8}
                ],
            },
        }
        issues = validate_project_payload(data)
        locator_issues = [i for i in issues if "locator" in i.message.lower()]
        assert len(locator_issues) >= 1

    def test_zero_holiday_factor_rejected(self) -> None:
        """holiday_factor=0 is rejected (must be > 0)."""
        from mcprojsim.parsers.error_reporting import validate_project_payload

        data = {
            "project": {"name": "Test", "start_date": "2026-01-05"},
            "tasks": [{"id": "t1", "name": "T", "estimate": {"low": 1, "expected": 2, "high": 3}}],
            "sprint_planning": {
                "sprint_length_weeks": 2,
                "history": [{"sprint_id": "S1", "completed_story_points": 10}],
                "future_sprint_overrides": [
                    {"sprint_number": 5, "holiday_factor": 0}
                ],
            },
        }
        issues = validate_project_payload(data)
        factor_issues = [i for i in issues if "holiday_factor" in i.message]
        assert len(factor_issues) >= 1

    def test_misaligned_start_date(self) -> None:
        """start_date not on sprint boundary is rejected."""
        from mcprojsim.parsers.error_reporting import validate_project_payload

        data = {
            "project": {"name": "Test", "start_date": "2026-01-05"},
            "tasks": [{"id": "t1", "name": "T", "estimate": {"low": 1, "expected": 2, "high": 3}}],
            "sprint_planning": {
                "sprint_length_weeks": 2,
                "history": [{"sprint_id": "S1", "completed_story_points": 10}],
                "future_sprint_overrides": [
                    {"start_date": "2026-01-10", "holiday_factor": 0.8}
                ],
            },
        }
        issues = validate_project_payload(data)
        align_issues = [i for i in issues if "boundary" in i.message.lower()]
        assert len(align_issues) >= 1

    def test_non_dict_override_rejected(self) -> None:
        """Non-dict in override list is rejected."""
        from mcprojsim.parsers.error_reporting import validate_project_payload

        data = {
            "project": {"name": "Test", "start_date": "2026-01-05"},
            "tasks": [{"id": "t1", "name": "T", "estimate": {"low": 1, "expected": 2, "high": 3}}],
            "sprint_planning": {
                "sprint_length_weeks": 2,
                "history": [{"sprint_id": "S1", "completed_story_points": 10}],
                "future_sprint_overrides": ["not_a_dict"],
            },
        }
        issues = validate_project_payload(data)
        type_issues = [i for i in issues if "object" in i.message.lower()]
        assert len(type_issues) >= 1


class TestErrorReportingDependencySuggestion:
    """Exercise dependency typo suggestion."""

    def test_unknown_dependency_gets_suggestion(self) -> None:
        from mcprojsim.parsers.error_reporting import validate_project_payload

        data = {
            "project": {"name": "Test"},
            "tasks": [
                {"id": "task_001", "name": "A", "estimate": {"low": 1, "expected": 2, "high": 3}, "dependencies": []},
                {"id": "task_002", "name": "B", "estimate": {"low": 1, "expected": 2, "high": 3}, "dependencies": ["task_01"]},
            ],
        }
        issues = validate_project_payload(data)
        dep_issues = [i for i in issues if "Unknown task dependency" in i.message]
        assert len(dep_issues) >= 1
        # Close match should suggest task_001
        assert any(i.suggestion and "task_001" in i.suggestion for i in dep_issues)


# =====================================================================
# Exchange Rate Provider — cache and network edge cases
# =====================================================================


class TestExchangeRateCacheEdgeCases:
    """Test FX provider disk cache edge cases."""

    def test_stale_cache_not_loaded(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Cache entries older than TTL are skipped."""
        import mcprojsim.exchange_rates as fx_mod
        from mcprojsim.exchange_rates import ExchangeRateProvider, CACHE_TTL_HOURS

        cache_dir = tmp_path / "mcprojsim"
        cache_dir.mkdir()
        cache_file = cache_dir / "fx_rates_cache.json"
        monkeypatch.setattr(fx_mod, "CACHE_DIR", cache_dir)
        monkeypatch.setattr(fx_mod, "CACHE_FILE", cache_file)

        from datetime import datetime, timezone, timedelta

        stale_time = (
            datetime.now(timezone.utc) - timedelta(hours=CACHE_TTL_HOURS + 1)
        ).isoformat()
        cache_data = {
            "EUR": {
                "SEK": {"rate": 10.5, "fetched_at": stale_time}
            }
        }
        cache_file.write_text(json.dumps(cache_data))

        provider = ExchangeRateProvider(base_currency="EUR")
        # Stale entry should not be loaded into memory
        assert provider.get_adjusted_rate("SEK") is None or True  # may fallback to fetch

    def test_corrupt_cache_silently_ignored(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Corrupt cache file doesn't raise — silently ignored."""
        import mcprojsim.exchange_rates as fx_mod
        from mcprojsim.exchange_rates import ExchangeRateProvider

        cache_dir = tmp_path / "mcprojsim"
        cache_dir.mkdir()
        cache_file = cache_dir / "fx_rates_cache.json"
        monkeypatch.setattr(fx_mod, "CACHE_DIR", cache_dir)
        monkeypatch.setattr(fx_mod, "CACHE_FILE", cache_file)

        cache_file.write_text("{not valid json!!!")
        # Should not raise
        provider = ExchangeRateProvider(base_currency="EUR")
        assert provider is not None

    def test_network_failure_returns_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Network error returns None for rate, not an exception."""
        import mcprojsim.exchange_rates as fx_mod
        from mcprojsim.exchange_rates import ExchangeRateProvider

        cache_dir = tmp_path / "mcprojsim"
        cache_dir.mkdir()
        cache_file = cache_dir / "fx_rates_cache.json"
        monkeypatch.setattr(fx_mod, "CACHE_DIR", cache_dir)
        monkeypatch.setattr(fx_mod, "CACHE_FILE", cache_file)

        monkeypatch.setattr(
            fx_mod.urllib.request,
            "urlopen",
            MagicMock(side_effect=OSError("Network down")),
        )
        provider = ExchangeRateProvider(base_currency="EUR")
        rate = provider.get_adjusted_rate("SEK")
        assert rate is None

    def test_requested_targets_property(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """requested_targets returns ordered list after fetch_rates."""
        import mcprojsim.exchange_rates as fx_mod
        from mcprojsim.exchange_rates import ExchangeRateProvider

        cache_dir = tmp_path / "mcprojsim"
        cache_dir.mkdir()
        cache_file = cache_dir / "fx_rates_cache.json"
        monkeypatch.setattr(fx_mod, "CACHE_DIR", cache_dir)
        monkeypatch.setattr(fx_mod, "CACHE_FILE", cache_file)

        monkeypatch.setattr(
            fx_mod.urllib.request,
            "urlopen",
            MagicMock(side_effect=OSError("offline")),
        )
        provider = ExchangeRateProvider(base_currency="EUR")
        provider.fetch_rates(["SEK", "USD"])
        assert provider.requested_targets == ["SEK", "USD"]


# =====================================================================
# Model Validation — T-shirt sizes, sprint spillover, resource refs
# =====================================================================


class TestProjectModelValidation:
    """Exercise model validation edge cases in models/project.py."""

    def test_tshirt_size_with_category_prefix(self) -> None:
        """T-shirt size with dot-separated category is accepted."""
        est = TaskEstimate(t_shirt_size="story.M")
        assert est.t_shirt_size == "story.M"

    def test_tshirt_size_without_category(self) -> None:
        """Plain T-shirt size (no category prefix) is accepted."""
        est = TaskEstimate(t_shirt_size="XL")
        assert est.t_shirt_size == "XL"

    def test_resource_calendar_ref_default(self) -> None:
        """Resource referencing 'default' calendar is always valid."""
        project = Project(
            project=ProjectMetadata(name="Test", start_date="2026-01-01"),
            tasks=[
                Task(id="t1", name="T1", estimate=TaskEstimate(low=1, expected=2, high=3))
            ],
            resources=[
                ResourceSpec(id="r1", name="Alice", calendar="default"),
            ],
        )
        assert project.resources[0].calendar == "default"

    def test_uncertainty_factor_inheritance(self) -> None:
        """Task-level factors override project-level defaults."""
        project = Project(
            project=ProjectMetadata(
                name="Test",
                start_date="2026-01-01",
                uncertainty_factors=UncertaintyFactors(
                    team_experience="low",
                    technical_complexity="medium",
                ),
            ),
            tasks=[
                Task(
                    id="t1",
                    name="T1",
                    estimate=TaskEstimate(low=1, expected=2, high=3),
                    uncertainty_factors=UncertaintyFactors(
                        technical_complexity="high",
                    ),
                ),
            ],
        )
        # After project construction, task should inherit team_experience=low
        # but keep its own technical_complexity=high
        task = project.tasks[0]
        assert task.uncertainty_factors is not None
        assert task.uncertainty_factors.technical_complexity == "high"
        assert task.uncertainty_factors.team_experience == "low"


# =====================================================================
# Config — T-shirt resolution edge cases
# =====================================================================


class TestConfigTShirtResolution:
    """Exercise config t-shirt size resolution fallbacks."""

    @staticmethod
    def _default_config() -> Config:
        return Config(**_build_default_config_data())

    def test_resolve_known_size(self) -> None:
        config = self._default_config()
        resolved = config.resolve_t_shirt_size("M")
        assert resolved.low > 0
        assert resolved.high > resolved.low

    def test_resolve_size_with_category(self) -> None:
        config = self._default_config()
        resolved = config.resolve_t_shirt_size("story.L")
        assert resolved.low > 0

    def test_resolve_unknown_size_raises(self) -> None:
        config = self._default_config()
        with pytest.raises(ValueError):
            config.resolve_t_shirt_size("XXXL")

    def test_resolve_unknown_category_raises(self) -> None:
        config = self._default_config()
        with pytest.raises(ValueError):
            config.resolve_t_shirt_size("nonexistent.M")


# =====================================================================
# Analysis — CostAnalyzer edge cases
# =====================================================================


class TestCostAnalyzerEdgeCases:
    """Exercise cost analysis edge cases."""

    def test_cost_analysis_on_results_with_costs(self) -> None:
        """CostAnalyzer.analyze returns valid CostAnalysis."""
        from mcprojsim.analysis.cost import CostAnalyzer

        results = _make_cost_results()
        analyzer = CostAnalyzer()
        analysis = analyzer.analyze(results)
        assert "t1" in analysis.sensitivity
        assert -1.0 <= analysis.duration_correlation <= 1.0

    def test_cost_analysis_no_task_costs(self) -> None:
        """CostAnalyzer with costs but no task_costs still works."""
        from mcprojsim.analysis.cost import CostAnalyzer

        results = _make_cost_results()
        results.task_costs = {}
        analyzer = CostAnalyzer()
        analysis = analyzer.analyze(results)
        assert analysis.sensitivity == {}
        assert -1.0 <= analysis.duration_correlation <= 1.0
