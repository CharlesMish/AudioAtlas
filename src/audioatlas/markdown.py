"""Small Markdown-safety helpers for user-controlled report labels."""

from __future__ import annotations

import re
from typing import Any

_MARKDOWN_PUNCTUATION = re.compile(r"([\\`*_\[\]<>|])")
_BACKTICK_RUN = re.compile(r"`+")


def markdown_text(value: Any) -> str:
    """Return a single-line Markdown text value with structural punctuation escaped."""

    text = str(value).replace("\r", " ").replace("\n", " ")
    return _MARKDOWN_PUNCTUATION.sub(r"\\\1", text)


def markdown_code_span(value: Any) -> str:
    """Wrap a single-line value in a code span that tolerates embedded backticks."""

    text = str(value).replace("\r", " ").replace("\n", " ")
    runs = [len(match.group(0)) for match in _BACKTICK_RUN.finditer(text)]
    if not runs:
        return f"`{text}`"
    fence = "`" * (max(runs) + 1)
    return f"{fence} {text} {fence}"
