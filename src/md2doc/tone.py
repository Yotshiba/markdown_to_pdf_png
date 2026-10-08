"""Zero-dependency OKLCH colour-tone engine (seed colour -> full palette, WCAG-checked)."""
import math

def _lin(c): return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
def _gam(c): return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
def _cbrt(x): return math.copysign(abs(x) ** (1 / 3), x)

def hex_to_rgb(h):
    h = h.lstrip('#')
    if len(h) in (3, 4): h = ''.join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

def rgb_to_hex(rgb): return '#%02x%02x%02x' % tuple(round(min(1, max(0, c)) * 255) for c in rgb)

def to_oklch(hx):
    r, g, b = (_lin(c) for c in hex_to_rgb(hx))
    l = _cbrt(0.4122214708*r + 0.5363325363*g + 0.0514459929*b)
    m = _cbrt(0.2119034982*r + 0.6806995451*g + 0.1073969566*b)
    s = _cbrt(0.0883024619*r + 0.2817188376*g + 0.6299787005*b)
    L = 0.2104542553*l + 0.7936177850*m - 0.0040720468*s
    a = 1.9779984951*l - 2.4285922050*m + 0.4505937099*s
    bb = 0.0259040371*l + 0.7827717662*m - 0.8086757660*s
    return L, math.hypot(a, bb), math.degrees(math.atan2(bb, a)) % 360

def _to_lin_rgb(L, a, b):
    l = (L + 0.3963377774*a + 0.2158037573*b) ** 3
    m = (L - 0.1055613458*a - 0.0638541728*b) ** 3
    s = (L - 0.0894841775*a - 1.2914855480*b) ** 3
    return (4.0767416621*l - 3.3077115913*m + 0.2309699292*s,
            -1.2684380046*l + 2.6097574011*m - 0.3413193965*s,
            -0.0041960863*l - 0.7034186147*m + 1.7076147010*s)

def oklch_to_hex(L, C, h):  # out of gamut -> reduce chroma, keep lightness and hue
    L = min(1.0, max(0.0, L)); hr = math.radians(h)
    def ok(c):
        rgb = _to_lin_rgb(L, c * math.cos(hr), c * math.sin(hr))
        return all(-1e-4 <= v <= 1 + 1e-4 for v in rgb), rgb
    good, rgb = ok(C)
    if not good:
        lo, hi = 0.0, C
        for _ in range(24):
            mid = (lo + hi) / 2
            if ok(mid)[0]: lo = mid
            else: hi = mid
        rgb = ok(lo)[1]
    return rgb_to_hex(tuple(_gam(min(1, max(0, v))) for v in rgb))

def luminance(hx):
    r, g, b = (_lin(c) for c in hex_to_rgb(hx))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def contrast(a, b):  # WCAG 2.x ratio
    la, lb = luminance(a), luminance(b)
    if la < lb: la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)

def mix(a, b, t):  # perceptual mix in OKLab, t=0 -> a, t=1 -> b
    def lab(x):
        L, C, h = to_oklch(x); return L, C * math.cos(math.radians(h)), C * math.sin(math.radians(h))
    A, B = lab(a), lab(b)
    L, p, q = (A[i] + (B[i] - A[i]) * t for i in range(3))
    return oklch_to_hex(L, math.hypot(p, q), math.degrees(math.atan2(q, p)) % 360)

def ensure_contrast(fg, bg, target):  # move fg lightness away from bg; keep hue/chroma, then desaturate
    if contrast(fg, bg) >= target: return fg
    L, C, h = to_oklch(fg)
    step = -0.004 if luminance(bg) > 0.4 else 0.004
    for k in (1.0, 0.7, 0.4, 0.0):
        l = L
        while 0 <= l <= 1:
            cand = oklch_to_hex(l, C * k, h)
            if contrast(cand, bg) >= target: return cand
            l += step
    return '#000000' if luminance(bg) > 0.4 else '#ffffff'

def _hue_lerp(a, b, t):
    d = ((b - a + 180) % 360) - 180
    return (a + d * t) % 360

SEMANTIC_HUES = dict(keyword=320, string=145, number=55, function=255, type=195, builtin=25, tag=20, attr=85)
ADMON_HUES = dict(note=250, tip=150, important=305, warning=85, caution=25)

def derive_palette(seed, mode='light', temperature=0.0, saturation=1.0, lightness=0.0, min_contrast=4.5):
    # temperature -1 (cool, hue 250) .. +1 (warm, hue 70) pulls the NEUTRALS; saturation 0..2 scales chroma;
    # lightness -1..1 shifts the page background (light 0.95..1.0, dark 0.14..0.26)
    dark = mode == 'dark'
    L0, C0, h0 = to_oklch(seed)
    k = min(C0 / 0.15, 1.0) * saturation
    hn = _hue_lerp(h0, 70 if temperature > 0 else 250, abs(temperature))
    cn = min(0.04, 0.004 + 0.022 * k + 0.012 * abs(temperature))
    Lbg = 0.20 + 0.06 * lightness if dark else 0.975 + 0.025 * lightness
    sgn = 1 if dark else -1
    N = lambda dL: oklch_to_hex(Lbg + sgn * dL, cn, hn)
    bg = oklch_to_hex(Lbg, cn * 0.6, hn)
    code_bg, stripe, head_bg, border = N(0.035), N(0.02), N(0.06), N(0.13)
    text = ensure_contrast(oklch_to_hex(0.93 if dark else 0.24, cn, hn), bg, max(7.0, min_contrast))
    muted = ensure_contrast(oklch_to_hex(0.74 if dark else 0.50, cn, hn), head_bg, min_contrast)
    ac = min(max(C0 * saturation, 0.04), 0.30)
    accent = oklch_to_hex(max(0.45, min(0.80, L0)), ac, h0)
    link = ensure_contrast(accent, bg, min_contrast)
    heading = ensure_contrast(oklch_to_hex(0.88 if dark else 0.28, min(0.07, 0.4 * ac), h0), bg, 7.0)
    p = dict(page_bg=bg, text=text, text_muted=muted, heading=heading, link=link, accent=accent, border=border,
             code_bg=code_bg, code_fg=text, inline_code_bg=head_bg, inline_code_fg=text, quote_bar=accent,
             quote_bg=mix(bg, accent, 0.10 if dark else 0.07), table_head_bg=head_bg, table_head_fg=text,
             table_stripe=stripe, selection=mix(bg, accent, 0.40 if dark else 0.28))
    p['on_accent'] = '#ffffff' if contrast('#ffffff', accent) >= contrast('#000000', accent) else '#000000'
    Lf, Lb = (0.36, 0.74) if dark else (0.90, 0.55)
    dia = []
    for i in range(8):  # 8 hues from the seed hue, pastel fill + strong border + readable text
        h = (h0 + i * 45) % 360
        fill = oklch_to_hex(Lf, 0.07 + 0.05 * min(saturation, 1.5), h)
        dia.append(dict(fill=fill, border=oklch_to_hex(Lb, 0.12 * min(saturation, 1.5) + 0.03, h),
                        text=ensure_contrast(text, fill, min_contrast)))
    p['diagram'] = dia
    code = {}
    for name, hue in SEMANTIC_HUES.items():  # fixed semantic hues, lightness solved against code_bg
        base = oklch_to_hex(0.80 if dark else 0.48, 0.13 * min(saturation, 1.5) + 0.02, hue)
        code[name] = ensure_contrast(base, code_bg, min_contrast)
    code['comment'] = ensure_contrast(muted, code_bg, min_contrast)
    p['code_tokens'] = code
    adm = {}
    for name, hue in ADMON_HUES.items():
        bar = oklch_to_hex(0.70 if dark else 0.62, 0.17, hue)
        abg = mix(bg, bar, 0.12 if dark else 0.08)
        adm[name] = dict(bar=bar, bg=abg, title=ensure_contrast(bar, abg, min_contrast))
    p['admonition'] = adm
    return p

# audit: [(fg, bg, min_ratio)] on any palette dict; derive_palette('#0969da','light') -> page_bg #f2f7ff, text #17202c, link #0969da
