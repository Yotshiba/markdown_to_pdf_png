"""Single source of truth for where bundled resources live."""
from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
if getattr(sys, "_MEIPASS", None):
    PACKAGE_DIR = PACKAGE_DIR / "md2doc"

WEB_DIR = PACKAGE_DIR / "web"
THEMES_DIR = PACKAGE_DIR / "themes"
VENDOR_DIR = PACKAGE_DIR / "vendor"
LOCK_FILE = PACKAGE_DIR / "vendor.lock.json"

KATEX_DIR = VENDOR_DIR / "katex"
MERMAID_JS = VENDOR_DIR / "mermaid" / "mermaid.min.js"
PLANTUML_DIR = VENDOR_DIR / "plantuml-js"
PLANTUML_JAR_DIR = VENDOR_DIR / "plantuml-jar"
JRE_DIR = VENDOR_DIR / "jre"
FONTS_DIR = VENDOR_DIR / "fonts"


def user_dirs() -> tuple[Path, Path]:
    """(config_dir, cache_dir) under the user profile."""
    from platformdirs import user_cache_dir, user_config_dir

    return Path(user_config_dir("md2doc", appauthor=False)), Path(user_cache_dir("md2doc", appauthor=False))


def vendor_status() -> dict[str, bool]:
    """Which renderers are installed (used by `md2doc doctor` and the GUI)."""
    return {
        "katex": (KATEX_DIR / "katex.min.js").is_file() and (KATEX_DIR / "katex.min.css").is_file(),
        "mermaid": MERMAID_JS.is_file(),
        "plantuml-js": (PLANTUML_DIR / "plantuml.js").is_file() and (PLANTUML_DIR / "viz-global.js").is_file(),
        "fonts": (FONTS_DIR / "Inter-Regular.ttf").is_file(),
        "plantuml-jar": any(PLANTUML_JAR_DIR.glob("*.jar")) if PLANTUML_JAR_DIR.is_dir() else False,
    }
