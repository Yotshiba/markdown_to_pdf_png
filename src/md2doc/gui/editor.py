"""Markdown source editor: line numbers, syntax highlighting, image paste/drop."""
from __future__ import annotations

import re
import time
from pathlib import Path

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QKeySequence, QPainter, QPalette, QShortcut, QSyntaxHighlighter,
                           QTextCharFormat, QTextCursor, QTextFormat)
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}


def _fmt(color: str, *, bold=False, italic=False, bg: str | None = None) -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Weight.Bold)
    f.setFontItalic(italic)
    if bg:
        f.setBackground(QColor(bg))
    return f


class MarkdownHighlighter(QSyntaxHighlighter):
    """Small state-aware highlighter: fenced code, $$ math, headings, emphasis, inline code, links, quotes, lists."""

    FENCE, MATH = 1, 2

    def __init__(self, doc, dark: bool = False):
        super().__init__(doc)
        self.set_dark(dark, rehighlight=False)

    def set_dark(self, dark: bool, rehighlight: bool = True) -> None:
        c = (dict(head="#79c0ff", bold="#e6edf3", ital="#e6edf3", code="#ffa657", codebg="#2d333b", link="#58a6ff",
                  quote="#8b949e", list="#ff7b72", fence="#8b949e", math="#d2a8ff", rule="#6e7681") if dark else
             dict(head="#0550ae", bold="#1f2328", ital="#1f2328", code="#953800", codebg="#eff1f3", link="#0969da",
                  quote="#59636e", list="#cf222e", fence="#59636e", math="#8250df", rule="#8c959f"))
        self.f_head = _fmt(c["head"], bold=True)
        self.f_bold = _fmt(c["bold"], bold=True)
        self.f_ital = _fmt(c["ital"], italic=True)
        self.f_code = _fmt(c["code"], bg=c["codebg"])
        self.f_link = _fmt(c["link"])
        self.f_quote = _fmt(c["quote"], italic=True)
        self.f_list = _fmt(c["list"], bold=True)
        self.f_fence = _fmt(c["fence"])
        self.f_math = _fmt(c["math"])
        self.f_rule = _fmt(c["rule"])
        if rehighlight:
            self.rehighlight()

    _re_head = re.compile(r"^\s{0,3}#{1,6}\s")
    _re_bold = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1")
    _re_ital = re.compile(r"(?<![*_\w])([*_])(?=\S)(.+?)(?<=\S)\1(?![*_\w])")
    _re_code = re.compile(r"`[^`\n]+`")
    _re_link = re.compile(r"!?\[[^\]\n]*\]\([^)\n]*\)")
    _re_list = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s(?:\[[ xX]\]\s)?")
    _re_imath = re.compile(r"(?<![\\$])\$(?!\s)[^$\n]+?(?<!\s)\$(?!\d)")

    def highlightBlock(self, text: str) -> None:
        prev = self.previousBlockState()
        stripped = text.strip()
        if prev == self.FENCE:
            self.setFormat(0, len(text), self.f_code)
            self.setCurrentBlockState(0 if stripped.startswith(("```", "~~~")) else self.FENCE)
            if stripped.startswith(("```", "~~~")):
                self.setFormat(0, len(text), self.f_fence)
            return
        if prev == self.MATH:
            self.setFormat(0, len(text), self.f_math)
            self.setCurrentBlockState(0 if "$$" in text else self.MATH)
            return
        if stripped.startswith(("```", "~~~")):
            self.setFormat(0, len(text), self.f_fence)
            self.setCurrentBlockState(self.FENCE)
            return
        if stripped.startswith("$$") and not (len(stripped) > 2 and stripped.endswith("$$")):
            self.setFormat(0, len(text), self.f_math)
            self.setCurrentBlockState(self.MATH)
            return
        self.setCurrentBlockState(0)
        if self._re_head.match(text):
            self.setFormat(0, len(text), self.f_head)
            return
        if stripped.startswith(">"):
            self.setFormat(0, len(text), self.f_quote)
        if re.fullmatch(r"\s*([-*_])(\s*\1){2,}\s*", text):
            self.setFormat(0, len(text), self.f_rule)
            return
        m = self._re_list.match(text)
        if m:
            self.setFormat(m.start(), m.end() - m.start(), self.f_list)
        for rx, fmt in ((self._re_bold, self.f_bold), (self._re_ital, self.f_ital), (self._re_link, self.f_link),
                        (self._re_imath, self.f_math), (self._re_code, self.f_code)):
            for mm in rx.finditer(text):
                self.setFormat(mm.start(), mm.end() - mm.start(), fmt)


class _Gutter(QWidget):
    def __init__(self, editor: "MarkdownEditor"):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self.editor.gutter_width(), 0)

    def paintEvent(self, e) -> None:
        self.editor.paint_gutter(e)


class MarkdownEditor(QPlainTextEdit):
    image_pasted = Signal(bytes)  # raw PNG bytes from the clipboard
    files_dropped = Signal(list)  # list[Path]

    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        for fam in ("Cascadia Mono", "Consolas"):
            if fam in QFontDatabase.families():
                font = QFont(fam)
                break
        font.setPointSize(11)
        self.setFont(font)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setAcceptDrops(True)
        self._gutter = _Gutter(self)
        self.blockCountChanged.connect(self._update_gutter_width)
        self.updateRequest.connect(self._update_gutter)
        self.cursorPositionChanged.connect(self._highlight_line)
        dark = self.palette().color(QPalette.ColorRole.Base).lightness() < 128  # follow the system theme
        self._dark = dark
        self.highlighter = MarkdownHighlighter(self.document(), dark)
        self._update_gutter_width()
        self._highlight_line()
        QShortcut(QKeySequence("Ctrl+B"), self, activated=lambda: self.wrap_selection("**"))
        QShortcut(QKeySequence("Ctrl+I"), self, activated=lambda: self.wrap_selection("*"))
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self.insert_link)

    # -- helpers ------------------------------------------------------------------------------
    def set_dark(self, dark: bool) -> None:
        self.highlighter.set_dark(dark)
        self._dark = dark
        self._highlight_line()

    def wrap_selection(self, mark: str) -> None:
        c = self.textCursor()
        sel = c.selectedText()
        c.insertText(f"{mark}{sel}{mark}")
        if not sel:
            c.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, len(mark))
            self.setTextCursor(c)

    def insert_link(self) -> None:
        c = self.textCursor()
        sel = c.selectedText() or "text"
        c.insertText(f"[{sel}](https://)")

    def insert_snippet(self, text: str) -> None:
        c = self.textCursor()
        c.insertText(text)
        self.setTextCursor(c)
        self.setFocus()

    def goto_line(self, line: int) -> None:
        block = self.document().findBlockByLineNumber(max(0, line - 1))
        c = QTextCursor(block)
        self.setTextCursor(c)
        self.centerCursor()
        self.setFocus()

    def current_line(self) -> int:
        return self.textCursor().blockNumber()

    # -- gutter -------------------------------------------------------------------------------
    def gutter_width(self) -> int:
        digits = max(2, len(str(self.blockCount())))
        return 14 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_gutter_width(self, *_) -> None:
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def _update_gutter(self, rect, dy) -> None:
        if dy:
            self._gutter.scroll(0, dy)
        else:
            self._gutter.update(0, rect.y(), self._gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_gutter_width()

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        cr = self.contentsRect()
        self._gutter.setGeometry(QRect(cr.left(), cr.top(), self.gutter_width(), cr.height()))

    def paint_gutter(self, event) -> None:
        p = QPainter(self._gutter)
        pal = self.palette()
        p.fillRect(event.rect(), pal.color(QPalette.ColorRole.AlternateBase))
        p.setPen(pal.color(QPalette.ColorRole.PlaceholderText))
        block = self.firstVisibleBlock()
        n = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                p.drawText(0, top, self._gutter.width() - 6, self.fontMetrics().height(),
                           Qt.AlignmentFlag.AlignRight, str(n + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            n += 1

    def _highlight_line(self) -> None:
        sel = QTextEdit.ExtraSelection()
        c = QColor(self.palette().color(QPalette.ColorRole.Highlight))
        c.setAlpha(28)
        sel.format.setBackground(c)
        sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        sel.cursor = self.textCursor()
        sel.cursor.clearSelection()
        self.setExtraSelections([sel])

    # -- paste / drop -------------------------------------------------------------------------
    def canInsertFromMimeData(self, source) -> bool:
        return source.hasImage() or super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source) -> None:
        if source.hasImage() and not source.hasText():
            from PySide6.QtCore import QBuffer, QIODevice
            from PySide6.QtGui import QImage

            img = source.imageData()
            if isinstance(img, QImage) and not img.isNull():
                buf = QBuffer()
                buf.open(QIODevice.OpenModeFlag.WriteOnly)
                img.save(buf, "PNG")
                self.image_pasted.emit(bytes(buf.data()))
                return
        super().insertFromMimeData(source)

    def dragEnterEvent(self, e) -> None:
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e) -> None:
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e) -> None:
        if e.mimeData().hasUrls():
            files = [Path(u.toLocalFile()) for u in e.mimeData().urls() if u.isLocalFile()]
            if files:
                self.files_dropped.emit(files)
                e.acceptProposedAction()
                return
        super().dropEvent(e)


def timestamp_name(prefix: str = "image", ext: str = ".png") -> str:
    return f"{prefix}-{time.strftime('%Y%m%d-%H%M%S')}{ext}"
