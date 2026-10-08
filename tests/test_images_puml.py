from __future__ import annotations

from pathlib import Path

from PIL import Image

from md2doc import puml
from md2doc.fonts import validate_font
from md2doc.images import PLACEHOLDER_URI, ImageStager, sniff


def make_png(path: Path, size=(40, 30)):
    Image.new("RGB", size, (200, 30, 30)).save(path)


def stager(tmp_path, **kw):
    warnings: list[str] = []
    s = ImageStager(tmp_path, tmp_path / "assets", cache_dir=None, warn=warnings.append, **kw)
    return s, warnings


def test_local_image_is_staged_with_file_uri(tmp_path):
    make_png(tmp_path / "a b.png")
    s, w = stager(tmp_path)
    uri = s.resolve("a%20b.png")
    assert uri.startswith("file:///") and uri.endswith(".png") and not w
    assert any((tmp_path / "assets").iterdir())
    assert s.resolve("a%20b.png") == uri  # memoised, content-addressed


def test_missing_and_non_image_files_give_placeholder(tmp_path):
    (tmp_path / "x.txt").write_text("hello")
    s, w = stager(tmp_path)
    assert s.resolve("nope.png") == PLACEHOLDER_URI
    assert s.resolve("x.txt") == PLACEHOLDER_URI
    assert len(w) == 2


def test_unc_and_foreign_hosts_are_never_read(tmp_path):
    s, w = stager(tmp_path)
    assert s.resolve("\\\\server\\share\\a.png") == PLACEHOLDER_URI
    assert s.resolve("file://evil-host/share/a.png") == PLACEHOLDER_URI


def test_untrusted_mode_blocks_outside_folder(tmp_path):
    outside = tmp_path / "outside"
    inside = tmp_path / "doc"
    outside.mkdir()
    inside.mkdir()
    make_png(outside / "o.png")
    s, w = stager(inside, trusted=False)
    assert s.resolve(str(outside / "o.png")) == PLACEHOLDER_URI
    assert any("outside the document folder" in m for m in w)
    s2, _ = stager(inside, trusted=True)
    assert s2.resolve(str(outside / "o.png")).startswith("file:///")


def test_remote_disabled_and_svg_sniffing(tmp_path):
    s, w = stager(tmp_path, allow_remote=False)
    assert s.resolve("https://example.com/a.png") == PLACEHOLDER_URI
    assert sniff(b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"/>') == "image/svg+xml"
    assert sniff(b"<html></html>") is None


def test_huge_images_are_downscaled(tmp_path):
    make_png(tmp_path / "big.png", (6000, 100))
    s, _ = stager(tmp_path, max_px=1000)
    uri = s.resolve("big.png")
    staged = next((tmp_path / "assets").iterdir())
    assert uri.endswith(".png") and Image.open(staged).size[0] == 1000


def test_puml_normalize_and_preamble():
    assert puml.normalize_puml("A -> B").startswith("@startuml")
    out = puml.inject_preamble("@startuml\nA -> B\n@enduml", "skinparam x y")
    assert out.splitlines()[:2] == ["@startuml", "skinparam x y"]


def test_puml_include_policy(tmp_path):
    (tmp_path / "common.puml").write_text("@startuml\nclass A\n@enduml")
    ok, err = puml.prepare("@startuml\n!include common.puml\nA <|-- B\n@enduml", "", tmp_path)
    assert err is None and "class A" in ok and "!include" not in ok
    _, err = puml.prepare("@startuml\n!include ../secret.puml\n@enduml", "", tmp_path)
    assert err and "blocked" in err
    _, err = puml.prepare("@startuml\n!includeurl https://x.test/a.puml\n@enduml", "", tmp_path)
    assert err and "Remote" in err
    _, err = puml.prepare("@startuml\n!include <C4/C4_Context>\n@enduml", "", tmp_path)
    assert err is None  # stdlib includes stay allowed


def test_puml_encoder_roundtrips_and_decodes_documented_example():
    documented = "Syp9J4vLqBLJSCfFib9mB2t9ICqhoKnEBCdCprC8IYqiJIqkuGBAAUW2rO0LOr5LN92VLvpA1G00"
    text = "Alice -> Bob: Authentication Request" + chr(10) + "Bob --> Alice: Authentication Response" + chr(10)
    assert puml.plantuml_decode(documented) == text
    assert puml.plantuml_decode(puml.plantuml_encode(text)) == text
    uni = "A -> B : héllo 世界"
    assert puml.plantuml_decode(puml.plantuml_encode(uni)) == uni


def test_svg_isolation_prefixes_ids_and_strips_scripts():
    svg = '<?xml version="1.0"?><svg onload="x()"><script>1</script><defs><g id="a"/></defs><use href="#a" fill="url(#a)"/></svg>'
    out = puml.isolate_svg(svg, "pu0")
    assert "script" not in out and "onload" not in out and 'id="pu0-a"' in out and "#pu0-a" in out


def test_font_validation_suggests_close_names():
    ok, hints = validate_font("Seoge UI")
    assert not ok and "Segoe UI" in hints
    assert validate_font("sans-serif")[0]
    assert validate_font("Inter", extra={"Inter"})[0]
