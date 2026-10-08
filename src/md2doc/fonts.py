"""Installed-font enumeration (no Qt), validation, imported-font inspection, @font-face generation."""
import ctypes, difflib
from ctypes import wintypes
from pathlib import Path

class _LOGFONTW(ctypes.Structure):
    _fields_ = [('lfHeight', wintypes.LONG), ('lfWidth', wintypes.LONG), ('lfEscapement', wintypes.LONG), ('lfOrientation', wintypes.LONG),
                ('lfWeight', wintypes.LONG), ('lfItalic', wintypes.BYTE), ('lfUnderline', wintypes.BYTE), ('lfStrikeOut', wintypes.BYTE),
                ('lfCharSet', wintypes.BYTE), ('lfOutPrecision', wintypes.BYTE), ('lfClipPrecision', wintypes.BYTE),
                ('lfQuality', wintypes.BYTE), ('lfPitchAndFamily', wintypes.BYTE), ('lfFaceName', wintypes.WCHAR * 32)]

class _ENUMLOGFONTEXW(ctypes.Structure):
    _fields_ = [('elfLogFont', _LOGFONTW), ('elfFullName', wintypes.WCHAR * 64), ('elfStyle', wintypes.WCHAR * 32), ('elfScript', wintypes.WCHAR * 32)]

_PROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.POINTER(_ENUMLOGFONTEXW), ctypes.c_void_p, wintypes.DWORD, wintypes.LPARAM)

def installed_families():  # system + per-user fonts, ~1.4 ms, no Qt
    names = set()
    def cb(elf, _tm, ftype, _lp):
        n = elf.contents.elfLogFont.lfFaceName
        if ftype & 0x0004 and not n.startswith('@'):   # TRUETYPE_FONTTYPE; drop raster fonts and vertical '@' aliases
            names.add(n)
        return 1
    gdi32, user32 = ctypes.windll.gdi32, ctypes.windll.user32
    gdi32.EnumFontFamiliesExW.argtypes = [wintypes.HDC, ctypes.POINTER(_LOGFONTW), _PROC, wintypes.LPARAM, wintypes.DWORD]
    user32.GetDC.argtypes, user32.GetDC.restype = [wintypes.HWND], wintypes.HDC   # REQUIRED: else OverflowError on ReleaseDC
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    hdc = user32.GetDC(None)
    try:
        lf = _LOGFONTW(); lf.lfCharSet = 1             # DEFAULT_CHARSET = all scripts
        keep = _PROC(cb)                               # keep a reference alive during the call
        gdi32.EnumFontFamiliesExW(hdc, ctypes.byref(lf), keep, 0, 0)
    finally:
        user32.ReleaseDC(None, hdc)
    return names

def first_family(stack): return stack.split(',')[0].strip().strip('"' + chr(39))

def validate_font(stack, extra=frozenset()):  # CLI: --font 'Segoe UI' -> (found, suggestions). extra = bundled + imported families
    fam = first_family(stack)
    if fam.lower() in {'serif', 'sans-serif', 'monospace', 'system-ui', 'ui-monospace', 'cursive', 'fantasy'}: return True, []
    pool = installed_families() | set(extra)
    if fam.lower() in {p.lower() for p in pool}: return True, []
    return False, difflib.get_close_matches(fam, list(pool), n=5, cutoff=0.6)   # 'Seoge UI' -> ['Segoe UI', ...]

def inspect_font(path, number=0):  # imported file -> metadata + warnings (fontTools; lazy table loading)
    from fontTools.ttLib import TTFont
    path = Path(path)
    f = TTFont(str(path), fontNumber=number, lazy=True)
    try:
        os2 = f['OS/2']; name = f['name']
        axes = {a.axisTag: (a.minValue, a.defaultValue, a.maxValue) for a in f['fvar'].axes} if 'fvar' in f else {}
        info = dict(family=name.getBestFamilyName() or path.stem, style=name.getBestSubFamilyName() or 'Regular',
                    weight=os2.usWeightClass, italic=bool(os2.fsSelection & 1), axes=axes, flavor=f.flavor,
                    cff=('CFF ' in f or 'CFF2' in f), embeddable=not (os2.fsType & 0x0002), warnings=[])
        w = info['warnings']
        if path.suffix.lower() in ('.ttc', '.otc'): w.append('collection: extract one face; @font-face cannot pick a sub-font')
        if axes: w.append('variable font: renders fine, but the PDF embeds Type3 outlines')
        if f.flavor: w.append(f'{f.flavor}: PDF embeds Type3; convert to .ttf (fonttools[woff] -> brotli) before use')
        if info['cff']: w.append('CFF outlines (.otf): PDF embeds Type3; prefer glyf .ttf')
        if not info['embeddable']: w.append('fsType restricted licence: PDF embeds Type3')
        return info
    finally:
        f.close()

def font_face_css(faces):  # faces: [{family, file, weight='400' | '100 900', style='normal'|'italic', variable=False}]
    out = []
    for f in faces:
        url = Path(f['file']).resolve().as_uri()       # file:///D:/.../Inter-Regular.ttf ('[' -> %5B, spaces -> %20)
        ext = url.rsplit('.', 1)[-1].lower()
        fmt = {'ttf': 'truetype', 'otf': 'opentype', 'woff': 'woff', 'woff2': 'woff2'}[ext] + ('-variations' if f.get('variable') else '')
        out.append(f"@font-face{{font-family:'{f['family']}';src:url('{url}') format('{fmt}');font-weight:{f.get('weight', '400')};font-style:{f.get('style', 'normal')};font-display:block}}")
    return chr(10).join(out)
# Bundled faces: 4 per family (400 normal, 400 italic, 700 normal, 700 italic). Self-contained HTML export: swap file:// url for base64 data URI.
