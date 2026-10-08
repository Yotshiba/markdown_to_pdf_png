"""YAML front matter: split it off the document and map it to theme overrides + document metadata."""
import re, datetime as dt
import yaml

_HEX = re.compile(r'#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})')
MAX_FRONT_MATTER = 65536

_FM = re.compile('\\A\\ufeff?---[ \\t]*\\r?\\n(.*?)\\r?\\n(?:---|\\.\\.\\.)[ \\t]*(?:\\r?\\n|\\Z)', re.S)
_UNITS = {'mm': 1.0, 'cm': 10.0, 'in': 25.4, 'pt': 25.4 / 72, 'px': 25.4 / 96}

def _blank_lines(m):
    return chr(10) * m.group(0).count(chr(10))


def split_front_matter(text):  # -> (dict, body, warnings)
    m = _FM.match(text)
    if not m: return {}, text, []
    try:
        if len(m.group(1)) > MAX_FRONT_MATTER:
            raise ValueError('front matter is larger than 64 KB')
        if any(isinstance(e, yaml.AliasEvent) for e in yaml.parse(m.group(1), Loader=yaml.SafeLoader)):
            raise ValueError('YAML aliases (*name) are not supported')  # alias bombs expand exponentially
        data = yaml.safe_load(m.group(1)) or {}
        if not isinstance(data, dict): raise ValueError('front matter must be a mapping')
    except Exception as e:  # bad YAML must not abort the render
        return {}, _blank_lines(m) + text[m.end():], [f'front matter ignored: {e}']
    # keep line numbers stable (scroll sync, error messages): replace the block by blank lines
    return data, _blank_lines(m) + text[m.end():], []

def mm(v):
    if isinstance(v, (int, float)): return float(v)
    n = re.fullmatch('\\s*([\\d.]+)\\s*(mm|cm|in|pt|px)?\\s*', str(v))
    if not n: raise ValueError(f'bad length {v!r}')
    return float(n.group(1)) * _UNITS[n.group(2) or 'mm']

def margins(v):  # '15mm 20mm' | [t,r,b,l] | {top,right,bottom,left}
    if isinstance(v, dict): return tuple(mm(v[k]) for k in ('top', 'right', 'bottom', 'left'))
    p = [mm(x) for x in (v if isinstance(v, (list, tuple)) else str(v).split())]
    if len(p) == 1: return (p[0],) * 4
    if len(p) == 2: return (p[0], p[1], p[0], p[1])
    if len(p) == 3: return (p[0], p[1], p[2], p[1])
    if len(p) == 4: return tuple(p)
    raise ValueError(f'margin needs 1 to 4 values, got {len(p)}')

def front_to_overrides(fm):  # -> (theme_overrides, doc_meta, warnings)
    ov, meta, warn = {}, {}, []
    for k, v in fm.items():
        try:
            if k == 'theme': ov['__theme__'] = str(v)                      # preset id or path; caller loads the base preset
            elif k == 'accent':                                              # recolour accent-linked tokens only
                if not _HEX.fullmatch(str(v).strip()): raise ValueError('needs a colour like #e91e63')
                ov['accent'] = str(v).strip()
            elif k == 'tone':                                                # full palette regeneration
                t = dict(v) if isinstance(v, dict) else {'seed': str(v)}
                if not _HEX.fullmatch(str(t.get('seed', '')).strip()): raise ValueError('tone needs a seed colour like #2e7d32')
                ov['tone'] = {a: b for a, b in t.items() if a in ('seed', 'temperature', 'saturation', 'lightness', 'min_contrast')}
            elif k == 'font':
                if isinstance(v, dict): ov.setdefault('fonts', {}).update({a: b for a, b in v.items() if a in ('body', 'heading', 'mono', 'size_pt', 'line_height')})
                else: ov.setdefault('fonts', {})['body'] = f"'{str(v).replace(chr(39), '')}', sans-serif"
            elif k == 'mono_font': ov.setdefault('fonts', {})['mono'] = f"'{str(v).replace(chr(39), '')}', monospace"
            elif k == 'font_size': ov.setdefault('fonts', {})['size_pt'] = float(v)
            elif k == 'page':
                p = {}
                if isinstance(v, str): p['size'] = v
                else:
                    for a, b in v.items():
                        if a == 'margin': p['margin_mm'] = list(margins(b))
                        elif a in ('size', 'orientation', 'columns', 'justify', 'hyphenate'): p[a] = b
                        elif a == 'numbers': p['footer'] = {'page_numbers': bool(b)}
                ov.setdefault('layout', {})['page'] = p
            elif k == 'numbered_headings': ov.setdefault('layout', {})['heading_numbers'] = bool(v)
            else: meta[k] = v.isoformat() if isinstance(v, (dt.date, dt.datetime)) else v   # title author date lang toc cover css ...
        except Exception as e:
            warn.append(f'front matter key {k!r} ignored: {e}')
    return ov, meta, warn

# CLI flags map to the same override shape: --font 'Segoe UI' -> {'fonts': {'body': "'Segoe UI', sans-serif"}}, --accent '#e91e63' -> {'accent': ...},
# --theme nord (base preset), --css extra.css (repeatable; appended LAST, unlayered). Front-matter css: is resolved relative to the .md file; CLI --css relative to cwd.
# Example front matter: theme: nord / accent: '#e91e63' / font: Inter / font_size: 10.5 / page: {size: Letter, margin: '15mm 20mm', columns: 2, numbers: false} / toc: {depth: 3} / numbered_headings: true / lang: en