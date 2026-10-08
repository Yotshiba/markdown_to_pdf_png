"""Map the app theme onto Mermaid themeVariables and PlantUML skinparams."""
from __future__ import annotations

from .tone import contrast, mix
from .theme import Theme


def readable_on(bg, light='#ffffff', dark='#111111'):
    return light if contrast(bg, light) >= contrast(bg, dark) else dark


def mermaid_theme_variables(t, font_family, font_size='16px'):
    d = bool(t['dark']); bg, fg = t['bg'], t['fg']; acc = t['accent']; acc2 = t.get('accent2', acc)
    line = mix(fg, bg, 0.35); border = t.get('border', mix(fg, bg, 0.8))
    surface = t.get('surface', mix(bg, fg, 0.08 if d else 0.04))
    warn = t.get('warn', '#d4a72c'); danger = t.get('danger', '#e5534b'); pal = (list(t['palette']) * 3)[:12]
    tint = lambda c, light=0.14, dark=0.32: mix(bg, c, dark if d else light)
    node, node2 = tint(acc), tint(acc2)
    adj = lambda c: mix(c, '#000000' if d else '#ffffff', 0.10)     # mindmap/timeline use lighten(+10)/darken(-10) of cScale
    task_fill = mix(bg, acc, 0.65 if d else 0.55)
    v = {
      'darkMode': d, 'background': bg, 'fontFamily': font_family, 'fontSize': font_size,
      'primaryColor': node, 'primaryTextColor': fg, 'primaryBorderColor': acc,
      'secondaryColor': node2, 'secondaryTextColor': fg, 'secondaryBorderColor': acc2,
      'tertiaryColor': surface, 'tertiaryTextColor': fg, 'tertiaryBorderColor': border,
      'lineColor': line, 'arrowheadColor': line, 'textColor': fg, 'titleColor': fg,
      'mainBkg': node, 'nodeBkg': node, 'nodeBorder': acc, 'nodeTextColor': fg,
      'clusterBkg': surface, 'clusterBorder': border, 'edgeLabelBackground': bg, 'border2': border,
      'noteBkgColor': tint(warn, 0.22, 0.30), 'noteBorderColor': warn, 'noteTextColor': fg,
      'actorBkg': node, 'actorBorder': acc, 'actorTextColor': fg, 'actorLineColor': mix(fg, bg, 0.5),
      'signalColor': mix(fg, bg, 0.15), 'signalTextColor': fg,
      'labelBoxBkgColor': surface, 'labelBoxBorderColor': border, 'labelTextColor': fg, 'loopTextColor': fg,
      'activationBkgColor': node2, 'activationBorderColor': acc2, 'sequenceNumberColor': bg, 'rectBkgColor': surface,
      'stateBkg': node, 'stateLabelColor': fg, 'transitionColor': line, 'transitionLabelColor': fg,
      'labelBackgroundColor': bg, 'compositeBackground': surface, 'compositeTitleBackground': node2,
      'compositeBorder': border, 'altBackground': surface, 'specialStateColor': line,
      'errorBkgColor': tint(danger), 'errorTextColor': fg,
      'attributeBackgroundColorOdd': surface, 'attributeBackgroundColorEven': mix(surface, bg, 0.5),
      'rowOdd': surface, 'rowEven': mix(surface, bg, 0.5),
      'sectionBkgColor': surface, 'altSectionBkgColor': bg, 'sectionBkgColor2': node2,
      'excludeBkgColor': mix(bg, fg, 0.08), 'taskBkgColor': task_fill, 'taskBorderColor': acc,
      'activeTaskBkgColor': node, 'activeTaskBorderColor': acc,
      'doneTaskBkgColor': mix(bg, fg, 0.25), 'doneTaskBorderColor': mix(bg, fg, 0.45),
      'critBkgColor': danger, 'critBorderColor': mix(danger, fg, 0.3), 'todayLineColor': danger, 'vertLineColor': acc2,
      'gridColor': border, 'taskTextColor': readable_on(task_fill), 'taskTextLightColor': readable_on(task_fill),
      'taskTextDarkColor': fg, 'taskTextOutsideColor': fg, 'taskTextClickableColor': acc,
      'classText': fg,
      'requirementBackground': node, 'requirementBorderColor': acc, 'requirementTextColor': fg,
      'relationColor': line, 'relationLabelBackground': bg, 'relationLabelColor': fg,
      'pieTitleTextColor': fg, 'pieSectionTextColor': fg, 'pieLegendTextColor': fg,
      'pieStrokeColor': bg, 'pieStrokeWidth': '2px', 'pieOuterStrokeColor': border, 'pieOuterStrokeWidth': '1px', 'pieOpacity': '0.85',
      'quadrant1Fill': tint(pal[0]), 'quadrant2Fill': tint(pal[1]), 'quadrant3Fill': tint(pal[2]), 'quadrant4Fill': tint(pal[3]),
      'quadrant1TextFill': fg, 'quadrant2TextFill': fg, 'quadrant3TextFill': fg, 'quadrant4TextFill': fg,
      'quadrantPointFill': acc, 'quadrantPointTextFill': fg, 'quadrantXAxisTextFill': fg, 'quadrantYAxisTextFill': fg,
      'quadrantInternalBorderStrokeFill': border, 'quadrantExternalBorderStrokeFill': border, 'quadrantTitleFill': fg,
      'commitLabelColor': fg, 'commitLabelBackground': surface, 'tagLabelColor': fg, 'tagLabelBackground': node,
      'tagBorder': acc, 'tagLabelBorder': acc, 'branchLabelColor': fg,
      'archEdgeColor': line, 'archEdgeArrowColor': line, 'archGroupBorderColor': border,
      'vennTitleTextColor': fg, 'vennSetTextColor': fg,
      'xyChart': {'backgroundColor': bg, 'titleColor': fg, 'dataLabelColor': fg, 'legendTextColor': fg,
                  'xAxisTitleColor': fg, 'xAxisLabelColor': fg, 'xAxisTickColor': fg, 'xAxisLineColor': fg,
                  'yAxisTitleColor': fg, 'yAxisLabelColor': fg, 'yAxisTickColor': fg, 'yAxisLineColor': fg,
                  'plotColorPalette': ','.join(pal[:10])},
      'packet': {'startByteColor': fg, 'endByteColor': fg, 'labelColor': fg, 'titleColor': fg, 'blockStrokeColor': line, 'blockFillColor': node},
      'treemap': {'sectionStrokeColor': border, 'sectionFillColor': surface, 'leafStrokeColor': acc, 'leafFillColor': node,
                  'labelColor': fg, 'valueColor': fg, 'titleColor': fg},
      'treeView': {'labelColor': fg, 'lineColor': line},
      'radar': {'axisColor': line, 'graticuleColor': border},
    }
    for i, c in enumerate(pal):
        v[f'cScale{i}'] = c; v[f'cScaleLabel{i}'] = readable_on(adj(c)); v[f'cScaleInv{i}'] = readable_on(c); v[f'pie{i + 1}'] = c
    for i in range(8):
        v[f'git{i}'] = pal[i]; v[f'gitInv{i}'] = readable_on(pal[i]); v[f'gitBranchLabel{i}'] = readable_on(pal[i])
        v[f'fillType{i}'] = pal[i]; v[f'venn{i + 1}'] = mix(pal[i], bg, 0.15)
        if i < 6: v[f'actor{i}'] = pal[i]         # journey actors (journey.actorColours config is ignored by 12.1.0)
    return v

def mermaid_extra_config(t):
    d = bool(t['dark']); line = mix(t['fg'], t['bg'], 0.35)
    css = [f'.lineWrapper line{{stroke:{line} !important}}']                       # timeline axis is stroke="black"
    if d: css.append('.link{mix-blend-mode:normal !important;stroke-opacity:.55 !important}')  # sankey multiply blend
    return {'sankey': {'useMaxWidth': True}, 'ishikawa': {'useMaxWidth': True}, 'themeCSS': ''.join(css)}

def mermaid_config(t: Theme, *, look: str = 'classic', elk: bool = False) -> dict:
    """Full mermaid.initialize() config (theme 'base' + variables derived from the app theme)."""
    c, d = t.colors, t.diagram
    fam = (d.font or t.fonts.body)
    tokens = {
        'dark': t.mode == 'dark', 'bg': c.page_bg, 'fg': c.text, 'accent': c.accent,
        'accent2': d.palette[3].border if len(d.palette) > 3 else c.accent,
        'border': c.border, 'surface': c.table_head_bg,
        'warn': c.admonition['warning'].bar if 'warning' in c.admonition else '#d4a72c',
        'danger': c.admonition['caution'].bar if 'caution' in c.admonition else '#e5534b',
        'palette': [p.border for p in d.palette] or [c.accent],
    }
    extra = mermaid_extra_config(tokens)
    variables = mermaid_theme_variables(tokens, fam, f'{d.font_size_px}px')
    variables.update(d.mermaid)
    cfg = {
        'theme': 'base', 'themeVariables': variables, 'fontFamily': fam, 'look': look,
        'layout': 'dagre', 'securityLevel': 'strict', 'maxTextSize': 200000, 'maxEdges': 2000,
        'flowchart': {'useMaxWidth': True}, 'sankey': extra['sankey'], 'ishikawa': extra['ishikawa'],
        'themeCSS': extra['themeCSS'],
    }
    if elk:
        cfg.pop('layout')
        for k in ('flowchart', 'state', 'class', 'er'):
            cfg.setdefault(k, {})['layout'] = 'elk'
    return cfg


def diagram_colors(t: Theme) -> dict:
    """The few colours every diagram engine needs, derived once so Mermaid and PlantUML match."""
    c, d = t.colors, t.diagram
    dark = t.mode == 'dark'
    acc = c.accent
    acc2 = d.palette[3].border if len(d.palette) > 3 else acc
    node = mix(c.page_bg, acc, 0.32 if dark else 0.14)
    node2 = mix(c.page_bg, acc2, 0.32 if dark else 0.14)
    line = d.line or mix(c.text, c.page_bg, 0.35)
    surface = c.table_head_bg
    return dict(node=node, node2=node2, border=acc, border2=acc2, line=line, surface=surface,
                text=c.text, note=d.note_bg or c.quote_bg, grid=c.border)


def plantuml_prologue(t: Theme) -> str:
    """skinparams injected on the line after @start...; the author's own skinparams later still win."""
    c, d = t.colors, t.diagram
    k = diagram_colors(t)
    font = (d.font or t.fonts.body).split(',')[0].strip(' "' + chr(39))
    sp = {'backgroundColor': 'transparent', 'defaultFontName': font, 'defaultFontSize': str(int(d.font_size_px * 0.8)),
          'defaultFontColor': k['text'], 'shadowing': 'false', 'roundCorner': '8',
          'ArrowColor': k['line'], 'ArrowFontColor': k['text'], 'BorderColor': k['border'],
          'NoteBackgroundColor': k['note'], 'NoteBorderColor': k['grid'], 'NoteFontColor': k['text'],
          'PackageBackgroundColor': k['surface'], 'PackageBorderColor': k['grid'], 'PackageFontColor': k['text'],
          'LegendBackgroundColor': k['surface'], 'LegendBorderColor': k['grid'], 'LegendFontColor': k['text']}
    for el in ('Class', 'Component', 'Node', 'Database', 'Rectangle', 'Usecase', 'State', 'Activity', 'Participant',
               'Interface', 'Object', 'Artifact', 'Cloud', 'Queue', 'Folder', 'Frame', 'Entity', 'Boundary', 'Control',
               'Collections', 'Storage', 'Package'):
        sp[f'{el}BackgroundColor'] = k['node']; sp[f'{el}BorderColor'] = k['border']; sp[f'{el}FontColor'] = k['text']
    # Actor: stick figures use the border colour for the whole figure, so keep it strong and the fill = node
    sp.update({'ActorBackgroundColor': k['node'], 'ActorBorderColor': k['border'], 'ActorFontColor': k['text'],
               'ActivityStartColor': k['line'], 'ActivityEndColor': k['line'], 'ActivityBarColor': k['line'],
               'ActivityDiamondBackgroundColor': k['node2'], 'ActivityDiamondBorderColor': k['border2'],
               'ActivityDiamondFontColor': k['text'], 'CircledCharacterFontColor': k['text'], 'CircledCharacterRadius': '9',
               'SequenceLifeLineBorderColor': k['line'], 'SequenceGroupBorderColor': k['grid'],
               'SequenceBoxBorderColor': k['grid'], 'SequenceDividerBorderColor': k['grid'],
               'SequenceGroupBackgroundColor': k['surface'], 'SequenceGroupHeaderFontColor': k['text'],
               'SequenceReferenceBackgroundColor': k['surface'], 'SequenceReferenceBorderColor': k['grid'],
               'SequenceReferenceFontColor': k['text'], 'SequenceDelayFontColor': k['text'],
               'SequenceTitleFontColor': k['text'], 'TitleFontColor': k['text']})
    sp.update(d.plantuml)
    return chr(10).join(f'skinparam {key} {val}' for key, val in sp.items())


STYLE_KINDS = {'mindmap': 'mindmapDiagram', 'wbs': 'wbsDiagram', 'gantt': 'ganttDiagram', 'json': 'jsonDiagram',
               'yaml': 'yamlDiagram', 'salt': 'saltDiagram'}


def plantuml_preamble(t: Theme, kind: str = 'uml') -> str:
    """Theme preamble for one @start<kind> block.

    UML-style diagrams take skinparams. The newer kinds (mindmap, wbs, gantt, json, yaml, salt) use a compact
    <style> block instead: the large skinparam list overflows the JS engine's stack on those parsers.
    """
    kind = (kind or 'uml').lower()
    if kind == 'uml':
        return plantuml_prologue(t)
    if kind not in STYLE_KINDS:
        return ''  # ditaa, dot, ebnf, regex, math, ... : leave untouched
    k = diagram_colors(t)
    if kind == 'salt':  # wireframes ignore <style>; a few skinparams are enough
        font = ((t.diagram.font or t.fonts.body).split(',')[0].strip(' "' + chr(39)))
        return chr(10).join(f'skinparam {a} {b}' for a, b in (
            ('backgroundColor', 'transparent'), ('defaultFontName', font), ('defaultFontColor', k['text']),
            ('shadowing', 'false')))
    font = ((t.diagram.font or t.fonts.body).split(',')[0].strip(' "' + chr(39)))
    sel = STYLE_KINDS[kind]
    node = f"BackGroundColor {k['node']}\n    LineColor {k['border']}\n    FontColor {k['text']}"
    body = {
        'mindmap': f"node {{\n    {node}\n  }}\n  arrow {{\n    LineColor {k['line']}\n  }}",
        'wbs': f"node {{\n    {node}\n  }}\n  arrow {{\n    LineColor {k['line']}\n  }}",
        'gantt': f"task {{\n    {node}\n  }}\n  separator {{\n    LineColor {k['grid']}\n  }}",
        'json': f"node {{\n    {node}\n  }}\n  highlight {{\n    BackGroundColor {k['node2']}\n  }}",
        'yaml': f"node {{\n    {node}\n  }}",
        'salt': '',
    }[kind]
    inner = f"\n  {body}" if body else ''
    return (f"<style>\nroot {{\n  BackGroundColor transparent\n  FontColor {k['text']}\n  FontName {font}\n"
            f"  LineColor {k['border']}\n}}\n{sel} {{{inner}\n}}\n</style>")
