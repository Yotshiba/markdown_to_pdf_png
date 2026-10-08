from __future__ import annotations

import pytest

from md2doc import paths
from md2doc.browser import NoBrowserError, find_browser


def pytest_collection_modifyitems(config, items):
    """Skip browser tests when Edge/Chrome or the vendored renderers are missing."""
    reason = None
    try:
        find_browser()
    except NoBrowserError:
        reason = "no Edge/Chrome installed"
    if reason is None and not all(paths.vendor_status()[k] for k in ("katex", "mermaid", "plantuml-js", "fonts")):
        reason = "renderers not installed: run `md2doc setup`"
    if reason:
        skip = pytest.mark.skip(reason=reason)
        for item in items:
            if "browser" in item.keywords:
                item.add_marker(skip)
