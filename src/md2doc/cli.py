"""Command line interface.

    md2doc notes.md                         -> notes.pdf
    md2doc notes.md -f png --theme nord     -> notes.png
    md2doc notes.md -f both --font "Georgia" --accent "#e91e63"
    md2doc setup | doctor | themes | fonts
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXIT_OK, EXIT_FATAL, EXIT_STRICT, EXIT_NO_BROWSER, EXIT_TIMEOUT, EXIT_CANCELLED, EXIT_USAGE = 0, 1, 2, 3, 4, 5, 64
SUBCOMMANDS = {"setup", "doctor", "themes", "fonts", "export"}


def _utf8() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # exit code 2 means "warnings under --strict"; usage errors use 64
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(EXIT_USAGE)


def build_parser() -> argparse.ArgumentParser:
    p = _Parser(
        prog="md2doc", description="Convert Markdown to PDF or PNG (images, LaTeX, Mermaid, PlantUML, themes, fonts).",
        epilog="Other commands: md2doc setup | doctor | themes | fonts   (md2doc <command> -h)")
    p.add_argument("input", type=Path, help="Markdown file")
    p.add_argument("-o", "--output", help="output file, or a folder when it ends with a slash (default: next to the input)")
    p.add_argument("-f", "--format", choices=["pdf", "png", "both"], default="pdf")
    g = p.add_argument_group("look")
    g.add_argument("--theme", help="preset id or path to a theme .json (see: md2doc themes)")
    g.add_argument("--mode", choices=["light", "dark"], help="force light or dark (re-derives the palette when used with --tone-seed)")
    g.add_argument("--accent", help="accent colour, e.g. '#e91e63' (links, quote bars, headings accents)")
    g.add_argument("--tone-seed", help="seed colour: derive a complete harmonious palette from it")
    g.add_argument("--temperature", type=float, help="-1 (cool) .. 1 (warm) tint of the neutrals (needs --tone-seed or a tone)")
    g.add_argument("--saturation", type=float, help="0 .. 2 colourfulness")
    g.add_argument("--lightness", type=float, help="-1 .. 1 page background lightness")
    g.add_argument("--font", help="body font family, e.g. 'Segoe UI' (see: md2doc fonts)")
    g.add_argument("--heading-font", help="heading font family")
    g.add_argument("--mono-font", help="code font family")
    g.add_argument("--font-size", type=float, help="body size in pt")
    g.add_argument("--line-height", type=float)
    g.add_argument("--font-file", action="append", type=Path, default=[], help="import a .ttf/.otf/.woff2 font file (repeatable)")
    g.add_argument("--css", action="append", type=Path, default=[], help="extra CSS file, applied last (repeatable)")
    g = p.add_argument_group("page (PDF)")
    g.add_argument("--page-size", help="A3, A4, A5, B5, Letter, Legal, Tabloid or '210mm 297mm'")
    g.add_argument("--landscape", action="store_true")
    g.add_argument("--margin", help="CSS-like margins in mm: '20', '15 20' or '10 15 20 15' (top right bottom left)")
    g.add_argument("--columns", type=int)
    g.add_argument("--no-page-numbers", action="store_true")
    g = p.add_argument_group("image (PNG)")
    g.add_argument("--png-width", type=int, help="page width in CSS px (default 900)")
    g.add_argument("--scale", type=float, help="device scale factor 1-4 (default 2)")
    g.add_argument("--transparent", action="store_true", help="transparent background")
    g = p.add_argument_group("document")
    g.add_argument("--toc", action="store_true", help="add a table of contents")
    g.add_argument("--toc-depth", type=int, default=3, metavar="N", help="heading depth for --toc (default 3)")
    g.add_argument("--cover", action="store_true", help="title page from front matter (title, subtitle, author, date)")
    g.add_argument("--numbered", action="store_true", help="number the headings")
    g.add_argument("--captions", choices=["alt", "title", "none"], default="alt", help="figure captions from image alt/title text")
    g.add_argument("--typographer", action="store_true", help="smart quotes and dashes")
    g = p.add_argument_group("safety / backends")
    g.add_argument("--html", choices=["safe", "off", "raw"], default="safe", help="raw HTML in Markdown: sanitise (default), disable, or keep as-is")
    g.add_argument("--untrusted", action="store_true", help="only read images/css/fonts from the document's folder")
    g.add_argument("--no-remote-images", action="store_true")
    g.add_argument("--plantuml", choices=["js", "java", "auto", "remote"], default="js", help="PlantUML renderer (default: built-in JS engine)")
    g.add_argument("--allow-remote-plantuml", action="store_true", help="allow --plantuml remote to send diagram text to plantuml.com")
    g.add_argument("--java-path")
    g.add_argument("--dot-path", help="Graphviz dot.exe for the Java PlantUML backend")
    g.add_argument("--browser", help="path to msedge.exe / chrome.exe")
    g.add_argument("--mermaid-look", choices=["classic", "neo", "handDrawn"], default="classic")
    g.add_argument("--mermaid-elk", action="store_true", help="use the ELK layout engine for flowcharts/state/class/ER")
    g.add_argument("--timeout", type=int, default=120, help="render time budget in seconds")
    g.add_argument("--keep-temp", action="store_true", help="keep the generated HTML for debugging")
    g.add_argument("--strict", action="store_true", help="exit with code 2 when there are warnings or diagram errors")
    g.add_argument("--jsonl", action="store_true", help="machine-readable progress events on stdout")
    g.add_argument("-q", "--quiet", action="store_true")
    return p


def job_from_args(a: argparse.Namespace):
    from .job import Job

    out = a.output
    if out and out.endswith(("/", chr(92))):  # "-o folder/" means a folder: create it
        Path(out).mkdir(parents=True, exist_ok=True)
    return Job(
        input=a.input, output=Path(out) if out else None, format="pdf" if a.format == "both" else a.format,
        theme=a.theme, mode=a.mode, accent=a.accent, tone_seed=a.tone_seed, temperature=a.temperature,
        saturation=a.saturation, lightness=a.lightness, font=a.font, heading_font=a.heading_font,
        mono_font=a.mono_font, font_size=a.font_size, line_height=a.line_height, font_files=a.font_file, css_files=a.css,
        page_size=a.page_size, orientation="landscape" if a.landscape else None, margin=a.margin, columns=a.columns,
        page_numbers=False if a.no_page_numbers else None, png_width=a.png_width, scale=a.scale,
        transparent=True if a.transparent else None, toc=a.toc_depth if a.toc else None, cover=True if a.cover else None,
        numbered_headings=True if a.numbered else None, captions=a.captions, typographer=a.typographer,
        html=a.html, trusted=not a.untrusted, remote_images=not a.no_remote_images, plantuml=a.plantuml,
        allow_remote_plantuml=a.allow_remote_plantuml, java_path=a.java_path, dot_path=a.dot_path,
        browser_path=a.browser, mermaid_look=a.mermaid_look, mermaid_elk=a.mermaid_elk, deadline_s=a.timeout,
        keep_temp=a.keep_temp, strict=a.strict,
    )


class _Reporter:
    def __init__(self, jsonl: bool, quiet: bool):
        self.jsonl, self.quiet = jsonl, quiet
        self.warnings = 0

    def __call__(self, kind: str, data: dict) -> None:
        if kind == "warning":
            self.warnings += 1
        if self.jsonl:
            print(json.dumps({"event": kind, **data}, ensure_ascii=False), flush=True)
        elif kind == "warning" and not self.quiet:
            where = f" (line {data['line']})" if data.get("line") else ""
            print(f"warning [{data.get('kind', '')}]{where}: {data.get('message', '')}", file=sys.stderr)
        elif kind == "stage" and not self.quiet:
            print(data.get("message", ""), file=sys.stderr)
        elif kind == "log" and not self.quiet:
            print(data.get("message", ""), file=sys.stderr)


def run_job(job, jsonl: bool = False, quiet: bool = False, both: bool = False) -> int:
    from .browser import NoBrowserError
    from .export import ExportError
    from .pipeline import convert

    rep = _Reporter(jsonl, quiet)
    results = []
    try:
        for fmt in (["pdf", "png"] if both else [job.format]):
            j = job.model_copy(update={"format": fmt, "output": job.output if not both else _both_out(job, fmt)})
            results.append(convert(j, rep))
    except KeyboardInterrupt:
        return _fail(RuntimeError("cancelled"), jsonl, EXIT_CANCELLED, "cancelled")
    except NoBrowserError as e:
        return _fail(e, jsonl, EXIT_NO_BROWSER, "no_browser")
    except (ExportError, ValueError, KeyError, OSError) as e:
        return _fail(e, jsonl, EXIT_FATAL, "error")
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        code = EXIT_TIMEOUT if "Timeout" in type(e).__name__ or "Timeout" in msg else EXIT_FATAL
        return _fail(e, jsonl, code, "timeout" if code == EXIT_TIMEOUT else "error")
    for r in results:
        if jsonl:
            print(json.dumps({"event": "done", "output": str(r.output), "warnings": len(r.warnings), "errors": len(r.errors)}), flush=True)
        elif not quiet:
            print(f"wrote {r.output}", file=sys.stdout)
    bad = any(r.errors for r in results) or rep.warnings
    return EXIT_STRICT if (job.strict and bad) else EXIT_OK


def _both_out(job, fmt: str):
    if job.output and not Path(job.output).is_dir():
        return Path(job.output).with_suffix("." + fmt)
    return job.output


def _fail(e: Exception, jsonl: bool, code: int, kind: str) -> int:
    if jsonl:
        print(json.dumps({"event": "error", "kind": kind, "message": str(e)}), flush=True)
    else:
        print(f"error: {e}", file=sys.stderr)
    return code


# ------------------------------------------------------------------------------------------------
def cmd_setup(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="md2doc setup", description="Download the offline renderers (one time, ~50 MB).")
    ap.add_argument("--java", action="store_true", help="also download the PlantUML jar (optional Java backend)")
    ap.add_argument("--jre", action="store_true", help="also download a portable Java 21 runtime (49 MB)")
    ap.add_argument("--force", action="store_true", help="download again even if installed")
    a = ap.parse_args(argv)
    from . import setup_vendor

    return setup_vendor.run(java=a.java, jre=a.jre, force=a.force)


def cmd_doctor(argv: list[str]) -> int:
    from . import paths, puml
    from .browser import NoBrowserError, find_browser

    ok = True
    print(f"Python        {sys.version.split()[0]}  ({sys.executable})")
    try:
        import playwright  # noqa: F401
        from importlib.metadata import version

        print(f"Playwright    {version('playwright')}")
    except ImportError:
        print("Playwright    MISSING (pip install md2doc)")
        ok = False
    try:
        kind, exe = find_browser()
        print(f"Browser       {kind}: {exe}")
    except NoBrowserError as e:
        print(f"Browser       MISSING - {e}")
        ok = False
    print("Renderers     (md2doc setup installs these)")
    for k, v in paths.vendor_status().items():
        needed = k in ("katex", "mermaid", "plantuml-js", "fonts")
        mark = "ok" if v else ("MISSING" if needed else "not installed (optional)")
        ok &= v or not needed
        print(f"  {k:<14}{mark}")
    java = puml.find_java()
    print(f"Java          {'%s (Java %d)' % java if java else 'not found (only needed for --plantuml java)'}")
    dot = puml.find_dot()
    print(f"Graphviz      {dot if dot else 'not found (optional; PlantUML JS engine bundles its own)'}")
    try:
        import PySide6  # noqa: F401

        print(f"GUI           PySide6 {PySide6.__version__}")
    except ImportError:
        print("GUI           PySide6 not installed (pip install \"md2doc[gui]\")")
    print("\nAll required parts are present." if ok else "\nSome required parts are missing; see above.")
    return EXIT_OK if ok else EXIT_FATAL


def cmd_themes(argv: list[str]) -> int:
    from .themes_store import list_themes

    for tid, t in list_themes().items():
        print(f"{tid:<18}{t['name']:<26}{t['mode']:<7}{t['source']}")
    return EXIT_OK


def cmd_fonts(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="md2doc fonts", description="List installed font families.")
    ap.add_argument("filter", nargs="?", default="")
    a = ap.parse_args(argv)
    from .fonts import installed_families

    for n in sorted(installed_families(), key=str.lower):
        if a.filter.lower() in n.lower():
            print(n)
    return EXIT_OK


def cmd_export(argv: list[str]) -> int:
    """Internal entry point used by the GUI: md2doc export --job job.json --jsonl"""
    ap = argparse.ArgumentParser(prog="md2doc export")
    ap.add_argument("--job", required=True, type=Path)
    ap.add_argument("--jsonl", action="store_true")
    ap.add_argument("--both", action="store_true")
    a = ap.parse_args(argv)
    from .job import Job

    return run_job(Job.load(a.job), jsonl=a.jsonl, both=a.both)


def main(argv: list[str] | None = None) -> int:
    _utf8()
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in SUBCOMMANDS:
        return {"setup": cmd_setup, "doctor": cmd_doctor, "themes": cmd_themes, "fonts": cmd_fonts, "export": cmd_export}[argv[0]](argv[1:])
    a = build_parser().parse_args(argv)
    return run_job(job_from_args(a), jsonl=a.jsonl, quiet=a.quiet, both=(a.format == "both"))


if __name__ == "__main__":
    raise SystemExit(main())
