"""GUI entry point: md2doc-gui [file.md]"""
from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if os.name == "nt":
        try:  # own taskbar identity instead of grouping under python.exe
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Yotshiba.md2doc")
        except Exception:  # noqa: BLE001
            pass
    # QtWebEngine must be imported before the QApplication exists
    from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
    from PySide6.QtWidgets import QApplication

    app = QApplication(argv)
    app.setApplicationName("md2doc")
    app.setOrganizationName("md2doc")
    from .main_window import MainWindow

    path = Path(argv[1]) if len(argv) > 1 else None
    win = MainWindow(path)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
