"""Theme / colour tone / font / page / diagram settings. Produces the fields of a `Job`."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox,
                               QHBoxLayout, QLabel, QPushButton, QScrollArea, QSlider, QSpinBox, QVBoxLayout, QWidget)

from ..fonts import installed_families
from ..themes_store import list_themes

DEFAULT = "(theme default)"
PAGE_SIZES = ["A4", "A3", "A5", "B5", "Letter", "Legal", "Tabloid"]


class ColorButton(QPushButton):
    changed = Signal()

    def __init__(self, color: str = "#0969da"):
        super().__init__()
        self._color = color
        self.setFixedWidth(96)
        self.clicked.connect(self._pick)
        self._paint()

    def color(self) -> str:
        return self._color

    def set_color(self, c: str) -> None:
        self._color = c
        self._paint()

    def _paint(self) -> None:
        q = QColor(self._color)
        fg = "#000" if q.lightness() > 140 else "#fff"
        self.setText(self._color)
        self.setStyleSheet(f"background:{self._color};color:{fg};border:1px solid rgba(128,128,128,0.55);padding:4px;")

    def _pick(self) -> None:
        c = QColorDialog.getColor(QColor(self._color), self, "Choose colour")
        if c.isValid():
            self._color = c.name()
            self._paint()
            self.changed.emit()


class PaletteStrip(QWidget):
    """Shows the resolved theme colours so tone changes are visible at a glance."""

    def __init__(self):
        super().__init__()
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(2)
        self._cells: list[QLabel] = []

    def set_colors(self, colors: list[tuple[str, str]]) -> None:
        while len(self._cells) < len(colors):
            lab = QLabel()
            lab.setFixedHeight(22)
            lab.setMinimumWidth(18)
            self._lay.addWidget(lab, 1)
            self._cells.append(lab)
        for lab, (name, col) in zip(self._cells, colors):
            lab.setStyleSheet(f"background:{col};border:1px solid rgba(128,128,128,0.4);")
            lab.setToolTip(f"{name}  {col}")


def _group(title: str) -> tuple[QGroupBox, QFormLayout]:
    g = QGroupBox(title)
    f = QFormLayout(g)
    f.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
    f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    return g, f


def _slider(lo: int, hi: int, val: int) -> QSlider:
    s = QSlider(Qt.Orientation.Horizontal)
    s.setRange(lo, hi)
    s.setValue(val)
    return s


class SettingsPanel(QScrollArea):
    changed = Signal()
    font_imported = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setMinimumWidth(300)
        self.font_files: list[Path] = []
        root = QWidget()
        lay = QVBoxLayout(root)
        self.setWidget(root)

        # ---- theme ----------------------------------------------------------------------------
        g, f = _group("Theme")
        self.theme = QComboBox()
        self.reload_themes("github-light")
        self.mode = QComboBox()
        self.mode.addItems([DEFAULT, "Light", "Dark"])
        f.addRow("Preset", self.theme)
        f.addRow("Mode", self.mode)
        self.palette_strip = PaletteStrip()
        f.addRow(self.palette_strip)
        lay.addWidget(g)

        # ---- colour tone ------------------------------------------------------------------------
        g, f = _group("Colour tone")
        self.use_tone = QCheckBox("Generate a palette from one colour")
        self.tone_seed = ColorButton("#0969da")
        self.temperature = _slider(-100, 100, 0)
        self.saturation = _slider(0, 200, 100)
        self.lightness = _slider(-100, 100, 0)
        self.use_accent = QCheckBox("Custom accent colour")
        self.accent = ColorButton("#e91e63")
        f.addRow(self.use_tone)
        f.addRow("Seed colour", self.tone_seed)
        f.addRow("Cool - Warm", self.temperature)
        f.addRow("Saturation", self.saturation)
        f.addRow("Background", self.lightness)
        f.addRow(self.use_accent, self.accent)
        lay.addWidget(g)

        # ---- fonts ------------------------------------------------------------------------------
        g, f = _group("Fonts")
        fams = sorted(installed_families(), key=str.lower)
        self.body_font, self.heading_font, self.mono_font = (self._font_combo(fams) for _ in range(3))
        self.font_size = QDoubleSpinBox()
        self.font_size.setRange(0, 36)
        self.font_size.setSingleStep(0.5)
        self.font_size.setSpecialValueText(DEFAULT)
        self.font_size.setSuffix(" pt")
        self.line_height = QDoubleSpinBox()
        self.line_height.setRange(0, 3)
        self.line_height.setSingleStep(0.05)
        self.line_height.setSpecialValueText(DEFAULT)
        f.addRow("Body", self.body_font)
        f.addRow("Headings", self.heading_font)
        f.addRow("Code", self.mono_font)
        f.addRow("Size", self.font_size)
        f.addRow("Line height", self.line_height)
        row = QHBoxLayout()
        self.import_btn = QPushButton("Import font file...")
        self.clear_fonts_btn = QPushButton("Clear")
        row.addWidget(self.import_btn, 1)
        row.addWidget(self.clear_fonts_btn)
        f.addRow(row)
        self.imported_lbl = QLabel("")
        self.imported_lbl.setWordWrap(True)
        f.addRow(self.imported_lbl)
        lay.addWidget(g)

        # ---- page -------------------------------------------------------------------------------
        g, f = _group("PDF page")
        self.page_size = QComboBox()
        self.page_size.addItems([DEFAULT] + PAGE_SIZES)
        self.orientation = QComboBox()
        self.orientation.addItems([DEFAULT, "Portrait", "Landscape"])
        self.margin = QDoubleSpinBox()
        self.margin.setRange(0, 60)
        self.margin.setSpecialValueText(DEFAULT)
        self.margin.setSuffix(" mm")
        self.columns = QSpinBox()
        self.columns.setRange(0, 3)
        self.columns.setSpecialValueText(DEFAULT)
        self.page_numbers = QComboBox()
        self.page_numbers.addItems([DEFAULT, "Show", "Hide"])
        f.addRow("Size", self.page_size)
        f.addRow("Orientation", self.orientation)
        f.addRow("Margins", self.margin)
        f.addRow("Columns", self.columns)
        f.addRow("Page numbers", self.page_numbers)
        lay.addWidget(g)

        # ---- document ---------------------------------------------------------------------------
        g, f = _group("Document")
        self.toc = QSpinBox()
        self.toc.setRange(0, 6)
        self.toc.setSpecialValueText("Off")
        self.toc.setPrefix("depth ")
        self.cover = QCheckBox("Title page (from front matter)")
        self.numbered = QCheckBox("Number headings")
        self.captions = QComboBox()
        self.captions.addItems(["Image alt text", "Image title", "None"])
        f.addRow("Table of contents", self.toc)
        f.addRow(self.cover)
        f.addRow(self.numbered)
        f.addRow("Figure captions", self.captions)
        lay.addWidget(g)

        # ---- png --------------------------------------------------------------------------------
        g, f = _group("PNG image")
        self.png_width = QSpinBox()
        self.png_width.setRange(0, 4000)
        self.png_width.setSingleStep(50)
        self.png_width.setSpecialValueText(DEFAULT)
        self.png_width.setSuffix(" px")
        self.scale = QComboBox()
        self.scale.addItems([DEFAULT, "1", "1.5", "2", "3", "4"])
        self.transparent = QCheckBox("Transparent background")
        f.addRow("Width", self.png_width)
        f.addRow("Scale", self.scale)
        f.addRow(self.transparent)
        lay.addWidget(g)

        # ---- diagrams / safety -----------------------------------------------------------------
        g, f = _group("Diagrams and safety")
        self.plantuml = QComboBox()
        self.plantuml.addItem("Built-in engine (no Java)", "js")
        self.plantuml.addItem("Java (plantuml jar)", "java")
        self.plantuml.addItem("Auto (Java if available)", "auto")
        self.mermaid_look = QComboBox()
        self.mermaid_look.addItems(["classic", "neo", "handDrawn"])
        self.html_mode = QComboBox()
        self.html_mode.addItem("Sanitise raw HTML", "safe")
        self.html_mode.addItem("Disable raw HTML", "off")
        self.html_mode.addItem("Keep raw HTML", "raw")
        self.remote_images = QCheckBox("Download remote images")
        self.remote_images.setChecked(True)
        f.addRow("PlantUML", self.plantuml)
        f.addRow("Mermaid style", self.mermaid_look)
        f.addRow("Raw HTML", self.html_mode)
        f.addRow(self.remote_images)
        lay.addWidget(g)
        lay.addStretch(1)

        self._wire()

    # ------------------------------------------------------------------------------------------
    def _font_combo(self, families: list[str]) -> QComboBox:
        c = QComboBox()
        c.setEditable(True)
        c.addItem(DEFAULT)
        c.addItems(families)
        c.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        return c

    def reload_themes(self, select: str | None = None) -> None:
        cur = select or self.theme.currentData()
        self.theme.blockSignals(True)
        self.theme.clear()
        for tid, t in list_themes().items():
            self.theme.addItem(f"{t['name']}" + ("  (mine)" if t["source"] == "user" else ""), tid)
        i = self.theme.findData(cur)
        self.theme.setCurrentIndex(max(0, i))
        self.theme.blockSignals(False)

    def _wire(self) -> None:
        emit = lambda *_: self.changed.emit()  # noqa: E731
        for c in (self.theme, self.mode, self.page_size, self.orientation, self.page_numbers, self.captions,
                  self.scale, self.plantuml, self.mermaid_look, self.html_mode):
            c.currentIndexChanged.connect(emit)
        for c in (self.body_font, self.heading_font, self.mono_font):
            c.currentTextChanged.connect(emit)
        for c in (self.use_tone, self.use_accent, self.cover, self.numbered, self.transparent, self.remote_images):
            c.toggled.connect(emit)
        for c in (self.temperature, self.saturation, self.lightness):
            c.valueChanged.connect(emit)
        for c in (self.font_size, self.line_height, self.margin, self.columns, self.toc, self.png_width):
            c.valueChanged.connect(emit)
        self.tone_seed.changed.connect(lambda: (self.use_tone.setChecked(True), self.changed.emit()))
        self.accent.changed.connect(lambda: (self.use_accent.setChecked(True), self.changed.emit()))
        self.import_btn.clicked.connect(self._import_font)
        self.clear_fonts_btn.clicked.connect(self._clear_fonts)

    def _import_font(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Import font files", "", "Fonts (*.ttf *.otf *.woff2 *.woff)")
        if not files:
            return
        from ..fonts import inspect_font

        first = None
        for f in files:
            p = Path(f)
            if p not in self.font_files:
                self.font_files.append(p)
            try:
                fam = inspect_font(p)["family"]
                first = first or fam
            except Exception:  # noqa: BLE001
                pass
        self._update_imported()
        if first:
            self.font_imported.emit(first)
        self.changed.emit()

    def use_font_everywhere(self, family: str) -> None:
        self.body_font.setCurrentText(family)

    def _clear_fonts(self) -> None:
        self.font_files.clear()
        self._update_imported()
        self.changed.emit()

    def _update_imported(self) -> None:
        self.imported_lbl.setText("Imported: " + ", ".join(p.name for p in self.font_files) if self.font_files else "")

    def set_palette(self, theme) -> None:
        c = theme.colors
        self.palette_strip.set_colors([("page", c.page_bg), ("text", c.text), ("heading", c.heading), ("link", c.link),
                                       ("accent", c.accent), ("code", c.code_bg), ("border", c.border),
                                       ("quote", c.quote_bg)] + [(f"diagram {i + 1}", d.border) for i, d in enumerate(theme.diagram.palette[:4])])

    # ------------------------------------------------------------------------------------------
    @staticmethod
    def _opt(combo: QComboBox):
        t = combo.currentText().strip()
        return None if t in ("", DEFAULT) else t

    def job_fields(self) -> dict:
        f: dict = {"theme": self.theme.currentData(), "html": self.html_mode.currentData(),
                   "plantuml": self.plantuml.currentData(), "mermaid_look": self.mermaid_look.currentText(),
                   "remote_images": self.remote_images.isChecked(),
                   "captions": ["alt", "title", "none"][self.captions.currentIndex()],
                   "font_files": list(self.font_files)}
        m = self.mode.currentText()
        if m != DEFAULT:
            f["mode"] = m.lower()
        if self.use_tone.isChecked():
            f.update(tone_seed=self.tone_seed.color(), temperature=self.temperature.value() / 100,
                     saturation=self.saturation.value() / 100, lightness=self.lightness.value() / 100)
        if self.use_accent.isChecked():
            f["accent"] = self.accent.color()
        for key, combo in (("font", self.body_font), ("heading_font", self.heading_font), ("mono_font", self.mono_font)):
            v = self._opt(combo)
            if v:
                f[key] = v
        if self.font_size.value() > 0:
            f["font_size"] = self.font_size.value()
        if self.line_height.value() > 0:
            f["line_height"] = self.line_height.value()
        if (v := self._opt(self.page_size)):
            f["page_size"] = v
        if (v := self._opt(self.orientation)):
            f["orientation"] = v.lower()
        if self.margin.value() > 0:
            f["margin"] = f"{self.margin.value():g}"
        if self.columns.value() > 0:
            f["columns"] = self.columns.value()
        pn = self.page_numbers.currentText()
        if pn != DEFAULT:
            f["page_numbers"] = pn == "Show"
        if self.toc.value() > 0:
            f["toc"] = self.toc.value()
        if self.cover.isChecked():
            f["cover"] = True
        if self.numbered.isChecked():
            f["numbered_headings"] = True
        if self.png_width.value() > 0:
            f["png_width"] = self.png_width.value()
        if (v := self._opt(self.scale)):
            f["scale"] = float(v)
        if self.transparent.isChecked():
            f["transparent"] = True
        return f

    # ---- persistence ---------------------------------------------------------------------------
    def state(self) -> dict:
        return {
            "theme": self.theme.currentData(), "mode": self.mode.currentIndex(), "use_tone": self.use_tone.isChecked(),
            "tone_seed": self.tone_seed.color(), "temperature": self.temperature.value(), "saturation": self.saturation.value(),
            "lightness": self.lightness.value(), "use_accent": self.use_accent.isChecked(), "accent": self.accent.color(),
            "body_font": self.body_font.currentText(), "heading_font": self.heading_font.currentText(),
            "mono_font": self.mono_font.currentText(), "font_size": self.font_size.value(), "line_height": self.line_height.value(),
            "font_files": [str(p) for p in self.font_files], "page_size": self.page_size.currentIndex(),
            "orientation": self.orientation.currentIndex(), "margin": self.margin.value(), "columns": self.columns.value(),
            "page_numbers": self.page_numbers.currentIndex(), "toc": self.toc.value(), "cover": self.cover.isChecked(),
            "numbered": self.numbered.isChecked(), "captions": self.captions.currentIndex(), "png_width": self.png_width.value(),
            "scale": self.scale.currentIndex(), "transparent": self.transparent.isChecked(),
            "plantuml": self.plantuml.currentIndex(), "mermaid_look": self.mermaid_look.currentIndex(),
            "html_mode": self.html_mode.currentIndex(), "remote_images": self.remote_images.isChecked(),
        }

    def set_state(self, s: dict) -> None:
        for w in self.findChildren(QWidget):
            w.blockSignals(True)
        try:
            if (i := self.theme.findData(s.get("theme"))) >= 0:
                self.theme.setCurrentIndex(i)
            self.mode.setCurrentIndex(s.get("mode", 0))
            self.use_tone.setChecked(s.get("use_tone", False))
            self.tone_seed.set_color(s.get("tone_seed", "#0969da"))
            self.temperature.setValue(s.get("temperature", 0))
            self.saturation.setValue(s.get("saturation", 100))
            self.lightness.setValue(s.get("lightness", 0))
            self.use_accent.setChecked(s.get("use_accent", False))
            self.accent.set_color(s.get("accent", "#e91e63"))
            self.body_font.setCurrentText(s.get("body_font", DEFAULT))
            self.heading_font.setCurrentText(s.get("heading_font", DEFAULT))
            self.mono_font.setCurrentText(s.get("mono_font", DEFAULT))
            self.font_size.setValue(s.get("font_size", 0))
            self.line_height.setValue(s.get("line_height", 0))
            self.font_files = [Path(p) for p in s.get("font_files", []) if Path(p).is_file()]
            self._update_imported()
            self.page_size.setCurrentIndex(s.get("page_size", 0))
            self.orientation.setCurrentIndex(s.get("orientation", 0))
            self.margin.setValue(s.get("margin", 0))
            self.columns.setValue(s.get("columns", 0))
            self.page_numbers.setCurrentIndex(s.get("page_numbers", 0))
            self.toc.setValue(s.get("toc", 0))
            self.cover.setChecked(s.get("cover", False))
            self.numbered.setChecked(s.get("numbered", False))
            self.captions.setCurrentIndex(s.get("captions", 0))
            self.png_width.setValue(s.get("png_width", 0))
            self.scale.setCurrentIndex(s.get("scale", 0))
            self.transparent.setChecked(s.get("transparent", False))
            self.plantuml.setCurrentIndex(s.get("plantuml", 0))
            self.mermaid_look.setCurrentIndex(s.get("mermaid_look", 0))
            self.html_mode.setCurrentIndex(s.get("html_mode", 0))
            self.remote_images.setChecked(s.get("remote_images", True))
        finally:
            for w in self.findChildren(QWidget):
                w.blockSignals(False)
