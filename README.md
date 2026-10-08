# md2doc

Convert **Markdown to PDF or PNG** with embedded images, **LaTeX math**, **Mermaid** and **PlantUML** diagrams,
and full control over **themes, colour tone and fonts**. Use the desktop app (editor + live preview) or the command line.

- Renders with the Microsoft Edge (or Chrome) already on your PC, so there is no browser to download.
- Works **offline**: KaTeX, Mermaid, PlantUML and fonts are downloaded once by `md2doc setup`, hash-verified, then stored locally.
- The preview and the export use the same HTML and the same renderer, so what you see is what you get.

## Install (Windows 10/11)

```bat
install.bat
```

That creates `.venv`, installs the dependencies and downloads the renderers (about 50 MB). Or by hand:

```bat
python -m venv .venv
.venv\Scripts\pip install -e ".[gui,dev]"
.venv\Scripts\md2doc setup          &:: one-time download of KaTeX, Mermaid, PlantUML, fonts
.venv\Scripts\md2doc doctor         &:: check everything is in place
```

Needs Python 3.11+ and Microsoft Edge or Google Chrome.

## Desktop app

```bat
md2doc-gui.bat            &:: or: md2doc-gui notes.md
```

- Markdown editor with syntax highlighting, line numbers, paste or drop images, and an **Insert** menu (tables, math, Mermaid, PlantUML, ...).
- Live preview that follows your cursor, and a **Problems** list (click an entry to jump to the line) for bad diagrams, math or missing images.
- **Look & layout** panel: theme preset, light/dark, **colour tone** (pick one colour, tune warm/cool, saturation, background), custom accent,
  **fonts** (any installed font, or import `.ttf`/`.otf`/`.woff2`), size, page size/margins/columns, table of contents, PNG width/scale.
- **File > Export PDF / PNG**. Save your own look with **Theme > Save current look as my theme**.

## Command line

```bat
md2doc notes.md                                   :: notes.pdf next to the input
md2doc notes.md -f png --theme nord               :: one long PNG
md2doc notes.md -f both -o out\report             :: report.pdf and report.png
md2doc notes.md -o exports\                       :: a trailing slash means a folder (created if missing)
md2doc notes.md --font "Georgia" --accent "#e91e63" --font-size 12
md2doc notes.md --tone-seed "#2e7d32" --temperature 0.4 --mode dark
md2doc notes.md --font-file MyFont.ttf --font "My Font" --toc --toc-depth 2 --cover --numbered
md2doc notes.md --page-size Letter --landscape --margin "15 20" --columns 2
md2doc themes        &:: list presets        md2doc fonts georgia   &:: search installed fonts
md2doc doctor        &:: environment check   md2doc -h              &:: all options
```

Exit codes: `0` ok, `1` error, `2` warnings with `--strict`, `3` no browser found, `4` timeout, `5` cancelled (Ctrl-C), `64` bad command line.
The output must end in `.pdf` / `.png` and can never overwrite the input file.

### Front matter

Settings can live in the document; the command line wins over front matter, which wins over the saved theme.

```yaml
---
title: Quarterly report
subtitle: Q3
author: Yotshiba
date: 2026-10-08
theme: paper-sepia
accent: "#a8541d"
font: Source Serif 4
page: { size: Letter, margin: "20mm 25mm", columns: 1, numbers: true }
toc: 3
cover: true
numbered_headings: true
css: extra.css
---
```

## What you can write

| Feature | Syntax |
|---|---|
| Math | `$x^2$`, `$$ ... $$`, `\( ... \)`, `\[ ... \]`, `\begin{align}...\end{align}`, ```` ```math ````, chemistry `$\ce{H2O}$` |
| Mermaid | ```` ```mermaid ```` - flowchart, sequence, class, state, ER, Gantt, pie, mindmap, git graph, timeline, journey, quadrant, sankey, xy-chart, block, architecture, kanban, ... |
| PlantUML | ```` ```plantuml ```` - sequence, class, use case, activity, component, state, Gantt, mindmap, JSON ... (built-in engine, no Java needed) |
| Images | `![caption](pic.png){width=50% .center}`, local, URL or `data:`; PNG, JPEG, GIF, WebP, SVG |
| Callouts | `> [!NOTE]`, `> [!WARNING]`, `!!! tip "Title"` |
| Also | tables, task lists, footnotes, definition lists, `~sub~`, `^sup^`, `\newpage` for a page break |

Diagrams adopt the active theme automatically. A broken diagram, equation or image never stops an export: it becomes an inline
error card and an entry in the Problems list.

### PlantUML engines

The default is PlantUML's official JavaScript engine running in the page. Optionally use Java:

```bat
md2doc setup --java        :: downloads the MIT-licensed plantuml jar (needs Java 11+; --jre adds a portable one)
md2doc notes.md --plantuml java
```

## Themes, tone and fonts

Ten built-in presets: GitHub Light/Dark, Solarized Light/Dark, Nord, Dracula, Paper (Sepia), Academic (LaTeX-like), Newspaper (2 columns),
High Contrast. A theme is a JSON file (see `src/md2doc/themes/`); drop your own into `%APPDATA%\md2doc\themes` or pass `--theme my.json`.

*Colour tone* generates a complete palette (page, text, headings, links, code, tables, callouts, diagram colours) from one seed colour
and keeps text readable (WCAG contrast is enforced). `--mode dark` on a light preset derives a matching dark palette.

*Fonts*: any installed family (`md2doc fonts`), plus imported files. For fully embedded PDF fonts prefer static `.ttf` files; variable,
CFF `.otf` and `.woff2` fonts work but PDF embeds them as outlines. Windows font fallback covers CJK, Thai, Arabic, Hebrew and emoji.

## Safety

Markdown may come from anywhere, so exports are locked down: raw HTML is sanitised (`--html off` disables it), the page runs under a
strict Content-Security-Policy with a per-render nonce (no `eval`), and the page may only read files from its own work folder, the
vendored renderers and fonts you imported; every network request from the page is blocked. Images are read by Python (magic-byte
checked, UNC/network paths refused, decompression bombs and oversized files rejected; `--untrusted` also confines them to the document
folder). Remote images are fetched only from public hosts (no localhost/private ranges, redirects re-checked). Front-matter fonts and
page sizes are validated before they reach any CSS, YAML aliases are refused, and PlantUML runs sandboxed.
`--no-remote-images` stops any download. Remote PlantUML rendering is off unless you pass `--allow-remote-plantuml`.

## Known limits

- Very wide tables are shrunk (down to 60% text size) to fit the page, then words are broken as a last resort; long display equations are
  scaled down the same way. The Problems list reports both.
- PlantUML wireframes (`@startsalt`) and ditaa are not supported by the built-in engine. They are rendered with Java automatically when
  `md2doc setup --java` and Java 11+ are available, otherwise you get an error card that says so.
- PNG output is one continuous image; very long documents are tiled internally and the scale is lowered automatically to stay under 90 megapixels.
- KaTeX has no `\label`/`\eqref`/`multline`; `multline` and `flalign` are mapped to the nearest supported environment.
- Mermaid ZenUML and icon packs are not bundled (they need extra downloads).
- Windows only for now (browser discovery and font enumeration use Windows APIs).

## Development

```bat
.venv\Scripts\python -m pytest              :: 90+ tests; browser tests skip when Edge/renderers are absent
```

```
src/md2doc/
  cli.py  job.py  pipeline.py      CLI, the Job description, Markdown -> HTML file -> export
  parser.py  sanitize.py  images.py  puml.py   Markdown, raw-HTML policy, image staging, PlantUML
  theme.py  tone.py  cssgen.py  diagram_theme.py  fonts.py   themes, colour tone, CSS, Mermaid/PlantUML mapping, fonts
  template.py  web/render.js  web/base.css       the one HTML page both preview and export load
  export.py  browser.py            Playwright driving Edge/Chrome: PDF and tiled PNG
  gui/                             PySide6 app (editor, preview, settings, export runner)
  setup_vendor.py                  hash-verified download of the offline renderers
```

The GUI never imports Playwright: it runs the same CLI (`md2doc export --job job.json --jsonl`) in a subprocess, so exports
are isolated, cancellable and identical to command-line results.

## Licence

MIT. Bundled/downloaded components keep their own licences: KaTeX (MIT), Mermaid (MIT), PlantUML (MIT build), Inter,
JetBrains Mono and Source Serif 4 (SIL OFL 1.1; licence files are stored with the fonts).
