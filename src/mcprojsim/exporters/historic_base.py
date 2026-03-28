"""Helpers for building historic sprint baseline data for exports."""

from __future__ import annotations

import math
from typing import Any

from mcprojsim.models.project import Project


def build_historic_base(project: Project | None) -> dict[str, Any] | None:
    """Build historic sprint rows and a compact statistical summary.

    Returns ``None`` when project sprint history is unavailable.
    """
    if project is None or project.sprint_planning is None:
        return None

    sprint_planning = project.sprint_planning
    history = sprint_planning.history
    if not history:
        return None

    capacity_mode = sprint_planning.capacity_mode.value
    unit_label = "story_points" if capacity_mode == "story_points" else "tasks"

    rows: list[dict[str, Any]] = []
    completed_values: list[float] = []
    committed_values: list[float] = []
    completion_rates: list[float] = []

    for entry in history:
        if capacity_mode == "story_points":
            completed = float(entry.completed_story_points or 0.0)
            spillover = float(entry.spillover_story_points)
            removed = float(entry.removed_story_points)
            added = float(entry.added_story_points)
        else:
            completed = float(entry.completed_tasks or 0.0)
            spillover = float(entry.spillover_tasks)
            removed = float(entry.removed_tasks)
            added = float(entry.added_tasks)

        # Baseline commitment approximates sprint-start scope before add/remove churn.
        committed = completed + spillover + removed
        completion_rate = completed / committed if committed > 0 else 0.0

        rows.append(
            {
                "sprint_id": entry.sprint_id,
                "end_date": entry.end_date.isoformat() if entry.end_date else None,
                "sprint_length_weeks": entry.sprint_length_weeks,
                "committed": round(committed, 4),
                "completed": round(completed, 4),
                "spillover": round(spillover, 4),
                "added": round(added, 4),
                "removed": round(removed, 4),
                "completion_rate": round(completion_rate, 4),
            }
        )

        committed_values.append(committed)
        completed_values.append(completed)
        completion_rates.append(completion_rate)

    return {
        "capacity_mode": capacity_mode,
        "unit_label": unit_label,
        "rows": rows,
        "summary": {
            "observation_count": len(rows),
            "mean_committed": _mean(committed_values),
            "mean_completed": _mean(completed_values),
            "mean_completion_rate": _mean(completion_rates),
            "std_committed": _std(committed_values),
            "std_completed": _std(completed_values),
            "min_completed": min(completed_values) if completed_values else 0.0,
            "max_completed": max(completed_values) if completed_values else 0.0,
        },
    }


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = _mean(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return math.sqrt(variance)
