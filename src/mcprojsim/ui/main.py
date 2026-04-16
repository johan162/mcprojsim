"""mcprojsim desktop UI entry point."""

from __future__ import annotations

import sys


def main() -> None:
    """Launch the mcprojsim desktop GUI."""
    try:
        from PySide6.QtWidgets import QApplication  # type: ignore[import-untyped]
    except ImportError:
        print(
            "PySide6 is required to run the mcprojsim desktop UI.\n"
            "Install it with:  poetry install --with ui",
            file=sys.stderr,
        )
        sys.exit(1)

    from mcprojsim.ui.main_window import MainWindow
    from mcprojsim.ui.theme import APP_STYLESHEET

    app = QApplication(sys.argv)
    app.setApplicationName("mcprojsim")
    app.setOrganizationName("mcprojsim")
    app.setStyleSheet(APP_STYLESHEET)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
