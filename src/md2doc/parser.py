"""Markdown -> HTML (markdown-it-py + plugins) with math, diagram and code-highlight handling.

Contract with the in-page renderer (web/render.js):
  inline math   <span class="math inline">TEX</span>
  display math  <div class="math block|display|amsmath">TEX</div>
  Mermaid       <div class="diagram diagram-mermaid"><pre class="mermaid-src">SRC</pre></div>
  PlantUML      <div class="diagram diagram-plantuml">@@PUML:i@@</div>   (pipeline fills the sentinel)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from markdown_it import MarkdownIt
from markdown_it.common.utils import escapeHtml
from markdown_it.renderer import RendererHTML
from markdown_it.rules_block import StateBlock
from markdown_it.rules_inline import StateInline
from markdown_it.token import Token
from mdit_py_plugins.admon import admon_plugin
from mdit_py_plugins.amsmath import amsmath_plugin
from mdit_py_plugins.anchors import anchors_plugin
from mdit_py_plugins.attrs import attrs_block_plugin, attrs_plugin
from mdit_py_plugins.deflist import deflist_plugin
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.gfm_autolink import gfm_autolink_plugin
from mdit_py_plugins.subscript import sub_plugin
from mdit_py_plugins.superscript import superscript_plugin
from pygments import highlight as pyg_highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_by_name
from pygments.util import ClassNotFound

BS, NL = chr(92), chr(10)
ATTRS_OK = ["id", "class", "width", "height", "align", "title"]  # never style / on*
PUML_LANGS = {"plantuml", "puml", "uml"}
MATH_LANGS = {"math", "latex", "tex"}

# Admonition type aliases -> the five themed types
ADMON_ALIASES = {
    "info": "note", "abstract": "note", "summary": "note", "tldr": "note", "todo": "note", "example": "note",
    "quote": "note", "cite": "note", "seealso": "note", "hint": "tip", "success": "tip", "check": "tip", "done": "tip",
    "question": "important", "help": "important", "faq": "important", "attention": "warning", "failure": "caution",
    "fail": "caution", "missing": "caution", "danger": "caution", "error": "caution", "bug": "caution",
}
THEMED = {"note", "tip", "important", "warning", "caution"}

# ---- link policy: allow data:image/*, block javascript:/vbscript:/other data: -----------------------
_BAD = re.compile(r"^(vbscript|javascript|data):", re.I)
_OK_DATA = re.compile(r"^data:image/(gif|png|jpe?g|webp|svg\+xml|bmp|avif)[;,]", re.I)


def _validate_link(url: str) -> bool:
    u = url.strip()
    return bool(_OK_DATA.match(u)) if _BAD.match(u) else True


# ---- KaTeX lacks multline/flalign/eqnarray -> nearest supported environment -------------------------
_AMS = re.compile(re.escape(BS) + r"(begin|end)[{](multline|flalign|eqnarray)([*]?)[}]")
_AMS_MAP = {"multline": "gather", "flalign": "align", "eqnarray": "align"}


def _ams_renderer(content: str) -> str:
    return escapeHtml(_AMS.sub(lambda m: BS + m[1] + "{" + _AMS_MAP[m[2]] + m[3] + "}", content))


# ---- extra math delimiters: \( ... \) inline and \[ ... \] block -------------------------------------
def _math_paren(state: StateInline, silent: bool) -> bool:
    src, start = state.src, state.pos
    if not src.startswith(BS + "(", start):
        return False
    i = start + 2
    while True:
        j = src.find(BS + ")", i, state.posMax)
        if j < 0:
            return False
        k, n = j - 1, 0
        while k >= start + 2 and src[k] == BS:
            n += 1
            k -= 1
        if n % 2 == 0:
            break
        i = j + 2
    content = src[start + 2 : j]
    if not content.strip():
        return False
    if not silent:
        t = state.push("math_inline", "math", 0)
        t.content, t.markup = content, BS + "("
    state.pos = j + 2
    return True


def _math_bracket(state: StateBlock, line0: int, line_end: int, silent: bool) -> bool:
    if state.sCount[line0] - state.blkIndent >= 4:
        return False
    if not state.src.startswith(BS + "[", state.bMarks[line0] + state.tShift[line0]):
        return False
    parts, line = [], line0
    while True:
        a = state.bMarks[line] + state.tShift[line] + (2 if line == line0 else 0)
        text = state.src[a : state.eMarks[line]]
        if text.rstrip().endswith(BS + "]"):
            parts.append(text.rstrip()[:-2])
            break
        parts.append(text)
        line += 1
        if line >= line_end:
            return False
    if silent:
        return True
    t = state.push("math_block", "math", 0)
    t.block, t.markup = True, BS + "["
    t.content = NL.join(parts).strip()
    t.map = [line0, line + 1]
    state.line = line + 1
    return True


def _page_break(state: StateBlock, line0: int, line_end: int, silent: bool) -> bool:
    """A line that is exactly \\newpage or \\pagebreak."""
    if state.sCount[line0] - state.blkIndent >= 4:
        return False
    line = state.src[state.bMarks[line0] + state.tShift[line0] : state.eMarks[line0]].strip()
    if line not in (BS + "newpage", BS + "pagebreak", BS + "clearpage"):
        return False
    if not silent:
        t = state.push("page_break", "div", 0)
        t.map = [line0, line0 + 1]
        t.block = True
    state.line = line0 + 1
    return True


def _render_math_display(self, tokens, idx, options, env):  # $$x$$ inside a paragraph
    env["has_math"] = True
    return '<span class="math display">' + escapeHtml(tokens[idx].content.strip()) + "</span>"


def _render_math_inline(self, tokens, idx, options, env):
    env["has_math"] = True
    return '<span class="math inline">' + escapeHtml(tokens[idx].content) + "</span>"


def _render_math_block(self, tokens, idx, options, env):
    env["has_math"] = True
    line = tokens[idx].map[0] if tokens[idx].map else 0
    return f'<div class="math block" data-line="{line}">' + escapeHtml(tokens[idx].content) + "</div>\n"


def _render_page_break(self, tokens, idx, options, env):
    return '<div class="page-break"></div>\n'


# ---- fences ---------------------------------------------------------------------------------------
def render_fence(self, tokens, idx, options, env):
    tok = tokens[idx]
    info = (tok.info or "").strip()
    lang = (info.split(None, 1)[0] if info else "").strip("{}.").lower()
    code = tok.content
    line = tok.map[0] if tok.map else 0
    if lang == "mermaid":
        env["has_mermaid"] = True
        return (f'<div class="diagram diagram-mermaid" data-line="{line}"><pre class="mermaid-src">'
                + escapeHtml(code) + "</pre></div>\n")
    if lang in PUML_LANGS:
        env["has_plantuml"] = True
        env["plantuml"].append((line, code))
        return f'<div class="diagram diagram-plantuml" data-line="{line}">@@PUML:{len(env["plantuml"]) - 1}@@</div>\n'
    if lang in MATH_LANGS:
        env["has_math"] = True
        return f'<div class="math block" data-line="{line}">' + escapeHtml(code) + "</div>\n"
    try:
        lexer = get_lexer_by_name(lang) if lang else TextLexer()
    except ClassNotFound:
        lexer = TextLexer()
    body = pyg_highlight(code, lexer, env["formatter"])
    return f'<div class="codeblock" data-line="{line}" data-lang="{escapeHtml(lang)}">{body}</div>\n'


def render_image(self, tokens, idx, options, env):
    tok = tokens[idx]
    tok.attrSet("src", env["resolve_image"](tok.attrGet("src") or ""))
    return RendererHTML.image(self, tokens, idx, options, env)


# ---- core rules -----------------------------------------------------------------------------------
def _figure_rule(state) -> None:
    """A paragraph holding only an image becomes <figure><img><figcaption>."""
    mode = state.env.get("captions", "alt")
    toks = state.tokens
    for i in range(len(toks) - 2):
        o, inl, c = toks[i], toks[i + 1], toks[i + 2]
        if o.type != "paragraph_open" or o.hidden or inl.type != "inline" or c.type != "paragraph_close":
            continue
        kids = [k for k in (inl.children or []) if not (k.type == "softbreak" or (k.type == "text" and not k.content.strip()))]
        if len(kids) != 1 or kids[0].type != "image":
            continue
        cap = ""
        if mode != "none":
            cap = kids[0].attrGet("title") or (kids[0].content if mode == "alt" else "")
        o.tag = c.tag = "figure"
        o.attrJoin("class", "md-figure")
        if cap:
            inl.children.append(Token("html_inline", "", 0, content="<figcaption>" + escapeHtml(cap) + "</figcaption>"))


def _post_rule(state) -> None:
    """data-line on block openers, admonition normalisation, heading collection."""
    toks = state.tokens
    heads = state.env["headings"]
    for i, t in enumerate(toks):
        if t.map and t.nesting == 1 and t.type not in ("heading_open",) and t.attrGet("data-line") is None:
            t.attrSet("data-line", str(t.map[0]))
        if t.type == "heading_open":
            if t.map:
                t.attrSet("data-line", str(t.map[0]))
            inl = toks[i + 1] if i + 1 < len(toks) else None
            text = _plain(inl) if inl is not None and inl.type == "inline" else ""
            heads.append((int(t.tag[1]), t.attrGet("id") or "", text))
        elif t.type == "admonition_open":
            cls = (t.attrGet("class") or "").split()
            kind = next((c for c in cls if c != "admonition"), "note").lower()
            kind = ADMON_ALIASES.get(kind, kind)
            if kind not in THEMED:
                kind = "note"
            t.attrSet("class", f"admonition {kind}")


def _plain(inline: Token) -> str:
    out = []
    for c in inline.children or []:
        if c.type in ("text", "code_inline"):
            out.append(c.content)
        elif c.type in ("softbreak", "hardbreak"):
            out.append(" ")
    return "".join(out).strip()


def _relax_attr_values() -> None:
    """Let {width=50% .center} parse (bare values may contain %). Patches mdit-py-plugins 0.6.x internals."""
    try:
        from mdit_py_plugins.attrs import parse as _p

        bare = re.compile(r"[A-Za-z0-9_:%.-]")

        def handler(char, pos, tokens):
            if bare.fullmatch(char):
                return _p.State.SCANNING_BARE_VALUE
            if char == "}":
                tokens.append(tokens.start, pos, "value")
                return _p.State.DONE
            if char in " \t\n\r":
                tokens.append(tokens.start, pos, "value")
                return _p.State.SCANNING
            raise _p.ParseError("Unexpected character whilst scanning bare value: " + char, pos)

        _p.HANDLERS[_p.State.SCANNING_BARE_VALUE] = handler
    except Exception:  # pragma: no cover - internals changed; attrs still work with quoted values
        pass


_relax_attr_values()


def make_md(html_mode: str = "safe", *, typographer: bool = False, breaks: bool = False) -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": html_mode != "off", "typographer": typographer, "breaks": breaks, "linkify": False})
    md.enable(["table", "strikethrough"])
    if typographer:
        md.enable(["replacements", "smartquotes"])
    md.options["tasklists"] = True
    md.options["tasklists_editable"] = False
    md.options["alerts"] = True
    md.validateLink = _validate_link
    md.use(gfm_autolink_plugin)
    md.use(footnote_plugin)
    md.use(deflist_plugin)
    md.use(dollarmath_plugin, allow_space=False, allow_digits=False, double_inline=True, allow_blank_lines=False, allow_labels=False)
    md.use(amsmath_plugin, renderer=_ams_renderer)
    md.use(attrs_plugin, allowed=ATTRS_OK)
    md.use(attrs_block_plugin, allowed=ATTRS_OK)
    md.use(admon_plugin)
    md.use(sub_plugin)
    md.use(superscript_plugin)
    md.use(anchors_plugin, min_level=1, max_level=6)
    md.inline.ruler.before("escape", "math_paren", _math_paren)
    md.block.ruler.before("fence", "math_bracket", _math_bracket, {"alt": ["paragraph", "reference", "blockquote", "list"]})
    md.block.ruler.before("fence", "page_break", _page_break, {"alt": ["paragraph", "reference", "blockquote", "list"]})
    md.add_render_rule("math_inline", _render_math_inline)
    md.add_render_rule("math_inline_double", _render_math_display)
    md.add_render_rule("math_block", _render_math_block)
    md.add_render_rule("math_block_label", _render_math_block)
    md.add_render_rule("page_break", _render_page_break)
    md.add_render_rule("fence", render_fence)
    md.add_render_rule("image", render_image)
    md.core.ruler.push("figure", _figure_rule)
    md.core.ruler.push("md2doc_post", _post_rule)
    return md


@dataclass
class ParsedDoc:
    html: str
    headings: list[tuple[int, str, str]] = field(default_factory=list)
    plantuml: list[tuple[int, str]] = field(default_factory=list)
    has_math: bool = False
    has_mermaid: bool = False
    has_plantuml: bool = False


def make_formatter(*, line_numbers: bool = False) -> HtmlFormatter:
    return HtmlFormatter(cssclass="highlight", wrapcode=True, nobackground=True, linenos="inline" if line_numbers else False)


def parse(
    text: str,
    *,
    html_mode: str,
    resolve_image: Callable[[str], str],
    formatter: HtmlFormatter,
    captions: str = "alt",
    typographer: bool = False,
    breaks: bool = False,
) -> ParsedDoc:
    md = make_md(html_mode, typographer=typographer, breaks=breaks)
    env = {
        "resolve_image": resolve_image, "formatter": formatter, "captions": captions,
        "headings": [], "plantuml": [], "has_math": False, "has_mermaid": False, "has_plantuml": False,
    }
    tokens = md.parse(text, env)
    html = md.renderer.render(tokens, md.options, env)
    # math tokens produced by plugins that bypass our render rules still need the flag
    has_math = env["has_math"] or any(t.type.startswith("math") or t.type == "amsmath" for t in tokens)
    return ParsedDoc(html, env["headings"], env["plantuml"], has_math, env["has_mermaid"], env["has_plantuml"])
