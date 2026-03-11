"""Tests for the MCP server tool functions.

These tests call the tool functions directly as regular Python functions,
bypassing MCP transport.
"""

from mcprojsim.mcp_server import (
    generate_project_file,
    simulate_project,
    validate_project_description,
)

import pytest

# The mcp package is an optional dependency – skip all tests when missing.
mcp = pytest.importorskip("mcp")


_SIMPLE_DESC = """\
Project name: MCP Test
Start date: 2026-06-01
Task 1:
- Design module
- Size: M
Task 2:
- Implement module
- Depends on Task 1
- Size: L
"""

_NO_NAME_DESC = """\
Task 1:
- Do something
- Size: S
"""


class TestGenerateProjectFile:
    """generate_project_file tool."""

    def test_returns_valid_yaml(self):
        import yaml

        output = generate_project_file(_SIMPLE_DESC)
        data = yaml.safe_load(output)
        assert "project" in data
        assert "tasks" in data
        assert data["project"]["name"] == "MCP Test"

    def test_preserves_dependencies(self):
        import yaml

        output = generate_project_file(_SIMPLE_DESC)
        data = yaml.safe_load(output)
        second_task = data["tasks"][1]
        assert second_task.get("dependencies"), "second task should have dependencies"

    def test_generates_two_tasks(self):
        import yaml

        output = generate_project_file(_SIMPLE_DESC)
        data = yaml.safe_load(output)
        assert len(data["tasks"]) == 2


class TestValidateProjectDescription:
    """validate_project_description tool."""

    def test_valid_description(self):
        result = validate_project_description(_SIMPLE_DESC)
        assert "Valid" in result or "WARNING" in result
        # Should not contain ERROR
        assert "ERROR" not in result

    def test_missing_name_warns(self):
        result = validate_project_description(_NO_NAME_DESC)
        assert "WARNING" in result
        assert "name" in result.lower()

    def test_missing_start_date_warns(self):
        result = validate_project_description(_NO_NAME_DESC)
        assert "start date" in result.lower()

    def test_missing_estimate_warns(self):
        desc = "Project name: Test\nTask 1:\n- No estimate task\n"
        result = validate_project_description(desc)
        assert "WARNING" in result or "estimate" in result.lower()

    def test_invalid_dependency_errors(self):
        desc = (
            "Project name: Bad Deps\n"
            "Task 1:\n- Alpha\n- Size: S\n- Depends on Task 5\n"
        )
        result = validate_project_description(desc)
        assert "ERROR" in result


class TestSimulateProject:
    """simulate_project tool."""

    def test_returns_simulation_results(self):
        result = simulate_project(_SIMPLE_DESC, iterations=100, seed=42)
        assert "Simulation Results" in result
        assert "MCP Test" in result

    def test_includes_confidence_intervals(self):
        result = simulate_project(_SIMPLE_DESC, iterations=100, seed=42)
        assert "Confidence Intervals" in result
        assert "P50" in result

    def test_includes_generated_yaml(self):
        result = simulate_project(_SIMPLE_DESC, iterations=100, seed=42)
        assert "Generated Project YAML" in result

    def test_includes_statistics(self):
        result = simulate_project(_SIMPLE_DESC, iterations=100, seed=42)
        assert "Mean:" in result
        assert "Std Dev:" in result
        assert "Skewness:" in result

    def test_seed_reproducibility(self):
        r1 = simulate_project(_SIMPLE_DESC, iterations=200, seed=99)
        r2 = simulate_project(_SIMPLE_DESC, iterations=200, seed=99)
        assert r1 == r2

    def test_custom_config_yaml(self):
        import yaml

        custom_cfg = yaml.safe_dump(
            {"t_shirt_sizes": {"M": {"min": 10, "most_likely": 20, "max": 30}}}
        )
        result = simulate_project(
            _SIMPLE_DESC, iterations=100, seed=42, config_yaml=custom_cfg
        )
        assert "Simulation Results" in result

    def test_includes_sensitivity(self):
        result = simulate_project(_SIMPLE_DESC, iterations=200, seed=42)
        assert "Sensitivity Analysis" in result or "Schedule Slack" in result
