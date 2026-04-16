"""Results summary pane (P1-15)."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt  # type: ignore[import-untyped]
from PySide6.QtWidgets import (  # type: ignore[import-untyped]
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from mcprojsim.models.simulation import SimulationResults


def _stat_row(label: str, value: str) -> QHBoxLayout:
    row = QHBoxLayout()
    lbl = QLabel(label + ":")
    lbl.setObjectName("hintLabel")
    lbl.setFixedWidth(200)
    val = QLabel(value)
    val.setObjectName("statValue")
    val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    val.setWordWrap(True)
    row.addWidget(lbl)
    row.addWidget(val, stretch=1)
    return row


def _section(title: str) -> tuple[QWidget, QVBoxLayout]:
    """Return a (container_widget, content_layout) pair with a visible header label."""
    outer = QWidget()
    outer_layout = QVBoxLayout(outer)
    outer_layout.setContentsMargins(0, 8, 0, 0)
    outer_layout.setSpacing(0)

    header = QLabel(title)
    header.setObjectName("sectionHeader")
    outer_layout.addWidget(header)

    card = QFrame()
    card.setObjectName("resultCard")
    card.setFrameShape(QFrame.Shape.NoFrame)
    content = QVBoxLayout(card)
    content.setContentsMargins(12, 10, 12, 10)
    content.setSpacing(6)
    outer_layout.addWidget(card)

    return outer, content


class ResultsPane(QWidget):
    """Shows a summary of the last simulation run."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._html_report_path: Path | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(16, 12, 16, 12)
        self._layout.setSpacing(12)

        self._placeholder = QLabel("No results yet. Run a simulation to see the summary here.")
        self._placeholder.setObjectName("hintLabel")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self._placeholder)
        self._layout.addStretch()

    def _clear_results(self) -> None:
        """Remove previous result widgets."""
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    def show_results(self, results: SimulationResults, html_report: Path | None = None) -> None:
        """Populate the pane with stats from *results*."""
        self._html_report_path = html_report
        self._clear_results()

        hours_per_day = results.hours_per_day or 8.0

        # ── Project Summary ──────────────────────────────────────────────────
        proj_outer, proj_layout = _section("Project Summary")
        proj_layout.addLayout(_stat_row("Project", results.project_name))
        proj_layout.addLayout(_stat_row("Iterations", f"{results.iterations:,}"))
        proj_layout.addLayout(_stat_row("Schedule mode", results.schedule_mode))
        proj_layout.addLayout(_stat_row("Hours per day", f"{hours_per_day:.0f}"))
        if results.max_parallel_tasks:
            proj_layout.addLayout(_stat_row("Max parallel tasks", str(results.max_parallel_tasks)))
        self._layout.addWidget(proj_outer)

        # ── Calendar Time Summary ─────────────────────────────────────────────
        cal_outer, cal_layout = _section("Calendar Time Summary")
        mean_days = results.mean / hours_per_day
        median_days = results.median / hours_per_day
        min_days = results.min_duration / hours_per_day
        max_days = results.max_duration / hours_per_day
        cal_layout.addLayout(_stat_row("Mean", f"{results.mean:.0f} h  ({mean_days:.1f} days)"))
        cal_layout.addLayout(_stat_row("Median (P50)", f"{results.median:.0f} h  ({median_days:.1f} days)"))
        cal_layout.addLayout(_stat_row("Std deviation", f"{results.std_dev:.0f} h"))
        cal_layout.addLayout(_stat_row("Minimum", f"{results.min_duration:.0f} h  ({min_days:.1f} days)"))
        cal_layout.addLayout(_stat_row("Maximum", f"{results.max_duration:.0f} h  ({max_days:.1f} days)"))
        self._layout.addWidget(cal_outer)

        # ── Effort Summary ────────────────────────────────────────────────────
        if results.effort_durations is not None and len(results.effort_durations) > 0:
            import numpy as np
            eff_mean = float(np.mean(results.effort_durations))
            eff_median = float(np.median(results.effort_durations))
            eff_std = float(np.std(results.effort_durations))
            eff_min = float(np.min(results.effort_durations))
            eff_max = float(np.max(results.effort_durations))
            eff_outer, eff_layout = _section("Effort Summary")
            eff_layout.addLayout(_stat_row("Mean", f"{eff_mean:.0f} person-hours  ({eff_mean / hours_per_day:.1f} person-days)"))
            eff_layout.addLayout(_stat_row("Median (P50)", f"{eff_median:.0f} person-hours  ({eff_median / hours_per_day:.1f} person-days)"))
            eff_layout.addLayout(_stat_row("Std deviation", f"{eff_std:.0f} person-hours"))
            eff_layout.addLayout(_stat_row("Minimum", f"{eff_min:.0f} person-hours"))
            eff_layout.addLayout(_stat_row("Maximum", f"{eff_max:.0f} person-hours"))
            self._layout.addWidget(eff_outer)

        # ── Calendar Time Confidence Intervals ────────────────────────────────
        if results.percentiles:
            ci_outer, ci_layout = _section("Calendar Time Confidence Intervals")
            for p in sorted(results.percentiles.keys()):
                hours = results.percentiles[p]
                days = hours / hours_per_day
                delivery = results.delivery_date(hours)
                date_str = f"  →  {delivery.isoformat()}" if delivery else ""
                ci_layout.addLayout(_stat_row(f"P{p}", f"{hours:.0f} h  ({days:.1f} days){date_str}"))
            self._layout.addWidget(ci_outer)

        # ── Effort Confidence Intervals ───────────────────────────────────────
        if results.effort_percentiles:
            eci_outer, eci_layout = _section("Effort Confidence Intervals")
            for p in sorted(results.effort_percentiles.keys()):
                eh = results.effort_percentiles[p]
                epd = eh / hours_per_day
                eci_layout.addLayout(_stat_row(f"P{p}", f"{eh:.0f} person-hours  ({epd:.1f} person-days)"))
            self._layout.addWidget(eci_outer)

        # ── Cost (if available) ───────────────────────────────────────────────
        if results.costs is not None and results.cost_percentiles:
            cost_outer, cost_layout = _section("Estimated Cost")
            currency = results.currency or "$"
            if results.cost_mean is not None:
                cost_layout.addLayout(_stat_row("Mean", f"{currency}{results.cost_mean:,.0f}"))
            for p in sorted(results.cost_percentiles.keys()):
                v = results.cost_percentiles[p]
                cost_layout.addLayout(_stat_row(f"P{p}", f"{currency}{v:,.0f}"))
            self._layout.addWidget(cost_outer)

        # ── Most Critical Tasks ───────────────────────────────────────────────
        if results.critical_path_frequency:
            cp_outer, cp_layout = _section("Most Critical Tasks")
            cp_freqs = results.get_critical_path()
            sorted_tasks = sorted(cp_freqs.items(), key=lambda kv: kv[1], reverse=True)
            for task_id, freq in sorted_tasks[:10]:
                cp_layout.addLayout(_stat_row(task_id, f"{freq * 100:.0f}% of runs"))
            self._layout.addWidget(cp_outer)

        # ── HTML report button ────────────────────────────────────────────────
        if html_report and html_report.exists():
            btn_row = QHBoxLayout()
            open_btn = QPushButton("Open HTML Report")
            open_btn.setProperty("role", "primary")
            open_btn.clicked.connect(lambda: self._open_report(html_report))
            btn_row.addStretch()
            btn_row.addWidget(open_btn)
            self._layout.addLayout(btn_row)

        self._layout.addStretch()

    def _open_report(self, path: Path) -> None:
        import subprocess
        import sys
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        elif sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def show_error(self, message: str) -> None:
        self._clear_results()
        lbl = QLabel(f"Simulation failed:\n{message}")
        lbl.setObjectName("errorLabel")
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._layout.addWidget(lbl)
        self._layout.addStretch()

    def show_placeholder(self) -> None:
        self._clear_results()
        ph = QLabel("No results yet. Run a simulation to see the summary here.")
        ph.setObjectName("hintLabel")
        ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(ph)
        self._layout.addStretch()
