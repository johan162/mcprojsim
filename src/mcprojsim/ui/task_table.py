"""Task table widget — QTableView + custom model (P1-07)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

# Column definitions: (header, dict key or None for computed)
_COLUMNS: list[tuple[str, str]] = [
    ("ID", "id"),
    ("Name", "name"),
    ("Expected (days)", "estimate"),
    ("Dependencies", "dependencies"),
]


class TaskTableModel(QAbstractTableModel):
    """Simple table model backed by a list of task dicts."""

    def __init__(self, tasks: list[dict[str, Any]] | None = None) -> None:
        super().__init__()
        self._tasks: list[dict[str, Any]] = tasks or []

    # ------------------------------------------------------------------
    # Required overrides
    # ------------------------------------------------------------------

    def rowCount(
        self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()
    ) -> int:
        if parent.isValid():
            return 0
        return len(self._tasks)

    def columnCount(
        self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()
    ) -> int:
        if parent.isValid():
            return 0
        return len(_COLUMNS)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid():
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            task = self._tasks[index.row()]
            key = _COLUMNS[index.column()][1]
            value = task.get(key, "")
            if key == "estimate" and isinstance(value, dict):
                # Show "low / expected / high unit" for readability
                exp = value.get("expected", value.get("most_likely", ""))
                unit = value.get("unit", "days")
                low = value.get("low", value.get("min", ""))
                high = value.get("high", value.get("max", ""))
                if low != "" and high != "":
                    return f"{low} / {exp} / {high} {unit}"
                return f"{exp} {unit}" if exp != "" else ""
            if isinstance(value, list):
                return ", ".join(str(v) for v in value)
            return str(value) if value is not None else ""
        if role == Qt.ItemDataRole.ToolTipRole:
            task = self._tasks[index.row()]
            return task.get("description", "")
        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return _COLUMNS[section][0]
        return None

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def set_tasks(self, tasks: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._tasks = list(tasks)
        self.endResetModel()

    def get_task(self, row: int) -> dict[str, Any]:
        return dict(self._tasks[row])

    def add_task(self, task: dict[str, Any]) -> None:
        row = len(self._tasks)
        self.beginInsertRows(QModelIndex(), row, row)
        self._tasks.append(task)
        self.endInsertRows()

    def update_task(self, row: int, task: dict[str, Any]) -> None:
        self._tasks[row] = task
        self.dataChanged.emit(
            self.index(row, 0),
            self.index(row, len(_COLUMNS) - 1),
        )

    def remove_task(self, row: int) -> None:
        self.beginRemoveRows(QModelIndex(), row, row)
        self._tasks.pop(row)
        self.endRemoveRows()

    def move_task(self, from_row: int, to_row: int) -> None:
        if from_row == to_row:
            return
        n = len(self._tasks)
        if not (0 <= from_row < n and 0 <= to_row < n):
            return
        task = self._tasks.pop(from_row)
        self._tasks.insert(to_row, task)
        self.beginResetModel()
        self.endResetModel()

    def all_tasks(self) -> list[dict[str, Any]]:
        return list(self._tasks)


class TaskTableWidget(QWidget):
    """Task table with Add / Edit / Delete / Move buttons."""

    taskEditRequested = Signal(int)  # row index
    tasksChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = TaskTableModel()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Toolbar row
        btn_bar = QHBoxLayout()
        btn_bar.setContentsMargins(0, 0, 0, 0)
        btn_bar.setSpacing(6)
        self._btn_add = QPushButton("+ Add Task")
        self._btn_add.setProperty("role", "primary")
        self._btn_edit = QPushButton("Edit")
        self._btn_delete = QPushButton("Delete")
        self._btn_delete.setProperty("role", "danger")
        self._btn_up = QPushButton("↑")
        self._btn_up.setToolTip("Move up")
        self._btn_down = QPushButton("↓")
        self._btn_down.setToolTip("Move down")
        for btn in (self._btn_add, self._btn_edit, self._btn_delete, self._btn_up, self._btn_down):
            btn.setFixedHeight(32)
        btn_bar.addWidget(self._btn_add)
        btn_bar.addWidget(self._btn_edit)
        btn_bar.addWidget(self._btn_delete)
        btn_bar.addStretch()
        btn_bar.addWidget(self._btn_up)
        btn_bar.addWidget(self._btn_down)
        layout.addLayout(btn_bar)

        # Table
        self._view = QTableView()
        self._view.setModel(self._model)
        self._view.setAlternatingRowColors(True)
        self._view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._view.verticalHeader().setDefaultSectionSize(36)
        self._view.horizontalHeader().setStretchLastSection(True)
        self._view.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self._view)

        # Wire buttons
        self._btn_add.clicked.connect(self._on_add)
        self._btn_edit.clicked.connect(self._on_edit_selected)
        self._btn_delete.clicked.connect(self._on_delete)
        self._btn_up.clicked.connect(self._on_move_up)
        self._btn_down.clicked.connect(self._on_move_down)

        self._update_button_states()
        self._view.selectionModel().selectionChanged.connect(self._update_button_states)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _selected_row(self) -> int:
        idxs = self._view.selectionModel().selectedRows()
        return idxs[0].row() if idxs else -1

    def _on_double_click(self, index: QModelIndex) -> None:
        self.taskEditRequested.emit(index.row())

    def _on_add(self) -> None:
        # Emit -1 to signal "new task"
        self.taskEditRequested.emit(-1)

    def _on_edit_selected(self) -> None:
        row = self._selected_row()
        if row >= 0:
            self.taskEditRequested.emit(row)

    def _on_delete(self) -> None:
        row = self._selected_row()
        if row >= 0:
            self._model.remove_task(row)
            self.tasksChanged.emit()
            self._update_button_states()

    def _on_move_up(self) -> None:
        row = self._selected_row()
        if row > 0:
            self._model.move_task(row, row - 1)
            self._view.selectRow(row - 1)
            self.tasksChanged.emit()

    def _on_move_down(self) -> None:
        row = self._selected_row()
        if row >= 0 and row < self._model.rowCount() - 1:
            self._model.move_task(row, row + 1)
            self._view.selectRow(row + 1)
            self.tasksChanged.emit()

    def _update_button_states(self) -> None:
        row = self._selected_row()
        has_sel = row >= 0
        self._btn_edit.setEnabled(has_sel)
        self._btn_delete.setEnabled(has_sel)
        self._btn_up.setEnabled(row > 0)
        self._btn_down.setEnabled(has_sel and row < self._model.rowCount() - 1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_tasks(self, tasks: list[dict[str, Any]]) -> None:
        self._model.set_tasks(tasks)
        self._update_button_states()

    def all_tasks(self) -> list[dict[str, Any]]:
        return self._model.all_tasks()

    def apply_task_edit(self, row: int, task: dict[str, Any]) -> None:
        """Called by the task editor when the user saves changes."""
        if row == -1:
            self._model.add_task(task)
        else:
            self._model.update_task(row, task)
        self.tasksChanged.emit()
        self._update_button_states()

    def get_task(self, row: int) -> dict[str, Any]:
        return self._model.get_task(row)
