"""In-memory project model that backs the UI.

Holds a plain dict representation of the project which is kept in sync
with all editor widgets and can be round-tripped to/from YAML at any time.
"""

from __future__ import annotations

import copy
import datetime
from typing import Any

import yaml
from PySide6.QtCore import QObject, Signal


# ---------------------------------------------------------------------------
# YAML dumper that double-quotes string values but leaves keys unquoted.
# ---------------------------------------------------------------------------

class _DoubleQuotedDumper(yaml.Dumper):
    """Dumper that quotes string *values*, keeps keys plain, and indents sequences."""

    def expect_block_sequence(self) -> None:
        # PyYAML defaults to indentless=True when inside a mapping, which puts
        # the '-' flush with the parent key.  Force indent so list items are
        # nested properly under their key.
        self.increase_indent(flow=False, indentless=False)
        self.state = self.expect_first_block_sequence_item

    def represent_mapping(
        self,
        tag: str,
        mapping: Any,
        flow_style: bool | None = None,
    ) -> yaml.MappingNode:
        node = super().represent_mapping(tag, mapping, flow_style)
        for key_node, value_node in node.value:
            # Force keys to plain (unquoted) style
            if isinstance(key_node, yaml.ScalarNode) and key_node.tag == "tag:yaml.org,2002:str":
                key_node.style = None
            # Force string values to double-quoted style
            if isinstance(value_node, yaml.ScalarNode) and value_node.tag == "tag:yaml.org,2002:str":
                value_node.style = '"'
        return node


def _strip_empty_collections(data: Any) -> Any:
    """Recursively remove keys whose value is an empty list, empty dict, or empty string."""
    if isinstance(data, dict):
        return {
            k: _strip_empty_collections(v)
            for k, v in data.items()
            if not (isinstance(v, (list, dict)) and len(v) == 0)
            and not (isinstance(v, str) and v == "" and k == "description")
        }
    if isinstance(data, list):
        return [_strip_empty_collections(item) for item in data]
    return data


_TASK_KEY_ORDER = ["id", "name", "estimate", "dependencies", "fixed_cost", "description"]


def _order_task_keys(task: dict[str, Any]) -> dict[str, Any]:
    """Return a new dict with id/name/estimate first, remaining keys after."""
    ordered: dict[str, Any] = {}
    for key in _TASK_KEY_ORDER:
        if key in task:
            ordered[key] = task[key]
    for key, value in task.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


class UIProjectModel(QObject):
    """Observable project model for the UI.

    All mutations go through setter methods which emit ``changed``.
    The model stores data in a plain dict that maps 1-to-1 onto the
    project YAML schema understood by the parsers.
    """

    changed = Signal()  # emitted whenever any part of the model changes

    # Default project dict skeleton (all required top-level keys present)
    _DEFAULTS: dict[str, Any] = {
        "project": {
            "name": "My Project",
            "description": "",
            "start_date": "",
            "hours_per_day": 8.0,
        },
        "tasks": [],
    }

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._data: dict[str, Any] = copy.deepcopy(self._DEFAULTS)
        # Set start_date to today
        today = datetime.date.today().isoformat()
        self._data["project"]["start_date"] = today

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self._data)

    def from_dict(self, data: dict[str, Any]) -> None:
        self._data = copy.deepcopy(data)
        self.changed.emit()

    def to_yaml(self) -> str:
        clean = _strip_empty_collections(self._data)
        # Reorder keys within each task dict
        if isinstance(clean.get("tasks"), list):
            clean["tasks"] = [_order_task_keys(t) for t in clean["tasks"]]
        return yaml.dump(
            clean,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            indent=2,
            Dumper=_DoubleQuotedDumper,
        )

    def from_yaml(self, text: str) -> None:
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError("YAML must contain a mapping at the top level.")
        self.from_dict(data)

    # ------------------------------------------------------------------
    # Project basics
    # ------------------------------------------------------------------

    def get_project_basics(self) -> dict[str, Any]:
        return dict(self._data.get("project", {}))

    def set_project_basics(self, basics: dict[str, Any]) -> None:
        self._data["project"].update(basics)
        self.changed.emit()

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    def get_tasks(self) -> list[dict[str, Any]]:
        return list(self._data.get("tasks", []))

    def set_tasks(self, tasks: list[dict[str, Any]]) -> None:
        self._data["tasks"] = copy.deepcopy(tasks)
        self.changed.emit()

    def add_task(self, task: dict[str, Any]) -> None:
        self._data.setdefault("tasks", []).append(copy.deepcopy(task))
        self.changed.emit()

    def update_task(self, index: int, task: dict[str, Any]) -> None:
        self._data["tasks"][index] = copy.deepcopy(task)
        self.changed.emit()

    def delete_task(self, index: int) -> None:
        self._data["tasks"].pop(index)
        self.changed.emit()

    def move_task(self, from_index: int, to_index: int) -> None:
        tasks = self._data.setdefault("tasks", [])
        task = tasks.pop(from_index)
        tasks.insert(to_index, task)
        self.changed.emit()

    # ------------------------------------------------------------------
    # Risks
    # ------------------------------------------------------------------

    def get_risks(self) -> list[dict[str, Any]]:
        return list(self._data.get("risks", []))

    def set_risks(self, risks: list[dict[str, Any]]) -> None:
        self._data["risks"] = copy.deepcopy(risks)
        self.changed.emit()

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        self._data = copy.deepcopy(self._DEFAULTS)
        today = datetime.date.today().isoformat()
        self._data["project"]["start_date"] = today
        self.changed.emit()
