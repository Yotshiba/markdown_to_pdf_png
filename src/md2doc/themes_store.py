"""Locate and load theme presets (bundled + the user's own JSON themes)."""
from __future__ import annotations

import json
from pathlib import Path

from . import paths


def user_theme_dir() -> Path:
    return paths.user_dirs()[0] / "themes"


def _scan(d: Path, source: str, out: dict[str, dict]) -> None:
    if not d.is_dir():
        return
    for f in sorted(d.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            out[data.get("id", f.stem)] = {"name": data.get("name", f.stem), "mode": data.get("mode", "light"),
                                           "path": f, "source": source}
        except (OSError, ValueError):
            continue


def list_themes() -> dict[str, dict]:
    out: dict[str, dict] = {}
    _scan(paths.THEMES_DIR, "built-in", out)
    _scan(user_theme_dir(), "user", out)  # user themes may shadow built-ins
    return out


def load_preset(name_or_path: str) -> dict:
    """Preset dict by id ('nord'), or from a .json file path."""
    p = Path(name_or_path)
    if p.suffix.lower() == ".json" and p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    themes = list_themes()
    if name_or_path not in themes:
        import difflib

        hint = difflib.get_close_matches(name_or_path, list(themes), n=3)
        raise KeyError(f"unknown theme {name_or_path!r}" + (f" (did you mean {', '.join(hint)}?)" if hint else "")
                       + f". Available: {', '.join(sorted(themes))}")
    return json.loads(themes[name_or_path]["path"].read_text(encoding="utf-8"))


def save_user_theme(theme_dict: dict) -> Path:
    d = user_theme_dir()
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{theme_dict['id']}.json"
    f.write_text(json.dumps(theme_dict, indent=2), encoding="utf-8")
    return f
