"""Regression tests for issues found by the adversarial review (security + real-world robustness)."""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from PIL import Image

from md2doc import cli, cssgen, puml
from md2doc.frontmatter import front_to_overrides, split_front_matter
from md2doc.images import PLACEHOLDER_URI, ImageStager
from md2doc.job import Job
from md2doc.parser import make_formatter, parse
from md2doc.pipeline import default_output, resolve_theme
from md2doc.safepath import is_unc, resolve_within
from md2doc.theme import page_dims_mm

BS = chr(92)


# ------------------------------------------------------------------ UNC / path jail
@pytest.mark.parametrize("s", [BS * 2 + "host" + BS + "share", "//host/share", "/" + BS + "host/share", BS + "/host/share",
                               BS * 2 + "?" + BS + "C:" + BS + "x", "file-less//"[:0] + BS + BS + ".\\pipe"])
def test_every_unc_spelling_is_detected(s):
    assert is_unc(s)


def test_normal_paths_are_not_unc():
    assert not is_unc("C:" + BS + "docs" + BS + "a.png") and not is_unc("images/a.png") and not is_unc("../a.png")


def test_unc_image_bypass_is_closed_and_never_touches_the_network(tmp_path):
    s = ImageStager(tmp_path, tmp_path / "assets", cache_dir=None, warn=lambda m: None)
    t0 = time.monotonic()
    for src in ("/" + BS + "192.0.2.1/share/a.png", BS + "/192.0.2.1/share/a.png", "//192.0.2.1/share/a.png"):
        assert s.resolve(src) == PLACEHOLDER_URI
    assert time.monotonic() - t0 < 2, "an SMB connection attempt would take seconds"


def test_resolve_within_rejects_unc_and_escapes(tmp_path):
    assert resolve_within(tmp_path, "/" + BS + "host/share/x.css", jail=False) is None
    assert resolve_within(tmp_path, "../outside.css", jail=True) is None
    (tmp_path / "a.css").write_text("x")
    assert resolve_within(tmp_path, "a.css", jail=True) == (tmp_path / "a.css").resolve()


def test_plantuml_unc_include_is_rejected_fast(tmp_path):
    t0 = time.monotonic()
    _, err = puml.prepare("@startuml" + chr(10) + "!include //192.0.2.1/share/x.puml" + chr(10) + "@enduml", "", tmp_path)
    assert err and "blocked" in err and time.monotonic() - t0 < 2


def test_plantuml_include_bomb_is_budgeted(tmp_path):
    (tmp_path / "a.puml").write_text("\n".join("!include a.puml" for _ in range(3)))
    _, err = puml.prepare("@startuml" + chr(10) + "!include a.puml" + chr(10) + "@enduml", "", tmp_path)
    assert err  # depth or budget exceeded, never an unbounded expansion


def test_ssrf_guard_refuses_private_and_loopback_hosts():
    from md2doc.images import _download_public, _public_host

    assert not _public_host("127.0.0.1") and not _public_host("localhost") and not _public_host("169.254.169.254")
    assert not _public_host("192.168.1.10") and not _public_host("10.0.0.5")
    assert _download_public("http://127.0.0.1:9/x.png") is None
    assert _download_public("file:///C:/Windows/win.ini") is None


def test_decompression_bomb_gives_placeholder(tmp_path):
    big = tmp_path / "bomb.png"
    Image.new("1", (20000, 20000)).save(big)  # 400 megapixels, tiny file
    s = ImageStager(tmp_path, tmp_path / "assets", cache_dir=None, warn=lambda m: None)
    assert s.resolve("bomb.png") == PLACEHOLDER_URI


# ------------------------------------------------------------------ CSS injection
HOSTILE_FONT = "x'; } body::before{background:url(file:///C:/secret.png)} :root{--z:'"


def test_hostile_font_stack_is_neutralised():
    t = resolve_theme(Job(font=HOSTILE_FONT), {})
    css = cssgen.theme_css(t, "T")
    assert "url(" not in css and "body::before" not in css.replace("body::before{content", "")
    assert ";" not in t.fonts.body and "}" not in t.fonts.body and "(" not in t.fonts.body


def test_front_matter_font_injection_is_neutralised():
    fm, _, _ = split_front_matter("---" + chr(10) + "font: \"" + HOSTILE_FONT.replace("'", "''") + "\"" + chr(10) + "---" + chr(10))
    ov, _, _ = front_to_overrides(fm)
    css = cssgen.theme_css(resolve_theme(Job(), ov), "T")
    assert "url(" not in css


def test_unknown_page_size_is_an_error_not_css():
    with pytest.raises(ValueError, match="unknown page size"):
        resolve_theme(Job(page_size="A4; margin:20mm} body{background:url(file:///x)} @page{size:A4"), {})


def test_running_title_cannot_break_out_of_its_css_string():
    t = resolve_theme(Job(), {})
    css = cssgen.theme_css(t, "T" + chr(13) + ";}} body{x:y} /*" + chr(12) + "</style>")
    top = css[css.index("@top-right{content:"):]
    assert chr(13) not in css and chr(12) not in css and "<" not in top.split("}")[0]


def test_tabloid_and_custom_sizes_are_real_page_sizes():
    assert page_dims_mm("Tabloid") == (279.4, 431.8)
    assert page_dims_mm("210mm 297mm") == (210, 297)
    css = cssgen.theme_css(resolve_theme(Job(page_size="Tabloid"), {}), "T")
    assert "@page{size:279.4mm 431.8mm" in css
    css = cssgen.theme_css(resolve_theme(Job(page_size="210mm 297mm", orientation="landscape"), {}), "T")
    assert "@page{size:297mm 210mm" in css


def test_small_margins_drop_margin_boxes_that_would_overprint():
    css = cssgen.theme_css(resolve_theme(Job(margin="2"), {}), "Title")
    assert "@bottom-center{content:'" not in css


# ------------------------------------------------------------------ front matter
def test_yaml_alias_bomb_is_rejected_quickly():
    bomb = "---" + chr(10) + "a: &a [x,x,x,x,x,x,x,x,x,x]" + chr(10) + "b: &b [*a,*a,*a,*a,*a,*a,*a,*a,*a,*a]" + chr(10) + "c: &c [*b,*b,*b,*b,*b,*b,*b,*b,*b,*b]" + chr(10) + "---" + chr(10) + "# t" + chr(10)
    t0 = time.monotonic()
    fm, body, warn = split_front_matter(bomb)
    assert fm == {} and warn and "alias" in warn[0].lower() and time.monotonic() - t0 < 1


def test_bad_colours_in_front_matter_warn_instead_of_crashing():
    ov, _, warn = front_to_overrides({"accent": "red", "tone": {"seed": "nope"}, "font": "Georgia"})
    assert "accent" not in ov and "tone" not in ov and len(warn) == 2 and "fonts" in ov


def test_bad_cli_colour_is_a_clear_error():
    with pytest.raises(ValueError, match="--accent"):
        Job(accent="notacolor").overrides()


# ------------------------------------------------------------------ parser
def test_deeply_nested_lists_do_not_swallow_the_document():
    src = "".join("  " * i + "- item" + str(i) + chr(10) for i in range(12)) + chr(10) + "TRAILING" + chr(10)
    doc = parse(src, html_mode="safe", resolve_image=lambda s: s, formatter=make_formatter())
    assert "TRAILING" in doc.html and "item11" in doc.html


def test_rtl_blocks_get_auto_direction_and_math_headings_get_ids():
    doc = parse("# $x^2$" + chr(10) + chr(10) + "\u05e9\u05dc\u05d5\u05dd \u05e2\u05d5\u05dc\u05dd" + chr(10),
                html_mode="safe", resolve_image=lambda s: s, formatter=make_formatter())
    assert 'dir="auto"' in doc.html
    assert doc.headings and doc.headings[0][1] and doc.headings[0][2] == "x^2"


# ------------------------------------------------------------------ output path rules
def test_output_path_rules(tmp_path):
    md = tmp_path / "a.md"
    md.write_text("# x")
    with pytest.raises(ValueError, match="must end with .pdf"):
        default_output(Job(input=md, output=md, format="pdf"))  # the classic mistake: -o notes.md
    pdf_in = tmp_path / "weird.pdf"
    pdf_in.write_text("# not really a pdf")
    with pytest.raises(ValueError, match="overwrite"):
        default_output(Job(input=pdf_in, output=pdf_in, format="pdf"))
    with pytest.raises(ValueError, match="must end with .pdf"):
        default_output(Job(input=md, output=tmp_path / "a.txt", format="pdf"))
    (tmp_path / "newdir").mkdir()
    assert default_output(Job(input=md, output=tmp_path / "newdir", format="png")).name == "a.png"
    assert default_output(Job(input=md, output=tmp_path / "x", format="pdf")).name == "x.pdf"
    assert default_output(Job(input=md, format="pdf")) == md.with_suffix(".pdf")


def test_cli_usage_errors_do_not_collide_with_strict_exit_code(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["--no-such-flag"])
    assert e.value.code == cli.EXIT_USAGE != cli.EXIT_STRICT


def test_toc_flag_no_longer_swallows_the_input_path():
    a = cli.build_parser().parse_args(["--toc", "notes.md"])
    assert a.toc and a.input == Path("notes.md") and a.toc_depth == 3


def test_utf16_and_cp1252_inputs_are_read(tmp_path):
    from md2doc.pipeline import _read_text

    (tmp_path / "u16.md").write_bytes("# h\u00e9llo".encode("utf-16"))
    (tmp_path / "w.md").write_bytes("# caf\u00e9".encode("cp1252"))
    assert _read_text(tmp_path / "u16.md") == "# h\u00e9llo" and _read_text(tmp_path / "w.md") == "# caf\u00e9"


# ------------------------------------------------------------------ browser-level
ROOT = Path(__file__).resolve().parents[1]
bro = pytest.mark.browser


def pdf_text(path: Path) -> str:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    return "\n".join(pdf[i].get_textpage().get_text_range() for i in range(len(pdf)))


def run(*args) -> int:
    return cli.main([str(a) for a in args])


@bro
def test_document_cannot_replace_the_renderer_config_and_csp_has_no_eval(tmp_path):
    md = tmp_path / "c.md"
    md.write_text("{#md2doc-config}" + chr(10) + '{"mermaid":{"securityLevel":"loose"}}' + chr(10) + chr(10)
                  + "```mermaid" + chr(10) + "flowchart LR" + chr(10) + "  A --> B" + chr(10) + "  click A call eval(\"window.__pwn=1\")" + chr(10) + "```" + chr(10), encoding="utf-8")
    out = tmp_path / "c.pdf"
    assert run(md, "-o", out, "-q", "--keep-temp") == 0
    import glob, os, tempfile

    d = sorted(glob.glob(os.path.join(tempfile.gettempdir(), "md2doc_*")), key=os.path.getmtime)[-1]
    html = (Path(d) / "index.html").read_text(encoding="utf-8")
    assert "window.__md2docConfig=" in html and 'id="md2doc-config"' not in html.split("<main")[0]
    assert "unsafe-eval'" not in html.split("</head>")[0].replace("'wasm-unsafe-eval'", "")


@bro
def test_page_cannot_read_local_files_outside_the_work_dir(tmp_path, capsys):
    secret = tmp_path / "secret.png"
    Image.new("RGB", (50, 50), (255, 0, 0)).save(secret)
    md = tmp_path / "m.md"
    md.write_text("```mermaid" + chr(10) + "flowchart LR" + chr(10) + '  A["<img src=\'' + secret.as_uri() + '\'>"] --> B' + chr(10) + "```" + chr(10), encoding="utf-8")
    out = tmp_path / "m.pdf"
    assert run(md, "-o", out, "--untrusted") == 0
    err = capsys.readouterr().err
    from PIL import ImageChops
    import pypdfium2 as pdfium

    img = pdfium.PdfDocument(str(out))[0].render(scale=1).to_pil().convert("RGB")
    r, g, b = zip(*img.getdata())
    assert not any(rr > 240 and gg < 20 and bb < 20 for rr, gg, bb in zip(r, g, b)), "the red secret image leaked into the PDF"
    assert "blocked" in err.lower() or "secret.png" not in err


@bro
def test_tabloid_and_custom_page_sizes_reach_the_pdf(tmp_path):
    from pypdf import PdfReader

    md = ROOT / "tests" / "fixtures" / "hostile.md"
    for size, wh in (("Tabloid", (792, 1224)), ("210mm 297mm", (595, 842)), ("A3", (842, 1191))):
        out = tmp_path / f"{size[:3]}.pdf"
        assert run(md, "-o", out, "-q", "--page-size", size) == 0
        box = PdfReader(str(out)).pages[0].mediabox
        assert abs(float(box.width) - wh[0]) < 3 and abs(float(box.height) - wh[1]) < 3, size


@bro
def test_heading_numbers_restart_per_section(tmp_path):
    md = tmp_path / "n.md"
    md.write_text("# Alpha\n\n## A one\n\n### A one x\n\n## A two\n\n# Beta\n\n## B one\n\n### B one x\n", encoding="utf-8")
    out = tmp_path / "n.pdf"
    assert run(md, "-o", out, "-q", "--numbered") == 0
    t = pdf_text(out)
    assert "2.1 B one" in t.replace("\r", "") and "2.1.1 B one x" in t


@bro
def test_wide_equation_is_shrunk_and_reported(tmp_path, capsys):
    md = tmp_path / "e.md"
    md.write_text("$$" + chr(10) + " + ".join(f"a_{{{i}}}" for i in range(1, 60)) + chr(10) + "$$" + chr(10), encoding="utf-8")
    assert run(md, "-o", tmp_path / "e.pdf") == 0
    assert "equation was wider than the page" in capsys.readouterr().err


@bro
def test_closed_details_are_printed_and_wide_tables_fit(tmp_path, capsys):
    cols = "| " + " | ".join(f"column {i}" for i in range(14)) + " |" + chr(10) + "|" + "---|" * 14 + chr(10) + "| " + " | ".join(f"v{i}" for i in range(14)) + " |"
    md = tmp_path / "d.md"
    md.write_text("<details><summary>More</summary>" + chr(10) + chr(10) + "hidden paragraph text" + chr(10) + chr(10) + "</details>" + chr(10) + chr(10) + cols + chr(10), encoding="utf-8")
    out = tmp_path / "d.pdf"
    assert run(md, "-o", out) == 0
    t = " ".join(pdf_text(out).split())  # headers wrap onto two lines; compare on normalised whitespace
    assert "hidden paragraph text" in t and "column 13" in t and "v13" in t  # nothing clipped


@bro
def test_refuses_to_overwrite_the_source_and_wrong_extension(tmp_path):
    md = tmp_path / "s.md"
    md.write_text("# keep me", encoding="utf-8")
    assert run(md, "-o", md, "-q") == cli.EXIT_FATAL
    assert md.read_text(encoding="utf-8") == "# keep me"
    assert run(md, "-o", tmp_path / "s.txt", "-q") == cli.EXIT_FATAL


@bro
def test_front_matter_css_injection_cannot_load_local_images(tmp_path):
    secret = tmp_path / "secret.png"
    Image.new("RGB", (200, 200), (255, 0, 0)).save(secret)
    payload = "x'; } body::before{content:'';display:block;width:300px;height:200px;background:url(" + secret.as_uri() + ")} :root{--z:'"
    md = tmp_path / "f.md"
    md.write_text('---\nfont: "' + payload.replace("'", "''").replace('"', "") + '"\n---\n# t\n', encoding="utf-8")
    out = tmp_path / "f.pdf"
    assert run(md, "-o", out, "-q", "--untrusted") == 0
    import pypdfium2 as pdfium

    img = pdfium.PdfDocument(str(out))[0].render(scale=0.5).to_pil().convert("RGB")
    assert not any(r > 240 and g < 20 and b < 20 for r, g, b in img.getdata())
