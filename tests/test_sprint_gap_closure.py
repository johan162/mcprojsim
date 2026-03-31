"""Focused regressions for sprint-planning requirement gap closures."""

from mcprojsim.parsers import TOMLParser, YAMLParser


class TestSprintGapClosure:
    """Targeted tests for the final sprint-planning compliance gaps."""

    def test_yaml_reports_future_overrides_must_be_list(self, tmp_path) -> None:
        """future_sprint_overrides should fail when not provided as a list."""
        file_path = tmp_path / "invalid_override_shape.yaml"
        file_path.write_text("""
project:
  name: Example
  start_date: 2025-01-01
sprint_planning:
  enabled: true
  sprint_length_weeks: 2
  capacity_mode: story_points
  future_sprint_overrides:
    sprint_number: 2
    holiday_factor: 0.8
  history:
    - sprint_id: SPR-001
      completed_story_points: 10
    - sprint_id: SPR-002
      completed_story_points: 8
tasks:
  - id: task_001
    name: Task 1
    planning_story_points: 3
    estimate:
      low: 1
      expected: 2
      high: 5
""".strip())

        is_valid, error = YAMLParser().validate_file(file_path)

        assert not is_valid
        assert "future_sprint_overrides" in error
        assert "must be a list" in error

    def test_yaml_reports_invalid_future_override_values(self, tmp_path) -> None:
        """Override entries with invalid multiplier values should report source errors."""
        file_path = tmp_path / "invalid_override_values.yaml"
        file_path.write_text("""
project:
  name: Example
  start_date: 2025-01-01
sprint_planning:
  enabled: true
  sprint_length_weeks: 2
  capacity_mode: story_points
  future_sprint_overrides:
    - sprint_number: 2
      holiday_factor: 0
      capacity_multiplier: bad
  history:
    - sprint_id: SPR-001
      completed_story_points: 10
    - sprint_id: SPR-002
      completed_story_points: 8
tasks:
  - id: task_001
    name: Task 1
    planning_story_points: 3
    estimate:
      low: 1
      expected: 2
      high: 5
""".strip())

        is_valid, error = YAMLParser().validate_file(file_path)

        assert not is_valid
        assert "holiday_factor" in error
        assert "capacity_multiplier" in error
        assert "greater than 0" in error

    def test_yaml_reports_conflicting_future_override_locators(self, tmp_path) -> None:
        """Future override locator conflicts should surface as source-aware errors."""
        file_path = tmp_path / "invalid_override.yaml"
        file_path.write_text("""
project:
  name: Example
  start_date: 2025-01-01
sprint_planning:
  enabled: true
  sprint_length_weeks: 2
  capacity_mode: story_points
  future_sprint_overrides:
    - sprint_number: 2
      start_date: 2025-01-01
      holiday_factor: 0.8
  history:
    - sprint_id: SPR-001
      completed_story_points: 10
    - sprint_id: SPR-002
      completed_story_points: 8
tasks:
  - id: task_001
    name: Task 1
    planning_story_points: 3
    estimate:
      low: 1
      expected: 2
      high: 5
""".strip())

        is_valid, error = YAMLParser().validate_file(file_path)

        assert not is_valid
        assert "line 10" in error
        assert "resolve to the same sprint" in error

    def test_yaml_reports_spillover_bracket_ordering(self, tmp_path) -> None:
        """Spillover bracket ordering errors should preserve source locations."""
        file_path = tmp_path / "invalid_brackets.yaml"
        file_path.write_text("""
project:
  name: Example
  start_date: 2025-01-01
sprint_planning:
  enabled: true
  sprint_length_weeks: 2
  capacity_mode: story_points
  spillover:
    enabled: true
    size_brackets:
      - max_points: 5
        probability: 0.2
      - max_points: 4
        probability: 0.3
  history:
    - sprint_id: SPR-001
      completed_story_points: 10
    - sprint_id: SPR-002
      completed_story_points: 8
tasks:
  - id: task_001
    name: Task 1
    planning_story_points: 3
    estimate:
      low: 1
      expected: 2
      high: 5
""".strip())

        is_valid, error = YAMLParser().validate_file(file_path)

        assert not is_valid
        assert "line 13" in error
        assert "strictly ascending" in error

    def test_toml_reports_unbounded_spillover_bracket_not_last(self, tmp_path) -> None:
        """TOML raw validation should flag size brackets after an unbounded bracket."""
        file_path = tmp_path / "invalid_spillover_brackets.toml"
        file_path.write_text("""
[project]
name = "Example"
start_date = "2025-01-01"

[sprint_planning]
enabled = true
sprint_length_weeks = 2
capacity_mode = "story_points"

[sprint_planning.spillover]
enabled = true

[[sprint_planning.spillover.size_brackets]]
probability = 0.2

[[sprint_planning.spillover.size_brackets]]
max_points = 5
probability = 0.3

[[sprint_planning.history]]
sprint_id = "SPR-001"
completed_story_points = 10

[[sprint_planning.history]]
sprint_id = "SPR-002"
completed_story_points = 8

[[tasks]]
id = "task_001"
name = "Task"
planning_story_points = 3

[tasks.estimate]
low = 1
expected = 2
high = 3
""".strip())

        is_valid, error = TOMLParser().validate_file(file_path)

        assert not is_valid
        assert "line 13" in error
        assert "unbounded bracket last" in error
