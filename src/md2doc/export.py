"""Headless-Chromium export (Playwright driving the system Edge/Chrome): PDF and tiled PNG."""
from __future__ import annotations

import io
import os
from dataclasses import dataclass, field
from pathlib import Path

from urllib.parse import urlparse
from urllib.request import url2pathname

from .browser import NoBrowserError, find_browser

MAX_TILE_DEVICE_PX = 8192  # Chromium silently wraps content every 16384 device px; stay well below
MAX_PIXELS = 90_000_000


class ExportError(RuntimeError):
    pass


@dataclass
class PageReport:
    errors: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    diagrams: list[dict] = field(default_factory=list)
    math: dict = field(default_factory=dict)
    ms: int = 0
    fatal: str | None = None
    browser: str = ""


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(data)
    try:
        os.replace(tmp, path)
    except PermissionError as e:
        tmp.unlink(missing_ok=True)
        raise ExportError(f"Cannot write {path.name}: the file is open in another program. Close it and try again.") from e


class Exporter:
    def __init__(self, browser_path: str | None = None, deadline_s: int = 120, allowed_roots: list[Path] | None = None):
        self.kind, self.exe = find_browser(browser_path)
        self.deadline_ms = deadline_s * 1000
        self.allowed_roots = [Path(r).resolve() for r in (allowed_roots or [])]

    def _file_allowed(self, url: str) -> bool:
        """The page may only read files from the work dir, the vendored renderers and imported fonts."""
        p = urlparse(url)
        if p.netloc not in ("", "localhost"):
            return False
        try:
            path = Path(url2pathname(p.path)).resolve()
        except OSError:
            return False
        return any(path == r or path.is_relative_to(r) for r in self.allowed_roots)

    def __enter__(self) -> "Exporter":
        from playwright.sync_api import Error as PWError
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        try:
            self._browser = self._pw.chromium.launch(
                executable_path=self.exe, headless=True, chromium_sandbox=True, timeout=30_000,
                args=["--host-resolver-rules=MAP * ~NOTFOUND", "--font-render-hinting=none"],
            )
        except PWError as e:
            self._pw.stop()
            raise NoBrowserError(f"Could not start {self.kind} ({self.exe}): {str(e).splitlines()[0]}") from e
        self.version = f"{self.kind} {self._browser.version}"
        return self

    def __exit__(self, *exc) -> None:
        try:
            self._browser.close()
        finally:
            self._pw.stop()

    # -- page --------------------------------------------------------------------------------
    def _open(self, html: Path, *, width: int, scale: float, media: str):
        ctx = self._browser.new_context(viewport={"width": width, "height": 1000}, device_scale_factor=scale,
                                        service_workers="block", accept_downloads=False)
        blocked: list[str] = []

        def gate(route):  # only local content may load; everything else is refused and reported
            url = route.request.url
            if url.startswith(("data:", "blob:", "about:")) or (url.startswith("file:") and self._file_allowed(url)):
                route.continue_()
            else:
                blocked.append(url[:120])
                route.abort()

        ctx.route("**/*", gate)
        page = ctx.new_page()
        page.set_default_timeout(self.deadline_ms + 15_000)
        page.emulate_media(media=media)
        page.goto(html.resolve().as_uri(), wait_until="load")
        # wait_for_function() evaluates its predicate with eval() inside the page, which the page's CSP (no
        # 'unsafe-eval') forbids; plain evaluate() goes through the DevTools protocol and is not affected.
        waited = 0
        while not page.evaluate("() => window.__renderDone === true"):
            page.wait_for_timeout(100)
            waited += 100
            if waited > self.deadline_ms + 15_000:
                raise TimeoutError("the page did not finish rendering in time")
        return ctx, page, blocked

    def _report(self, page, blocked: list[str]) -> PageReport:
        raw = page.evaluate("() => window.__renderReport || {}")
        r = PageReport(errors=raw.get("errors", []), warnings=raw.get("warnings", []), diagrams=raw.get("diagrams", []),
                       math=raw.get("math", {}), ms=raw.get("ms", 0), fatal=raw.get("fatal"), browser=self.version)
        for u in dict.fromkeys(blocked):
            r.warnings.append({"kind": "network", "line": None, "message": f"blocked network request: {u}"})
        return r

    # -- outputs -----------------------------------------------------------------------------
    def pdf(self, html: Path, out: Path, *, viewport_w: int = 794) -> PageReport:
        ctx, page, blocked = self._open(html, width=viewport_w, scale=1, media="print")
        try:
            report = self._report(page, blocked)
            data = page.pdf(prefer_css_page_size=True, print_background=True, outline=True, tagged=True)
            _atomic_write(out, data)
            return report
        finally:
            ctx.close()

    def png(self, html: Path, out: Path, *, width: int, scale: float, transparent: bool = False,
            max_pixels: int = MAX_PIXELS) -> PageReport:
        from PIL import Image

        ctx, page, blocked = self._open(html, width=width, scale=scale, media="screen")
        try:
            report = self._report(page, blocked)
            w = page.evaluate("() => Math.ceil(document.documentElement.getBoundingClientRect().width)")
            h = page.evaluate("() => Math.ceil(Math.max(document.documentElement.scrollHeight, document.body.scrollHeight,"
                              " document.documentElement.getBoundingClientRect().height))")
            h += h % 2  # even height keeps fractional scales seam-free
            eff = scale
            if w * h * eff * eff > max_pixels:
                eff = max(1.0, (max_pixels / (w * h)) ** 0.5)
                eff = int(eff * 2) / 2  # step of 0.5
                if w * h * eff * eff > max_pixels or eff < 1:
                    raise ExportError(f"The image would be {w}x{h} px - too large for one PNG. Use PDF, a narrower width, or split the document.")
                report.warnings.append({"kind": "png", "line": None, "message": f"PNG scale lowered from {scale:g} to {eff:g} to stay under {max_pixels // 1_000_000} megapixels"})
                page.close()
                ctx.close()
                ctx, page, blocked = self._open(html, width=width, scale=eff, media="screen")
            tile = int(MAX_TILE_DEVICE_PX / eff) // 4 * 4
            canvas = Image.new("RGBA" if transparent else "RGB", (round(w * eff), round(h * eff)), (255, 255, 255))
            y = 0
            while y < h:
                th = min(tile, h - y)
                png = page.screenshot(type="png", full_page=True, animations="disabled", omit_background=transparent,
                                      clip={"x": 0, "y": y, "width": w, "height": th})
                with Image.open(io.BytesIO(png)) as im:
                    canvas.paste(im, (0, round(y * eff)))
                y += th
            buf = io.BytesIO()
            canvas.save(buf, format="PNG", compress_level=3, dpi=(96 * eff, 96 * eff))
            _atomic_write(out, buf.getvalue())
            return report
        finally:
            ctx.close()
