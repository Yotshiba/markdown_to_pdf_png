"""Find a Chromium-based browser (Edge first, then Chrome) without installing anything."""
from __future__ import annotations

import os
from pathlib import Path


class NoBrowserError(RuntimeError):
    pass


def _app_path(exe: str) -> str | None:
    if os.name != "nt":
        return None
    import winreg

    subs = (rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe}",
            rf"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\{exe}")
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for sub in subs:
            try:
                with winreg.OpenKey(root, sub) as k:
                    p, _ = winreg.QueryValueEx(k, None)
                    if p and Path(p).is_file():
                        return p
            except OSError:
                pass
    return None


def find_browser(user_path: str | None = None) -> tuple[str, str]:
    """-> (kind, executable path). Raises NoBrowserError with an actionable message."""
    cands: list[tuple[str, str | None]] = []
    if user_path:
        cands.append(("custom", user_path))
    cands.append(("msedge", _app_path("msedge.exe")))
    for env in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            cands.append(("msedge", str(Path(base, "Microsoft/Edge/Application/msedge.exe"))))
    cands.append(("chrome", _app_path("chrome.exe")))
    for env in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            cands.append(("chrome", str(Path(base, "Google/Chrome/Application/chrome.exe"))))
    for kind, p in cands:
        if p and Path(p).is_file():
            return kind, p
    raise NoBrowserError(
        "Microsoft Edge or Google Chrome was not found. Install one of them, or pass --browser <path to msedge.exe/chrome.exe>."
    )
