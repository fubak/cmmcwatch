#!/usr/bin/env python3
"""Shared HTML/URL sanitizers for untrusted feed and LLM output."""

from __future__ import annotations

import html
import ipaddress
import json
import re
from typing import Any, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup, NavigableString

ALLOWED_ARTICLE_TAGS = frozenset(
    {
        "h2",
        "h3",
        "p",
        "strong",
        "em",
        "b",
        "i",
        "blockquote",
        "ul",
        "ol",
        "li",
        "br",
        "a",
    }
)
ALLOWED_ARTICLE_ATTRS = {"a": frozenset({"href", "title"})}
_UNWRAP_TAGS = frozenset({"html", "body", "span", "div", "section", "article", "font"})
_DROP_TAGS = frozenset({"script", "style", "iframe", "object", "embed", "link", "meta", "svg"})
_HEX_COLOR = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")
_BLOCKED_HOSTS = frozenset(
    {
        "localhost",
        "metadata.google.internal",
        "metadata.internal",
        "169.254.169.254",
    }
)


def is_http_url(url: Optional[str]) -> bool:
    """True when url is an absolute http(s) URL with a host and no userinfo."""
    if not url or not isinstance(url, str):
        return False
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        return False
    if not parsed.netloc or parsed.username:
        return False
    return True


def is_public_http_url(url: Optional[str]) -> bool:
    """http(s) URL whose host is not localhost / link-local / RFC1918 literal."""
    if not is_http_url(url):
        return False
    host = urlparse(url.strip()).hostname
    if not host:
        return False
    lowered = host.lower().rstrip(".")
    if lowered in _BLOCKED_HOSTS or lowered.endswith(".local") or lowered.endswith(".internal"):
        return False
    try:
        ip = ipaddress.ip_address(lowered)
    except ValueError:
        return True
    return bool(ip.is_global)


def sanitize_http_url(url: Optional[str]) -> Optional[str]:
    """Return a stripped http(s) URL, or None if the value is not safe to link."""
    if not is_http_url(url):
        return None
    return url.strip()


def is_safe_hex_color(value: Optional[str]) -> bool:
    if not value or not isinstance(value, str):
        return False
    return bool(_HEX_COLOR.fullmatch(value.strip()))


def sanitize_hex_color(value: Optional[str], fallback: str) -> str:
    if is_safe_hex_color(value):
        return value.strip()
    return fallback


def json_for_script(data: Any) -> str:
    """JSON encode for embedding in a <script> tag (no raw < / > / &)."""
    return json.dumps(data, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def css_safe_image_url(url: Optional[str]) -> Optional[str]:
    """http(s) image URL safe to put inside CSS url(\"…\")."""
    cleaned = sanitize_http_url(url)
    if not cleaned:
        return None
    if any(ch in cleaned for ch in ("'", '"', ")", "<", ">", "\\")):
        return None
    return cleaned


def escape_attr(value: Optional[str]) -> str:
    return html.escape(value or "", quote=True)


def sanitize_article_html(raw: Optional[str]) -> str:
    """Keep a small allowlist of editorial tags; drop scripts and event handlers."""
    if not raw:
        return ""
    soup = BeautifulSoup(raw, "html.parser")
    for tag in list(soup.find_all(True)):
        name = tag.name.lower() if tag.name else ""
        if name in _DROP_TAGS:
            tag.decompose()
            continue
        if name not in ALLOWED_ARTICLE_TAGS:
            if name in _UNWRAP_TAGS:
                tag.unwrap()
            else:
                tag.decompose()
            continue
        allowed = ALLOWED_ARTICLE_ATTRS.get(name, frozenset())
        for attr in list(tag.attrs):
            if attr not in allowed or str(attr).lower().startswith("on"):
                del tag[attr]
        if name == "a":
            href = tag.get("href")
            cleaned = sanitize_http_url(href) if href else None
            if cleaned:
                tag["href"] = cleaned
            elif "href" in tag.attrs:
                del tag["href"]
    if soup.body:
        parts = [
            str(child) for child in soup.body.contents if not isinstance(child, NavigableString) or str(child).strip()
        ]
        return "".join(parts)
    return "".join(str(child) for child in soup.contents)
