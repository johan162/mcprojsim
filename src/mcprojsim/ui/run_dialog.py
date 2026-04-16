"""Run Simulation dialog (P1-12)."""

from __future__ import annotations

import os
from typing import Any

from PySide6.QtCore import Qt  # type: ignore[import-untyped]
from PySide6.QtWidgets import (  # type: ignore[import-untyped]
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QSettings  # type: ignore[import-untyped]


class RunSimulationDialog(QDialog):
    """Dialog for configuring and launching a simulation run."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Run Simulation")
        self.setMinimumWidth(440)
        self.setModal(True)
        self._settings = QSettings("mcprojsim", "mcprojsim-ui")
        self._build_ui()
        self._restore_settings()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        # --- Simulation parameters ---
        params_group = QGroupBox("Simulation Parameters")
        form = QFormLayout(params_group)
        form.setSpacing(10)
        form.setContentsMargins(12, 16, 12, 12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._iterations = QSpinBox()
        self._iterations.setRange(100, 100_000)
        self._iterations.setValue(10_000)
        self._iterations.setSingleStep(1_000)
        form.addRow("Iterations", self._iterations)

        self._seed = QSpinBox()
        self._seed.setRange(0, 999_999)
        self._seed.setValue(42)
        self._seed.setSpecialValueText("(random)")
        form.addRow("Random Seed", self._seed)

        layout.addWidget(params_group)

        # --- Output options ---
        output_group = QGroupBox("Output")
        out_layout = QVBoxLayout(output_group)
        out_layout.setContentsMargins(12, 16, 12, 12)
        out_layout.setSpacing(8)

        self._export_json = QCheckBox("JSON")
        self._export_csv = QCheckBox("CSV")
        self._export_html = QCheckBox("HTML report")
        self._export_html.setChecked(True)

        out_layout.addWidget(self._export_json)
        out_layout.addWidget(self._export_csv)
        out_layout.addWidget(self._export_html)

        # Output folder
        folder_row = QHBoxLayout()
        folder_row.setSpacing(6)
        self._output_folder = QLineEdit()
        self._output_folder.setPlaceholderText("Output folder (leave blank for current dir)")
        folder_browse = QPushButton("Browse…")
        folder_browse.setFixedWidth(80)
        folder_browse.clicked.connect(self._browse_folder)
        folder_row.addWidget(self._output_folder)
        folder_row.addWidget(folder_browse)
        out_layout.addLayout(folder_row)

        layout.addWidget(output_group)

        # --- Options ---
        self._validate_first = QCheckBox("Validate project before simulating")
        self._validate_first.setChecked(True)
        layout.addWidget(self._validate_first)

        # --- Buttons ---
        btn_box = QDialogButtonBox()
        self._run_btn = QPushButton("Run Simulation")
        self._run_btn.setProperty("role", "primary")
        cancel_btn = QPushButton("Cancel")
        btn_box.addButton(self._run_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        btn_box.addButton(cancel_btn, QDialogButtonBox.ButtonRole.RejectRole)
        self._run_btn.clicked.connect(self._on_accept)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(btn_box)

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Select Output Folder", self._output_folder.text() or os.getcwd()
        )
        if folder:
            self._output_folder.setText(folder)

    def _on_accept(self) -> None:
        self._save_settings()
        self.accept()

    def _restore_settings(self) -> None:
        self._iterations.setValue(int(self._settings.value("run/iterations", 10_000)))
        self._seed.setValue(int(self._settings.value("run/seed", 42)))
        self._export_json.setChecked(bool(self._settings.value("run/json", False)))
        self._export_csv.setChecked(bool(self._settings.value("run/csv", False)))
        self._export_html.setChecked(bool(self._settings.value("run/html", True)))
        self._output_folder.setText(str(self._settings.value("run/folder", "")))

    def _save_settings(self) -> None:
        self._settings.setValue("run/iterations", self._iterations.value())
        self._settings.setValue("run/seed", self._seed.value())
        self._settings.setValue("run/json", self._export_json.isChecked())
        self._settings.setValue("run/csv", self._export_csv.isChecked())
        self._settings.setValue("run/html", self._export_html.isChecked())
        self._settings.setValue("run/folder", self._output_folder.text())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_config(self) -> dict[str, Any]:
        """Return the dialog settings as a plain dict."""
        formats: list[str] = []
        if self._export_json.isChecked():
            formats.append("json")
        if self._export_csv.isChecked():
            formats.append("csv")
        if self._export_html.isChecked():
            formats.append("html")
        seed = self._seed.value()
        folder = self._output_folder.text().strip()
        return {
            "iterations": self._iterations.value(),
            "random_seed": seed if seed != 0 else None,
            "formats": formats,
            "output_folder": folder or None,
            "validate_first": self._validate_first.isChecked(),
        }
