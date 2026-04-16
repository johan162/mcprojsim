"""Auto-save and crash recovery helper (P1-18)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QTimer  # type: ignore[import-untyped]


_AUTOSAVE_PATH = Path.home() / ".mcprojsim" / "autosave.yaml"
_AUTOSAVE_INTERVAL_MS = 60_000  # 60 seconds


class AutoSave(QObject):
    """Periodically writes project YAML to a fixed recovery location."""

    def __init__(self, interval_ms: int = _AUTOSAVE_INTERVAL_MS, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._get_yaml_callback = None
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._do_save)

    def start(self, get_yaml_fn):  # type: ignore[no-untyped-def]
        """Start auto-save; *get_yaml_fn* is a zero-arg callable returning YAML str."""
        self._get_yaml_callback = get_yaml_fn
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def save_now(self) -> None:
        self._do_save()

    def _do_save(self) -> None:
        if self._get_yaml_callback is None:
            return
        try:
            yaml_text = self._get_yaml_callback()
            _AUTOSAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
            _AUTOSAVE_PATH.write_text(yaml_text, encoding="utf-8")
        except Exception:
            pass  # Silent — auto-save must never interrupt the user

    @staticmethod
    def recovery_file() -> Path:
        return _AUTOSAVE_PATH

    @staticmethod
    def has_recovery() -> bool:
        return _AUTOSAVE_PATH.exists()

    @staticmethod
    def load_recovery() -> str:
        return _AUTOSAVE_PATH.read_text(encoding="utf-8")

    @staticmethod
    def discard_recovery() -> None:
        try:
            _AUTOSAVE_PATH.unlink()
        except FileNotFoundError:
            pass
