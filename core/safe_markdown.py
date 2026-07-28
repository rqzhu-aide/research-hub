"""Render user-visible Markdown through a small HTML allowlist."""

from __future__ import annotations

import html
from html.parser import HTMLParser
from urllib.parse import urlsplit


class _SafeHtml(HTMLParser):
    """Discard unsafe tags, attributes, and link schemes."""

    allowed_tags = {
        "p", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol",
        "li", "strong", "em", "code", "pre", "blockquote", "a", "table", "thead",
        "tbody", "tr", "th", "td",
    }
    void_tags = {"br", "hr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag not in self.allowed_tags:
            return
        rendered: list[str] = []
        if tag == "a":
            values = dict(attrs)
            href = values.get("href") or ""
            parsed = urlsplit(href)
            if (
                parsed.scheme.lower() in {"", "http", "https", "mailto"}
                and not href.startswith("//")
            ):
                rendered.append(f'href="{html.escape(href, quote=True)}"')
                rendered.append('rel="noopener noreferrer"')
        suffix = (" " + " ".join(rendered)) if rendered else ""
        self.parts.append(f"<{tag}{suffix}>")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.allowed_tags and tag not in self.void_tags:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self.parts.append(html.escape(data))

    def get_html(self) -> str:
        return "".join(self.parts)


def render_safe_markdown(source: str, *, extensions: list[str] | None = None) -> str:
    """Render escaped Markdown and sanitize the generated HTML."""

    try:
        import markdown

        generated = markdown.markdown(
            source, extensions=extensions or ["extra", "sane_lists"]
        )
    except Exception:
        return ""
    sanitizer = _SafeHtml()
    sanitizer.feed(generated)
    sanitizer.close()
    return sanitizer.get_html()
