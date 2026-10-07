"""Minimal markup for lesson theory.

The model writes theory with Markdown emphasis, and Jinja would print it
as is, leaving bare asterisks on screen. A full Markdown engine is not worth
it for three styles, and it would be unsafe: theory comes from a language
model, so it is untrusted text.

The order matters: escape everything first, then add the allowed tags.
The reverse order would open an HTML injection.
"""

from __future__ import annotations

import re

from markupsafe import Markup, escape

_BOLD = re.compile(r"\*\*(.+?)\*\*", re.S)
_ITALIC = re.compile(r"(?<![\*\w])\*([^\*\n]+?)\*(?![\*\w])")
_CODE = re.compile(r"`([^`\n]+?)`")


def markup(text: str | None) -> Markup:
    """**bold**, *italic*, `code` and line breaks. Everything else stays plain text."""
    if not text:
        return Markup("")
    safe = str(escape(text))
    safe = _CODE.sub(r"<code>\1</code>", safe)
    safe = _BOLD.sub(r"<strong>\1</strong>", safe)
    safe = _ITALIC.sub(r"<em>\1</em>", safe)
    safe = safe.replace("\n\n", "</p><p>").replace("\n", "<br>")
    return Markup(f"<p>{safe}</p>")
