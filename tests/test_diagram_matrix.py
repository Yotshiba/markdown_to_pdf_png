"""Every Mermaid and PlantUML type we advertise renders without an error card, in light and dark themes."""
from __future__ import annotations

from pathlib import Path

import pytest

from md2doc import cli, puml

pytestmark = pytest.mark.browser

FIX = Path(__file__).resolve().parent / "fixtures"
THEMES = ["github-light", "nord", "high-contrast"]


def convert(md: Path, out: Path, *args: str, capsys) -> str:
    assert cli.main([str(md), "-o", str(out), "--scale", "1", *args]) == 0
    return capsys.readouterr().err


@pytest.mark.parametrize("theme", THEMES)
def test_every_mermaid_type_renders(theme, tmp_path, capsys):
    err = convert(FIX / "diagrams_mermaid.md", tmp_path / "m.png", "-f", "png", "--theme", theme, capsys=capsys)
    bad = [ln for ln in err.splitlines() if "[mermaid]" in ln]
    assert not bad, "\n".join(bad)


@pytest.mark.parametrize("theme", THEMES)
def test_every_plantuml_type_renders_with_the_js_engine(theme, tmp_path, capsys):
    err = convert(FIX / "diagrams_plantuml.md", tmp_path / "p.png", "-f", "png", "--theme", theme, capsys=capsys)
    bad = [ln for ln in err.splitlines() if "[plantuml]" in ln]
    if not (puml.find_java() and puml.find_jar()):  # without Java, @startsalt gets a clear card plus a warning
        bad = [ln for ln in bad if "@startsalt" not in ln]
    assert not bad, "\n".join(bad)


def test_plantuml_java_backend_renders_the_same_gallery(tmp_path, capsys):
    if not (puml.find_java() and puml.find_jar()):
        pytest.skip("Java or the PlantUML jar is not installed")
    err = convert(FIX / "diagrams_plantuml.md", tmp_path / "pj.png", "-f", "png", "--plantuml", "java", capsys=capsys)
    assert not [ln for ln in err.splitlines() if "[plantuml]" in ln], err
