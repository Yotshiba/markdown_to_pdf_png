"""Markdown text -> a complete HTML file on disk -> PDF/PNG. Shared by the CLI and the GUI preview."""
from __future__ import annotations

import html as html_lib
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import cssgen, diagram_theme, paths, puml
from .fonts import first_family, inspect_font, validate_font
from .frontmatter import front_to_overrides, split_front_matter
from .images import ImageStager
from .job import Job
from .parser import make_formatter, parse
from .sanitize import sanitize
from .template import BUNDLED_FACES, BuildInput, DocMeta, build_html
from .theme import Theme, audit, resolve
from .themes_store import load_preset

Emit = Callable[[str, dict], None]


@dataclass
class Prepared:
    html_path: Path
    work_dir: Path
    theme: Theme
    mode: str
    meta: DocMeta
    warnings: list[dict] = field(default_factory=list)
    base_dir: Path = Path(".")


def _noop(kind: str, data: dict) -> None:
    pass


def _error_card(title: str, message: str, src: str = "") -> str:
    det = (f"<details><summary>diagram source</summary><pre class=\"diagram-error-src\">{html_lib.escape(src)}</pre></details>"
           if src else "")
    return (f'<div class="diagram-error" role="alert"><div class="diagram-error-title">{html_lib.escape(title)}</div>'
            f'<pre class="diagram-error-msg">{html_lib.escape(message)}</pre>{det}</div>')


def read_source(job: Job) -> tuple[str, Path]:
    if job.markdown is not None:
        text = job.markdown
    elif job.input:
        text = Path(job.input).read_text(encoding="utf-8-sig")
    else:
        raise ValueError("no input: give a Markdown file")
    base = job.base_dir or (Path(job.input).resolve().parent if job.input else Path.cwd())
    return text, Path(base).resolve()


def resolve_theme(job: Job, fm_overrides: dict) -> Theme:
    fm_ov = dict(fm_overrides)
    name = job.theme or fm_ov.pop("__theme__", None) or "github-light"
    fm_ov.pop("__theme__", None)
    return resolve(load_preset(name), None, fm_ov, job.overrides())


def _as_list(v) -> list:
    return [] if v is None else (v if isinstance(v, list) else [v])


def prepare(job: Job, mode: str, work_dir: Path | None = None, emit: Emit = _noop) -> Prepared:
    """Build index.html (+ assets/) in a work dir. `mode` is pdf | png | preview."""
    warnings: list[dict] = []

    def warn(kind: str, message: str, line: int | None = None) -> None:
        warnings.append({"kind": kind, "line": line, "message": message})
        emit("warning", {"kind": kind, "line": line, "message": message})

    text, base = read_source(job)
    fm, body, fm_warn = split_front_matter(text)
    for w in fm_warn:
        warn("front-matter", w)
    fm_ov, meta_dict, ow = front_to_overrides(fm)
    for w in ow:
        warn("front-matter", w)
    theme = resolve_theme(job, fm_ov)
    for w in audit(theme):
        warn("contrast", w)

    _sweep_stale_temp()
    work = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="md2doc_"))
    work.mkdir(parents=True, exist_ok=True)
    assets = work / "assets"

    cache_dir = paths.user_dirs()[1]
    stager = ImageStager(base, assets, trusted=job.trusted, allow_remote=job.remote_images,
                         cache_dir=cache_dir, warn=lambda m: warn("image", m))

    parsed = parse(body, html_mode=job.html, resolve_image=stager.resolve,
                   formatter=make_formatter(line_numbers=theme.code.line_numbers),
                   captions=meta_dict.get("captions", job.captions) if isinstance(meta_dict.get("captions"), str) else job.captions,
                   typographer=job.typographer)
    body_html = sanitize(parsed.html, stager.resolve) if job.html == "safe" else parsed.html

    # ---- PlantUML ------------------------------------------------------------------------------
    has_puml_js = False
    puml_text = ""
    if parsed.plantuml:
        body_html, has_puml_js, puml_text = _fill_plantuml(job, theme, parsed.plantuml, body_html, base, warn)

    # ---- fonts / css / meta ----------------------------------------------------------------------
    extra_faces, bundled_families = _imported_fonts(job, meta_dict, base, warn)
    for stack in (theme.fonts.body, theme.fonts.heading or "", theme.fonts.mono):
        if stack:
            ok, hints = validate_font(stack, extra=set(BUNDLED_FACES) | set(bundled_families))
            if not ok:
                warn("font", f"font {first_family(stack)!r} is not installed; a fallback will be used"
                     + (f" (did you mean {', '.join(hints)}?)" if hints else ""))

    user_css = _user_css(job, meta_dict, base, warn)
    toc = job.toc if job.toc is not None else _toc_from_meta(meta_dict.get("toc"))
    cover = job.cover if job.cover is not None else bool(meta_dict.get("cover"))
    m = DocMeta(title=str(meta_dict.get("title", "")), subtitle=str(meta_dict.get("subtitle", "")),
                author=str(meta_dict.get("author", "")), date=str(meta_dict.get("date", "")),
                lang=str(meta_dict.get("lang", "en")))
    numbered = job.numbered_headings if job.numbered_headings is not None else bool(meta_dict.get("numbered_headings"))

    from .template import build_html

    html_text = build_html(BuildInput(
        body_html=body_html, theme=theme, mode=mode, meta=m, headings=parsed.headings, toc_depth=toc or 0,
        cover=cover, has_math=parsed.has_math, has_mermaid=parsed.has_mermaid, has_plantuml_js=has_puml_js,
        plantuml_source_text=puml_text, user_css=user_css, extra_faces=extra_faces, mermaid_look=job.mermaid_look,
        mermaid_elk=job.mermaid_elk, deadline_ms=job.deadline_s * 1000,
        katex_output="html", numbered_headings=numbered,
    ))
    html_path = work / "index.html"
    html_path.write_text(html_text, encoding="utf-8")
    return Prepared(html_path, work, theme, mode, m, warnings, base)


def _sweep_stale_temp(max_age_h: float = 24.0) -> None:
    """Remove md2doc_* work folders older than a day (left behind when an export was force-killed)."""
    import time

    try:
        now = time.time()
        for d in Path(tempfile.gettempdir()).glob("md2doc_*"):
            if d.is_dir() and now - d.stat().st_mtime > max_age_h * 3600:
                shutil.rmtree(d, ignore_errors=True)
    except OSError:
        pass


def _toc_from_meta(v) -> int:
    if v in (None, False):
        return 0
    if v is True:
        return 3
    if isinstance(v, int):
        return v
    if isinstance(v, dict):
        return int(v.get("depth", 3)) if v.get("enabled", True) else 0
    return 0


def _fill_plantuml(job: Job, theme: Theme, items: list[tuple[int, str]], body_html: str, base: Path, warn) -> tuple[str, bool, str]:
    preamble = diagram_theme.plantuml_prologue(theme)
    prepared: list[tuple[str, str | None]] = [puml.prepare(src, preamble, base) for _, src in items]
    backend = job.plantuml
    java = jar = None
    if backend in ("java", "auto"):
        found = puml.find_java(job.java_path)
        jar = puml.find_jar()
        java = found[0] if found else None
        if backend == "auto":
            backend = "java" if (java and jar) else "js"
    use_js = False
    svgs: dict[int, str] = {}
    if backend == "java":
        if not java or not jar:
            msg = ("Java 11 or newer was not found (set --java-path, or run: md2doc setup --jre)." if not java
                   else "The PlantUML jar is not installed. Run: md2doc setup --java")
            for i, (line, src) in enumerate(items):
                svgs[i] = _error_card(f"PlantUML diagram {i + 1} could not be rendered", msg, src)
                warn("plantuml", msg, line + 1)
        else:
            ok_idx = [i for i, (_, e) in enumerate(prepared) if e is None]
            try:
                out = puml.render_java([prepared[i][0] for i in ok_idx], java=java, jar=jar, dot=puml.find_dot(job.dot_path))
                for i, svg in zip(ok_idx, out):
                    svgs[i] = f'<div class="plantuml-host" data-state="ok">{puml.isolate_svg(svg, f"pu{i}")}</div>'
            except puml.PumlError as e:
                for i in ok_idx:
                    svgs[i] = _error_card(f"PlantUML diagram {i + 1} could not be rendered", e.user_message, items[i][1])
                    warn("plantuml", e.user_message, items[i][0] + 1)
    elif backend == "remote":
        for i, (line, src) in enumerate(items):
            final, err = prepared[i]
            if err is None and not job.allow_remote_plantuml:
                err = "The online PlantUML renderer is not allowed (it would send the diagram text to plantuml.com)."
            if err is None:
                try:
                    svgs[i] = f'<div class="plantuml-host" data-state="ok">{puml.isolate_svg(puml.render_remote(final), f"pu{i}")}</div>'
                    continue
                except puml.PumlError as e:
                    err = e.user_message
            svgs[i] = _error_card(f"PlantUML diagram {i + 1} could not be rendered", err, src)
            warn("plantuml", err, line + 1)
    else:
        use_js = True

    texts = []
    for i, (line, src) in enumerate(items):
        final, err = prepared[i]
        if i in svgs:
            repl = svgs[i]
        elif err is not None:
            repl = _error_card(f"PlantUML diagram {i + 1} could not be rendered", err, src)
            warn("plantuml", err, line + 1)
        elif use_js:
            orig = puml.normalize_puml(src)
            repl = (f'<pre class="plantuml-src" data-orig="{html_lib.escape(orig, quote=True)}">'
                    f'{html_lib.escape(final, quote=False)}</pre>')
            texts.append(final)
        else:
            repl = _error_card("PlantUML", "no renderer", src)
        body_html = body_html.replace(f"@@PUML:{i}@@", repl)
    return body_html, bool(texts), "\n".join(texts)


def _imported_fonts(job: Job, meta: dict, base: Path, warn) -> tuple[list[dict], set[str]]:
    files = list(job.font_files)
    if job.trusted:
        files += [Path(base / f) for f in _as_list(meta.get("font_files")) if isinstance(f, str)]
    faces: list[dict] = []
    for fp in files:
        fp = Path(fp)
        if not fp.is_file():
            warn("font", f"font file not found: {fp}")
            continue
        try:
            info = inspect_font(fp)
        except Exception as e:  # noqa: BLE001
            warn("font", f"cannot read font {fp.name}: {e}")
            continue
        for w in info["warnings"]:
            warn("font", f"{fp.name}: {w}")
        faces.append({"family": info["family"], "file": fp.resolve(), "weight": str(info["weight"]),
                      "style": "italic" if info["italic"] else "normal", "variable": bool(info["axes"])})
    return faces, {f["family"] for f in faces}


def _user_css(job: Job, meta: dict, base: Path, warn) -> list[str]:
    out: list[str] = []
    cands = [(Path(p), "--css") for p in job.css_files]
    if job.trusted:
        cands += [(base / p, "front matter css") for p in _as_list(meta.get("css")) if isinstance(p, str)]
    for p, origin in cands:
        try:
            out.append(Path(p).read_text(encoding="utf-8"))
        except OSError:
            warn("css", f"{origin}: cannot read {p}")
    return out


# ---------------------------------------------------------------------------------------------------
@dataclass
class ConvertResult:
    output: Path
    warnings: list[dict]
    errors: list[dict]
    diagrams: list[dict]
    browser: str = ""
    ms: int = 0


def default_output(job: Job) -> Path:
    if job.output:
        out = Path(job.output)
        return out / f"{Path(job.input).stem}.{job.format}" if out.is_dir() and job.input else out
    if not job.input:
        raise ValueError("no output path: give --output")
    return Path(job.input).with_suffix("." + job.format)


def convert(job: Job, emit: Emit = _noop) -> ConvertResult:
    from .export import Exporter

    out = default_output(job)
    emit("stage", {"name": "prepare", "message": "Converting Markdown..."})
    prep = prepare(job, job.format, emit=emit)
    try:
        emit("stage", {"name": "render", "message": "Rendering in the browser..."})
        with Exporter(job.browser_path, job.deadline_s) as ex:
            emit("log", {"message": f"browser: {ex.version}"})
            if job.format == "pdf":
                pw, _ = cssgen.printable_px(prep.theme)
                report = ex.pdf(prep.html_path, out, viewport_w=pw)
            else:
                png = prep.theme.layout.png
                report = ex.png(prep.html_path, out, width=png.width_px, scale=png.scale, transparent=png.transparent)
        warnings = prep.warnings + [dict(w, kind=w.get("kind", "page")) for w in report.warnings]
        for w in report.warnings:
            emit("warning", w)
        for e in report.errors:
            emit("warning", {**e, "kind": e.get("kind", "error")})
        return ConvertResult(out, warnings, report.errors, report.diagrams, report.browser, report.ms)
    finally:
        if not job.keep_temp:
            shutil.rmtree(prep.work_dir, ignore_errors=True)
