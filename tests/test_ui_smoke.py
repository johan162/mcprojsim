"""Smoke tests for the mcprojsim desktop UI (P1-20).

These tests require pytest-qt and PySide6.  Skip automatically if either is
missing so CI runs that don't install the ui group continue to pass.
"""

from __future__ import annotations

import pytest

# Skip the entire module if PySide6 or pytest-qt are not available
PySide6 = pytest.importorskip("PySide6", reason="PySide6 not installed")
pytest.importorskip("pytestqt", reason="pytest-qt not installed")


from mcprojsim.ui.basics_form import ProjectBasicsWidget  # noqa: E402
from mcprojsim.ui.main_window import MainWindow  # noqa: E402
from mcprojsim.ui.project_model import UIProjectModel  # noqa: E402
from mcprojsim.ui.run_dialog import RunSimulationDialog  # noqa: E402
from mcprojsim.ui.task_editor import TaskEditorDialog  # noqa: E402
from mcprojsim.ui.task_table import TaskTableWidget  # noqa: E402
from mcprojsim.ui.theme import APP_STYLESHEET  # noqa: E402


# ---------------------------------------------------------------------------
# UIProjectModel
# ---------------------------------------------------------------------------


class TestUIProjectModel:
    def test_defaults_present(self) -> None:
        model = UIProjectModel()
        data = model.to_dict()
        assert "project" in data
        assert "tasks" in data
        assert data["project"]["hours_per_day"] == 8.0

    def test_round_trip_yaml(self) -> None:
        model = UIProjectModel()
        model.set_project_basics({"name": "Test Project", "description": "desc"})
        yaml_text = model.to_yaml()
        model2 = UIProjectModel()
        model2.from_yaml(yaml_text)
        assert model2.get_project_basics()["name"] == "Test Project"

    def test_add_delete_task(self) -> None:
        model = UIProjectModel()
        task = {"id": "t1", "name": "Task One", "estimate": 5.0}
        model.add_task(task)
        assert len(model.get_tasks()) == 1
        model.delete_task(0)
        assert len(model.get_tasks()) == 0

    def test_changed_signal(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        model = UIProjectModel()
        with qtbot.waitSignal(model.changed, timeout=1000):
            model.add_task({"id": "t1", "name": "T1", "estimate": 3.0})

    def test_move_task(self) -> None:
        model = UIProjectModel()
        model.add_task({"id": "a", "name": "A"})
        model.add_task({"id": "b", "name": "B"})
        model.move_task(0, 1)
        tasks = model.get_tasks()
        assert tasks[0]["id"] == "b"
        assert tasks[1]["id"] == "a"


# ---------------------------------------------------------------------------
# ProjectBasicsWidget
# ---------------------------------------------------------------------------


class TestProjectBasicsWidget:
    def test_create(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        w = ProjectBasicsWidget()
        qtbot.addWidget(w)
        assert w is not None

    def test_to_dict_from_dict_round_trip(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        w = ProjectBasicsWidget()
        qtbot.addWidget(w)
        data = {
            "name": "Round-trip Test",
            "description": "A test project.",
            "start_date": "2025-01-01",
            "hours_per_day": 7.5,
            "days_per_week": 4,
        }
        w.from_dict(data)
        out = w.to_dict()
        assert out["name"] == "Round-trip Test"
        assert out["hours_per_day"] == 7.5
        assert out["days_per_week"] == 4

    def test_is_valid_empty_name(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        w = ProjectBasicsWidget()
        qtbot.addWidget(w)
        w.from_dict({"name": ""})
        assert not w.is_valid()

    def test_is_valid_with_name(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        w = ProjectBasicsWidget()
        qtbot.addWidget(w)
        w.from_dict({"name": "My Project"})
        assert w.is_valid()


# ---------------------------------------------------------------------------
# TaskTableWidget
# ---------------------------------------------------------------------------


class TestTaskTableWidget:
    def test_create(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        w = TaskTableWidget()
        qtbot.addWidget(w)
        assert w is not None

    def test_set_and_get_tasks(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        w = TaskTableWidget()
        qtbot.addWidget(w)
        tasks = [
            {"id": "t1", "name": "Task 1", "estimate": 3.0},
            {"id": "t2", "name": "Task 2", "estimate": 5.0},
        ]
        w.set_tasks(tasks)
        assert len(w.all_tasks()) == 2

    def test_apply_new_task(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        w = TaskTableWidget()
        qtbot.addWidget(w)
        w.apply_task_edit(-1, {"id": "t3", "name": "New Task", "estimate": 2.0})
        assert len(w.all_tasks()) == 1


# ---------------------------------------------------------------------------
# TaskEditorDialog
# ---------------------------------------------------------------------------


class TestTaskEditorDialog:
    def test_create_new(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        d = TaskEditorDialog()
        qtbot.addWidget(d)
        assert d.windowTitle() == "New Task"

    def test_create_edit(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        task = {"id": "t1", "name": "Existing", "estimate": 4.0}
        d = TaskEditorDialog(task=task)
        qtbot.addWidget(d)
        assert d.windowTitle() == "Edit Task"


# ---------------------------------------------------------------------------
# RunSimulationDialog
# ---------------------------------------------------------------------------


class TestRunSimulationDialog:
    def test_create(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        d = RunSimulationDialog()
        qtbot.addWidget(d)
        assert d is not None

    def test_get_config_defaults(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        d = RunSimulationDialog()
        qtbot.addWidget(d)
        cfg = d.get_config()
        assert cfg["iterations"] >= 100
        assert isinstance(cfg["formats"], list)


# ---------------------------------------------------------------------------
# MainWindow
# ---------------------------------------------------------------------------


class TestMainWindow:
    def test_creates_without_crash(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        w = MainWindow()
        qtbot.addWidget(w)
        assert w.windowTitle().startswith("Untitled") or "mcprojsim" in w.windowTitle()

    def test_theme_applied(self, qapp) -> None:  # type: ignore[no-untyped-def]
        assert APP_STYLESHEET  # non-empty string
        # Apply and verify no crash
        qapp.setStyleSheet(APP_STYLESHEET)

    def test_nav_switches_pages(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        w = MainWindow()
        qtbot.addWidget(w)
        w._nav.setCurrentRow(1)  # Tasks section
        assert w._stack.currentIndex() == 1

    def test_new_resets_model(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        w = MainWindow()
        qtbot.addWidget(w)
        w._model.set_project_basics({"name": "Old Name"})
        w._on_new()
        assert w._model.get_project_basics().get("name") == "My Project"

    def test_yaml_preview_updates(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        w = MainWindow()
        qtbot.addWidget(w)
        w._model.set_project_basics({"name": "YAML Test Project"})
        yaml_text = w._yaml_editor.toPlainText()
        assert "YAML Test Project" in yaml_text
