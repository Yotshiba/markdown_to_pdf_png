"""The single job description shared by the CLI, the GUI preview and the GUI export (as job.json)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Job(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # source
    input: Path | None = None
    markdown: str | None = None  # in-memory text (GUI); `input` still gives the base folder
    base_dir: Path | None = None
    output: Path | None = None
    format: Literal["pdf", "png"] = "pdf"

    # theme / look (all optional; None = keep what the theme or front matter says)
    theme: str | None = None
    theme_overrides: dict = Field(default_factory=dict)  # raw Theme-shaped overrides (GUI)
    mode: Literal["light", "dark"] | None = None
    accent: str | None = None
    tone_seed: str | None = None
    temperature: float | None = None
    saturation: float | None = None
    lightness: float | None = None
    font: str | None = None
    heading_font: str | None = None
    mono_font: str | None = None
    font_size: float | None = None
    line_height: float | None = None
    font_files: list[Path] = Field(default_factory=list)
    css_files: list[Path] = Field(default_factory=list)

    # page / png
    page_size: str | None = None
    orientation: Literal["portrait", "landscape"] | None = None
    margin: str | None = None
    columns: int | None = None
    page_numbers: bool | None = None
    png_width: int | None = None
    scale: float | None = None
    transparent: bool | None = None

    # document features
    toc: int | None = None  # heading depth; 0 = off; None = front matter / off
    cover: bool | None = None
    numbered_headings: bool | None = None
    captions: Literal["alt", "title", "none"] = "alt"
    typographer: bool = False

    # safety / behaviour
    html: Literal["safe", "off", "raw"] = "safe"
    trusted: bool = True
    remote_images: bool = True
    plantuml: Literal["js", "java", "auto", "remote"] = "js"
    allow_remote_plantuml: bool = False
    java_path: str | None = None
    dot_path: str | None = None
    browser_path: str | None = None
    mermaid_look: Literal["classic", "neo", "handDrawn"] = "classic"
    mermaid_elk: bool = False
    deadline_s: int = 120
    keep_temp: bool = False
    strict: bool = False

    def overrides(self) -> dict:
        """Flatten the simple fields into a Theme-shaped override dict (merged over front matter)."""
        from .frontmatter import margins

        ov: dict = {}

        def put(path: list[str], value) -> None:
            d = ov
            for k in path[:-1]:
                d = d.setdefault(k, {})
            d[path[-1]] = value

        def fam(name: str) -> str:
            return f"'{name}', sans-serif" if name else name

        if self.mode:
            ov["mode"] = self.mode
        if self.tone_seed or self.temperature is not None or self.saturation is not None or self.lightness is not None:
            tone = {"seed": self.tone_seed or self.accent or "#0969da"}
            for k in ("temperature", "saturation", "lightness"):
                if getattr(self, k) is not None:
                    tone[k] = getattr(self, k)
            ov["tone"] = tone
        if self.accent:
            ov["accent"] = self.accent
        if self.font:
            put(["fonts", "body"], fam(self.font))
        if self.heading_font:
            put(["fonts", "heading"], fam(self.heading_font))
        if self.mono_font:
            put(["fonts", "mono"], f"'{self.mono_font}', monospace")
        if self.font_size:
            put(["fonts", "size_pt"], self.font_size)
        if self.line_height:
            put(["fonts", "line_height"], self.line_height)
        if self.page_size:
            put(["layout", "page", "size"], self.page_size)
        if self.orientation:
            put(["layout", "page", "orientation"], self.orientation)
        if self.margin:
            put(["layout", "page", "margin_mm"], list(margins(self.margin)))
        if self.columns:
            put(["layout", "page", "columns"], self.columns)
        if self.page_numbers is not None:
            put(["layout", "page", "footer", "page_numbers"], self.page_numbers)
        if self.png_width:
            put(["layout", "png", "width_px"], self.png_width)
        if self.scale:
            put(["layout", "png", "scale"], self.scale)
        if self.transparent is not None:
            put(["layout", "png", "transparent"], self.transparent)
        from .theme import deep_merge

        return deep_merge(ov, self.theme_overrides) if self.theme_overrides else ov

    @classmethod
    def load(cls, path: Path) -> "Job":
        return cls.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))

    def dump(self, path: Path) -> None:
        Path(path).write_text(self.model_dump_json(indent=1, exclude_defaults=True), encoding="utf-8")
