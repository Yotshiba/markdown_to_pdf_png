"""Resolve Markdown image references and stage them next to the generated HTML.

Every image is read by Python (never by the browser), validated by magic bytes, downscaled when huge,
and copied into the per-render assets directory. The page only ever sees `file:///.../assets/<hash>.<ext>`.
"""
from __future__ import annotations

import base64
import hashlib
import io
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import unquote, urlparse

from .safepath import is_unc
from urllib.request import url2pathname

MAX_LOCAL_BYTES = 60 * 1024 * 1024
MAX_REMOTE_BYTES = 25 * 1024 * 1024
CACHE_TTL_S = 7 * 24 * 3600

_SIGS = [
    (bytes.fromhex("89504e470d0a1a0a"), "image/png", ".png"),
    (bytes.fromhex("ffd8ff"), "image/jpeg", ".jpg"),
    (b"GIF8", "image/gif", ".gif"),
    (b"BM", "image/bmp", ".bmp"),
]
_EXT = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/bmp": ".bmp",
        "image/webp": ".webp", "image/svg+xml": ".svg", "image/avif": ".avif"}

_MISSING_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' width='320' height='72' viewBox='0 0 320 72'>"
    "<rect x='1' y='1' width='318' height='70' rx='6' fill='#fff5f5' stroke='#cf222e' stroke-dasharray='5 4'/>"
    "<text x='160' y='42' font-family='Segoe UI,Arial,sans-serif' font-size='14' fill='#cf222e' "
    "text-anchor='middle'>image not found</text></svg>"
)
PLACEHOLDER_URI = "data:image/svg+xml;base64," + base64.b64encode(_MISSING_SVG.encode()).decode()


def sniff(b: bytes) -> str | None:
    for sig, mime, _ in _SIGS:
        if b.startswith(sig):
            return mime
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "image/webp"
    if b[4:12] in (b"ftypavif", b"ftypavis"):
        return "image/avif"
    head = b[:4096].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if head.startswith(b"<svg") or (head.startswith((b"<?xml", b"<!doctype svg")) and b"<svg" in head):
        return "image/svg+xml"
    return None


def _shrink(data: bytes, mime: str, max_px: int) -> tuple[bytes, str]:
    """Downscale oversized rasters. Small PNG/JPEG/WebP pass through unchanged."""
    from PIL import Image, ImageOps

    Image.MAX_IMAGE_PIXELS = 100_000_000  # bigger than this is treated as a decompression bomb
    try:
        im = Image.open(io.BytesIO(data))
        if max(im.size) <= max_px and mime in ("image/png", "image/jpeg", "image/webp"):
            return data, mime
        im = ImageOps.exif_transpose(im)
        im.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        if im.mode in ("RGBA", "LA", "P") or mime in ("image/png", "image/webp"):
            im.convert("RGBA").save(out, "PNG", optimize=True)
            return out.getvalue(), "image/png"
        im.convert("RGB").save(out, "JPEG", quality=90, optimize=True)
        return out.getvalue(), "image/jpeg"
    except Image.DecompressionBombError:
        raise
    except Exception:
        return data, mime


class ImageStager:
    def __init__(
        self,
        base_dir: Path,
        assets_dir: Path,
        *,
        trusted: bool = True,
        allow_remote: bool = True,
        max_px: int = 3000,
        cache_dir: Path | None = None,
        warn: Callable[[str], None] = lambda m: None,
    ):
        self.base = base_dir.resolve()
        self.assets = assets_dir
        self.trusted = trusted
        self.allow_remote = allow_remote
        self.max_px = max_px
        self.cache_dir = cache_dir
        self.warn = warn
        self._memo: dict[str, str] = {}

    # -- public -----------------------------------------------------------------------------
    def resolve(self, src: str) -> str:
        src = (src or "").strip()
        if not src:
            return PLACEHOLDER_URI
        if src in self._memo:
            return self._memo[src]
        uri = self._resolve(src)
        self._memo[src] = uri
        return uri

    # -- internals --------------------------------------------------------------------------
    def _resolve(self, src: str) -> str:
        if src.startswith("data:"):
            return src if src.lower().startswith("data:image/") else self._fail(src, "data URI is not an image")
        if self._is_staged(src):
            return src
        if src.lower().startswith(("http://", "https://")):
            data = self._fetch(src) if self.allow_remote else None
            if data is None and not self.allow_remote:
                return self._fail(src, "remote images are disabled")
        else:
            data = self._read_local(src)
        if data is None:
            return self._fail(src, "could not be read")
        mime = sniff(data)
        if mime is None:
            return self._fail(src, "not a supported image format")
        if mime not in ("image/svg+xml", "image/gif"):
            try:
                data, mime = _shrink(data, mime, self.max_px)
            except Exception:  # decompression bomb, corrupt file
                return self._fail(src, "image is corrupt or too large to decode")
        return self._stage(data, mime)

    def _fail(self, src: str, why: str) -> str:
        self.warn(f"image unavailable ({why}): {unquote(src)[:120]}")
        return PLACEHOLDER_URI

    def _is_staged(self, src: str) -> bool:
        if not src.startswith("file:"):
            return False
        try:
            p = Path(url2pathname(urlparse(src).path)).resolve()
            return p.is_relative_to(self.assets.resolve())
        except (OSError, ValueError):
            return False

    def _local_path(self, src: str) -> Path | None:
        p = urlparse(src)
        if len(p.scheme) == 1:  # "C:\images\a.png" parses as scheme "c"
            s = src
        elif p.scheme == "file":
            if p.netloc not in ("", "localhost"):
                return None  # file://host/share -> would trigger an SMB (NTLM) connection
            s = url2pathname(p.path)
        elif p.scheme:
            return None
        else:
            s = unquote(src.split("#")[0].split("?")[0])
        if is_unc(s):
            return None  # UNC paths are never read (checked before any resolve(): resolving would touch the network)
        q = Path(s)
        return (q if q.is_absolute() else self.base / q).resolve()

    def _read_local(self, src: str) -> bytes | None:
        path = self._local_path(src)
        if path is None:
            return None
        if not self.trusted and not path.is_relative_to(self.base):
            self.warn(f"image outside the document folder was blocked: {src[:120]}")
            return None
        try:
            if not path.is_file() or path.stat().st_size > MAX_LOCAL_BYTES:
                return None
            return path.read_bytes()
        except OSError:
            return None

    def _fetch(self, url: str) -> bytes | None:
        cached = self._cache_path(url)
        if cached and cached.is_file() and time.time() - cached.stat().st_mtime < CACHE_TTL_S:
            return cached.read_bytes()
        data = _download_public(url)
        if data is None:
            return None
        if cached and sniff(data):
            try:
                cached.parent.mkdir(parents=True, exist_ok=True)
                cached.write_bytes(data)
            except OSError:
                pass
        return data

    def _cache_path(self, url: str) -> Path | None:
        if not self.cache_dir:
            return None
        return self.cache_dir / "images" / hashlib.sha256(url.encode()).hexdigest()

    def _stage(self, data: bytes, mime: str) -> str:
        name = hashlib.sha1(data).hexdigest()[:20] + _EXT.get(mime, ".bin")
        dest = self.assets / name
        if not dest.exists():
            self.assets.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        return dest.resolve().as_uri()


def _public_host(host: str) -> bool:
    """Only public internet hosts: no loopback, private, link-local or reserved addresses (SSRF guard)."""
    import ipaddress
    import socket

    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return False
    return bool(infos)


def _download_public(url: str, total_s: float = 25.0, max_redirects: int = 4) -> bytes | None:
    """GET with manual redirect handling: every hop must be http(s) to a public host; hard overall time cap."""
    import httpx

    deadline = time.monotonic() + total_s
    try:
        with httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0), follow_redirects=False,
                          headers={"User-Agent": "md2doc/0.1"}) as c:
            for _ in range(max_redirects + 1):
                p = urlparse(url)
                if p.scheme not in ("http", "https") or not p.hostname or not _public_host(p.hostname):
                    return None
                with c.stream("GET", url) as r:
                    if r.is_redirect:
                        url = str(r.next_request.url) if r.next_request else ""
                        if not url:
                            return None
                        continue
                    if r.status_code != 200:
                        return None
                    buf = bytearray()
                    for chunk in r.iter_bytes():
                        buf += chunk
                        if len(buf) > MAX_REMOTE_BYTES or time.monotonic() > deadline:
                            return None
                    return bytes(buf)
    except Exception:
        return None
    return None
