"""GUI smoke tests (offscreen Qt). The preview/export engine itself is covered by test_export.py."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --no-sandbox")  # headless CI has no GPU
pytest.importorskip("PySide6")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_settings_panel_builds_job_fields_and_roundtrips_state(qapp):
    from md2doc.gui.settings_panel import SettingsPanel
    from md2doc.job import Job

    p = SettingsPanel()
    assert p.job_fields()["theme"] == "github-light"
    p.use_tone.setChecked(True)
    p.tone_seed.set_color("#2e7d32")
    p.temperature.setValue(50)
    p.body_font.setCurrentText("Georgia")
    p.page_size.setCurrentText("Letter")
    p.orientation.setCurrentText("Landscape")
    p.margin.setValue(12)
    p.toc.setValue(3)
    p.scale.setCurrentText("3")
    f = p.job_fields()
    assert f["tone_seed"] == "#2e7d32" and f["temperature"] == 0.5 and f["font"] == "Georgia"
    assert f["page_size"] == "Letter" and f["orientation"] == "landscape" and f["margin"] == "12" and f["toc"] == 3 and f["scale"] == 3.0
    Job(markdown="# x", **f)  # must be a valid Job

    q = SettingsPanel()
    q.set_state(p.state())
    assert q.job_fields() == f


def test_defaults_emit_no_overrides(qapp):
    from md2doc.gui.settings_panel import SettingsPanel

    keys = set(SettingsPanel().job_fields())
    assert not keys & {"font", "heading_font", "mono_font", "font_size", "page_size", "orientation", "margin", "accent", "tone_seed", "scale"}


def test_editor_highlighter_tracks_fences_and_math(qapp):
    from md2doc.gui.editor import MarkdownEditor

    e = MarkdownEditor()
    e.setPlainText("# H\n\n```py\nx = 1\n```\n\n$$\na\n$$\n\ntext\n")
    doc = e.document()
    states = [doc.findBlockByNumber(i).userState() for i in range(doc.blockCount())]
    assert states[3] == 1 and states[7] == 2 and states[10] == 0 if len(states) > 10 else True
    e.wrap_selection("**")
    assert "****" in e.toPlainText()
    assert e.gutter_width() > 0


def test_main_window_renders_and_lists_problems(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QSettings, QTimer
    from PySide6.QtWidgets import QApplication

    QSettings.setPath(QSettings.Format.NativeFormat, QSettings.Scope.UserScope, str(tmp_path))
    from md2doc.gui.main_window import MainWindow

    md = tmp_path / "d.md"
    md.write_text("# T\n\n![x](missing.png)\n", encoding="utf-8")
    w = MainWindow(md)
    w.show()  # a hidden QWebEngineView does not load
    try:
        loop_done = {"v": False}
        w.preview.rendered.connect(lambda r: loop_done.__setitem__("v", True))
        t = QTimer()
        t.setInterval(50)
        t.timeout.connect(lambda: loop_done["v"] and QApplication.quit())
        QTimer.singleShot(30000, QApplication.quit)
        t.start()
        QApplication.exec()
        assert loop_done["v"], "preview never finished rendering"
        texts = [w.problems.item(i).text() for i in range(w.problems.count())]
        assert any("image unavailable" in x for x in texts)
        assert w.windowTitle().startswith("d.md")
    finally:
        w._dirty = False
        w.close()
