# PyInstaller spec: one folder holding md2doc-gui.exe (desktop app) and md2doc.exe (console CLI).
# Build with build_exe.bat. Both programs share one set of libraries (MERGE).
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent
SRC = ROOT / "src"
PKG = SRC / "md2doc"
ICON = str(Path(SPECPATH) / "md2doc.ico")

datas = [
    (str(PKG / "web"), "md2doc/web"),
    (str(PKG / "themes"), "md2doc/themes"),
    (str(PKG / "vendor"), "md2doc/vendor"),  # KaTeX, Mermaid, PlantUML (+ jar), fonts: filled by `md2doc setup`
    (str(PKG / "vendor.lock.json"), "md2doc"),
]
for required in ("vendor/katex/katex.min.js", "vendor/mermaid/mermaid.min.js", "vendor/plantuml-js/plantuml.classic.js", "vendor/fonts/Inter-Regular.ttf"):
    if not (PKG / required).is_file():
        raise SystemExit(f"missing {required}: run build_exe.bat (it runs `md2doc setup` first)")

hidden = collect_submodules("md2doc") + collect_submodules("pygments") + collect_submodules("mdit_py_plugins")
common_excludes = ["tkinter", "matplotlib", "numpy", "scipy", "pytest", "IPython", "pypdfium2", "setuptools"]

# ---- console CLI: needs Playwright (its driver ships node.exe) but no Qt
a_cli = Analysis(
    [str(Path(SPECPATH) / "entry_cli.py")], pathex=[str(SRC)],
    datas=datas + collect_data_files("playwright"), hiddenimports=hidden,
    excludes=common_excludes + ["PySide6", "shiboken6"],
)
# ---- desktop app: needs Qt WebEngine, never imports Playwright (exports run md2doc.exe)
a_gui = Analysis(
    [str(Path(SPECPATH) / "entry_gui.py")], pathex=[str(SRC)],
    datas=datas, hiddenimports=hidden,
    excludes=common_excludes + ["playwright", "greenlet", "pyee"],
)
MERGE((a_cli, "entry_cli", "md2doc"), (a_gui, "entry_gui", "md2doc-gui"))

pyz_cli, pyz_gui = PYZ(a_cli.pure), PYZ(a_gui.pure)
exe_cli = EXE(pyz_cli, a_cli.scripts, [], exclude_binaries=True, name="md2doc", console=True, icon=ICON)
exe_gui = EXE(pyz_gui, a_gui.scripts, [], exclude_binaries=True, name="md2doc-gui", console=False, icon=ICON)
COLLECT(exe_cli, a_cli.binaries, a_cli.datas, exe_gui, a_gui.binaries, a_gui.datas,
        strip=False, upx=False, name="md2doc")
