"""HTML → plain text. Descriptions are stored as text so the UI never renders source HTML."""

import html
import re

from bs4 import BeautifulSoup

_DROP = ["script", "style", "noscript", "template", "svg", "iframe", "form", "button"]
_BLOCK = [
    "p", "div", "section", "article", "br", "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "table", "tr", "blockquote", "header", "footer",
]  # fmt: skip
_SPACES = re.compile(r"[ \t\r\f\v ]+")
_BLANK_LINES = re.compile(r"\n\s*\n\s*\n+")


def html_to_text(markup: str, *, unescape_first: bool = False) -> str:
    if unescape_first:  # e.g. Greenhouse returns HTML-escaped HTML
        markup = html.unescape(markup)
    soup = BeautifulSoup(markup, "html.parser")
    for tag in soup(_DROP):
        tag.decompose()
    for li in soup.find_all("li"):
        li.insert_before("\n• ")
    for tag in soup.find_all(_BLOCK):
        tag.insert_before("\n")
        tag.insert_after("\n")
    text = soup.get_text()
    lines = [_SPACES.sub(" ", line).strip() for line in text.split("\n")]
    joined = "\n".join(lines)
    return _BLANK_LINES.sub("\n\n", joined).strip()


def clean_text(value: object) -> str | None:
    """Single-line text field from untrusted source data."""
    if not isinstance(value, str):
        return None
    cleaned = _SPACES.sub(" ", html.unescape(value)).strip()
    return cleaned or None
