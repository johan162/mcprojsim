"""Helpers for source-aware parsing and validation errors."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import difflib
from pathlib import Path
import re
from typing import Any, TypeAlias

from pydantic import ValidationError
import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

LocationPath: TypeAlias = tuple[str | int, ...]


@dataclass(frozen=True)
class ParsedDocument:
    """Parsed source data with line-number metadata."""

    data: Any
    path_lines: dict[LocationPath, int]


@dataclass(frozen=True)
class ValidationIssue:
    """A user-facing validation issue tied to a source path."""

    path: LocationPath
    message: str
    suggestion: str | None = None


def load_yaml_with_locations(text: str) -> ParsedDocument:
    """Load YAML text while recording line numbers for source paths."""
    loader = yaml.SafeLoader(text)

    try:
        root = loader.get_single_node()
        if root is None:
            return ParsedDocument(data=None, path_lines={(): 1})

        path_lines: dict[LocationPath, int] = {(): _line_from_node(root)}
        data = _construct_yaml_node(loader, root, (), path_lines)
        return ParsedDocument(data=data, path_lines=path_lines)
    finally:
        loader.dispose()  # type: ignore[no-untyped-call]


def load_toml_with_locations(text: str, toml_loader: Any) -> ParsedDocument:
    """Load TOML text while recording best-effort source line numbers."""
    data = toml_loader.loads(text)
    return ParsedDocument(data=data, path_lines=_collect_toml_path_lines(text))


def validate_project_payload(data: Any) -> list[ValidationIssue]:
    """Run raw-data checks that benefit from direct source paths."""
    issues: list[ValidationIssue] = []

    if not isinstance(data, dict):
        issues.append(
            ValidationIssue(
                path=(),
                message="Project file must contain a top-level mapping/object.",
                suggestion="Start with top-level sections like 'project:' and 'tasks:'",
            )
        )
        return issues

    _collect_unknown_field_issues(data, (), issues)
    _collect_duplicate_task_id_issues(data, issues)
    _collect_missing_dependency_issues(data, issues)
    _collect_circular_dependency_issues(data, issues)
    _collect_duplicate_sprint_id_issues(data, issues)
    _collect_sprint_history_unit_issues(data, issues)
    _collect_future_override_issues(data, issues)
    _collect_spillover_bracket_issues(data, issues)

    return issues


def format_validation_error(
    error: Exception,
    path_lines: dict[LocationPath, int],
    data: Any,
    file_path: Path | str,
) -> str:
    """Format a parse or validation error with source line numbers."""
    file_path = Path(file_path)

    if isinstance(error, ValidationError):
        return _format_pydantic_validation_error(error, path_lines, data, file_path)

    return f"Invalid project data:\n- {_format_single_exception(error, file_path)}"


def format_validation_issues(
    issues: list[ValidationIssue],
    path_lines: dict[LocationPath, int],
    file_path: Path | str,
) -> str:
    """Format raw validation issues with line numbers."""
    file_path = Path(file_path)
    lines = ["Invalid project data:"]

    for issue in issues:
        location = _format_location(file_path, issue.path, path_lines)
        message = f"- {location}: {issue.message}"
        if issue.suggestion:
            message += f" Suggestion: {issue.suggestion}."
        lines.append(message)

    return "\n".join(lines)


def format_yaml_parse_error(error: yaml.YAMLError, file_path: Path | str) -> str:
    """Format a YAML syntax error with line and suggestion."""
    file_path = Path(file_path)
    mark = getattr(error, "problem_mark", None)
    line = getattr(mark, "line", 0) + 1 if mark is not None else 1
    column = getattr(mark, "column", 0) + 1 if mark is not None else 1
    message = str(error).split("\n", 1)[0]
    suggestion = _suggest_for_parse_message(message, "yaml")
    return (
        "Invalid project data:\n"
        f"- {file_path.name}:line {line}, column {column}: YAML syntax error: {message}. "
        f"Suggestion: {suggestion}."
    )


def format_toml_parse_error(error: Exception, file_path: Path | str) -> str:
    """Format a TOML syntax error with line and suggestion."""
    file_path = Path(file_path)
    line = getattr(error, "lineno", 1)
    column = getattr(error, "colno", 1)
    message = str(error).split("\n", 1)[0]
    suggestion = _suggest_for_parse_message(message, "toml")
    return (
        "Invalid project data:\n"
        f"- {file_path.name}:line {line}, column {column}: TOML syntax error: {message}. "
        f"Suggestion: {suggestion}."
    )


def _construct_yaml_node(
    loader: yaml.SafeLoader,
    node: Node,
    path: LocationPath,
    path_lines: dict[LocationPath, int],
) -> Any:
    if isinstance(node, MappingNode):
        mapping_result: dict[Any, Any] = {}
        path_lines.setdefault(path, _line_from_node(node))
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=False)  # type: ignore[no-untyped-call]
            child_path = path + (key,)
            path_lines[child_path] = _line_from_node(key_node)
            mapping_result[key] = _construct_yaml_node(
                loader, value_node, child_path, path_lines
            )
        return mapping_result

    if isinstance(node, SequenceNode):
        sequence_result: list[Any] = []
        path_lines.setdefault(path, _line_from_node(node))
        for index, item_node in enumerate(node.value):
            child_path = path + (index,)
            path_lines[child_path] = _line_from_node(item_node)
            sequence_result.append(
                _construct_yaml_node(loader, item_node, child_path, path_lines)
            )
        return sequence_result

    if isinstance(node, ScalarNode):
        path_lines.setdefault(path, _line_from_node(node))
        return loader.construct_object(node, deep=False)  # type: ignore[no-untyped-call]

    return loader.construct_object(node, deep=False)  # type: ignore[no-untyped-call]


def _line_from_node(node: Node) -> int:
    return node.start_mark.line + 1


def _collect_toml_path_lines(text: str) -> dict[LocationPath, int]:
    path_lines: dict[LocationPath, int] = {(): 1}
    current_path: LocationPath = ()
    active_indices: dict[LocationPath, int] = {}
    next_indices: dict[LocationPath, int] = {}
    array_table_names = {"tasks", "project_risks", "resources", "calendars", "risks"}

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = _strip_toml_comment(raw_line).strip()
        if not line:
            continue

        if line.startswith("[[") and line.endswith("]]"):
            header = line[2:-2].strip()
            segments = _split_toml_dotted_key(header)
            current_path = _resolve_toml_header(
                segments,
                is_array=True,
                active_indices=active_indices,
                next_indices=next_indices,
                array_table_names=array_table_names,
            )
            path_lines.setdefault(current_path, line_number)
            continue

        if line.startswith("[") and line.endswith("]"):
            header = line[1:-1].strip()
            segments = _split_toml_dotted_key(header)
            current_path = _resolve_toml_header(
                segments,
                is_array=False,
                active_indices=active_indices,
                next_indices=next_indices,
                array_table_names=array_table_names,
            )
            path_lines.setdefault(current_path, line_number)
            continue

        key = _extract_toml_key(line)
        if key is None:
            continue

        key_path = current_path + tuple(_split_toml_dotted_key(key))
        path_lines.setdefault(key_path, line_number)

    return path_lines


def _resolve_toml_header(
    segments: list[str],
    is_array: bool,
    active_indices: dict[LocationPath, int],
    next_indices: dict[LocationPath, int],
    array_table_names: set[str],
) -> LocationPath:
    resolved: list[str | int] = []

    for index, segment in enumerate(segments):
        is_final = index == len(segments) - 1
        collection_path = tuple(resolved + [segment])

        if segment in array_table_names:
            if is_array and is_final:
                next_index = next_indices.get(collection_path, 0)
                next_indices[collection_path] = next_index + 1
                active_indices[collection_path] = next_index
                resolved.extend([segment, next_index])
            elif collection_path in active_indices:
                resolved.extend([segment, active_indices[collection_path]])
            else:
                resolved.append(segment)
        else:
            resolved.append(segment)

    return tuple(resolved)


def _strip_toml_comment(line: str) -> str:
    result: list[str] = []
    quote: str | None = None
    escaped = False

    for char in line:
        if escaped:
            result.append(char)
            escaped = False
            continue

        if quote == '"' and char == "\\":
            result.append(char)
            escaped = True
            continue

        if quote is None and char in {'"', "'"}:
            quote = char
            result.append(char)
            continue

        if quote == char:
            quote = None
            result.append(char)
            continue

        if quote is None and char == "#":
            break

        result.append(char)

    return "".join(result)


def _split_toml_dotted_key(key: str) -> list[str]:
    segments: list[str] = []
    current: list[str] = []
    quote: str | None = None

    for char in key.strip():
        if quote is None and char in {'"', "'"}:
            quote = char
            continue

        if quote == char:
            quote = None
            continue

        if quote is None and char == ".":
            segment = "".join(current).strip()
            if segment:
                segments.append(segment)
            current = []
            continue

        current.append(char)

    final_segment = "".join(current).strip()
    if final_segment:
        segments.append(final_segment)

    return segments


def _extract_toml_key(line: str) -> str | None:
    quote: str | None = None

    for index, char in enumerate(line):
        if quote is None and char in {'"', "'"}:
            quote = char
            continue

        if quote == char:
            quote = None
            continue

        if quote is None and char == "=":
            return line[:index].strip()

    return None


def _collect_unknown_field_issues(
    value: Any,
    path: LocationPath,
    issues: list[ValidationIssue],
) -> None:
    schema = _allowed_fields_for_path(path)

    if schema is not None and isinstance(value, dict):
        for key, child in value.items():
            if key not in schema:
                suggestion = _close_match(str(key), sorted(schema))
                suggestion_text = (
                    f"Did you mean '{suggestion}'" if suggestion is not None else None
                )
                issues.append(
                    ValidationIssue(
                        path=path + (str(key),),
                        message=f"Unknown field '{key}'.",
                        suggestion=suggestion_text,
                    )
                )

        for key, child in value.items():
            if key in schema:
                _collect_unknown_field_issues(child, path + (str(key),), issues)
        return

    if isinstance(value, list):
        for index, child in enumerate(value):
            _collect_unknown_field_issues(child, path + (index,), issues)


def _collect_duplicate_task_id_issues(
    data: Any,
    issues: list[ValidationIssue],
) -> None:
    tasks = data.get("tasks") if isinstance(data, dict) else None
    if not isinstance(tasks, list):
        return

    seen: dict[str, int] = {}
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            continue

        task_id = task.get("id")
        if not isinstance(task_id, str):
            continue

        if task_id in seen:
            first_index = seen[task_id]
            issues.append(
                ValidationIssue(
                    path=("tasks", index, "id"),
                    message=f"Duplicate task id '{task_id}'.",
                    suggestion=f"Rename this task or reuse the first definition from tasks[{first_index + 1}]",
                )
            )
        else:
            seen[task_id] = index


def _collect_missing_dependency_issues(
    data: Any,
    issues: list[ValidationIssue],
) -> None:
    tasks = data.get("tasks") if isinstance(data, dict) else None
    if not isinstance(tasks, list):
        return

    valid_task_ids: list[str] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = task.get("id")
        if isinstance(task_id, str):
            valid_task_ids.append(task_id)

    valid_task_id_set = set(valid_task_ids)

    for task_index, task in enumerate(tasks):
        if not isinstance(task, dict):
            continue

        dependencies = task.get("dependencies")
        if not isinstance(dependencies, list):
            continue

        for dep_index, dependency in enumerate(dependencies):
            if not isinstance(dependency, str) or dependency in valid_task_id_set:
                continue

            suggestion = _close_match(dependency, valid_task_ids)
            suggestion_text = (
                f"Did you mean '{suggestion}'" if suggestion is not None else None
            )
            issues.append(
                ValidationIssue(
                    path=("tasks", task_index, "dependencies", dep_index),
                    message=f"Unknown task dependency '{dependency}'.",
                    suggestion=suggestion_text,
                )
            )


def _collect_circular_dependency_issues(
    data: Any,
    issues: list[ValidationIssue],
) -> None:
    tasks = data.get("tasks") if isinstance(data, dict) else None
    if not isinstance(tasks, list):
        return

    task_ids_to_index: dict[str, int] = {}
    graph: dict[str, list[str]] = {}

    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            continue
        task_id = task.get("id")
        dependencies = task.get("dependencies", [])
        if isinstance(task_id, str):
            task_ids_to_index[task_id] = index
            graph[task_id] = [dep for dep in dependencies if isinstance(dep, str)]

    visited: set[str] = set()
    stack: list[str] = []
    in_stack: set[str] = set()
    reported_edges: set[tuple[str, str]] = set()

    def visit(task_id: str) -> None:
        visited.add(task_id)
        stack.append(task_id)
        in_stack.add(task_id)

        for dependency in graph.get(task_id, []):
            if dependency not in graph:
                continue

            if dependency in in_stack:
                edge = (task_id, dependency)
                if edge not in reported_edges:
                    reported_edges.add(edge)
                    cycle = stack[stack.index(dependency) :] + [dependency]
                    task_index = task_ids_to_index[task_id]
                    dep_position = _dependency_position(tasks[task_index], dependency)
                    if dep_position is not None:
                        issues.append(
                            ValidationIssue(
                                path=(
                                    "tasks",
                                    task_index,
                                    "dependencies",
                                    dep_position,
                                ),
                                message=(
                                    "Circular dependency detected: "
                                    + " -> ".join(cycle)
                                ),
                                suggestion="Remove one dependency from the cycle so the task graph becomes acyclic",
                            )
                        )
                continue

            if dependency not in visited:
                visit(dependency)

        stack.pop()
        in_stack.remove(task_id)

    for task_id in graph:
        if task_id not in visited:
            visit(task_id)


def _dependency_position(task: Any, dependency: str) -> int | None:
    if not isinstance(task, dict):
        return None
    dependencies = task.get("dependencies")
    if not isinstance(dependencies, list):
        return None
    for index, value in enumerate(dependencies):
        if value == dependency:
            return index
    return None


def _collect_duplicate_sprint_id_issues(
    data: Any,
    issues: list[ValidationIssue],
) -> None:
    sprint_planning = data.get("sprint_planning") if isinstance(data, dict) else None
    if not isinstance(sprint_planning, dict):
        return

    history = sprint_planning.get("history")
    if not isinstance(history, list):
        return

    seen: dict[str, int] = {}
    for index, entry in enumerate(history):
        if not isinstance(entry, dict):
            continue

        sprint_id = entry.get("sprint_id")
        if not isinstance(sprint_id, str):
            continue

        if sprint_id in seen:
            first_index = seen[sprint_id]
            issues.append(
                ValidationIssue(
                    path=("sprint_planning", "history", index, "sprint_id"),
                    message=f"Duplicate sprint_id '{sprint_id}'.",
                    suggestion=(
                        "Rename this sprint or reuse the first definition from "
                        f"sprint_planning.history[{first_index + 1}]"
                    ),
                )
            )
        else:
            seen[sprint_id] = index


def _collect_sprint_history_unit_issues(
    data: Any,
    issues: list[ValidationIssue],
) -> None:
    sprint_planning = data.get("sprint_planning") if isinstance(data, dict) else None
    if not isinstance(sprint_planning, dict):
        return

    capacity_mode = sprint_planning.get("capacity_mode")
    history = sprint_planning.get("history")
    if not isinstance(history, list):
        return

    for index, entry in enumerate(history):
        if not isinstance(entry, dict):
            continue

        has_story_points = "completed_story_points" in entry
        has_tasks = "completed_tasks" in entry

        if has_story_points and has_tasks:
            issues.append(
                ValidationIssue(
                    path=("sprint_planning", "history", index),
                    message=(
                        "Sprint history entries must include exactly one of "
                        "'completed_story_points' or 'completed_tasks'"
                    ),
                )
            )
            continue

        if not has_story_points and not has_tasks:
            issues.append(
                ValidationIssue(
                    path=("sprint_planning", "history", index),
                    message=(
                        "Sprint history entries must include either "
                        "'completed_story_points' or 'completed_tasks'"
                    ),
                )
            )
            continue

        if has_story_points and _entry_uses_task_fields(entry):
            issues.append(
                ValidationIssue(
                    path=("sprint_planning", "history", index),
                    message=(
                        "Sprint history entries using 'completed_story_points' must "
                        "not include task-based spillover, added, or removed fields"
                    ),
                )
            )

        if has_tasks and _entry_uses_story_point_fields(entry):
            issues.append(
                ValidationIssue(
                    path=("sprint_planning", "history", index),
                    message=(
                        "Sprint history entries using 'completed_tasks' must not "
                        "include story-point-based spillover, added, or removed fields"
                    ),
                )
            )

        if capacity_mode == "story_points" and has_tasks:
            issues.append(
                ValidationIssue(
                    path=("sprint_planning", "history", index, "completed_tasks"),
                    message=(
                        "Sprint history entries must use story-point completed fields "
                        "when capacity_mode is 'story_points'"
                    ),
                )
            )

        if capacity_mode == "tasks" and has_story_points:
            issues.append(
                ValidationIssue(
                    path=(
                        "sprint_planning",
                        "history",
                        index,
                        "completed_story_points",
                    ),
                    message=(
                        "Sprint history entries must use task-count completed fields "
                        "when capacity_mode is 'tasks'"
                    ),
                )
            )


def _collect_future_override_issues(
    data: Any,
    issues: list[ValidationIssue],
) -> None:
    sprint_planning = data.get("sprint_planning") if isinstance(data, dict) else None
    if not isinstance(sprint_planning, dict):
        return

    overrides = sprint_planning.get("future_sprint_overrides")
    if not isinstance(overrides, list):
        return

    sprint_length_weeks = sprint_planning.get("sprint_length_weeks")
    project = data.get("project") if isinstance(data, dict) else None
    project_start_date = (
        project.get("start_date") if isinstance(project, dict) else None
    )
    project_start = _parse_iso_date(project_start_date)
    sprint_days = (
        sprint_length_weeks * 7 if isinstance(sprint_length_weeks, int) else None
    )

    seen_targets: dict[int, int] = {}
    for index, override in enumerate(overrides):
        if not isinstance(override, dict):
            continue

        sprint_number = override.get("sprint_number")
        start_date_raw = override.get("start_date")
        start_date = _parse_iso_date(start_date_raw)
        if sprint_number is None and start_date is None:
            issues.append(
                ValidationIssue(
                    path=("sprint_planning", "future_sprint_overrides", index),
                    message=(
                        "Future sprint overrides must define at least one locator: "
                        "'sprint_number' or 'start_date'"
                    ),
                )
            )
            continue

        resolved_sprint_number = (
            sprint_number if isinstance(sprint_number, int) else None
        )
        if (
            start_date is not None
            and project_start is not None
            and sprint_days is not None
            and sprint_days > 0
        ):
            delta_days = (start_date - project_start).days
            if delta_days < 0 or delta_days % sprint_days != 0:
                issues.append(
                    ValidationIssue(
                        path=(
                            "sprint_planning",
                            "future_sprint_overrides",
                            index,
                            "start_date",
                        ),
                        message=(
                            "Future sprint override start_date must align to a simulated "
                            "sprint boundary"
                        ),
                    )
                )
                continue

            derived_sprint_number = (delta_days // sprint_days) + 1
            if (
                resolved_sprint_number is not None
                and resolved_sprint_number != derived_sprint_number
            ):
                issues.append(
                    ValidationIssue(
                        path=(
                            "sprint_planning",
                            "future_sprint_overrides",
                            index,
                            "start_date",
                        ),
                        message=(
                            "Future sprint override sprint_number and start_date must "
                            "resolve to the same sprint"
                        ),
                    )
                )
                continue
            resolved_sprint_number = derived_sprint_number

        if resolved_sprint_number is not None:
            previous_index = seen_targets.get(resolved_sprint_number)
            if previous_index is not None:
                issues.append(
                    ValidationIssue(
                        path=("sprint_planning", "future_sprint_overrides", index),
                        message=(
                            "Future sprint overrides must target unique simulated sprints"
                        ),
                        suggestion=(
                            "Merge this override with sprint_planning.future_sprint_overrides["
                            f"{previous_index + 1}] or target a different sprint"
                        ),
                    )
                )
            else:
                seen_targets[resolved_sprint_number] = index


def _collect_spillover_bracket_issues(
    data: Any,
    issues: list[ValidationIssue],
) -> None:
    sprint_planning = data.get("sprint_planning") if isinstance(data, dict) else None
    if not isinstance(sprint_planning, dict):
        return

    spillover = sprint_planning.get("spillover")
    if not isinstance(spillover, dict):
        return

    size_brackets = spillover.get("size_brackets")
    if not isinstance(size_brackets, list):
        return

    previous_max = 0.0
    saw_unbounded = False
    for index, bracket in enumerate(size_brackets):
        if not isinstance(bracket, dict):
            continue

        max_points = bracket.get("max_points")
        bracket_path = ("sprint_planning", "spillover", "size_brackets", index)

        if saw_unbounded:
            issues.append(
                ValidationIssue(
                    path=bracket_path,
                    message=(
                        "Spillover size_brackets must place the unbounded bracket last"
                    ),
                )
            )
            continue

        if max_points is None:
            saw_unbounded = True
            continue

        if isinstance(max_points, (int, float)) and float(max_points) <= previous_max:
            issues.append(
                ValidationIssue(
                    path=bracket_path + ("max_points",),
                    message=(
                        "Spillover size_brackets max_points values must be strictly "
                        "ascending"
                    ),
                )
            )
            continue

        if isinstance(max_points, (int, float)):
            previous_max = float(max_points)


def _entry_uses_task_fields(entry: Mapping[str, Any]) -> bool:
    return any(
        field in entry for field in ("spillover_tasks", "added_tasks", "removed_tasks")
    )


def _entry_uses_story_point_fields(entry: Mapping[str, Any]) -> bool:
    return any(
        field in entry
        for field in (
            "spillover_story_points",
            "added_story_points",
            "removed_story_points",
        )
    )


def _parse_iso_date(value: Any) -> Any:
    from datetime import date

    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _allowed_fields_for_path(path: LocationPath) -> set[str] | None:
    if not path:
        return {
            "project",
            "tasks",
            "project_risks",
            "resources",
            "calendars",
            "sprint_planning",
        }

    if path == ("project",):
        return {
            "name",
            "description",
            "start_date",
            "hours_per_day",
            "currency",
            "confidence_levels",
            "probability_red_threshold",
            "probability_green_threshold",
            "distribution",
            "team_size",
        }

    if len(path) == 2 and path[0] == "tasks" and isinstance(path[1], int):
        return {
            "id",
            "name",
            "description",
            "estimate",
            "dependencies",
            "uncertainty_factors",
            "resources",
            "max_resources",
            "min_experience_level",
            "planning_story_points",
            "priority",
            "spillover_probability_override",
            "risks",
        }

    if path == ("sprint_planning",):
        return {
            "enabled",
            "sprint_length_weeks",
            "capacity_mode",
            "history",
            "planning_confidence_level",
            "removed_work_treatment",
            "future_sprint_overrides",
            "volatility_overlay",
            "spillover",
            "velocity_model",
            "sickness",
        }

    if (
        len(path) == 3
        and path[0] == "sprint_planning"
        and path[1] == "future_sprint_overrides"
        and isinstance(path[2], int)
    ):
        return {
            "sprint_number",
            "start_date",
            "holiday_factor",
            "capacity_multiplier",
            "notes",
        }

    if path == ("sprint_planning", "volatility_overlay"):
        return {
            "enabled",
            "disruption_probability",
            "disruption_multiplier_low",
            "disruption_multiplier_expected",
            "disruption_multiplier_high",
        }

    if path == ("sprint_planning", "spillover"):
        return {
            "enabled",
            "model",
            "size_reference_points",
            "size_brackets",
            "consumed_fraction_alpha",
            "consumed_fraction_beta",
            "logistic_slope",
            "logistic_intercept",
        }

    if path == ("sprint_planning", "sickness"):
        return {
            "enabled",
            "team_size",
            "probability_per_person_per_week",
            "duration_log_mu",
            "duration_log_sigma",
        }

    if (
        len(path) == 4
        and path[0] == "sprint_planning"
        and path[1] == "spillover"
        and path[2] == "size_brackets"
        and isinstance(path[3], int)
    ):
        return {"max_points", "probability"}

    if (
        len(path) == 3
        and path[0] == "sprint_planning"
        and path[1] == "history"
        and isinstance(path[2], int)
    ):
        return {
            "sprint_id",
            "sprint_length_weeks",
            "completed_story_points",
            "completed_tasks",
            "spillover_story_points",
            "spillover_tasks",
            "added_story_points",
            "added_tasks",
            "removed_story_points",
            "removed_tasks",
            "holiday_factor",
            "end_date",
            "team_size",
            "notes",
        }

    if len(path) == 2 and path[0] == "resources" and isinstance(path[1], int):
        return {
            "name",
            "id",
            "availability",
            "calendar",
            "experience_level",
            "productivity_level",
            "sickness_prob",
            "planned_absence",
        }

    if len(path) == 2 and path[0] == "calendars" and isinstance(path[1], int):
        return {
            "id",
            "work_hours_per_day",
            "work_days",
            "holidays",
        }

    if (
        len(path) == 3
        and path[0] == "tasks"
        and isinstance(path[1], int)
        and path[2] == "estimate"
    ):
        return {
            "distribution",
            "low",
            "expected",
            "high",
            "t_shirt_size",
            "story_points",
            "unit",
        }

    if (
        len(path) == 3
        and path[0] == "tasks"
        and isinstance(path[1], int)
        and path[2] == "uncertainty_factors"
    ):
        return {
            "team_experience",
            "requirements_maturity",
            "technical_complexity",
            "team_distribution",
            "integration_complexity",
        }

    if (
        len(path) == 4
        and path[0] == "tasks"
        and isinstance(path[1], int)
        and path[2] == "risks"
        and isinstance(path[3], int)
    ):
        return {"id", "name", "probability", "impact", "description"}

    if len(path) == 2 and path[0] == "project_risks" and isinstance(path[1], int):
        return {"id", "name", "probability", "impact", "description"}

    if path and path[-1] == "impact":
        return {"type", "value", "unit"}

    return None


def _format_pydantic_validation_error(
    error: ValidationError,
    path_lines: dict[LocationPath, int],
    data: Any,
    file_path: Path,
) -> str:
    lines = ["Invalid project data:"]

    for item in error.errors(include_url=False):
        raw_loc = item.get("loc", ())
        loc = tuple(
            part
            for part in raw_loc
            if isinstance(
                part, (str, int)
            )  # pyright: ignore[reportUnnecessaryIsInstance]
        )
        message = str(item.get("msg", "Validation error"))
        if message.startswith("Value error, "):
            message = message[len("Value error, ") :]
        suggestion = _suggest_for_validation_error(item, data)
        location = _format_location(file_path, loc, path_lines)
        formatted = f"- {location}: {message}"
        if suggestion:
            formatted += f" Suggestion: {suggestion}."
        lines.append(formatted)

    return "\n".join(lines)


def _format_single_exception(error: Exception, file_path: Path) -> str:
    message = str(error)
    suggestion = _suggest_for_parse_message(message, file_path.suffix.lstrip("."))
    return f"{file_path.name}: {message}. Suggestion: {suggestion}."


def _format_location(
    file_path: Path,
    path: LocationPath,
    path_lines: dict[LocationPath, int],
) -> str:
    line = _find_best_line(path, path_lines)
    path_text = _format_path(path)
    return f"{file_path.name}:line {line} ({path_text})"


def _find_best_line(path: LocationPath, path_lines: dict[LocationPath, int]) -> int:
    if path in path_lines:
        return path_lines[path]

    current = path
    while current:
        current = current[:-1]
        if current in path_lines:
            return path_lines[current]

    return path_lines.get((), 1)


def _format_path(path: LocationPath) -> str:
    if not path:
        return "<root>"

    parts: list[str] = []
    for part in path:
        if isinstance(part, int):
            if parts:
                parts[-1] = f"{parts[-1]}[{part + 1}]"
            else:
                parts.append(f"[{part + 1}]")
        else:
            parts.append(part)

    return ".".join(parts)


def _suggest_for_validation_error(error: Mapping[str, Any], data: Any) -> str | None:
    loc = tuple(part for part in error.get("loc", ()) if isinstance(part, (str, int)))
    error_type = error.get("type")

    if error_type == "missing" and loc:
        parent = _get_value_at_path(data, loc[:-1])
        if isinstance(parent, dict) and isinstance(loc[-1], str):
            suggestion_key = _close_match(
                str(loc[-1]), [str(key) for key in parent.keys()]
            )
            if suggestion_key is not None:
                return f"Did you mean '{suggestion_key}' instead of '{loc[-1]}'"

    message = str(error.get("msg", ""))

    dependency_match = re.search(r"Unknown task dependency '([^']+)'", message)
    if dependency_match:
        dependency = dependency_match.group(1)
        tasks = data.get("tasks") if isinstance(data, dict) else None
        if isinstance(tasks, list):
            task_ids = [task.get("id") for task in tasks if isinstance(task, dict)]
            suggestion = _close_match(
                dependency,
                [task_id for task_id in task_ids if isinstance(task_id, str)],
            )
            if suggestion is not None:
                return f"Did you mean '{suggestion}'"

    return None


def _get_value_at_path(data: Any, path: LocationPath) -> Any:
    current = data
    for part in path:
        if isinstance(part, int):
            if not isinstance(current, list) or part >= len(current):
                return None
            current = current[part]
        else:
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
    return current


def _close_match(value: str, choices: list[str]) -> str | None:
    if not choices:
        return None
    matches = difflib.get_close_matches(value, choices, n=1, cutoff=0.6)
    return matches[0] if matches else None


def _suggest_for_parse_message(message: str, file_format: str) -> str:
    lower = message.lower()

    if (
        "expected '<document start>'" in lower
        or "mapping values are not allowed" in lower
    ):
        return "Check indentation and make sure each key is followed by a colon"
    if "could not find expected ':'" in lower:
        return "Add the missing ':' after the key name"
    if "unterminated" in lower or "unclosed" in lower:
        return "Close the quoted string, array, or table declaration"
    if "invalid statement" in lower or "invalid value" in lower:
        if file_format == "toml":
            return "Check table headers, '=' separators, and quote string values"
        return "Check the syntax near this line and make sure values are valid"

    if file_format == "toml":
        return "Check table headers, '=' separators, commas, and string quoting"
    return "Check indentation, colons, and list formatting near this line"
