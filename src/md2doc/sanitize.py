"""Allow-list sanitiser for raw HTML embedded in Markdown ('safe' mode)."""
from __future__ import annotations

from collections.abc import Callable

import nh3

TAGS = {
    "a", "abbr", "aside", "b", "blockquote", "br", "caption", "center", "cite", "code", "col", "colgroup", "dd", "del",
    "details", "div", "dl", "dt", "em", "figcaption", "figure", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i", "img",
    "input", "ins", "kbd", "li", "mark", "ol", "p", "pre", "q", "s", "samp", "section", "small", "span", "strong",
    "sub", "summary", "sup", "table", "tbody", "td", "tfoot", "th", "thead", "tr", "u", "ul", "var", "nav", "main",
}
ATTRS = {
    "*": {"class", "id", "title", "lang", "dir", "data-line"},
    "a": {"href"},
    "img": {"src", "alt", "width", "height"},
    "th": {"align", "colspan", "rowspan", "style"},
    "td": {"align", "colspan", "rowspan", "style"},
    "ol": {"start"},
    "input": {"type", "checked", "disabled"},
    "details": {"open"},
    "div": {"align"},
    "p": {"align"},
    "col": {"span", "width"},
}
STYLE_OK = {
    "text-align", "width", "height", "max-width", "float", "margin", "margin-left", "margin-right", "vertical-align",
    "break-before", "break-after", "break-inside", "page-break-before", "page-break-after", "page-break-inside",
}


def sanitize(html: str, resolve_image: Callable[[str], str]) -> str:
    """Clean `html`. Every <img src> is routed through `resolve_image` (jail, sniff, stage)."""

    def attr_filter(tag: str, attr: str, value: str):
        v = value.strip().lower()
        if attr == "href" and v.startswith(("data:", "javascript:", "vbscript:", "file:")):
            return None
        if tag == "input" and attr == "type" and v != "checkbox":
            return None
        if tag == "img" and attr == "src":
            return resolve_image(value)
        return value

    return nh3.clean(
        html,
        tags=TAGS,
        attributes=ATTRS,
        attribute_filter=attr_filter,
        url_schemes={"http", "https", "mailto", "data", "file"},
        filter_style_properties=STYLE_OK,
        link_rel=None,
    )
