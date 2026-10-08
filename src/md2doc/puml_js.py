"""Prepare the vendored @plantuml/core bundle for classic-script loading from file://."""
from __future__ import annotations

import re
from pathlib import Path

from . import paths

# plantuml.js is an ES module ending in `export { a as render, b as renderToString };`.
# Rewriting that line lets it load as a classic <script> (module scripts do not run from file://).
_EXPORT = re.compile(r"export\s*\{\s*(\w+)\s+as\s+render\s*,\s*(\w+)\s+as\s+renderToString\s*\}\s*;?\s*$")
CLASSIC = "plantuml.classic.js"


def ensure_classic() -> Path:
    src = paths.PLANTUML_DIR / "plantuml.js"
    dst = paths.PLANTUML_DIR / CLASSIC
    if dst.is_file() and dst.stat().st_mtime >= src.stat().st_mtime:
        return dst
    text, n = _EXPORT.subn(r"globalThis.__plantuml={render:\1,renderToString:\2};", src.read_text(encoding="utf-8").rstrip())
    if n != 1:
        raise RuntimeError("plantuml.js export line not found - the engine version changed; update the regex in puml_js.py")
    dst.write_text(text, encoding="utf-8")
    return dst


def script_files(source_text: str) -> list[Path]:
    """Scripts to load, in order. Optional bundles (icons, emoji) only when the diagrams use them."""
    files = [paths.PLANTUML_DIR / "viz-global.js", paths.PLANTUML_DIR / "themes.js"]
    if "<&" in source_text:
        files.append(paths.PLANTUML_DIR / "openiconic.js")
    if "<:" in source_text:
        files.append(paths.PLANTUML_DIR / "emoji.js")
    files.append(ensure_classic())
    return [f for f in files if f.is_file()]
