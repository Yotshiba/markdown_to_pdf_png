"""One-time download of the offline renderers (KaTeX, Mermaid, PlantUML, fonts ...).

Every download is verified against a pinned hash. Hashes that were verified during research are
hard-coded below; for the remaining files the first download records a hash in `vendor.lock.json`
(trust on first use) and every later run must match it.

    python -m md2doc setup            # everything the app needs
    python -m md2doc setup --java     # + MIT PlantUML jar (optional Java backend)
    python -m md2doc setup --jre      # + portable Temurin 21 JRE (49 MB, optional)
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import tarfile
import urllib.request
import zipfile
from pathlib import Path

from . import paths

UA = {"User-Agent": "md2doc-setup/1.0"}

KATEX_VERSION = "0.19.0"
KATEX_TGZ = f"https://registry.npmjs.org/katex/-/katex-{KATEX_VERSION}.tgz"
KATEX_INTEGRITY = "sha512-v6Tznz3zJ7u3niRCoDTsumM2+HA2XXcCu+WAacCeHD2z3p9A9Ks987o5FzfTGBN0e8A0vjEgIDvLbICrXpdw/Q=="
KATEX_FONTS = [
    "AMS-Regular", "Caligraphic-Bold", "Caligraphic-Regular", "Fraktur-Bold", "Fraktur-Regular",
    "Main-Bold", "Main-BoldItalic", "Main-Italic", "Main-Regular", "Math-BoldItalic", "Math-Italic",
    "SansSerif-Bold", "SansSerif-Italic", "SansSerif-Regular", "Script-Regular",
    "Size1-Regular", "Size2-Regular", "Size3-Regular", "Size4-Regular", "Typewriter-Regular",
]

MERMAID_VERSION = "12.1.0"
MERMAID_URL = f"https://cdn.jsdelivr.net/npm/mermaid@{MERMAID_VERSION}/dist/mermaid.min.js"
MERMAID_SHA256 = "6484afc32872a3aa16cac9a76ba1816a1ed4cc870a6593cc2e17757750f518b2"
MERMAID_LICENSE = f"https://cdn.jsdelivr.net/npm/mermaid@{MERMAID_VERSION}/LICENSE"

PLANTUML_VERSION = "1.2026.8"
PUML_TGZ = f"https://registry.npmjs.org/@plantuml/core/-/core-{PLANTUML_VERSION}.tgz"
PUML_INTEGRITY = "sha512-md2wGuaIJnAq1yKkedSpQE68cLsvZvctwzWHkDAnC3DTVLe/MSd/2vr4ETwr6jtc1av8cdxCohFuW4VGejMHyw=="
PUML_MEMBERS = {
    "package/plantuml.js", "package/viz-global.js", "package/themes.js", "package/openiconic.js",
    "package/emoji.js", "package/LICENSE", "package/package.json",
}
PUML_JAR_URL = (
    f"https://repo1.maven.org/maven2/net/sourceforge/plantuml/plantuml-mit/{PLANTUML_VERSION}/"
    f"plantuml-mit-{PLANTUML_VERSION}.jar"
)
PUML_JAR_SHA256 = "8a171e8941d1f68f4ec28f5c180a4bf8d54a2cd679348370d4ba59fc9fb910e3"
TEMURIN_JRE_URL = (
    "https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.12.1%2B1/"
    "OpenJDK21U-jre_x64_windows_hotspot_21.0.12.1_1.zip"
)
TEMURIN_JRE_SHA256 = "d35f31e712f0fcf6ac5a093edc90204fbff22f720ba3950bd09d331d5e621636"

INTER_ZIP = "https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip"
INTER_ZIP_SHA256 = "9883fdd4a49d4fb66bd8177ba6625ef9a64aa45899767dde3d36aa425756b11e"
INTER_MEMBERS = {
    "extras/ttf/Inter-Regular.ttf": "Inter-Regular.ttf", "extras/ttf/Inter-Italic.ttf": "Inter-Italic.ttf",
    "extras/ttf/Inter-Bold.ttf": "Inter-Bold.ttf", "extras/ttf/Inter-BoldItalic.ttf": "Inter-BoldItalic.ttf",
}
JBM_BASE = "https://raw.githubusercontent.com/JetBrains/JetBrainsMono/v2.304/fonts/ttf/"
JBM_FILES = [f"JetBrainsMono-{s}.ttf" for s in ("Regular", "Italic", "Bold", "BoldItalic")]
SS4_BASE = "https://raw.githubusercontent.com/adobe-fonts/source-serif/4.005R/TTF/"
SS4_FILES = [f"SourceSerif4-{s}.ttf" for s in ("Regular", "It", "Bold", "BoldIt")]
FONT_LICENSES = {
    "Inter-OFL.txt": "https://raw.githubusercontent.com/rsms/inter/v4.1/LICENSE.txt",
    "JetBrainsMono-OFL.txt": "https://raw.githubusercontent.com/JetBrains/JetBrainsMono/v2.304/OFL.txt",
    "SourceSerif4-OFL.md": "https://raw.githubusercontent.com/adobe-fonts/source-serif/4.005R/LICENSE.md",
}


class VendorError(RuntimeError):
    pass


def _log(msg: str) -> None:
    print(msg, flush=True)


def _get(url: str, timeout: int = 180) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except OSError as e:
        raise VendorError(f"download failed: {url}\n  {e}\nCheck your internet connection and retry.") from e


def _sri_ok(data: bytes, integrity: str) -> bool:
    algo, _, b64 = integrity.partition("-")
    return base64.b64encode(hashlib.new(algo, data).digest()).decode() == b64


def _load_lock() -> dict[str, str]:
    try:
        return json.loads(paths.LOCK_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_lock(lock: dict[str, str]) -> None:
    paths.LOCK_FILE.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _verified(name: str, url: str, sha256: str | None, lock: dict[str, str], timeout: int = 180) -> bytes:
    """Download `url`; check against `sha256` or the locked hash; record the hash on first use."""
    data = _get(url, timeout)
    digest = hashlib.sha256(data).hexdigest()
    expected = sha256 or lock.get(name)
    if expected and digest != expected:
        raise VendorError(f"{name}: hash mismatch (expected {expected[:12]}..., got {digest[:12]}...). Refusing to install.")
    if not expected:
        lock[name] = digest
    return data


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(data)
    tmp.replace(path)


def vendor_katex(lock: dict[str, str]) -> None:
    _log(f"KaTeX {KATEX_VERSION} ...")
    data = _get(KATEX_TGZ)
    if not _sri_ok(data, KATEX_INTEGRITY):
        raise VendorError("KaTeX tarball integrity check failed")
    want = {
        "package/LICENSE": "LICENSE", "package/dist/katex.min.js": "katex.min.js",
        "package/dist/katex.min.css": "katex.min.css", "package/dist/contrib/mhchem.min.js": "contrib/mhchem.min.js",
    }
    want.update({f"package/dist/fonts/KaTeX_{f}.woff2": f"fonts/KaTeX_{f}.woff2" for f in KATEX_FONTS})
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        for member, rel in want.items():
            f = tf.extractfile(member)
            if f is None:
                raise VendorError(f"KaTeX tarball is missing {member}")
            _write(paths.KATEX_DIR / rel, f.read())


def vendor_mermaid(lock: dict[str, str]) -> None:
    _log(f"Mermaid {MERMAID_VERSION} (5 MB) ...")
    _write(paths.MERMAID_JS, _verified("mermaid.min.js", MERMAID_URL, MERMAID_SHA256, lock))
    _write(paths.MERMAID_JS.with_name("LICENSE"), _verified("mermaid.LICENSE", MERMAID_LICENSE, None, lock))


def vendor_plantuml_js(lock: dict[str, str]) -> None:
    _log(f"PlantUML JS engine {PLANTUML_VERSION} (8 MB) ...")
    data = _get(PUML_TGZ)
    if not _sri_ok(data, PUML_INTEGRITY):
        raise VendorError("@plantuml/core tarball integrity check failed")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        for m in tf.getmembers():
            if m.name in PUML_MEMBERS:
                f = tf.extractfile(m)
                if f is not None:
                    _write(paths.PLANTUML_DIR / Path(m.name).name, f.read())


def vendor_fonts(lock: dict[str, str]) -> None:
    _log("Fonts: Inter, JetBrains Mono, Source Serif 4 (OFL) ...")
    data = _verified("Inter-4.1.zip", INTER_ZIP, INTER_ZIP_SHA256, lock, timeout=600)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for member, dest in INTER_MEMBERS.items():
            _write(paths.FONTS_DIR / dest, z.read(member))
    for base, files in ((JBM_BASE, JBM_FILES), (SS4_BASE, SS4_FILES)):
        for name in files:
            _write(paths.FONTS_DIR / name, _verified(name, base + name, None, lock))
    for name, url in FONT_LICENSES.items():
        _write(paths.FONTS_DIR / "LICENSES" / name, _verified(name, url, None, lock))


def vendor_plantuml_jar(lock: dict[str, str]) -> None:
    _log(f"PlantUML MIT jar {PLANTUML_VERSION} (18 MB, needs Java 11+) ...")
    data = _verified("plantuml-mit.jar", PUML_JAR_URL, PUML_JAR_SHA256, lock, timeout=300)
    _write(paths.PLANTUML_JAR_DIR / f"plantuml-mit-{PLANTUML_VERSION}.jar", data)


def vendor_jre(lock: dict[str, str]) -> None:
    _log("Portable Temurin 21 JRE (49 MB) ...")
    data = _verified("temurin-jre21.zip", TEMURIN_JRE_URL, TEMURIN_JRE_SHA256, lock, timeout=900)
    tmp = paths.JRE_DIR.with_name("jre_tmp")
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for n in z.namelist():
            p = Path(n)
            if p.is_absolute() or ".." in p.parts:
                raise VendorError("unsafe path in JRE zip")
        z.extractall(tmp)
    root = next(p for p in tmp.iterdir() if (p / "bin" / "java.exe").is_file())
    if paths.JRE_DIR.exists():
        import shutil

        shutil.rmtree(paths.JRE_DIR)
    root.rename(paths.JRE_DIR)
    tmp.rmdir()


def run(*, java: bool = False, jre: bool = False, force: bool = False) -> int:
    status = paths.vendor_status()
    lock = _load_lock()
    steps = [
        ("katex", vendor_katex), ("mermaid", vendor_mermaid), ("plantuml-js", vendor_plantuml_js),
        ("fonts", vendor_fonts),
    ]
    try:
        for key, fn in steps:
            if force or not status.get(key):
                fn(lock)
            else:
                _log(f"{key}: already installed")
        if java and (force or not status["plantuml-jar"]):
            vendor_plantuml_jar(lock)
        if jre and (force or not paths.JRE_DIR.joinpath("bin", "java.exe").is_file()):
            vendor_jre(lock)
    except VendorError as e:
        _save_lock(lock)
        print(f"\nSetup failed: {e}")
        return 1
    _save_lock(lock)
    _log("\nDone. Run `md2doc doctor` to verify.")
    return 0
