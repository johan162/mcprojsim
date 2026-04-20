"""Task editor panel — slide-in dialog for creating / editing tasks (P1-08)."""

from __future__ import annotations

import re
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

_UNITS = ["days", "hours", "weeks"]
_STORY_POINTS = [1, 2, 3, 5, 8, 13, 21]
_T_SHIRT_SIZES = ["XS", "S", "M", "L", "XL", "XXL"]
_T_SHIRT_CATEGORIES = ["story", "bug", "epic", "business", "initiative"]


def _num_field(placeholder: str = "", tooltip: str = "") -> QLineEdit:
    """Return a QLineEdit for positive numeric input (no spin arrows)."""
    field = QLineEdit()
    field.setPlaceholderText(placeholder)
    if tooltip:
        field.setToolTip(tooltip)
    v = QDoubleValidator(0.0, 999_999.0, 2, field)
    v.setNotation(QDoubleValidator.Notation.StandardNotation)
    field.setValidator(v)
    return field


class TaskEditorDialog(QDialog):
    """Modal dialog for creating or editing a task."""

    taskSaved = Signal(dict)  # emits the task dict when saved

    def __init__(
        self,
        task: dict[str, Any] | None = None,
        existing_task_ids: list[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._existing_ids = set(existing_task_ids or [])
        self._edit_task_id = task.get("id", "") if task else ""
        if self._edit_task_id:
            self._existing_ids.discard(self._edit_task_id)
        self.setWindowTitle("New Task" if task is None else "Edit Task")
        self.setMinimumWidth(500)
        self.setModal(True)
        self._build_ui()
        if task:
            self._populate(task)
        else:
            self._populate({})

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        # ---- Basics tab ----
        basics_widget = QWidget()
        form = QFormLayout(basics_widget)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # ID
        self._id_field = QLineEdit()
        self._id_field.setPlaceholderText("e.g. task_1 (letters, digits, _)")
        self._id_err = QLabel("")
        self._id_err.setObjectName("errorLabel")
        form.addRow("ID *", self._id_field)
        form.addRow("", self._id_err)

        # Name
        self._name_field = QLineEdit()
        self._name_field.setPlaceholderText("Short descriptive name")
        self._name_err = QLabel("")
        self._name_err.setObjectName("errorLabel")
        form.addRow("Name *", self._name_field)
        form.addRow("", self._name_err)

        # Estimate group with three sub-tabs
        est_group = QGroupBox("Estimate")
        est_group_layout = QVBoxLayout(est_group)
        est_group_layout.setContentsMargins(8, 8, 8, 8)
        est_group_layout.setSpacing(4)

        self._est_tabs = QTabWidget()
        est_group_layout.addWidget(self._est_tabs)

        # Sub-tab 0: Three-Point
        tp_widget = QWidget()
        tp_form = QFormLayout(tp_widget)
        tp_form.setContentsMargins(8, 8, 8, 8)
        tp_form.setSpacing(8)
        tp_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        tp_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._est_low = _num_field("e.g. 3", "Optimistic (best-case) estimate")
        self._est_low.setText("3")
        self._est_expected = _num_field("e.g. 5", "Most likely estimate")
        self._est_expected.setText("5")
        self._est_high = _num_field("e.g. 8", "Pessimistic (worst-case) estimate")
        self._est_high.setText("8")

        self._est_unit = QComboBox()
        self._est_unit.addItems(_UNITS)
        self._est_unit.setCurrentText("days")

        self._est_err = QLabel("")
        self._est_err.setObjectName("errorLabel")

        tp_form.addRow("Low *", self._est_low)
        tp_form.addRow("Expected *", self._est_expected)
        tp_form.addRow("High *", self._est_high)
        tp_form.addRow("Unit", self._est_unit)
        tp_form.addRow("", self._est_err)
        self._est_tabs.addTab(tp_widget, "Three-Point")

        # Sub-tab 1: Story Points
        sp_widget = QWidget()
        sp_form = QFormLayout(sp_widget)
        sp_form.setContentsMargins(8, 8, 8, 8)
        sp_form.setSpacing(8)
        sp_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        sp_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._sp_field = QComboBox()
        self._sp_field.addItems([str(p) for p in _STORY_POINTS])
        self._sp_field.setCurrentIndex(2)  # default: 3 pts

        sp_form.addRow("Points *", self._sp_field)
        sp_hint = QLabel("Low / expected / high are resolved from the project config.")
        sp_hint.setObjectName("hintLabel")
        sp_hint.setWordWrap(True)
        sp_form.addRow("", sp_hint)
        self._est_tabs.addTab(sp_widget, "Story Points")

        # Sub-tab 2: T-Shirt Size
        ts_widget = QWidget()
        ts_form = QFormLayout(ts_widget)
        ts_form.setContentsMargins(8, 8, 8, 8)
        ts_form.setSpacing(8)
        ts_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        ts_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._ts_size = QComboBox()
        self._ts_size.addItems(_T_SHIRT_SIZES)
        self._ts_size.setCurrentText("M")

        self._ts_category = QComboBox()
        self._ts_category.addItems(_T_SHIRT_CATEGORIES)
        self._ts_category.setCurrentText("story")

        ts_form.addRow("Size *", self._ts_size)
        ts_form.addRow("Category", self._ts_category)
        ts_hint = QLabel("Low / expected / high are resolved from the project config.")
        ts_hint.setObjectName("hintLabel")
        ts_hint.setWordWrap(True)
        ts_form.addRow("", ts_hint)
        self._est_tabs.addTab(ts_widget, "T-Shirt Size")

        form.addRow(est_group)

        # Dependencies
        self._deps_field = QLineEdit()
        self._deps_field.setPlaceholderText("Comma-separated task IDs, e.g. task_1, task_2")
        form.addRow("Dependencies", self._deps_field)

        # Fixed cost
        self._fixed_cost_field = QDoubleSpinBox()
        self._fixed_cost_field.setRange(0.0, 10_000_000.0)
        self._fixed_cost_field.setValue(0.0)
        self._fixed_cost_field.setSingleStep(100.0)
        self._fixed_cost_field.setPrefix("$ ")
        self._fixed_cost_field.setDecimals(2)
        form.addRow("Fixed Cost", self._fixed_cost_field)

        # Notes
        self._description_field = QTextEdit()
        self._description_field.setPlaceholderText("Optional notes about this task.")
        self._description_field.setFixedHeight(72)
        form.addRow("Notes", self._description_field)

        self._tabs.addTab(basics_widget, "Basics")

        # ---- Button box ----
        self._button_box = QDialogButtonBox()
        self._save_btn = QPushButton("Save")
        self._save_btn.setProperty("role", "primary")
        self._cancel_btn = QPushButton("Cancel")
        self._button_box.addButton(self._save_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        self._button_box.addButton(self._cancel_btn, QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(self._button_box)

        self._save_btn.clicked.connect(self._on_save)
        self._cancel_btn.clicked.connect(self.reject)

        # Live validation
        self._id_field.textChanged.connect(self._validate)
        self._name_field.textChanged.connect(self._validate)
        self._est_low.textChanged.connect(self._validate)
        self._est_expected.textChanged.connect(self._validate)
        self._est_high.textChanged.connect(self._validate)
        self._est_tabs.currentChanged.connect(self._validate)
        self._validate()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    _ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]*$")

    def _populate(self, task: dict[str, Any]) -> None:
        self._id_field.setText(str(task.get("id", "")))
        self._name_field.setText(str(task.get("name", "")))

        est = task.get("estimate", {})
        if isinstance(est, dict):
            if "story_points" in est:
                idx = self._sp_field.findText(str(est["story_points"]))
                if idx >= 0:
                    self._sp_field.setCurrentIndex(idx)
                self._est_tabs.setCurrentIndex(1)
            elif "t_shirt_size" in est:
                raw = str(est["t_shirt_size"])
                if "." in raw:
                    category, size = raw.split(".", 1)
                    idx_c = self._ts_category.findText(category.lower())
                    if idx_c >= 0:
                        self._ts_category.setCurrentIndex(idx_c)
                    idx_s = self._ts_size.findText(size.upper())
                    if idx_s >= 0:
                        self._ts_size.setCurrentIndex(idx_s)
                else:
                    idx_s = self._ts_size.findText(raw.upper())
                    if idx_s >= 0:
                        self._ts_size.setCurrentIndex(idx_s)
                self._est_tabs.setCurrentIndex(2)
            else:
                self._est_low.setText(str(est.get("low", est.get("min", 3))))
                self._est_expected.setText(
                    str(est.get("expected", est.get("most_likely", 5)))
                )
                self._est_high.setText(str(est.get("high", est.get("max", 8))))
                unit = str(est.get("unit", "days"))
                idx = self._est_unit.findText(unit)
                self._est_unit.setCurrentIndex(idx if idx >= 0 else 0)
                self._est_tabs.setCurrentIndex(0)
        else:
            try:
                v = float(est)
            except (ValueError, TypeError):
                v = 5.0
            self._est_expected.setText(str(v))
            self._est_low.setText(str(max(0.1, round(v * 0.7, 1))))
            self._est_high.setText(str(round(v * 1.5, 1)))
            self._est_tabs.setCurrentIndex(0)

        deps = task.get("dependencies", [])
        if isinstance(deps, list):
            self._deps_field.setText(", ".join(str(d) for d in deps))
        elif isinstance(deps, str):
            self._deps_field.setText(deps)

        self._fixed_cost_field.setValue(float(task.get("fixed_cost", 0.0)))
        self._description_field.setPlainText(str(task.get("description", "")))

    def _validate(self) -> bool:
        ok = True

        task_id = self._id_field.text().strip()
        if not task_id:
            self._id_err.setText("ID is required.")
            ok = False
        elif not self._ID_RE.match(task_id):
            self._id_err.setText(
                "ID must start with a letter or _ and contain only letters, digits, _ or -."
            )
            ok = False
        elif task_id in self._existing_ids:
            self._id_err.setText("This ID is already used by another task.")
            ok = False
        else:
            self._id_err.setText("")

        if not self._name_field.text().strip():
            self._name_err.setText("Name is required.")
            ok = False
        else:
            self._name_err.setText("")

        if self._est_tabs.currentIndex() == 0:
            try:
                low = float(self._est_low.text() or "0")
                expected = float(self._est_expected.text() or "0")
                high = float(self._est_high.text() or "0")
            except ValueError:
                self._est_err.setText("Enter valid numbers for low, expected, and high.")
                ok = False
            else:
                if not (0 < low <= expected <= high):
                    self._est_err.setText("Required: 0 < Low \u2264 Expected \u2264 High.")
                    ok = False
                else:
                    self._est_err.setText("")
        else:
            self._est_err.setText("")

        self._save_btn.setEnabled(ok)
        return ok

    def _on_save(self) -> None:
        if not self._validate():
            return
        deps_text = self._deps_field.text().strip()
        deps: list[str] = (
            [d.strip() for d in deps_text.split(",") if d.strip()] if deps_text else []
        )
        est_tab = self._est_tabs.currentIndex()
        if est_tab == 0:
            estimate: dict[str, Any] = {
                "low": float(self._est_low.text()),
                "expected": float(self._est_expected.text()),
                "high": float(self._est_high.text()),
                "unit": self._est_unit.currentText(),
            }
        elif est_tab == 1:
            estimate = {"story_points": int(self._sp_field.currentText())}
        else:
            estimate = {
                "t_shirt_size": f"{self._ts_category.currentText()}.{self._ts_size.currentText()}"
            }

        task: dict[str, Any] = {
            "id": self._id_field.text().strip(),
            "name": self._name_field.text().strip(),
            "estimate": estimate,
        }
        if deps:
            task["dependencies"] = deps
        fixed_cost = self._fixed_cost_field.value()
        if fixed_cost > 0.0:
            task["fixed_cost"] = fixed_cost
        desc = self._description_field.toPlainText().strip()
        if desc:
            task["description"] = desc
        self.taskSaved.emit(task)
        self.accept()
