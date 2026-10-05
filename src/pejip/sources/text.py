"""Turn posting HTML into plain text for analysis."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser

_BLOCK_TAGS = frozenset({"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "tr"})


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")
        if tag == "li":
            self.parts.append("- ")

    def handle_endtag(self, tag: str) -> None:
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def html_to_text(markup: str) -> str:
    """Convert (possibly entity-escaped) HTML into readable plain text."""
    if "&lt;" in markup:
        markup = html.unescape(markup)
    parser = _TextExtractor()
    parser.feed(markup)
    parser.close()
    text = "".join(parser.parts).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


_AMOUNT = r"\$\s?(\d{2,3}(?:,\d{3})+|\d{2,3}(?:\.\d)?[kK])"
_RANGE = re.compile(_AMOUNT + r"\s*(?:-|\u2013|\u2014|to)\s*" + _AMOUNT)


def _amount(token: str) -> float:
    if token[-1] in "kK":
        return float(token[:-1]) * 1000
    return float(token.replace(",", ""))


def extract_salary_range(text: str) -> tuple[float, float] | None:
    """Find the first annual-looking ``$low - $high`` range stated in the text."""
    for match in _RANGE.finditer(text):
        low, high = _amount(match.group(1)), _amount(match.group(2))
        if 50_000 <= low <= high:
            return low, high
    return None
