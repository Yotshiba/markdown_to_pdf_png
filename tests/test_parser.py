from __future__ import annotations

from md2doc.frontmatter import split_front_matter
from md2doc.parser import make_formatter, parse
from md2doc.sanitize import sanitize


def render(src: str, mode: str = "safe", **kw):
    doc = parse(src, html_mode=mode, resolve_image=lambda s: "file:///X/" + s, formatter=make_formatter(), **kw)
    html = sanitize(doc.html, lambda s: s) if mode == "safe" else doc.html
    return doc, html


BS = chr(92)


def test_math_delimiters_and_currency():
    doc, html = render(f"Inline $a_1^2$ and {BS}(b{BS}) and cost $5 and $10. Display $$x^2$$ here.")
    assert doc.has_math
    assert '<span class="math inline">a_1^2</span>' in html
    assert '<span class="math inline">b</span>' in html
    assert "$5 and $10" in html  # currency is not math
    assert '<span class="math display">x^2</span>' in html  # no <div> inside <p>


def test_display_and_ams_math():
    _, html = render(f"$$\n{BS}int_0^1 x\n$$\n\n{BS}begin{{align}}a&=b{BS}{BS}c&=d{BS}end{{align}}\n")
    assert 'class="math block"' in html
    assert 'class="math amsmath"' in html


def test_unsupported_ams_env_is_mapped():
    _, html = render(f"{BS}begin{{multline}}a{BS}{BS}b{BS}end{{multline}}\n")
    assert "gather" in html and "multline" not in html


def test_diagram_fences_become_placeholders():
    doc, html = render("```mermaid\ngraph TD; A-->B\n```\n\n```plantuml\nA -> B\n```\n")
    assert doc.has_mermaid and doc.has_plantuml
    assert '<pre class="mermaid-src">' in html and "A--&gt;B" in html
    assert "@@PUML:0@@" in html and doc.plantuml[0][1].strip() == "A -> B"


def test_code_is_highlighted():
    _, html = render("```python\ndef f(): pass\n```\n")
    assert 'class="highlight"' in html and '<span class="k">def</span>' in html


def test_image_attrs_caption_and_figure():
    _, html = render('![A cat](cat.png "Title cap"){width=50% .center}\n')
    assert "<figure" in html and 'width="50%"' in html and "<figcaption>Title cap</figcaption>" in html
    assert 'src="file:///X/cat.png"' in html


def test_captions_none():
    _, html = render("![alt](a.png)\n", captions="none")
    assert "<figcaption>" not in html


def test_admonition_aliases_and_alerts():
    _, html = render("!!! danger \"Boom\"\n    text\n\n> [!WARNING]\n> careful\n")
    assert 'class="admonition caution"' in html
    assert "markdown-alert-warning" in html


def test_page_break_and_task_list_and_footnote():
    _, html = render("a\n\n" + BS + "newpage\n\n- [x] done[^1]\n\n[^1]: note\n")
    assert 'class="page-break"' in html
    assert "task-list-item-checkbox" in html
    assert 'class="footnotes"' in html


def test_headings_are_collected_with_ids():
    doc, _ = render("# One\n\n## Two *x*\n")
    assert doc.headings == [(1, "one", "One"), (2, "two-x", "Two x")]


def test_data_line_attributes():
    _, html = render("# H\n\ntext\n\n- a\n")
    assert 'data-line="0"' in html and 'data-line="2"' in html


def test_sanitizer_removes_active_content():
    src = ('<script>alert(1)</script><img src="x.png" onerror="alert(1)"><a href="javascript:alert(1)">c</a>'
           '<iframe src="file:///C:/Windows/win.ini"></iframe><div style="position:fixed;top:0">o</div>')
    _, html = render(src)
    for bad in ("<script", "onerror", "javascript:", "<iframe", "position"):
        assert bad not in html
    assert "<div>o</div>" in html


def test_html_off_escapes_raw_html():
    _, html = render("<b>x</b>\n", mode="off")
    assert "<b>" not in html


def test_front_matter_keeps_line_numbers():
    fm, body, warn = split_front_matter("---\ntitle: T\ntoc: 2\n---\n# H\n")
    assert fm == {"title": "T", "toc": 2} and not warn
    assert body.count("\n") == "---\ntitle: T\ntoc: 2\n---\n# H\n".count("\n")
    assert body.splitlines()[4] == "# H"


def test_bad_front_matter_is_a_warning_not_an_error():
    fm, body, warn = split_front_matter("---\n: : [\n---\ntext\n")
    assert fm == {} and warn and "text" in body
