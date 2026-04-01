"""Tests for the natural language project description parser."""

from __future__ import annotations

import pytest
import yaml

from mcprojsim.nl_parser import NLProjectParser


class TestNLProjectParserParsing:
    """Tests for the parse() method."""

    def setup_method(self) -> None:
        self.parser = NLProjectParser()

    def test_parse_user_example(self) -> None:
        """Parse the exact example from the user's request."""
        text = """
Project name: Rework Web Interface
Start date: 2026-06-02
Task 1:
- Analyse existing UI
- Size: M
Task 2:
- Refine requirements
- Depends on Task1
- Size XL
Task 3:
- Design solution
- Depends on Task 2
- Size. XL
"""
        project = self.parser.parse(text)

        assert project.name == "Rework Web Interface"
        assert project.start_date == "2026-06-02"
        assert len(project.tasks) == 3

        assert project.tasks[0].number == 1
        assert project.tasks[0].name == "Analyse existing UI"
        assert project.tasks[0].t_shirt_size == "M"
        assert project.tasks[0].dependency_refs == []

        assert project.tasks[1].number == 2
        assert project.tasks[1].name == "Refine requirements"
        assert project.tasks[1].t_shirt_size == "XL"
        assert project.tasks[1].dependency_refs == ["1"]

        assert project.tasks[2].number == 3
        assert project.tasks[2].name == "Design solution"
        assert project.tasks[2].t_shirt_size == "XL"
        assert project.tasks[2].dependency_refs == ["2"]

    def test_project_name_variants(self) -> None:
        """Project name with different separators."""
        for line in [
            "Project name: Alpha",
            "Project: Alpha",
            "project name= Alpha",
        ]:
            text = f"{line}\nTask 1:\n- Work\n- Size: S"
            assert self.parser.parse(text).name == "Alpha"

    def test_missing_project_name_defaults(self) -> None:
        text = "Task 1:\n- Something\n- Size: M"
        assert self.parser.parse(text).name == "Untitled Project"

    def test_start_date_parsed(self) -> None:
        text = "Start date: 2026-12-25\nTask 1:\n- Work\n- Size: S"
        assert self.parser.parse(text).start_date == "2026-12-25"

    def test_description_parsed(self) -> None:
        text = (
            "Project: Test\n"
            "Description: A very important project\n"
            "Task 1:\n- Work\n- Size: S"
        )
        assert self.parser.parse(text).description == "A very important project"

    def test_hours_per_day(self) -> None:
        text = "Hours per day: 6.5\nTask 1:\n- Work\n- Size: M"
        assert self.parser.parse(text).hours_per_day == 6.5

    def test_confidence_levels(self) -> None:
        text = "Confidence levels: 50, 90, 95\nTask 1:\n- Work\n- Size: M"
        assert self.parser.parse(text).confidence_levels == [50, 90, 95]


class TestNLProjectParserTasks:
    """Tests for task-level parsing."""

    def setup_method(self) -> None:
        self.parser = NLProjectParser()

    def test_inline_task_name(self) -> None:
        text = "Task 1: Setup infrastructure\n- Size: L"
        assert self.parser.parse(text).tasks[0].name == "Setup infrastructure"

    def test_task_name_from_bullet(self) -> None:
        """Task name specified as a bullet point with 'name:' pattern."""
        text = "Task 1:\n- name: Analyze Requirements\n- Size: L"
        assert self.parser.parse(text).tasks[0].name == "Analyze Requirements"

    def test_task_name_from_bullet_no_colon(self) -> None:
        """Task name specified as a bullet point with 'name' (no colon)."""
        text = "Task 1:\n- name Analyze Requirements\n- Size: L"
        assert self.parser.parse(text).tasks[0].name == "Analyze Requirements"

    def test_default_task_name(self) -> None:
        text = "Task 1:\n- Size: M"
        assert self.parser.parse(text).tasks[0].name == "Task 1"

    def test_task_description_bullet(self) -> None:
        text = "Task 1:\n- Build feature\n- Extra context here\n- Size: M"
        task = self.parser.parse(text).tasks[0]
        assert task.name == "Build feature"
        assert task.description == "Extra context here"

    def test_no_tasks_raises(self) -> None:
        with pytest.raises(ValueError, match="No tasks found"):
            self.parser.parse("Project name: Empty")

    def test_size_with_colon(self) -> None:
        text = "Task 1:\n- Work\n- Size: M"
        assert self.parser.parse(text).tasks[0].t_shirt_size == "M"

    def test_size_without_colon(self) -> None:
        text = "Task 1:\n- Work\n- Size XL"
        assert self.parser.parse(text).tasks[0].t_shirt_size == "XL"

    def test_size_with_period(self) -> None:
        text = "Task 1:\n- Work\n- Size. XL"
        assert self.parser.parse(text).tasks[0].t_shirt_size == "XL"

    @pytest.mark.parametrize(
        "size_str,expected",
        [
            ("XS", "XS"),
            ("S", "S"),
            ("M", "M"),
            ("L", "L"),
            ("XL", "XL"),
            ("XXL", "XXL"),
            ("Medium", "M"),
            ("Large", "L"),
            ("Small", "S"),
            ("Extra Large", "XL"),
            ("extra small", "XS"),
        ],
    )
    def test_size_aliases(self, size_str: str, expected: str) -> None:
        text = f"Task 1:\n- Test\n- Size: {size_str}"
        assert self.parser.parse(text).tasks[0].t_shirt_size == expected

    def test_story_points(self) -> None:
        text = "Task 1:\n- User story\n- Story points: 5"
        assert self.parser.parse(text).tasks[0].story_points == 5

    def test_points_without_story_prefix(self) -> None:
        text = "Task 1:\n- Work\n- Points: 8"
        assert self.parser.parse(text).tasks[0].story_points == 8

    def test_explicit_estimate(self) -> None:
        text = "Task 1:\n- Development\n- Estimate: 3/5/10 days"
        task = self.parser.parse(text).tasks[0]
        assert task.low_estimate == 3.0
        assert task.expected_estimate == 5.0
        assert task.high_estimate == 10.0
        assert task.estimate_unit == "days"

    def test_explicit_estimate_hours(self) -> None:
        text = "Task 1:\n- Work\n- Estimate: 4/8/16 hours"
        assert self.parser.parse(text).tasks[0].estimate_unit == "hours"

    def test_explicit_estimate_dash_separator(self) -> None:
        text = "Task 1:\n- Work\n- Estimate: 2-4-8"
        task = self.parser.parse(text).tasks[0]
        assert task.low_estimate == 2.0
        assert task.expected_estimate == 4.0
        assert task.high_estimate == 8.0

    def test_single_dependency(self) -> None:
        text = "Task 1:\n- A\n- Size: S\nTask 2:\n- B\n- Depends on Task 1\n- Size: M"
        assert self.parser.parse(text).tasks[1].dependency_refs == ["1"]

    def test_dependency_no_space(self) -> None:
        """'Task1' without space between 'Task' and '1'."""
        text = "Task 1:\n- A\n- Size: S\nTask 2:\n- B\n- Depends on Task1\n- Size: M"
        assert self.parser.parse(text).tasks[1].dependency_refs == ["1"]

    def test_multiple_dependencies_and_keyword(self) -> None:
        text = (
            "Task 1:\n- A\n- Size: S\n"
            "Task 2:\n- B\n- Size: S\n"
            "Task 3:\n- C\n- Depends on Task 1 and Task 2\n- Size: M"
        )
        assert set(self.parser.parse(text).tasks[2].dependency_refs) == {
            "1",
            "2",
        }

    def test_multiple_dependencies_comma(self) -> None:
        text = (
            "Task 1:\n- A\n- Size: S\n"
            "Task 2:\n- B\n- Size: S\n"
            "Task 3:\n- C\n- Depends on Task 1, Task 2\n- Size: M"
        )
        assert set(self.parser.parse(text).tasks[2].dependency_refs) == {
            "1",
            "2",
        }

    def test_blank_lines_ignored(self) -> None:
        text = "Task 1:\n\n- Work\n\n- Size: M\n\n"
        project = self.parser.parse(text)
        assert len(project.tasks) == 1
        assert project.tasks[0].t_shirt_size == "M"


class TestNLProjectParserDates:
    """Tests for date extraction and range expansion."""

    def setup_method(self) -> None:
        self.parser = NLProjectParser(current_year=2026)

    def test_calendar_holiday_iso_range_expands(self) -> None:
        text = (
            "Task 1:\n- Work\n- Size: S\nCalendar:\n- Holiday: 2026-03-19 to 2026-03-21"
        )
        project = self.parser.parse(text)

        assert project.calendars[0].holidays == [
            "2026-03-19",
            "2026-03-20",
            "2026-03-21",
        ]

    def test_calendar_holiday_compact_range_expands(self) -> None:
        text = "Task 1:\n- Work\n- Size: S\nCalendar:\n- Holidays: 20260319 - 20260321"
        project = self.parser.parse(text)

        assert project.calendars[0].holidays == [
            "2026-03-19",
            "2026-03-20",
            "2026-03-21",
        ]

    def test_calendar_holiday_day_month_range_uses_current_year(self) -> None:
        text = "Task 1:\n- Work\n- Size: S\nCalendar:\n- Holiday: 19 Mar to 21 Mar"
        project = self.parser.parse(text)

        assert project.calendars[0].holidays == [
            "2026-03-19",
            "2026-03-20",
            "2026-03-21",
        ]

    def test_resource_absence_range_expands(self) -> None:
        text = (
            "Task 1:\n- Work\n- Size: S\n"
            "Resource 1: Alice\n- Absence: 2026-04-01 to 2026-04-03"
        )
        project = self.parser.parse(text)

        assert project.resources[0].planned_absence == [
            "2026-04-01",
            "2026-04-02",
            "2026-04-03",
        ]

    def test_extract_dates_keeps_single_dates_and_ranges(self) -> None:
        assert self.parser._extract_dates(
            "2026-03-19 to 2026-03-20, 20260322, 24 Mar"
        ) == [
            "2026-03-19",
            "2026-03-20",
            "2026-03-22",
            "2026-03-24",
        ]


class TestNLProjectParserYAML:
    """Tests for YAML generation."""

    def setup_method(self) -> None:
        self.parser = NLProjectParser()

    def test_yaml_is_valid(self) -> None:
        text = (
            "Project name: Test\nStart date: 2026-01-01\n"
            "Task 1:\n- Setup\n- Size: S\n"
            "Task 2:\n- Build\n- Depends on Task 1\n- Size: L"
        )
        yaml_str = self.parser.parse_and_generate(text)
        data = yaml.safe_load(yaml_str)

        assert data["project"]["name"] == "Test"
        assert data["project"]["start_date"] == "2026-01-01"
        assert len(data["tasks"]) == 2

    def test_yaml_task_ids(self) -> None:
        text = "Task 1:\n- A\n- Size: S\nTask 2:\n- B\n- Size: M"
        data = yaml.safe_load(self.parser.parse_and_generate(text))
        assert data["tasks"][0]["id"] == "task_001"
        assert data["tasks"][1]["id"] == "task_002"

    def test_yaml_t_shirt_estimate(self) -> None:
        text = "Task 1:\n- Work\n- Size: XL"
        data = yaml.safe_load(self.parser.parse_and_generate(text))
        assert data["tasks"][0]["estimate"]["t_shirt_size"] == "XL"

    def test_yaml_story_points_estimate(self) -> None:
        text = "Task 1:\n- Work\n- Story points: 8"
        data = yaml.safe_load(self.parser.parse_and_generate(text))
        assert data["tasks"][0]["estimate"]["story_points"] == 8

    def test_yaml_explicit_estimate(self) -> None:
        text = "Task 1:\n- Work\n- Estimate: 3/5/10 days"
        data = yaml.safe_load(self.parser.parse_and_generate(text))
        est = data["tasks"][0]["estimate"]
        assert est["low"] == 3
        assert est["expected"] == 5
        assert est["high"] == 10
        assert est["unit"] == "days"

    def test_yaml_dependencies_mapped(self) -> None:
        text = (
            "Task 1:\n- A\n- Size: S\n" "Task 2:\n- B\n- Depends on Task 1\n- Size: M"
        )
        data = yaml.safe_load(self.parser.parse_and_generate(text))
        assert data["tasks"][0]["dependencies"] == []
        assert data["tasks"][1]["dependencies"] == ["task_001"]

    def test_yaml_confidence_levels(self) -> None:
        text = "Task 1:\n- Work\n- Size: M"
        data = yaml.safe_load(self.parser.parse_and_generate(text))
        assert data["project"]["confidence_levels"] == [50, 80, 90, 95]

    def test_yaml_special_chars_escaped(self) -> None:
        text = 'Task 1:\n- Fix "broken" feature\n- Size: M'
        yaml_str = self.parser.parse_and_generate(text)
        data = yaml.safe_load(yaml_str)
        assert '"broken"' in data["tasks"][0]["name"]

    def test_yaml_no_estimate_omits_section(self) -> None:
        text = "Task 1:\n- Work without estimate"
        data = yaml.safe_load(self.parser.parse_and_generate(text))
        assert "estimate" not in data["tasks"][0]

    def test_yaml_hours_per_day_included(self) -> None:
        text = "Hours per day: 6\nTask 1:\n- Work\n- Size: M"
        data = yaml.safe_load(self.parser.parse_and_generate(text))
        assert data["project"]["hours_per_day"] == 6

    def test_yaml_hours_per_day_omitted_when_default(self) -> None:
        text = "Task 1:\n- Work\n- Size: M"
        data = yaml.safe_load(self.parser.parse_and_generate(text))
        assert "hours_per_day" not in data["project"]

    def test_full_roundtrip_user_example(self) -> None:
        """Full roundtrip of the user's example produces loadable YAML."""
        text = """
Project name: Rework Web Interface
Start date: 2026-06-02
Task 1:
- Analyse existing UI
- Size: M
Task 2:
- Refine requirements
- Depends on Task1
- Size XL
Task 3:
- Design solution
- Depends on Task 2
- Size. XL
"""
        yaml_str = self.parser.parse_and_generate(text)
        data = yaml.safe_load(yaml_str)

        assert data["project"]["name"] == "Rework Web Interface"
        assert data["project"]["start_date"] == "2026-06-02"
        assert len(data["tasks"]) == 3

        # Task 1
        t1 = data["tasks"][0]
        assert t1["id"] == "task_001"
        assert t1["name"] == "Analyse existing UI"
        assert t1["estimate"]["t_shirt_size"] == "M"
        assert t1["dependencies"] == []

        # Task 2
        t2 = data["tasks"][1]
        assert t2["id"] == "task_002"
        assert t2["name"] == "Refine requirements"
        assert t2["estimate"]["t_shirt_size"] == "XL"
        assert t2["dependencies"] == ["task_001"]

        # Task 3
        t3 = data["tasks"][2]
        assert t3["id"] == "task_003"
        assert t3["name"] == "Design solution"
        assert t3["estimate"]["t_shirt_size"] == "XL"
        assert t3["dependencies"] == ["task_002"]

    def test_parse_sprint_planning_and_history(self) -> None:
        text = (
            "Project: Sprint NL\n"
            "Start date: 2026-01-01\n"
            "Task 1:\n- Story\n- Story points: 5\n"
            "Sprint planning:\n"
            "- Sprint length: 2\n"
            "- Capacity mode: story points\n"
            "- Planning confidence level: 80%\n"
            "Sprint history SPR-001:\n"
            "- Done: 20 points\n"
            "- Carryover: 3 points\n"
            "- Scope added: 2 points\n"
            "- Scope removed: 1 points\n"
            "- Holiday factor: 90%\n"
            "Sprint history SPR-002:\n"
            "- Delivered: 18 points\n"
            "- Rolled over: 2 points"
        )

        project = self.parser.parse(text)

        assert project.sprint_planning is not None
        assert project.sprint_planning.capacity_mode == "story_points"
        assert project.sprint_planning.planning_confidence_level == pytest.approx(0.8)
        assert len(project.sprint_planning.history) == 2
        assert project.sprint_planning.history[
            0
        ].completed_story_points == pytest.approx(20.0)
        assert project.sprint_planning.history[
            0
        ].spillover_story_points == pytest.approx(3.0)
        assert project.sprint_planning.history[0].holiday_factor == pytest.approx(0.9)

    def test_yaml_includes_sprint_planning_section(self) -> None:
        text = (
            "Project: Sprint YAML\n"
            "Task 1:\n- Story\n- Story points: 3\n"
            "Sprint planning:\n- Sprint length: 2\n- Capacity mode: story points\n"
            "Sprint history S1:\n- Done: 10 points\n- Carryover: 1 points"
        )

        data = yaml.safe_load(self.parser.parse_and_generate(text))

        assert data["sprint_planning"]["enabled"] is True
        assert data["sprint_planning"]["capacity_mode"] == "story_points"
        assert data["sprint_planning"]["history"][0]["sprint_id"] == "S1"
        assert data["sprint_planning"]["history"][0]["spillover_story_points"] == 1

    def test_parse_sprint_removed_work_aliases(self) -> None:
        text = (
            "Project: Alias Test\n"
            "Task 1:\n- Story\n- Story points: 3\n"
            "Sprint planning:\n"
            "- Removed work treatment: churn only\n"
            "Sprint history S1:\n- Done: 10 points\n"
        )
        project = self.parser.parse(text)
        assert project.sprint_planning is not None
        assert project.sprint_planning.removed_work_treatment == "churn_only"

    def test_parse_sprint_velocity_model_alias(self) -> None:
        text = (
            "Project: Velocity Test\n"
            "Task 1:\n- Story\n- Story points: 3\n"
            "Sprint planning:\n"
            "- Velocity model: negative binomial\n"
            "Sprint history S1:\n- Done: 10 points\n"
        )
        project = self.parser.parse(text)
        assert project.sprint_planning is not None
        assert project.sprint_planning.velocity_model == "neg_binomial"

    def test_parse_future_sprint_override(self) -> None:
        text = (
            "Project: Override Test\n"
            "Task 1:\n- Story\n- Story points: 3\n"
            "Sprint planning:\n"
            "- Sprint length: 2\n"
            "Sprint history S1:\n- Done: 10 points\n"
            "Future sprint override 4:\n"
            "- Holiday factor: 80%\n"
            "- Capacity multiplier: 0.9\n"
            "- Notes: Public holiday sprint\n"
        )
        project = self.parser.parse(text)
        assert project.sprint_planning is not None
        assert len(project.sprint_planning.future_sprint_overrides) == 1
        override = project.sprint_planning.future_sprint_overrides[0]
        assert override.sprint_number == 4
        assert override.holiday_factor == pytest.approx(0.8)
        assert override.capacity_multiplier == pytest.approx(0.9)

    def test_yaml_includes_future_overrides_and_sickness(self) -> None:
        text = (
            "Project: Sprint YAML+\n"
            "Task 1:\n- Story\n- Story points: 3\n"
            "Sprint planning:\n"
            "- Velocity model: empirical\n"
            "- Sickness: enabled\n"
            "- Sickness team size: 5\n"
            "Sprint history S1:\n- Done: 10 points\n"
            "Future sprint override 3:\n"
            "- Holiday factor: 0.8\n"
        )

        data = yaml.safe_load(self.parser.parse_and_generate(text))
        sprint = data["sprint_planning"]
        assert sprint["velocity_model"] == "empirical"
        assert sprint["sickness"]["enabled"] is True
        assert sprint["sickness"]["team_size"] == 5
        assert sprint["future_sprint_overrides"][0]["sprint_number"] == 3
        assert sprint["future_sprint_overrides"][0]["holiday_factor"] == 0.8
