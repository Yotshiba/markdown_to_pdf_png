"""End-to-end tests: real headless Edge/Chrome. Skipped automatically when it or the renderers are missing."""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageChops

from md2doc import cli

pytestmark = pytest.mark.browser

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "sample.md"
HOSTILE = ROOT / "tests" / "fixtures" / "hostile.md"


def pdf_text(path: Path) -> str:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    return "\n".join(pdf[i].get_textpage().get_text_range() for i in range(len(pdf)))


def run(*args: str) -> int:
    return cli.main([str(a) for a in args])


def test_sample_pdf_has_real_text_pages_outline_and_footer(tmp_path):
    out = tmp_path / "s.pdf"
    assert run(SAMPLE, "-o", out, "-q") == 0
    from pypdf import PdfReader

    r = PdfReader(str(out))
    assert len(r.pages) >= 3
    assert abs(float(r.pages[0].mediabox.width) - 595) < 2  # A4
    assert len(r.outline) >= 1
    text = pdf_text(out)
    for needle in ("Feature tour", "Inline math", "def fibonacci", "Page 1 of"):
        assert needle in text


def test_pdf_page_size_orientation_and_theme_background(tmp_path):
    out = tmp_path / "l.pdf"
    assert run(SAMPLE, "-o", out, "-q", "--page-size", "Letter", "--landscape", "--theme", "nord") == 0
    from pypdf import PdfReader

    box = PdfReader(str(out)).pages[0].mediabox
    assert float(box.width) > float(box.height) and abs(float(box.height) - 612) < 2
    import pypdfium2 as pdfium

    img = pdfium.PdfDocument(str(out))[0].render(scale=0.3).to_pil().convert("RGB")
    r, g, b = img.getpixel((2, 2))  # margin area must carry the dark page colour
    assert r < 80 and g < 80 and b < 100


def test_png_theme_font_and_size(tmp_path):
    out = tmp_path / "s.png"
    assert run(SAMPLE, "-f", "png", "-o", out, "-q", "--theme", "dracula", "--png-width", "700", "--scale", "1") == 0
    im = Image.open(out).convert("RGB")
    assert im.width == 700 and im.height > 1000
    assert sum(im.getpixel((3, 3))) < 200  # dark theme


def test_themes_change_the_output(tmp_path):
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    assert run(SAMPLE, "-f", "png", "-o", a, "-q", "--scale", "1", "--theme", "github-light") == 0
    assert run(SAMPLE, "-f", "png", "-o", b, "-q", "--scale", "1", "--theme", "paper-sepia", "--accent", "#e91e63") == 0
    assert ImageChops.difference(Image.open(a).convert("RGB"), Image.open(b).convert("RGB").resize(Image.open(a).size)).getbbox()


def test_diagram_and_math_errors_do_not_abort_and_are_reported(tmp_path, capsys):
    out = tmp_path / "h.pdf"
    assert run(HOSTILE, "-o", out) == 0
    err = capsys.readouterr().err
    assert out.is_file()
    assert "[mermaid]" in err and "[plantuml]" in err and "[math]" in err and "image unavailable" in err
    text = pdf_text(out)
    assert "Still renders after all of that" in text and "PWNED" not in text


def test_strict_mode_fails_on_warnings(tmp_path):
    assert run(HOSTILE, "-o", tmp_path / "x.pdf", "-q", "--strict") == cli.EXIT_STRICT


def test_hostile_html_cannot_run_or_reach_the_network(tmp_path):
    out = tmp_path / "x.pdf"
    assert run(HOSTILE, "-o", out, "-q", "--html", "raw", "--keep-temp") == 0  # even 'raw': the CSP blocks scripts
    assert "PWNED" not in pdf_text(out)


def test_missing_input_and_unknown_theme_exit_codes(tmp_path):
    assert run(tmp_path / "nope.md", "-o", tmp_path / "x.pdf", "-q") == cli.EXIT_FATAL
    assert run(SAMPLE, "-o", tmp_path / "x.pdf", "-q", "--theme", "does-not-exist") == cli.EXIT_FATAL


def test_very_long_png_is_tiled_without_wrapping(tmp_path):
    md = tmp_path / "long.md"
    md.write_text("\n".join(f"## Section {i}\n\n" + "Lorem ipsum dolor sit amet. " * 20 + "\n" for i in range(1, 110)), encoding="utf-8")
    out = tmp_path / "long.png"
    assert run(md, "-f", "png", "-o", out, "-q", "--scale", "1", "--png-width", "800") == 0
    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(out).convert("L")
    assert im.height > 17000  # beyond Chromium's 16384 px single-capture limit
    top = im.crop((0, 0, im.width, 300))
    for y in (8192, 16384):
        assert ImageChops.difference(top, im.crop((0, y, im.width, y + 300))).getbbox() is not None


def test_java_backend_matches_when_available(tmp_path):
    from md2doc import puml

    if not (puml.find_java() and puml.find_jar()):
        pytest.skip("Java or the PlantUML jar is not installed (md2doc setup --java)")
    out = tmp_path / "j.pdf"
    assert run(SAMPLE, "-o", out, "-q", "--plantuml", "java") == 0
    assert out.stat().st_size > 10_000


def test_font_file_import(tmp_path):
    from md2doc import paths

    font = paths.FONTS_DIR / "SourceSerif4-Regular.ttf"
    out = tmp_path / "f.pdf"
    assert run(SAMPLE, "-o", out, "-q", "--font-file", font, "--font", "Source Serif 4") == 0
    from pypdf import PdfReader

    fonts = {f.get("/BaseFont", "") for p in PdfReader(str(out)).pages for f in (p["/Resources"].get("/Font") or {}).values() for f in [f.get_object()]}
    assert any("SourceSerif4" in str(f) for f in fonts)
