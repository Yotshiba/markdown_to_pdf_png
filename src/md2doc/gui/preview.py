"""Live preview: QtWebEngine loading the very same HTML file the exporter prints."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings, QWebEngineUrlRequestInterceptor
from PySide6.QtWebEngineWidgets import QWebEngineView


class _Page(QWebEnginePage):
    """Keeps navigation inside the preview; external links open in the system browser."""

    def acceptNavigationRequest(self, url: QUrl, nav_type, is_main_frame: bool) -> bool:
        if nav_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
            if url.scheme() == "file" and url.fragment() and url.path() == self.url().path():
                return True  # in-document anchor (TOC, footnotes)
            if url.scheme() in ("http", "https", "mailto"):
                QDesktopServices.openUrl(url)
            return False
        return True


class _Interceptor(QWebEngineUrlRequestInterceptor):
    """Same policy as the exporter's route gate: only local files from the work dir / renderers, no network."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.roots: list[Path] = []

    def interceptRequest(self, info) -> None:
        url = info.requestUrl()
        scheme = url.scheme()
        if scheme in ("data", "blob", "about", "qrc"):
            return
        if scheme == "file":
            if url.host() in ("", "localhost"):
                try:
                    p = Path(url.toLocalFile()).resolve()
                    if any(p == r or p.is_relative_to(r) for r in self.roots):
                        return
                except OSError:
                    pass
        info.block(True)


class PreviewView(QWebEngineView):
    rendered = Signal(dict)  # page report once render.js finished

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPage(_Page(self))
        s = self.page().settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, False)
        self._interceptor = _Interceptor(self)
        self.page().profile().setUrlRequestInterceptor(self._interceptor)
        self._scroll_y = 0.0
        self._generation = 0
        self._poll = QTimer(self)
        self._poll.setInterval(120)
        self._poll.timeout.connect(self._check_done)
        self._ticks = 0
        self._restore = True
        self.loadFinished.connect(self._on_loaded)

    def set_allowed_roots(self, roots: list[Path]) -> None:
        self._interceptor.roots = [Path(r).resolve() for r in roots]

    def show_html(self, html_path: Path, *, keep_scroll: bool = True) -> None:
        self._restore = keep_scroll
        self._generation += 1
        self._poll.stop()
        pos = self.page().scrollPosition()
        self._scroll_y = pos.y() if keep_scroll else 0.0
        url = QUrl.fromLocalFile(str(html_path))
        url.setQuery(f"v={self._generation}")
        self.load(url)

    def _on_loaded(self, ok: bool) -> None:
        if not ok:
            return
        self._ticks = 0
        self._poll.start()

    def _check_done(self) -> None:
        gen = self._generation
        self._ticks += 1
        if self._ticks > 300:  # 36 s
            self._poll.stop()
            return

        def got(done) -> None:
            if gen != self._generation or done is not True:
                return
            self._poll.stop()
            if self._restore and self._scroll_y:
                self.page().runJavaScript(f"window.scrollTo(0,{self._scroll_y})")
            self.page().runJavaScript("JSON.stringify(window.__renderReport||{})", lambda r: self._emit(gen, r))

        self.page().runJavaScript("window.__renderDone === true", got)

    def _emit(self, gen: int, raw) -> None:
        if gen != self._generation:
            return
        try:
            self.rendered.emit(json.loads(raw or "{}"))
        except ValueError:
            self.rendered.emit({})

    def scroll_to_line(self, line: int) -> None:
        js = ("(function(n){var els=document.querySelectorAll('[data-line]'),best=null;"
              "for(var i=0;i<els.length;i++){if(+els[i].getAttribute('data-line')<=n)best=els[i];else break;}"
              "if(best){window.scrollTo(0,window.scrollY+best.getBoundingClientRect().top-24);}})(%d)" % line)
        self.page().runJavaScript(js)
