"""Theme data model, layered resolution (CLI > front matter > saved > preset) and contrast audit."""
import copy
import re
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator
from . import tone

Hex = Annotated[str, StringConstraints(pattern=r'^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')]
Slug = Annotated[str, StringConstraints(pattern=r'^[a-z0-9][a-z0-9-]{0,47}$')]

PAPER_MM = {'A3': (297, 420), 'A4': (210, 297), 'A5': (148, 210), 'B5': (176, 250), 'LETTER': (215.9, 279.4),
            'LEGAL': (215.9, 355.6), 'TABLOID': (279.4, 431.8)}
_TO_MM = {'mm': 1.0, 'cm': 10.0, 'in': 25.4, 'pt': 25.4 / 72, 'px': 25.4 / 96}
_DIMS = re.compile(r'^\s*(\d+(?:\.\d+)?)\s*(mm|cm|in|pt|px)?\s*(?:x|X|\s)\s*(\d+(?:\.\d+)?)\s*(mm|cm|in|pt|px)?\s*$')


def page_dims_mm(size: str) -> tuple[float, float]:
    """(width, height) in mm, portrait. Accepts a paper name or two lengths like '210mm 297mm' / '8.5inx11in'."""
    s = str(size).strip()
    if s.upper() in PAPER_MM:
        return PAPER_MM[s.upper()]
    m = _DIMS.match(s)
    if m:
        w = float(m.group(1)) * _TO_MM[m.group(2) or 'mm']
        h = float(m.group(3)) * _TO_MM[m.group(4) or m.group(2) or 'mm']
        if 50 <= w <= 2000 and 50 <= h <= 2000:
            return w, h
    raise ValueError(f"unknown page size {size!r}: use {', '.join(n.title() for n in PAPER_MM)} or e.g. '210mm 297mm'")


# anything that could end a CSS declaration or string is dropped from user-supplied font stacks
_FONT_BAD = re.compile(r"[^A-Za-z0-9 ,'\".\u00A0-\u2027\u202A-\uFFFF_-]")


def clean_font_stack(v):
    if v is None:
        return None
    s = _FONT_BAD.sub('', str(v))
    for q in ('"', "'"):
        if s.count(q) % 2:
            s = s.replace(q, '')
    return s.strip()[:200] or 'sans-serif'


class _M(BaseModel):
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

class Admonition(_M):
    bar: Hex; bg: Hex; title: Hex

class Colors(_M):
    page_bg: Hex; text: Hex; text_muted: Hex; heading: Hex; link: Hex; accent: Hex; border: Hex
    code_bg: Hex; code_fg: Hex; inline_code_bg: Hex; inline_code_fg: Hex | None = None
    quote_bar: Hex; quote_bg: Hex; table_head_bg: Hex; table_head_fg: Hex | None = None
    table_stripe: Hex; selection: Hex; on_accent: Hex = '#ffffff'
    admonition: dict[Literal['note', 'tip', 'important', 'warning', 'caution'], Admonition] = {}

class Fonts(_M):  # CSS font-family lists; single quotes inside JSON keep files readable
    body: str = "'Segoe UI', system-ui, sans-serif"
    heading: str | None = None               # None -> body
    mono: str = "'Cascadia Mono', Consolas, monospace"
    size_pt: float = Field(11, ge=6, le=36)
    line_height: float = Field(1.6, ge=1.0, le=3.0)
    heading_scale: float = Field(1.25, ge=1.0, le=1.6)   # h1..h6 = scale ** [3,2,1,0,-0.5,-0.75]
    heading_weight: int = Field(700, ge=100, le=900)
    body_weight: int = Field(400, ge=100, le=900)
    letter_spacing_em: float = Field(0.0, ge=-0.05, le=0.2)
    heading_letter_spacing_em: float = Field(0.0, ge=-0.05, le=0.2)
    code_scale: float = Field(0.9, ge=0.6, le=1.2)

    @field_validator('body', 'heading', 'mono', mode='before')
    @classmethod
    def _clean_stack(cls, v):
        return clean_font_stack(v)


class Footer(_M):
    page_numbers: bool = True
    format: str = 'Page {page} of {pages}'
    show_title: bool = True

class PageLayout(_M):
    size: str = 'A4'                         # A3 A4 A5 B5 Letter Legal Tabloid or '210mm 297mm'
    orientation: Literal['portrait', 'landscape'] = 'portrait'
    margin_mm: tuple[float, float, float, float] = (22, 20, 24, 20)   # top right bottom left
    columns: int = Field(1, ge=1, le=3)
    column_gap_mm: float = Field(8, ge=0, le=30)
    justify: bool = False
    hyphenate: bool = False
    paragraph_gap_em: float = Field(0.9, ge=0, le=3)
    footer: Footer = Footer()

    @field_validator('size')
    @classmethod
    def _check_size(cls, v):
        page_dims_mm(v)
        return v


class PngLayout(_M):
    width_px: int = Field(900, ge=320, le=4000)
    padding_px: int = Field(48, ge=0, le=300)
    scale: float = Field(2.0, ge=1, le=4)    # device_scale_factor
    transparent: bool = False

class Layout(_M):
    content_max_px: int = Field(860, ge=360, le=2400)   # preview only
    page: PageLayout = PageLayout()
    png: PngLayout = PngLayout()
    heading_rules: bool = True
    heading_numbers: bool = False
    table_style: Literal['grid', 'booktabs', 'zebra'] = 'zebra'

class Code(_M):
    pygments_style: str | None = None        # named style (nord, dracula, github-dark...) or None -> build from tokens
    tokens: dict[Literal['keyword', 'string', 'number', 'function', 'type', 'builtin', 'tag', 'attr', 'comment'], Hex] = {}
    radius_px: float = 6
    line_numbers: bool = False

class DiagramColor(_M):
    fill: Hex; border: Hex; text: Hex

class Diagram(_M):
    palette: list[DiagramColor] = Field(default_factory=list, max_length=12)
    line: Hex | None = None
    note_bg: Hex | None = None
    font: str | None = None                  # None -> fonts.body
    font_size_px: int = Field(15, ge=8, le=32)
    mermaid: dict[str, str | int | bool] = {}   # raw themeVariables overrides
    plantuml: dict[str, str] = {}               # raw skinparam overrides

    @field_validator('font', mode='before')
    @classmethod
    def _clean_font(cls, v):
        return clean_font_stack(v)


class Tone(_M):
    seed: Hex
    temperature: float = Field(0.0, ge=-1, le=1)
    saturation: float = Field(1.0, ge=0, le=2)
    lightness: float = Field(0.0, ge=-1, le=1)
    min_contrast: float = Field(4.5, ge=3, le=7)

class Theme(_M):
    schema_version: Literal[1] = 1
    id: Slug
    name: str
    mode: Literal['light', 'dark']          # drives color-scheme and Mermaid darkMode
    tone: Tone | None = None
    colors: Colors
    fonts: Fonts = Fonts()
    layout: Layout = Layout()
    code: Code = Code()
    diagram: Diagram = Diagram()

    @model_validator(mode='after')
    def _fill(self):  # presets may omit admonition/diagram/code tokens: derive from the accent colour
        c = self.colors
        if not c.admonition or not self.diagram.palette or (not self.code.tokens and not self.code.pygments_style):
            p = tone.derive_palette(c.accent, self.mode)
            if not c.admonition: c.admonition = {k: Admonition(**v) for k, v in p['admonition'].items()}
            if not self.diagram.palette: self.diagram.palette = [DiagramColor(**d) for d in p['diagram']]
            if not self.code.tokens and not self.code.pygments_style: self.code.tokens = p['code_tokens']
        return self

# JSON Schema for editors / theme files: Theme.model_json_schema()

def deep_merge(a, b):
    out = copy.deepcopy(a)
    for k, v in b.items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out

def apply_tone(d):  # tone block present -> generate palette; explicit d['colors'] keys still win
    t = d.get('tone')
    if not t: return d
    p = tone.derive_palette(t['seed'], d['mode'], t.get('temperature', 0), t.get('saturation', 1), t.get('lightness', 0), t.get('min_contrast', 4.5))
    colors = {k: v for k, v in p.items() if isinstance(v, str)}
    colors['admonition'] = p['admonition']
    gen = {'colors': colors, 'diagram': {'palette': p['diagram']}, 'code': {'tokens': p['code_tokens']}}
    return deep_merge(gen, d)

def apply_accent(d, accent):  # front matter 'accent:' recolours accent-linked tokens only; link kept readable
    c = d['colors']; bg = c['page_bg']
    c['accent'] = accent; c['link'] = tone.ensure_contrast(accent, bg, 4.5); c['quote_bar'] = accent
    c['selection'] = tone.mix(bg, accent, 0.28 if d['mode'] == 'light' else 0.40)
    c['on_accent'] = '#ffffff' if tone.contrast('#ffffff', accent) >= tone.contrast('#000000', accent) else '#000000'
    return d

def _generate(tone_cfg: dict, mode: str) -> dict:
    """Palette-shaped dict generated from a tone block (colours, admonitions, diagram palette, code tokens)."""
    p = tone.derive_palette(tone_cfg['seed'], mode, tone_cfg.get('temperature', 0), tone_cfg.get('saturation', 1),
                            tone_cfg.get('lightness', 0), tone_cfg.get('min_contrast', 4.5))
    colors = {k: v for k, v in p.items() if isinstance(v, str)}
    colors['admonition'] = p['admonition']
    # pygments_style=None: a named code style would ignore the new palette
    return {'colors': colors, 'diagram': {'palette': p['diagram']}, 'code': {'tokens': p['code_tokens'], 'pygments_style': None}}


def resolve(preset, saved=None, front=None, cli=None):
    """precedence: CLI > front matter > saved user theme > preset.

    A layer that carries a `tone` block (or flips `mode`) REPLACES the colours of everything below it with a
    freshly generated palette; colours listed explicitly in that same layer still win over the generated ones.
    """
    d = apply_tone(copy.deepcopy(preset))
    for layer in (saved or {}, front or {}, cli or {}):
        layer = dict(layer)
        accent = layer.pop('accent', None)
        mode = layer.get('mode', d['mode'])
        tone_cfg = layer.get('tone')
        if not tone_cfg and mode != d['mode']:  # light <-> dark switch: derive a matching palette from the accent
            tone_cfg = {'seed': d['colors']['accent']}
            layer['tone'] = tone_cfg
        if tone_cfg:
            tone_cfg = {**(d.get('tone') or {}), **tone_cfg} if d.get('tone', {}) and d['tone'].get('seed') == tone_cfg.get('seed') else tone_cfg
            layer['tone'] = tone_cfg
            d = deep_merge(d, _generate(tone_cfg, mode))
        d = deep_merge(d, layer)
        if accent: d = apply_accent(d, accent)
    return Theme.model_validate(d)


def audit(t):  # non-fatal warnings shown in GUI/CLI
    c, out = t.colors, []
    def chk(name, fg, bg, need):
        r = tone.contrast(fg, bg)
        if r < need: out.append(f'{name}: {r:.2f} < {need}')
    chk('text/page_bg', c.text, c.page_bg, 7); chk('text_muted/page_bg', c.text_muted, c.page_bg, 4.5)
    chk('heading/page_bg', c.heading, c.page_bg, 4.5); chk('link/page_bg', c.link, c.page_bg, 4.5)
    chk('code_fg/code_bg', c.code_fg, c.code_bg, 4.5)
    for i, d in enumerate(t.diagram.palette): chk(f'diagram[{i}].text/fill', d.text, d.fill, 4.5)
    return out
