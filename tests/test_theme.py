from __future__ import annotations

import json

import pytest

from md2doc import cssgen, diagram_theme, paths, tone
from md2doc.job import Job
from md2doc.pipeline import resolve_theme
from md2doc.theme import Theme, audit, resolve
from md2doc.themes_store import list_themes, load_preset

PRESETS = sorted(p.stem for p in paths.THEMES_DIR.glob("*.json"))


def test_ten_presets_ship():
    assert len(PRESETS) >= 10


@pytest.mark.parametrize("name", PRESETS)
def test_preset_validates_and_is_readable(name):
    t = Theme.model_validate(load_preset(name))
    assert audit(t) == [], f"{name} has low-contrast pairs"
    css = cssgen.theme_css(t, "T")
    assert "--page-bg" in css and "@page" in css
    cfg = diagram_theme.mermaid_config(t)
    assert cfg["theme"] == "base" and cfg["layout"] == "dagre" and cfg["themeVariables"]["background"] == t.colors.page_bg
    assert "skinparam backgroundColor transparent" in diagram_theme.plantuml_prologue(t)


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("seed", ["#0969da", "#e91e63", "#2e7d32", "#ff9800", "#6a1b9a"])
@pytest.mark.parametrize("temperature", [-1.0, 0.0, 1.0])
def test_tone_engine_keeps_text_readable(mode, seed, temperature):
    p = tone.derive_palette(seed, mode, temperature=temperature, saturation=1.2)
    assert tone.contrast(p["text"], p["page_bg"]) >= 7
    assert tone.contrast(p["link"], p["page_bg"]) >= 4.5
    assert tone.contrast(p["heading"], p["page_bg"]) >= 4.5


def test_tone_changes_palette():
    a = tone.derive_palette("#0969da", "light")
    b = tone.derive_palette("#e91e63", "light")
    assert a["accent"] != b["accent"] and a["page_bg"] != b["page_bg"]


def test_precedence_cli_over_front_matter_over_preset():
    preset = load_preset("github-light")
    t = resolve(preset, None, {"fonts": {"size_pt": 12}}, {"fonts": {"size_pt": 14}})
    assert t.fonts.size_pt == 14
    t = resolve(preset, None, {"fonts": {"size_pt": 12}}, {})
    assert t.fonts.size_pt == 12


def test_job_overrides_flow_into_theme():
    job = Job(theme="nord", font="Georgia", font_size=13, accent="#e91e63", page_size="Letter", orientation="landscape",
              margin="10 20", columns=2, png_width=1200, scale=3, page_numbers=False)
    t = resolve_theme(job, {})
    assert t.id == "nord" and "Georgia" in t.fonts.body and t.fonts.size_pt == 13
    assert t.colors.accent == "#e91e63" and t.layout.page.size == "Letter" and t.layout.page.orientation == "landscape"
    assert t.layout.page.margin_mm == (10, 20, 10, 20) and t.layout.page.columns == 2
    assert t.layout.png.width_px == 1200 and t.layout.png.scale == 3 and not t.layout.page.footer.page_numbers


def test_tone_seed_regenerates_palette_in_requested_mode():
    t = resolve_theme(Job(theme="github-light", tone_seed="#2e7d32", mode="dark", temperature=0.5), {})
    assert t.mode == "dark" and tone.luminance(t.colors.page_bg) < 0.1
    assert audit(t) == []


def test_front_matter_theme_is_used_unless_cli_overrides():
    assert resolve_theme(Job(), {"__theme__": "dracula"}).id == "dracula"
    assert resolve_theme(Job(theme="nord"), {"__theme__": "dracula"}).id == "nord"


def test_unknown_theme_has_a_helpful_error():
    with pytest.raises(KeyError, match="did you mean"):
        load_preset("nordd")


def test_theme_roundtrips_as_user_theme(tmp_path):
    t = resolve_theme(Job(theme="nord", accent="#e91e63"), {})
    d = json.loads(t.model_dump_json())
    d["id"], d["name"] = "mine", "Mine"
    assert Theme.model_validate(d).colors.accent == "#e91e63"
    assert "nord" in list_themes()


def test_tone_actually_replaces_the_preset_palette():
    base = resolve_theme(Job(theme="github-light"), {})
    toned = resolve_theme(Job(theme="github-light", tone_seed="#2e7d32"), {})
    assert toned.colors.page_bg != base.colors.page_bg or toned.colors.accent != base.colors.accent
    assert toned.colors.accent != "#0969da" and toned.code.pygments_style is None and audit(toned) == []


def test_mode_flip_derives_a_matching_palette():
    dark = resolve_theme(Job(theme="github-light", mode="dark"), {})
    assert dark.mode == "dark" and tone.luminance(dark.colors.page_bg) < 0.1 and audit(dark) == []
    light = resolve_theme(Job(theme="nord", mode="light"), {})
    assert light.mode == "light" and tone.luminance(light.colors.page_bg) > 0.8


def test_explicit_colours_in_the_same_layer_beat_the_generated_ones():
    t = resolve_theme(Job(theme="github-light", tone_seed="#2e7d32", theme_overrides={"colors": {"page_bg": "#fffbe6"}}), {})
    assert t.colors.page_bg == "#fffbe6" and t.colors.accent != "#0969da"
