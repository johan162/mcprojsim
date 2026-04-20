"""Lark POC validator for mcprojsim grammar.

This script demonstrates grammar-driven validation for project/config files
without hand-writing a parser for the grammar itself.

Design:
1. Load YAML/TOML into a Python object.
2. Normalize to a canonical textual representation.
3. Parse canonical text using a Lark grammar.

This is intentionally a POC under design-ideas/ and not wired into src/ yet.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

import yaml

try:
    from lark import Lark, UnexpectedInput
except ImportError:  # pragma: no cover - POC runtime guard
    print("Missing dependency: lark. Install with: poetry run pip install lark", file=sys.stderr)
    raise

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib


THIS_DIR = Path(__file__).resolve().parent
GRAMMAR_PATH = THIS_DIR / "mcprojsim_schema.lark"


def _q(value: Any) -> str:
    return json.dumps(str(value))


def _bool(value: bool) -> str:
    return "true" if value else "false"


def _val(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return _bool(value)
    if isinstance(value, (int, float)):
        return str(value)
    return _q(value)


class Writer:
    def __init__(self) -> None:
        self._lines: list[str] = []
        self._indent = 0

    def line(self, text: str) -> None:
        self._lines.append("  " * self._indent + text)

    def open(self, header: str, opener: str = "{") -> None:
        self.line(f"{header} {opener}")
        self._indent += 1

    def close(self, closer: str = "}") -> None:
        self._indent -= 1
        self.line(closer)

    def text(self) -> str:
        return "\n".join(self._lines) + "\n"


def _emit_string_list(name: str, values: Iterable[Any], w: Writer) -> None:
    rendered = ", ".join(_q(v) for v in values)
    w.line(f"{name}: [{rendered}];")


def _emit_int_list(name: str, values: Iterable[Any], w: Writer) -> None:
    rendered = ", ".join(str(int(v)) for v in values)
    w.line(f"{name}: [{rendered}];")


def _emit_date_list(name: str, values: Iterable[Any], w: Writer) -> None:
    rendered = ", ".join(str(v) for v in values)
    w.line(f"{name}: [{rendered}];")


def _emit_string_number_map(name: str, values: dict[str, Any], w: Writer) -> None:
    w.line(f"{name}: {{")
    w._indent += 1
    for key, value in values.items():
        w.line(f"{_q(key)}: {value};")
    w._indent -= 1
    w.line("};")


def _emit_string_string_map(name: str, values: dict[str, Any], w: Writer) -> None:
    w.line(f"{name}: {{")
    w._indent += 1
    for key, value in values.items():
        w.line(f"{_q(key)}: {_q(value)};")
    w._indent -= 1
    w.line("};")


def _emit_risk(risk: dict[str, Any], w: Writer) -> None:
    w.open("risk", "{")
    w.line(f"id: {_val(risk['id'])};")
    w.line(f"name: {_q(risk['name'])};")
    w.line(f"probability: {risk['probability']};")

    impact = risk.get("impact")
    if isinstance(impact, dict):
        if impact.get("type") == "percentage":
            w.line("impact: {")
            w._indent += 1
            w.line("type: percentage;")
            w.line(f"value: {impact['value']};")
            w._indent -= 1
            w.line("}")
        else:
            w.line("impact: {")
            w._indent += 1
            w.line("type: absolute;")
            w.line(f"value: {impact['value']};")
            if "unit" in impact:
                w.line(f"unit: {impact['unit']};")
            w._indent -= 1
            w.line("}")
    else:
        w.line(f"impact: {impact};")

    if "description" in risk:
        w.line(f"description: {_q(risk['description'])};")
    if "cost_impact" in risk:
        w.line(f"cost_impact: {risk['cost_impact']};")
    w.close("}")


def serialize_project_payload(payload: dict[str, Any]) -> str:
    w = Writer()

    project = payload["project"]
    w.open("project", "{")
    w.line(f"name: {_q(project['name'])};")
    if "description" in project:
        w.line(f"description: {_q(project['description'])};")
    w.line(f"start_date: {project['start_date']};")

    for key in (
        "hours_per_day",
        "currency",
        "default_hourly_rate",
        "overhead_rate",
        "fx_conversion_cost",
        "fx_overhead_rate",
        "distribution",
        "t_shirt_size_default_category",
        "team_size",
    ):
        if key in project:
            w.line(f"{key}: {_val(project[key])};")

    if "secondary_currencies" in project:
        _emit_string_list("secondary_currencies", project["secondary_currencies"], w)
    if "fx_rates" in project:
        _emit_string_number_map("fx_rates", project["fx_rates"], w)
    if "confidence_levels" in project:
        _emit_int_list("confidence_levels", project["confidence_levels"], w)

    if "probability_red_threshold" in project:
        w.line(f"probability_red_threshold: {project['probability_red_threshold']};")
    if "probability_green_threshold" in project:
        w.line(f"probability_green_threshold: {project['probability_green_threshold']};")

    if "uncertainty_factors" in project:
        _emit_string_string_map("uncertainty_factors", project["uncertainty_factors"], w)

    w.close("}")

    w.open("tasks", "[")
    for task in payload["tasks"]:
        w.open("task", "{")
        w.line(f"id: {_val(task['id'])};")
        w.line(f"name: {_q(task['name'])};")
        if "description" in task:
            w.line(f"description: {_q(task['description'])};")

        estimate = task["estimate"]
        w.open("estimate", "{")
        if "t_shirt_size" in estimate:
            w.line(f"t_shirt_size: {_q(estimate['t_shirt_size'])};")
        elif "story_points" in estimate:
            w.line(f"story_points: {estimate['story_points']};")
        else:
            if "distribution" in estimate:
                w.line(f"distribution: {estimate['distribution']};")
            w.line(f"low: {estimate['low']};")
            w.line(f"expected: {estimate['expected']};")
            w.line(f"high: {estimate['high']};")
            if "unit" in estimate:
                w.line(f"unit: {estimate['unit']};")
        w.close("}")

        if "dependencies" in task:
            _emit_string_list("dependencies", task["dependencies"], w)
        if "uncertainty_factors" in task:
            _emit_string_string_map("uncertainty_factors", task["uncertainty_factors"], w)

        for key in (
            "resources",
            "max_resources",
            "min_experience_level",
            "planning_story_points",
            "priority",
            "spillover_probability_override",
            "fixed_cost",
        ):
            if key in task:
                if key == "resources":
                    _emit_string_list("resources", task["resources"], w)
                else:
                    w.line(f"{key}: {_val(task[key])};")

        if "risks" in task:
            w.open("risks", "[")
            for risk in task["risks"]:
                _emit_risk(risk, w)
            w.close("]")

        w.close("}")
    w.close("]")

    if "project_risks" in payload:
        w.open("project_risks", "[")
        for risk in payload["project_risks"]:
            _emit_risk(risk, w)
        w.close("]")

    if "resources" in payload:
        w.open("resources", "[")
        for resource in payload["resources"]:
            w.open("resource", "{")
            for key in (
                "name",
                "id",
                "availability",
                "calendar",
                "experience_level",
                "productivity_level",
                "sickness_prob",
                "hourly_rate",
            ):
                if key in resource:
                    w.line(f"{key}: {_val(resource[key])};")
            if "planned_absence" in resource:
                _emit_date_list("planned_absence", resource["planned_absence"], w)
            w.close("}")
        w.close("]")

    if "calendars" in payload:
        w.open("calendars", "[")
        for calendar in payload["calendars"]:
            w.open("calendar", "{")
            for key in ("id", "work_hours_per_day"):
                if key in calendar:
                    w.line(f"{key}: {_val(calendar[key])};")
            if "work_days" in calendar:
                _emit_int_list("work_days", calendar["work_days"], w)
            if "holidays" in calendar:
                _emit_date_list("holidays", calendar["holidays"], w)
            w.close("}")
        w.close("]")

    if "sprint_planning" in payload:
        sprint = payload["sprint_planning"]
        w.open("sprint_planning", "{")
        if "enabled" in sprint:
            w.line(f"enabled: {_bool(bool(sprint['enabled']))};")
        w.line(f"sprint_length_weeks: {sprint['sprint_length_weeks']};")
        w.line(f"capacity_mode: {sprint['capacity_mode']};")

        for key in ("planning_confidence_level", "removed_work_treatment", "velocity_model"):
            if key in sprint:
                w.line(f"{key}: {_val(sprint[key])};")

        if "history" in sprint:
            history = sprint["history"]
            if isinstance(history, dict) and {"format", "path"}.issubset(history):
                w.line("history: external {")
                w._indent += 1
                w.line(f"format: {history['format']};")
                w.line(f"path: {_q(history['path'])};")
                w._indent -= 1
                w.line("}")
            else:
                w.open("history:", "[")
                for entry in history:
                    w.open("history_entry", "{")
                    w.line(f"sprint_id: {_q(entry['sprint_id'])};")
                    for key in (
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
                    ):
                        if key in entry:
                            w.line(f"{key}: {_val(entry[key])};")
                    w.close("}")
                w.close("]")

        if "future_sprint_overrides" in sprint:
            w.open("future_sprint_overrides:", "[")
            for override in sprint["future_sprint_overrides"]:
                w.open("future_override", "{")
                for key in (
                    "sprint_number",
                    "start_date",
                    "holiday_factor",
                    "capacity_multiplier",
                    "notes",
                ):
                    if key in override:
                        w.line(f"{key}: {_val(override[key])};")
                w.close("}")
            w.close("]")

        if "volatility_overlay" in sprint:
            w.open("volatility_overlay:", "{")
            for key, value in sprint["volatility_overlay"].items():
                w.line(f"{key}: {_val(value)};")
            w.close("}")

        if "spillover" in sprint:
            spillover = sprint["spillover"]
            w.open("spillover:", "{")
            for key in (
                "enabled",
                "model",
                "size_reference_points",
                "consumed_fraction_alpha",
                "consumed_fraction_beta",
                "logistic_slope",
                "logistic_intercept",
            ):
                if key in spillover:
                    w.line(f"{key}: {_val(spillover[key])};")
            if "size_brackets" in spillover:
                w.open("size_brackets:", "[")
                for bracket in spillover["size_brackets"]:
                    w.open("size_bracket", "{")
                    if "max_points" in bracket and bracket["max_points"] is not None:
                        w.line(f"max_points: {bracket['max_points']};")
                    w.line(f"probability: {bracket['probability']};")
                    w.close("}")
                w.close("]")
            w.close("}")

        if "sickness" in sprint:
            w.open("sickness:", "{")
            for key, value in sprint["sickness"].items():
                w.line(f"{key}: {_val(value)};")
            w.close("}")

        w.close("}")

    return w.text()


def _emit_generic_map(name: str, payload: dict[str, Any], w: Writer) -> None:
    w.line(f"{name}: {{")
    w._indent += 1
    for key, value in payload.items():
        w.line(f"{_val(key)}: {_generic_value(value)};")
    w._indent -= 1
    w.line("}")


def _generic_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return _bool(value)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return _q(value)
    if isinstance(value, list):
        return "[" + ", ".join(_generic_value(v) for v in value) + "]"
    if isinstance(value, dict):
        parts = [f"{_val(k)}: {_generic_value(v)};" for k, v in value.items()]
        if parts:
            return "{ " + " ".join(parts) + " }"
        return "{}"
    return _q(value)


def serialize_config_payload(payload: dict[str, Any]) -> str:
    w = Writer()
    for key in (
        "uncertainty_factors",
        "t_shirt_sizes",
        "t_shirt_size_categories",
        "story_points",
        "staffing",
    ):
        if key in payload:
            _emit_generic_map(key, payload[key], w)

    for key in ("t_shirt_size_default_category", "t_shirt_size_unit", "story_point_unit"):
        if key in payload:
            w.line(f"{key}: {_val(payload[key])};")

    if "simulation" in payload:
        w.open("simulation:", "{")
        for item_key in ("default_iterations", "random_seed", "max_stored_critical_paths"):
            if item_key in payload["simulation"]:
                w.line(f"{item_key}: {_val(payload['simulation'][item_key])};")
        w.close("}")

    if "lognormal" in payload:
        w.open("lognormal:", "{")
        if "high_percentile" in payload["lognormal"]:
            w.line(f"high_percentile: {_val(payload['lognormal']['high_percentile'])};")
        w.close("}")

    if "output" in payload:
        w.open("output:", "{")
        for item_key in ("formats", "include_histogram", "number_bins", "critical_path_report_limit"):
            if item_key in payload["output"]:
                if item_key == "formats":
                    _emit_string_list("formats", payload["output"][item_key], w)
                else:
                    w.line(f"{item_key}: {_val(payload['output'][item_key])};")
        w.close("}")

    if "constrained_scheduling" in payload:
        w.open("constrained_scheduling:", "{")
        for item_key in ("sickness_prob", "assignment_mode", "pass1_iterations"):
            if item_key in payload["constrained_scheduling"]:
                w.line(f"{item_key}: {_val(payload['constrained_scheduling'][item_key])};")
        w.close("}")

    if "sprint_defaults" in payload:
        w.open("sprint_defaults:", "{")
        for item_key in (
            "planning_confidence_level",
            "removed_work_treatment",
            "velocity_model",
            "volatility_disruption_probability",
            "volatility_disruption_multiplier_low",
            "volatility_disruption_multiplier_expected",
            "volatility_disruption_multiplier_high",
            "spillover_model",
            "spillover_size_reference_points",
            "spillover_size_brackets",
            "spillover_consumed_fraction_alpha",
            "spillover_consumed_fraction_beta",
            "spillover_logistic_slope",
            "spillover_logistic_intercept",
        ):
            if item_key in payload["sprint_defaults"]:
                if item_key == "spillover_size_brackets":
                    w.line(f"{item_key}: {_generic_value(payload['sprint_defaults'][item_key])};")
                else:
                    w.line(f"{item_key}: {_val(payload['sprint_defaults'][item_key])};")

        sickness = payload["sprint_defaults"].get("sickness")
        if isinstance(sickness, dict):
            w.open("sickness:", "{")
            for k, v in sickness.items():
                w.line(f"{k}: {_val(v)};")
            w.close("}")

        w.close("}")

    if "cost" in payload:
        w.open("cost:", "{")
        for item_key in ("default_hourly_rate", "overhead_rate", "currency", "include_in_output"):
            if item_key in payload["cost"]:
                w.line(f"{item_key}: {_val(payload['cost'][item_key])};")
        w.close("}")

    return w.text()


def load_payload(path: Path) -> dict[str, Any]:
    if path.suffix in {".yaml", ".yml"}:
        with open(path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
    elif path.suffix == ".toml":
        with open(path, "rb") as f:
            loaded = tomllib.load(f)
    else:
        raise ValueError(f"Unsupported file extension: {path.suffix}")

    if not isinstance(loaded, dict):
        raise ValueError("Top-level payload must be a mapping")
    return loaded


def infer_mode(payload: dict[str, Any]) -> str:
    if "project" in payload and "tasks" in payload:
        return "project"
    return "config"


def build_parser(start_rule: str) -> Lark:
    grammar = GRAMMAR_PATH.read_text(encoding="utf-8")
    return Lark(grammar, parser="earley", lexer="dynamic", start=start_rule)


def validate_payload(path: Path, mode: str, show_canonical: bool) -> int:
    payload = load_payload(path)

    if mode == "auto":
        mode = infer_mode(payload)

    canonical = (
        serialize_project_payload(payload)
        if mode == "project"
        else serialize_config_payload(payload)
    )

    if show_canonical:
        print("=== Canonical Representation ===")
        print(canonical)

    start_rule = "project_file" if mode == "project" else "config_file"
    parser = build_parser(start_rule)
    try:
        parser.parse(canonical, start=start_rule)
    except UnexpectedInput as exc:
        print(f"Lark parse failed for {path} ({mode} mode)", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Lark parse OK: {path} ({mode} mode)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="mcprojsim Lark grammar POC validator")
    parser.add_argument("input_file", type=Path, help="YAML/TOML file to validate")
    parser.add_argument(
        "--mode",
        choices=["auto", "project", "config"],
        default="auto",
        help="Validation mode. Default: auto",
    )
    parser.add_argument(
        "--show-canonical",
        action="store_true",
        help="Print the canonical intermediate representation before parsing",
    )

    args = parser.parse_args()
    return validate_payload(args.input_file, args.mode, args.show_canonical)


if __name__ == "__main__":
    raise SystemExit(main())
