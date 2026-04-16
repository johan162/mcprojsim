"""Main application window (P1-04, P1-10, P1-11, P1-14, P1-16, P1-19)."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer  # type: ignore[import-untyped]
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence  # type: ignore[import-untyped]
from PySide6.QtWidgets import (  # type: ignore[import-untyped]
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QSplitter,
    QStackedWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QSettings, QSize  # type: ignore[import-untyped]

import mcprojsim
from mcprojsim.config import Config
from mcprojsim.exporters.csv_exporter import CSVExporter
from mcprojsim.exporters.html_exporter import HTMLExporter
from mcprojsim.exporters.json_exporter import JSONExporter
from mcprojsim.models.simulation import SimulationResults
from mcprojsim.parsers.yaml_parser import YAMLParser

from mcprojsim.ui.autosave import AutoSave
from mcprojsim.ui.basics_form import ProjectBasicsWidget, make_scrollable
from mcprojsim.ui.project_model import UIProjectModel
from mcprojsim.ui.results_pane import ResultsPane
from mcprojsim.ui.run_dialog import RunSimulationDialog
from mcprojsim.ui.simulation_worker import SimulationWorker
from mcprojsim.ui.task_editor import TaskEditorDialog
from mcprojsim.ui.task_table import TaskTableWidget
from mcprojsim.ui.yaml_highlighter import YAMLSyntaxHighlighter

# Section IDs used in the nav list
_SECTIONS = [
    ("Project Details", "basics"),
    ("Tasks", "tasks"),
    ("Risks", "risks"),
    ("Resources", "resources"),
    ("Results", "results"),
]


class MainWindow(QMainWindow):
    """Main application window for mcprojsim."""

    def __init__(self) -> None:
        super().__init__()
        self._settings = QSettings("mcprojsim", "mcprojsim-ui")
        self._model = UIProjectModel()
        self._current_file: Path | None = None
        self._dirty = False
        self._worker: SimulationWorker | None = None
        self._last_results: SimulationResults | None = None
        self._last_html_report: Path | None = None
        self._autosave = AutoSave(parent=self)

        self._build_ui()
        self._build_menus()
        self._build_toolbar()
        self._wire_signals()
        self._restore_geometry()
        self._autosave.start(lambda: self._model.to_yaml())

        # Recovery check
        QTimer.singleShot(0, self._check_recovery)

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.setWindowTitle("mcprojsim")
        self.setMinimumSize(QSize(900, 600))

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Outer horizontal splitter: [nav | content]
        self._h_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._h_splitter.setChildrenCollapsible(False)
        root.addWidget(self._h_splitter, 1)

        # -- Left nav list --
        self._nav = QListWidget()
        self._nav.setObjectName("navList")
        self._nav.setFixedWidth(180)
        for title, _ in _SECTIONS:
            self._nav.addItem(title)
        self._nav.setCurrentRow(0)
        self._h_splitter.addWidget(self._nav)

        # -- Right area: vertical splitter [form stack | bottom pane] --
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self._v_splitter = QSplitter(Qt.Orientation.Vertical)
        self._v_splitter.setChildrenCollapsible(False)
        right_layout.addWidget(self._v_splitter, 1)

        # Form stack
        self._stack = QStackedWidget()
        self._v_splitter.addWidget(self._stack)

        # Build form pages
        self._basics_form = ProjectBasicsWidget()
        self._stack.addWidget(make_scrollable(self._basics_form))  # 0

        self._task_table = TaskTableWidget()
        task_container = QWidget()
        tc_layout = QVBoxLayout(task_container)
        tc_layout.setContentsMargins(16, 12, 16, 12)
        tc_layout.addWidget(QLabel("Tasks"))
        tc_layout.addWidget(self._task_table)
        self._stack.addWidget(task_container)  # 1

        # Risks placeholder
        risks_ph = QLabel("Risk editor coming soon.\nAdd risks directly in the YAML preview below.")
        risks_ph.setObjectName("hintLabel")
        risks_ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stack.addWidget(risks_ph)  # 2

        # Resources placeholder
        res_ph = QLabel("Resource editor coming soon.\nAdd resources directly in the YAML preview below.")
        res_ph.setObjectName("hintLabel")
        res_ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stack.addWidget(res_ph)  # 3

        # Results pane
        self._results_pane = ResultsPane()
        self._stack.addWidget(self._results_pane)  # 4

        # Bottom pane: YAML preview + progress
        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(0)

        yaml_header = QWidget()
        yaml_header.setFixedHeight(28)
        yaml_header_layout = QHBoxLayout(yaml_header)
        yaml_header_layout.setContentsMargins(12, 4, 12, 4)
        yaml_lbl = QLabel("YAML Preview")
        yaml_lbl.setObjectName("sectionHeader")
        yaml_header_layout.addWidget(yaml_lbl)
        yaml_header_layout.addStretch()
        bottom_layout.addWidget(yaml_header)

        self._yaml_editor = QPlainTextEdit()
        self._yaml_editor.setObjectName("yamlEditor")
        self._yaml_editor.setReadOnly(True)
        self._yaml_editor.setMinimumHeight(80)
        self._yaml_highlighter = YAMLSyntaxHighlighter(self._yaml_editor.document())
        bottom_layout.addWidget(self._yaml_editor)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setVisible(False)
        self._progress_bar.setFixedHeight(20)
        bottom_layout.addWidget(self._progress_bar)

        self._v_splitter.addWidget(bottom)
        self._v_splitter.setSizes([400, 200])
        self._h_splitter.addWidget(right_widget)
        self._h_splitter.setSizes([180, 720])

        # Status bar
        self._status_label = QLabel("Ready")
        self.statusBar().addWidget(self._status_label)

    def _build_menus(self) -> None:
        mb = self.menuBar()

        # File
        file_menu = mb.addMenu("&File")
        self._act_new = QAction("&New", self)
        self._act_new.setShortcut(QKeySequence.StandardKey.New)
        self._act_open = QAction("&Open…", self)
        self._act_open.setShortcut(QKeySequence.StandardKey.Open)
        self._act_save = QAction("&Save", self)
        self._act_save.setShortcut(QKeySequence.StandardKey.Save)
        self._act_save_as = QAction("Save &As…", self)
        self._act_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self._act_quit = QAction("&Quit", self)
        self._act_quit.setShortcut(QKeySequence.StandardKey.Quit)
        file_menu.addAction(self._act_new)
        file_menu.addAction(self._act_open)
        file_menu.addSeparator()
        file_menu.addAction(self._act_save)
        file_menu.addAction(self._act_save_as)
        file_menu.addSeparator()
        self._recent_menu = file_menu.addMenu("Recent Files")
        file_menu.addSeparator()
        file_menu.addAction(self._act_quit)

        # Edit
        edit_menu = mb.addMenu("&Edit")
        self._act_validate = QAction("&Validate Project", self)
        self._act_validate.setShortcut(QKeySequence("Ctrl+K"))
        edit_menu.addAction(self._act_validate)

        # Help
        help_menu = mb.addMenu("&Help")
        self._act_about = QAction("&About mcprojsim", self)
        help_menu.addAction(self._act_about)

        # Wire menu actions
        self._act_new.triggered.connect(self._on_new)
        self._act_open.triggered.connect(self._on_open)
        self._act_save.triggered.connect(self._on_save)
        self._act_save_as.triggered.connect(self._on_save_as)
        self._act_quit.triggered.connect(self.close)
        self._act_validate.triggered.connect(self._on_validate)
        self._act_about.triggered.connect(self._on_about)

        self._refresh_recent_menu()

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(tb)

        self._tb_new = tb.addAction("New")
        self._tb_open = tb.addAction("Open")
        self._tb_save = tb.addAction("Save")
        tb.addSeparator()
        self._tb_validate = tb.addAction("Validate")
        tb.addSeparator()
        self._tb_run = tb.addAction("▶  Run Simulation")

        # Give run button a distinct object name for stylesheet targeting
        tb_widgets = tb.widgetForAction(self._tb_run)
        if tb_widgets is not None:
            tb_widgets.setObjectName("runBtn")

        tb.addSeparator()
        self._tb_cancel = tb.addAction("Cancel")
        self._tb_cancel.setEnabled(False)

        self._tb_new.triggered.connect(self._on_new)
        self._tb_open.triggered.connect(self._on_open)
        self._tb_save.triggered.connect(self._on_save)
        self._tb_validate.triggered.connect(self._on_validate)
        self._tb_run.triggered.connect(self._on_run)
        self._tb_cancel.triggered.connect(self._on_cancel)

    def _wire_signals(self) -> None:
        self._nav.currentRowChanged.connect(self._on_nav_changed)
        self._basics_form.dataChanged.connect(self._on_basics_changed)
        self._task_table.tasksChanged.connect(self._on_tasks_changed)
        self._task_table.taskEditRequested.connect(self._on_task_edit_requested)
        self._model.changed.connect(self._refresh_yaml)

    # ------------------------------------------------------------------
    # Geometry persistence
    # ------------------------------------------------------------------

    def _restore_geometry(self) -> None:
        geom = self._settings.value("window/geometry")
        if geom:
            self.restoreGeometry(geom)
        state = self._settings.value("window/state")
        if state:
            self.restoreState(state)

    def _save_geometry(self) -> None:
        self._settings.setValue("window/geometry", self.saveGeometry())
        self._settings.setValue("window/state", self.saveState())

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _on_nav_changed(self, row: int) -> None:
        self._stack.setCurrentIndex(row)

    # ------------------------------------------------------------------
    # Model → UI sync
    # ------------------------------------------------------------------

    def _refresh_yaml(self) -> None:
        self._yaml_editor.setPlainText(self._model.to_yaml())

    def _on_basics_changed(self) -> None:
        self._model.set_project_basics(self._basics_form.to_dict())
        self._mark_dirty()

    def _on_tasks_changed(self) -> None:
        self._model.set_tasks(self._task_table.all_tasks())
        self._mark_dirty()

    # ------------------------------------------------------------------
    # Task editor
    # ------------------------------------------------------------------

    def _on_task_edit_requested(self, row: int) -> None:
        existing = [t.get("id", "") for t in self._model.get_tasks()]
        task_data = self._model.get_tasks()[row] if row >= 0 else None
        dialog = TaskEditorDialog(
            task=task_data,
            existing_task_ids=existing,
            parent=self,
        )
        dialog.taskSaved.connect(lambda t: self._task_table.apply_task_edit(row, t))
        dialog.exec()

    # ------------------------------------------------------------------
    # Dirty tracking
    # ------------------------------------------------------------------

    def _mark_dirty(self, dirty: bool = True) -> None:
        self._dirty = dirty
        self._update_title()

    def _update_title(self) -> None:
        name = self._current_file.name if self._current_file else "Untitled"
        prefix = "* " if self._dirty else ""
        project_name = self._model.get_project_basics().get("name", "")
        if project_name:
            self.setWindowTitle(f"{prefix}{project_name} — {name} — mcprojsim")
        else:
            self.setWindowTitle(f"{prefix}{name} — mcprojsim")

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def _check_unsaved_changes(self) -> bool:
        """Return True if it is safe to proceed (discard or save)."""
        if not self._dirty:
            return True
        reply = QMessageBox.question(
            self,
            "Unsaved Changes",
            "The project has unsaved changes. Save before continuing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Cancel:
            return False
        if reply == QMessageBox.StandardButton.Save:
            return self._on_save()
        return True

    def _on_new(self) -> None:
        if not self._check_unsaved_changes():
            return
        self._model.reset()
        self._current_file = None
        self._mark_dirty(False)
        self._load_model_into_forms()
        self._results_pane.show_placeholder()
        self._status_label.setText("New project.")

    def _on_open(self) -> None:
        if not self._check_unsaved_changes():
            return
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", "YAML Files (*.yaml *.yml);;All Files (*)"
        )
        if not path_str:
            return
        self._load_file(Path(path_str))

    def _load_file(self, path: Path) -> None:
        try:
            text = path.read_text(encoding="utf-8")
            self._model.from_yaml(text)
            self._current_file = path
            self._mark_dirty(False)
            self._load_model_into_forms()
            self._add_recent(str(path))
            self._status_label.setText(f"Opened {path.name}")
        except Exception as exc:
            QMessageBox.critical(self, "Open Error", f"Could not open file:\n{exc}")

    def _on_save(self) -> bool:
        if self._current_file is None:
            return self._on_save_as()
        return self._save_to(self._current_file)

    def _on_save_as(self) -> bool:
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Save Project", "", "YAML Files (*.yaml);;All Files (*)"
        )
        if not path_str:
            return False
        path = Path(path_str)
        if path.suffix == "":
            path = path.with_suffix(".yaml")
        return self._save_to(path)

    def _save_to(self, path: Path) -> bool:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self._model.to_yaml(), encoding="utf-8")
            self._current_file = path
            self._mark_dirty(False)
            self._add_recent(str(path))
            self._status_label.setText(f"Saved {path.name}")
            return True
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", f"Could not save file:\n{exc}")
            return False

    def _load_model_into_forms(self) -> None:
        basics = self._model.get_project_basics()
        self._basics_form.from_dict(basics)
        self._task_table.set_tasks(self._model.get_tasks())

    # ------------------------------------------------------------------
    # Recent files
    # ------------------------------------------------------------------

    def _add_recent(self, path_str: str) -> None:
        recents: list[str] = list(self._settings.value("file/recents", []) or [])
        if path_str in recents:
            recents.remove(path_str)
        recents.insert(0, path_str)
        recents = recents[:10]
        self._settings.setValue("file/recents", recents)
        self._refresh_recent_menu()

    def _refresh_recent_menu(self) -> None:
        self._recent_menu.clear()
        recents: list[str] = list(self._settings.value("file/recents", []) or [])
        for path_str in recents:
            action = self._recent_menu.addAction(Path(path_str).name)
            action.setData(path_str)
            action.triggered.connect(lambda checked=False, p=path_str: self._load_file(Path(p)))
        if not recents:
            empty = self._recent_menu.addAction("(empty)")
            empty.setEnabled(False)

    # ------------------------------------------------------------------
    # Validation (P1-10)
    # ------------------------------------------------------------------

    def _on_validate(self) -> None:
        try:
            parser = YAMLParser()
            parser.parse_dict(self._model.to_dict())
            QMessageBox.information(self, "Validation", "Project is valid ✓")
            self._status_label.setText("Project validated successfully.")
        except Exception as exc:
            QMessageBox.warning(self, "Validation Errors", str(exc))
            self._status_label.setText("Validation failed — see dialog.")

    # ------------------------------------------------------------------
    # Run simulation (P1-12, P1-13, P1-14)
    # ------------------------------------------------------------------

    def _on_run(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return

        dialog = RunSimulationDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        run_cfg = dialog.get_config()

        if run_cfg.get("validate_first"):
            try:
                YAMLParser().parse_dict(self._model.to_dict())
            except Exception as exc:
                QMessageBox.warning(self, "Validation Failed", str(exc))
                return

        self._tb_run.setEnabled(False)
        self._tb_cancel.setEnabled(True)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._status_label.setText("Running simulation…")

        self._worker = SimulationWorker(
            project_data=self._model.to_dict(),
            run_config=run_cfg,
            parent=self,
        )
        self._worker.progress.connect(self._on_sim_progress)
        self._worker.finished.connect(lambda r: self._on_sim_finished(r, run_cfg))
        self._worker.error.connect(self._on_sim_error)
        self._worker.start()

    def _on_cancel(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self._status_label.setText("Cancelling…")

    def _on_sim_progress(self, done: int, total: int) -> None:
        pct = int(done * 100 / total) if total else 0
        self._progress_bar.setValue(pct)

    def _on_sim_finished(self, results: SimulationResults, run_cfg: dict[str, Any]) -> None:
        self._tb_run.setEnabled(True)
        self._tb_cancel.setEnabled(False)
        self._progress_bar.setVisible(False)
        self._last_results = results
        self._status_label.setText("Simulation complete.")

        # Export (P1-16)
        html_path = self._run_exports(results, run_cfg)
        self._last_html_report = html_path

        # Show results
        self._results_pane.show_results(results, html_path)
        # Navigate to Results section
        self._nav.setCurrentRow(len(_SECTIONS) - 1)

    def _on_sim_error(self, message: str) -> None:
        self._tb_run.setEnabled(True)
        self._tb_cancel.setEnabled(False)
        self._progress_bar.setVisible(False)
        self._results_pane.show_error(message)
        self._status_label.setText("Simulation failed.")
        self._nav.setCurrentRow(len(_SECTIONS) - 1)

    # ------------------------------------------------------------------
    # Export (P1-16)
    # ------------------------------------------------------------------

    def _run_exports(self, results: SimulationResults, run_cfg: dict[str, Any]) -> Path | None:
        formats: list[str] = run_cfg.get("formats", [])
        folder_str = run_cfg.get("output_folder")
        if folder_str:
            out_dir = Path(folder_str)
        elif self._current_file:
            out_dir = self._current_file.parent
        else:
            out_dir = Path.cwd()

        project_name = self._model.get_project_basics().get("name", "project")
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in project_name)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        base = out_dir / f"{safe_name}_{ts}"

        config = Config.get_default()
        html_path: Path | None = None

        if "json" in formats:
            JSONExporter.export(results, base.with_suffix(".json"), config=config)
        if "csv" in formats:
            CSVExporter.export(results, base.with_suffix(".csv"))
        if "html" in formats:
            html_path = base.with_suffix(".html")
            HTMLExporter.export(results, html_path, config=config)

        if formats:
            self._status_label.setText(f"Exported to {out_dir.name}/")

        return html_path

    # ------------------------------------------------------------------
    # Auto-save recovery (P1-18)
    # ------------------------------------------------------------------

    def _check_recovery(self) -> None:
        if not AutoSave.has_recovery():
            return
        reply = QMessageBox.question(
            self,
            "Recover Auto-save",
            "An auto-saved project was found from a previous session. Load it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                text = AutoSave.load_recovery()
                self._model.from_yaml(text)
                self._load_model_into_forms()
                self._mark_dirty(True)
                self._status_label.setText("Recovered auto-saved project.")
            except Exception as exc:
                QMessageBox.warning(self, "Recovery Error", str(exc))
        AutoSave.discard_recovery()

    # ------------------------------------------------------------------
    # About dialog (P1-19)
    # ------------------------------------------------------------------

    def _on_about(self) -> None:
        version = getattr(mcprojsim, "__version__", "unknown")
        QMessageBox.about(
            self,
            "About mcprojsim",
            f"<b>mcprojsim</b> {version}<br><br>"
            "Monte Carlo simulation for project management.<br><br>"
            '<a href="https://github.com/johan162/mcprojsim">https://github.com/johan162/mcprojsim</a>',
        )

    # ------------------------------------------------------------------
    # Close event
    # ------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._check_unsaved_changes():
            event.ignore()
            return
        self._autosave.stop()
        AutoSave.discard_recovery()
        self._save_geometry()
        super().closeEvent(event)
