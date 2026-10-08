"""Assemble the complete static HTML document that both the exporter and the preview load."""
from __future__ import annotations

import html
import json
import re
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from . import cssgen, diagram_theme, paths
from .fonts import font_face_css, first_family
from .theme import Theme

# bundled OFL families -> (file, weight, style)
BUNDLED_FACES: dict[str, list[tuple[str, str, str]]] = {
    "Inter": [("Inter-Regular.ttf", "400", "normal"), ("Inter-Italic.ttf", "400", "italic"),
              ("Inter-Bold.ttf", "700", "normal"), ("Inter-BoldItalic.ttf", "700", "italic")],
    "JetBrains Mono": [("JetBrainsMono-Regular.ttf", "400", "normal"), ("JetBrainsMono-Italic.ttf", "400", "italic"),
                       ("JetBrainsMono-Bold.ttf", "700", "normal"), ("JetBrainsMono-BoldItalic.ttf", "700", "italic")],
    "Source Serif 4": [("SourceSerif4-Regular.ttf", "400", "normal"), ("SourceSerif4-It.ttf", "400", "italic"),
                       ("SourceSerif4-Bold.ttf", "700", "normal"), ("SourceSerif4-BoldIt.ttf", "700", "italic")],
}


@dataclass
class DocMeta:
    title: str = ""
    subtitle: str = ""
    author: str = ""
    date: str = ""
    lang: str = "en"


@dataclass
class BuildInput:
    body_html: str
    theme: Theme
    mode: str  # pdf | png | preview
    meta: DocMeta = field(default_factory=DocMeta)
    headings: list[tuple[int, str, str]] = field(default_factory=list)
    toc_depth: int = 0  # 0 = no TOC
    cover: bool = False
    has_math: bool = False
    has_mermaid: bool = False
    has_plantuml_js: bool = False
    plantuml_source_text: str = ""  # used to decide which optional PlantUML bundles to include
    user_css: list[str] = field(default_factory=list)
    extra_faces: list[dict] = field(default_factory=list)  # imported fonts: {family,file,weight,style,variable}
    mermaid_look: str = "classic"
    mermaid_elk: bool = False
    deadline_ms: int = 120_000
    katex_output: str = "html"
    numbered_headings: bool = False


def _stack_families(stack: str) -> list[str]:
    return [p.strip().strip("\"'") for p in stack.split(",") if p.strip()]


def _font_faces(theme: Theme, extra: list[dict]) -> tuple[str, list[str]]:
    """@font-face css for bundled + imported fonts that this theme uses, and the families to preload."""
    f = theme.fonts
    wanted: list[str] = []
    for stack in (f.body, f.heading or f.body, f.mono, theme.diagram.font or ""):
        wanted += _stack_families(stack)
    faces: list[dict] = []
    for fam in dict.fromkeys(wanted):
        for fname, weight, style in BUNDLED_FACES.get(fam, []):
            fp = paths.FONTS_DIR / fname
            if fp.is_file():
                faces.append({"family": fam, "file": fp, "weight": weight, "style": style})
    faces += extra
    families = list(dict.fromkeys(fc["family"] for fc in faces))
    return font_face_css(faces) if faces else "", families


def _toc_html(headings: list[tuple[int, str, str]], depth: int) -> str:
    items = [(lvl, hid, text) for lvl, hid, text in headings if lvl <= depth and hid and text]
    if not items:
        return ""
    base = min(lvl for lvl, _, _ in items)
    li = "".join(
        f'<li class="toc-l{lvl - base + 1}"><a href="#{html.escape(hid)}">{html.escape(text)}</a></li>' for lvl, hid, text in items
    )
    return f'<nav class="toc"><div class="toc-title">Contents</div><ul>{li}</ul></nav>'


def _cover_html(m: DocMeta) -> str:
    if not m.title:
        return ""
    sub = f'<div class="subtitle">{html.escape(m.subtitle)}</div>' if m.subtitle else ""
    meta = " &middot; ".join(html.escape(x) for x in (m.author, m.date) if x)
    meta_html = f'<div class="meta">{meta}</div>' if meta else ""
    return f'<section class="cover"><h1>{html.escape(m.title)}</h1>{sub}{meta_html}</section>'


def _css_safe(css: str) -> str:
    return re.sub(r"</(style)", r"<\\/\1", css, flags=re.I)


def _script(src: Path, nonce: str) -> str:
    return f'<script nonce="{nonce}" src="{src.resolve().as_uri()}"></script>\n'


def build_html(b: BuildInput) -> str:
    t, m = b.theme, b.meta
    nonce = secrets.token_urlsafe(16)
    csp = (
        f"default-src 'none'; script-src 'nonce-{nonce}' 'wasm-unsafe-eval'; style-src 'unsafe-inline' file:; "
        "font-src file: data:; img-src file: data:; connect-src 'none'; frame-src 'none'; object-src 'none'; "
        "base-uri 'none'; form-action 'none'; worker-src blob:"
    )
    face_css, families = _font_faces(t, b.extra_faces)
    title = m.title or next((txt for lvl, _, txt in b.headings if lvl == 1), "") or "Document"
    base_css = (paths.WEB_DIR / "base.css").read_text(encoding="utf-8")
    css_parts = [face_css, cssgen.theme_css(t, m.title or title), base_css, cssgen.pygments_css(t)]
    css_parts += b.user_css

    pw, ph = cssgen.printable_px(t)
    css_parts.insert(1, f":root{{--printable-w:{pw}px;--printable-h:{ph}px}}")
    cfg = {
        "mode": b.mode, "fontFamilies": families, "fontWeights": [400, 700],
        "katexOutput": b.katex_output, "deadlineMs": b.deadline_ms,
        "mermaidTimeoutMs": 20000, "plantumlTimeoutMs": 30000,
        "printableWidthPx": pw, "printableHeightPx": ph,
    }
    if b.has_mermaid:
        cfg["mermaid"] = diagram_theme.mermaid_config(t, look=b.mermaid_look, elk=b.mermaid_elk)

    head = [
        '<!doctype html>',
        f'<html lang="{html.escape(m.lang)}" data-mode="{b.mode}" data-table="{t.layout.table_style}"'
        f'{" data-numbered" if (b.numbered_headings or t.layout.heading_numbers) else ""}'
        f'{" class=transparent" if (b.mode == "png" and t.layout.png.transparent) else ""}>',
        '<head><meta charset="utf-8">',
        f'<meta http-equiv="Content-Security-Policy" content="{csp}">',
        f"<title>{html.escape(title)}</title>",
    ]
    if b.has_math:
        head.append(f'<link rel="stylesheet" href="{(paths.KATEX_DIR / "katex.min.css").resolve().as_uri()}">')
    head.append("<style>" + _css_safe("\n".join(p for p in css_parts if p)) + "</style></head>")

    toc = _toc_html(b.headings, b.toc_depth) if b.toc_depth else ""
    cover = _cover_html(m) if b.cover else ""
    body = [f'<body class="md">{cover}{toc}<main class="content">{b.body_html}</main>']

    scripts = []
    if b.has_math:
        scripts.append(_script(paths.KATEX_DIR / "katex.min.js", nonce))
        mhchem = paths.KATEX_DIR / "contrib" / "mhchem.min.js"
        if mhchem.is_file():
            scripts.append(_script(mhchem, nonce))
    if b.has_mermaid:
        scripts.append(_script(paths.MERMAID_JS, nonce))
    if b.has_plantuml_js:
        from . import puml_js

        scripts += [_script(p, nonce) for p in puml_js.script_files(b.plantuml_source_text)]
    # a JS global (not a DOM element looked up by id, which a document could shadow); ASCII-only, no < > &
    payload = (json.dumps(cfg, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))
    scripts.append(f'<script nonce="{nonce}">window.__md2docConfig={payload};</script>\n')
    scripts.append(_script(paths.WEB_DIR / "render.js", nonce))
    return "\n".join(head) + "\n" + body[0] + "\n" + "".join(scripts) + "</body></html>\n"
