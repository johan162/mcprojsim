"""Project basics form widget (P1-05)."""

from __future__ import annotations

import datetime
from typing import Any

from PySide6.QtCore import Qt, Signal  # type: ignore[import-untyped]
from PySide6.QtGui import QRegularExpressionValidator  # type: ignore[import-untyped]
from PySide6.QtCore import QRegularExpression  # type: ignore[import-untyped]
from PySide6.QtWidgets import (  # type: ignore[import-untyped]
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QTextEdit,
    QWidget,
)


class ProjectBasicsWidget(QWidget):
    """Form for editing the top-level project settings."""

    dataChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._building = False
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QFormLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Header
        header = QLabel("Project Details")
        header.setObjectName("sectionHeader")
        layout.addRow(header)

        # Name
        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. Auth Service Rewrite")
        self._name.setMaxLength(120)
        layout.addRow("Name *", self._name)

        # Start date
        self._start_date = QLineEdit()
        self._start_date.setPlaceholderText("YYYY-MM-DD")
        self._start_date.setMaxLength(10)
        _date_re = QRegularExpression(r"\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])")
        self._start_date.setValidator(QRegularExpressionValidator(_date_re))
        self._start_date.setText(datetime.date.today().isoformat())
        layout.addRow("Start Date *", self._start_date)

        # Description
        self._description = QTextEdit()
        self._description.setPlaceholderText("Optional — brief summary of the project.")
        self._description.setFixedHeight(80)
        layout.addRow("Description", self._description)

        # Hours per day
        self._hours_per_day = QDoubleSpinBox()
        self._hours_per_day.setRange(1.0, 24.0)
        self._hours_per_day.setSingleStep(0.5)
        self._hours_per_day.setValue(8.0)
        self._hours_per_day.setSuffix(" h")
        self._hours_per_day.setDecimals(1)
        layout.addRow("Hours / Day", self._hours_per_day)

        # Validation label
        self._validation_label = QLabel("")
        self._validation_label.setObjectName("errorLabel")
        layout.addRow("", self._validation_label)

        # Connect change signals
        self._name.textChanged.connect(self._on_changed)
        self._start_date.textChanged.connect(self._on_changed)
        self._description.textChanged.connect(self._on_changed)
        self._hours_per_day.valueChanged.connect(self._on_changed)

        # Wrap in scroll area (this widget IS the scroll content; parent wraps)
        self.setLayout(layout)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _on_changed(self) -> None:
        if not self._building:
            self._validate()
            self.dataChanged.emit()

    def _validate(self) -> bool:
        if not self._name.text().strip():
            self._validation_label.setText("Project name is required.")
            self._name.setProperty("invalid", True)
            self._name.style().unpolish(self._name)
            self._name.style().polish(self._name)
            return False
        self._validation_label.setText("")
        self._name.setProperty("invalid", False)
        self._name.style().unpolish(self._name)
        self._name.style().polish(self._name)
        return True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_valid(self) -> bool:
        return bool(self._name.text().strip())

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self._name.text().strip(),
            "description": self._description.toPlainText().strip(),
            "start_date": self._start_date.text().strip(),
            "hours_per_day": self._hours_per_day.value(),
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        self._building = True
        try:
            self._name.setText(str(data.get("name", "")))
            self._description.setPlainText(str(data.get("description", "")))
            raw_date = data.get("start_date", "")
            if raw_date:
                self._start_date.setText(str(raw_date))
            self._hours_per_day.setValue(float(data.get("hours_per_day", 8.0)))
        finally:
            self._building = False
        self._validate()
        self.dataChanged.emit()


def make_scrollable(widget: QWidget) -> QScrollArea:
    """Wrap *widget* in a scroll area and return the scroll area."""
    scroll = QScrollArea()
    scroll.setWidget(widget)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    return scroll
