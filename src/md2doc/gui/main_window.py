"""Main window: editor | live preview, settings dock, problems list, export."""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from PySide6.QtCore import QRunnable, QSettings, QObject, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QKeySequence, QPalette
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QApplication, QDockWidget, QFileDialog, QInputDialog, QLabel, QListWidget, QListWidgetItem,
                               QMainWindow, QMessageBox, QProgressBar, QSplitter, QToolBar)

from ..job import Job
from ..pipeline import prepare
from ..themes_store import save_user_theme
from .editor import MarkdownEditor, timestamp_name
from .export_runner import ExportRunner
from .preview import PreviewView
from .settings_panel import SettingsPanel

SNIPPETS = {
    "Table": "| Column A | Column B |\n|----------|:--------:|\n| one      | two      |\n",
    "Code block": "```python\nprint('hello')\n```\n",
    "Math (display)": "$$\n\\int_0^1 x^2\\,dx = \\frac{1}{3}\n$$\n",
    "Math (inline)": "$E = mc^2$",
    "Mermaid flowchart": "```mermaid\nflowchart LR\n    A[Start] --> B{Choice}\n    B -->|yes| C[Done]\n    B -->|no| D[Retry]\n```\n",
    "Mermaid sequence": "```mermaid\nsequenceDiagram\n    Alice->>Bob: Hello\n    Bob-->>Alice: Hi\n```\n",
    "Mermaid gantt": "```mermaid\ngantt\n    title Plan\n    dateFormat YYYY-MM-DD\n    section Work\n    Design :a1, 2026-01-01, 7d\n    Build  :after a1, 10d\n```\n",
    "PlantUML sequence": "```plantuml\n@startuml\nAlice -> Bob : Hello\nBob --> Alice : Hi\n@enduml\n```\n",
    "PlantUML class": "```plantuml\n@startuml\nclass Animal {\n  +name : string\n  +speak()\n}\nclass Dog\nAnimal <|-- Dog\n@enduml\n```\n",
    "Admonition": "> [!NOTE]\n> Something worth knowing.\n",
    "Task list": "- [x] done\n- [ ] to do\n",
    "Page break": "\n\\newpage\n\n",
    "Footnote": "Text with a footnote[^1].\n\n[^1]: The footnote text.\n",
}


class _Signals(QObject):
    done = Signal(int, object)
    failed = Signal(int, str)


class _PrepareTask(QRunnable):
    def __init__(self, gen: int, job: Job, work_dir: Path, signals: _Signals):
        super().__init__()
        self.gen, self.job, self.work_dir, self.signals = gen, job, work_dir, signals

    def run(self) -> None:
        try:
            prep = prepare(self.job, "preview", self.work_dir)
            self.signals.done.emit(self.gen, prep)
        except Exception as e:  # noqa: BLE001
            self.signals.failed.emit(self.gen, f"{type(e).__name__}: {e}")


class MainWindow(QMainWindow):
    def __init__(self, open_path: Path | None = None):
        super().__init__()
        self.path: Path | None = None
        self._dirty = False
        self._gen = 0
        self._last_theme = None
        self._dark_app = False
        self._work = Path(tempfile.mkdtemp(prefix="md2doc_preview_"))
        self.qs = QSettings("md2doc", "md2doc")
        self.signals = _Signals()
        self.signals.done.connect(self._on_prepared)
        self.signals.failed.connect(self._on_prepare_failed)

        self.editor = MarkdownEditor()
        self.preview = PreviewView()
        self.settings = SettingsPanel()
        self.problems = QListWidget()
        self.runner = ExportRunner(self)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(self.editor)
        split.addWidget(self.preview)
        split.setSizes([520, 700])
        self.setCentralWidget(split)
        self.split = split

        self.dock_settings = QDockWidget("Look && layout", self)
        self.dock_settings.setObjectName("dock_settings")
        self.dock_settings.setWidget(self.settings)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_settings)
        self.dock_problems = QDockWidget("Problems", self)
        self.dock_problems.setObjectName("dock_problems")
        self.dock_problems.setWidget(self.problems)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dock_problems)

        self.status_label = QLabel("")
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setMaximumWidth(140)
        self.progress.hide()
        self.statusBar().addWidget(self.status_label, 1)
        self.statusBar().addPermanentWidget(self.progress)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self.render_now)
        self._sync = QTimer(self)
        self._sync.setSingleShot(True)
        self._sync.setInterval(120)
        self._sync.timeout.connect(lambda: self.preview.scroll_to_line(self.editor.current_line()))
        self.sync_scroll = True

        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.cursorPositionChanged.connect(lambda: self.sync_scroll and self._sync.start())
        self.editor.image_pasted.connect(self._paste_image)
        self.editor.files_dropped.connect(self._files_dropped)
        self.settings.changed.connect(self.schedule_render)
        self.settings.font_imported.connect(self.settings.use_font_everywhere)
        self.preview.rendered.connect(self._on_page_report)
        self.problems.itemActivated.connect(lambda it: it.data(Qt.ItemDataRole.UserRole) and self.editor.goto_line(it.data(Qt.ItemDataRole.UserRole)))
        self.runner.event.connect(self._on_export_event)
        self.runner.finished.connect(self._on_export_finished)

        self._build_actions()
        self._restore()
        self.resizeDocks([self.dock_problems], [120], Qt.Orientation.Vertical)
        if open_path and open_path.is_file():
            self.open_file(open_path)
        elif not self.editor.toPlainText():
            self.editor.setPlainText(WELCOME)
            self._dirty = False
        self._update_title()
        self.render_now()

    # ------------------------------------------------------------------------------------------
    # actions / menus
    def _act(self, text: str, slot, shortcut: str | QKeySequence.StandardKey | None = None, checkable=False) -> QAction:
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.setCheckable(checkable)
        a.triggered.connect(slot)
        return a

    def _build_actions(self) -> None:
        mb = self.menuBar()
        f = mb.addMenu("&File")
        f.addAction(self._act("&New", self.new_file, QKeySequence.StandardKey.New))
        f.addAction(self._act("&Open...", self.open_dialog, QKeySequence.StandardKey.Open))
        self.recent_menu = f.addMenu("Open &Recent")
        f.addAction(self._act("&Save", self.save, QKeySequence.StandardKey.Save))
        f.addAction(self._act("Save &As...", self.save_as, "Ctrl+Shift+S"))
        f.addSeparator()
        self.act_pdf = self._act("Export &PDF...", lambda: self.export("pdf"), "Ctrl+E")
        self.act_png = self._act("Export P&NG...", lambda: self.export("png"), "Ctrl+Shift+E")
        self.act_both = self._act("Export PDF && PNG...", lambda: self.export("both"))
        self.act_cancel = self._act("Cancel export", self.runner.cancel)
        self.act_cancel.setEnabled(False)
        for a in (self.act_pdf, self.act_png, self.act_both, self.act_cancel):
            f.addAction(a)
        f.addSeparator()
        f.addAction(self._act("E&xit", self.close, "Ctrl+Q"))

        e = mb.addMenu("&Edit")
        for text, sl, key in (("Undo", self.editor.undo, QKeySequence.StandardKey.Undo), ("Redo", self.editor.redo, QKeySequence.StandardKey.Redo),
                              ("Cut", self.editor.cut, QKeySequence.StandardKey.Cut), ("Copy", self.editor.copy, QKeySequence.StandardKey.Copy),
                              ("Paste", self.editor.paste, QKeySequence.StandardKey.Paste)):
            e.addAction(self._act(text, sl, key))

        ins = mb.addMenu("&Insert")
        ins.addAction(self._act("Image...", self.insert_image, "Ctrl+Shift+I"))
        ins.addSeparator()
        for name, text in SNIPPETS.items():
            ins.addAction(self._act(name, lambda _=False, t=text: self.editor.insert_snippet(t)))

        v = mb.addMenu("&View")
        v.addAction(self.dock_settings.toggleViewAction())
        v.addAction(self.dock_problems.toggleViewAction())
        a = self._act("Scroll preview with cursor", self._toggle_sync, checkable=True)
        a.setChecked(True)
        v.addAction(a)
        a = self._act("Dark application theme", self._toggle_dark, checkable=True)
        v.addAction(a)
        v.addAction(self._act("Refresh preview", lambda: self.render_now(), "F5"))

        t = mb.addMenu("&Theme")
        t.addAction(self._act("Save current look as my theme...", self.save_theme))
        t.addAction(self._act("Open my themes folder", self.open_themes_folder))

        h = mb.addMenu("&Help")
        h.addAction(self._act("About", self._about))

        tb = QToolBar("Main")
        tb.setObjectName("toolbar_main")
        tb.setMovable(False)
        for a in (self._act("Open", self.open_dialog), self._act("Save", self.save), None, self.act_pdf, self.act_png, None,
                  self._act("Insert image", self.insert_image)):
            tb.addSeparator() if a is None else tb.addAction(a)
        self.addToolBar(tb)

    def _toggle_sync(self, on: bool) -> None:
        self.sync_scroll = on

    def _toggle_dark(self, on: bool) -> None:
        self._dark_app = on
        app = QApplication.instance()
        app.setStyle("Fusion")
        if on:
            p = QPalette()
            p.setColor(QPalette.ColorRole.Window, QColor("#1f2328"))
            p.setColor(QPalette.ColorRole.WindowText, QColor("#e6edf3"))
            p.setColor(QPalette.ColorRole.Base, QColor("#0d1117"))
            p.setColor(QPalette.ColorRole.AlternateBase, QColor("#161b22"))
            p.setColor(QPalette.ColorRole.Text, QColor("#e6edf3"))
            p.setColor(QPalette.ColorRole.PlaceholderText, QColor("#7d8590"))
            p.setColor(QPalette.ColorRole.Button, QColor("#2d333b"))
            p.setColor(QPalette.ColorRole.ButtonText, QColor("#e6edf3"))
            p.setColor(QPalette.ColorRole.Highlight, QColor("#1f6feb"))
            p.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
            p.setColor(QPalette.ColorRole.ToolTipBase, QColor("#2d333b"))
            p.setColor(QPalette.ColorRole.ToolTipText, QColor("#e6edf3"))
            app.setPalette(p)
        else:
            app.setPalette(app.style().standardPalette())
        self.editor.set_dark(on)

    # ------------------------------------------------------------------------------------------
    # document state
    def base_dir(self) -> Path:
        if self.path:
            return self.path.parent
        d = Path.home() / "Documents" / "md2doc"
        return d

    def _update_title(self) -> None:
        name = self.path.name if self.path else "Untitled"
        self.setWindowTitle(f"{'*' if self._dirty else ''}{name} - md2doc")

    def _on_text_changed(self) -> None:
        self._dirty = True
        self._update_title()
        self.schedule_render()

    def _maybe_save(self) -> bool:
        if not self._dirty:
            return True
        r = QMessageBox.question(self, "md2doc", "Save changes to this document?",
                                 QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        if r == QMessageBox.StandardButton.Save:
            return self.save()
        return r == QMessageBox.StandardButton.Discard

    def new_file(self) -> None:
        if not self._maybe_save():
            return
        self.path = None
        self.editor.setPlainText("")
        self._dirty = False
        self._update_title()

    def open_dialog(self) -> None:
        f, _ = QFileDialog.getOpenFileName(self, "Open Markdown", str(self.base_dir()), "Markdown (*.md *.markdown *.txt);;All files (*)")
        if f:
            self.open_file(Path(f))

    def open_file(self, p: Path) -> None:
        if not self._maybe_save():
            return
        try:
            text = p.read_text(encoding="utf-8-sig")
        except OSError as e:
            QMessageBox.warning(self, "Open", f"Cannot open {p}:\n{e}")
            return
        self.path = p.resolve()
        self.editor.blockSignals(True)
        self.editor.setPlainText(text)
        self.editor.blockSignals(False)
        self._dirty = False
        self._update_title()
        self._remember(self.path)
        self.preview_reset_scroll = True
        self.render_now(keep_scroll=False)

    def save(self) -> bool:
        if not self.path:
            return self.save_as()
        return self._write(self.path)

    def save_as(self) -> bool:
        f, _ = QFileDialog.getSaveFileName(self, "Save Markdown", str(self.base_dir() / "document.md"), "Markdown (*.md)")
        if not f:
            return False
        self.path = Path(f)
        return self._write(self.path)

    def _write(self, p: Path) -> bool:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(self.editor.toPlainText(), encoding="utf-8")
        except OSError as e:
            QMessageBox.warning(self, "Save", f"Cannot save {p}:\n{e}")
            return False
        self._dirty = False
        self._update_title()
        self._remember(p)
        self.status("Saved " + str(p))
        return True

    def _remember(self, p: Path) -> None:
        recent = [str(p)] + [r for r in self.qs.value("recent", [], type=list) if r != str(p)]
        self.qs.setValue("recent", recent[:10])
        self._fill_recent()

    def _fill_recent(self) -> None:
        self.recent_menu.clear()
        for r in self.qs.value("recent", [], type=list):
            self.recent_menu.addAction(self._act(r, lambda _=False, rr=r: self.open_file(Path(rr))))

    # ------------------------------------------------------------------------------------------
    # images
    def _rel(self, p: Path) -> str:
        try:
            s = os.path.relpath(p, self.base_dir()).replace("\\", "/")
            if s.startswith("..") and not self.path:
                s = str(p).replace("\\", "/")
        except ValueError:
            s = str(p).replace("\\", "/")
        return f"<{s}>" if " " in s else s

    def insert_image(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Insert image", str(self.base_dir()), "Images (*.png *.jpg *.jpeg *.gif *.webp *.bmp *.svg)")
        for f in files:
            p = Path(f)
            self.editor.insert_snippet(f"![{p.stem}]({self._rel(p)})\n")

    def _paste_image(self, data: bytes) -> None:
        d = self.base_dir() / "assets"
        try:
            d.mkdir(parents=True, exist_ok=True)
            p = d / timestamp_name()
            p.write_bytes(data)
        except OSError as e:
            QMessageBox.warning(self, "Paste image", f"Cannot save the pasted image:\n{e}")
            return
        self.editor.insert_snippet(f"![image]({self._rel(p)})\n")
        if not self.path:
            self.status(f"Pasted image saved to {p}. Save the document to keep relative links.")

    def _files_dropped(self, files: list) -> None:
        for p in files:
            ext = Path(p).suffix.lower()
            if ext in (".md", ".markdown", ".txt"):
                self.open_file(Path(p))
                return
            if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"):
                self.editor.insert_snippet(f"![{Path(p).stem}]({self._rel(Path(p))})\n")

    # ------------------------------------------------------------------------------------------
    # rendering
    def current_job(self) -> Job:
        return Job(markdown=self.editor.toPlainText(), input=self.path, base_dir=self.base_dir(), **self.settings.job_fields())

    def schedule_render(self) -> None:
        self._debounce.start(350 if self.editor.document().characterCount() < 50_000 else 800)

    def render_now(self, keep_scroll: bool = True) -> None:
        self._debounce.stop()
        self._gen += 1
        self._keep_scroll = keep_scroll
        try:
            job = self.current_job()
        except Exception as e:  # noqa: BLE001
            self.status(f"Settings error: {e}")
            return
        self.status("Rendering...")
        QThreadPool.globalInstance().start(_PrepareTask(self._gen, job, self._work, self.signals))

    def _on_prepared(self, gen: int, prep) -> None:
        if gen != self._gen:
            return
        self._last_theme = prep.theme
        from .. import paths as _paths

        self.preview.set_allowed_roots([prep.work_dir, _paths.VENDOR_DIR, _paths.WEB_DIR] + list(prep.font_files))
        self.settings.set_palette(prep.theme)
        self._python_warnings = prep.warnings
        self.problems.clear()
        for w in prep.warnings:
            self._add_problem(w)
        self.preview.show_html(prep.html_path, keep_scroll=getattr(self, "_keep_scroll", True))

    def _on_prepare_failed(self, gen: int, msg: str) -> None:
        if gen != self._gen:
            return
        self.problems.clear()
        self._add_problem({"kind": "error", "message": msg, "line": None})
        self.status(msg)

    def _on_page_report(self, rep: dict) -> None:
        for w in rep.get("errors", []) + rep.get("warnings", []):
            self._add_problem(w)
        n_err = len(rep.get("errors", []))
        n_warn = self.problems.count()
        ms = rep.get("ms", 0)
        self.status(f"Rendered in {ms / 1000:.1f} s" + (f" - {n_err} diagram/math error(s)" if n_err else "")
                    + (f" - {n_warn} note(s)" if n_warn and not n_err else ""))

    def _add_problem(self, w: dict) -> None:
        line = w.get("line")
        txt = f"[{w.get('kind', '')}] " + (f"line {line}: " if line else "") + str(w.get("message", "")).replace("\n", " ")
        it = QListWidgetItem(txt)
        it.setToolTip(str(w.get("message", "")))
        if line:
            it.setData(Qt.ItemDataRole.UserRole, int(line))
        self.problems.addItem(it)

    def status(self, msg: str) -> None:
        self.status_label.setText(msg)

    # ------------------------------------------------------------------------------------------
    # export
    def export(self, fmt: str) -> None:
        if self.runner.running:
            return
        stem = self.path.stem if self.path else "document"
        folder = self.base_dir()
        ext = "png" if fmt == "png" else "pdf"
        f, _ = QFileDialog.getSaveFileName(self, "Export " + ("PDF and PNG" if fmt == "both" else ext.upper()), str(folder / f"{stem}.{ext}"),
                                           "PNG image (*.png)" if ext == "png" else "PDF document (*.pdf)")
        if not f:
            return
        job = self.current_job().model_copy(update={"output": Path(f), "format": "png" if fmt == "png" else "pdf"})
        self.problems.clear()
        self.progress.show()
        self.act_cancel.setEnabled(True)
        for a in (self.act_pdf, self.act_png, self.act_both):
            a.setEnabled(False)
        self.status("Exporting...")
        self.runner.start(job, both=(fmt == "both"))

    def _on_export_event(self, ev: dict) -> None:
        k = ev.get("event")
        if k == "stage":
            self.status(ev.get("message", ""))
        elif k == "warning":
            self._add_problem(ev)
        elif k == "log" and ev.get("message"):
            self.status(ev["message"].splitlines()[-1][:160])

    def _on_export_finished(self, ok: bool, outputs: list, error: str) -> None:
        self.progress.hide()
        self.act_cancel.setEnabled(False)
        for a in (self.act_pdf, self.act_png, self.act_both):
            a.setEnabled(True)
        if not ok:
            self.status(error or "Export failed")
            if error != "Export cancelled.":
                QMessageBox.warning(self, "Export failed", error or "The export failed.")
            return
        self.status("Exported " + ", ".join(outputs))
        box = QMessageBox(self)
        box.setWindowTitle("Export finished")
        box.setText("Exported:\n" + "\n".join(outputs))
        open_btn = box.addButton("Open", QMessageBox.ButtonRole.AcceptRole)
        folder_btn = box.addButton("Show in folder", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Close)
        box.exec()
        if box.clickedButton() == open_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(outputs[0]))
        elif box.clickedButton() == folder_btn:
            import subprocess

            subprocess.Popen(["explorer", "/select,", str(Path(outputs[0]))])

    # ------------------------------------------------------------------------------------------
    # themes
    def save_theme(self) -> None:
        if self._last_theme is None:
            return
        name, ok = QInputDialog.getText(self, "Save theme", "Name for your theme:")
        if not ok or not name.strip():
            return
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "my-theme"
        d = json.loads(self._last_theme.model_dump_json())
        d["id"], d["name"] = slug, name.strip()
        try:
            save_user_theme(d)
        except OSError as e:
            QMessageBox.warning(self, "Save theme", str(e))
            return
        self.settings.reload_themes(slug)
        self.settings.use_tone.setChecked(False)
        self.settings.use_accent.setChecked(False)
        self.status(f"Saved theme '{name.strip()}'")

    def open_themes_folder(self) -> None:
        from ..themes_store import user_theme_dir

        d = user_theme_dir()
        d.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(d)))

    def _about(self) -> None:
        QMessageBox.about(self, "md2doc", "md2doc - Markdown to PDF and PNG\n\nLaTeX math, Mermaid and PlantUML diagrams, images,\n"
                          "themes, colour tone and fonts. Renders with Microsoft Edge (Chromium).\n\nhttps://github.com/Yotshiba/markdown_to_pdf_png")

    # ------------------------------------------------------------------------------------------
    # persistence / lifecycle
    def _restore(self) -> None:
        g = self.qs.value("geometry")
        if g:
            self.restoreGeometry(g)
        else:
            self.resize(1400, 860)
        s = self.qs.value("windowState")
        if s:
            self.restoreState(s)
        sp = self.qs.value("splitter")
        if sp:
            self.split.restoreState(sp)
        try:
            self.settings.set_state(json.loads(self.qs.value("settings", "{}")))
        except ValueError:
            pass
        if self.qs.value("dark_app", False, type=bool):
            self._toggle_dark(True)
        self._fill_recent()

    def closeEvent(self, e) -> None:
        if not self._maybe_save():
            e.ignore()
            return
        if self.runner.running:
            self.runner.cancel()
        self.qs.setValue("geometry", self.saveGeometry())
        self.qs.setValue("windowState", self.saveState())
        self.qs.setValue("splitter", self.split.saveState())
        self.qs.setValue("settings", json.dumps(self.settings.state()))
        self.qs.setValue("dark_app", self._dark_app)
        shutil.rmtree(self._work, ignore_errors=True)
        e.accept()


WELCOME = """---
title: Welcome to md2doc
toc: 2
---

# Welcome to md2doc

Write Markdown on the left, see the result on the right, export to **PDF** or **PNG** from the *File* menu.

## What works

- Images: drop or paste them into the editor (*Insert > Image*)
- LaTeX math: $E = mc^2$ and display equations

$$
\\int_{-\\infty}^{\\infty} e^{-x^2}\\,dx = \\sqrt{\\pi}
$$

- Diagrams: Mermaid and PlantUML (see the *Insert* menu)
- Themes, colour tone and fonts: use the **Look & layout** panel on the right

```mermaid
flowchart LR
    A[Write] --> B[Preview] --> C[Export]
```
"""
