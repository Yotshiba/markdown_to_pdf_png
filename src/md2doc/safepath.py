"""Path helpers for locations that a document (front matter, includes, images) can name."""
from __future__ import annotations

from pathlib import Path


def is_unc(s: str) -> bool:
    """True for \\\\host\\share, //host/share, /\\host, \\?\\..., \\.\\... (any mix of slash kinds).

    Opening such a path makes Windows connect to a remote host (SMB/NTLM), so they are never read.
    """
    n = str(s).replace("/", "\\")
    return n.startswith("\\\\")


def resolve_within(base: Path, rel: str, *, jail: bool) -> Path | None:
    """Resolve a document-relative path. None for UNC paths, or (when `jail`) for paths leaving `base`."""
    rel = str(rel).strip().strip('"')
    if not rel or is_unc(rel):
        return None
    p = Path(rel)
    p = p if p.is_absolute() else base / p
    if is_unc(str(p)):
        return None
    try:
        p = p.resolve()
    except OSError:
        return None
    if jail and not p.is_relative_to(base.resolve()):
        return None
    return p
