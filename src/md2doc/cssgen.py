"""Theme -> CSS custom properties, literal @page block, and a scoped Pygments stylesheet."""
from pygments.formatters import HtmlFormatter
from pygments.style import Style
from pygments.token import Token, Comment, Keyword, Name, String, Number, Operator, Punctuation, Generic, Error, Literal as Lit
from .theme import Theme, page_dims_mm

GENERIC = ('serif', 'sans-serif', 'monospace', 'system-ui', 'ui-monospace')
FONT_TAIL = "'Segoe UI Emoji', 'Segoe UI Symbol', 'Noto Color Emoji', 'Apple Color Emoji'"
PAPER = {'A3': 'A3', 'A4': 'A4', 'A5': 'A5', 'B5': 'B5', 'LETTER': 'Letter', 'LEGAL': 'legal', 'TABLOID': '11in 17in'}
PAPER_MM = {'A3': (297, 420), 'A4': (210, 297), 'A5': (148, 210), 'B5': (176, 250), 'LETTER': (215.9, 279.4), 'LEGAL': (215.9, 355.6), 'TABLOID': (279.4, 431.8)}

def with_tail(stack):  # user stack + emoji fallbacks + the user's generic (Chromium default for unknown names is Times New Roman)
    parts = [p.strip() for p in stack.split(',') if p.strip()]
    generic = parts.pop() if parts and parts[-1].lower() in GENERIC else 'sans-serif'
    return ', '.join(parts + [FONT_TAIL, generic])

def css_str(s):  # CSS string literal for the running title
    bs = chr(92)
    s = ''.join(' ' if ch in '\r\n\f\u2028\u2029\x00' else ch for ch in s)
    return "'" + s.replace(bs, bs + bs).replace("'", bs + "'").replace('<', bs + '3c ') + "'"

def theme_css(t: Theme, title=None):
    c, f, L = t.colors, t.fonts, t.layout
    pg = L.page
    v = {
        '--scheme': t.mode, '--page-bg': c.page_bg, '--text': c.text, '--text-muted': c.text_muted, '--heading': c.heading,
        '--link': c.link, '--accent': c.accent, '--on-accent': c.on_accent, '--border': c.border, '--code-bg': c.code_bg,
        '--code-fg': c.code_fg, '--inline-code-bg': c.inline_code_bg, '--inline-code-fg': c.inline_code_fg or c.code_fg,
        '--quote-bar': c.quote_bar, '--quote-bg': c.quote_bg, '--th-bg': c.table_head_bg, '--th-fg': c.table_head_fg or c.text,
        '--stripe': c.table_stripe, '--selection': c.selection,
        '--font-body': with_tail(f.body), '--font-heading': with_tail(f.heading or f.body), '--font-mono': with_tail(f.mono),
        '--font-size': f'{f.size_pt}pt', '--line-height': f.line_height, '--body-weight': f.body_weight,
        '--heading-weight': f.heading_weight, '--ls-body': f'{f.letter_spacing_em}em', '--ls-heading': f'{f.heading_letter_spacing_em}em',
        '--code-scale': f.code_scale, '--para-gap': f'{pg.paragraph_gap_em}em', '--radius': f'{t.code.radius_px}px',
        '--content-max': f'{L.content_max_px}px', '--png-width': f'{L.png.width_px}px', '--png-pad': f'{L.png.padding_px}px',
        '--h-rule': '1px' if L.heading_rules else '0px',
        '--justify': 'justify' if pg.justify else 'start', '--hyphens': 'auto' if pg.hyphenate else 'manual',
    }
    for i, e in enumerate([3, 2, 1, 0, -0.5, -0.75], 1):
        v[f'--h{i}'] = f'{f.heading_scale ** e:.3f}em'
    for k, a in c.admonition.items():
        v[f'--adm-{k}-bar'], v[f'--adm-{k}-bg'], v[f'--adm-{k}-title'] = a.bar, a.bg, a.title
    for i, d in enumerate(t.diagram.palette):
        v[f'--dg{i}-fill'], v[f'--dg{i}-border'], v[f'--dg{i}-text'] = d.fill, d.border, d.text
    w, h = page_dims_mm(pg.size)
    v['--page-h'] = f"{(w if pg.orientation == 'landscape' else h):g}mm"
    root = ':root{' + ';'.join(f'{k}:{val}' for k, val in v.items()) + '}'
    boxes = ''
    top_mm, _r, bottom_mm, _l = pg.margin_mm
    if pg.footer.page_numbers and bottom_mm >= 10:  # margin boxes need room
        txt = pg.footer.format.replace('{page}', "' counter(page) '").replace('{pages}', "' counter(pages) '")
        boxes += f"@bottom-center{{content:'{txt}';font-family:var(--font-body);font-size:8.5pt;color:var(--text-muted)}}"
    if pg.footer.show_title and title and top_mm >= 10:
        boxes += f'@top-right{{content:{css_str(title)};font-family:var(--font-body);font-size:8.5pt;color:var(--text-muted)}}'
    m = ' '.join(f'{x:g}mm' for x in pg.margin_mm)
    pw_mm, ph_mm = page_dims_mm(pg.size)
    if pg.orientation == 'landscape':
        pw_mm, ph_mm = ph_mm, pw_mm
    page = (f'@page{{size:{pw_mm:g}mm {ph_mm:g}mm;margin:{m};background:var(--page-bg);{boxes}}}'
            '@page:first{@top-right{content:none}}'
            '@page cover{margin:0;@top-right{content:none}@bottom-center{content:none}}')
    # multicol ONLY when needed: a multicol ancestor disables the named-page (cover) feature
    cols = f'@media print{{.content{{columns:{pg.columns};column-gap:{pg.column_gap_mm:g}mm}}}}' if pg.columns > 1 else ''
    return root + chr(10) + page + chr(10) + cols

# HTML skeleton: <html lang=.. data-mode='pdf|preview|png' data-table='zebra|grid|booktabs' [data-numbered]>
#   <head> <style>@font-face...</style> <style>theme_css</style> <style>BASE_CSS</style> <style>pygments_css</style> <style>user css</style> </head>
#   <body> <section class='cover'>..</section>  <nav class='toc'>..</nav>  <main class='content'>..</main> </body>
# (cover and toc OUTSIDE main.content.)  PNG: screen media + data-mode=png; PDF: print media.



def printable_mm(t: Theme) -> tuple[float, float]:
    """Printable content box (width, height) in mm for the theme's page size / orientation / margins."""
    pg = t.layout.page
    w, h = page_dims_mm(pg.size)
    if pg.orientation == 'landscape':
        w, h = h, w
    top, right, bottom, left = pg.margin_mm
    return w - left - right, h - top - bottom


def printable_px(t: Theme) -> tuple[int, int]:
    w, h = printable_mm(t)
    return round(w / 25.4 * 96), round(h / 25.4 * 96)


def pygments_css(t, scope='.highlight'):
    c = t.colors
    if t.code.pygments_style:
        style = t.code.pygments_style          # e.g. 'nord', 'dracula', 'github-dark'; Style.background_color holds its bg
    else:
        k = t.code.tokens
        styles = {Token: c.code_fg, Comment: f"italic {k['comment']}", Keyword: f"bold {k['keyword']}", Keyword.Type: k['type'],
                  Name.Builtin: k['builtin'], Name.Function: k['function'], Name.Class: f"bold {k['type']}",
                  Name.Decorator: k['function'], Name.Tag: k['tag'], Name.Attribute: k['attr'], Name.Constant: k['number'],
                  Name.Exception: k['type'], String: k['string'], Number: k['number'], Lit.Number: k['number'],
                  Operator: c.text_muted, Operator.Word: f"bold {k['keyword']}", Punctuation: c.text_muted,
                  Generic.Deleted: k['tag'], Generic.Inserted: k['string'], Generic.Heading: f"bold {k['function']}",
                  Generic.Emph: 'italic', Generic.Strong: 'bold', Error: f"border:{k['tag']}"}
        style = type('ThemeStyle', (Style,), {'background_color': c.code_bg, 'styles': styles})
    css = HtmlFormatter(style=style, cssclass='highlight', nobackground=True).get_style_defs(scope)
    # drop unscoped 'pre{line-height:125%}' etc. (unlayered, would beat @layer base)
    keep = [ln for ln in css.splitlines() if ln.startswith(scope) or (t.code.line_numbers and 'linenos' in ln)]
    return chr(10).join(keep)
# markdown renderer must emit: <div class='highlight'><pre><code>..</code></pre></div>  (HtmlFormatter(cssclass='highlight', nobackground=True, wrapcode=True))


