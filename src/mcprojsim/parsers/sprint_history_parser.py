"""Helpers for loading external sprint history sources."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

NEW_HISTORY_REQUIRED_METRICS = (
    "committed_StoryPoints",
    "completed_StoryPoints",
)
NEW_HISTORY_OPTIONAL_METRICS_DEFAULTS = {
    "addedIntraSprint_StoryPoints": 0.0,
    "removedInSprint_StoryPoints": 0.0,
    "spilledOver_StoryPoints": 0.0,
}


def load_external_sprint_history(
    data: dict[str, Any],
    *,
    file_path: Path,
) -> dict[str, Any]:
    """Replace an external sprint history descriptor with loaded rows.

    The returned payload preserves the existing inline-history shape so downstream
    raw validation and model validation can stay unchanged.
    """
    sprint_planning = data.get("sprint_planning")
    if not isinstance(sprint_planning, dict):
        return data

    history = sprint_planning.get("history")
    if not isinstance(history, dict):
        return data

    format_name = history.get("format")
    history_path = history.get("path")

    if not isinstance(format_name, str) or not format_name.strip():
        raise ValueError(
            "Invalid project data:\n"
            "- sprint_planning.history: external history source requires a non-empty 'format'."
        )
    if not isinstance(history_path, str) or not history_path.strip():
        raise ValueError(
            "Invalid project data:\n"
            "- sprint_planning.history: external history source requires a non-empty 'path'."
        )

    resolved_path = Path(history_path)
    if not resolved_path.is_absolute():
        resolved_path = file_path.parent / resolved_path

    format_key = format_name.strip().lower()
    if format_key not in {"json", "csv"}:
        raise ValueError(
            "Invalid project data:\n"
            f"- sprint_planning.history: unsupported external history format '{format_name}'. "
            "Supported formats are 'json' and 'csv'."
        )
    if not resolved_path.exists():
        raise ValueError(
            "Invalid project data:\n"
            f"- sprint_planning.history: external history file not found: {resolved_path}"
        )

    rows = (
        _load_json_history(resolved_path)
        if format_key == "json"
        else _load_csv_history(resolved_path)
    )

    updated = dict(data)
    updated_sprint_planning = dict(sprint_planning)
    updated_sprint_planning["history"] = rows
    updated["sprint_planning"] = updated_sprint_planning
    return updated


def _load_json_history(file_path: Path) -> list[dict[str, Any]]:
    """Load sprint history rows from a JSON file."""
    try:
        with open(file_path, "r", encoding="utf-8") as history_file:
            payload = json.load(history_file)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Invalid project data:\n"
            f"- {file_path.name}:line {exc.lineno}, column {exc.colno}: "
            f"JSON syntax error: {exc.msg}."
        ) from exc

    if isinstance(payload, list):
        raw_rows = _validate_raw_row_list(payload, file_path)
    elif isinstance(payload, dict):
        if "sprints" not in payload:
            raise ValueError(
                "Invalid project data:\n"
                f"- {file_path.name}: external JSON sprint history object must contain a 'sprints' array."
            )

        sprints = payload.get("sprints")
        if not isinstance(sprints, list):
            raise ValueError(
                "Invalid project data:\n"
                f"- {file_path.name}: 'sprints' must be an array of sprint objects."
            )
        raw_rows = _validate_raw_row_list(sprints, file_path)
    else:
        raise ValueError(
            "Invalid project data:\n"
            f"- {file_path.name}: external JSON sprint history must be an array of rows or an object containing 'sprints'."
        )

    rows = [
        _normalize_external_history_row(item, index=index, file_path=file_path)
        for index, item in enumerate(raw_rows, start=1)
    ]
    _validate_unique_sprint_ids(rows, file_path)
    return rows


def _load_csv_history(file_path: Path) -> list[dict[str, Any]]:
    """Load sprint history rows from a CSV file."""
    with open(file_path, "r", encoding="utf-8", newline="") as history_file:
        reader = csv.DictReader(history_file)
        if reader.fieldnames is None:
            raise ValueError(
                "Invalid project data:\n"
                f"- {file_path.name}: external CSV sprint history must include a header row."
            )

        rows: list[dict[str, Any]] = []
        for index, row in enumerate(reader, start=1):
            normalized_row = {
                key: _normalize_csv_value(value)
                for key, value in row.items()
                if key is not None and _normalize_csv_value(value) is not None
            }
            rows.append(
                _normalize_external_history_row(
                    normalized_row,
                    index=index,
                    file_path=file_path,
                )
            )

    _validate_unique_sprint_ids(rows, file_path)
    return rows


def _normalize_csv_value(value: str | None) -> str | None:
    """Map blank CSV cells to None and preserve other values as strings."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _validate_raw_row_list(payload: list[Any], file_path: Path) -> list[dict[str, Any]]:
    """Ensure external history row lists are object mappings."""
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise ValueError(
                "Invalid project data:\n"
                f"- {file_path.name}: history row {index} must be an object/mapping."
            )
        rows.append(dict(item))
    return rows


def _normalize_external_history_row(
    row: dict[str, Any],
    *,
    index: int,
    file_path: Path,
) -> dict[str, Any]:
    """Normalize a raw external row into the inline sprint-history shape."""
    metrics = row.get("metrics")
    if metrics is not None:
        if not isinstance(metrics, dict):
            raise ValueError(
                "Invalid project data:\n"
                f"- {file_path.name}: history row {index} has non-object 'metrics'."
            )
        merged_row = dict(row)
        merged_row.pop("metrics", None)
        merged_row.update(metrics)
        row = merged_row

    is_new_metric_schema = any(
        key in row
        for key in (
            "sprintUniqueID",
            "committed_StoryPoints",
            "completed_StoryPoints",
            "addedIntraSprint_StoryPoints",
            "removedInSprint_StoryPoints",
            "spilledOver_StoryPoints",
        )
    )
    if not is_new_metric_schema:
        return dict(row)

    sprint_unique_id = row.get("sprintUniqueID")
    if not isinstance(sprint_unique_id, str) or not sprint_unique_id.strip():
        raise ValueError(
            "Invalid project data:\n"
            f"- {file_path.name}: history row {index} requires a non-empty 'sprintUniqueID'."
        )

    metric_values: dict[str, float] = {}
    for metric_key in NEW_HISTORY_REQUIRED_METRICS:
        if metric_key not in row:
            raise ValueError(
                "Invalid project data:\n"
                f"- {file_path.name}: history row {index} is missing required metric '{metric_key}'."
            )
        metric_values[metric_key] = _parse_metric_number(
            row.get(metric_key),
            metric_key=metric_key,
            index=index,
            file_path=file_path,
        )

    for metric_key, default_value in NEW_HISTORY_OPTIONAL_METRICS_DEFAULTS.items():
        raw_value = row.get(metric_key, default_value)
        if raw_value is None or raw_value == "":
            raw_value = default_value
        metric_values[metric_key] = _parse_metric_number(
            raw_value,
            metric_key=metric_key,
            index=index,
            file_path=file_path,
        )

    normalized: dict[str, Any] = {
        "sprint_id": sprint_unique_id.strip(),
        "completed_story_points": metric_values["completed_StoryPoints"],
        "added_story_points": metric_values["addedIntraSprint_StoryPoints"],
        "removed_story_points": metric_values["removedInSprint_StoryPoints"],
        "spillover_story_points": metric_values["spilledOver_StoryPoints"],
    }

    end_date = row.get("endDate")
    if isinstance(end_date, str) and end_date.strip():
        normalized["end_date"] = end_date.strip()

    # Validate but intentionally drop committed_StoryPoints for compatibility with
    # SprintHistoryEntry, which does not currently expose this metric.
    _ = metric_values["committed_StoryPoints"]
    return normalized


def _parse_metric_number(
    value: Any,
    *,
    metric_key: str,
    index: int,
    file_path: Path,
) -> float:
    """Parse and validate a numeric metric value."""
    if value is None:
        raise ValueError(
            "Invalid project data:\n"
            f"- {file_path.name}: history row {index} metric '{metric_key}' must be numeric."
        )

    if isinstance(value, bool):
        raise ValueError(
            "Invalid project data:\n"
            f"- {file_path.name}: history row {index} metric '{metric_key}' must be numeric."
        )

    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Invalid project data:\n"
            f"- {file_path.name}: history row {index} metric '{metric_key}' must be numeric, got {value!r}."
        ) from exc

    if number < 0:
        raise ValueError(
            "Invalid project data:\n"
            f"- {file_path.name}: history row {index} metric '{metric_key}' must be >= 0."
        )

    return number


def _validate_unique_sprint_ids(rows: list[dict[str, Any]], file_path: Path) -> None:
    """Ensure sprint IDs are unique after normalization."""
    seen: set[str] = set()
    duplicates: set[str] = set()

    for row in rows:
        sprint_id = row.get("sprint_id")
        if not isinstance(sprint_id, str) or not sprint_id.strip():
            continue
        if sprint_id in seen:
            duplicates.add(sprint_id)
        seen.add(sprint_id)

    if duplicates:
        duplicate_list = ", ".join(sorted(duplicates))
        raise ValueError(
            "Invalid project data:\n"
            f"- {file_path.name}: duplicate sprint identifiers found: {duplicate_list}"
        )
