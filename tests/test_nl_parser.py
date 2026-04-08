"""Tests for the natural language project description parser."""

from __future__ import annotations

from datetime import date

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


class TestRelativeStartDates:
    """Tests for relative project start-date parsing."""

    def setup_method(self) -> None:
        self.parser = NLProjectParser(today=date(2026, 4, 8))

    def test_start_date_next_monday(self) -> None:
        text = "Start date: next Monday\nTask 1:\n- Work\n- Size: S"
        assert self.parser.parse(text).start_date == "2026-04-13"

    def test_starting_in_two_weeks(self) -> None:
        text = "Starting in 2 weeks\nTask 1:\n- Work\n- Size: S"
        assert self.parser.parse(text).start_date == "2026-04-22"

    def test_starting_in_five_days(self) -> None:
        text = "Starting in 5 days\nTask 1:\n- Work\n- Size: S"
        assert self.parser.parse(text).start_date == "2026-04-13"

    def test_start_date_beginning_of_may(self) -> None:
        text = "Start date: beginning of May\nTask 1:\n- Work\n- Size: S"
        assert self.parser.parse(text).start_date == "2026-05-01"

    def test_start_date_beginning_of_next_month(self) -> None:
        text = "Start date: beginning of next month\nTask 1:\n- Work\n- Size: S"
        assert self.parser.parse(text).start_date == "2026-05-01"

    def test_start_date_month_and_year(self) -> None:
        text = "Start date: May 2026\nTask 1:\n- Work\n- Size: S"
        assert self.parser.parse(text).start_date == "2026-05-01"

    def test_iso_start_date_still_parses(self) -> None:
        text = "Start date: 2026-06-02\nTask 1:\n- Work\n- Size: S"
        assert self.parser.parse(text).start_date == "2026-06-02"


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


class TestAutoTaskDetection:
    """Tests for auto-task detection from unnumbered/plain lists (Item 1)."""

    def setup_method(self) -> None:
        self.parser = NLProjectParser()

    # -- AC 1: Plain numbered list produces one ParsedTask per item ----------

    def test_plain_numbered_dot_list(self) -> None:
        text = """
Project name: Test
1. Design database schema
2. Implement REST API
3. Frontend integration testing
4. Deployment and smoke tests
"""
        project = self.parser.parse(text)
        assert len(project.tasks) == 4
        assert project.tasks[0].name == "Design database schema"
        assert project.tasks[1].name == "Implement REST API"
        assert project.tasks[2].name == "Frontend integration testing"
        assert project.tasks[3].name == "Deployment and smoke tests"

    def test_plain_numbered_paren_list(self) -> None:
        text = """
Project name: Test
1) Authentication module
2) User management
3) Reporting
"""
        project = self.parser.parse(text)
        assert len(project.tasks) == 3
        assert project.tasks[0].name == "Authentication module"
        assert project.tasks[1].name == "User management"
        assert project.tasks[2].name == "Reporting"

    def test_bracket_numbered_list(self) -> None:
        text = """
Project name: Test
[1] Authentication
[2] User management
[3] Reporting module
"""
        project = self.parser.parse(text)
        assert len(project.tasks) == 3
        assert project.tasks[0].name == "Authentication"
        assert project.tasks[1].name == "User management"
        assert project.tasks[2].name == "Reporting module"

    # -- AC 2: Task numbers preserved from source numbering ------------------

    def test_numbered_list_preserves_numbers(self) -> None:
        text = """
Project name: Test
1. First task
2. Second task
3. Third task
"""
        project = self.parser.parse(text)
        assert project.tasks[0].number == 1
        assert project.tasks[1].number == 2
        assert project.tasks[2].number == 3

    def test_bullet_list_auto_numbers(self) -> None:
        text = """
Project name: Test
- Discovery and requirements
- Database design
- Backend implementation
- Frontend
- QA
- Deployment
"""
        project = self.parser.parse(text)
        assert len(project.tasks) == 6
        assert project.tasks[0].number == 1
        assert project.tasks[0].name == "Discovery and requirements"
        assert project.tasks[1].number == 2
        assert project.tasks[2].number == 3
        assert project.tasks[3].number == 4
        assert project.tasks[4].number == 5
        assert project.tasks[5].number == 6

    def test_asterisk_bullet_list(self) -> None:
        text = """
Project name: Test
* Design phase
* Implementation
* Testing
"""
        project = self.parser.parse(text)
        assert len(project.tasks) == 3
        assert project.tasks[0].name == "Design phase"

    def test_unicode_bullet_list(self) -> None:
        text = """
Project name: Test
• Design phase
• Implementation
• Testing
"""
        project = self.parser.parse(text)
        assert len(project.tasks) == 3

    def test_hash_numbered_list(self) -> None:
        text = """
Project name: Test
# 1 First task
# 2 Second task
"""
        project = self.parser.parse(text)
        assert len(project.tasks) == 2
        assert project.tasks[0].number == 1
        assert project.tasks[0].name == "First task"

    # -- AC 6: Mixing explicit Task N: with plain bullets disables auto-task --

    def test_explicit_tasks_disable_auto_task(self) -> None:
        text = """
Project name: Test
Task 1: Real task
- Size: M
- some extra bullet line that looks like a list item
"""
        project = self.parser.parse(text)
        assert len(project.tasks) == 1
        assert project.tasks[0].name == "Real task"
        assert project.tasks[0].t_shirt_size == "M"

    def test_explicit_and_plain_bullets_no_auto(self) -> None:
        """When Task N: headers appear, plain bullets are NOT auto-tasks."""
        text = """
Project name: Test
Task 1: Design
- Size: M
Task 2: Implementation
- Size: L
- Not a new task
"""
        project = self.parser.parse(text)
        assert len(project.tasks) == 2

    # -- AC 7: Indented continuation lines under auto-task bullets -----------

    def test_continuation_lines_under_numbered(self) -> None:
        text = """
Project name: Test
1. Design database schema
  Size: M
2. Implement REST API
  Size: XL
  Depends on Task 1
"""
        project = self.parser.parse(text)
        assert len(project.tasks) == 2
        assert project.tasks[0].t_shirt_size == "M"
        assert project.tasks[1].t_shirt_size == "XL"
        assert project.tasks[1].dependency_refs == ["1"]

    def test_continuation_lines_under_bullets(self) -> None:
        text = """
Project name: Test
- Design phase
  Size: M
- Implementation
  Size: L
  Estimate: 3/5/10 days
"""
        project = self.parser.parse(text)
        assert len(project.tasks) == 2
        assert project.tasks[0].t_shirt_size == "M"
        assert project.tasks[1].t_shirt_size == "L"
        assert project.tasks[1].low_estimate == pytest.approx(3.0)

    def test_auto_task_with_project_metadata(self) -> None:
        """Auto-task lines work alongside project metadata."""
        text = """
Project name: My Project
Start date: 2026-01-15
1. Design phase
2. Implementation
"""
        project = self.parser.parse(text)
        assert project.name == "My Project"
        assert project.start_date == "2026-01-15"
        assert len(project.tasks) == 2

    def test_auto_task_yaml_roundtrip(self) -> None:
        """Auto-detected tasks produce valid YAML output."""
        text = """
Project name: Test
1. Design
2. Implementation
3. Testing
"""
        yaml_str = self.parser.parse_and_generate(text)
        data = yaml.safe_load(yaml_str)
        assert len(data["tasks"]) == 3
        assert data["tasks"][0]["id"] == "task_001"
        assert data["tasks"][0]["name"] == "Design"


class TestInlinePropertyExtraction:
    """Tests for inline property extraction on auto-task lines (Item 1, AC 3-5)."""

    def setup_method(self) -> None:
        self.parser = NLProjectParser()

    # -- AC 3: Bracketed/parenthesized size on task name line ----------------

    def test_bracket_size_on_numbered_item(self) -> None:
        text = """
Project name: Test
1. Backend API [XL]
2. Frontend [M]
3. QA [S]
"""
        project = self.parser.parse(text)
        assert project.tasks[0].t_shirt_size == "XL"
        assert project.tasks[1].t_shirt_size == "M"
        assert project.tasks[2].t_shirt_size == "S"
        # Size token stripped from name
        assert "XL" not in project.tasks[0].name
        assert "Backend API" in project.tasks[0].name

    def test_paren_size_on_bullet_item(self) -> None:
        text = """
Project name: Test
- Backend API (XL)
- Frontend (M)
"""
        project = self.parser.parse(text)
        assert project.tasks[0].t_shirt_size == "XL"
        assert project.tasks[1].t_shirt_size == "M"

    def test_paren_size_lowercase(self) -> None:
        text = """
Project name: Test
- Backend (xl)
- Frontend (m)
"""
        project = self.parser.parse(text)
        assert project.tasks[0].t_shirt_size == "XL"
        assert project.tasks[1].t_shirt_size == "M"

    # -- AC 5: Inline estimate ranges ----------------------------------------

    def test_inline_range_on_task_line(self) -> None:
        """'3–5 days' on task line → low=3, expected=4, high=5, unit=days."""
        text = """
Project name: Test
- QA: 3–5 days
"""
        project = self.parser.parse(text)
        assert project.tasks[0].low_estimate == pytest.approx(3.0)
        assert project.tasks[0].expected_estimate == pytest.approx(4.0)
        assert project.tasks[0].high_estimate == pytest.approx(5.0)
        assert project.tasks[0].estimate_unit == "days"

    def test_inline_range_hours(self) -> None:
        text = """
Project name: Test
1. Quick fix 2-4 hours
"""
        project = self.parser.parse(text)
        assert project.tasks[0].low_estimate == pytest.approx(2.0)
        assert project.tasks[0].high_estimate == pytest.approx(4.0)
        assert project.tasks[0].estimate_unit == "hours"

    def test_inline_range_weeks(self) -> None:
        text = """
Project name: Test
- Backend migration 2–4 weeks
"""
        project = self.parser.parse(text)
        assert project.tasks[0].low_estimate == pytest.approx(2.0)
        assert project.tasks[0].high_estimate == pytest.approx(4.0)
        assert project.tasks[0].estimate_unit == "weeks"

    def test_inline_range_with_to(self) -> None:
        """'3 to 5 days' also works."""
        text = """
Project name: Test
- Implementation 3 to 5 days
"""
        project = self.parser.parse(text)
        assert project.tasks[0].low_estimate == pytest.approx(3.0)
        assert project.tasks[0].high_estimate == pytest.approx(5.0)

    def test_inline_qualified_point_estimate(self) -> None:
        text = """
Project name: Test
- Quick fix about 10 hours
"""
        project = self.parser.parse(text)
        assert project.tasks[0].low_estimate == pytest.approx(7.0)
        assert project.tasks[0].expected_estimate == pytest.approx(10.0)
        assert project.tasks[0].high_estimate == pytest.approx(18.0)
        assert project.tasks[0].estimate_unit == "hours"

    def test_inline_point_estimate_in_weeks(self) -> None:
        text = """
Project name: Test
1. Frontend integration around 3 weeks
"""
        project = self.parser.parse(text)
        assert project.tasks[0].low_estimate == 2.1
        assert project.tasks[0].expected_estimate == pytest.approx(3.0)
        assert project.tasks[0].high_estimate == 5.4
        assert project.tasks[0].estimate_unit == "weeks"

    def test_inline_range_does_not_parse_date_fragment(self) -> None:
        text = """
Project name: Test
- Release train for 2026-04 planning
"""
        project = self.parser.parse(text)
        assert project.tasks[0].low_estimate is None
        assert project.tasks[0].expected_estimate is None
        assert project.tasks[0].high_estimate is None

    def test_inline_point_does_not_parse_version_number(self) -> None:
        text = """
Project name: Test
- Upgrade service to v2.4
"""
        project = self.parser.parse(text)
        assert project.tasks[0].low_estimate is None
        assert project.tasks[0].expected_estimate is None
        assert project.tasks[0].high_estimate is None

    # -- Inline dependency on task line --------------------------------------

    def test_inline_depends_on_task_line(self) -> None:
        text = """
Project name: Test
1. Design database schema
2. Implement REST API depends on Task 1
"""
        project = self.parser.parse(text)
        assert project.tasks[1].dependency_refs == ["1"]


class TestFuzzyDurations:
    """Tests for fuzzy natural duration phrase parsing."""

    def setup_method(self) -> None:
        self.parser = NLProjectParser(today=date(2026, 4, 8))

    def test_couple_of_days_maps_to_small(self) -> None:
        text = """
Project name: Test
- Quick patch takes a couple of days
"""
        project = self.parser.parse(text)
        assert project.tasks[0].t_shirt_size == "S"

    def test_about_a_week_maps_to_medium(self) -> None:
        text = """
Project name: Test
- Design database schema about a week
"""
        project = self.parser.parse(text)
        assert project.tasks[0].t_shirt_size == "M"

    def test_a_few_weeks_maps_to_large(self) -> None:
        text = """
Project name: Test
- Frontend integration will take a few weeks
"""
        project = self.parser.parse(text)
        assert project.tasks[0].t_shirt_size == "L"

    def test_month_or_so_maps_to_large(self) -> None:
        text = """
Project name: Test
- Migration effort is a month or so
"""
        project = self.parser.parse(text)
        assert project.tasks[0].t_shirt_size == "L"

    def test_a_sprint_defaults_to_large(self) -> None:
        text = """
Project name: Test
- Post-launch monitoring takes a sprint
"""
        project = self.parser.parse(text)
        assert project.tasks[0].t_shirt_size == "L"

    def test_a_sprint_uses_configured_sprint_length(self) -> None:
        text = """
Project name: Test
Sprint planning:
- Sprint length: 4
Sprint history S1:
- Done: 10 points
- Carryover: 1 points
Task 1:
- Future sprint tasks are about a sprint
"""
        project = self.parser.parse(text)
        assert project.tasks[0].t_shirt_size == "XL"


class TestFuzzyDependencyMatching:
    """Tests for fuzzy matching of dependency phrases to previous tasks."""

    def setup_method(self) -> None:
        self.parser = NLProjectParser(today=date(2026, 4, 8))

    def test_db_work_phrase_matches_database_task(self) -> None:
        text = """
Project: New feature launch
1. Design database schema
2. Implement backend REST API (probably 2–4 days, depends on the DB work)
"""
        project = self.parser.parse(text)
        assert project.tasks[1].dependency_refs == ["1"]

    def test_frontend_and_backend_phrase_matches_multiple_tasks(self) -> None:
        text = """
Project: New feature launch
1. Design database schema
2. Implement backend REST API
3. Frontend integration testing
4. Deployment and smoke tests (a few days), depends on frontend and backend being ready
"""
        project = self.parser.parse(text)
        assert set(project.tasks[3].dependency_refs) == {"2", "3"}

    def test_no_false_positive_on_generic_dependency_phrase(self) -> None:
        text = """
Project: New feature launch
1. Design database schema
2. This task has dependencies
"""
        project = self.parser.parse(text)
        assert project.tasks[1].dependency_refs == []

    def test_design_example_parses_correctly(self) -> None:
        text = """
Project: New feature launch
Start date: next Monday
1. Design database schema (about a week)
2. Implement backend REST API (probably 2–4 days, depends on the DB work)
3. Frontend integration testing (around 3 weeks)
4. Deployment and smoke tests (a few days), depends on frontend and backend being ready
5. Post-launch monitoring (a sprint)
"""
        project = self.parser.parse(text)

        assert project.start_date == "2026-04-13"
        assert len(project.tasks) == 5

        assert project.tasks[0].t_shirt_size == "M"
        assert project.tasks[1].low_estimate == pytest.approx(2.0)
        assert project.tasks[1].expected_estimate == pytest.approx(3.0)
        assert project.tasks[1].high_estimate == pytest.approx(4.0)
        assert project.tasks[1].dependency_refs == ["1"]
        assert project.tasks[2].expected_estimate == pytest.approx(3.0)
        assert project.tasks[2].estimate_unit == "weeks"
        assert set(project.tasks[3].dependency_refs) == {"2", "3"}
        assert project.tasks[4].t_shirt_size == "L"


class TestFreeformExplicitTaskBullets:
    """Integration tests for Item 2 features inside explicit Task N sections."""

    def setup_method(self) -> None:
        self.parser = NLProjectParser(today=date(2026, 4, 8))

    def test_freeform_duration_bullet_sets_name_and_size(self) -> None:
        text = """
Project: Test
Task 1:
- Design database schema about a week
"""
        project = self.parser.parse(text)
        assert project.tasks[0].name == "Design database schema"
        assert project.tasks[0].t_shirt_size == "M"

    def test_freeform_dependency_bullet_resolves_previous_task(self) -> None:
        text = """
Project: Test
Task 1:
- Design database schema
Task 2:
- Implement backend REST API (probably 2–4 days, depends on the DB work)
"""
        project = self.parser.parse(text)
        assert project.tasks[1].dependency_refs == ["1"]
        assert project.tasks[1].expected_estimate == pytest.approx(3.0)

    # -- Combined: size + estimate on same line ------------------------------

    def test_size_and_range_on_same_line(self) -> None:
        text = """
Project name: Test
- Backend API [XL] 3–5 days
"""
        project = self.parser.parse(text)
        assert project.tasks[0].t_shirt_size == "XL"
        assert project.tasks[0].low_estimate == pytest.approx(3.0)

    # -- AC 4: Fuzzy size tokens ---------------------------------------------

    def test_fuzzy_probably_m(self) -> None:
        text = """
Project name: Test
- Backend refactoring, probably an M
"""
        project = self.parser.parse(text)
        assert project.tasks[0].t_shirt_size == "M"

    def test_fuzzy_likely_l(self) -> None:
        text = """
Project name: Test
- Frontend overhaul, likely an L
"""
        project = self.parser.parse(text)
        assert project.tasks[0].t_shirt_size == "L"

    def test_fuzzy_assume_s(self) -> None:
        text = """
Project name: Test
- Quick patch, assume S
"""
        project = self.parser.parse(text)
        assert project.tasks[0].t_shirt_size == "S"

    def test_bracket_size_takes_precedence_over_fuzzy(self) -> None:
        """If both bracket size and fuzzy are present, bracket wins."""
        text = """
Project name: Test
- Backend [XL] probably an M
"""
        project = self.parser.parse(text)
        assert project.tasks[0].t_shirt_size == "XL"
