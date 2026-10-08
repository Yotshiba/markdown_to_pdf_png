"""GUI entry point: md2doc-gui [file.md]   (hidden: --selftest result.json, used to verify packaged builds)"""
from __future__ import annotations

import ctypes
import json
import os
import sys
import tempfile
from pathlib import Path


def _selftest(win, result_path: Path) -> None:
    """Wait for the preview to render, export a PDF through the real runner, write a JSON verdict, quit."""
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    verdict: dict = {"preview_rendered": False, "export_ok": False, "outputs": [], "error": ""}
    out = Path(tempfile.mkdtemp(prefix="md2doc_selftest_")) / "selftest.pdf"

    def finish() -> None:
        result_path.write_text(json.dumps(verdict), encoding="utf-8")
        QApplication.quit()

    def on_export(ok: bool, outputs: list, error: str) -> None:
        verdict.update(export_ok=ok and Path(outputs[0]).is_file() if outputs else False, outputs=outputs, error=error)
        finish()

    def on_render(report: dict) -> None:
        if verdict["preview_rendered"]:
            return
        verdict["preview_rendered"] = True
        verdict["preview_errors"] = len(report.get("errors", []))
        win.runner.finished.connect(on_export)
        win.runner.start(win.current_job().model_copy(update={"output": out, "format": "pdf"}))

    win.preview.rendered.connect(on_render)
    QTimer.singleShot(90_000, lambda: (verdict.update(error=verdict["error"] or "timeout"), finish()))


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if sys.stdout is None:  # windowed (no console) build: keep print() harmless
        sys.stdout = sys.stderr = open(os.devnull, "w")
    if os.name == "nt":
        try:  # own taskbar identity instead of grouping under python.exe
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Yotshiba.md2doc")
        except Exception:  # noqa: BLE001
            pass
    selftest = None
    if "--selftest" in argv:
        i = argv.index("--selftest")
        selftest = Path(argv[i + 1])
        del argv[i : i + 2]
    # QtWebEngine must be imported before the QApplication exists
    from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
    from PySide6.QtWidgets import QApplication

    app = QApplication(argv)
    app.setApplicationName("md2doc")
    app.setOrganizationName("md2doc")
    from .main_window import MainWindow

    path = Path(argv[1]) if len(argv) > 1 else None
    if selftest:  # never touch the user's saved settings (registry): use a throwaway INI file instead
        os.environ["MD2DOC_SETTINGS_INI"] = str(Path(tempfile.mkdtemp(prefix="md2doc_qs_")) / "settings.ini")
    win = MainWindow(path)
    win.show()
    if selftest:
        _selftest(win, selftest)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
