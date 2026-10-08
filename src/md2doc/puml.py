"""PlantUML support.

Default backend  : the official @plantuml/core JS engine, running inside the page (no Java, no Graphviz).
Optional backend : `plantuml-mit.jar` through Java, rendered in Python and embedded as inline SVG.
Remote backend   : strictly opt-in (sends the diagram text to a third party).
"""
from __future__ import annotations

import base64
import hashlib
import os
import re
import shutil
import subprocess
import textwrap
import urllib.error
import urllib.request
import zlib
from pathlib import Path

from . import paths

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
MIN_JAVA = 11
DELIM = "<<<PUML-SEP-7f3a>>>"


class PumlError(Exception):
    def __init__(self, user_message: str, detail: str = ""):
        super().__init__(user_message)
        self.user_message, self.detail = user_message, detail


# ---------------------------------------------------------------------------------------------
# Source preparation
# ---------------------------------------------------------------------------------------------
def normalize_puml(src: str) -> str:
    src = textwrap.dedent(src).strip("\n")
    if not re.search(r"^@start\w*", src, re.M):
        src = f"@startuml\n{src}\n@enduml"
    return src


def inject_preamble(src: str, preamble: str) -> str:
    """Insert right after the first @start line, so the author's own skinparam / !theme still win."""
    if not preamble:
        return src
    return re.sub(r"^(@start\w*[^\n]*\n)", lambda m: m.group(1) + preamble + "\n", src, count=1, flags=re.M)


_RISKY = re.compile(r"^\s*!(?:include\w*|import|theme\s+\S+\s+from)\b(?!\s*<)", re.I | re.M)
_LOCAL_INC = re.compile(r"^[ \t]*!include(?:_once)?[ \t]+(?!<|https?:)([^\r\n]+?)[ \t]*$", re.M)
_REMOTE = re.compile(r"^\s*!(?:includeurl|include_many|theme\s+\S+\s+from\s+\S+|include(?:_once)?\s+https?:)", re.I | re.M)


def inline_local_includes(src: str, base: Path, depth: int = 0, cap: int = 200_000) -> str:
    """Replace `!include foo.puml` by the file text when it lives inside `base`. Raises ValueError otherwise."""
    if depth > 5:
        raise ValueError("include depth > 5")

    def repl(m: re.Match) -> str:
        p = (base / m.group(1).strip().strip('"')).resolve()
        if not p.is_relative_to(base.resolve()) or not p.is_file() or p.stat().st_size > cap:
            raise ValueError(f'include not allowed or missing: {m.group(1)}')
        txt = p.read_text(encoding="utf-8")
        txt = re.sub(r"^\s*@(?:start|end)\w*.*$", "", txt, flags=re.M)
        return inline_local_includes(txt, p.parent, depth + 1, cap)

    return _LOCAL_INC.sub(repl, src)


def prepare(src: str, preamble: str, base_dir: Path) -> tuple[str, str | None]:
    """-> (final source, error message or None). Includes are resolved here; remote ones are refused."""
    s = normalize_puml(src)
    if _REMOTE.search(s):
        return s, "Remote includes/themes (!includeurl, http includes, '!theme x from url') are disabled for safety."
    try:
        s = inline_local_includes(s, base_dir)
    except ValueError as e:
        return s, f"PlantUML include blocked: {e}"
    if _RISKY.search(s):  # anything left after inlining that is not a stdlib <...> include
        return s, "Only '!include <stdlib/...>' and '!include file' inside the document folder are allowed."
    return inject_preamble(s, preamble), None


def cache_key(engine: str, version: str, preamble: str, src: str) -> str:
    return hashlib.sha256("\0".join((engine, version, preamble, src)).encode()).hexdigest()


# ---------------------------------------------------------------------------------------------
# Java backend (optional)
# ---------------------------------------------------------------------------------------------
def java_major(java_exe: Path) -> int | None:
    try:
        p = subprocess.run([str(java_exe), "-version"], capture_output=True, text=True, timeout=20,
                           creationflags=CREATE_NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r'version "(\d+)(?:\.(\d+))?', (p.stderr or "") + (p.stdout or ""))
    if not m:
        return None
    major = int(m.group(1))
    return int(m.group(2) or 8) if major == 1 else major


def _registry_homes():
    if os.name != "nt":
        return
    import winreg

    for root in (r"SOFTWARE\JavaSoft", r"SOFTWARE\WOW6432Node\JavaSoft"):
        for sub in ("JDK", "Java Development Kit", "JRE", "Java Runtime Environment"):
            try:
                k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rf"{root}\{sub}")
            except OSError:
                continue
            with k:
                i = 0
                while True:
                    try:
                        ver = winreg.EnumKey(k, i)
                        i += 1
                    except OSError:
                        break
                    try:
                        with winreg.OpenKey(k, ver) as vk:
                            yield Path(winreg.QueryValueEx(vk, "JavaHome")[0])
                    except OSError:
                        pass


def find_java(user_path: str | None = None) -> tuple[Path, int] | None:
    """(java.exe, major) or None. Order: bundled JRE > user setting > JAVA_HOME > PATH > registry."""
    c: list[Path] = [paths.JRE_DIR / "bin" / "java.exe"]
    if user_path:
        c.append(Path(user_path))
    if os.environ.get("JAVA_HOME"):
        c.append(Path(os.environ["JAVA_HOME"]) / "bin" / "java.exe")
    c += [Path(d.strip('"')) / "java.exe" for d in os.environ.get("PATH", "").split(os.pathsep) if d]
    c += [h / "bin" / "java.exe" for h in _registry_homes()]
    seen: set[str] = set()
    for p in c:
        try:
            key = str(p.resolve()).lower()
        except OSError:
            continue
        if key in seen or not p.is_file():
            continue
        seen.add(key)
        m = java_major(p)
        if m and m >= MIN_JAVA:
            return p, m
    return None


def find_dot(user_path: str | None = None) -> Path | None:
    c = [user_path, os.environ.get("GRAPHVIZ_DOT"), shutil.which("dot")]
    for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
        c += [str(p / "bin" / "dot.exe") for p in Path(base).glob("Graphviz*")]
    return next((Path(x) for x in c if x and Path(x).is_file()), None)


def find_jar() -> Path | None:
    if paths.PLANTUML_JAR_DIR.is_dir():
        jars = sorted(paths.PLANTUML_JAR_DIR.glob("*.jar"))
        return jars[-1] if jars else None
    return None


def _run(cmd: list[str], stdin: bytes, timeout: int) -> tuple[int, str, str]:
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         creationflags=CREATE_NO_WINDOW)
    try:
        out, err = p.communicate(stdin, timeout=timeout)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True, creationflags=CREATE_NO_WINDOW)
        p.communicate()
        raise PumlError(f"PlantUML took longer than {timeout} s and was stopped.", "timeout") from None
    return p.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")


def render_java(sources: list[str], *, java: Path, jar: Path, dot: Path | None, timeout: int = 90) -> list[str]:
    """One JVM for the whole document. `sources` are prepared (@startuml ... @enduml at column 0)."""
    if not sources:
        return []
    if dot is None:  # without Graphviz keep class/usecase/component/state diagrams working via Smetana
        sources = [re.sub(r"^(@start\w*[^\n]*\n)", r"\1!pragma layout smetana\n", s, count=1, flags=re.M) for s in sources]
    cmd = [str(java), "-Djava.awt.headless=true", "-XX:TieredStopAtLevel=1", "-XX:+UseSerialGC", "-Xshare:auto",
           "-DPLANTUML_SECURITY_PROFILE=SANDBOX", "-jar", str(jar), "-pipe", "-tsvg", "-charset", "UTF-8",
           "-pipedelimitor", DELIM]
    if dot:
        cmd += ["-graphvizdot", str(dot)]
    stdin = "".join(s.strip("\n") + "\n" for s in sources).encode("utf-8")
    _, out, err = _run(cmd, stdin, timeout)
    chunks = [c.strip() for c in out.split(DELIM)]
    if chunks and not chunks[-1]:
        chunks.pop()
    if len(chunks) != len(sources):
        if len(sources) > 1:  # one process per diagram so errors map to the right block
            return [render_java([s], java=java, jar=jar, dot=dot, timeout=timeout)[0] for s in sources]
        raise PumlError("PlantUML returned no diagram.", err[-500:])
    return chunks


# ---------------------------------------------------------------------------------------------
# Remote backend (opt-in only)
# ---------------------------------------------------------------------------------------------
_STD = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
_PUML = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"
_ENC = str.maketrans(_STD, _PUML)


def plantuml_encode(text: str) -> str:
    co = zlib.compressobj(9, zlib.DEFLATED, -zlib.MAX_WBITS)
    raw = co.compress(text.encode("utf-8")) + co.flush()
    return base64.b64encode(raw).decode("ascii").rstrip("=").translate(_ENC)


def plantuml_decode(s: str) -> str:
    dec = str.maketrans(_PUML, _STD)
    b = s.translate(dec)
    b += "=" * (-len(b) % 4)
    return zlib.decompress(base64.b64decode(b), -zlib.MAX_WBITS).decode("utf-8")


def render_remote(source: str, timeout: int = 20) -> str:
    req = urllib.request.Request(f"https://www.plantuml.com/plantuml/svg/{plantuml_encode(source)}",
                                 headers={"User-Agent": "md2doc"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise PumlError("The online PlantUML server rejected the diagram.", e.read().decode("utf-8", "replace")[:500]) from e
    except OSError as e:
        raise PumlError("The online PlantUML server did not answer.", str(e)) from e


def isolate_svg(svg: str, uid: str) -> str:
    """Make a Python-rendered SVG safe to inline: unique ids, no scripts/handlers/javascript: links."""
    svg = re.sub(r"<\?xml[^>]*\?>", "", svg).strip()
    svg = re.sub(r"<script\b.*?</script>", "", svg, flags=re.S | re.I)
    svg = re.sub(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*')", "", svg, flags=re.I)
    svg = re.sub(r"(xlink:)?href\s*=\s*([\"'])\s*javascript:[^\"']*\2", "", svg, flags=re.I)
    ids = set(re.findall(r'\bid="([^"]+)"', svg))
    for i in sorted(ids, key=len, reverse=True):
        svg = svg.replace(f'id="{i}"', f'id="{uid}-{i}"').replace(f"url(#{i})", f"url(#{uid}-{i})")
        svg = svg.replace(f'href="#{i}"', f'href="#{uid}-{i}"')
    svg = re.sub(r"(<svg\b[^>]*?)\sstyle=\"[^\"]*background:[^\";]*;?[^\"]*\"", r"\1", svg, count=1)
    return svg
